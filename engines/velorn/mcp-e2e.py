# SPDX-License-Identifier: GPL-3.0-only
"""Actual SDK client -> stdio launcher -> native editor; no model evaluation."""
import argparse
import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import tempfile
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from proof_contract import assert_editor_catalog


ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


async def exercise(options):
    from studio_next.native_editor_project import capture_render_project
    from studio_next.native_render_evidence import native_render_binding

    from studio_next.native_editor_source_pin import (
        _source_matches_pinned_native_collaboration,
        _source_matches_pinned_native_scene)
    collaboration_source = _source_matches_pinned_native_collaboration(
        options.source)
    scene_source = _source_matches_pinned_native_scene(options.source)
    assert not scene_source or collaboration_source, (
        "Scene source requires the reviewed parent title collaboration revision")
    fixture = Path(tempfile.mkdtemp(prefix="zx7-editor-mcp-"))
    projects, staging, outputs = (fixture / name for name in ("projects", "staging", "outputs"))
    for path in (projects, staging, outputs):
        path.mkdir()
    snapshots = fixture / "saved-render-projects"
    snapshots.mkdir(mode=0o700)
    # Exercise the shipped host profile, including every advertised schema.
    # Actual edits below cover a narrower, explicitly measured workflow.
    tools = json.loads((ROOT / "engines/velorn/editor.example.json").read_text())["allowed_tools"]
    config = fixture / "editor.json"
    config.write_text(json.dumps({"endpoint": "http://127.0.0.1:19790/mcp", "projects_root": str(projects),
        "staging_root": str(staging), "outputs_root": str(outputs), "allowed_tools": tools,
        "allowed_access": ["read", "write"], "verify_native_exports": True}))
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    assert ffmpeg and ffprobe, "Install FFmpeg and FFprobe for independent decoding"
    def run(argv):
        return subprocess.check_output(argv, stderr=subprocess.PIPE, timeout=30)
    run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(staging / "source.mp4")])
    run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=2", str(staging / "tone.wav")])
    args = [str(ROOT / "engines/velorn/mcp.mjs"), "--source", str(options.source), "--config", str(config),
            "--state", str(fixture / "state"), "--python", sys.executable]
    for name in ("xvfb_binary", "xvfb_lib_dir", "display"):
        if getattr(options, name):
            args += ["--" + name.replace("_", "-"), getattr(options, name)]
    for name in ("no_sandbox", "software_gpu"):
        if getattr(options, name):
            args += ["--" + name.replace("_", "-")]
    params = StdioServerParameters(command="node", args=args, cwd=ROOT)

    @asynccontextmanager
    async def connected():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=120) as session:
                await session.initialize()
                yield session

    async def call(session, name, arguments=None):
        result = await session.call_tool(name, arguments or {})
        assert not result.is_error, (name, result)
        texts = [block.text for block in result.content if block.type == "text"]
        assert len(texts) == 1, (name, result)
        data = json.loads(texts[0])
        assert data.get("success") is not False or (arguments or {}).get("previewOnly") is True, (name, data)
        return data

    async def render_and_verify(session, output, save_receipt):
        rendered = await call(session, "export_timeline", {
            "outputPath": str(output), "target": "h264_project", "width": 320,
            "height": 180, "range": "custom", "startSeconds": 0, "endSeconds": 2,
            "fps": 24, "includeAudio": True, "previewOnly": False})
        save = save_receipt["result"]["project"]
        binding = native_render_binding(str(output), rendered)
        captured = capture_render_project(
            projects, snapshots, rendered, binding, (save["path"], save["modified"]))
        deadline = time.monotonic() + 90
        while True:
            logs = (fixture / "state").glob("session-*/velorn/export-worker.log")
            if any("[ExportWorker] Export complete" in line and
                   json.dumps(str(output)) in line
                   for log in logs for line in log.read_text().splitlines()):
                break
            assert time.monotonic() < deadline, "Native export worker did not finish this export"
            await asyncio.sleep(.2)
        inspection = await call(session, "inspect_export_file", {
            "path": str(output), "width": 320, "height": 180, "durationSeconds": 2})
        assert inspection["ready"], inspection
        assert (await session.call_tool("zx7_observe_verified_export_frame", {
            "path": str(output), "at_seconds": 0.5})).is_error
        proof = await call(session, "zx7_verify_native_export", {
            "path": str(output),
            "expected": {"width": 320, "height": 180,
                         "duration_seconds": 2, "require_audio": True}})
        assert proof["physical_export_verified"] and not proof["artistic_quality_approved"], proof
        assert proof["native_export_sha256"] == digest(output), proof
        assert proof["observation"]["audio_present"] is True
        assert proof["observation"]["full_picture_and_sound_decoder_completed"] is True
        profile = json.loads(run([ffprobe, "-v", "error", "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate,channels,sample_rate",
            "-of", "json", str(output)]))["streams"]
        video, = (stream for stream in profile if stream["codec_type"] == "video")
        audio, = (stream for stream in profile if stream["codec_type"] == "audio")
        assert (video["width"], video["height"], video["r_frame_rate"], video["codec_name"]) == (
            320, 180, "24/1", "h264"), video
        return rendered["timeline"]["id"], proof["native_export_sha256"], (video, audio), captured

    async def observe_samples(session, output, export_sha):
        # Real independent samples give sparse visual temporal evidence.
        times = [0.25, 1.25]
        sampled = await session.call_tool("zx7_observe_verified_export_samples", {
            "path": str(output), "at_seconds": times})
        assert not sampled.is_error and len(sampled.content) == 3, sampled
        receipt = json.loads(sampled.content[0].text)
        assert receipt["kind"] == "verified_native_editor_selected_frames"
        assert receipt["export_sha256"] == export_sha
        assert receipt["continuous_motion_or_audio_proven"] is False
        assert [item["sampled_video_seconds_requested"] for item in receipt["samples"]] == times
        hashes = []
        for block, evidence in zip(sampled.content[1:], receipt["samples"], strict=True):
            assert block.type == "image" and block.mime_type == "image/png"
            png = base64.b64decode(block.data, validate=True)
            assert png.startswith(bytes.fromhex("89504e470d0a1a0a"))
            hashes.append(hashlib.sha256(png).hexdigest())
            assert hashes[-1] == evidence["png_sha256"]
        return hashes

    async def observe_audio_envelope(session, output, export_sha):
        overview = await call(session, "zx7_observe_verified_export_audio_timeline", {
            "path": str(output), "start_seconds": 0, "duration_seconds": 2,
            "bins": 8})
        assert overview["kind"] == "verified_native_editor_audio_temporal_envelope"
        assert overview["export_sha256"] == export_sha
        assert (overview["requested_start_seconds"], overview["requested_duration_seconds"]) == (0, 2)
        assert len(overview["intervals"]) == 8
        assert overview["observed_pcm_samples"] >= 15840
        assert all((entry["rms_dbfs"] is not None and entry["rms_dbfs"] > -55)
                   for entry in overview["intervals"])
        assert not overview["human_or_artistic_quality_approved"]
        return overview

    async def wait(session, predicate, seconds=20, *, read_observations=None):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            state = await call(session, "get_project")
            if read_observations is not None:
                # Actual native reads only. No model/synthetic state, no
                # project name/path/media contents in diagnostic output.
                read_observations.append({
                    "at_monotonic": time.monotonic(),
                    "has_project": (
                        isinstance(state.get("mcp"), dict) and
                        state["mcp"].get("hasProject") is True),
                    "project_identity_present": isinstance(state.get("project"), dict),
                })
            if predicate(state):
                return state
            await asyncio.sleep(.15)
        raise AssertionError("Native debounced project state did not converge")

    def inject_gui_keyboard(key):
        """Real X11 keyboard event into installed Electron, not an MCP mutation.

        Run only under the isolated Xvfb CI display. No window-guess fallback
        or false success if a visible Velorn editor is not uniquely identified.
        """
        assert options.display and shutil.which("xdotool"), (
            "Physical GUI proof requires isolated Xvfb and xdotool")
        env = {**os.environ, "DISPLAY": options.display}
        windows = subprocess.check_output(
            ["xdotool", "search", "--onlyvisible", "--name", "."],
            env=env, stderr=subprocess.PIPE, timeout=8).decode().split()
        matches = []
        for window in set(windows):
            name = subprocess.check_output(
                ["xdotool", "getwindowname", window], env=env,
                stderr=subprocess.PIPE, timeout=8).decode().strip()
            if "Velorn" in name:
                matches.append(window)
        assert len(matches) == 1, (
            "Exactly one visible Velorn editor GUI window required", len(matches))
        subprocess.run(["xdotool", "windowfocus", "--sync", matches[0]],
                       env=env, check=True, timeout=8,
                       capture_output=True)
        subprocess.run(["xdotool", "key", "--clearmodifiers", key],
                       env=env, check=True, timeout=8,
                       capture_output=True)

    async with connected() as session:
        discovered = (await session.list_tools()).tools
        from studio_next.body_editor_client import LocalEditorClient
        native = {tool["name"]: tool for tool in LocalEditorClient(
            "http://127.0.0.1:19790/mcp", allowed_tools={}).list_tools()}
        assert_editor_catalog(discovered, tools, native)
        # One genuine pinned-editor catalog audit, not an inference or an
        # execution guarantee. Do not grant absent specialist/cloud tools.
        from studio_next.native_capability_audit import audit_native_coverage
        coverage = audit_native_coverage(list(native.values()), tools)
        assert (coverage["native_advertised"], coverage["host_granted"],
                coverage["host_ungranted"]) == (130, 77, 53), coverage
        assert {"generate_music", "import_stock_media",
                "queue_timeline_generation_batch"}.issubset(
                    coverage["ungranted_native_names"])
        print("ACTUAL_NATIVE_EDITOR_CAPABILITY_COVERAGE " +
              json.dumps(coverage, sort_keys=True))
        # The universal host admission gateway must actually work against
        # this installed native Electron editor, not merely a fake tool
        # listing or a separate BODY operation. All operations exposed here
        # are from the ORIGINAL host grants, not model-generated permissions.
        from studio_next.capability_gateway import (
            CapabilityExecutionError, CapabilityGateway)
        from studio_next.capability_mcp_session import CapabilityGatewayMcpSession
        from studio_next.capability_session_budget import CapabilitySessionBudget
        host_budget = CapabilitySessionBudget(max_calls=2, max_writes=0)
        host_gateway = CapabilityGateway(
            {"editor": (session, tools)}, session_budget=host_budget)
        await host_gateway.refresh()
        host_session = CapabilityGatewayMcpSession(host_gateway, "editor")
        admitted = await host_session.list_tools()
        assert {item.name for item in admitted.tools} == set(tools)
        first_read = await host_session.call_tool("get_project", {})
        assert first_read.is_error is False
        # An authenticated creative Brain cannot make a single native
        # write when the host grants zero write reservations. This must
        # refuse BEFORE the Electron writer is ever dispatched.
        refused = False
        try:
            await host_session.call_tool("create_project", {
                "name": "MUST NOT BE CREATED", "width": 320,
                "height": 180, "fps": 24, "previewOnly": False})
        except CapabilityExecutionError as exc:
            refused = (str(exc) == "host_session_write_budget_exhausted")
        assert refused, "Host failed to refuse a budget-forbidden native write"
        budget_state = host_gateway.host_budget_evidence()
        assert budget_state["reserved_calls"] == 1
        assert budget_state["reserved_writes"] == 0
        trace = host_gateway.evidence()
        assert len(trace) == 1 and trace[0]["operation_id"] == "editor/get_project"
        no_project = await call(session, "get_project")
        assert (not no_project.get("mcp", {}).get("hasProject")
                and no_project.get("project") is None), (
            "Forbidden gateway-native write unexpectedly affected editor state")
        print("ACTUAL_NATIVE_EDITOR_GATEWAY_BUDGET " + json.dumps({
            "pinned_electron_mcp_source": True,
            "complete_host_granted_tool_catalog_exposed": True,
            "actual_read_routed_through_host_gateway": True,
            "native_write_refused_before_dispatch": True,
            "zero_native_write_budget_reservations": True,
            "no_new_native_project_created": True,
            "creative_neural_or_artistic_proof": False,
            "provider_tokens_or_cost_measured": False,
        }, sort_keys=True), flush=True)
        assert (await session.call_tool("queue_prompt_generation_batch", {})).is_error
        assert (await session.call_tool("create_project", {"name": "Bad", "width": "wrong"})).is_error
        # One independently granted gateway now performs the existing real
        # editor create operation. This proves the positive native WRITE path,
        # not merely a denied request or a synthetic test session.
        enabled_budget = CapabilitySessionBudget(max_calls=2, max_writes=1)
        enabled_gateway = CapabilityGateway(
            {"editor": (session, tools)}, session_budget=enabled_budget)
        await enabled_gateway.refresh()
        enabled_session = CapabilityGatewayMcpSession(enabled_gateway, "editor")
        created = await call(enabled_session, "create_project", {
            "name": "MCP native edit", "width": 320,
            "height": 180, "fps": 24, "previewOnly": False})
        enabled_trace = enabled_gateway.evidence()
        assert (len(enabled_trace) == 1 and
                enabled_trace[0]["operation_id"] == "editor/create_project" and
                enabled_trace[0]["state"] == "host_reported_success_unverified")
        assert enabled_gateway.host_budget_evidence()["reserved_writes"] == 1
        # Measure the real gap between an application ACK and independently
        # observable native project state. The existing test uses 20s
        # bounded read-only convergence; one immediate read (as in the real
        # 2B neural trial) is not proof that the project state is current.
        assert created.get("success") is True, "Missing native application-level project ACK"
        ack_at = time.monotonic()
        observed_reads = []
        state = await wait(
            session, lambda state: (state.get("project") or {}).get("name") == "MCP native edit",
            read_observations=observed_reads)
        # A native application ACK alone is not a durable project: the
        # original readback loop above independently confirmed project state.
        assert (state["project"]["name"] == "MCP native edit" and
                state.get("mcp", {}).get("hasProject") is True)
        print("ACTUAL_NATIVE_EDITOR_GATEWAY_WRITE " + json.dumps({
            "native_project_created_through_shared_gateway": True,
            "one_host_admitted_native_write": True,
            "native_application_acknowledged": True,
            "actual_project_readback_converged": True,
            "no_model_or_artistic_quality_claim": True,
            "native_write_auto_retried": False,
        }, sort_keys=True), flush=True)
        print("ACTUAL_NATIVE_PROJECT_READ_CONVERGENCE " + json.dumps({
            "source": "pinned complete Velorn Electron via real MCP session",
            "application_success_acknowledged": True,
            "reads_until_native_project_visible": len(observed_reads),
            "initial_snapshot_present": observed_reads[0]["project_identity_present"],
            "initial_snapshot_has_project": observed_reads[0]["has_project"],
            "first_read_elapsed_ms": round((observed_reads[0]["at_monotonic"] - ack_at) * 1000, 2),
            "converged_read_elapsed_ms": round((observed_reads[-1]["at_monotonic"] - ack_at) * 1000, 2),
            "read_only_observation": True,
            "automated_project_write_retries": 0,
            "human_or_artistic_quality_approved": False,
        }, sort_keys=True), flush=True)
        project = Path(state["project"]["path"])
        blocked_output = outputs / "no-source.mp4"
        unready = await session.call_tool("export_timeline", {
            "outputPath": str(blocked_output), "target": "h264_project",
            "range": "custom", "startSeconds": 0, "endSeconds": 2,
            "previewOnly": False})
        assert unready.is_error and not blocked_output.exists(), unready
        assert unready.meta["zx7.host/pre-dispatch-rejection"]["code"] == "export_readiness_unconfirmed"
        assert (await session.call_tool("import_asset_from_path", {"path": "/etc/passwd", "previewOnly": False})).is_error
        for name, count in (("source.mp4", 1), ("tone.wav", 2)):
            await call(session, "import_asset_from_path", {"path": str(staging / name), "previewOnly": False})
            await wait(session, lambda state: state.get("assetCount") == count)
        unimported = await session.call_tool("add_assets_to_timeline", {
            "assetNames": ["source.mp4", "not-imported.mp4"], "previewOnly": False})
        assert unimported.is_error, unimported
        assert unimported.meta["zx7.host/pre-dispatch-rejection"]["code"] == "placement_plan_unconfirmed"
        missing = await session.call_tool("add_asset_to_timeline", {
            "assetName": "not-imported.mp4", "previewOnly": False})
        assert missing.is_error, missing
        assert missing.meta["zx7.host/pre-dispatch-rejection"]["code"] == "placement_plan_unconfirmed"
        assert (await call(session, "get_project"))["currentTimeline"]["clipCount"] == 0
        timeline = await call(session, "get_timeline", {"includeClips": False})
        picture_track = next(track["id"] for track in timeline["tracks"] if track["type"] == "video")
        await call(session, "add_assets_to_timeline", {"assetNames": ["source.mp4"],
            "trackStrategy": "singleTrack", "trackId": picture_track, "startSeconds": 0,
            "includeAudio": False, "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 1)
        await call(session, "add_asset_to_timeline", {"assetName": "tone.wav", "startSeconds": 0, "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 2)
        await call(session, "add_track", {"type": "video", "name": "Editable title", "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("trackCount") == 3)
        title = await call(session, "add_text_clip", {"text": "MCP native edit", "startSeconds": 0, "durationSeconds": 2,
                    "style": {"fontSize": 24}, "previewOnly": False})
        title_id = title["result"]["clip"]["id"]
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 3)
        initial_title_keyframes = {"clipId": title_id, "keyframes": [
            {"property": "opacity", "timeSeconds": 0, "value": 20, "easing": "cubicBezier(0.2,0,0.8,1)"},
            {"property": "opacity", "timeSeconds": 1, "value": 100, "easing": "linear"}], "previewOnly": False}
        if scene_source:
            # The source-attested scene writer refuses direct tokenless
            # keyframe writes. Preserve the same original fixture through
            # the trusted host-only CAS route, not a direct-MCP bypass.
            from studio_next.native_editor_identity import (
                pinned_native_editor_identity_policy)
            scene_initial_policy = pinned_native_editor_identity_policy(
                options.source, tools, session)
            assert scene_initial_policy and set(scene_initial_policy["fence"]) == {
                "update_text_clip", "update_shape_clip", "set_clip_keyframes"}
            scene_initial_gateway = CapabilityGateway({"editor": (
                session, tools, {}, None, {}, scene_initial_policy)})
            await scene_initial_gateway.refresh()
            scene_initial_client = CapabilityGatewayMcpSession(
                scene_initial_gateway, "editor")
            await call(scene_initial_client, "set_clip_keyframes",
                       initial_title_keyframes)
            assert scene_initial_gateway.evidence()[-1]["state"] == (
                "host_reported_success_unverified")
        else:
            await call(session, "set_clip_keyframes", initial_title_keyframes)
        saved_first = await call(session, "save_project", {"previewOnly": False})
        native_path = project / "project.comfystudio"
        shutil.copy2(native_path, fixture / "revision-1.comfystudio")
        first_output = outputs / "mcp-export-first.mp4"
        first_timeline, first_sha, first_profile, first_capture = await render_and_verify(
            session, first_output, saved_first)
        first_frames = await observe_samples(session, first_output, first_sha)
        first_audio = await observe_audio_envelope(session, first_output, first_sha)
        if collaboration_source:
            from studio_next.native_editor_identity import (
                pinned_native_editor_identity_policy)
            captured = await call(session, "get_project")
            stale_token = captured.get("zx7NativeRevision")
            assert isinstance(stale_token, str) and len(stale_token) >= 38
            # Real X11 human-style keyboard gesture into the installed GUI,
            # using the editor's own default M hotkey (not an MCP write).
            # Prove the renderer's actual timeline store accepted the key.
            before_gui = await call(session, "get_timeline", {})
            before_gui_ids = {m["id"] for m in before_gui["markers"]}
            initial_count = len(before_gui_ids)
            inject_gui_keyboard("m")
            # get_project deliberately publishes only clip/track counts.
            # Marker state belongs to the full real get_timeline schema.
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                after_gui = await call(session, "get_timeline", {})
                if len(after_gui.get("markers", [])) == initial_count + 1:
                    break
                await asyncio.sleep(.15)
            else:
                raise AssertionError("Electron GUI M hotkey did not create an editable marker")
            new_gui_markers = [m for m in after_gui["markers"]
                               if m["id"] not in before_gui_ids]
            assert len(new_gui_markers) == 1, (
                "GUI keyboard input did not create exactly one source-owned marker")
            gui_marker_id = new_gui_markers[0]["id"]
            # A second independent renderer mutation demonstrates the
            # original human review annotation survives stale AI refusal.
            await call(session, "add_timeline_markers", {
                "markers": [{"timeSeconds": 0.5,
                             "label": "Human review marker"}],
                "previewOnly": False})
            refused = await session.call_tool("update_text_clip", {
                "clipId": title_id, "text": "STALE AI MUST NOT OVERWRITE",
                "previewOnly": False,
                "__zx7ExpectedRevision": stale_token})
            assert refused.is_error, "Native renderer accepted stale source"
            assert len(refused.content) == 1
            assert refused.content[0].text == "ZX7_STALE_NATIVE_REVISION", refused
            await wait(session, lambda state:
                state.get("zx7NativeRevision") != stale_token)
            # The source snapshot publishes at a debounce, so neither a
            # transport ACK nor one immediate timeline read proves the latest
            # marker has appeared. Wait for actual source-owned convergence.
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                unmodified = await call(session, "get_timeline", {"includeClips": True})
                observed_ids = {m["id"] for m in unmodified.get("markers", [])}
                review_seen = any(
                    marker.get("name") == "Human review marker"
                    for marker in unmodified.get("markers", []))
                if gui_marker_id in observed_ids and review_seen:
                    break
                await asyncio.sleep(.15)
            else:
                raise AssertionError(
                    "Real GUI and native review markers failed to converge in source")
            title_after_conflict = next(
                item for item in unmodified["clips"] if item["id"] == title_id)
            assert title_after_conflict["textProperties"]["text"] == "MCP native edit"
            # Interleave a REAL native GUI event precisely after the host
            # finishes all four source observations but before its outbound
            # renderer write. This is the gap #301 cannot protect by itself.
            from studio_next.body_editor_client import host_native_revision_rejection
            baseline_ids = {marker["id"] for marker in unmodified["markers"]}
            class HumanInterruptingNativeSession:
                def __init__(self, remote):
                    self.remote = remote
                    self.intervened = False
                    self.human_marker_id = None

                async def list_tools(self):
                    return await self.remote.list_tools()

                async def call_tool(self, name, inputs):
                    if name == "update_text_clip" and not self.intervened:
                        self.intervened = True
                        inject_gui_keyboard("m")
                        deadline = time.monotonic() + 20
                        while time.monotonic() < deadline:
                            observed = await call(
                                self.remote, "get_timeline", {"includeClips": True})
                            fresh_ids = {m["id"] for m in observed["markers"]}
                            added = fresh_ids - baseline_ids
                            if len(added) == 1:
                                self.human_marker_id = added.pop()
                                break
                            await asyncio.sleep(.15)
                        else:
                            raise AssertionError(
                                "Human GUI intervention never became native-visible")
                    return await self.remote.call_tool(name, inputs)

            interleaved = HumanInterruptingNativeSession(session)
            policy = pinned_native_editor_identity_policy(
                options.source, tools, interleaved)
            assert policy is not None and "fence" in policy
            admitted_gateway = CapabilityGateway({"editor": (
                interleaved, tools, {}, None, {}, policy)})
            await admitted_gateway.refresh()
            admitted_session = CapabilityGatewayMcpSession(
                admitted_gateway, "editor")
            race_inputs = {"clipId": title_id, "text": "STALE AFTER HOST READ",
                           "previewOnly": False}
            raced = await admitted_session.call_tool("update_text_clip", race_inputs)
            assert raced.is_error
            assert host_native_revision_rejection(
                raced, "update_text_clip", race_inputs
            ) == "native_revision_changed_at_commit", raced
            assert interleaved.human_marker_id
            assert admitted_gateway.evidence()[-1]["state"] == (
                "native_conflict_rejected_no_write")
            after_race = await call(session, "get_timeline", {"includeClips": True})
            assert any(m["id"] == interleaved.human_marker_id
                       for m in after_race["markers"])
            assert next(c for c in after_race["clips"] if c["id"] == title_id
                        )["textProperties"]["text"] == "MCP native edit"
            # A new model decision, NOT an automatic replay of the rejected
            # write. Use fresh source reads and the actual live revision.
            await call(admitted_session, "update_text_clip", {
                "clipId": title_id, "text": "MCP revised", "previewOnly": False})
            assert admitted_gateway.evidence()[-1]["state"] == (
                "host_reported_success_unverified")

            async def wait_title(text):
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    state = await call(session, "get_timeline", {"includeClips": True})
                    clip = next(c for c in state["clips"] if c["id"] == title_id)
                    if clip["textProperties"]["text"] == text:
                        return state
                    await asyncio.sleep(.15)
                raise AssertionError("Native editable title did not converge after GUI action")

            await wait_title("MCP revised")
            inject_gui_keyboard("ctrl+z")
            undone = await wait_title("MCP native edit")
            assert all(any(m["id"] == mid for m in undone["markers"])
                       for mid in (gui_marker_id, interleaved.human_marker_id))
            inject_gui_keyboard("ctrl+shift+z")
            redone = await wait_title("MCP revised")
            assert all(any(m["id"] == mid for m in redone["markers"])
                       for mid in (gui_marker_id, interleaved.human_marker_id))
            print("ACTUAL_NATIVE_REVISION_FENCE " + json.dumps({
                "pinned_source": True,
                "stale_writer_rejected_no_native_title_mutation": True,
                "independent_renderer_edit_preserved": True,
                "human_marker_survived_stale_AI_write": True,
                "trusted_host_revision_token_injected": True,
                "gui_interrupted_after_host_read_before_native_commit": True,
                "gui_undo_then_redo_preserved_human_annotations": True,
                "corrected_native_edit_acknowledged_unverified": True,
                "actual_direct_human_mouse_edit_tested": False,
                "real_X11_keyboard_editor_marker_tested": True,
                "real_model_creative_autonomy_tested": False,
            }, sort_keys=True), flush=True)
        else:
            await call(session, "update_text_clip", {
                "clipId": title_id, "text": "MCP revised",
                "previewOnly": False})
        saved_second = await call(session, "save_project", {"previewOnly": False})
        shutil.copy2(native_path, fixture / "revision-2.comfystudio")
        assert digest(fixture / "revision-1.comfystudio") != digest(fixture / "revision-2.comfystudio")
        saved = json.loads(native_path.read_text())
        original = project / saved["assets"][0]["path"]
        original_hash = digest(original)
        assert (await session.call_tool("export_fcpxml", {"outputPath": str(original), "previewOnly": False})).is_error
        assert digest(original) == original_hash
        private_document = fixture / "outside-project.comfystudio"
        shutil.copy2(native_path, private_document)
        linked_project = projects / "linked-document"
        linked_project.mkdir()
        (linked_project / "project.comfystudio").symlink_to(private_document)
        assert (await session.call_tool("open_project", {"projectPath": str(linked_project), "previewOnly": False})).is_error
        output = outputs / "mcp-export.mp4"
        second_timeline, second_sha, second_profile, second_capture = await render_and_verify(
            session, output, saved_second)
        second_frames = await observe_samples(session, output, second_sha)
        second_audio = await observe_audio_envelope(session, output, second_sha)
        assert first_timeline and first_timeline == second_timeline
        assert first_sha != second_sha and digest(first_output) == first_sha
        assert first_profile == second_profile
        assert first_capture[0] == digest(fixture / "revision-1.comfystudio")
        assert second_capture[0] == digest(fixture / "revision-2.comfystudio")
        assert first_capture[1] == second_capture[1]
        assert first_frames != second_frames, "The saved title edit did not change paired decoded frames"
        # Title-only edits must retain this fixture's measured soundtrack.
        assert first_audio["preview_pcm_sha256"] == second_audio["preview_pcm_sha256"]
        print("ACTUAL_NATIVE_PAIRED_AV_REVISION " + json.dumps({
            "native_editable_revision": True,
            "matching_physical_video_and_audio_profiles": True,
            "decoded_frames_changed_at_equal_requested_times": True,
            "decoded_mono_sound_preserved": True,
            "exact_saved_render_snapshots_and_matching_options": True,
            "artistic_quality_approved": False,
            "real_neural_model_inference_attested": False,
        }, sort_keys=True), flush=True)
        observed = await session.call_tool("zx7_observe_verified_export_frame", {
            "path": str(output), "at_seconds": 0.5})
        assert not observed.is_error and len(observed.content) == 2, observed
        assert observed.content[1].type == "image" and observed.content[1].mime_type == "image/png"
        frame = base64.b64decode(observed.content[1].data, validate=True)
        assert frame.startswith(bytes.fromhex("89504e470d0a1a0a"))
        frame_receipt = json.loads(observed.content[0].text)
        assert frame_receipt["export_sha256"] == digest(output)
        assert frame_receipt["png_sha256"] == hashlib.sha256(frame).hexdigest()
        assert frame_receipt["human_or_artistic_quality_approved"] is False
        # Expose an actual short WAV payload for compatible audio-capable brains.
        audio_observed = await session.call_tool("zx7_observe_verified_export_audio", {
            "path": str(output), "start_seconds": 0.25, "duration_seconds": 1.0})
        assert not audio_observed.is_error and len(audio_observed.content) == 2, audio_observed
        audio_receipt = json.loads(audio_observed.content[0].text)
        assert audio_observed.content[1].type == "audio"
        assert audio_observed.content[1].mime_type == "audio/wav"
        wav_bytes = base64.b64decode(audio_observed.content[1].data, validate=True)
        assert wav_bytes.startswith(b"RIFF")
        assert audio_receipt["wav_sha256"] == hashlib.sha256(wav_bytes).hexdigest()
        assert audio_receipt["export_sha256"] == digest(output)
        assert audio_receipt["full_film_listening_or_spatial_mix_verified"] is False
        import io
        import wave
        with wave.open(io.BytesIO(wav_bytes), "rb") as decoded:
            assert (decoded.getnchannels(), decoded.getframerate(), decoded.getsampwidth()) == (1, 16000, 2)
            assert decoded.getnframes() > 8000

        # Real pinned Electron -> independent SHA export verifier -> actual
        # PNG/WAV MCP bytes -> BODY model-interface transport -> journal audit.
        # Deliberately scripted fake model; does NOT validate neural judgment.
        from studio_next.native_creative_control import NativeCreativeControl
        from studio_next.native_creative_audit import audit_native_journal, read_native_journal

        class AVTransportFixtureModel:
            def __init__(self):
                self.stage = 0
                self.actual_frame_hash = None
                self.actual_audio_hash = None

            def decide(self, context):
                self.stage += 1
                if self.stage == 1:
                    return {"action": "invoke", "arguments": {
                        "tool": "zx7_verify_native_export", "inputs": {
                            "path": str(output),
                            "expected": {"width": 320, "height": 180,
                                         "duration_seconds": 2, "require_audio": True}}},
                            "reason": "Independently verify physical export before observation"}
                if self.stage == 2:
                    return {"action": "invoke", "arguments": {
                        "tool": "zx7_observe_verified_export_frame", "inputs": {
                            "path": str(output), "at_seconds": 0.5}},
                            "reason": "Observe actual decoded frame evidence"}
                raise AssertionError("Unexpected scripted test model decision")

            def decide_with_images(self, context, images):
                assert len(images) == 1 and images[0][0] == "image/png"
                self.actual_frame_hash = hashlib.sha256(images[0][1]).hexdigest()
                assert context["observed_picture_sha256"] == [self.actual_frame_hash]
                return {"action": "invoke", "arguments": {
                    "tool": "zx7_observe_verified_export_audio", "inputs": {
                        "path": str(output), "start_seconds": 0.25,
                        "duration_seconds": 1.0}},
                        "reason": "Inspect actual audio source after independently decoded pixels"}

            def decide_with_audio(self, context, audio):
                assert len(audio) == 1 and audio[0][0] == "audio/wav"
                self.actual_audio_hash = hashlib.sha256(audio[0][1]).hexdigest()
                assert audio[0][1].startswith(b"RIFF")
                assert context["audio_evidence"] == {
                    "export_sha256": digest(output), "wav_sha256": self.actual_audio_hash}
                return {"action": "finish", "arguments": {
                    "summary": "Actual A/V transported, no neural creativity asserted"},
                    "reason": "Technical-only real-media transport fixture"}

        fixture_brain = AVTransportFixtureModel()
        verified_trace = fixture / "native-av-model-transport-only.jsonl"
        controlled = await NativeCreativeControl(
            session, fixture_brain, max_turns=4,
            receipt_path=verified_trace).run("Validate physical A/V transport, not artistry")
        grants = {**tools, "zx7_verify_native_export": "read",
                  "zx7_observe_verified_export_frame": "read",
                  "zx7_observe_verified_export_audio": "read"}
        audit = audit_native_journal(read_native_journal(verified_trace),
                                    host_tool_access=grants)
        assert controlled["status"] == "model_finished_unverified"
        assert audit["journal_chain_structurally_valid"]
        assert audit["export_digests_independently_reported_by_native_host"] == [digest(output)]
        assert audit["observed_verified_export_digests"] == [digest(output)]
        assert audit["recorded_native_write_result_count"] == 0
        assert fixture_brain.actual_frame_hash == frame_receipt["png_sha256"]
        assert fixture_brain.actual_audio_hash == audio_receipt["wav_sha256"]
        assert not audit["real_neural_model_weights_or_inference_independently_attested"]
        assert not audit["human_or_artistic_quality_approved"]

    async with connected() as session:
        await call(session, "open_project", {"projectPath": str(project), "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 3 and state.get("assetCount") == 2)
        timeline = await call(session, "get_timeline", {"includeClips": True})
        title = next(clip for clip in timeline["clips"] if clip["id"] == title_id)
        assert title["textProperties"]["text"] == "MCP revised"
        if collaboration_source:
            assert all(any(m.get("id") == marker_id
                           for m in timeline.get("markers", []))
                       for marker_id in (gui_marker_id,
                                         interleaved.human_marker_id)), (
                "Real GUI-entered human markers were not saved/reopened")
        assert title["keyframes"] == next(clip for clip in saved["timelines"][0]["clips"] if clip["id"] == title_id)["keyframes"]
        # The pinned upstream razor drops arbitrary effects/keyframes on its
        # new right-hand clip. Never silently let BODY split an animated title.
        forbidden = await session.call_tool("split_clip", {
            "clipId": title_id, "timeSeconds": 1, "previewOnly": False})
        assert forbidden.is_error and "discard editable clip state" in forbidden.content[0].text, forbidden
        unchanged = await call(session, "get_timeline", {"includeClips": True})
        assert len(unchanged["clips"]) == 3
        preserved = next(clip for clip in unchanged["clips"] if clip["id"] == title_id)
        assert preserved["keyframes"] == title["keyframes"]
        assert digest(native_path) == digest(fixture / "revision-2.comfystudio")
        # A real model selected native *batch* placement after import, then
        # hit a native MCP error. Isolate the actual engine/ABI independent
        # of the model using only IDs read from this reopened real project.
        # This is a technical fixture, NOT a successful neural creative edit.
        live_assets = await call(session, "get_assets", {"limit": 1000})
        assert live_assets.get("count") == 2 and live_assets.get("limitApplied") is False
        rows = live_assets.get("assets")
        assert isinstance(rows, list) and len(rows) == 2
        video_ids = [a["id"] for a in rows
                     if isinstance(a, dict) and a.get("type") == "video"
                     and isinstance(a.get("id"), str) and a["id"]]
        assert len(video_ids) == 1, "Native source inventory has ambiguous video identities"
        batch_args = {"assetIds": video_ids, "trackStrategy": "newTracks",
                      "layout": "stacked", "startSeconds": 0,
                      "includeAudio": False}
        preview = await call(session, "add_assets_to_timeline", {
            **batch_args, "previewOnly": True})
        assert preview.get("previewOnly") is True
        before = await call(session, "get_timeline", {"includeClips": True})
        assert len(before["clips"]) == 3, "Native batch preview changed a real timeline"
        applied = await call(session, "add_assets_to_timeline", {
            **batch_args, "previewOnly": False})
        # Pinned Electron MCP apply response uses success:true and omits
        # previewOnly; independent timeline readback proves actual mutation.
        assert applied.get("success") is True and applied.get("action") == "add_assets_to_timeline"
        await wait(session, lambda state:
            (state.get("currentTimeline") or {}).get("clipCount") == 4)
        after = await call(session, "get_timeline", {"includeClips": True})
        assert len(after["clips"]) == 4
        assert sum(c.get("assetId") == video_ids[0] for c in after["clips"]) == 2
        assert digest(original) == original_hash
        print("ACTUAL_NATIVE_BATCH_PLACEMENT " + json.dumps({
            "scripted_native_control_not_neural": True,
            "host_observed_video_asset": True,
            "preview_non_mutating": True,
            "native_batch_write_acknowledged": True,
            "post_write_native_clips": len(after["clips"]),
            "original_media_sha_unchanged": True,
            "artistic_quality_approved": False,
        }, sort_keys=True), flush=True)

        # The failed Qwen trial observed an imported video but zero timeline
        # picture. A batch control over an already-edited timeline alone
        # would not isolate that machine-state hypothesis. Create an EMPTY
        # new native sequence in this disposable project, let the editor
        # switch to it, and prove that the very first content placement works.
        created_sequence = await call(session, "create_timeline", {
            "name": "Original footage first-placement control",
            "width": 320, "height": 180, "fps": 24,
            "switchToTimeline": True, "previewOnly": False})
        assert created_sequence.get("success") is True
        await wait(session, lambda state:
            (state.get("currentTimeline") or {}).get("name")
            == "Original footage first-placement control")
        empty_sequence = await call(session, "get_timeline", {"includeClips": True})
        assert empty_sequence["clips"] == [], (
            "New timeline has existing picture; first-placement control invalid")
        initial_asset_inventory = await call(session, "get_assets", {"limit": 1000})
        assert initial_asset_inventory.get("count") == 2
        assert initial_asset_inventory.get("limitApplied") is False
        observed_video = [a["id"] for a in initial_asset_inventory["assets"]
                          if isinstance(a, dict) and a.get("type") == "video"
                          and isinstance(a.get("id"), str) and a["id"]]
        assert observed_video == video_ids
        preview_first = await call(session, "add_assets_to_timeline", {
            "assetIds": observed_video, "trackStrategy": "newTracks",
            "layout": "stacked", "includeAudio": False, "startSeconds": 0,
            "previewOnly": True})
        assert preview_first.get("previewOnly") is True
        still_empty = await call(session, "get_timeline", {"includeClips": True})
        assert still_empty["clips"] == [], (
            "Preview unexpectedly altered empty native timeline")
        first_applied = await call(session, "add_assets_to_timeline", {
            "assetIds": observed_video, "trackStrategy": "newTracks",
            "layout": "stacked", "includeAudio": False, "startSeconds": 0,
            "previewOnly": False})
        assert first_applied.get("success") is True
        await wait(session, lambda state:
            (state.get("currentTimeline") or {}).get("clipCount") == 1)
        populated = await call(session, "get_timeline", {"includeClips": True})
        assert len(populated["clips"]) == 1
        assert populated["clips"][0].get("assetId") == observed_video[0]
        assert digest(original) == original_hash
        await call(session, "save_project", {"previewOnly": False})
        assert digest(native_path) != digest(fixture / "revision-2.comfystudio")
        print("ACTUAL_NATIVE_EMPTY_SEQUENCE_BATCH_PLACEMENT " + json.dumps({
            "scripted_control_not_neural": True,
            "source_id_reobserved_after_sequence_switch": True,
            "preexisting_picture_clip_count": 0,
            "first_native_batch_write_acknowledged": True,
            "physical_timeline_clip_count_after_first_placement": 1,
            "original_media_sha_unchanged": True,
            "artistic_quality_approved": False,
        }, sort_keys=True), flush=True)

    # The live clip count is insufficient: prove that the newly created
    # sequence, its first native batch placement and exact original asset ID
    # survive a fresh independent editor process before accepting this
    # technical control as durable. Original source content must be untouched.
    async with connected() as session:
        await call(session, "open_project", {
            "projectPath": str(project), "previewOnly": False})
        await wait(session, lambda state:
            (state.get("currentTimeline") or {}).get("name")
            == "Original footage first-placement control"
            and (state.get("currentTimeline") or {}).get("clipCount") == 1)
        persisted = await call(session, "get_timeline", {"includeClips": True})
        assert len(persisted["clips"]) == 1
        assert persisted["clips"][0].get("assetId") == video_ids[0]
        assert digest(original) == original_hash
        print("ACTUAL_NATIVE_BATCH_REOPEN_PERSISTENCE " + json.dumps({
            "new_process_reopened_saved_native_project": True,
            "first_source_linked_video_clip_persisted": True,
            "source_video_id_matches_prior_live_inventory": True,
            "source_media_sha_unchanged": True,
            "neural_artistic_success_asserted": False,
        }, sort_keys=True), flush=True)

        # Distinguish an inherent batch-tool failure from one bad model-
        # selected source selector: the original failed neural call did not
        # retain its arguments. Exercise the native, *implicit* source
        # selection path separately, on another truly empty sequence.
        sequence = await call(session, "create_timeline", {
            "name": "Native implicit video selection control",
            "width": 320, "height": 180, "fps": 24,
            "switchToTimeline": True, "previewOnly": False})
        assert sequence.get("success") is True
        await wait(session, lambda state:
            (state.get("currentTimeline") or {}).get("name")
            == "Native implicit video selection control")
        before_implicit = await call(session, "get_timeline", {"includeClips": True})
        assert before_implicit["clips"] == []
        implicit_inputs = {
            "type": "video", "count": 1, "trackStrategy": "newTracks",
            "includeAudio": False, "startSeconds": 0,
        }
        implicit_preview = await call(session, "add_assets_to_timeline", {
            **implicit_inputs, "previewOnly": True})
        assert implicit_preview.get("previewOnly") is True
        planned = implicit_preview.get("plan", {}).get("placements", [])
        assert len(planned) == 1 and planned[0]["asset"]["id"] == video_ids[0]
        assert (await call(session, "get_timeline", {
            "includeClips": True}))["clips"] == []
        implicit_apply = await call(session, "add_assets_to_timeline", {
            **implicit_inputs, "previewOnly": False})
        assert implicit_apply.get("success") is True
        await wait(session, lambda state:
            (state.get("currentTimeline") or {}).get("clipCount") == 1)
        after_implicit = await call(session, "get_timeline", {
            "includeClips": True})
        assert len(after_implicit["clips"]) == 1
        assert after_implicit["clips"][0]["assetId"] == video_ids[0]
        # A wrong explicit selector must be rejected by native Velorn, and
        # must not alter even this disposable working sequence. Do not expose
        # the source path or native error text in logs.
        bad_preview = await session.call_tool("add_assets_to_timeline", {
            "assetIds": ["zx7-nonexistent-asset-reference"],
            "trackStrategy": "newTracks",
            "previewOnly": True})
        assert bad_preview.is_error
        unchanged = await call(session, "get_timeline", {
            "includeClips": True})
        assert [clip["id"] for clip in unchanged["clips"]] == [
            clip["id"] for clip in after_implicit["clips"]]
        assert digest(original) == original_hash
        await call(session, "save_project", {"previewOnly": False})
        print("ACTUAL_NATIVE_BATCH_SELECTOR_DISCRIMINATION " + json.dumps({
            "technical_fixture_not_neural": True,
            "implicit_editor_source_selection_preview_nonmutating": True,
            "implicit_native_source_id_matched_read_inventory": True,
            "implicit_batch_apply_created_exactly_one_real_clip": True,
            "invalid_explicit_id_preview_rejected_without_edit": True,
            "original_media_sha_unchanged": True,
            "artistic_quality_approved": False,
        }, sort_keys=True), flush=True)

        # An actual Qwen4B camera trial (#42327595943) applied a source-
        # linked single-clip write, saved that source, but its subsequent
        # get_timeline snapshot still reported no picture. Isolate whether
        # the native single-clip tool and snapshot converge without a
        # model. No scripted creative success is inferred from this test.
        single_created = await call(session, "create_timeline", {
            "name": "Independent single-clip readback control",
            "width": 320, "height": 180, "fps": 24,
            "switchToTimeline": True, "previewOnly": False})
        assert single_created.get("success") is True
        await wait(session, lambda state:
            (state.get("currentTimeline") or {}).get("name")
            == "Independent single-clip readback control"
            and (state.get("currentTimeline") or {}).get("clipCount") == 0)
        assert (await call(session, "get_timeline", {
            "includeClips": True}))["clips"] == []
        single_ack = await call(session, "add_asset_to_timeline", {
            "assetId": video_ids[0], "startSeconds": 0,
            "includeAudio": False, "previewOnly": False})
        assert single_ack.get("success") is True
        immediately = await call(session, "get_timeline", {
            "includeClips": True, "limit": 1000})
        immediate_project = await call(session, "get_project")
        # Inspect the two live observations without private media contents.
        # A delayed snapshot must not be called 'no clip' authoritatively.
        immediate_source_clips = sum(
            isinstance(clip, dict) and clip.get("assetId") == video_ids[0]
            for clip in immediately.get("clips", []))
        immediate_project_count = (
            (immediate_project.get("currentTimeline") or {}).get("clipCount"))
        await wait(session, lambda state:
            (state.get("currentTimeline") or {}).get("name")
            == "Independent single-clip readback control"
            and (state.get("currentTimeline") or {}).get("clipCount") == 1)
        converged = await call(session, "get_timeline", {
            "includeClips": True, "limit": 1000})
        assert len(converged["clips"]) == 1
        assert converged["clips"][0].get("assetId") == video_ids[0]
        assert digest(original) == original_hash
        await call(session, "save_project", {"previewOnly": False})
        print("ACTUAL_NATIVE_SINGLE_CLIP_READ_CONVERGENCE " + json.dumps({
            "technical_native_fixture_not_neural": True,
            "model_camera_original_error_was_not_assumed": True,
            "immediate_get_timeline_original_clip_count": immediate_source_clips,
            "immediate_get_project_clip_count": immediate_project_count,
            "after_independent_read_convergence_source_clip_count":
                len(converged["clips"]),
            "original_media_sha_unchanged": True,
            "native_saved_after_single_source_placement": True,
            "artistic_quality_approved": False,
        }, sort_keys=True), flush=True)
        # Distinguish the real 4B trial's export failure from model arguments:
        # exercise the pinned native read/preflight/preview/apply ABI with only
        # ONE real source-linked video clip on the active native timeline.
        # The source/video parameters below are technical test fixtures,
        # never a creative plan given to the model.
        single_output = outputs / "mcp-single-clip-export.mp4"
        single_export = {
            "outputPath": str(single_output), "target": "h264_project",
            "resolution": "custom", "width": 320, "height": 180, "fps": 24,
            "range": "custom", "startSeconds": 0, "endSeconds": 2,
            "includeAudio": False,
        }
        # Read-only readiness has no outputPath in its pinned native schema.
        # Keep destination selection exclusively in preview/apply export calls;
        # the strict host bridge must reject undeclared parameters.
        readiness_args = {key: value for key, value in single_export.items()
                          if key != "outputPath"}
        readiness = await call(session, "check_export_readiness", readiness_args)
        assert readiness["ready"] is True and readiness["blockers"] == [], readiness
        assert readiness["counts"]["exportableVisualClipCount"] == 1, readiness
        preview = await call(session, "export_timeline", {
            **single_export, "previewOnly": True})
        assert preview.get("previewOnly") is True, preview
        assert preview.get("readiness", {}).get("ready") is True, preview
        assert not single_output.exists(), "Native preview unexpectedly exported a file"
        applied = await call(session, "export_timeline", {
            **single_export, "previewOnly": False})
        assert applied.get("success") is True, "Native export worker did not acknowledge start"
        # A worker ACK is not a delivery. Wait for complete independent
        # decode of the NEW output, not an old successful worker log.
        single_deadline = time.monotonic() + 90
        single_probe = None
        while time.monotonic() < single_deadline:
            if single_output.is_file() and single_output.stat().st_size > 0:
                try:
                    candidate = json.loads(run([ffprobe, "-v", "error",
                        "-count_frames", "-show_streams", "-of", "json",
                        str(single_output)]))
                    picture = next(stream for stream in candidate["streams"]
                        if stream["codec_type"] == "video")
                    if (picture["codec_name"] == "h264"
                            and picture["width"] == 320
                            and picture["height"] == 180
                            and picture["r_frame_rate"] == "24/1"
                            and int(picture["nb_read_frames"]) == 48):
                        run([ffmpeg, "-v", "error", "-xerror", "-i",
                             str(single_output), "-f", "null", "-"])
                        single_probe = candidate
                        break
                except (subprocess.CalledProcessError, ValueError, KeyError,
                        StopIteration):
                    # Partial in-flight output is not accepted as a result.
                    pass
            await asyncio.sleep(.25)
        assert single_probe is not None, (
            "Independent single-clip native export did not decode and converge")
        assert digest(original) == original_hash, "Native export modified source"
        print("ACTUAL_NATIVE_SINGLE_CLIP_EXPORT_CONTRACT " + json.dumps({
            "technical_native_fixture_not_neural": True,
            "single_source_linked_video_clip": True,
            "readiness_checked_and_unblocked": True,
            "preview_nonmutating": True,
            "native_worker_start_acknowledged": True,
            "export_mp4_independently_decoded": True,
            "decoded_video_frames": 48,
            "original_source_sha_unchanged": True,
            "prior_qwen_failure_cause_proven": False,
            "neural_or_artistic_completion_proven": False,
        }, sort_keys=True), flush=True)
        # The successful one-clip proof above uses a technical synthetic
        # source. The previous genuine Qwen4B camera failed during export.
        # Independently discriminate the original camera's actual VP9/WebM
        # decoder + pinned editor export without paying for another model turn.
        # This is NOT an artist-selected edit or a neural acceptance test.
        if options.camera_video is not None:
            import re
            if (not options.camera_video.is_file() or
                    not isinstance(options.camera_sha256, str) or
                    re.fullmatch(r"[0-9a-f]{64}", options.camera_sha256) is None):
                raise ValueError("Independent camera bytes and pinned SHA are required")
            if digest(options.camera_video) != options.camera_sha256:
                raise AssertionError("Source camera SHA mismatch before native import")
            camera_staged = staging / "original-camera.webm"
            assert not camera_staged.exists()
            shutil.copyfile(options.camera_video, camera_staged)
            assert digest(camera_staged) == options.camera_sha256
            before_camera = await call(session, "get_assets", {"limit": 1000})
            before_camera_ids = {asset.get("id") for asset in before_camera["assets"]
                                 if isinstance(asset, dict)}
            camera_created = await call(session, "create_timeline", {
                "name": "Independent real camera export control",
                "width": 320, "height": 180, "fps": 24,
                "switchToTimeline": True, "previewOnly": False})
            assert camera_created.get("success") is True
            await wait(session, lambda state:
                (state.get("currentTimeline") or {}).get("name")
                == "Independent real camera export control"
                and (state.get("currentTimeline") or {}).get("clipCount") == 0)
            assert (await call(session, "get_timeline", {
                "includeClips": True}))["clips"] == []
            await call(session, "import_asset_from_path", {
                "path": str(camera_staged), "previewOnly": False})
            await wait(session, lambda state:
                state.get("assetCount") == len(before_camera_ids) + 1)
            inventory = await call(session, "get_assets", {"limit": 1000})
            added = [asset for asset in inventory["assets"]
                     if isinstance(asset, dict)
                     and asset.get("id") not in before_camera_ids]
            assert (len(added) == 1 and added[0].get("type") == "video"
                    and isinstance(added[0].get("id"), str)), (
                "Original camera import did not create exactly one native video ID")
            native_camera_id = added[0]["id"]
            native_place = await call(session, "add_asset_to_timeline", {
                "assetId": native_camera_id, "startSeconds": 0,
                "includeAudio": False, "previewOnly": False})
            assert native_place.get("success") is True
            await wait(session, lambda state:
                (state.get("currentTimeline") or {}).get("clipCount") == 1)
            clip_state = await call(session, "get_timeline", {"includeClips": True})
            assert len(clip_state["clips"]) == 1
            assert clip_state["clips"][0].get("assetId") == native_camera_id
            await call(session, "save_project", {"previewOnly": False})
            stored_camera = json.loads(native_path.read_text())
            stored_assets = [asset for asset in stored_camera["assets"]
                             if asset.get("id") == native_camera_id]
            assert len(stored_assets) == 1
            source_inside_project = project / stored_assets[0]["path"]
            assert digest(source_inside_project) == options.camera_sha256
            camera_export = outputs / "original-camera-native-export.mp4"
            camera_settings = {
                "target": "h264_project", "resolution": "custom",
                "width": 320, "height": 180, "fps": 24,
                "range": "custom", "startSeconds": 0, "endSeconds": 2,
                "includeAudio": False,
            }
            ready = await call(session, "check_export_readiness", camera_settings)
            assert ready["ready"] is True and ready["blockers"] == [], ready
            assert ready["counts"]["exportableVisualClipCount"] == 1, ready
            preview = await call(session, "export_timeline", {
                **camera_settings, "outputPath": str(camera_export),
                "previewOnly": True})
            assert preview.get("previewOnly") is True
            assert not camera_export.exists()
            accepted = await call(session, "export_timeline", {
                **camera_settings, "outputPath": str(camera_export),
                "previewOnly": False})
            assert accepted.get("success") is True
            # Do not mistake asynchronous worker ACK for an accepted film.
            camera_deadline = time.monotonic() + 120
            decoded_camera_frames = None
            while time.monotonic() < camera_deadline:
                if camera_export.is_file() and camera_export.stat().st_size > 0:
                    try:
                        record = json.loads(run([ffprobe, "-v", "error",
                            "-count_frames", "-show_streams", "-of", "json",
                            str(camera_export)]))
                        picture = next(item for item in record["streams"]
                                       if item.get("codec_type") == "video")
                        if (picture.get("codec_name") == "h264"
                                and picture.get("width") == 320
                                and picture.get("height") == 180
                                and picture.get("r_frame_rate") == "24/1"
                                and int(picture.get("nb_read_frames", 0)) == 48):
                            run([ffmpeg, "-v", "error", "-xerror", "-i",
                                 str(camera_export), "-map", "0:v:0",
                                 "-f", "null", "-"])
                            decoded_camera_frames = 48
                            break
                    except (subprocess.CalledProcessError, ValueError,
                            KeyError, StopIteration, TypeError):
                        # A partially encoded file cannot satisfy the gate.
                        pass
                await asyncio.sleep(.25)
            assert decoded_camera_frames == 48, (
                "Original camera native export did not fully decode")
            assert digest(options.camera_video) == options.camera_sha256
            assert digest(camera_staged) == options.camera_sha256
            assert digest(source_inside_project) == options.camera_sha256
            print("ACTUAL_ORIGINAL_CAMERA_NATIVE_EXPORT " + json.dumps({
                "source": "independently_sha_attested_original_camera_webm",
                "camera_sha256": options.camera_sha256,
                "native_project_placed_exactly_one_camera_clip": True,
                "readiness_unblocked": True,
                "preview_nonmutating": True,
                "native_worker_start_acknowledged": True,
                "independently_decoded_h264_frame_count": decoded_camera_frames,
                "full_original_source_unchanged": True,
                "model_inference_or_artist_quality_demonstrated": False,
                "previous_model_export_error_attributed": False,
            }, sort_keys=True), flush=True)
        if scene_source:
            # G1 native scene: preserve original picture/sound and operate
            # on an editable shape. The real GUI keyboard marker changes the
            # timeline during native shape/keyframe CAS, but this does NOT
            # exercise human pointer dragging the shape or changing its curve.
            # Scripted physical-editor proof, NOT creative AI inference.
            from studio_next.native_editor_identity import (
                pinned_native_editor_identity_policy)
            from studio_next.body_editor_client import (
                host_native_revision_rejection)
            sequence = await call(session, "create_timeline", {
                "name": "G1 scene revision source proof",
                "width": 320, "height": 180, "fps": 24,
                "switchToTimeline": True, "previewOnly": False})
            assert sequence.get("success") is True
            await wait(session, lambda s:
                (s.get("currentTimeline") or {}).get("name")
                == "G1 scene revision source proof"
                and (s.get("currentTimeline") or {}).get("clipCount") == 0)
            await call(session, "add_asset_to_timeline", {
                "assetId": video_ids[0], "startSeconds": 0,
                "includeAudio": False, "previewOnly": False})
            await wait(session, lambda s:
                (s.get("currentTimeline") or {}).get("clipCount") == 1)
            await call(session, "add_asset_to_timeline", {
                "assetName": "tone.wav", "startSeconds": 0,
                "previewOnly": False})
            await wait(session, lambda s:
                (s.get("currentTimeline") or {}).get("clipCount") == 2)
            await call(session, "add_track", {
                "type": "video", "name": "Scene shape overlay",
                "previewOnly": False})
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                tracks = (await call(session, "get_timeline", {}))["tracks"]
                layers = [t for t in tracks
                          if t["name"] == "Scene shape overlay"]
                if len(layers) == 1:
                    break
                await asyncio.sleep(.15)
            else:
                raise AssertionError("Editable motion overlay track not observed")
            overlay_track = layers[0]["id"]
            created_shape = await call(session, "add_shape_clip", {
                "shapeType": "rectangle", "name": "G1 scene editable rectangle",
                "fillColor": "#03c471", "width": 140, "height": 100,
                "trackId": overlay_track, "startSeconds": 0,
                "durationSeconds": 2, "previewOnly": False})
            shape_id = created_shape["result"]["clip"]["id"]
            await wait(session, lambda s:
                (s.get("currentTimeline") or {}).get("clipCount") == 3)
            async def live_shape():
                state = await call(session, "get_timeline", {
                    "includeClips": True})
                shape = next(c for c in state["clips"]
                             if c["id"] == shape_id)
                return state, shape
            before_timeline, before_shape = await live_shape()
            assert before_shape.get("type") == "shape"
            assert before_shape["shapeProperties"]["fillColor"].lower() == "#03c471"
            assert before_shape.get("keyframes") in ([], None)
            # A native default preview must never apply or consume the
            # model's write budget merely because the action is exposed.
            planned_keyframes = [
                {"property": "opacity", "timeSeconds": 0,
                 "value": 20, "easing": "linear"},
                {"property": "opacity", "timeSeconds": 1,
                 "value": 100, "easing": "linear"}]
            keyframe_preview = await call(session, "set_clip_keyframes", {
                "clipId": shape_id, "keyframes": planned_keyframes})
            assert keyframe_preview.get("previewOnly") is True
            _, after_preview = await live_shape()
            assert after_preview.get("keyframes") in ([], None), (
                "Source keyframe default preview unexpectedly applied")
            baseline_save = await call(
                session, "save_project", {"previewOnly": False})
            baseline_export = outputs / "scene-before-shape-revision.mp4"
            baseline_id, baseline_sha, baseline_profile, baseline_capture = (
                await render_and_verify(session, baseline_export, baseline_save))
            baseline_frames = await observe_samples(
                session, baseline_export, baseline_sha)
            baseline_audio = await observe_audio_envelope(
                session, baseline_export, baseline_sha)
            # Capture a source revision, then intervene through real GUI.
            # A stale *direct* native shape write must not overwrite its
            # pre-observed human timeline context or modify shape color.
            baseline_revision = (
                await call(session, "get_project"))["zx7NativeRevision"]
            previous_ids = {m["id"] for m in before_timeline["markers"]}
            inject_gui_keyboard("m")
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                current_timeline, current_shape = await live_shape()
                new_ids = ({m["id"] for m in current_timeline["markers"]}
                           - previous_ids)
                if len(new_ids) == 1:
                    first_gui_marker = next(iter(new_ids))
                    break
                await asyncio.sleep(.15)
            else:
                raise AssertionError("Real GUI marker did not enter shape timeline")
            stale_shape = await session.call_tool("update_shape_clip", {
                "clipId": shape_id, "fillColor": "#e83b61",
                "previewOnly": False,
                "__zx7ExpectedRevision": baseline_revision})
            assert (stale_shape.is_error
                    and len(stale_shape.content) == 1
                    and stale_shape.content[0].text ==
                    "ZX7_STALE_NATIVE_REVISION"), stale_shape
            _, after_stale_shape = await live_shape()
            assert after_stale_shape["shapeProperties"]["fillColor"].lower() == (
                "#03c471")
            # Trusted host obtains a fresh source-checked clip inventory
            # and alone supplies the commit revision to the native writer.
            scene_policy = pinned_native_editor_identity_policy(
                options.source, tools, session)
            assert scene_policy and set(scene_policy["fence"]) == {
                "update_text_clip", "update_shape_clip", "set_clip_keyframes"}
            native_gateway = CapabilityGateway({"editor": (
                session, tools, {}, None, {}, scene_policy)})
            await native_gateway.refresh()
            scene_host = CapabilityGatewayMcpSession(native_gateway, "editor")
            changed = await call(scene_host, "update_shape_clip", {
                "clipId": shape_id, "fillColor": "#e83b61",
                "previewOnly": False})
            assert changed.get("success") is True
            assert native_gateway.evidence()[-1]["state"] == (
                "host_reported_success_unverified")
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                current_timeline, changed_shape = await live_shape()
                if changed_shape["shapeProperties"]["fillColor"].lower() == (
                    "#e83b61"):
                    break
                await asyncio.sleep(.15)
            else:
                raise AssertionError("Source-owned shape color never changed")
            assert any(m["id"] == first_gui_marker
                       for m in current_timeline["markers"])

            # Human GUI event strictly between host's source transaction
            # and the keyframe writer entry. This is distinct from merely
            # passing an old token to a fake function in a unit test.
            marker_baseline = {
                m["id"] for m in current_timeline["markers"]}
            class InterveningSceneSession:
                def __init__(self, original):
                    self.original = original
                    self.interrupted = False
                    self.manual_marker = None
                async def list_tools(self):
                    return await self.original.list_tools()
                async def call_tool(self, name, inputs):
                    if (name == "set_clip_keyframes" and
                            not self.interrupted):
                        self.interrupted = True
                        inject_gui_keyboard("m")
                        deadline = time.monotonic() + 20
                        while time.monotonic() < deadline:
                            state = await call(self.original, "get_timeline", {
                                "includeClips": True})
                            added = ({m["id"] for m in state["markers"]}
                                     - marker_baseline)
                            if len(added) == 1:
                                self.manual_marker = next(iter(added))
                                break
                            await asyncio.sleep(.15)
                        else:
                            raise AssertionError(
                                "Keyboard GUI intervention was never observed")
                    return await self.original.call_tool(name, inputs)
            interrupted = InterveningSceneSession(session)
            interleaved_policy = pinned_native_editor_identity_policy(
                options.source, tools, interrupted)
            key_gateway = CapabilityGateway({"editor": (
                interrupted, tools, {}, None, {}, interleaved_policy)})
            await key_gateway.refresh()
            key_host = CapabilityGatewayMcpSession(key_gateway, "editor")
            key_args = {"clipId": shape_id,
                        "keyframes": planned_keyframes,
                        "previewOnly": False}
            stale_keyframe = await key_host.call_tool(
                "set_clip_keyframes", key_args)
            assert stale_keyframe.is_error
            assert host_native_revision_rejection(
                stale_keyframe, "set_clip_keyframes", key_args
            ) == "native_revision_changed_at_commit"
            assert key_gateway.evidence()[-1]["state"] == (
                "native_conflict_rejected_no_write")
            assert interrupted.manual_marker
            _, unchanged_keyframes = await live_shape()
            assert unchanged_keyframes.get("keyframes") in ([], None)
            def shape_opacity_curve(shape_clip):
                curves = shape_clip.get("keyframes")
                if not isinstance(curves, dict):
                    return []
                keys = curves.get("opacity")
                return keys if isinstance(keys, list) else []

            # Fresh explicit model-side decision after observing changed
            # source; never replay an uncertain edit or reuse request ID.
            accepted_keyframes = await call(key_host, "set_clip_keyframes",
                                            key_args)
            assert accepted_keyframes.get("success") is True
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                timeline, shape_now = await live_shape()
                if len(shape_opacity_curve(shape_now)) >= 2:
                    break
                await asyncio.sleep(.15)
            else:
                raise AssertionError("Source keyframes never appeared")
            # Source GUI Undo/Redo must preserve both manual annotations.
            inject_gui_keyboard("ctrl+z")
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                timeline, undone_shape = await live_shape()
                if not shape_opacity_curve(undone_shape):
                    break
                await asyncio.sleep(.15)
            else:
                raise AssertionError("GUI Undo did not restore original shape curves")
            inject_gui_keyboard("ctrl+shift+z")
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                timeline, redone_shape = await live_shape()
                if len(shape_opacity_curve(redone_shape)) >= 2:
                    break
                await asyncio.sleep(.15)
            else:
                raise AssertionError("GUI Redo did not restore editable shape curves")
            assert all(any(m["id"] == marker for m in timeline["markers"])
                       for marker in (
                           first_gui_marker, interrupted.manual_marker))
            scene_save = await call(session, "save_project", {
                "previewOnly": False})
            scene_save_sha = digest(native_path)
            scene_output = outputs / "scene-after-shape-keyframe-revision.mp4"
            final_id, final_sha, final_profile, final_capture = (
                await render_and_verify(session, scene_output, scene_save))
            final_frames = await observe_samples(session, scene_output, final_sha)
            final_audio = await observe_audio_envelope(
                session, scene_output, final_sha)
            assert baseline_id == final_id
            assert baseline_sha != final_sha
            assert baseline_profile == final_profile
            assert baseline_frames != final_frames, (
                "Shape/color/curve did not change independently decoded frames")
            assert (baseline_audio["preview_pcm_sha256"] ==
                    final_audio["preview_pcm_sha256"]), (
                "The scene revision unexpectedly changed the owner audio")
            assert baseline_capture[1] == final_capture[1], (
                "Native scene render changed original media custody")
            assert digest(original) == original_hash
            print("ACTUAL_NATIVE_SCENE_CAS " + json.dumps({
                "source_pinned_scene_variant": True,
                "real_GUI_marker_intervention_during_shape_and_keyframe_edit": True,
                "direct_human_shape_drag_or_keyframe_manipulation_tested": False,
                "stale_shape_and_keyframe_mutations_refused": True,
                "host_reobserved_and_applied_distinct_scene_edits": True,
                "GUI_undo_redo_preserved_two_manual_markers": True,
                "native_editable_shape_keyframes_saved": True,
                "paired_decoded_frames_changed": True,
                "paired_decoded_audio_preserved": True,
                "original_source_sha_unchanged": True,
                "genuine_model_authored_scene": False,
                "professional_art_quality_approved": False,
            }, sort_keys=True), flush=True)
    probe = json.loads(run([ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(output)]))
    video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
    audio = next(stream for stream in probe["streams"] if stream["codec_type"] == "audio")
    assert (video["width"], video["height"], video["r_frame_rate"], int(video["nb_read_frames"])) == (320, 180, "24/1", 48)
    assert video["codec_name"] == "h264"
    assert audio["codec_name"] == "aac"
    assert abs(float(probe["format"]["duration"]) - 2) < .05
    run([ffmpeg, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"])
    pcm = run([ffmpeg, "-v", "error", "-i", str(output), "-map", "0:a:0", "-ac", "1", "-f", "f32le", "pipe:1"])
    samples = struct.unpack("<" + "f" * (len(pcm) // 4), pcm)
    audio_rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    assert .03 < audio_rms < .2
    receipt = {"success": True, "kind": "scripted official SDK client; no autonomous model evaluation",
        "transport": "standard MCP stdio; Python SDK 2.3.0", "nativeSchemaContractVerified": True,
        "discoveredGrantedTools": len(tools), "additionalVerifiedBodyTools": len(discovered) - len(tools), "physicalVisualFrameObserved": True,
        "physicalBoundedSourceAudioObserved": True,
        "physicalTemporalAudioEnvelopeObserved": True,
        "physicalSparseTemporalFramesObserved": True,
        "physicalEditorExportIndependentlyDecoded": True,
        "deniedNetworkTool": True, "deniedOutsideImport": True,
        "existingSourceExportDenied": True, "outsideNativeDocumentDenied": True,
        "invalidNativeArgumentsRejected": True, "editableTracks": 3, "savedVersions": 5,
        "processRestartReopenPassed": True, "frames": 48, "fps": "24/1", "audioCodec": "aac",
        "fullDecodePassed": True, "physicalModelInterfaceAVTransportFixturePassed": True,
        "physicalHostObservedAssetBatchPlacementPassed": True,
        "physicalEmptyTimelineFirstNativeBatchPlacementPassed": True,
        "physicalNativeBatchProjectRestartPersistencePassed": True,
        "physicalNativeBatchSelectorDiscriminationPassed": True,
        "physicalNativeSingleClipReadConvergencePassed": True,
        "physicalNativeSingleClipExportContractPassed": True,
        "physicalInstalledHostGatewayAdmissionPassed": True,
        "physicalInstalledHostGatewayWriteAndReadbackPassed": True,
        "neuralModelEvaluated": False, "artisticQualityApproved": False,
        "audioRms": audio_rms, "output": str(output), "sha256": digest(output), "fixture": str(fixture)}
    (fixture / "receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if scene_source:
        # Independent new Electron process, not an in-memory JSON fixture.
        async with connected() as session:
            await call(session, "open_project", {
                "projectPath": str(project), "previewOnly": False})
            await wait(session, lambda s:
                (s.get("currentTimeline") or {}).get("name") ==
                "G1 scene revision source proof" and
                (s.get("currentTimeline") or {}).get("clipCount") == 3)
            reopened = await call(session, "get_timeline", {
                "includeClips": True})
            shape = next(c for c in reopened["clips"]
                         if c["id"] == shape_id)
            assert shape["shapeProperties"]["fillColor"].lower() == "#e83b61"
            assert isinstance(shape.get("keyframes"), dict)
            assert len(shape["keyframes"].get("opacity") or []) >= 2
            assert all(any(m["id"] == mid for m in reopened["markers"])
                       for mid in (first_gui_marker, interrupted.manual_marker))
            assert digest(native_path) == scene_save_sha
            assert digest(original) == original_hash
            print("ACTUAL_NATIVE_SCENE_REOPEN " + json.dumps({
                "new_native_Electron_process": True,
                "editable_shape_and_keyframes_persisted": True,
                "manual_GUI_markers_persisted": True,
                "source_video_hash_unchanged": True,
                "model_creativity_attested": False,
            }, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--camera-video", type=Path)
    parser.add_argument("--camera-sha256")
    for name in ("xvfb-binary", "xvfb-lib-dir", "display"):
        parser.add_argument("--" + name)
    parser.add_argument("--no-sandbox", action="store_true")
    parser.add_argument("--software-gpu", action="store_true")
    asyncio.run(exercise(parser.parse_args()))
