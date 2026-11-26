"""Physical acceptance tests: real encoded video and sound, not canned metrics."""
from __future__ import annotations

import json
import math
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

    def test_real_mixed_audio_is_averaged_by_linear_sample_energy(self):
        """16s encoded soundtrack: one loud second, fifteen quieter seconds.

        Graph bin 0 contains 2 decoded seconds. Averaging their dBFS labels
        instead of PCM energy misrepresents the stronger segment by ~7 dB.
        """
        with tempfile.TemporaryDirectory() as temp:
            movie = Path(temp) / "mixed-levels.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=128x72:r=8:d=16",
                "-f", "lavfi", "-i",
                "sine=frequency=440:sample_rate=8000:duration=1",
                "-f", "lavfi", "-i",
                "sine=frequency=440:sample_rate=8000:duration=15",
                "-filter_complex",
                "[2:a]volume=0.1[quiet];"
                "[1:a][quiet]concat=n=2:v=0:a=1[sound]",
                "-map", "0:v", "-map", "[sound]",
                "-c:v", "libx264", "-c:a", "aac", str(movie)],
                check=True, timeout=45)
            physical = observe_reference(movie)["audio_observations"]
            self.assertGreaterEqual(len(physical), 16)
            first_two = physical[:2]
            self.assertEqual([row["sample_count"] for row in first_two],
                             [8000, 8000])
            self.assertGreater(first_two[0]["rms_dbfs"] -
                               first_two[1]["rms_dbfs"], 15)
            graph = inspect_authorized_reference(temp, "mixed-levels.mp4", bins=8)
            total_samples = sum(row["sample_count"] for row in first_two)
            actual_mean_square = sum(
                10 ** (row["rms_dbfs"] / 10.) * row["sample_count"]
                for row in first_two) / total_samples
            expected_dbfs = 10 * math.log10(actual_mean_square)
            observed_dbfs = graph["graph"][0]["audio_rms_dbfs"]
            self.assertAlmostEqual(observed_dbfs, expected_dbfs, delta=0.03)
            false_dbfs = sum(row["rms_dbfs"] for row in first_two) / 2
            self.assertGreater(abs(observed_dbfs - false_dbfs), 4)

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
            self.assertTrue(result["visual_observations"])
            colored = result["visual_observations"][0]
            self.assertGreater(colored["mean_rgb"][0], 0.5)
            self.assertLess(colored["mean_rgb"][1], 0.05)
            self.assertLess(colored["mean_rgb"][2], 0.05)
            self.assertGreater(colored["mean_chroma"], 0.5)
            graph = inspect_authorized_reference(temp, "silent.mp4", bins=8)
            self.assertGreater(graph["graph"][0]["mean_chroma"], 0.5)
            self.assertEqual(graph["graph"][0]["audio_rms_dbfs"], None)

    def test_source_mutation_during_decode_blocks_false_identity(self):
        from unittest.mock import patch
        from . import reference_observatory as measured
        with tempfile.TemporaryDirectory() as temp:
            movie = Path(temp) / "changing.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f",
                "lavfi", "-i", "color=c=blue:s=128x72:r=24:d=1",
                "-c:v", "libx264", str(movie)], check=True, timeout=35)
            original_decode = measured._decode_video
            def mutate_after_observation(*args):
                rows = original_decode(*args)
                with movie.open("ab") as stream:
                    stream.write(b"ZX7_SOURCE_CHANGED")
                return rows
            with patch.object(measured, "_decode_video",
                              side_effect=mutate_after_observation):
                with self.assertRaisesRegex(ReferenceObservationError, "mutated"):
                    observe_reference(movie)

    def test_invalid_reference_fails_closed(self):
        with self.assertRaises((ReferenceObservationError, FileNotFoundError)):
            observe_reference("/not/existing/reference.mp4")
        with self.assertRaises(ReferenceObservationError):
            observe_reference(__file__, sample_fps=99)
        with self.assertRaises(ReferenceObservationError):
            observe_reference(__file__)


if __name__ == "__main__":
    unittest.main()
