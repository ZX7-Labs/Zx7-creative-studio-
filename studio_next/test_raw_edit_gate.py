"""Mechanical acceptance rejects the actual observed 2B failure, not art styles."""
import unittest

from studio_next.raw_edit_gate import (
    InsufficientEditorialEvidence, assess_minimum_editorial_evidence,
)


def candidate(cuts, *, music=False, graphics=None):
    return {
        "cuts": [{"source_in": start, "source_out": end,
                  "speed": speed, "contrast": contrast, "saturation": saturation}
                 for start, end, speed, contrast, saturation in cuts],
        "graphics": [] if graphics is None else graphics,
        "music": {"enabled": music}
    }


class NeuralRawEditMinimumEvidenceTests(unittest.TestCase):
    def test_real_240_second_noop_prefix_rejected_without_style_hardcoding(self):
        observed = candidate([(i, i + 1, 1, 1, 1) for i in range(12)])
        with self.assertRaises(InsufficientEditorialEvidence) as refusal:
            assess_minimum_editorial_evidence(observed, source_seconds=240.032, output_fps=24)
        fields = refusal.exception.diagnostics
        self.assertTrue(fields["unmodified_source_prefix_detected"])
        self.assertFalse(fields["passes_minimum_editorial_evidence"])
        self.assertFalse(fields["artistic_quality_certified"])
        self.assertEqual(fields["last_selected_source_second"], 12)

    def test_native_source_selection_or_deliberate_changes_can_pass_minimum(self):
        examples = [
            candidate([(50, 56, 1, 1, 1)]),  # deliberate different source interval
            candidate([(0, 5, 1, 1, 1), (20, 27, 1, 1, 1)]),
            candidate([(0, 12, 0.8, 1, 1)]),  # temporal treatment, not a copied prefix
            candidate([(0, 12, 1, 1.05, 1)]),  # color decision
            candidate([(0, 12, 1, 1, 1)], music=True),
            candidate([(0, 12, 1, 1, 1)], graphics=[{"real": "caption"}]),
        ]
        for example in examples:
            with self.subTest(example=example):
                x = assess_minimum_editorial_evidence(example, source_seconds=240, output_fps=24)
                self.assertTrue(x["passes_minimum_editorial_evidence"])
                self.assertFalse(x["artistic_quality_certified"])

    def test_numeric_nudge_smaller_than_real_output_frame_cannot_forge_edit(self):
        for field,value in (("speed",1.000002),("contrast",1.00001),
                            ("saturation",1.00001)):
            plan=candidate([(0,12,1,1,1)])
            plan["cuts"][0][field]=value
            with self.subTest(field=field), self.assertRaises(
                    InsufficientEditorialEvidence):
                assess_minimum_editorial_evidence(
                    plan, source_seconds=240.032, output_fps=24)
        # The actual renderer's clock must change for speed to qualify.
        frame_distinct=candidate([(0,12,0.9,1,1)])
        accepted=assess_minimum_editorial_evidence(
            frame_distinct, source_seconds=240.032, output_fps=24)
        self.assertTrue(accepted["passes_minimum_editorial_evidence"])

    def test_completely_unchanged_full_recording_is_not_artistic_edit(self):
        full=candidate([(0,12,1,1,1)])
        with self.assertRaises(InsufficientEditorialEvidence) as event:
            assess_minimum_editorial_evidence(full,source_seconds=12,output_fps=24)
        self.assertTrue(event.exception.diagnostics[
            "unmodified_full_source_playback_detected"])
        self.assertFalse(event.exception.diagnostics[
            "passes_minimum_editorial_evidence"])

    def test_invalid_nonnumeric_spans_do_not_bypass_audit(self):
        for value in ("NaN", float("nan"), float("inf"), None, True):
            bad = candidate([(0, 12, 1, 1, 1)])
            bad["cuts"][0]["speed"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                assess_minimum_editorial_evidence(bad, source_seconds=240, output_fps=24)


if __name__ == "__main__":
    unittest.main()
