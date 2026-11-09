"""Admission-only local model budget checks; never load weights or start an editor."""
import contextlib
import io
from pathlib import Path
import unittest

from scripts.run_native_model_trial import build_trial_parser


class NativeModelTrialBudgetTests(unittest.TestCase):
    @staticmethod
    def arguments(*extra):
        return ["--source", "/tmp/pinned-velorn", "--runtime", "/tmp/local-runtime",
                "--artifacts", "/tmp/retained-trial", *extra]

    def test_default_remains_bounded_for_non_extended_local_runs(self):
        args = build_trial_parser().parse_args(self.arguments())
        self.assertEqual(args.model_timeout, 300)
        self.assertEqual(args.trial_timeout, 2400)

    def test_extended_cpu_evaluation_requires_explicit_allowed_values(self):
        args = build_trial_parser().parse_args(self.arguments(
            "--model-timeout", "480", "--trial-timeout", "13200"))
        self.assertEqual(args.model_timeout, 480)
        self.assertEqual(args.trial_timeout, 13200)
        for bad in ("0", "-1", "13201", "14400", "999999", "3600"):
            with self.subTest(invalid_trial_budget=bad), self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    build_trial_parser().parse_args(self.arguments("--trial-timeout", bad))
        for bad in ("0", "1200", "481", "99999"):
            with self.subTest(invalid_turn_budget=bad), self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    build_trial_parser().parse_args(self.arguments("--model-timeout", bad))

    def test_opt_in_ci_workflow_has_an_outer_timeout_and_artifact_preservation(self):
        # Regression guard for the workflow's relationship to the parser, not
        # a substitute for a live model trial or proof of quality.
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/zx7-live-native-model.yml").read_text()
        job = workflow.split("  actual-local-model-and-native-editor:", 1)[1]
        self.assertIn("    timeout-minutes: 240", job)
        self.assertIn("--model-timeout 480 --trial-timeout 13200", job)
        self.assertIn("github.event_name != 'pull_request'", job)
        self.assertIn("needs.pr-local-model-opt-in.outputs.requested == 'true'", job)
        self.assertIn("if: always()", job)
        self.assertIn("name: zx7-live-native-model-", job)


if __name__ == "__main__":
    unittest.main()
