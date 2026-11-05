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
            assess_minimum_editorial_evidence(observed, source_seconds=240.032)
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
                x = assess_minimum_editorial_evidence(example, source_seconds=240)
                self.assertTrue(x["passes_minimum_editorial_evidence"])
                self.assertFalse(x["artistic_quality_certified"])

    def test_invalid_nonnumeric_spans_do_not_bypass_audit(self):
        for value in ("NaN", float("nan"), float("inf"), None, True):
            bad = candidate([(0, 12, 1, 1, 1)])
            bad["cuts"][0]["speed"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                assess_minimum_editorial_evidence(bad, source_seconds=240)


if __name__ == "__main__":
    unittest.main()
