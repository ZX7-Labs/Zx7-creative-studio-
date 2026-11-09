# SPDX-License-Identifier: GPL-3.0-only
"""Create an original 60-second technical EDITABLE native-video demonstration.

A deliberately modest, source-owned procedural film. Five shots, five native
title layers, original sound, genuine app restart, real editor export, physical
full decode, and independent observation frames are all fail-closed checks.
Does not certify aesthetic quality or autonomous creativity.
"""
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
    fixture = Path(tempfile.mkdtemp(prefix="zx7-native-minute-demo-"))
    artifact = options.artifacts.resolve()
    if artifact.exists() and any(artifact.iterdir()):
        raise ValueError("Refusing to overwrite an existing demonstration")
    artifact.mkdir(parents=True, exist_ok=True)
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
        return subprocess.check_output(argv, stderr=subprocess.PIPE, timeout=240)
    # Video source clips are created by local FFmpeg from its open test
    # generator, then independently color-transformed. No downloaded assets.
    for index, hue in enumerate((0, 60, 135, 210, 300)):
        run([ffmpeg, "-v", "error", "-f", "lavfi", "-i",
             "testsrc2=s=640x360:r=24:d=12",
             "-vf", f"hue=h={hue},eq=contrast=1.08",
             "-c:v", "libx264", "-pix_fmt", "yuv420p",
             str(staging / f"scene-{index+1}.mp4")])
    run([ffmpeg, "-v", "error", "-f", "lavfi", "-i",
         "sine=f=440:d=60", "-af", "volume=0.5",
         str(staging / "original-pulse.wav")])
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

    async def wait(session, predicate, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            state = await call(session, "get_project")
            if predicate(state):
                return state
            await asyncio.sleep(.15)
        raise AssertionError("Native debounced project state did not converge")

    async with connected() as session:
        discovered = (await session.list_tools()).tools
        from studio_next.body_editor_client import LocalEditorClient
        native = {tool["name"]: tool for tool in LocalEditorClient(
            "http://127.0.0.1:19790/mcp", allowed_tools={}).list_tools()}
        assert_editor_catalog(discovered, tools, native)
        body_tools = {tool.name for tool in discovered} - set(tools)
        assert (await session.call_tool("queue_prompt_generation_batch", {})).is_error
        assert (await session.call_tool("create_project", {"name": "Bad", "width": "wrong"})).is_error
        await call(session, "create_project", {"name": "ZX7 original minute editing acceptance", "width": 640, "height": 360, "fps": 24, "previewOnly": False})
        state = await wait(session, lambda state: (state.get("project") or {}).get("name") == "ZX7 original minute editing acceptance")
        project = Path(state["project"]["path"])
        assert (await session.call_tool("import_asset_from_path", {"path": "/etc/passwd", "previewOnly": False})).is_error
        for index in range(5):
            await call(session, "import_asset_from_path", {
                "path": str(staging / f"scene-{index+1}.mp4"), "previewOnly": False})
            await wait(session, lambda state, count=index+1: state.get("assetCount") == count)
        await call(session, "import_asset_from_path", {
            "path": str(staging / "original-pulse.wav"), "previewOnly": False})
        await wait(session, lambda state: state.get("assetCount") == 6)
        for index in range(5):
            await call(session, "add_asset_to_timeline", {
                "assetName": f"scene-{index+1}.mp4", "startSeconds": index*12,
                "includeAudio": False, "previewOnly": False})
            await wait(session, lambda state, count=index+1:
                       (state.get("currentTimeline") or {}).get("clipCount") == count)
        await call(session, "add_asset_to_timeline", {
            "assetName": "original-pulse.wav", "startSeconds": 0, "previewOnly": False})
        await wait(session, lambda state:
                   (state.get("currentTimeline") or {}).get("clipCount") == 6)
        titles = ("SOURCE-OWNED VISUALS", "AN EDITABLE TIMELINE",
                  "ORIGINAL AUDIO", "PHYSICAL OUTPUT PROOF", "ZX7 BODY / NATIVE EDIT")
        title_ids = []
        for index, title_text in enumerate(titles):
            await call(session, "add_track", {
                "type": "video", "name": f"Editable title {index+1}", "previewOnly": False})
            await wait(session, lambda state, count=index+3:
                       (state.get("currentTimeline") or {}).get("trackCount") == count)
            title_result = await call(session, "add_text_clip", {
                "text": title_text, "startSeconds": index*12,
                "durationSeconds": 12, "style": {"fontSize": 30},
                "previewOnly": False})
            title_ids.append(title_result["result"]["clip"]["id"])
            await wait(session, lambda state, count=index+7:
                       (state.get("currentTimeline") or {}).get("clipCount") == count)
            await call(session, "set_clip_keyframes", {
                "clipId": title_ids[-1], "keyframes": [
                    {"property": "opacity", "timeSeconds": 0, "value": 20, "easing": "linear"},
                    {"property": "opacity", "timeSeconds": 1, "value": 100, "easing": "linear"},
                    {"property": "opacity", "timeSeconds": 11, "value": 100, "easing": "linear"},
                ], "previewOnly": False})
        title_id = title_ids[1]
        await call(session, "save_project", {"previewOnly": False})
        native_path = project / "project.comfystudio"
        shutil.copy2(native_path, fixture / "revision-1.comfystudio")
        await call(session, "update_text_clip", {"clipId": title_id, "text": "AN EDITABLE NATIVE TIMELINE", "previewOnly": False})
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
        await call(session, "export_timeline", {"outputPath": str(output), "target": "h264_project", "width": 640,
            "height": 360, "range": "custom", "startSeconds": 0, "endSeconds": 60, "fps": 24,
            "includeAudio": True, "previewOnly": False})
        deadline = time.monotonic() + 600
        while True:
            logs = list((fixture / "state").glob("session-*/velorn/export-worker.log"))
            if any("[ExportWorker] Export complete" in log.read_text() for log in logs):
                break
            assert time.monotonic() < deadline, "Native export worker did not finish"
            await asyncio.sleep(.2)
        inspection = await call(session, "inspect_export_file", {"path": str(output), "width": 640, "height": 360, "durationSeconds": 60})
        assert inspection["ready"], inspection
        assert (await session.call_tool("zx7_observe_verified_export_frame", {
            "path": str(output), "at_seconds": 0.5})).is_error
        proof = await call(session, "zx7_verify_native_export", {
            "path": str(output),
            "expected": {"width": 640, "height": 360,
                         "duration_seconds": 60, "require_audio": True}})
        assert proof["physical_export_verified"] and not proof["artistic_quality_approved"], proof
        assert proof["native_export_sha256"] == digest(output), proof
        samples = []
        for second in (6, 18, 30, 42, 54):
            observed = await session.call_tool("zx7_observe_verified_export_frame", {
                "path": str(output), "at_seconds": second})
            assert not observed.is_error and len(observed.content) == 2, observed
            assert observed.content[1].type == "image" and observed.content[1].mime_type == "image/png"
            png = base64.b64decode(observed.content[1].data, validate=True)
            frame_receipt = json.loads(observed.content[0].text)
            assert png.startswith(bytes.fromhex("89504e470d0a1a0a"))
            assert frame_receipt["export_sha256"] == digest(output)
            assert frame_receipt["png_sha256"] == hashlib.sha256(png).hexdigest()
            frame_path = artifact / f"native-frame-{second:02d}s.png"
            frame_path.write_bytes(png)
            samples.append({"second": second, "sha256": digest(frame_path)})
        assert len({sample["sha256"] for sample in samples}) == 5, samples
        # Hear a real native audio excerpt in the same source-bound session;
        # it is not a certificate of full-film mixing or artistic quality.
        heard = await session.call_tool("zx7_observe_verified_export_audio", {
            "path": str(output), "start_seconds": 36, "duration_seconds": 2})
        assert not heard.is_error and len(heard.content) == 2, heard
        assert heard.content[1].type == "audio"
        assert heard.content[1].mime_type == "audio/wav"
        wav = base64.b64decode(heard.content[1].data, validate=True)
        assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
        heard_receipt = json.loads(heard.content[0].text)
        assert heard_receipt["export_sha256"] == digest(output)
        assert heard_receipt["wav_sha256"] == hashlib.sha256(wav).hexdigest()
        assert heard_receipt["observed_pcm_frames"] > 30000
        assert not heard_receipt["full_film_listening_or_spatial_mix_verified"]
        (artifact / "native-audio-36s.wav").write_bytes(wav)
        # Independently inspect the *entire* original 60-second sound bed as
        # 60 physical one-second decoder buckets. Whole-film RMS alone could
        # conceal a clipped/silent scene boundary or half a missing soundtrack.
        audio_timeline = await call(session, "zx7_observe_verified_export_audio_timeline", {
            "path": str(output), "start_seconds": 0, "duration_seconds": 60,
            "bins": 60})
        assert audio_timeline["kind"] == "verified_native_editor_audio_temporal_envelope"
        assert audio_timeline["export_sha256"] == digest(output)
        assert audio_timeline["preview_downmixed_and_resampled"] is True
        assert audio_timeline["exact_original_audio_pts_proven"] is False
        envelope = audio_timeline["intervals"]
        assert len(envelope) == 60, "Missing one or more physical soundtrack seconds"
        dbs = [item["rms_dbfs"] for item in envelope]
        assert all(type(db) in (int, float) and math.isfinite(db) for db in dbs)
        assert all(item["no_nonzero_mono_samples"] is False for item in envelope)
        assert -50 < min(dbs) and max(dbs) < -5, (
            "A portion of the original soundtrack vanished or clipped", min(dbs), max(dbs))
        assert max(dbs) - min(dbs) < 3, (
            "Original uniform soundtrack became unstable at a native edit boundary", dbs)
        audio_continuity = {
            "original_source_must_span_all_60_seconds": True,
            "verified_pcm_buckets": len(envelope),
            "min_rms_dbfs": min(dbs), "max_rms_dbfs": max(dbs),
            "source_sha256": audio_timeline["export_sha256"],
            "full_film_mix_or_sample_exact_pts_approved": False,
        }

    async with connected() as session:
        await call(session, "open_project", {"projectPath": str(project), "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 11 and state.get("assetCount") == 6)
        timeline = await call(session, "get_timeline", {"includeClips": True})
        title = next(clip for clip in timeline["clips"] if clip["id"] == title_id)
        assert title["textProperties"]["text"] == "AN EDITABLE NATIVE TIMELINE"
        assert title["keyframes"] == next(clip for clip in saved["timelines"][0]["clips"] if clip["id"] == title_id)["keyframes"]
    probe = json.loads(run([ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(output)]))
    video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
    audio = next(stream for stream in probe["streams"] if stream["codec_type"] == "audio")
    assert (video["width"], video["height"], video["r_frame_rate"], int(video["nb_read_frames"])) == (640, 360, "24/1", 1440)
    assert video["codec_name"] == "h264"
    assert audio["codec_name"] == "aac"
    assert abs(float(probe["format"]["duration"]) - 60) < .05
    # Independently prove the 60s encoded movie still shows the intended
    # *five different* source shots in order, not just five distinct hashes.
    # Measure four video corners, excluding center titles. Competing source
    # clips are compared on the same original 6-second source-relative frame.
    def picture_at(path, seconds):
        frame = run([ffmpeg, "-v", "error", "-ss", str(seconds), "-i",
                     str(path), "-map", "0:v:0", "-frames:v", "1",
                     "-vf", "format=rgb24", "-f", "rawvideo", "pipe:1"])
        assert len(frame) == 640 * 360 * 3, ("Invalid decoded full RGB frame", path, len(frame))
        return frame

    def corners(frame):
        samples = []
        for left, top in ((0, 0), (576, 0), (0, 296), (576, 296)):
            region = b"".join(frame[((top + y)*640 + left)*3:
                                    ((top + y)*640 + left + 64)*3]
                              for y in range(64))
            assert len(region) == 64*64*3
            samples.append(region)
        return samples

    original_frames = [picture_at(staging / f"scene-{i+1}.mp4", 6)
                       for i in range(5)]
    reference = [corners(frame) for frame in original_frames]
    source_alignment = []
    rendered_frames = []
    for index, second in enumerate((6, 18, 30, 42, 54)):
        actual = picture_at(output, second)
        rendered_frames.append(actual)
        actual_corners = corners(actual)
        winners = 0
        errors = []
        for corner_index, observed in enumerate(actual_corners):
            differences = [
                sum(abs(x-y) for x, y in zip(observed, reference[src][corner_index]))
                / len(observed) for src in range(5)]
            nearest = min(range(5), key=lambda src: differences[src])
            winners += nearest == index
            errors.append(round(differences[index], 3))
        # If even the corners are no longer the intended shot, a playable
        # movie and a readable title are insufficient editorial evidence.
        assert winners >= 3 and min(errors) < 45, (
            "Native export lost source/shot identity", index, second, winners, errors)
        source_alignment.append({"source_index": index, "at_seconds": second,
                                 "corners_matching_correct_shot": winners,
                                 "source_corner_mean_absolute_error": errors})
    # An editable title in a saved project is not evidence that its pixels
    # survived the native export. Compare real source frames against physically
    # decoded exported frames, away from the source generator's top-left clock.
    # Neutral white is intentionally absent from these 5 synthetic source
    # center-bands; the original title is rendered in this exact native region.
    def title_white_pixels(frame):
        if len(frame) != 640 * 360 * 3:
            raise AssertionError("Cannot inspect a malformed decoded video frame")
        count = 0
        for y in range(145, 204):
            for x in range(65, 585):
                at = (y * 640 + x) * 3
                red, green, blue = frame[at:at+3]
                if min(red, green, blue) > 210 and max(red, green, blue) - min(red, green, blue) < 35:
                    count += 1
        return count

    title_pixels = []
    for index, (original_frame, exported_frame) in enumerate(zip(original_frames, rendered_frames)):
        source_white = title_white_pixels(original_frame)
        export_white = title_white_pixels(exported_frame)
        # A missing title silently passes a clip-count or native-project test.
        # Do not make merely playable source footage count as composed editing.
        assert export_white > source_white + 300, (
            "The native export lost its real overlaid title pixels",
            index, source_white, export_white)
        title_pixels.append({"source_index": index,
                             "original_neutral_bright_pixels": source_white,
                             "native_export_neutral_bright_pixels": export_white})
    quiet = title_white_pixels(picture_at(output, 0.3))
    full = title_white_pixels(picture_at(output, 1.5))
    assert full > quiet + 300, (
        "The native title keyframe did not visibly fade in", quiet, full)
    title_fade_pixels = {"at_0_3_seconds": quiet, "at_1_5_seconds": full,
                         "verified_real_visible_fade": True}
    run([ffmpeg, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"])
    pcm = run([ffmpeg, "-v", "error", "-i", str(output), "-map", "0:a:0", "-ac", "1", "-f", "f32le", "pipe:1"])
    from array import array
    pcm_samples = array("f")
    pcm_samples.frombytes(pcm)
    assert pcm_samples, "Original audio decoder returned no PCM samples"
    audio_rms = math.sqrt(sum(sample * sample for sample in pcm_samples) / len(pcm_samples))
    assert .015 < audio_rms < .2
    receipt = {"success": True, "kind": "scripted official SDK client; no autonomous model evaluation",
        "transport": "standard MCP stdio; Python SDK 2.3.0", "nativeSchemasUnchanged": True,
        "discoveredGrantedTools": len(tools), "additionalVerifiedBodyTools": len(body_tools), "physicalVisualFrameObserved": True,
        "physicalEditorExportIndependentlyDecoded": True, "realBoundedAudioHeard": True,
        "realFullMinuteAudioContinuity": audio_continuity,
        "deniedNetworkTool": True, "deniedOutsideImport": True,
        "existingSourceExportDenied": True, "outsideNativeDocumentDenied": True,
        "invalidNativeArgumentsRejected": True, "editableTracks": 7, "editableClips": 11, "sourceOwnedGeneratedShots": 5, "physicalSourceShotOrder": source_alignment,
        "realCompositedTitlePixels": title_pixels, "realTitleOpacityKeyframePixels": title_fade_pixels,
        "distinctVideoFrames": samples, "technicalDemoOnly": True,
        "professionalCreativeCapabilityComplete": False,
        "autonomousArtisticQualityProven": False, "savedVersions": 2,
        "processRestartReopenPassed": True, "frames": 1440, "fps": "24/1", "audioCodec": "aac",
        "fullDecodePassed": True, "audioRms": audio_rms, "output": str(output), "sha256": digest(output), "fixture": str(fixture)}
    (fixture / "receipt.json").write_text(json.dumps(receipt, indent=2))
    # Preserve the complete source-bearing, editable native project, not only
    # its project manifest. The copied relative asset paths remain usable.
    shutil.copytree(project, artifact / "native-editable-project")
    shutil.copy2(output, artifact / "zx7-body-one-minute-native-demo.mp4")
    shutil.copy2(fixture / "revision-1.comfystudio", artifact / "revision-1.comfystudio")
    shutil.copy2(fixture / "revision-2.comfystudio", artifact / "revision-2.comfystudio")
    assert len(samples) == 5 and all("second" in item for item in samples)
    receipt_text = json.dumps(receipt, indent=2, allow_nan=False)
    assert len(receipt_text) < 32768, "Unexpectedly large demo evidence"
    (artifact / "evidence.json").write_text(receipt_text + "\n")
    print(receipt_text, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    for name in ("xvfb-binary", "xvfb-lib-dir", "display"):
        parser.add_argument("--" + name)
    parser.add_argument("--no-sandbox", action="store_true")
    parser.add_argument("--software-gpu", action="store_true")
    asyncio.run(exercise(parser.parse_args()))
