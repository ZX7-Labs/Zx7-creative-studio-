"""No-network tests for explicit GitHub NVIDIA evaluation admission."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.nvidia_smoke_request import SmokeRequestError, validate_smoke_request


_BASE = {
    "schema": 1,
    "kind": "nvidia-no-media-protocol-smoke",
    "model_variant": "nemotron-super-vl",
    "media_upload": False,
    "max_tokens": 128,
    "request_id": "nvidia-protocol-contract-0001",
}


class NvidiaSmokeRequestAdmissionTests(unittest.TestCase):
    def test_current_versioned_request_is_valid_and_no_media(self):
        request = Path(__file__).resolve().parents[1] / "research" / "nvidia-smoke-request.json"
        self.assertEqual(validate_smoke_request(request), "nemotron-super-vl")

    def test_only_strict_model_variants_are_allowed(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "reviewed.json"
            for model in ("nemotron-super-vl", "qwen3.5-122b"):
                data = dict(_BASE, model_variant=model)
                path.write_text(json.dumps(data), encoding="utf-8")
                self.assertEqual(validate_smoke_request(path), model)
            for bad in ("other", "model\\nMALICIOUS=value", 42, False, ["nemotron-super-vl"]):
                path.write_text(json.dumps(dict(_BASE, model_variant=bad)), encoding="utf-8")
                with self.subTest(bad=bad), self.assertRaises(SmokeRequestError):
                    validate_smoke_request(path)

    def test_rejects_broader_compute_private_media_and_extra_fields(self):
        bad = (
            dict(_BASE, media_upload=True),
            dict(_BASE, max_tokens=32768),
            dict(_BASE, max_tokens=True),
            dict(_BASE, schema=True),
            dict(_BASE, kind="native-video-editor-write"),
            dict(_BASE, request_id="bad\\nINJECTED=value"),
            dict(_BASE, api_key="must-not-appear"),
            dict(_BASE, endpoint="https://attacker.invalid"),
        )
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "request.json"
            for value in bad:
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.subTest(value=value), self.assertRaises(SmokeRequestError):
                    validate_smoke_request(path)

    def test_rejects_duplicate_fields_and_oversize_request(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "request.json"
            path.write_text('{"schema":1,"schema":1}', encoding="utf-8")
            with self.assertRaises(SmokeRequestError):
                validate_smoke_request(path)
            path.write_text("x" * 2049, encoding="utf-8")
            with self.assertRaises(SmokeRequestError):
                validate_smoke_request(path)

    def test_rejects_missing_and_symbolic_linked_requests(self):
        with tempfile.TemporaryDirectory() as root:
            missing = Path(root) / "missing.json"
            with self.assertRaises(SmokeRequestError):
                validate_smoke_request(missing)
            target = Path(root) / "real.json"
            target.write_text(json.dumps(_BASE), encoding="utf-8")
            linked = Path(root) / "link.json"
            linked.symlink_to(target)
            with self.assertRaises(SmokeRequestError):
                validate_smoke_request(linked)


if __name__ == "__main__":
    unittest.main()
