"""Real two-frame Blender->owned EXR->ACES2 16-bit raster->10-bit ProRes proof."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_aces2_movie import render_aces2_scene_movie
from studio_next.body_aces2_preview import SOURCE_COLOR,DISPLAY,VIEW
from studio_next.body_exr_passes import render_original_exr_passes
from studio_next.body_integration import body_catalog,validate_witness
from studio_next.body_publication import physical_tool_attempt
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.test_blender_scene import sample

_READY=(shutil.which("blender") and shutil.which("ffmpeg") and
        importlib.util.find_spec("OpenEXR") and
        importlib.util.find_spec("PyOpenColorIO") and
        importlib.util.find_spec("numpy"))


HDR_DISPLAY = "Rec.2100-PQ - Display"
HDR_VIEW = "ACES 2.0 - HDR 1000 nits (Rec.2020)"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("numpy"), "Real ProRes codec stack required")
class ActualDisplayMasterCodec(unittest.TestCase):
    def test_pq_display_signal_survives_physical_10bit_prores(self):
        """Known ST2084 signal patches, not a mocked OCIO or a fake HDR label."""
        import numpy as np
        from studio_next.body_aces2_movie import _encode_display_movie
        nits = np.array([0, 1, 10, 100, 400, 1000], dtype=np.float64)
        m1, m2, c1, c2, c3 = 2610/16384, 2523/32, 3424/4096, 2413/128, 2392/128
        normalized = (nits/10000)**m1
        pq = ((c1+c2*normalized)/(1+c3*normalized))**m2
        width, height, count, fps = 96, 32, 3, 12
        frame = np.broadcast_to(np.repeat(pq,16)[None,:,None], (height,width,3))
        colors=np.array([[.6,.1,.1],[.1,.6,.1],[.1,.1,.6],[.4,.3,.2],[.2,.4,.3],[.3,.2,.4]])
        chromatic=np.broadcast_to(np.repeat(colors,16,axis=0)[None,:,:],(height,width,3))
        raster = np.rint(np.stack([frame,frame[:,::-1,:],chromatic])*65535).astype("<u2")
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); raw=root/"display.raw"; movie=root/"master.mov"
            raw.write_bytes(raster.tobytes())
            coded=_encode_display_movie(raw,movie,width,height,count,fps,
                                       display=HDR_DISPLAY,view=HDR_VIEW)
            self.assertEqual(coded["color_primaries"],"bt2020")
            self.assertEqual(coded["color_transfer"],"smpte2084")
            self.assertEqual(coded["color_space"],"bt2020nc")
            self.assertEqual(coded["color_range"],"tv")
            self.assertEqual(coded["pix_fmt"],"yuv422p10le")
            self.assertEqual(coded["nb_read_frames"],"3")
            decoded=subprocess.check_output(["ffmpeg","-v","error","-xerror","-i",str(movie),
                "-f","rawvideo","-pix_fmt","yuv422p10le","pipe:1"],timeout=60)
            planes=np.frombuffer(decoded,dtype="<u2").reshape(count,height*width*2)
            y=planes[:,:height*width].reshape(count,height,width)
            expected=64+876*pq
            np.testing.assert_allclose(y[0,8:24,8::16].mean(axis=0),expected,atol=3)
            np.testing.assert_allclose(y[1,8:24,8::16].mean(axis=0),expected[::-1],atol=3)
            self.assertGreater(y[0,16,-8],y[0,16,8])
            expected_color=64+876*(colors@np.array([.2627,.6780,.0593]))
            np.testing.assert_allclose(y[2,8:24,8::16].mean(axis=0),expected_color,atol=3)
            u=planes[:,height*width:height*width*3//2].reshape(count,height,width//2)
            v=planes[:,height*width*3//2:].reshape(count,height,width//2)
            luma=colors@np.array([.2627,.6780,.0593])
            np.testing.assert_allclose(u[2,8:24,4::8].mean(axis=0),512+896*(colors[:,2]-luma)/(2*(1-.0593)),atol=4)
            np.testing.assert_allclose(v[2,8:24,4::8].mean(axis=0),512+896*(colors[:,0]-luma)/(2*(1-.2627)),atol=4)

    def test_sdr_display_signal_remains_10bit_bt709(self):
        import numpy as np
        from studio_next.body_aces2_movie import _encode_display_movie
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); raw=root/"display.raw"; movie=root/"sdr.mov"
            raw.write_bytes(np.full((2,32,96,3),32768,dtype="<u2").tobytes())
            coded=_encode_display_movie(raw,movie,96,32,2,12,display=DISPLAY,view=VIEW)
            self.assertEqual(coded["color_primaries"],"bt709")
            self.assertEqual(coded["color_space"],"bt709")
            self.assertEqual(coded["pix_fmt"],"yuv422p10le")
            self.assertEqual(coded["nb_read_frames"],"2")

    def test_movie_rejects_crossed_display_view_pairs_before_encoding(self):
        from studio_next.body_aces2_movie import _encode_display_movie
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); raw=root/"unused.raw"; movie=root/"bad.mov"
            for display, view in ((HDR_DISPLAY,VIEW),(DISPLAY,HDR_VIEW)):
                with self.subTest(display=display,view=view):
                    with self.assertRaises(ValueError):
                        _encode_display_movie(raw,movie,96,32,1,12,display=display,view=view)
                    self.assertFalse(movie.exists())


class DisplayContractTests(unittest.TestCase):
    def test_only_exact_hdr_pair_is_available_to_movie_not_preview(self):
        from studio_next.body_document_schemas import validate_document
        plan={"source":{"source":"zx7:sha256:"+"a"*64,"asset_id":"a"*64,"attestation_id":"test"},
              "source_color_space":SOURCE_COLOR,"alpha_association":"associated_scene_linear",
              "scene_linear_background_rgb":[0,0,0],"display":DISPLAY,"view":VIEW}
        self.assertTrue(validate_document("body.aces2_movie",plan))
        self.assertTrue(validate_document("body.aces2_preview",{**plan,"frame_index":1}))
        hdr={**plan,"display":HDR_DISPLAY,"view":HDR_VIEW}
        self.assertTrue(validate_document("body.aces2_movie",hdr))
        with self.assertRaises(ValueError):
            validate_document("body.aces2_preview",{**hdr,"frame_index":1})
        for bad in ({**plan,"view":HDR_VIEW},{**hdr,"view":VIEW}):
            with self.assertRaises(ValueError):
                validate_document("body.aces2_movie",bad)


@unittest.skipUnless(_READY,"Real Blender/OpenEXR/OCIO/FFmpeg native film stack required")
class ActualNativeSceneToProRes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        scene=sample()
        scene["shot_id"]="native-two-frame-aces2-prores-scene"
        scene["width"]=96;scene["height"]=64
        scene["frames"]=2;scene["fps"]=12;scene["samples"]=2
        scene["camera"]["animate_location"][-1]["frame"]=2
        for obj in scene["objects"]:
            for curve in obj.get("animate",{}).values():
                if curve:curve[-1]["frame"]=2
        self.scene=self.root/"owned-director-shot.json"
        self.scene.write_text(json.dumps(scene))
        self.archive=self.root/"verified-original-32f-exr.zip"
        render_original_exr_passes(self.scene,self.root,self.archive)
        with physical_tool_attempt("original-cinema","original-exr",
                                   "blender-native-proof","body.asset_vault"):
            proof=body_catalog(self.root).invoke(
                "body.asset_vault",{"source_witness":{
                    "path":str(self.archive),
                    "sha256":sha256_file(self.archive),
                    "bytes":self.archive.stat().st_size}},
                allowed_access={"read","write"})
        self.proof=proof
        self.plan={"source":{
            "source":"zx7:sha256:"+proof["asset_id"],
            "asset_id":proof["asset_id"],
            "attestation_id":proof["attestation_id"]},
            "source_color_space":SOURCE_COLOR,
            "alpha_association":"associated_scene_linear",
            "scene_linear_background_rgb":[.025,.045,.09],
            "display":DISPLAY,"view":VIEW}
        self.planfile=self.root/"real-director-color.json"
        self.planfile.write_text(json.dumps(self.plan))
    def tearDown(self):self.temp.cleanup()

    def test_all_actual_linear_frames_produce_decoded_10bit_sdr_movie(self):
        listed={x["id"]:x for x in body_catalog(self.root).discover()}
        self.assertEqual(listed["body.aces2_movie"]["status"],"installed")
        args={"plan":self.planfile.name,"out":"real-aces2-prores.mov"}
        response=body_catalog(self.root).invoke(
            "body.aces2_movie",args,allowed_access={"read","write"})
        self.assertTrue(validate_witness("body.aces2_movie",response))
        observed=subprocess.run(["ffprobe","-v","error","-count_frames",
            "-show_entries","stream=codec_name,pix_fmt,nb_read_frames,color_space,color_transfer,color_primaries,color_range",
            "-of","json",str(self.root/"real-aces2-prores.mov")],
            capture_output=True,text=True,check=True,timeout=60)
        streams=json.loads(observed.stdout)["streams"]
        self.assertEqual(len(streams),1)
        self.assertEqual(streams[0]["codec_name"],"prores")
        self.assertEqual(streams[0]["pix_fmt"],"yuv422p10le")
        self.assertEqual(streams[0]["nb_read_frames"],"2")
        self.assertEqual(streams[0].get("color_space"),"bt709")
        self.assertEqual(streams[0].get("color_primaries"),"bt709")
        self.assertFalse(list(self.root.glob(".zx7-aces2-movie-*")))

    def test_original_linear_scene_produces_real_pq_hdr_movie(self):
        import numpy as np
        from studio_next.body_aces2_preview import _float_channels, OCIO_BUILTIN
        import PyOpenColorIO as OCIO
        import zipfile
        self.plan.update(display=HDR_DISPLAY,view=HDR_VIEW)
        self.planfile.write_text(json.dumps(self.plan))
        args={"plan":self.planfile.name,"out":"real-aces2-pq.mov"}
        catalog=body_catalog(self.root)
        self.assertEqual(next(x for x in catalog.discover() if x["id"]=="body.aces2_movie")["status"],"installed")
        before=sha256_file(self.archive)
        response=catalog.invoke("body.aces2_movie",args,allowed_access={"read","write"})
        self.assertTrue(validate_witness("body.aces2_movie",response))
        movie=self.root/args["out"]
        probe=json.loads(subprocess.check_output(["ffprobe","-v","error","-count_frames",
            "-show_entries","stream=codec_name,pix_fmt,nb_read_frames,color_space,color_transfer,color_primaries,color_range",
            "-of","json",str(movie)],timeout=60))["streams"]
        self.assertEqual(len(probe),1)
        for key,value in {"codec_name":"prores","pix_fmt":"yuv422p10le","nb_read_frames":"2",
                          "color_space":"bt2020nc","color_transfer":"smpte2084",
                          "color_primaries":"bt2020"}.items():
            self.assertEqual(probe[0].get(key),value)
        decoded_tags=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0",
            "-show_frames","-show_entries","frame=color_range,color_space,color_primaries,color_transfer",
            "-of","json",str(movie)],timeout=60))["frames"]
        self.assertEqual(len(decoded_tags),2)
        self.assertTrue(all(f.get("color_range")=="tv" and f.get("color_transfer")=="smpte2084" and
                            f.get("color_primaries")=="bt2020" and f.get("color_space")=="bt2020nc"
                            for f in decoded_tags))
        # Independent processor and Rec.2020 luma oracle from actual original
        # EXR pixels. Check picture values as well as container tags.
        config=OCIO.Config.CreateFromBuiltinConfig(OCIO_BUILTIN)
        transform=OCIO.DisplayViewTransform()
        transform.setSrc(SOURCE_COLOR);transform.setDisplay(HDR_DISPLAY);transform.setView(HDR_VIEW)
        cpu=config.getProcessor(transform).getDefaultCPUProcessor()
        decoded=subprocess.check_output(["ffmpeg","-v","error","-xerror","-i",str(movie),
            "-f","rawvideo","-pix_fmt","yuv422p10le","pipe:1"],timeout=60)
        width,height=96,64
        y=np.frombuffer(decoded,dtype="<u2").reshape(2,height*width*2)[:,:height*width]
        with zipfile.ZipFile(self.archive) as bundle:
            for index in range(2):
                original=self.root/"oracle.exr"
                original.write_bytes(bundle.read(f"frames/frame_{index+1:04d}.exr"))
                rgba=_float_channels(original)
                linear=rgba[:,:,:3]+(1-np.clip(rgba[:,:,3:4],0,1))*np.array(
                    self.plan["scene_linear_background_rgb"],dtype=np.float32)
                values=[]
                for pixel in linear.reshape(-1,3):
                    rgb=[float(v) for v in pixel]
                    mapped=cpu.applyRGB(rgb)
                    values.append(rgb if mapped is None else mapped)
                expected=64+876*(np.clip(values,0,1)@np.array([.2627,.6780,.0593]))
                error=np.abs(y[index].astype(np.float64)-expected)
                self.assertLess(float(np.mean(error)),3.0)
                self.assertLess(float(np.quantile(error,.95)),8.0)
        self.assertEqual(sha256_file(self.archive),before)
        self.assertFalse(list(self.root.glob(".zx7-aces2-movie-*")))

    def test_native_aces2_movie_enters_real_generated_license_and_resumes(self):
        from studio_next.body_integration import run_body_project
        graph={"project":{"creative_intent":
                     "Actual 32f Blender scene graded to independent SDR MOV"},
               "assets":[],
               "shots":[{"id":"scene","purpose":"Physically color manage complete CG shot",
                         "duration_seconds":2/12}],
               "tool_graph":[
                   {"id":"movie","tool_id":"body.aces2_movie",
                    "purpose":"Original every-frame ACES2 scene conversion",
                    "inputs":{"plan":self.planfile.name,
                              "out":"full-director-ACES2.mov"},
                    "depends_on":[]},
                   {"id":"rights","tool_id":"body.asset_vault",
                    "purpose":"Custody of actual decoded original color-managed MOV",
                    "inputs":{"source_witness":{"$node_output":"movie"}},
                    "depends_on":["movie"]}]}
        first=run_body_project(graph,self.root)
        self.assertEqual(first["status"],"all_tool_results_verified",first)
        self.assertEqual(first["completed"],["movie","rights"])
        result=self.root/"full-director-ACES2.mov"
        digest=sha256_file(result)
        asset=MediaVault(self.root/"vault").inspect(digest)
        self.assertEqual(asset["mime"],"video/quicktime")
        self.assertTrue(any(x["rights"]=="generated_original" and
                            x["source_type"]=="trusted_renderer"
                            for x in asset["rights_attestations"]))
        second=run_body_project(graph,self.root)
        self.assertEqual(second["status"],"all_tool_results_verified",second)
        self.assertEqual(second["reused"],["movie","rights"])
        self.assertEqual(sha256_file(result),digest)
        self.assertFalse(second["video_proven"])

    def test_production_movie_does_not_allow_swapped_rights_or_source_primaries(self):
        self.plan["source_color_space"]="ACEScg (unproven source)"
        self.planfile.write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(ValueError,"Only pinned ACES2"):
            render_aces2_scene_movie(self.planfile,self.root,self.root/"vault",
                                     self.root/"untrustworthy.mov")
        self.assertFalse((self.root/"untrustworthy.mov").exists())

    def test_another_artist_wins_prores_output_without_truncation(self):
        existing=self.root/"first-approved-aces.mov"
        render_aces2_scene_movie(self.planfile,self.root,self.root/"vault",existing)
        expected_sha=sha256_file(existing)
        target=self.root/"other-approved-master.mov"
        real_link=os.link
        collided=False
        from studio_next import body_aces2_movie as movie
        def first_artist_wins(src,dst,*a,**k):
            nonlocal collided
            if Path(dst)==target:
                shutil.copyfile(existing,target)
                collided=True
            return real_link(src,dst,*a,**k)
        with patch.object(movie.os,"link",side_effect=first_artist_wins):
            with self.assertRaises(FileExistsError):
                render_aces2_scene_movie(self.planfile,self.root,
                                         self.root/"vault",target)
        self.assertTrue(collided)
        self.assertEqual(sha256_file(target),expected_sha)
