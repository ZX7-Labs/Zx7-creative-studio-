"""Scripted local-model protocol fixtures + real codecs, not live LLM artistry."""
import copy
import importlib.util
import json
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

from studio_next.body_creative_session import SESSION_SYSTEM
from studio_next.body_service import LocalBodyCoordinator
from studio_next.body_signal import BodyAuthority,LiveBodySignal
from studio_next.providers import LocalCreativeModel,LocalModelSettings


class SessionControlRegression(unittest.TestCase):
    def test_owner_stop_during_inference_prevents_new_body_action_and_snapshot_refuses_active_session(self):
        entered=threading.Event();release=threading.Event()
        class SlowModel:
            def decide(self,context):
                entered.set();release.wait(4)
                return {'action':'submit','arguments':{'film_ir':execution('no-plan.json')},'reason':'Fixture only'}
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,creative_model=SlowModel())
            try:
                created=c.creative_sessions.create('film','Synthetic stop test',{})
                self.assertTrue(entered.wait(3))
                with self.assertRaisesRegex(RuntimeError,'creative session'):
                    c.create_recovery_snapshot(Path(root)/'snapshot.tar.gz')
                c.creative_sessions.stop(created['session_id']);release.set()
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    state=c.creative_sessions.inspect(created['session_id'])
                    if state['status']=='stopped':break
                    time.sleep(.02)
                self.assertEqual(state['status'],'stopped')
                self.assertEqual(state['jobs'],[])
                self.assertEqual(state['events'],[])
            finally:release.set();c.close()

    def test_model_adapter_cannot_mutate_owner_facts_or_prior_receipts(self):
        from studio_next.body_creative_session import CreativeSessions
        class MutatingAdapter:
            calls = 0
            last_call_usage = None
            def decide(self, context):
                self.calls += 1
                if self.calls == 1:
                    context['owner_facts']['product']['claim'] = 'forged'
                    self.last_call_usage = {'prompt_tokens': 12, 'completion_tokens': 4,
                                            'total_tokens': 16, 'private': 'discard'}
                    return {'action':'assets','arguments':{},'reason':'Fixture only'}
                context['recent_events'][0]['result']['assets'].append({'forged':True})
                context['submitted_jobs'].append('foreign-job')
                self.last_call_usage = {'prompt_tokens': True, 'completion_tokens': -1,
                                        'total_tokens': 1000000001}
                return {'action':'finish','arguments':{'summary':'Fixture only'},'reason':'Fixture only'}
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root)
            manager=CreativeSessions(c,MutatingAdapter(),max_turns=2)
            try:
                created=manager.create('film','Synthetic integrity test',{'product':{'claim':'owner fact'}})
                manager.close()
                state=manager.inspect(created['session_id'])
                self.assertEqual(state['facts'],{'product':{'claim':'owner fact'}})
                self.assertEqual(state['jobs'],[])
                self.assertEqual(state['events'][0]['result']['assets'],[])
                self.assertEqual(state['status'],'model_finished')
                self.assertEqual(len(state['events']),2)
                first, second = [event['model_call'] for event in state['events']]
                self.assertEqual(first['provider_reported_token_usage'],
                                 {'prompt_tokens':12,'completion_tokens':4,'total_tokens':16})
                self.assertIsNone(second['provider_reported_token_usage'])
                for event in state['events']:
                    self.assertGreaterEqual(event['model_call']['measured_model_wall_ms'],0)
                    self.assertFalse(event['model_call']['token_usage_independently_verified'])
                    self.assertTrue(event['model_call']['model_response_returned'])
                    self.assertGreaterEqual(event['measured_dispatch_wall_ms'],0)
                self.assertIsNone(state['pending_model_call'])
            finally:manager.close();c.close()

    def test_resume_pending_decision_keeps_known_or_unknown_model_measurement(self):
        from studio_next.body_creative_session import CreativeSessions
        from unittest.mock import patch
        class NoNewInference:
            def decide(self,context):
                raise AssertionError('Already persisted decision must not be inferred twice')
        for recorded in (None, {'measured_model_wall_ms':1.25,
                               'provider_reported_token_usage':{'total_tokens':21},
                               'token_usage_independently_verified':False,
                               'model_response_returned':True}):
            with self.subTest(recorded=recorded), tempfile.TemporaryDirectory() as root:
                c=LocalBodyCoordinator(root)
                manager=CreativeSessions(c,NoNewInference(),max_turns=1)
                try:
                    with patch.object(manager,'_queue'):
                        created=manager.create('film','Synthetic replay test',{})
                    state=manager.inspect(created['session_id'])
                    state['pending']={'action':'finish','arguments':{'summary':'Persisted intent'},'reason':'Fixture only'}
                    if recorded is None:
                        state.pop('pending_model_call',None) # legacy persisted session
                    else:
                        state['pending_model_call']=recorded
                    manager._save(state)
                    manager.resume_pending();manager.close()
                    result=manager.inspect(created['session_id'])
                    self.assertEqual(result['status'],'model_finished')
                    self.assertEqual(len(result['events']),1)
                    self.assertEqual(result['events'][0]['model_call'],recorded)
                    self.assertIsNone(result['pending_model_call'])
                finally:manager.close();c.close()

    def test_resume_rejects_changed_model_settings_and_media_permission(self):
        from studio_next.body_creative_session import CreativeSessions
        from studio_next.nvidia_model import NvidiaCreativeModel, NvidiaModelSettings
        from unittest.mock import patch

        class LocalFixture(LocalCreativeModel):
            calls=0
            def decide(self, context):
                self.calls+=1
                return {'action':'finish','arguments':{'summary':'Fixture only'},'reason':'Fixture only'}

        class CloudFixture(NvidiaCreativeModel):
            calls=0
            def decide(self, context):
                self.calls+=1
                return {'action':'finish','arguments':{'summary':'Fixture only'},'reason':'Fixture only'}

        controls = (
            (LocalFixture(LocalModelSettings(sampling={'temperature':0.0})),
             LocalFixture(LocalModelSettings(sampling={'temperature':1.0})), False),
            (LocalFixture(LocalModelSettings(timeout_seconds=10)),
             LocalFixture(LocalModelSettings(timeout_seconds=20)), False),
            (CloudFixture(NvidiaModelSettings(max_tokens=1024)),
             CloudFixture(NvidiaModelSettings(max_tokens=2048)), False),
            (CloudFixture(allow_image_upload=False),
             CloudFixture(allow_image_upload=True), False),
            (LocalFixture(LocalModelSettings(sampling={'temperature':0.0,'seed':7})),
             LocalFixture(LocalModelSettings(sampling={'seed':7,'temperature':0.0})), True),
        )
        for original, resumed, matches in controls:
            with self.subTest(original=original.settings, matches=matches), tempfile.TemporaryDirectory() as root:
                coordinator=LocalBodyCoordinator(root)
                first=CreativeSessions(coordinator,original,max_turns=1)
                try:
                    with patch.object(first,'_queue'):
                        created=first.create('film','Synthetic matched experiment',{})
                    first.close()
                    second=CreativeSessions(coordinator,resumed,max_turns=1)
                    try:
                        second.resume_pending();second.close()
                        state=second.inspect(created['session_id'])
                        self.assertEqual(state['status'],'model_finished' if matches else 'blocked')
                        self.assertEqual(len(state['events']),1 if matches else 0)
                        self.assertEqual(resumed.calls,1 if matches else 0)
                        self.assertEqual(state['jobs'],[])
                    finally:second.close()
                finally:first.close();coordinator.close()

    def test_legacy_active_session_without_configuration_receipt_is_preserved(self):
        from studio_next.body_creative_session import CreativeSessions
        from unittest.mock import patch
        class NoInference:
            def decide(self, context):
                raise AssertionError('Unmatched legacy configuration must not infer')
        with tempfile.TemporaryDirectory() as root:
            coordinator=LocalBodyCoordinator(root)
            manager=CreativeSessions(coordinator,NoInference(),max_turns=1)
            try:
                with patch.object(manager,'_queue'):
                    created=manager.create('film','Synthetic legacy session',{'keep':'original fact'})
                original=manager.inspect(created['session_id'])
                original['model_identity'].pop('model_config_sha256',None)
                original['pending']={'action':'finish','arguments':{'summary':'Original intent'},'reason':'Fixture only'}
                manager._save(original)
                manager.resume_pending();manager.close()
                state=manager.inspect(created['session_id'])
                self.assertEqual(state['status'],'blocked')
                self.assertIn('Legacy session',state['error'])
                self.assertEqual(state['pending'],original['pending'])
                self.assertEqual(state['facts'],original['facts'])
                self.assertEqual(state['events'],[])
            finally:manager.close();coordinator.close()

    def test_mid_session_model_config_drift_blocks_before_dispatch(self):
        from studio_next.body_creative_session import CreativeSessions
        class MutatingFixture(LocalCreativeModel):
            def decide(self, context):
                self.settings.sampling['temperature']=1.0
                return {'action':'finish','arguments':{'summary':'Fixture only'},'reason':'Fixture only'}
        with tempfile.TemporaryDirectory() as root:
            coordinator=LocalBodyCoordinator(root)
            manager=CreativeSessions(coordinator,MutatingFixture(
                LocalModelSettings(sampling={'temperature':0.0})),max_turns=1)
            try:
                created=manager.create('film','Synthetic settings drift',{})
                manager.close()
                state=manager.inspect(created['session_id'])
                self.assertEqual(state['status'],'blocked')
                self.assertEqual(state['events'],[])
                self.assertEqual(state['jobs'],[])
                self.assertTrue(state['pending_model_call']['model_response_returned'])
            finally:manager.close();coordinator.close()

    def test_failed_inference_retains_elapsed_but_not_stale_token_claim(self):
        from studio_next.body_creative_session import CreativeSessions
        class FailingAdapter:
            last_call_usage={'total_tokens':42}
            def decide(self,context):
                raise OSError('Fixture transport failure')
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root)
            manager=CreativeSessions(c,FailingAdapter(),max_turns=1)
            try:
                created=manager.create('film','Synthetic failure test',{})
                manager.close()
                result=manager.inspect(created['session_id'])
                self.assertEqual(result['status'],'blocked')
                self.assertEqual(result['events'],[])
                self.assertIsNone(result['pending'])
                call=result['pending_model_call']
                self.assertGreaterEqual(call['measured_model_wall_ms'],0)
                self.assertFalse(call['model_response_returned'])
                self.assertIsNone(call['provider_reported_token_usage'])
            finally:manager.close();c.close()

    def test_nonfinite_model_response_is_persisted_as_blocked_not_left_running(self):
        class InvalidModel:
            def decide(self,context):
                return {'action':'finish','arguments':{'summary':float('nan')},'reason':'Invalid fixture'}
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,creative_model=InvalidModel())
            try:
                created=c.creative_sessions.create('film','Test invalid structured model output',{})
                c.creative_sessions.close()
                state=c.creative_sessions.inspect(created['session_id'])
                self.assertEqual(state['status'],'blocked')
                self.assertIsNone(state['pending'])
                self.assertEqual(state['jobs'],[])
            finally:c.close()


def tiny_motion(gain):
    return {'project':{'title':'Protocol fixture','creative_intent':'Test an original pixel and sound change',
        'width':320,'height':320,'voice':'no_voice','background':'#172636'},
        'assets':[{'id':'shape','status':'verified','rights':'generated_original',
                   'location':'inline://shape','artwork':{'size':[64,64],
                   'items':[{'type':'rect','box':[0,0,63,63],'fill':'#F3B454'}]}}],
        'shots':[{'id':'one','purpose':'Exercise real timed pixels and authored sound',
                  'duration_seconds':.5,'narration':'','asset_refs':['shape'],'fact_refs':[],
                  'layers':[{'asset':'shape','x':160,'y':160}],
                  'cues':[{'type':'synth','at':0,'seconds':.5,'gain':gain,'noise_gain':0,'seed':321,
                    'partials':[{'start_hz':647,'end_hz':647,'amplitude':1,'phase_radians':0}],
                    'envelope':[[0,1],[.5,1]]}]}],
        'tool_graph':[{'id':'paint','tool_id':'motion_studio.composite','purpose':'Draw actual original test art',
                       'inputs':{},'depends_on':[]}]}


def execution(plan_path,second_path=None):
    nodes=[{'id':'original','tool_id':'body.motion2d','purpose':'Actual original test render',
            'inputs':{'original_film_ir':plan_path,'out':'original.mp4','width':320,'fps':12},'depends_on':[]}]
    if second_path:
        nodes.append({'id':'revised','tool_id':'body.motion2d','purpose':'Test revised sound amplitude',
            'inputs':{'original_film_ir':second_path,'out':'revised.mp4','width':320,'fps':12},'depends_on':[]})
    return {'project':{'creative_intent':'Protocol fixture for actual original and revised media'},
            'owner_facts':{},'shots':[{'id':'one','purpose':'Physical media verification','duration_seconds':.5}],
            'assets':[],'tool_graph':nodes}


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe') and all(
    importlib.util.find_spec(x) for x in ('numpy','PIL','fontTools')),'Real FFmpeg and motion dependencies required')
class CreativeSessionPhysicalAcceptance(unittest.TestCase):
    def test_ordinary_brief_local_http_model_contract_real_render_observation_and_revision(self):
        # This server returns known test decisions, not a neural model response.
        requests=[]; paths=[]; jobs=[]
        def choose(context):
            step=len(requests)-1
            if step==0:return 'describe',{'tool_id':'body.motion2d'}
            if step==1:
                schema=context['recent_events'][-1]['result']['document_contracts']['original_film_ir']
                self.assertIn('cues',schema['json_schema']['properties']['shots']['items']['properties'])
                return 'author_plan',{'tool_id':'body.motion2d','document':tiny_motion(.2)}
            if step==2:
                paths.append(context['recent_events'][-1]['result']['path'])
                return 'submit',{'film_ir':execution(paths[0])}
            if step==3:
                jobs.append(context['recent_events'][-1]['result']['job_id'])
                return 'wait',{'job_id':jobs[0],'seconds':10}
            if step==4:return 'read',{'tool_id':'body.full_decode','inputs':{'source':'original.mp4'}}
            if step==5:
                self.assertTrue(context['recent_events'][-1]['result']['full_picture_and_sound_decoder_completed'])
                return 'author_plan',{'tool_id':'body.motion2d','document':tiny_motion(.1)}
            if step==6:
                paths.append(context['recent_events'][-1]['result']['path'])
                return 'submit',{'film_ir':execution(paths[0],paths[1])}
            if step==7:
                jobs.append(context['recent_events'][-1]['result']['job_id'])
                return 'wait',{'job_id':jobs[1],'seconds':10}
            if step==8:
                result=context['recent_events'][-1]['result']
                self.assertEqual(result['status'],'completed',result)
                self.assertIn('original',result['result']['reused'])
                return 'read',{'tool_id':'body.full_decode','inputs':{'source':'revised.mp4'}}
            return 'finish',{'summary':'Synthetic protocol test rendered and revised. No artistic acceptance claimed.'}
        class FixtureServer(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(payload)
                action,args=choose(json.loads(payload['messages'][1]['content']))
                decision={'action':action,'arguments':args,'reason':'Scripted protocol regression fixture'}
                raw=json.dumps({'choices':[{'message':{'content':json.dumps(decision)},'finish_reason':'stop'}]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),FixtureServer)
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            with tempfile.TemporaryDirectory() as root:
                model=LocalCreativeModel(LocalModelSettings(base_url='http://127.0.0.1:'+str(server.server_port),
                    model_id='scripted-protocol-fixture',timeout_seconds=20),system_prompt=SESSION_SYSTEM)
                c=LocalBodyCoordinator(root,creative_model=model)
                try:
                    created=c.creative_sessions.create('film','Test only: create, observe and revise original sound.',{})
                    deadline=time.monotonic()+65
                    while time.monotonic()<deadline:
                        state=c.creative_sessions.inspect(created['session_id'])
                        if state['status'] not in ('queued','running'):break
                        time.sleep(.1)
                    self.assertEqual(state['status'],'model_finished',state)
                    self.assertFalse(state['artistic_quality_approved'])
                    self.assertFalse(state['audio_semantically_reviewed'])
                    self.assertEqual(state['model_identity']['model_id'],'scripted-protocol-fixture')
                    self.assertEqual(len(state['jobs']),2)
                    self.assertFalse([event for event in state['events'] if 'error' in event['result']])
                    import numpy as np
                    def rms(path):
                        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-ac','1','pipe:1'],timeout=15)
                        return float(np.sqrt(np.mean(np.frombuffer(raw,dtype='<f4')**2)))
                    workspace=c._workspace('film')
                    self.assertAlmostEqual(rms(workspace/'original.mp4')/rms(workspace/'revised.mp4'),2,delta=.15)
                finally:c.close()
                reopened=LocalBodyCoordinator(root)
                try:
                    from studio_next.body_creative_session import CreativeSessions
                    manager=CreativeSessions(reopened,model)
                    self.assertEqual(manager.inspect(created['session_id'])['status'],'model_finished')
                    manager.close()
                finally:reopened.close()
        finally:server.shutdown();server.server_close();t.join(3)

    def test_replayed_host_submission_after_receipt_loss_reuses_one_original_job(self):
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,execute=lambda ir,w:{'status':'blocked','errors':['Fixture only']})
            try:
                signal=LiveBodySignal(c,authority=BodyAuthority(workspace_ids=frozenset({'film'}),
                    operations=frozenset({'submit'}),tool_access=frozenset({'read','write'})))
                ir=execution('missing.json')
                args={'workspace_id':'film','film_ir':ir}
                first=signal.command('submit',args,submission_key='a'*64)
                replay=signal.command('submit',args,submission_key='a'*64)
                self.assertEqual(first['job_id'],replay['job_id'])
                self.assertTrue(replay['existing_submission_reused'])
                changed=copy.deepcopy(ir);changed['project']['creative_intent']='Changed original intent'
                with self.assertRaisesRegex(ValueError,'conflicts'):
                    signal.command('submit',{'workspace_id':'film','film_ir':changed},submission_key='a'*64)
            finally:c.close()


if __name__=='__main__':unittest.main()
