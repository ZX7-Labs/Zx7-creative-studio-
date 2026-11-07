"""Physical fixture and host admission checks for real NVIDIA native trial.

These tests do not simulate a neural edit or claim an artistic result.
"""
from __future__ import annotations

import json
import runpy
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.nvidia_native_trial_request import validate_native_trial_request
from scripts.nvidia_smoke_request import SmokeRequestError

from scripts.run_nvidia_native_trial import (
    _ALLOWED_MODEL, _HOST_ALLOWED, _SOURCE_EDITOR, prepare_trial, run_trial,
)


class RealNvidiaTrialBootstrapTests(unittest.TestCase):
    def test_host_only_grants_and_real_owned_media_are_created(self):
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Path(scratch) / "fresh"
            roots, cfg = prepare_trial(workspace, source=_SOURCE_EDITOR)
            self.assertTrue(cfg.is_file())
            self.assertTrue((workspace / "brief.txt").is_file())
            self.assertEqual(list(roots["projects"].iterdir()), [])
            config = json.loads(cfg.read_text())
            self.assertEqual(set(config["allowed_tools"]), _HOST_ALLOWED)
            self.assertTrue(config["verify_native_exports"])
            self.assertEqual(config["projects_root"], str(roots["projects"]))
            self.assertFalse("get_ai_review_passes" in config["allowed_tools"])
            src = roots["staging"] / "original-neutral-gradient.mp4"
            self.assertGreater(src.stat().st_size, 1000)
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(src),
                            "-frames:v", "1", "-f", "null", "-"],
                           check=True, timeout=30)
            ledger = json.loads((workspace / "source-ledger.json").read_text())
            self.assertEqual(ledger[0]["path"], str(src))
            self.assertFalse(ledger[0]["preauthored_timeline"])
            with self.assertRaisesRegex(ValueError, "must not preexist"):
                prepare_trial(workspace, source=_SOURCE_EDITOR)

    def test_cloud_media_consent_is_exactly_synthetic_and_bounded(self):
        request_path = (Path(__file__).resolve().parents[1] /
                        "research" / "nvidia-native-trial-request.json")
        self.assertEqual(validate_native_trial_request(request_path), _ALLOWED_MODEL)
        baseline = json.loads(request_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as root:
            candidate = Path(root) / "request.json"
            for changes in (
                {"synthetic_only": False},
                {"cloud_synthetic_frames_allowed": False},
                {"model_id": "untrusted/remote-model"},
                {"max_turns": 800},
                {"max_turns": True},
                {"kind": "upload-private-footage"},
                {"api_key": "not-a-permitted-field"},
            ):
                candidate.write_text(
                    json.dumps({**baseline, **changes}), encoding="utf-8")
                with self.subTest(changes=changes), self.assertRaises(SmokeRequestError):
                    validate_native_trial_request(candidate)

    def test_real_editor_child_does_not_inherit_cloud_provider_key(self):
        script = (Path(__file__).resolve().parents[1] / "engines" /
                  "velorn" / "native-model-client.py")
        module = runpy.run_path(str(script), run_name="native_client_test")
        given = {"PATH": "/usr/bin", "NVIDIA_API_KEY": "synthetic-secret-test-value",
                 "OTHER_SETTING": "keep"}
        child = module["native_editor_child_environment"](given)
        self.assertNotIn("NVIDIA_API_KEY", child)
        self.assertEqual(child, {"PATH": "/usr/bin", "OTHER_SETTING": "keep"})
        self.assertIn("NVIDIA_API_KEY", given)

    def test_native_contract_excludes_ungranted_tool_prerequisites(self):
        import runpy
        from studio_next.capability_fabric import CapabilityFabric
        script = (Path(__file__).resolve().parents[1] / "engines" /
                  "velorn" / "native-model-client.py")
        method = runpy.run_path(str(script), run_name="native_contract_test")[
            "trial_machine_contracts"]
        granted = {
            "create_project": "write", "import_asset_from_path": "write",
            "add_text_clip": "write", "save_project": "write",
        }
        requires, effects = method(granted, fresh=True)
        self.assertEqual(
            set(requires), {"import_asset_from_path", "add_text_clip", "save_project"})
        self.assertEqual(effects, {"create_project": ["project_open"]})
        self.assertNotIn("add_asset_to_timeline", requires)
        tools = [{"name": name, "description": "", "inputSchema": {
            "type": "object", "properties": {}}} for name in granted]
        fabric = CapabilityFabric({
            "native": (tools, granted, requires, effects)})
        self.assertEqual(fabric.count, len(granted))
        with self.assertRaisesRegex(ValueError, "authorized project creator"):
            method({"save_project": "write"}, fresh=True)
        self.assertEqual(method({}, fresh=False), ({}, {}))

    def test_unknown_remote_model_is_refused_before_writing_files(self):
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Path(scratch) / "not-created"
            with self.assertRaisesRegex(ValueError, "audited fixed"):
                run_trial(workspace, model_id="untrusted/paid-model",
                          xvfb_binary="/usr/bin/Xvfb", display="127.0.0.1:95")
            self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
