"""Adversarial original-camera-edit controls and actual decoded graphic frames."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image
from scripts.run_raw_video_neural_edit_test import (
    plan_schema,validate_edit,overlay_graphics,create_graphic,
    SYSTEM,shot_reel,probe
)


def model_edit():
    return {
        "cuts":[{"source_in":0,"source_out":3,"speed":1.0,
                 "contrast":1.0,"saturation":1.0}],
        "graphics":[],
        "music":{"enabled":False,"bpm":85,"root_midi":51,
                 "mode":"minor","progression":[0,2,4]},
    }


class UnscriptedRawEditorTests(unittest.TestCase):
    def test_actual_task_has_no_designer_selected_style_or_subject(self):
        # This test concerns the actual studio's role and instruction surface,
        # not a mocked brain response.
        self.assertNotIn("cinematic", SYSTEM.lower())
        self.assertNotIn("motion graphic", SYSTEM.lower())
        self.assertNotIn("drone", SYSTEM.lower())
        schema=plan_schema(30)
        self.assertEqual(set(schema["properties"]),{"cuts","graphics","music"})

    def test_model_controls_are_typed_reversible_and_bounded(self):
        plan=model_edit()
        self.assertEqual(validate_edit(plan,30),3)
        for field,value in (
            ("source_out",35),("source_out",0.4),("source_in",True),
            ("speed",0),("speed",float("nan")),("contrast",float("inf")),
            ("saturation",3)):
            test=model_edit()
            test["cuts"][0][field]=value
            with self.subTest(field=field,value=value):
                with self.assertRaises(ValueError):
                    validate_edit(test,30)
        with self.assertRaises(ValueError):
            validate_edit({"cuts":[], "graphics":[],
                           "music":model_edit()["music"]},30)
        too_long=model_edit()
        too_long["cuts"]=[{
            "source_in":0,"source_out":30,"speed":.5,
            "contrast":1,"saturation":1,
        } for _ in range(3)]
        with self.assertRaises(ValueError):
            validate_edit(too_long,30)

    def test_transparent_native_graphic_is_written_from_authored_pixels(self):
        graphic={"text":"REAL TEST","start":0.1,"end":1.6,
                 "x0":25,"x1":225,"y0":40,"y1":40,
                 "size":33,"red":230,"green":200,"blue":10}
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            png=root/"graphic.png"
            size=create_graphic(graphic,png)
            self.assertGreater(size[0],50)
            with Image.open(png) as im:
                self.assertEqual(im.mode,"RGBA")
                self.assertTrue(any(im.getchannel("A").getextrema()))
            original=root/"source.mp4"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
              "-y","-f","lavfi","-i","color=black:size=1280x720:rate=24:duration=2",
              "-pix_fmt","yuv420p","-c:v","libx264",str(original)],
              check=True,timeout=50)
            edited=root/"with_neural_graphic.mp4"
            receipt=overlay_graphics(original,[graphic],edited,root)
            self.assertEqual(receipt["authored_graphics"],1)
            self.assertNotEqual(original.read_bytes(),edited.read_bytes())
            out=json.loads(subprocess.check_output(
                ["ffprobe","-v","error","-count_frames",
                 "-select_streams","v:0",
                 "-show_entries","stream=nb_read_frames",
                 "-of","json",str(edited)],timeout=30))
            self.assertEqual(int(out["streams"][0]["nb_read_frames"]),48)
            original2=root/"without_neural_graphic.mp4"
            identity=overlay_graphics(original,[],original2,root)
            self.assertFalse(identity["applied"])
            self.assertEqual(original.read_bytes(),original2.read_bytes())

    def test_decoded_raw_camera_times_are_not_an_imaginary_storyboard(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            video=root/"actual_encoded_camera.mp4"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                "-y","-f","lavfi","-i",
                "testsrc2=size=640x360:rate=24:duration=4",
                "-pix_fmt","yuv420p","-c:v","libx264",str(video)],
                check=True,timeout=40)
            info=probe(video)
            sheet=root/"source-actually-decoded.png"
            evidence=shot_reel(video,info,sheet)
            self.assertEqual(len(evidence["sample_times_seconds"]),16)
            self.assertTrue(sheet.is_file())
            with Image.open(sheet) as visual:
                self.assertEqual(visual.size,(1280,840))
            self.assertTrue(evidence[
                "samples_are_not_full_motion_semantic_understanding"])


if __name__=="__main__":
    unittest.main()
