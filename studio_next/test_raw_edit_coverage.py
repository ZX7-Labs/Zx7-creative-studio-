"""Hostile source-coverage tests: metrics must never certify creative quality."""
import unittest

from studio_next.raw_edit_coverage import EditCoverageError, assess_raw_edit_coverage


SOURCE = "a" * 64
DERIVED = "zx7:sha256:" + "b" * 64


def assess(**updates):
    args = {
        "source_duration_seconds": 100,
        "source_sha256": SOURCE,
        "source_has_audio": True,
        "sample_times_seconds": [3, 40, 95],
        "edit": {"cuts": [
            {"source_in": 0, "source_out": 5},
            {"source_in": 5, "source_out": 10},
            {"source_in": 8, "source_out": 12},
        ]},
        "native_plan": {"tracks": [{"clips": [
            {"source": DERIVED, "audio": "intentional_silence"}
            for _ in range(3)]}], "audio_tracks": []},
    }
    args.update(updates)
    return assess_raw_edit_coverage(**args)


class SourceCoverageTests(unittest.TestCase):
    def test_union_avoids_double_counting_overlapping_footage(self):
        report = assess()
        self.assertEqual(report["distinct_selected_source_seconds"], 12)
        self.assertEqual(report["distinct_source_coverage_fraction"], .12)
        self.assertEqual(report["native_plan_direct_original_source_clip_count"], 0)
        self.assertIs(report["native_plan_preserves_source_audio"], False)
        self.assertIs(report["artistic_quality_certified"], False)

    def test_direct_source_and_audio_absence_not_misclassified(self):
        native = {"tracks": [{"clips": [
            {"source": "zx7:sha256:" + SOURCE} for _ in range(3)]}],
            "audio_tracks": []}
        report = assess(source_has_audio=False, native_plan=native)
        self.assertEqual(report["native_plan_direct_original_source_clip_count"], 3)
        self.assertIsNone(report["native_plan_preserves_source_audio"])

    def test_rejects_contradictory_and_untrusted_evidence(self):
        invalid = [
            {"source_duration_seconds": float("nan")},
            {"source_sha256": "x" * 64},
            {"source_has_audio": "false"},
            {"sample_times_seconds": [100]},
            {"edit": {"cuts": [{"source_in": 1, "source_out": 200}]}},
            {"edit": {"cuts": [{"source_in": False, "source_out": 2}]}},
            {"native_plan": {"tracks": [], "audio_tracks": []}},
            {"native_plan": {"tracks": [{"clips": [
                {"source": DERIVED} for _ in range(3)]}]}}
        ]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(EditCoverageError):
                assess(**change)


if __name__ == "__main__":
    unittest.main()
