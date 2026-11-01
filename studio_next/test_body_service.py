import io
import hashlib
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from studio_next.body_service import LocalBodyCoordinator,make_body_http_handler


def plan():
    return {"project":{"creative_intent":"Original independently directed cinema"},
            "shots":[{"id":"art-1","purpose":"Actual artist-chosen shot",
                      "duration_seconds":2.31}],
            "tool_graph":[{"id":"render","tool_id":"body.inspect",
                           "inputs":{"source":"actual.mp4"},"depends_on":[]}]}


class IndependentLocalCreativeServiceTests(unittest.TestCase):
    def test_real_job_queue_and_restart_do_not_rewrite_approved_art(self):
        with tempfile.TemporaryDirectory() as root:
            seen=[]
            def fake(original,workspace):
                seen.append((original,workspace))
                return {"status":"all_tool_results_verified",
                        "completed":["render"],"reused":[],"video_proven":False}
            c=LocalBodyCoordinator(root,execute=fake)
            try:
                created=c.submit(plan(),workspace_id="one-original-studio-project",
                                 job_id="shot-1")
                self.assertEqual(created["job_id"],"shot-1")
                for _ in range(100):
                    if c.inspect("shot-1")["status"]=="completed":break
                    time.sleep(.01)
                self.assertEqual(c.inspect("shot-1")["status"],"completed")
                self.assertEqual(seen[0][0],plan())
                with self.assertRaisesRegex(ValueError,"already exists"):
                    c.submit(plan(),workspace_id="one-original-studio-project",
                             job_id="shot-1")
                self.assertFalse(c.queue("shot-1"))
            finally:
                c.close()
            recovered=LocalBodyCoordinator(root,execute=fake)
            try:
                self.assertEqual(recovered.pending_restart(),0)
                self.assertEqual(recovered.inspect("shot-1")["attempts"],1)
            finally:recovered.close()

    def test_desktop_job_browser_and_explicit_retries_reuse_same_original_plan(self):
        with tempfile.TemporaryDirectory() as root:
            executed=[]
            def run(ir,workspace):
                executed.append(ir)
                return {"status":"blocked","errors":["missing originally licensed actor footage"],
                        "video_proven":False}
            owner=LocalBodyCoordinator(root,execute=run)
            try:
                owner.submit(plan(),workspace_id="independent-film",job_id="film-a")
                for _ in range(150):
                    if owner.inspect("film-a")["status"]=="blocked":break
                    time.sleep(.01)
                items=owner.list_jobs()
                self.assertEqual(items["jobs"][0]["job_id"],"film-a")
                self.assertEqual(items["jobs"][0]["status"],"blocked")
                with self.assertRaisesRegex(ValueError,"bounded"):
                    owner.list_jobs(limit=10000)
                retried=owner.retry_job("film-a")
                self.assertTrue(retried["original_film_ir_unchanged"])
                for _ in range(150):
                    if owner.inspect("film-a")["attempts"]>=2 and (
                            owner.inspect("film-a")["status"]=="blocked"):break
                    time.sleep(.01)
                self.assertEqual(executed,[plan(),plan()])
                self.assertEqual(owner.inspect("film-a")["attempts"],2)
            finally:owner.close()

    def test_studio_host_denies_linked_owner_workspaces(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            approved=root/"real-studio"
            approved.mkdir()
            linked=root/"external"
            linked.symlink_to(approved,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,"filesystem link"):
                LocalBodyCoordinator(linked,execute=lambda p,w:{"status":"blocked"})
            for name in ("body-service.lock","body-jobs.sqlite3","projects"):
                with self.subTest(name=name):
                    alias=approved/name
                    alias.symlink_to(root/"other-artist-files")
                    with self.assertRaisesRegex(ValueError,"filesystem link"):
                        LocalBodyCoordinator(approved,execute=lambda p,w:{"status":"blocked"})
                    alias.unlink()

    def test_one_process_owns_same_original_workspace_at_a_time(self):
        with tempfile.TemporaryDirectory() as root:
            first=LocalBodyCoordinator(root,execute=lambda ir,path:{
                "status":"all_tool_results_verified"})
            try:
                with self.assertRaisesRegex(RuntimeError,"already owned"):
                    LocalBodyCoordinator(root,execute=lambda ir,path:{})
            finally:first.close()
            second=LocalBodyCoordinator(root,execute=lambda ir,path:{
                "status":"all_tool_results_verified"})
            second.close()

    def test_blocked_original_art_keeps_reasons_never_fakes_movie(self):
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,execute=lambda ir,workspace:{
                "status":"blocked","errors":["missing real footage"],
                "completed":[],"video_proven":False})
            try:
                c.submit(plan(),workspace_id="project")
                for _ in range(100):
                    with c._connect() as db:
                        status=db.execute("SELECT status FROM jobs").fetchone()[0]
                    if status=="blocked":break
                    time.sleep(.01)
                with c._connect() as db:
                    identity=db.execute("SELECT id FROM jobs").fetchone()[0]
                result=c.inspect(identity)
                self.assertEqual(result["status"],"blocked")
                self.assertFalse(result["result"]["video_proven"])
            finally:c.close()

    def test_two_concurrent_jobs_cannot_overwrite_one_original_project(self):
        with tempfile.TemporaryDirectory() as root:
            start=threading.Event()
            release=threading.Event()
            gate=threading.Lock()
            in_progress=[0]
            simultaneous=[0]
            def actual_artistic_work(ir,workspace):
                with gate:
                    in_progress[0]+=1
                    simultaneous[0]=max(simultaneous[0],in_progress[0])
                start.set()
                release.wait(timeout=3)
                try:
                    return {"status":"all_tool_results_verified",
                            "completed":["artist-shot"],"video_proven":False}
                finally:
                    with gate:in_progress[0]-=1
            service=LocalBodyCoordinator(root,execute=actual_artistic_work,workers=2)
            try:
                service.submit(plan(),workspace_id="same-film",job_id="artist-one")
                self.assertTrue(start.wait(timeout=2))
                service.submit(plan(),workspace_id="same-film",job_id="artist-two")
                time.sleep(.05)
                self.assertEqual(simultaneous[0],1)
                release.set()
                for _ in range(200):
                    if (service.inspect("artist-one")["status"]=="completed" and
                        service.inspect("artist-two")["status"]=="completed"):break
                    time.sleep(.01)
                self.assertEqual(simultaneous[0],1)
                self.assertEqual(service.inspect("artist-two")["status"],"completed")
            finally:
                release.set()
                service.close()

    def test_interrupted_job_restarts_from_original_sqlite_not_new_story(self):
        with tempfile.TemporaryDirectory() as root:
            first=LocalBodyCoordinator(root)
            try:
                root_name="same-owner-original"
                with first._connect() as db:
                    db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)",
                        ("interrupted",root_name,json.dumps(plan()),"running",
                         1,None,time.time()))
            finally:first.close()
            observed=[]
            def resumed(ir,workspace):
                observed.append(ir)
                return {"status":"all_tool_results_verified",
                        "reused":["artwork"],"video_proven":False}
            second=LocalBodyCoordinator(root,execute=resumed)
            try:
                self.assertEqual(second.pending_restart(),1)
                for _ in range(100):
                    if second.inspect("interrupted")["status"]=="completed":break
                    time.sleep(.01)
                self.assertEqual(observed,[plan()])
                self.assertEqual(second.inspect("interrupted")["attempts"],2)
                self.assertEqual(second.inspect("interrupted")["status"],"completed")
            finally:second.close()

    def test_immediate_crash_restart_recovers_idempotent_scene_before_old_lease_expires(self):
        from studio_next.durable_graph import DurableFilmGraph
        with tempfile.TemporaryDirectory() as root:
            original=LocalBodyCoordinator(root)
            try:
                workspace=original._workspace("film")
                workspace.mkdir(parents=True)
                store=DurableFilmGraph(workspace/"production.sqlite3")
                act,_,worker=store.start_or_reuse("original-film","scene_001",
                    "fixed-director-and-art-hash",trusted_idempotent=True,
                    existing_result_verifier=lambda _:True,lease_seconds=86400)
                self.assertEqual(act,"execute")
                with original._connect() as db:
                    db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)",
                        ("interrupted-real-art","film",json.dumps(plan()),
                         "running",1,None,time.time()))
                with sqlite3.connect(workspace/"production.sqlite3") as db:
                    old_lease=db.execute("SELECT lease_until FROM node_results").fetchone()[0]
                self.assertGreater(old_lease,time.time()+3600)
            finally:
                original.close()
            performed=[]
            def artist_resumes_same_scene(ir,workspace):
                resumed=DurableFilmGraph(workspace/"production.sqlite3")
                action,cached,token=resumed.start_or_reuse(
                    "original-film","scene_001","fixed-director-and-art-hash",
                    trusted_idempotent=True,existing_result_verifier=lambda _:True,
                    lease_seconds=3600)
                performed.append(action)
                resumed.complete("original-film","scene_001",
                                 "fixed-director-and-art-hash",token,{"original":"same"})
                return {"status":"all_tool_results_verified",
                        "completed":["scene_001"],"video_proven":False}
            restarted=LocalBodyCoordinator(root,execute=artist_resumes_same_scene)
            try:
                self.assertEqual(restarted.pending_restart(),1)
                for _ in range(100):
                    if restarted.inspect("interrupted-real-art")["status"]=="completed":
                        break
                    time.sleep(.01)
                self.assertEqual(restarted.inspect("interrupted-real-art")["status"],
                                 "completed")
                self.assertEqual(performed,["execute"])
                self.assertEqual(restarted.inspect("interrupted-real-art")["attempts"],2)
            finally:
                restarted.close()

    def test_crash_restart_never_replays_uncertain_nonidempotent_video_generation(self):
        from studio_next.durable_graph import DurableFilmGraph,RecoveryBlocked
        with tempfile.TemporaryDirectory() as root:
            initial=LocalBodyCoordinator(root)
            try:
                place=initial._workspace("film");place.mkdir()
                ledger=DurableFilmGraph(place/"production.sqlite3")
                ledger.start_or_reuse("film","video_diffusion","prompt-hash",
                    trusted_idempotent=False,
                    existing_result_verifier=lambda _:True,lease_seconds=999999)
                with initial._connect() as db:
                    db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)",
                        ("do-not-regenerate","film",json.dumps(plan()),
                         "running",1,None,time.time()))
            finally:initial.close()
            restart=LocalBodyCoordinator(root,execute=lambda ir,w:{
                "status":"all_tool_results_verified"})
            try:
                ledger=DurableFilmGraph(restart._workspace("film")/"production.sqlite3")
                with self.assertRaisesRegex(RecoveryBlocked,"reconciliation"):
                    ledger.start_or_reuse("film","video_diffusion","prompt-hash",
                        trusted_idempotent=False,
                        existing_result_verifier=lambda _:True,lease_seconds=3600)
            finally:restart.close()

    def test_api_exposes_actual_stored_tool_progress_not_invented_percent(self):
        with tempfile.TemporaryDirectory() as root:
            from studio_next.durable_graph import DurableFilmGraph
            entered=threading.Event()
            release=threading.Event()
            def genuine_coordinator_race(ir,w):
                entered.set()
                if not release.wait(8):
                    raise RuntimeError("Test did not release actual coordinator")
                return {"status":"all_tool_results_verified","completed":[]}
            service=LocalBodyCoordinator(root,execute=genuine_coordinator_race)
            try:
                directory=service._workspace("evidence");directory.mkdir()
                ledger=DurableFilmGraph(directory/"production.sqlite3")
                from studio_next.durable_graph import durable_project_key
                key=durable_project_key(plan(),fact_ids=set(),
                         allowed_access={"read","write"})
                ledger.start_or_reuse(key,"render","shaA",
                    trusted_idempotent=True,
                    existing_result_verifier=lambda _:True,lease_seconds=120)
                service.submit(plan(),workspace_id="evidence",job_id="evidence-job")
                self.assertTrue(entered.wait(4),"Real worker never entered")
                self.assertEqual(service.inspect("evidence-job")["status"],"running")
                state=service.inspect("evidence-job")["actual_tool_progress"]
                self.assertTrue(state["tool_progress_is_actual_sqlite"])
                self.assertEqual(state["observed_tool_states"][0]["node_id"],"render")
                self.assertEqual(state["observed_tool_states"][0]["state"],"running")
                self.assertEqual(state["stage_scope"],
                    "verified_shared_project_lineage_not_single_job_attempt")
                release.set()
                for _ in range(150):
                    if service.inspect("evidence-job")["status"]=="completed":
                        break
                    time.sleep(.01)
                self.assertEqual(service.inspect("evidence-job")["status"],"completed")
                # The fake executor has no signed graph result/project key.
                # A completed job may not claim another attempt's stage cache.
                self.assertFalse(service.inspect("evidence-job")
                                 ["actual_tool_progress"]["tool_progress_is_actual_sqlite"])
            finally:
                release.set()
                service.close()


    def test_two_projects_same_workspace_never_mix_unrelated_stages(self):
        from studio_next.durable_graph import DurableFilmGraph,durable_project_key
        with tempfile.TemporaryDirectory() as root:
            service=LocalBodyCoordinator(root,execute=lambda ir,w:{
                 "status":"all_tool_results_verified","completed":[]})
            try:
                folder=service._workspace("shared-editor")
                folder.mkdir(parents=True,exist_ok=True)
                plan_a=plan()
                plan_b=plan()
                plan_b["project"]={"creative_intent":"Entirely independent other owner's storyboard"}
                plan_b["tool_graph"][0]["id"]="render"
                akey=durable_project_key(plan_a,fact_ids=set(),
                        allowed_access={"read","write"})
                bkey=durable_project_key(plan_b,fact_ids=set(),
                        allowed_access={"read","write"})
                self.assertNotEqual(akey,bkey)
                ledger=DurableFilmGraph(folder/"production.sqlite3")
                ledger.start_or_reuse(akey,"render","sha-original",
                    trusted_idempotent=True,
                    existing_result_verifier=lambda _:True,lease_seconds=120)
                ledger.start_or_reuse(bkey,"render","sha-other",
                    trusted_idempotent=True,
                    existing_result_verifier=lambda _:True,lease_seconds=120)
                service.submit(plan_a,workspace_id="shared-editor",job_id="film-a")
                service.submit(plan_b,workspace_id="shared-editor",job_id="film-b")
                for _ in range(200):
                    if all(service.inspect(job)["status"]=="completed"
                           for job in ("film-a","film-b")):break
                    time.sleep(.01)
                # The mocked executor contains no runtime lineage receipt:
                # project DB stages must NOT be laundered as job evidence.
                for job in ("film-a","film-b"):
                    snap=service.inspect(job)["actual_tool_progress"]
                    self.assertFalse(snap["tool_progress_is_actual_sqlite"])
                    self.assertEqual(snap["observed_tool_states"],[])
                with service._connect() as db:
                    db.execute("UPDATE jobs SET status='running',result=NULL WHERE id='film-a'")
                a=service.inspect("film-a")["actual_tool_progress"]
                self.assertEqual(len(a["observed_tool_states"]),1)
                self.assertEqual(a["observed_tool_states"][0]["node_id"],"render")
                with service._connect() as db:
                    db.execute("UPDATE jobs SET status='queued',result=NULL WHERE id='film-a'")
                    db.execute("UPDATE jobs SET status='running',result=NULL WHERE id='film-b'")
                self.assertEqual(service.inspect("film-a")["actual_tool_progress"]
                                 ["observed_tool_states"],[])
                b=service.inspect("film-b")["actual_tool_progress"]
                self.assertEqual(len(b["observed_tool_states"]),1)
                self.assertEqual(b["observed_tool_states"][0]["node_id"],"render")
            finally:
                service.close()

    def test_whole_independent_studio_service_survives_original_machine_loss(self):
        import shutil
        from studio_next.body_archive import restore_body_archive
        with tempfile.TemporaryDirectory() as outer:
            base=Path(outer)
            home=base/"permanent-creative-studio"
            service=LocalBodyCoordinator(home,execute=lambda ir,path:{
                "status":"all_tool_results_verified","completed":["actual-shot"],
                "video_proven":False})
            try:
                media=b"real-owner-original-raw-cinema"*1024
                asset=service.upload_owner_media(
                    "the-owner-film","original-raw.bin",
                    io.BytesIO(media),len(media),
                    mime="application/octet-stream",
                    source_id="operator-original-asset",
                    rights_evidence="Original creator supplied raw files")
                service.submit(plan(),workspace_id="the-owner-film",job_id="unique-cinema")
                for _ in range(150):
                    if service.inspect("unique-cinema")["status"]=="completed":break
                    time.sleep(.01)
                self.assertEqual(service.inspect("unique-cinema")["status"],"completed")
                for _ in range(150):
                    if not service._queued:break
                    time.sleep(.01)
                snapshot=service.create_recovery_snapshot(base/"entire-studio.tar.gz")
                self.assertGreaterEqual(snapshot["files"],4)
            finally:service.close()
            shutil.rmtree(home)
            verified=restore_body_archive(base/"entire-studio.tar.gz",home,
                                         expected_sha256=snapshot["sha256"])
            self.assertTrue(verified["all_physical_bytes_verified"])
            recovered=LocalBodyCoordinator(home)
            try:
                self.assertEqual(recovered.inspect("unique-cinema")["status"],"completed")
                self.assertEqual(recovered.pending_restart(),0)
                actual=home/"projects"/"the-owner-film"/"original-raw.bin"
                self.assertEqual(actual.read_bytes(),media)
                from studio_next.media_vault import MediaVault
                vault=MediaVault(home/"projects"/"the-owner-film"/"vault")
                record=vault.inspect(asset["asset_id"],
                                   attestation_id=asset["attestation_id"])
                self.assertEqual(record["rights_attestations"][0]["rights"],
                                 "owner_supplied")
            finally:recovered.close()

    def test_running_creative_renderer_cannot_be_inconsistently_archived(self):
        with tempfile.TemporaryDirectory() as outer:
            start=threading.Event()
            release=threading.Event()
            def active(ir,workspace):
                start.set()
                release.wait(timeout=5)
                return {"status":"all_tool_results_verified"}
            service=LocalBodyCoordinator(Path(outer)/"studio",execute=active)
            try:
                service.submit(plan(),workspace_id="film",job_id="film-1")
                self.assertTrue(start.wait(timeout=2))
                with self.assertRaisesRegex(RuntimeError,"active render"):
                    service.create_recovery_snapshot(Path(outer)/"unsafe.tar.gz")
                self.assertFalse((Path(outer)/"unsafe.tar.gz").exists())
            finally:
                release.set()
                service.close()

    def test_owner_can_import_actual_bytes_with_immutable_rights_custody(self):
        with tempfile.TemporaryDirectory() as root:
            backend=LocalBodyCoordinator(root,execute=lambda ir,workspace:{
                "status":"all_tool_results_verified"})
            data=b"original signed local artist source bytes"*32
            try:
                record=backend.upload_owner_media(
                    "original-project","artist-data.bin",io.BytesIO(data),len(data),
                    mime="application/octet-stream",source_id="owner-camera-raw-001",
                    rights_evidence="Owner explicitly supplied this original file")
                self.assertEqual(record["bytes"],len(data))
                media=Path(root)/"projects"/"original-project"/"artist-data.bin"
                self.assertEqual(media.read_bytes(),data)
                with self.assertRaises(FileExistsError):
                    backend.upload_owner_media(
                        "original-project","artist-data.bin",io.BytesIO(data),len(data),
                        mime="application/octet-stream",source_id="owner",
                        rights_evidence="owner supplied")
                with self.assertRaisesRegex(ValueError,"Invalid media"):
                    backend.upload_owner_media(
                        "original-project","../private.bin",io.BytesIO(data),len(data),
                        mime="application/octet-stream",source_id="owner",
                        rights_evidence="owner supplied")
                with self.assertRaisesRegex(ValueError,"match"):
                    backend.upload_owner_media(
                        "original-project","false-video.mp4",io.BytesIO(data),len(data),
                        mime="application/octet-stream",source_id="owner",
                        rights_evidence="owner supplied")
                with self.assertRaises((ValueError,RuntimeError)):
                    backend.upload_owner_media(
                        "original-project","fake-footage.mp4",io.BytesIO(data),len(data),
                        mime="video/mp4",source_id="owner",
                        rights_evidence="owner supplied")
                self.assertFalse((media.parent/"fake-footage.mp4").exists())
                self.assertFalse(list(media.parent.glob(".zx7-import-*")))
            finally:backend.close()

    def test_authenticated_local_creative_research_has_no_separate_setup(self):
        from unittest.mock import patch
        from studio_next.creative_research_hub import CreativeResearchHub, CreativeSource
        with tempfile.TemporaryDirectory() as root:
            token="creative-owner-local-token-123456789012"
            coordinator=LocalBodyCoordinator(root,execute=lambda ir,workspace:{
                "status":"blocked"})
            server=ThreadingHTTPServer(("127.0.0.1",0),
                make_body_http_handler(coordinator,token))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            origin=f"http://127.0.0.1:{server.server_port}/v1/research"
            hits=[]
            def research(query,limit):
                hits.append(query)
                return [{"title":"Film grammar",
                         "source_page":"https://example.org/grammar"}]
            hub=CreativeResearchHub([
                CreativeSource("narrative","knowledge",frozenset({"all"}),research)])
            def post(payload,credential=token):
                return Request(origin,data=json.dumps(payload).encode(),
                    headers={"Authorization":"Bearer "+credential,
                             "Content-Type":"application/json"},method="POST")
            try:
                with patch("studio_next.body_service.CreativeResearchHub.installed",
                           return_value=hub):
                    with self.assertRaises(HTTPError) as denied:
                        urlopen(post({"query":"story"},credential="bad"),timeout=2)
                    self.assertEqual(denied.exception.code,401)
                    with urlopen(post({"query":"story structure"}),timeout=3) as response:
                        result=json.loads(response.read())
                    self.assertEqual(len(result["results"]),1)
                    self.assertFalse(result["rights_verified"])
                    self.assertEqual(hits,["story structure"])
                    with self.assertRaises(HTTPError) as illegal:
                        urlopen(post({"query":"story", "url":"http://private"}),timeout=2)
                    self.assertEqual(illegal.exception.code,400)
                    self.assertEqual(hits,["story structure"])
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)
                coordinator.close()

    def test_authentication_and_no_public_source_or_mutable_shell_commands(self):
        with tempfile.TemporaryDirectory() as root:
            token="local-unguessable-operator-token-123456789"
            c=LocalBodyCoordinator(root,execute=lambda ir,workspace:{
                "status":"all_tool_results_verified"})
            server=ThreadingHTTPServer(("127.0.0.1",0),
                                       make_body_http_handler(c,token))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            origin=f"http://127.0.0.1:{server.server_port}"
            def request(uri,body=None,authorized=True):
                headers={}
                if authorized:headers["Authorization"]="Bearer "+token
                if body is not None:headers["Content-Type"]="application/json"
                return Request(origin+uri,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers=headers,method="POST" if body is not None else "GET")
            try:
                with self.assertRaises(HTTPError) as denied:
                    urlopen(request("/v1/health",authorized=False),timeout=2)
                self.assertEqual(denied.exception.code,401)
                with urlopen(request("/v1/health"),timeout=2) as r:
                    self.assertTrue(json.loads(r.read())["online"])
                with self.assertRaises(HTTPError) as bad:
                    urlopen(request("/v1/jobs",{"workspace_id":"../escape",
                                               "film_ir":plan()}),timeout=2)
                self.assertEqual(bad.exception.code,400)
                with urlopen(request("/v1/jobs",
                    {"workspace_id":"real-studio","film_ir":plan()}),timeout=2) as r:
                    id=json.loads(r.read())["job_id"]
                for _ in range(100):
                    with urlopen(request("/v1/jobs/"+id),timeout=2) as r:
                        status=json.loads(r.read())
                    if status["status"]=="completed":break
                    time.sleep(.01)
                self.assertEqual(status["status"],"completed")
                original=b"source-camera-raw-bytes"*64
                payload=Request(origin+"/v1/workspaces/real-studio/assets/camera-original.bin",
                    data=original,method="POST",
                    headers={"Authorization":"Bearer "+token,
                             "Content-Type":"application/octet-stream",
                             "X-Source-Id":"actual-owner-shot-source",
                             "X-Rights-Evidence":"Owner generated original camera data"})
                with urlopen(payload,timeout=5) as response:
                    attached=json.loads(response.read())
                self.assertEqual(attached["asset_id"],hashlib.sha256(original).hexdigest())
                with urlopen(request("/v1/jobs/"+id+"/artifacts"),timeout=5) as response:
                    listed=json.loads(response.read())["assets"]
                self.assertIn("camera-original.bin",[a["path"] for a in listed])
                with urlopen(request("/v1/jobs/"+id+"/artifacts/camera-original.bin"),
                             timeout=5) as response:
                    self.assertEqual(response.read(),original)

            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)
                c.close()


if __name__=="__main__":unittest.main()
