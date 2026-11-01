"""Physical acceptance tests: real encoded video and sound, not canned metrics."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from .reference_observatory import observe_reference, ReferenceObservationError
from .reference_evidence_tools import inspect_authorized_reference


class ReferenceObservatoryTests(unittest.TestCase):
    def test_real_decoded_cuts_and_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            movie = Path(temp) / "film.mp4"
            args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
            for tone in ("black", "white", "black", "white"):
                args += ["-f", "lavfi", "-i", f"color=c={tone}:s=128x72:r=24:d=1"]
            args += [
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000:duration=4",
                "-filter_complex", "[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0[v]",
                "-map", "[v]", "-map", "4:a", "-c:v", "libx264", "-c:a", "aac",
                "-pix_fmt", "yuv420p", str(movie)]
            subprocess.run(args, check=True, timeout=45)
            receipt = Path(temp) / "evidence.json"
            result = observe_reference(movie, sample_fps=8, output=receipt)
            self.assertEqual(result["schema"], "ZX7_REFERENCE_OBSERVATION_V1")
            self.assertEqual(len(result["cut_candidates_seconds"]), 3)
            for detected, actual in zip(result["cut_candidates_seconds"], (1, 2, 3)):
                self.assertLess(abs(detected-actual), 0.15)
            self.assertTrue(result["audio_observations"])
            self.assertTrue(result["has_audio"])
            self.assertEqual(json.loads(receipt.read_text())["source_sha256"],
                             result["source_sha256"])
            self.assertEqual(result["limits"]["professional_artistic_quality"],
                             "not certified")
            summary = inspect_authorized_reference(temp, "film.mp4", bins=16)
            self.assertEqual(len(summary["graph"]), 16)
            self.assertEqual(summary["cut_candidate_count"], 3)
            self.assertTrue(summary["has_audio"])
            self.assertFalse(summary["original_video_bytes_retained"])
            self.assertFalse(summary["model_has_understood_story_or_editing_intent"])
            with self.assertRaises(ReferenceObservationError):
                inspect_authorized_reference(temp, "../outside.mp4")
            with self.assertRaises(ReferenceObservationError):
                inspect_authorized_reference(temp, "/etc/passwd")
            with self.assertRaises(ReferenceObservationError):
                inspect_authorized_reference(temp, "film.mp4", bins=257)
            (Path(temp)/"escaped.mp4").symlink_to("/etc/passwd")
            with self.assertRaises(ReferenceObservationError):
                inspect_authorized_reference(temp, "escaped.mp4")

    def test_no_audio_is_observed_not_invented(self):
        with tempfile.TemporaryDirectory() as temp:
            movie = Path(temp) / "silent.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f",
                "lavfi", "-i", "color=c=red:s=128x72:r=24:d=3",
                "-c:v", "libx264", str(movie)], check=True, timeout=35)
            with self.assertRaisesRegex(ReferenceObservationError, "budget"):
                observe_reference(movie, max_duration_seconds=2)
            result = observe_reference(movie)
            self.assertEqual(result["audio_observations"], [])
            self.assertFalse(result["has_audio"])

    def test_invalid_reference_fails_closed(self):
        with self.assertRaises((ReferenceObservationError, FileNotFoundError)):
            observe_reference("/not/existing/reference.mp4")
        with self.assertRaises(ReferenceObservationError):
            observe_reference(__file__, sample_fps=99)
        with self.assertRaises(ReferenceObservationError):
            observe_reference(__file__)


if __name__ == "__main__":
    unittest.main()
