"""Physical fixture and host admission checks for real NVIDIA native trial.

These tests do not simulate a neural edit or claim an artistic result.
"""
from __future__ import annotations

import asyncio
import json
import runpy
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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
            self.assertEqual(config["required_export_delivery"], {
                "width": 640, "height": 360, "fps": 24,
                "max_duration": 6, "video_codec": "h264",
            })
            from studio_next.body_editor_policy import load_editor_config
            admitted = load_editor_config(cfg)
            self.assertEqual(dict(admitted.required_export_delivery),
                             config["required_export_delivery"])
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
                {"max_turns": 40},  # cannot silently re-run a stale consent budget
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

    def test_pinned_real_electron_preview_attestation_requires_clean_exact_source(self):
        """No agent route may claim read-only marker semantics from a random
        editor checkout. Only the exact pinned clean Electron MCP source
        grants the strict top-level preview protocol to eligible tools.
        """
        script = (Path(__file__).resolve().parents[1] / "engines" /
                  "velorn" / "native-model-client.py")
        method = runpy.run_path(str(script), run_name="native_marker_contract_test")[
            "pinned_electron_marker_previews"]
        source = Path(__file__).resolve().parents[1] / "third_party" / "velorn"
        grants = {
            "add_timeline_markers": "write",
            "remove_timeline_markers": "read",
            "set_timeline_marker_properties": "write",
        }
        pin = "b3c02adbd5c0779feb8abf34978299e9502cc0e7"
        witnessed = []

        def git_response(argv, **options):
            witnessed.append((argv, options))
            if "rev-parse" in argv:
                return subprocess.CompletedProcess(argv, 0, f"{source.resolve()}\n{pin}\n", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        with patch("subprocess.run", side_effect=git_response):
            self.assertEqual(method(source, grants), (
                "add_timeline_markers", "set_timeline_marker_properties"))
        self.assertEqual(len(witnessed), 2)
        self.assertEqual(witnessed[1][0][-2:], ["--", "electron/mcpServer.js"])
        self.assertTrue(all("NVIDIA_API_KEY" not in opts["env"]
                            for _, opts in witnessed))

        def bad_commit(argv, **_):
            return subprocess.CompletedProcess(argv, 0, f"{source.resolve()}\ndifferent-revision\n", "")
        with patch("subprocess.run", side_effect=bad_commit):
            self.assertEqual(method(source, grants), ())

        def parent_checkout(argv, **_):
            return subprocess.CompletedProcess(argv, 0, f"{source.parent.resolve()}\n{pin}\n", "")
        with patch("subprocess.run", side_effect=parent_checkout):
            self.assertEqual(method(source, grants), ())

        def edited_source(argv, **_):
            return subprocess.CompletedProcess(
                argv, 0 if "rev-parse" in argv else 1,
                f"{source.resolve()}\n{pin}\n" if "rev-parse" in argv else "", "")
        with patch("subprocess.run", side_effect=edited_source):
            self.assertEqual(method(source, grants), ())

        with patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(method(source, grants), ())
        with self.assertRaises(ValueError):
            method(source, {"add_timeline_markers": "unknown-access"})

    def test_pinned_clip_edit_previews_require_source_integrity_and_write_grant(self):
        """Default native move/trim/delete preview plans do not grant
        mutation authority to model text or unknown upstream editor builds.
        """
        from studio_next.native_editor_source_pin import (
            pinned_electron_clip_edit_previews)
        source = Path(__file__).resolve().parents[1] / "third_party" / "velorn"
        pin = "b3c02adbd5c0779feb8abf34978299e9502cc0e7"
        def clean(argv, **_):
            return subprocess.CompletedProcess(
                argv, 0, f"{source.resolve()}\n{pin}\n" if "rev-parse" in argv else "", "")
        grants = {"move_clips": "write", "trim_clips": "write",
                  "delete_clips": "read", "get_project": "read"}
        with patch("subprocess.run", side_effect=clean):
            self.assertEqual(pinned_electron_clip_edit_previews(
                source, grants), ("move_clips", "trim_clips"))
        with patch("subprocess.run", side_effect=lambda argv, **_: (
                subprocess.CompletedProcess(
                    argv, 0, f"{source.resolve()}\nunknown-revision\n" if "rev-parse" in argv
                    else "", ""))):
            self.assertEqual(pinned_electron_clip_edit_previews(
                source, grants), ())
        with self.assertRaises(ValueError):
            pinned_electron_clip_edit_previews(
                source, {"move_clips": "execute-all"})

    def test_pinned_timeline_jpeg_requires_exact_clean_source_and_two_read_grants(self):
        """An actual native timeline JPEG is not a physical-export
        verifier. Only the audited pinned Electron MCP entrypoint and
        actual read grants may enable this separate model observation.
        """
        from studio_next.native_editor_source_pin import (
            pinned_electron_timeline_frame_previews)
        source = Path(__file__).resolve().parents[1] / "third_party" / "velorn"
        pin = "b3c02adbd5c0779feb8abf34978299e9502cc0e7"

        def clean_source(argv, **kwargs):
            if "rev-parse" in argv:
                return subprocess.CompletedProcess(argv, 0, f"{source.resolve()}\n{pin}\n", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        grants = {"inspect_timeline_frame": "read", "get_project": "read"}
        with patch("subprocess.run", side_effect=clean_source):
            self.assertEqual(pinned_electron_timeline_frame_previews(source, grants),
                             ("inspect_timeline_frame",))
            self.assertEqual(pinned_electron_timeline_frame_previews(
                source, {"inspect_timeline_frame": "read"}), ())
            self.assertEqual(pinned_electron_timeline_frame_previews(
                source, {"inspect_timeline_frame": "write",
                         "get_project": "read"}), ())
        def modified_source(argv, **kwargs):
            return subprocess.CompletedProcess(
                argv, 0 if "rev-parse" in argv else 1,
                f"{source.resolve()}\n{pin}\n" if "rev-parse" in argv else "", "")
        with patch("subprocess.run", side_effect=modified_source):
            self.assertEqual(pinned_electron_timeline_frame_previews(source, grants), ())
        with self.assertRaises(ValueError):
            pinned_electron_timeline_frame_previews(
                source, {"inspect_timeline_frame": "promoted-to-write"})

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
        with_asset = {**granted, "add_asset_to_timeline": "write",
                      "replace_clip_with_asset": "write"}
        source_rules, _ = method(with_asset, fresh=True)
        self.assertEqual(source_rules["add_asset_to_timeline"],
                         ["project_open", "project_assets_available"])
        self.assertEqual(source_rules["replace_clip_with_asset"],
                         ["project_open", "project_assets_available"])
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

    def test_actual_native_launcher_requires_media_consent_only_for_cloud_review(self):
        """Exercise launcher admission with real model factories, stopping
        before any editor process or model request can be started.
        """
        script = (Path(__file__).resolve().parents[1] / "engines" /
                  "velorn" / "native-model-client.py")
        entry = runpy.run_path(str(script), run_name="native_review_consent_test")["main"]

        class ReachedNativeLaunch(RuntimeError):
            pass

        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            state = root / "state"
            state.mkdir()
            config = root / "host.json"
            config.write_text(json.dumps({
                "verify_native_exports": True,
                "allowed_tools": {"get_project": "read", "update_text_clip": "write"},
            }))
            brief = root / "brief.txt"
            brief.write_text("Revise the editable project after observing its export.")
            common = dict(
                source=root, state=state, config=config, brief_file=brief,
                receipt=root / "receipt.jsonl", xvfb_binary=None,
                xvfb_lib_dir=None, display=None, software_gpu=False,
                no_sandbox=False, base_url="http://127.0.0.1:8080",
                model_id=_ALLOWED_MODEL, model_timeout=15,
                structured_actions=True, fresh_trial_project=False, max_turns=4)
            cases = (
                ("reviewed-revision", "local", False, False, None),
                ("reviewed-revision", "nvidia", False, False, "explicit synthetic image upload permission"),
                ("reviewed-revision", "local", True, False, "Cloud-media consent requires --provider nvidia"),
                ("reviewed-revision", "nvidia", True, False, None),
                ("none", "nvidia", False, False, None),
                ("export", "nvidia", False, False, None),
                ("reviewed-av-revision", "local", False, False, None),
                ("reviewed-av-revision", "nvidia", True, False, "explicit audio diagnostics consent"),
                ("reviewed-av-revision", "nvidia", False, True, "explicit synthetic image upload permission"),
                ("reviewed-av-revision", "nvidia", True, True, None),
                ("reviewed-revision", "nvidia", True, True, "require NVIDIA audiovisual review mode"),
            )
            for profile, provider, cloud_consent, audio_consent, refusal in cases:
                args = SimpleNamespace(**common, provider=provider,
                                       evaluation_evidence=profile,
                                       allow_cloud_image_upload=cloud_consent,
                                       allow_cloud_audio_diagnostics=audio_consent)
                with self.subTest(profile=profile, provider=provider, image=cloud_consent,
                                  audio=audio_consent), patch(
                        "studio_next.nvidia_model.NvidiaCreativeModel.verify_host_credentials"
                        ) as credentials, patch.dict(entry.__globals__, {
                            "stdio_client": MagicMock(),
                            "ClientSession": MagicMock(),
                            "CapabilityGateway": MagicMock(side_effect=ReachedNativeLaunch),
                        }):
                    launch = entry.__globals__["stdio_client"]
                    launch.return_value.__aenter__.return_value = (None, None)
                    session = entry.__globals__["ClientSession"]
                    session.return_value.__aenter__.return_value = SimpleNamespace(
                        initialize=AsyncMock())
                    gateway = entry.__globals__["CapabilityGateway"]
                    if refusal is None:
                        with self.assertRaises(ReachedNativeLaunch):
                            asyncio.run(entry(args))
                        launch.assert_called_once()
                        grants = gateway.call_args.args[0]["editor"][1]
                        self.assertEqual("zx7_observe_verified_export_audio" in grants,
                                         provider == "local")
                        self.assertEqual("zx7_observe_verified_export_audio_timeline" in grants,
                                         provider == "local" or audio_consent)
                    else:
                        with self.assertRaisesRegex(ValueError, refusal):
                            asyncio.run(entry(args))
                        launch.assert_not_called()
                        gateway.assert_not_called()
                    self.assertEqual(credentials.call_count,
                                     1 if provider == "nvidia" else 0)


    def test_public_nvidia_trial_artifact_is_a_strict_synthetic_allowlist(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/zx7-nvidia-native-editor-trial.yml").read_text()
        upload = workflow.split("uses: actions/upload-artifact@v4", 1)[1]
        self.assertIn("include-hidden-files: false", upload)
        self.assertIn("          path: |", upload)
        paths = [line.strip() for line in upload.split("          path: |", 1)[1]
                 .split("          include-hidden-files:", 1)[0].splitlines()
                 if line.strip()]
        prefix = "${{ runner.temp }}/zx7-nvidia-native-trial/"
        self.assertTrue(all(p.startswith(prefix) for p in paths), paths)
        suffixes = [p[len(prefix):] for p in paths]
        # Every added forensic file requires explicit security review. Past
        # uploads of the entire root accidentally included Electron Cookies,
        # Chromium Cache and local-storage data from state/session-*/.
        self.assertEqual(len(suffixes), len(set(suffixes)))
        self.assertEqual(set(suffixes), {
            "host-grants.json", "brief.txt", "source-ledger.json",
            "native-evaluation.json", "native-journal.jsonl",
            "native-client-stdout.txt", "native-client-stderr.txt",
            "staging/original-neutral-gradient.mp4", "outputs/*.mp4",
            "projects/**/*.comfystudio",
            "projects/**/assets/video/*.mp4",
            "projects/**/project.thumbnail.webp",
        })
        self.assertNotIn("zx7-nvidia-native-trial/\n", upload)
        self.assertTrue(all(not p.startswith("state/") for p in suffixes))

    def test_offline_pr_admission_is_separate_from_single_hosted_api_lane(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/zx7-nvidia-native-editor-trial.yml").read_text()
        group = workflow.split("concurrency:", 1)[1].split("jobs:", 1)[0]
        self.assertIn("github.event_name == 'pull_request'", group)
        self.assertIn("zx7-nvidia-offline-{0}", group)
        self.assertIn("'zx7-nvidia-native-creative-acceptance'", group)
        self.assertIn("cancel-in-progress: false", group)
        self.assertIn("if: github.event_name == 'pull_request'", workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)

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
            self.assertEqual(command[command.index("--max-turns") + 1], "48")
            # Last verified remote 120B call timed out at 90s while reasoning.
            # Use bounded 180s patience, no extra model turns or retries.
            self.assertEqual(command[command.index("--model-timeout") + 1], "180")
            self.assertEqual(native_call.call_args.kwargs["timeout"], 1500)
            self.assertEqual(native_call.call_count, 1)
            self.assertLessEqual(
                native_call.call_args.kwargs["timeout"], 35 * 60 - 5 * 60)


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
                    "assetId": "asset-1", "startTime": 0.0, "duration": 3.0}
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

            # Local trials stage two originals. A valid placed source must be
            # resolved by its ledger identity, independently of ledger order.
            second = staging / "second.mp4"
            second.write_bytes(b"another authorized test original")
            sources = [{"path": str(second), "sha256": hashlib.sha256(second.read_bytes()).hexdigest()},
                       {"path": str(source), "sha256": sha}]
            self.assertEqual(verify_saved_native_trial(workspace, source_ledger=sources,
                                                       max_clip_duration=8), result)
            second.write_bytes(b"changed staged source")
            with self.assertRaisesRegex(ValueError, "differs from owner SHA ledger"):
                verify_saved_native_trial(workspace, source_ledger=sources, max_clip_duration=8)

            # A source is still an active trial picture when it intersects
            # the delivery interval by a fraction of a second. This validates
            # source placement, not pixels being visible through other layers.
            partly_visible = {**clip, "startTime": 5.75}
            write_project({**project, "timelines": [
                {**timeline, "clips": [partly_visible]}]})
            self.assertEqual(
                verify_saved_native_trial(workspace)["verified_source_backed_video_clips"], 1)
            write_project(project)

            for change in (
                {"timelines": [{**timeline, "clips": []}]},
                {"currentTimelineId": "nonexistent"},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "assetId": "unknown"}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "duration": 0}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "duration": float("inf")}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "duration": 10 ** 400}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "startTime": 6.0}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "startTime": 60.0}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "startTime": 10 ** 400}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "startTime": -0.25}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "startTime": float("nan")}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "startTime": "0"}]}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "startTime": True}]}]},
                {"timelines": [{**timeline, "clips": [
                    {key: value for key, value in clip.items()
                     if key != "startTime"}]}]},
                {"assets": [{**asset, "type": "image"}]},
                {"timelines": [{**timeline, "clips": [
                    {**clip, "enabled": False}]}]},
                {"timelines": [{**timeline, "tracks": [
                    {"id": "video-1", "type": "video", "visible": False}]}]},
                {"timelines": [{**timeline, "tracks": [
                    {"id": "video-1", "type": "video"},
                    {"id": "video-1", "type": "audio"}]}]},
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
        from scripts.run_nvidia_native_trial import (
            decode_trial_export, decoded_video_frames_sha256,
            trial_delivery_profile_compliant, trial_picture_changed,
        )
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("Physical native-video proof requires FFmpeg and FFprobe")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def make(color, title, filename, *, size="64x36", sar="1", matrix="bt709",
                     retime=False, rate=24, seconds=0.5):
                destination = root / filename
                filters = f"setsar={sar}" + (",setpts=2*PTS" if retime else "")
                subprocess.run(
                    ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error",
                     "-f", "lavfi", "-i",
                     f"color=c={color}:s={size}:r={rate}:d={seconds}",
                     "-vf", filters, "-fps_mode", "passthrough",
                     "-metadata", f"title={title}",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p",
                     "-color_primaries", "bt709", "-color_trc", "bt709",
                     "-colorspace", matrix, "-color_range", "tv",
                     "-y", str(destination)],
                    check=True, timeout=30)
                return destination
            original = make("blue", "original", "original.mp4")
            rewrapped = make("blue", "different metadata", "rewrapped.mp4")
            revised = make("red", "revision", "revised.mp4")
            resized = make("blue", "resized", "resized.mp4", size="128x72")
            stretched = make("blue", "stretched", "stretched.mp4", sar="4/3")
            color_tagged = make("blue", "color tagged", "color-tagged.mp4", matrix="smpte170m")
            # A pure retiming edit is a valid editorial revision even when
            # EVERY RGB frame is pixel-identical to the original.
            retimed = make("blue", "retimed", "retimed.mp4", retime=True)
            longer = make("blue", "longer", "longer.mp4", seconds=1.0)
            faster = make("blue", "faster", "faster.mp4", rate=30)
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
            before = decode_trial_export(original)
            self.assertEqual(before.presentation, first)
            self.assertFalse(trial_picture_changed(before, decode_trial_export(rewrapped)))
            self.assertTrue(trial_picture_changed(before, decode_trial_export(revised)))
            self.assertTrue(trial_picture_changed(before, decode_trial_export(retimed)))
            # This is a synthetic resource-limit gate, NOT a product video
            # size restriction. Actual decoder timestamps must also comply.
            trial = lambda item: trial_delivery_profile_compliant(
                item, width=64, height=36, fps=24, max_seconds=0.5)
            self.assertTrue(trial(before))
            # The actual pinned 60-second Velorn H.264 proof has no SAR
            # metadata. It must not fail an otherwise sound 640x360 export.
            self.assertTrue(trial(before._replace(picture_profile={
                **before.picture_profile, "sample_aspect_ratio": None})))
            self.assertTrue(trial(decode_trial_export(revised)))
            self.assertFalse(trial_delivery_profile_compliant(before))
            self.assertFalse(trial(decode_trial_export(retimed)))
            self.assertFalse(trial(decode_trial_export(longer)))
            self.assertFalse(trial(decode_trial_export(faster)))
            resize_result = decode_trial_export(resized)
            self.assertNotEqual(before.presentation, resize_result.presentation)
            self.assertEqual(resize_result.picture_profile["width"], 128)
            self.assertEqual(resize_result.picture_profile["height"], 72)
            self.assertFalse(trial_picture_changed(before, resize_result))
            self.assertFalse(trial(resize_result))
            sar_result = decode_trial_export(stretched)
            self.assertEqual(sar_result.picture_profile["sample_aspect_ratio"], "4:3")
            self.assertFalse(trial_picture_changed(before, sar_result))
            self.assertFalse(trial(sar_result))
            color_result = decode_trial_export(color_tagged)
            self.assertEqual(color_result.picture_profile["color_space"], "smpte170m")
            self.assertFalse(trial_picture_changed(before, color_result))
            with self.assertRaises((subprocess.CalledProcessError, ValueError)):
                decoded_video_frames_sha256(root / "missing.mp4")

    def test_audio_cloud_consent_required_before_any_workspace_or_native_launch(self):
        """Do not promote an earlier visual-only allowance into cloud A/V usage."""
        with tempfile.TemporaryDirectory() as scratch:
            trial = Path(scratch) / "no-consent"
            with self.assertRaisesRegex(ValueError, "explicit audio diagnostics consent"):
                run_trial(trial, model_id=_ALLOWED_MODEL,
                          xvfb_binary="/usr/bin/Xvfb", display="127.0.0.1:95",
                          audiovisual=True)
            self.assertFalse(trial.exists())
            with self.assertRaisesRegex(ValueError, "require audiovisual"):
                run_trial(trial, model_id=_ALLOWED_MODEL,
                          xvfb_binary="/usr/bin/Xvfb", display="127.0.0.1:95",
                          allow_cloud_audio_diagnostics=True)
            self.assertFalse(trial.exists())

    def test_real_synthetic_audiovisual_bootstrap_and_model_selection(self):
        """Two original signals, no model-directed shot list or paid request."""
        import hashlib
        from scripts.run_nvidia_native_trial import AV_TRIAL_REVISION_TOOLS
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Path(scratch) / "av"
            roots, config_path = prepare_trial(
                workspace, source=_SOURCE_EDITOR, audiovisual=True)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(set(config["allowed_tools"]),
                             _HOST_ALLOWED | AV_TRIAL_REVISION_TOOLS)
            ledger = json.loads((workspace / "source-ledger.json").read_text())
            self.assertEqual(len(ledger), 2)
            self.assertEqual({Path(item["path"]).suffix for item in ledger},
                             {".mp4", ".wav"})
            self.assertTrue(all(not x["preauthored_timeline"] for x in ledger))
            for item in ledger:
                path = Path(item["path"])
                self.assertTrue(path.is_file())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                                 item["sha256"])
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
                                "-i", str(path), "-f", "null", "-"],
                               check=True, timeout=30)
            self.assertIn("timed sound diagnostics",
                          (workspace / "brief.txt").read_text())
            with self.assertRaisesRegex(ValueError, "must not preexist"):
                prepare_trial(workspace, source=_SOURCE_EDITOR, audiovisual=True)

        # Nothing launches the model. Verify exact planned CLI arguments
        # before accepting a future separately consented hosted experiment.
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Path(scratch) / "trial"
            workspace.mkdir()
            roots = {"state": workspace / "state", "outputs": workspace / "out"}
            with patch("scripts.run_nvidia_native_trial.prepare_trial",
                       return_value=(roots, workspace / "host.json")) as staged, patch(
                    "scripts.run_nvidia_native_trial.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 1, "", "offline stop")
            ) as child:
                with self.assertRaisesRegex(RuntimeError, "trial failed"):
                    run_trial(workspace, model_id=_ALLOWED_MODEL,
                              xvfb_binary="/usr/bin/Xvfb",
                              display="127.0.0.1:95", audiovisual=True,
                              allow_cloud_audio_diagnostics=True)
            staged.assert_called_once_with(
                workspace, source=_SOURCE_EDITOR, audiovisual=True)
            command = child.call_args.args[0]
            self.assertEqual(command[command.index("--evaluation-evidence") + 1],
                             "reviewed-av-revision")
            self.assertIn("--allow-cloud-audio-diagnostics", command)
            self.assertIn("--record-av-project-snapshots", command)
            self.assertIn("--structured-actions", command)
            self.assertEqual(child.call_count, 1)

    def test_audiovisual_native_source_custody_requires_original_active_sound(self):
        """The saved project must contain actual video AND audio originals."""
        import hashlib
        import shutil
        from scripts.run_nvidia_native_trial import verify_saved_native_trial
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            stage = root / "staging"
            stage.mkdir()
            video = stage / "original-neutral-gradient.mp4"
            sound = stage / "original-synthetic-sound.wav"
            video.write_bytes(b"source video unit bytes")
            sound.write_bytes(b"source sound unit bytes")
            ledger = [{"path": str(p),
                       "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                       "media_kind": kind}
                      for p, kind in ((video, "video"), (sound, "audio"))]
            (root / "source-ledger.json").write_text(json.dumps(ledger))
            project_root = root / "projects" / "unit"
            copies = []
            assets = []
            clips = []
            for index, (source, kind) in enumerate(((video, "video"), (sound, "audio"))):
                relative = f"assets/{kind}/{source.name}"
                target = project_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                copies.append(target)
                assets.append({"id": f"asset-{kind}", "type": kind,
                               "path": relative,
                               "settings": {"sourcePath": str(source)}})
                clips.append({"id": f"clip-{kind}", "assetId": f"asset-{kind}",
                              "trackId": f"track-{kind}", "enabled": True,
                              "startTime": 0.0, "duration": 4.0})
            base = {"currentTimelineId": "timeline",
                    "timelines": [{"id": "timeline",
                                   "tracks": [{"id": "track-video", "type": "video"},
                                              {"id": "track-audio", "type": "audio"}],
                                   "clips": clips}],
                    "assets": assets}
            saved = project_root / "project.comfystudio"
            def run(project):
                saved.write_text(json.dumps(project), encoding="utf-8")
                return verify_saved_native_trial(root, require_audio=True)
            result = run(base)
            self.assertEqual(result["verified_source_backed_audio_clips"], 1)
            self.assertEqual(result["verified_source_backed_video_clips"], 1)
            self.assertFalse(result["artistic_quality_approved"])
            for change in (
                [{"id": "track-video", "type": "video"},
                 {"id": "track-audio", "type": "audio", "muted": True}],
                [{"id": "track-video", "type": "video"},
                 {"id": "track-audio", "type": "video"}],
            ):
                with self.subTest(tracks=change), self.assertRaisesRegex(
                    ValueError, "source-backed audible clip"
                ):
                    run({**base, "timelines": [{**base["timelines"][0],
                                               "tracks": change}]})
            with self.assertRaisesRegex(ValueError, "source-backed audible clip"):
                run({**base, "timelines": [{**base["timelines"][0],
                                           "clips": clips[:1]}]})
            with self.assertRaisesRegex(ValueError, "source-backed audible clip"):
                run({**base, "timelines": [{**base["timelines"][0],
                                           "clips": [clips[0], {**clips[1], "startTime": 6.0}]}]})
            run(base)
            # Source identities are typed by the host, not guessed from
            # filenames. Swapping a manifest's audio/video role is rejected
            # even if all physical SHA-256 values still match.
            swapped = [
                {**ledger[0], "media_kind": "audio"},
                {**ledger[1], "media_kind": "video"},
            ]
            (root / "source-ledger.json").write_text(json.dumps(swapped))
            with self.assertRaisesRegex(ValueError, "contradicts"):
                verify_saved_native_trial(root, require_audio=True)
            (root / "source-ledger.json").write_text(json.dumps(ledger))
            copies[1].write_bytes(b"substituted sound")
            with self.assertRaisesRegex(ValueError, "differ"):
                verify_saved_native_trial(root, require_audio=True)

    def test_physical_audio_decode_rejects_missing_silence_and_wrong_timing(self):
        """Real FFmpeg PCM decoding; never infer sound from MP4 metadata."""
        import shutil
        from scripts.run_nvidia_native_trial import decode_trial_audio
        if not shutil.which("ffmpeg"):
            self.skipTest("Physical PCM proof requires FFmpeg")
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            def render(name, tone):
                target = root / name
                subprocess.run([
                    "ffmpeg", "-nostdin", "-v", "error",
                    "-f", "lavfi", "-i", "color=c=navy:s=64x36:r=24:d=0.5",
                    "-f", "lavfi", "-i",
                    ("sine=frequency=440:sample_rate=48000:duration=0.5"
                     if tone else
                     "anullsrc=channel_layout=mono:sample_rate=48000:d=0.5"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(target)
                ], check=True, timeout=30)
                return target
            good = render("audible.mp4", True)
            silent = render("silent.mp4", False)
            present = decode_trial_audio(good, expected_video_seconds=0.5,
                                         max_seconds=1)
            self.assertTrue(present.audible)
            # The decoder must limit PCM generation BEFORE capture_output,
            # not after loading potentially unbounded audio into memory.
            with patch("scripts.run_nvidia_native_trial.subprocess.run",
                       return_value=subprocess.CompletedProcess(
                           [], 0, b"\0" * 8000, b"")) as bounded:
                staged = decode_trial_audio(good, expected_video_seconds=0.5,
                                            max_seconds=1)
            self.assertFalse(staged.audible)
            command = bounded.call_args.args[0]
            self.assertEqual(command[command.index("-t") + 1], "2")
            self.assertNotIn("NVIDIA_API_KEY", bounded.call_args.kwargs["env"])
            self.assertEqual(present.sample_rate, 8000)
            self.assertGreater(present.sample_count, 3000)
            self.assertFalse(
                decode_trial_audio(silent, expected_video_seconds=0.5,
                                   max_seconds=1).audible)
            with self.assertRaisesRegex(ValueError, "aligned"):
                decode_trial_audio(good, expected_video_seconds=0.25,
                                   max_seconds=1)
            with self.assertRaisesRegex(ValueError, "budget"):
                decode_trial_audio(good, expected_video_seconds=float("nan"))
            no_sound = root / "video-only.mp4"
            subprocess.run([
                "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi",
                "-i", "color=c=navy:s=64x36:r=24:d=0.5",
                "-c:v", "libx264", str(no_sound)
            ], check=True, timeout=30)
            with self.assertRaisesRegex(ValueError, "missing"):
                decode_trial_audio(no_sound, expected_video_seconds=0.5,
                                   max_seconds=1)

    def test_failed_model_audiovisual_export_retains_negative_audio_receipt(self):
        """A model-reported success cannot erase absent sound from forensic output."""
        import hashlib
        from scripts.run_nvidia_native_trial import (
            DecodedTrialAudio, DecodedTrialExport)
        from studio_next.native_render_evidence import destination_digest
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Path(scratch) / "run"
            workspace.mkdir()
            outputs = workspace / "outputs"
            outputs.mkdir()
            first, second = (outputs / x for x in ("before.mp4", "after.mp4"))
            first.write_bytes(b"synthetic-video-a")
            second.write_bytes(b"synthetic-video-b")
            def sha(path):
                return hashlib.sha256(path.read_bytes()).hexdigest()
            def pair_entry(path):
                return {"destination_sha256": destination_digest(str(path)),
                        "export_sha256": sha(path), "timeline_sha256": "fixed-scope"}
            model_result = {
                "status": "model_finished_unverified",
                "evaluation_evidence_satisfied": True,
                "reviewed_native_audiovisual_pair": [pair_entry(first), pair_entry(second)],
                "model_selected_write_receipts": 2,
                "independently_verified_export_receipts": 2,
            }
            completed = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(model_result) + "\n", stderr="")
            def video(path):
                return DecodedTrialExport(
                    (str(path), "", path.stat().st_size, "", sha(path)),
                    ((str(path.name), "1/24", sha(path)),),
                    {"width": 640, "height": 360, "codec_name": "h264"})
            def audio(path, **_):
                if path == second:
                    raise ValueError("Decoded audio absent")
                return DecodedTrialAudio("f" * 64, 8000, 4000, 0.5, .1, True)
            saved = {"saved_native_timeline_sha256": "fixed-scope",
                     "verified_source_backed_video_clips": 1,
                     "verified_source_backed_audio_clips": 1}
            roots = {"outputs": outputs, "state": workspace / "state"}
            with patch("scripts.run_nvidia_native_trial.prepare_trial",
                       return_value=(roots, workspace / "config.json")), patch(
                    "scripts.run_nvidia_native_trial.subprocess.run",
                    return_value=completed), patch(
                    "scripts.run_nvidia_native_trial.decode_trial_export",
                    side_effect=video), patch(
                    "scripts.run_nvidia_native_trial.decode_trial_audio",
                    side_effect=audio), patch(
                    "scripts.run_nvidia_native_trial.verify_saved_native_trial",
                    return_value=saved) as project_check, patch(
                    "scripts.run_nvidia_native_trial.trial_delivery_profile_compliant",
                    return_value=True):
                with self.assertRaisesRegex(RuntimeError, "visual-revision-export proof"):
                    run_trial(workspace, model_id=_ALLOWED_MODEL,
                              xvfb_binary="/usr/bin/Xvfb",
                              display="127.0.0.1:95", audiovisual=True,
                              allow_cloud_audio_diagnostics=True)
            project_check.assert_called_once_with(workspace, require_audio=True)
            evaluation = json.loads(
                (workspace / "native-evaluation.json").read_text(encoding="utf-8"))
            self.assertTrue(evaluation["native_saved_project_verified"])
            self.assertEqual(evaluation["decoded_audio_errors"], 1)
            self.assertFalse(evaluation["reviewed_pair_audible_audio_acceptable"])
            self.assertEqual(
                [item["decoded_audio_rejection"]
                 for item in evaluation["decoded_real_exports"]
                 if "decoded_audio_rejection" in item],
                ["audio_missing_or_decode_or_sync_failed"])
            self.assertFalse(evaluation["artistic_quality_approved"])

    def test_unknown_remote_model_is_refused_before_writing_files(self):
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Path(scratch) / "not-created"
            with self.assertRaisesRegex(ValueError, "audited fixed"):
                run_trial(workspace, model_id="untrusted/paid-model",
                          xvfb_binary="/usr/bin/Xvfb", display="127.0.0.1:95")
            self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
