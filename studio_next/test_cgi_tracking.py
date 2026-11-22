"""CGI contracts and independently projected/encoded planar VFX acceptance."""
import copy,importlib.util,json,math,os,shutil,subprocess,tempfile,unittest,wave
from pathlib import Path
from studio_next.blender_scene import validate_blender_shot,lathe_geometry,Invalid3DShot
from studio_next.body_document_schemas import validate_document,document_contract
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.body_planar import PlanarTracker,composite_corner_pin,render_planar_insert

def scene():
    p=Path(__file__).parent/'fixtures/three_dimensional_shot.json'
    return json.loads(p.read_text())

class CGIContractTests(unittest.TestCase):
    def test_authored_glass_radial_shape_camera_focus_and_hierarchy(self):
        s=scene();s['denoise']=True;s['materials'][0].update(transmission=.95,ior=1.46,coat=.3,emission_color=[.1,.2,.3],emission_strength=.1)
        base={'id':'rig','type':'empty','material':s['materials'][0]['id'],'location':[0,0,0],'rotation_degrees':[0,0,0],'scale':[1,1,1]}
        bottle={**base,'id':'bottle','type':'lathe','parent':'rig','profile':[[.5,0],[.5,1],[.2,1.5]],'segments':32,'caps':True,
            'interpolation':'LINEAR','modifiers':[{'kind':'bevel','width':.01,'segments':3,'angle_degrees':35},{'kind':'solidify','thickness':.02,'offset':-1}]}
        s['objects']=[base,bottle];s['camera']['depth_of_field']={'focus_distance':5,'fstop':4}
        s['camera']['animate_focus_distance']=[{'frame':1,'value':[5]},{'frame':s['frames'],'value':[6]}]
        s['camera']['animate_lens_mm']=[{'frame':1,'value':[45]},{'frame':s['frames'],'value':[60]}]
        self.assertIs(validate_blender_shot(s),s);self.assertTrue(validate_document('body.cgi_shot',{'scene':s,'assets':[]}))

    def test_lathe_is_closed_and_has_per_polygon_uvs(self):
        v,f,uv=lathe_geometry([[.5,0],[.7,.3],[.2,1]],16,True)
        self.assertEqual(len(v),48);self.assertEqual(len(f),34)
        edges={}
        for face,coords in zip(f,uv):
            self.assertEqual(len(face),len(coords))
            for a,b in zip(face,face[1:]+face[:1]):edges[tuple(sorted((a,b)))]=edges.get(tuple(sorted((a,b))),0)+1
        self.assertTrue(all(x==2 for x in edges.values()))
        self.assertEqual(max(p[2] for p in v),1)

    def test_image_maps_require_local_root_and_do_not_escape(self):
        s=scene();s['materials'][0]['base_color_texture']='label.png'
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        with tempfile.TemporaryDirectory() as d:
            Path(d,'label.png').write_bytes(b'owned-image')
            self.assertIs(validate_blender_shot(s,verified_assets_root=d),s)
            s['materials'][0]['base_color_texture']='../label.png'
            with self.assertRaises(Invalid3DShot):validate_blender_shot(s,verified_assets_root=d)

    def test_bad_pbr_uv_parent_and_hidden_geometry_rejected(self):
        s=scene();s['materials'][0]['ior']=float('nan')
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=scene();s['objects'][0]['uvs']=[[[0,0]]]
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=scene();s['objects'][0]['parent']=s['objects'][1]['id'];s['objects'][1]['parent']=s['objects'][0]['id']
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=scene();s['objects'][0]['type']='lathe';s['objects'][0].update(profile=[[1,0],[1,1]],segments=16,caps=True)
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)

    def test_cgi_texture_source_bytes_are_in_actual_material_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'label.png';p.write_bytes(b'first original')
            plan={'scene':{},'assets':[{'name':'label.png','media':{'source':'label.png','asset_id':'x','attestation_id':'y'}}]}
            (root/'cgi.json').write_text(json.dumps(plan))
            a=fingerprint_physical_inputs('body.cgi_shot',{'plan':'cgi.json','out':'out.mp4'},root)
            p.write_bytes(b'changed original');b=fingerprint_physical_inputs('body.cgi_shot',{'plan':'cgi.json','out':'out.mp4'},root)
            self.assertNotEqual(a,b)

TRACKING_READY=bool(importlib.util.find_spec('cv2') and importlib.util.find_spec('numpy') and shutil.which('ffmpeg'))
SETTINGS={'max_features':1800,'min_matches':10,'min_inlier_ratio':.55,'ransac_pixels':2,'max_reprojection_error':1.5}

def projected_frames(count=8):
    """Perspective ground truth comes from a pinhole 3D camera, not the tracker."""
    import cv2,numpy as np
    rng=np.random.default_rng(1561);texture=rng.integers(30,220,(160,220,3),dtype=np.uint8)
    for i in range(65):
        x,y=rng.integers(10,205),rng.integers(10,145);cv2.circle(texture,(int(x),int(y)),int(rng.integers(2,7)),tuple(int(x) for x in rng.integers(0,255,3)),-1)
    cv2.putText(texture,'ORIGINAL PLANE',(12,80),cv2.FONT_HERSHEY_SIMPLEX,.6,(240,240,240),2)
    K=np.array([[310,0,160],[0,310,120],[0,0,1.]])
    points=np.array([[-1,-.7,0],[1,-.7,0],[1,.7,0],[-1,.7,0]])
    frames=[];quads=[]
    for i in range(count):
        a=.018*i;R=np.array([[math.cos(a),0,math.sin(a)],[0,1,0],[-math.sin(a),0,math.cos(a)]])
        cam=points@R.T+np.array([.015*i,.01*i,3.2]);q=cam@K.T;q=q[:,:2]/q[:,2:3]
        src=np.float32([[0,0],[219,0],[219,159],[0,159]])
        H=cv2.getPerspectiveTransform(src,q.astype(np.float32));frame=np.full((240,320,3),22,np.uint8)
        warped=cv2.warpPerspective(texture,H,(320,240));mask=cv2.warpPerspective(np.full((160,220),255,np.uint8),H,(320,240))
        frame[mask>0]=warped[mask>0];frames.append(frame);quads.append(q)
    return frames,quads

@unittest.skipUnless(TRACKING_READY,'Install .[vfx_tracking] and native FFmpeg for actual planar acceptance')
class PlanarAcceptanceTests(unittest.TestCase):
    def test_measured_motion_matches_independent_3d_projection(self):
        import numpy as np
        frames,ground_truth=projected_frames();tracker=PlanarTracker(frames[0],ground_truth[0],SETTINGS)
        for frame,wanted in zip(frames,ground_truth):
            actual,metrics=tracker.locate(frame)
            self.assertLess(float(np.max(np.linalg.norm(actual-wanted,axis=1))),1.5)
            self.assertGreaterEqual(metrics['inlier_ratio'],SETTINGS['min_inlier_ratio'])

    def test_transparency_and_original_foreground_are_preserved(self):
        import numpy as np
        frame=np.full((80,100,3),80,np.uint8);overlay=np.zeros((20,30,4),np.uint8);overlay[:,:,:3]=[0,0,255];overlay[:,:,3]=128
        q=[[20,20],[70,20],[70,60],[20,60]];mask=np.zeros((80,100),np.uint8);mask[35:45,40:50]=255
        out=composite_corner_pin(frame,overlay,q,.8,mask)
        np.testing.assert_array_equal(out[38,44],frame[38,44])
        self.assertGreater(int(out[30,30,2]),int(frame[30,30,2]));np.testing.assert_array_equal(out[0,0],frame[0,0])

    def test_blank_reference_and_missing_current_plane_fail(self):
        import numpy as np
        frames,q=projected_frames()
        with self.assertRaises(ValueError):PlanarTracker(np.zeros_like(frames[0]),q[0],SETTINGS)
        t=PlanarTracker(frames[0],q[0],SETTINGS)
        with self.assertRaises(RuntimeError):t.locate(np.zeros_like(frames[0]))

    def test_native_movie_preserves_full_audio_and_exact_frame_clock(self):
        import cv2,numpy as np
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);frames,quads=projected_frames(8)
            for i,im in enumerate(frames):cv2.imwrite(str(root/f'f{i:03}.png'),im)
            with wave.open(str(root/'sound.wav'),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000)
                a=(np.sin(2*np.pi*440*np.arange(48000)/48000)*4000).astype('<i2');w.writeframes(a.tobytes())
            subprocess.run(['ffmpeg','-v','error','-framerate','8','-i',str(root/'f%03d.png'),'-i',str(root/'sound.wav'),'-c:v','libx264','-crf','12','-pix_fmt','yuv420p','-vf','scale=in_range=full:out_range=tv:out_color_matrix=bt709','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv','-x264-params','colorprim=bt709:transfer=bt709:colormatrix=bt709','-c:a','aac','-y',str(root/'source.mp4')],check=True)
            art=np.zeros((80,120,4),np.uint8);art[:,:,1]=220;art[:,:,3]=100;cv2.imwrite(str(root/'art.png'),art)
            vault=MediaVault(root/'vault')
            def ref(name,mime):
                r=vault.ingest(root/name,mime=mime,rights='owner_supplied',source_type='owner_upload',source_id='actual-native-fixture',evidence='Original independently projected test scene and original PCM',owner_or_generator='test author')
                return {'source':name,'asset_id':r['asset_id'],'attestation_id':r['attestation_id']}
            plan={'media':ref('source.mp4','video/mp4'),'overlay':ref('art.png','image/png'),'quad':quads[0].tolist(),
                'opacity':.8,'audio':'preserve_source','tracking':SETTINGS}
            self.assertTrue(validate_document('body.planar_insert',plan));(root/'plan.json').write_text(json.dumps(plan))
            r=render_planar_insert(root/'plan.json',root,root/'vault',root/'out.mp4')
            self.assertEqual(r['actual_tracked_frames'],8);self.assertTrue(r['source_sound_bitstream_preserved'])
            def pcm(name):return subprocess.check_output(['ffmpeg','-v','error','-i',str(root/name),'-vn','-f','s16le','-'])
            self.assertEqual(pcm('source.mp4'),pcm('out.mp4'))
            for name in ('source.mp4','out.mp4'):
                probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=color_space,color_primaries,color_transfer,color_range','-of','json',str(root/name)]))
                self.assertEqual(probe['streams'],[{'color_range':'tv','color_space':'bt709','color_transfer':'bt709','color_primaries':'bt709'}],name)

if __name__=='__main__':unittest.main()
