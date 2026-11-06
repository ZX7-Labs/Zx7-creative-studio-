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


ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


async def exercise(options):
    fixture = Path(tempfile.mkdtemp(prefix="zx7-editor-mcp-"))
    projects, staging, outputs = (fixture / name for name in ("projects", "staging", "outputs"))
    for path in (projects, staging, outputs):
        path.mkdir()
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

    async with connected() as session:
        discovered = (await session.list_tools()).tools
        assert {tool.name for tool in discovered} == set(tools) | {"zx7_verify_native_export", "zx7_observe_verified_export_frame", "zx7_observe_verified_export_samples", "zx7_observe_verified_export_audio", "zx7_observe_verified_export_audio_timeline"}
        from studio_next.body_editor_client import LocalEditorClient
        native = {tool["name"]: tool for tool in LocalEditorClient(
            "http://127.0.0.1:19790/mcp", allowed_tools={}).list_tools()}
        for tool in discovered:
            if tool.name in native:
                assert tool.input_schema == native[tool.name]["inputSchema"]
        assert (await session.call_tool("queue_prompt_generation_batch", {})).is_error
        assert (await session.call_tool("create_project", {"name": "Bad", "width": "wrong"})).is_error
        created = await call(session, "create_project", {"name": "MCP native edit", "width": 320, "height": 180, "fps": 24, "previewOnly": False})
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
        assert (await session.call_tool("import_asset_from_path", {"path": "/etc/passwd", "previewOnly": False})).is_error
        for name, count in (("source.mp4", 1), ("tone.wav", 2)):
            await call(session, "import_asset_from_path", {"path": str(staging / name), "previewOnly": False})
            await wait(session, lambda state: state.get("assetCount") == count)
        await call(session, "add_asset_to_timeline", {"assetName": "source.mp4", "startSeconds": 0, "includeAudio": False, "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 1)
        await call(session, "add_asset_to_timeline", {"assetName": "tone.wav", "startSeconds": 0, "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 2)
        await call(session, "add_track", {"type": "video", "name": "Editable title", "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("trackCount") == 3)
        title = await call(session, "add_text_clip", {"text": "MCP native edit", "startSeconds": 0, "durationSeconds": 2,
                    "style": {"fontSize": 24}, "previewOnly": False})
        title_id = title["result"]["clip"]["id"]
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 3)
        await call(session, "set_clip_keyframes", {"clipId": title_id, "keyframes": [
            {"property": "opacity", "timeSeconds": 0, "value": 20, "easing": "cubicBezier(0.2,0,0.8,1)"},
            {"property": "opacity", "timeSeconds": 1, "value": 100, "easing": "linear"}], "previewOnly": False})
        await call(session, "save_project", {"previewOnly": False})
        native_path = project / "project.comfystudio"
        shutil.copy2(native_path, fixture / "revision-1.comfystudio")
        await call(session, "update_text_clip", {"clipId": title_id, "text": "MCP revised", "previewOnly": False})
        await call(session, "save_project", {"previewOnly": False})
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
        await call(session, "export_timeline", {"outputPath": str(output), "target": "h264_project", "width": 320,
            "height": 180, "range": "custom", "startSeconds": 0, "endSeconds": 2, "fps": 24,
            "includeAudio": True, "previewOnly": False})
        deadline = time.monotonic() + 90
        while True:
            logs = list((fixture / "state").glob("session-*/velorn/export-worker.log"))
            if any("[ExportWorker] Export complete" in log.read_text() for log in logs):
                break
            assert time.monotonic() < deadline, "Native export worker did not finish"
            await asyncio.sleep(.2)
        inspection = await call(session, "inspect_export_file", {"path": str(output), "width": 320, "height": 180, "durationSeconds": 2})
        assert inspection["ready"], inspection
        assert (await session.call_tool("zx7_observe_verified_export_frame", {
            "path": str(output), "at_seconds": 0.5})).is_error
        proof = await call(session, "zx7_verify_native_export", {
            "path": str(output),
            "expected": {"width": 320, "height": 180,
                         "duration_seconds": 2, "require_audio": True}})
        assert proof["physical_export_verified"] and not proof["artistic_quality_approved"], proof
        assert proof["native_export_sha256"] == digest(output), proof
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
        # Real independent samples provide sparse visual temporal evidence.
        # They do not assert animation/motion continuity or audio understanding.
        sampled = await session.call_tool("zx7_observe_verified_export_samples", {
            "path": str(output), "at_seconds": [0.25, 1.25]})
        assert not sampled.is_error and len(sampled.content) == 3, sampled
        multi_receipt = json.loads(sampled.content[0].text)
        assert multi_receipt["kind"] == "verified_native_editor_selected_frames"
        assert multi_receipt["export_sha256"] == digest(output)
        assert multi_receipt["continuous_motion_or_audio_proven"] is False
        assert [x["sampled_video_seconds_requested"] for x in multi_receipt["samples"]] == [0.25, 1.25]
        for block, evidence in zip(sampled.content[1:], multi_receipt["samples"]):
            assert block.type == "image" and block.mime_type == "image/png"
            png = base64.b64decode(block.data, validate=True)
            assert png.startswith(bytes.fromhex("89504e470d0a1a0a"))
            assert hashlib.sha256(png).hexdigest() == evidence["png_sha256"]
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
        overview = await call(session, "zx7_observe_verified_export_audio_timeline", {
            "path": str(output), "start_seconds": 0, "duration_seconds": 2,
            "bins": 8})
        assert overview["kind"] == "verified_native_editor_audio_temporal_envelope"
        assert overview["export_sha256"] == digest(output)
        assert len(overview["intervals"]) == 8
        assert overview["observed_pcm_samples"] >= 15840
        assert all((entry["rms_dbfs"] is not None and entry["rms_dbfs"] > -55)
                   for entry in overview["intervals"])
        assert not overview["human_or_artistic_quality_approved"]
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
        assert applied.get("previewOnly") is False, "Native batch was not applied"
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
        "transport": "standard MCP stdio; Python SDK 2.3.0", "nativeSchemasUnchanged": True,
        "discoveredGrantedTools": len(tools), "additionalVerifiedBodyTools": 5, "physicalVisualFrameObserved": True,
        "physicalBoundedSourceAudioObserved": True,
        "physicalTemporalAudioEnvelopeObserved": True,
        "physicalSparseTemporalFramesObserved": True,
        "physicalEditorExportIndependentlyDecoded": True,
        "deniedNetworkTool": True, "deniedOutsideImport": True,
        "existingSourceExportDenied": True, "outsideNativeDocumentDenied": True,
        "invalidNativeArgumentsRejected": True, "editableTracks": 3, "savedVersions": 2,
        "processRestartReopenPassed": True, "frames": 48, "fps": "24/1", "audioCodec": "aac",
        "fullDecodePassed": True, "physicalModelInterfaceAVTransportFixturePassed": True,
        "physicalHostObservedAssetBatchPlacementPassed": True,
        "neuralModelEvaluated": False, "artisticQualityApproved": False,
        "audioRms": audio_rms, "output": str(output), "sha256": digest(output), "fixture": str(fixture)}
    (fixture / "receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    for name in ("xvfb-binary", "xvfb-lib-dir", "display"):
        parser.add_argument("--" + name)
    parser.add_argument("--no-sandbox", action="store_true")
    parser.add_argument("--software-gpu", action="store_true")
    asyncio.run(exercise(parser.parse_args()))
