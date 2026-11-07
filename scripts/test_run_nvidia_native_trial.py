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
from types import SimpleNamespace
from unittest.mock import patch

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

    def test_real_native_client_can_use_nvidia_function_tool_model(self):
        script = (Path(__file__).resolve().parents[1] / "engines" /
                  "velorn" / "native-model-client.py")
        factory = runpy.run_path(str(script), run_name="native_model_route_test")[
            "native_decision_model"]
        common = dict(provider="nvidia", base_url="http://127.0.0.1:8080",
                      model_id=_ALLOWED_MODEL, model_timeout=60,
                      allow_cloud_image_upload=False)
        with patch("studio_next.nvidia_model.NvidiaCreativeModel.verify_host_credentials") as check:
            structured = factory(SimpleNamespace(**common, structured_actions=True))
            legacy = factory(SimpleNamespace(**common, structured_actions=False))
        self.assertEqual(type(structured).__name__, "NvidiaNativeToolCreativeModel")
        self.assertEqual(type(legacy).__name__, "NvidiaCreativeModel")
        # Hosted API reasoning contract; self-hosted template knobs excluded.
        self.assertEqual(structured.settings.sampling["reasoning_effort"], "low")
        self.assertNotIn("chat_template_kwargs", structured.settings.sampling)
        self.assertEqual(structured.settings.sampling["temperature"], 1.0)
        self.assertEqual(structured.settings.sampling["top_p"], 0.95)
        self.assertEqual(structured.settings.max_tokens, 8192)
        self.assertEqual(legacy.settings.sampling["chat_template_kwargs"],
                         {"enable_thinking": False})
        self.assertEqual(legacy.settings.max_tokens, 2048)
        self.assertEqual(check.call_count, 2)
        with self.assertRaisesRegex(ValueError, "fixed"):
            factory(SimpleNamespace(**{**common, "base_url": "https://other.invalid"},
                                    structured_actions=True))

    def test_local_indexed_and_full_grammar_modes_both_use_live_host_context(self):
        script = (Path(__file__).resolve().parents[1] / "engines" /
                  "velorn" / "native-model-client.py")
        factory = runpy.run_path(str(script), run_name="native_local_route_test")[
            "native_decision_model"]
        common = dict(provider="local", base_url="http://127.0.0.1:8080",
                      model_id="test", model_timeout=15,
                      allow_cloud_image_upload=False)
        structured = factory(SimpleNamespace(**common, structured_actions=True))
        legacy = factory(SimpleNamespace(**common, structured_actions=False))
        self.assertEqual(type(structured).__name__, "LocalNativeStructuredCreativeModel")
        self.assertEqual(type(legacy).__name__, "LocalCreativeModel")
        self.assertNotIn("response_format", structured.settings.sampling)

    def test_native_trial_actually_requests_structured_actions(self):
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Path(scratch) / "trial"
            workspace.mkdir()
            roots = {"state": workspace / "state", "outputs": workspace / "out"}
            failed = subprocess.CompletedProcess([], 1, "", "test failure")
            with patch("scripts.run_nvidia_native_trial.prepare_trial",
                       return_value=(roots, workspace / "host.json")), patch(
                    "scripts.run_nvidia_native_trial.subprocess.run",
                    return_value=failed) as native_call:
                with self.assertRaisesRegex(RuntimeError, "trial failed"):
                    run_trial(workspace, model_id=_ALLOWED_MODEL,
                              xvfb_binary="/usr/bin/Xvfb", display="127.0.0.1:95")
            command = native_call.call_args.args[0]
            self.assertIn("--structured-actions", command)
            self.assertNotIn("--indexed-catalog", command)
            self.assertIn("--fresh-trial-project", command)
            self.assertEqual(command[command.index("--max-turns") + 1], "40")

    def test_saved_native_trial_requires_active_real_source_clip(self):
        """Only a structural acceptance fixture, not model or video proof."""
        import hashlib
        import shutil
        from scripts.run_nvidia_native_trial import verify_saved_native_trial
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            staging = workspace / "staging"
            staging.mkdir()
            source = staging / "original-neutral-gradient.mp4"
            source.write_bytes(b"unit test only; separately decoded physical video")
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            (workspace / "source-ledger.json").write_text(json.dumps([
                {"path": str(source), "sha256": sha}]))
            project_root = workspace / "projects" / "sample"
            copied = project_root / "assets" / "video" / source.name
            copied.parent.mkdir(parents=True)
            shutil.copyfile(source, copied)
            asset = {"id": "asset-1", "type": "video",
                     "path": "assets/video/" + source.name,
                     "settings": {"sourcePath": str(source)}}
            clip = {"id": "clip-1", "trackId": "video-1",
                    "assetId": "asset-1", "duration": 3.0}
            timeline = {"id": "timeline-1", "tracks": [
                {"id": "video-1", "type": "video"}], "clips": [clip]}
            project = {"currentTimelineId": "timeline-1",
                       "timelines": [timeline], "assets": [asset]}
            saved = project_root / "project.comfystudio"
            def write_project(value):
                saved.write_text(json.dumps(value), encoding="utf-8")
            write_project(project)
            result = verify_saved_native_trial(workspace)
            self.assertEqual(result["verified_source_backed_video_clips"], 1)
            self.assertEqual(result["saved_active_clip_count"], 1)
            self.assertFalse(result["artistic_quality_approved"])
            self.assertEqual(result["native_project_sha256"], hashlib.sha256(
                saved.read_bytes()).hexdigest())

            for change in (
                {"timelines": [{**timeline, "clips": []}]},
                {"currentTimelineId": "nonexistent"},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "assetId": "unknown"}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "duration": 0}]}]},
                {"assets": [{**asset, "type": "image"}]},
                {"assets": [{**asset, "settings": {
                    "sourcePath": "/not-the-original.mp4"}}]},
            ):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    write_project({**project, **change})
                    verify_saved_native_trial(workspace)
            write_project(project)
            copied.write_bytes(b"substituted bytes")
            with self.assertRaisesRegex(ValueError, "differ"):
                verify_saved_native_trial(workspace)
            shutil.copyfile(source, copied)
            (project_root / "assets" / "video" / "other.mp4").write_bytes(
                b"outsider")
            bad = {**project, "assets": [
                {**asset, "path": "../sample-not-valid.mp4"}]}
            write_project(bad)
            with self.assertRaises((ValueError, FileNotFoundError)):
                verify_saved_native_trial(workspace)
            write_project(project)
            saved.write_text('{"timelines":[],"timelines":[]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                verify_saved_native_trial(workspace)


    def test_native_export_revision_requires_changed_decoded_picture_not_new_container(self):
        """Actual FFmpeg decoder, not a mocked model or a filename assertion."""
        import hashlib
        import shutil
        from scripts.run_nvidia_native_trial import decoded_video_frames_sha256
        if shutil.which("ffmpeg") is None:
            self.skipTest("Physical native-video framehash requires installed FFmpeg")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def make(color, title, filename):
                destination = root / filename
                subprocess.run(
                    ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error",
                     "-f", "lavfi", "-i",
                     f"color=c={color}:s=64x36:r=24:d=0.5",
                     "-metadata", f"title={title}",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p",
                     "-y", str(destination)],
                    check=True, timeout=30)
                return destination
            original = make("blue", "original", "original.mp4")
            rewrapped = make("blue", "different metadata", "rewrapped.mp4")
            revised = make("red", "revision", "revised.mp4")
            # A pure retiming edit is a valid editorial revision even when
            # EVERY RGB frame is pixel-identical to the original.
            retimed = root / "retimed.mp4"
            subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error",
                 "-f", "lavfi", "-i",
                 "color=c=blue:s=64x36:r=24:d=0.5",
                 "-vf", "setpts=2*PTS", "-fps_mode", "passthrough",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-y", str(retimed)], check=True, timeout=30)
            self.assertNotEqual(
                hashlib.sha256(original.read_bytes()).digest(),
                hashlib.sha256(rewrapped.read_bytes()).digest())
            first = decoded_video_frames_sha256(original)
            self.assertEqual(first, decoded_video_frames_sha256(rewrapped))
            self.assertNotEqual(first, decoded_video_frames_sha256(revised))
            changed_timing = decoded_video_frames_sha256(retimed)
            self.assertEqual([row[2] for row in first],
                             [row[2] for row in changed_timing])
            self.assertNotEqual(first, changed_timing)
            self.assertEqual(len(first), 12)
            with self.assertRaises((subprocess.CalledProcessError, ValueError)):
                decoded_video_frames_sha256(root / "missing.mp4")

    def test_unknown_remote_model_is_refused_before_writing_files(self):
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Path(scratch) / "not-created"
            with self.assertRaisesRegex(ValueError, "audited fixed"):
                run_trial(workspace, model_id="untrusted/paid-model",
                          xvfb_binary="/usr/bin/Xvfb", display="127.0.0.1:95")
            self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
