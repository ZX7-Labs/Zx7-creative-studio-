"""No-provider/no-network tests of new G1 audiovisual consent and budget."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.nvidia_smoke_request import SmokeRequestError
from scripts.nvidia_av_trial_request import validate_av_trial_request
from scripts.run_nvidia_native_trial import _ALLOWED_MODEL, _TRIAL_MAX_TURNS

_ID = "NEW_EXPLICIT_AV_TRIAL_20261112"
_VALID = {
    "schema": 1, "kind": "nvidia-synthetic-native-audiovisual-revision",
    "model_id": _ALLOWED_MODEL, "synthetic_only": True,
    "cloud_synthetic_frames_allowed": True,
    "cloud_numerical_audio_diagnostics_allowed": True,
    "owner_media_allowed": False, "max_turns": _TRIAL_MAX_TURNS,
    "request_id": _ID, "run_authorized": True,
}


class ExplicitNvidiaAudiovisualAdmissionTests(unittest.TestCase):
    def validate(self, data, *, request_id=_ID):
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "reviewed.json"
            source.write_text(json.dumps(data))
            return validate_av_trial_request(source, dispatch_request_id=request_id)

    def test_repo_request_is_deliberately_not_a_paid_authorization(self):
        request = (Path(__file__).resolve().parents[1] / "research" /
                   "nvidia-native-audiovisual-request.json")
        with self.assertRaisesRegex(SmokeRequestError, "not newly approved"):
            validate_av_trial_request(
                request, dispatch_request_id="PENDING_UNAPPROVED_NO_EXECUTION")

    def test_exact_new_approved_media_scope_and_manual_dispatch_identity(self):
        self.assertEqual(self.validate(_VALID), _ALLOWED_MODEL)
        with self.assertRaisesRegex(SmokeRequestError, "not newly approved"):
            self.validate(_VALID, request_id="DIFFERENT_EXPLICIT_RUN_20261112")

    def test_refuses_reusing_prior_spent_visual_request(self):
        old = Path(__file__).resolve().parents[1] / "research" / "nvidia-native-trial-request.json"
        with self.assertRaises(SmokeRequestError):
            validate_av_trial_request(old, dispatch_request_id=_ID)

    def test_denies_inactive_broadened_expensive_or_injected_requests(self):
        denial = [
            {"run_authorized": False},
            {"cloud_numerical_audio_diagnostics_allowed": False},
            {"cloud_synthetic_frames_allowed": False},
            {"owner_media_allowed": True},
            {"synthetic_only": False},
            {"max_turns": _TRIAL_MAX_TURNS + 1},
            {"max_turns": True},
            {"schema": True},
            {"model_id": "unreviewed-model"},
            {"request_id": "unexpected"},
            {"kind": "nvidia-synthetic-native-editor-visual-revision"},
            {"extra_providercall": "yes"},
            {"api_key": "must-not-leak"},
            {"provider_endpoint": "https://malicious.invalid"},
        ]
        for change in denial:
            with self.subTest(change=change), self.assertRaises(SmokeRequestError):
                self.validate({**_VALID, **change})

    def test_refuses_missing_malformed_duplicate_fields_and_symlinks(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            p = root / "approval.json"
            with self.assertRaises(SmokeRequestError):
                validate_av_trial_request(p, dispatch_request_id=_ID)
            p.write_text('{"schema":1,"schema":1}')
            with self.assertRaises(SmokeRequestError):
                validate_av_trial_request(p, dispatch_request_id=_ID)
            p.write_text("x" * 2049)
            with self.assertRaises(SmokeRequestError):
                validate_av_trial_request(p, dispatch_request_id=_ID)
            p.write_text(json.dumps(_VALID))
            link = root / "linked.json"
            link.symlink_to(p)
            with self.assertRaises(SmokeRequestError):
                validate_av_trial_request(link, dispatch_request_id=_ID)
            for wrong_id in ("", "x", "a\nb", "long_" * 30, None):
                with self.assertRaises(SmokeRequestError):
                    validate_av_trial_request(p, dispatch_request_id=wrong_id)


if __name__ == "__main__":
    unittest.main()
