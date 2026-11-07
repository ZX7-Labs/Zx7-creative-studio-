"""No-network adversarial tests of explicit LOCAL model evaluation requests."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.local_native_trial_request import (
    LocalTrialRequestError, validate_local_trial_request,
)

_BASE = {
    "schema": 1,
    "kind": "local-cpu-synthetic-native-editor-visual-revision",
    "model_variant": "qwen3.5-2b",
    "synthetic_only": True,
    "hosted_model_api": False,
    "private_media": False,
    "max_model_turns": 48,
    "request_id": "zx7-local-cpu-20261107",
}


class LocalNativeTrialRequestTests(unittest.TestCase):
    def test_versioned_source_request_is_explicit_and_local_only(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "research" / "local-native-trial-request.json"
        self.assertEqual(validate_local_trial_request(path), "qwen3.5-2b")
        result = subprocess.run(
            [sys.executable, "-m", "scripts.local_native_trial_request", str(path)],
            cwd=root, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, "qwen3.5-2b\n")

    def test_only_pinned_candidate_choices(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "trial.json"
            for variant in ("qwen3.5-2b", "qwen3.5-4b"):
                p.write_text(json.dumps(dict(_BASE, model_variant=variant)))
                self.assertEqual(validate_local_trial_request(p), variant)
            for invalid in ("llm-remote", True, 4, ["qwen3.5-2b"], "qwen3.5-2b\nBAD=1"):
                p.write_text(json.dumps(dict(_BASE, model_variant=invalid)))
                with self.subTest(variant=invalid), self.assertRaises(LocalTrialRequestError):
                    validate_local_trial_request(p)

    def test_no_private_or_remote_inference_or_unbounded_work(self):
        failures = [
            dict(_BASE, hosted_model_api=True),
            dict(_BASE, private_media=True),
            dict(_BASE, synthetic_only=False),
            dict(_BASE, max_model_turns=128),
            dict(_BASE, max_model_turns=True),
            dict(_BASE, schema=True),
            dict(_BASE, endpoint="https://other-host.invalid"),
            dict(_BASE, api_key="not a credential field"),
            dict(_BASE, request_id="trial\nMODEL_VARIANT=evil"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "trial.json"
            for value in failures:
                p.write_text(json.dumps(value))
                with self.subTest(value=value), self.assertRaises(LocalTrialRequestError):
                    validate_local_trial_request(p)

    def test_duplicate_fields_symlink_and_oversized_request_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "trial.json"
            p.write_text('{"schema":1,"schema":1}')
            with self.assertRaises(LocalTrialRequestError):
                validate_local_trial_request(p)
            p.write_text("x" * 2049)
            with self.assertRaises(LocalTrialRequestError):
                validate_local_trial_request(p)
            p.write_text(json.dumps(_BASE))
            link = Path(tmp) / "linked.json"
            link.symlink_to(p)
            with self.assertRaises(LocalTrialRequestError):
                validate_local_trial_request(link)
            with self.assertRaises(LocalTrialRequestError):
                validate_local_trial_request(Path(tmp) / "missing.json")


if __name__ == "__main__":
    unittest.main()
