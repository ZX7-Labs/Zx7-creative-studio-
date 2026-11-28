"""Agent-controlled CGI boundaries plus actual native simulation/render acceptance."""
import copy
import json
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from studio_next.blender_scene import validate_blender_shot, Invalid3DShot
from studio_next.body_document_schemas import document_contract, validate_document


def scene():
    return json.loads((Path(__file__).parent/'fixtures/advanced_cgi_physics_shot.json').read_text())


class CGIControlsContracts(unittest.TestCase):
    def test_agent_can_query_all_render_material_camera_and_physics_controls(self):
        s=scene()
        self.assertIs(validate_blender_shot(s),s)
        for tool,doc in [('body.cgi_shot',{'scene':s,'assets':[]}),
                         ('body.blender3d',s),('body.exr_passes',s),('body.exr_checkpoint',s)]:
            self.assertTrue(validate_document(tool,doc))
        schema=document_contract('body.cgi_shot')['json_schema']['properties']['scene']
        self.assertIn('physics',schema['properties'])
        self.assertIn('render_settings',schema['properties'])
        self.assertNotIn('default',json.dumps(schema))

    def test_controls_accept_no_shader_code_or_arbitrary_python(self):
        for path in ('material','physics','render','noise','rigid'):
            s=scene()
            target={'material':s['materials'][0], 'physics':s['physics'],
                'render':s['render_settings'],'noise':s['materials'][0]['surface_noise'],
                'rigid':s['objects'][0]['rigid_body']}[path]
            target['python']='__import__("os").system("untrusted")'
            with self.subTest(path=path),self.assertRaises(ValueError):validate_blender_shot(s)
            with self.subTest(schema=path),self.assertRaises(ValueError):validate_document('body.cgi_shot',{'scene':s,'assets':[]})

    def test_numeric_physical_controls_reject_nonfinite_boolean_and_out_of_range(self):
        for key,value in [('seed',True),('seed',-1),('max_bounces',-1),
                          ('adaptive_threshold',float('nan')),('exposure',33)]:
            s=scene();s['render_settings'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        for key,value in [('density',float('inf')),('density',-1)]:
            s=scene();s['materials'][1]['volume']['absorption'][key]=value
            with self.assertRaises(Invalid3DShot):validate_blender_shot(s)

    def test_dynamic_animation_parenting_and_missing_world_cannot_hide_conflicting_control(self):
        original=scene()
        cases=[]
        s=copy.deepcopy(original);s.pop('physics');cases.append(s)
        s=copy.deepcopy(original);s['objects'][0]['parent']='floor';cases.append(s)
        s=copy.deepcopy(original);s['objects'][0]['animate']={'location':[{'frame':1,'value':[0,0,1]}]};cases.append(s)
        s=copy.deepcopy(original);s['objects'][0]['rigid_body']['collision_shape']='MESH';cases.append(s)
        s=copy.deepcopy(original);s['objects'][0]['rigid_body']['kinematic']='yes';cases.append(s)
        for s in cases:
            with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=scene();s['objects'][0]['rigid_body']['kinematic']=True
        s['objects'][0]['animate']={'location':[{'frame':1,'value':[0,0,1]},{'frame':12,'value':[1,0,1]}]}
        self.assertIs(validate_blender_shot(s),s)
        s['objects'][0]['animate']['scale']=[{'frame':1,'value':[1,1,1]}]
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)

    def test_missing_focus_and_competing_distance_animation_are_rejected(self):
        s=scene();s['camera']['depth_of_field']['focus_object']='missing'
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=scene();s['camera']['animate_focus_distance']=[{'frame':1,'value':[3]}]
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)

    def test_no_silently_overwritten_procedural_texture(self):
        for field,noise_field in [('base_color_texture','color_range'),('roughness_texture','roughness_range')]:
            s=scene();m=s['materials'][0];m[field]='map.png'
            if noise_field=='color_range':m['surface_noise'][noise_field]=[[0,0,0,1],[1,1,1,1]]
            with self.assertRaisesRegex(Invalid3DShot,'ignored input'):validate_blender_shot(s)
        s=scene();s['materials'][0]['volume']={}
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)

    def test_material_and_light_curves_obey_original_clock_and_input_ranges(self):
        s=scene();s['materials'][0]['animate']['coat'][0]['frame']=13
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=scene();s['lights'][0]['animate_energy'][0]['value']=[-1]
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=scene();s['materials'][0]['animate']['roughness']=[{'frame':1,'value':[.3]}]
        with self.assertRaisesRegex(Invalid3DShot,'overridden'):validate_blender_shot(s)

    def test_physical_shutter_cannot_silently_empty_required_exr_vectors(self):
        s=scene()
        self.assertIs(validate_blender_shot(s),s)
        with self.assertRaisesRegex(Invalid3DShot,'Vector-pass EXR'):
            validate_blender_shot(s,require_vector_passes=True)
        s['render_settings'].pop('motion_blur')
        self.assertIs(validate_blender_shot(s,require_vector_passes=True),s)

    def test_both_exr_entry_points_refuse_blur_before_launch_or_checkpoint(self):
        from studio_next.body_exr_passes import render_original_exr_passes
        from studio_next.body_frame_resume import render_resumable_exr_passes
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'scene.json';source.write_text(json.dumps(scene()))
            with patch('shutil.which',return_value='/installed/blender'),patch('importlib.util.find_spec',return_value=object()),patch('subprocess.run') as launched:
                for index,render in enumerate((render_original_exr_passes,render_resumable_exr_passes)):
                    with self.assertRaisesRegex(Invalid3DShot,'Vector-pass EXR'):
                        render(source,root,root/f'passes{index}.zip')
                launched.assert_not_called()
            self.assertFalse((root/'.zx7-frame-checkpoints').exists())
            self.assertEqual(list(root.glob('*.zip')),[])


@unittest.skipUnless(shutil.which('blender') and shutil.which('ffmpeg') and shutil.which('ffprobe') and
                     importlib.util.find_spec('numpy') and importlib.util.find_spec('PIL'),
                     'Actual Blender + FFmpeg required for physics/shading/render acceptance')
class NativeCGIControlsAcceptance(unittest.TestCase):
    def test_public_body_real_pixels_physics_frame_resume_and_reuse(self):
        from studio_next.body_cgi_controls_proof import run
        with tempfile.TemporaryDirectory() as temp:
            root=Path(os.environ.get('ZX7_CGI_CONTROLS_PROOF',temp))
            proof=run(root,size=96,samples=4)
            self.assertTrue(proof['all_checks_passed'])
            self.assertTrue(proof['original_clock_subset_physics_identical'])
            self.assertTrue(proof['original_clock_subset_picture_within_quantization_tolerance'])
            self.assertGreater(proof['volume_control_mean_pixel_difference'],.05)
            self.assertGreater(proof['motion_blur_support_gain_pixels'],2)

    def test_real_textured_cgi_derivative_retains_exact_grant_after_graph_reopen(self):
        from PIL import Image
        from studio_next.body_integration import run_body_project
        from studio_next.media_vault import MediaVault, MediaRightsWithdrawn, sha256_file
        from studio_next.test_blender_scene import sample
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            texture=root/"owned-label.png"
            image=Image.new("RGB",(32,32),(220,50,30))
            image.paste((20,160,210),(0,0,16,16))
            image.save(texture)
            vault=MediaVault(root/"vault")
            def grant(identity):
                return vault.ingest(texture,mime="image/png",rights="owner_supplied",
                    source_type="owner_upload",source_id=identity,
                    evidence="Original synthetic authored texture",owner_or_generator="owner")
            original,other=grant("cgi-exact-grant"),grant("independent-same-bytes")
            scene=sample()
            scene.update(shot_id="owned-textured-cgi",width=96,height=64,frames=2,samples=2)
            scene["camera"]["animate_location"][-1]["frame"]=2
            scene["objects"][1]["animate"]["rotation_degrees"][-1]["frame"]=2
            scene["materials"][2]["base_color_texture"]=texture.name
            plan={"scene":scene,"assets":[{"name":texture.name,"media":{
                "source":texture.name,"asset_id":original["asset_id"],
                "attestation_id":original["attestation_id"]}}]}
            (root/"plan.json").write_text(json.dumps(plan))
            graph={"project":{"creative_intent":"Original texture on a native CGI shot"},
                "assets":[],"shots":[{"id":"shot","purpose":"Owned textured scene",
                                       "duration_seconds":2/scene["fps"]}],
                "tool_graph":[
                    {"id":"shot","tool_id":"body.cgi_shot","purpose":"Render owned native scene",
                     "inputs":{"plan":"plan.json","out":"shot.mp4"},"depends_on":[]},
                    {"id":"custody","tool_id":"body.asset_vault","purpose":"Exact derived rights",
                     "inputs":{"source_witness":{"$node_output":"shot"}},"depends_on":["shot"]}]}
            first=run_body_project(graph,root)
            self.assertEqual(first["status"],"all_tool_results_verified",first)
            digest=sha256_file(root/"shot.mp4")
            generated=vault.inspect(digest)["rights_attestations"][0]
            self.assertEqual(generated["source_attestations"],[
                {key:original[key] for key in ("asset_id","attestation_id")}])
            derivative=generated["attestation_id"]
            reopened=run_body_project(graph,root)
            self.assertEqual(reopened["reused"],["shot","custody"],reopened)
            vault.withdraw_attestation(original["asset_id"],original["attestation_id"],
                                       reason="Texture grant withdrawn")
            self.assertEqual(vault.inspect(other["asset_id"],attestation_id=other["attestation_id"])
                             ["rights_attestations"][0]["attestation_id"],other["attestation_id"])
            with self.assertRaises(MediaRightsWithdrawn):
                vault.inspect(digest,attestation_id=derivative)
            with self.assertRaises(MediaRightsWithdrawn):
                vault.checkout(digest,derivative,root/"revoked.mp4")
            self.assertFalse((root/"revoked.mp4").exists())
            self.assertNotEqual(run_body_project(graph,root)["status"],"all_tool_results_verified")
            self.assertEqual(sha256_file(root/"shot.mp4"),digest)


if __name__=='__main__':unittest.main()
