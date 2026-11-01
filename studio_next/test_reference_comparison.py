"""Real-film evidence comparisons, including a silent edit reference."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from .reference_evidence_tools import inspect_authorized_reference
from .reference_comparison import (
    ReferenceComparisonError, compare_observed_cases, editing_signature)


class ObservedCaseComparisonTests(unittest.TestCase):
    def test_two_physical_reference_editing_signatures_are_not_ranked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slow = root/"quiet.mp4"
            fast = root/"changing.mp4"
            subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i",
                "color=c=red:s=160x90:r=24:d=4","-c:v","libx264",str(slow)],
                check=True,timeout=40)
            args=["ffmpeg","-v","error","-y"]
            for tone in ("white","black","white","black"):
                args+=["-f","lavfi","-i",f"color=c={tone}:s=160x90:r=24:d=1"]
            args+=["-f","lavfi","-i","sine=frequency=540:duration=4",
                   "-filter_complex","[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0[v]",
                   "-map","[v]","-map","4:a","-c:v","libx264","-c:a","aac",
                   str(fast)]
            subprocess.run(args,check=True,timeout=40)
            left = inspect_authorized_reference(root,"quiet.mp4",bins=20)
            right = inspect_authorized_reference(root,"changing.mp4",bins=20)
            result = compare_observed_cases("quiet",left,"changing",right)
            self.assertEqual(left["cut_candidate_count"],0)
            self.assertEqual(right["cut_candidate_count"],3)
            self.assertGreater(result["second_minus_first"][
                "cut_candidates_per_minute"], 40)
            self.assertGreater(result["second_minus_first"][
                "mean_motion_energy"], 0)
            self.assertIsNone(result["first_observed"][
                "mean_audio_energy_dbfs"])
            self.assertIsNone(result["second_minus_first"][
                "mean_audio_energy_dbfs"])
            self.assertIsNotNone(result["second_observed"][
                "mean_audio_energy_dbfs"])
            self.assertTrue(result["comparison_is_not_aesthetic_quality_score"])
            self.assertTrue(result["audience_engagement_or_causality_not_established"])

    def test_invented_or_nonfinite_traces_fail(self):
        with self.assertRaises(ReferenceComparisonError):
            editing_signature({"schema":"ZX7_AUTHORIZED_REFERENCE_GRAPH_V1"})
        with self.assertRaises(ReferenceComparisonError):
            editing_signature({
                "schema":"ZX7_AUTHORIZED_REFERENCE_GRAPH_V1",
                "duration_seconds":1., "cut_candidate_count":1,
                "has_audio":False,
                "graph":[{"motion_energy_mean":float("nan")} for _ in range(8)]
            })


if __name__ == "__main__":
    unittest.main()
