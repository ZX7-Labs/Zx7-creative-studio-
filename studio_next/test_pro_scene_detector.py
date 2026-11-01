"""Independent real-frame regressions for OSS shot detector, no fake results."""
from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

from .pro_scene_detector import detect_authorized_shots
from .reference_observatory import ReferenceObservationError

HAS_SCENEDETECT = importlib.util.find_spec("scenedetect") is not None


@unittest.skipUnless(HAS_SCENEDETECT, "Install research_video extra")
class OSSShotDetectorTests(unittest.TestCase):
    def test_real_four_shots_and_permission_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "four-shots.mp4"
            args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
            for color in ("black", "white", "black", "white"):
                args.extend(["-f", "lavfi", "-i",
                             f"color=c={color}:s=160x90:r=24:d=1"])
            args += [
                "-filter_complex", "[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0[v]",
                "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(movie)]
            subprocess.run(args, check=True, timeout=45)
            result = detect_authorized_shots(root, "four-shots.mp4", method="content")
            self.assertEqual(result["library"], "PySceneDetect")
            self.assertEqual(result["detector"], "content")
            self.assertEqual(result["source_resolution"], [160, 90])
            self.assertEqual(len(result["shot_intervals"]), 4)
            self.assertEqual(len(result["cut_candidates_seconds"]), 3)
            for actual, expected in zip(result["cut_candidates_seconds"], (1., 2., 3.)):
                self.assertLess(abs(actual - expected), 0.1)
            self.assertFalse(result["creative_quality_certified"])
            self.assertFalse(result["rights_to_reuse_original_footage_verified"])
            with self.assertRaises(ReferenceObservationError):
                detect_authorized_shots(root, "../private.mp4")
            with self.assertRaises(ReferenceObservationError):
                detect_authorized_shots(root, "/etc/passwd")
            with self.assertRaises(ReferenceObservationError):
                detect_authorized_shots(root, "four-shots.mp4", max_seconds=3)
            with self.assertRaises(ReferenceObservationError):
                detect_authorized_shots(root, "four-shots.mp4", method="model_guess")
            (root / "out.mp4").symlink_to("/etc/passwd")
            with self.assertRaises(ReferenceObservationError):
                detect_authorized_shots(root, "out.mp4")


if __name__ == "__main__":
    unittest.main()
