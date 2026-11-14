# SPDX-License-Identifier: GPL-3.0-only
"""Actual installed creative BODY graph -> native Electron timeline -> picture+sound.

Scripted, host-authorized tool decisions. Neither a neural creative model nor a
professional VFX review. Requires separate synthetic X11 source-pinned editor.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from studio_next.body_capability_adapter import InstalledBodyAdapter
from studio_next.native_editor_session import (
    attest_owner_body_source, editor_runtime_path,
    native_editor_child_environment, native_session_grants)
from studio_next.native_editor_identity import pinned_native_editor_identity_policy
from studio_next.capability_gateway import CapabilityGateway
from studio_next.capability_mcp_session import CombinedCapabilityMcpSession
from studio_next.capability_session_budget import CapabilitySessionBudget


def digest(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()


def decode(cmd, timeout=100):
    return subprocess.check_output(cmd, stderr=subprocess.PIPE, timeout=timeout)


def text_receipt(response):
    assert not response.is_error, response
    texts = [c.text for c in response.content if c.type == "text"]
    assert len(texts) == 1
    return json.loads(texts[0])


def graphic_plan():
    # A synthetic artistic fixture, NOT a universal scene design.
    return {
        "version": "zx7-visual-graph/1",
        "canvas": {"width": 320, "height": 180,
                   "frame_rate": {"numerator": 24, "denominator": 1},
                   "frames": 48, "working_space": "linear_srgb"},
        "nodes": [{
            "id": "original", "op": "expression", "inputs": {},
            "params": {"channels": {
                "r": "u", "g": "v", "b": "0.25", "a": "1"},
                "uniforms": {}},
        }],
        "output": "original",
        "render": {"first_frame": 0, "frame_count": 1, "format": "png",
                   "rgb_range": "clip_to_sdr", "audio": "separate_tracks"},
    }


async def exercise(source: Path, xvfb: str, display: str):
    assert shutil.which("ffmpeg") and shutil.which("ffprobe")
    assert source.is_dir() and (source / "dist/index.html").is_file()
    with tempfile.TemporaryDirectory(prefix="zx7-unified-owner-native-") as temp:
        root = Path(temp) / "studio"
        root.mkdir(mode=0o700)
        for name in ("projects", "staging", "outputs", "state"):
            (root / name).mkdir(mode=0o700)
        plan = root / "staging" / "original-art.json"
        plan.write_text(json.dumps(graphic_plan(), sort_keys=True), encoding="utf-8")
        graph_sha = digest(plan)
        tone = root / "staging" / "original-tone.wav"
        decode(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi",
                "-i", "sine=f=440:sample_rate=48000:duration=2",
                "-ac", "2", str(tone)])
        tone_sha = digest(tone)
        original = root / "staging" / "original-art.png"
        export = root / "outputs" / "original-graph-and-sound.mp4"
        source_config = json.loads((Path(__file__).parent / "editor.example.json").read_text())
        source_config.update({
            "projects_root": str(root / "projects"),
            "staging_root": str(root / "staging"),
            "outputs_root": str(root / "outputs"),
            "allowed_access": ["read", "write"],
            "verify_native_exports": True,
        })
        config = root / "editor.json"
        config.write_text(json.dumps(source_config), encoding="utf-8")
        host_grants = native_session_grants(source_config, source)
        source_adapter = attest_owner_body_source(
            root, configuration=source_config, provider="local")
        assert isinstance(source_adapter, InstalledBodyAdapter)
        params = StdioServerParameters(command="node", args=[
            str(editor_runtime_path("mcp.mjs")),
            "--source", str(source),
            "--config", str(config),
            "--state", str(root / "state"),
            "--python", sys.executable,
            "--xvfb-binary", xvfb,
            "--display", display,
        ], cwd=Path(__file__).resolve().parents[2],
            env=native_editor_child_environment())

        @asynccontextmanager
        async def connected():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write,
                                         read_timeout_seconds=120) as raw:
                    await raw.initialize()
                    budget = CapabilitySessionBudget(
                        max_calls=200, max_writes=24)
                    identity = pinned_native_editor_identity_policy(
                        source, host_grants, raw,
                        reserve_read=lambda: budget.reserve(
                            source="editor", access="read"))
                    assert identity and identity["fence"]
                    gateway = CapabilityGateway({
                        "editor": (raw, host_grants, {}, None, {}, identity),
                        "zx7": (source_adapter, source_adapter.trusted_grants),
                    }, session_budget=budget)
                    await gateway.refresh()
                    view = CombinedCapabilityMcpSession(
                        gateway, "editor", "zx7",
                        require_model_native_observation_for=("editor",))
                    discovered = {x.name for x in (await view.list_tools()).tools}
                    assert {"body.visual_graph", "create_project",
                            "import_asset_from_path", "get_timeline",
                            "get_project", "add_asset_to_timeline", "save_project",
                            "export_timeline", "zx7_verify_native_export"}.issubset(discovered), discovered
                    assert "body.research_assets" not in discovered, (
                        "This local creative-source mode cannot silently authorize network research")
                    yield view, gateway

        async def invoke(view, name, args=None):
            return text_receipt(await view.call_tool(name, args or {}))

        async def read_until(view, check, seconds=25):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                data = await invoke(view, "get_project")
                if check(data):
                    return data
                await asyncio.sleep(.15)
            raise AssertionError("Native source snapshot did not converge")

        async with connected() as (studio, gateway):
            result = await invoke(studio, "body.visual_graph", {
                "plan": "staging/original-art.json",
                "out": "staging/original-art.png",
            })
            assert result and original.is_file()
            image_sha = digest(original)
            assert len(image_sha) == 64 and digest(plan) == graph_sha
            image_decoded = decode(["ffmpeg", "-nostdin", "-v", "error",
                                   "-i", str(original), "-pix_fmt", "rgb24",
                                   "-f", "rawvideo", "-"])
            assert len(image_decoded) == 320 * 180 * 3
            assert len(set(image_decoded)) > 64, "A fake/blank generated image is not evidence"

            await invoke(studio, "create_project", {
                "name": "Real cross-engine editable visual and sound",
                "width": 320, "height": 180, "fps": 24,
                "previewOnly": False})
            current = await read_until(studio, lambda s:
                s.get("mcp", {}).get("hasProject") is True)
            project = Path(current["project"]["path"])
            assert project.is_relative_to(root / "projects") and project.is_dir()
            for file in (original, tone):
                await invoke(studio, "import_asset_from_path", {
                    "path": str(file), "previewOnly": False})
            await read_until(studio, lambda s: s.get("assetCount") == 2)
            all_clips = await invoke(studio, "get_timeline", {"includeClips": True})
            video_track = next(t["id"] for t in all_clips["tracks"]
                               if t["type"] == "video")
            await invoke(studio, "get_project")
            await invoke(studio, "add_asset_to_timeline", {
                "assetName": original.name, "trackId": video_track,
                "startSeconds": 0, "durationSeconds": 2,
                "includeAudio": False, "previewOnly": False})
            await read_until(studio, lambda s:
                s.get("currentTimeline", {}).get("clipCount") == 1)
            await invoke(studio, "get_project")
            await invoke(studio, "add_asset_to_timeline", {
                "assetName": tone.name, "startSeconds": 0,
                "previewOnly": False})
            await read_until(studio, lambda s:
                s.get("currentTimeline", {}).get("clipCount") == 2)
            timeline = await invoke(studio, "get_timeline", {"includeClips": True})
            assert len(timeline["clips"]) == 2
            assert {c["type"] for c in timeline["clips"]} == {"video", "audio"}
            assert digest(original) == image_sha and digest(tone) == tone_sha
            save = await invoke(studio, "save_project", {"previewOnly": False})
            document = project / "project.comfystudio"
            assert document.is_file() and not document.is_symlink()
            actual_saved = json.loads(document.read_text(encoding="utf-8"))
            assert actual_saved["modified"] == save["result"]["project"]["modified"]
            assert any(len(t.get("clips") or []) == 2
                       for t in actual_saved["timelines"])
            saved_sha = digest(document)
            # A native render must be physically decoded, including sound.
            await invoke(studio, "export_timeline", {
                "outputPath": str(export), "target": "h264_project",
                "width": 320, "height": 180, "fps": 24,
                "range": "custom", "startSeconds": 0,
                "endSeconds": 2, "includeAudio": True,
                "previewOnly": False})
            deadline = time.monotonic() + 90
            video_pcm = audio_pcm = None
            while time.monotonic() < deadline:
                try:
                    if export.is_file() and export.stat().st_size > 4000:
                        video_pcm = decode(["ffmpeg", "-nostdin", "-v", "error",
                                            "-xerror", "-i", str(export),
                                            "-map", "0:v:0", "-f", "rawvideo",
                                            "-pix_fmt", "rgb24", "-"])
                        audio_pcm = decode(["ffmpeg", "-nostdin", "-v", "error",
                                            "-xerror", "-i", str(export),
                                            "-map", "0:a:0", "-ac", "1",
                                            "-ar", "16000", "-f", "s16le", "-"])
                        break
                except (subprocess.CalledProcessError, OSError):
                    pass
                await asyncio.sleep(.35)
            assert video_pcm is not None and audio_pcm is not None, (
                "Real native editor did not produce independently decoded audiovisual output")
            assert len(video_pcm) == 48 * 320 * 180 * 3
            assert len(audio_pcm) >= 48000 and any(audio_pcm), (
                "The original authored sound source was absent/silent")
            assert len(set(video_pcm[:320 * 180 * 3])) > 64
            # The encoded first frame must *visually correspond* to BODY's
            # independently decoded original graphic, not just be nonblank.
            # Lossy H.264 chroma/resampling may differ slightly by design.
            first_frame = video_pcm[:len(image_decoded)]
            assert len(first_frame) == len(image_decoded)
            mean_abs_pixel_error = sum(
                abs(a - b) for a, b in zip(first_frame, image_decoded)
            ) / len(image_decoded)
            assert mean_abs_pixel_error < 25, (
                "The native picture does not resemble the BODY-authored graphic",
                round(mean_abs_pixel_error, 2))
            verification = await invoke(studio, "zx7_verify_native_export", {
                "path": str(export), "expected": {
                    "width": 320, "height": 180,
                    "duration_seconds": 2, "require_audio": True}})
            assert verification["physical_export_verified"] is True
            assert verification["native_export_sha256"] == digest(export)
            assert digest(document) == saved_sha
            assert digest(plan) == graph_sha
            assert digest(original) == image_sha and digest(tone) == tone_sha
            assert gateway.host_budget_evidence()["reserved_writes"] >= 6
        # New real Electron session, not one fake in-memory project document.
        async with connected() as (reopened, _):
            await invoke(reopened, "open_project", {
                "projectPath": str(project), "previewOnly": False})
            await read_until(reopened, lambda s:
                s.get("currentTimeline", {}).get("clipCount") == 2)
            actual = await invoke(reopened, "get_timeline", {"includeClips": True})
            assert len(actual["clips"]) == 2
            assert any(c["assetId"] == timeline["clips"][0]["assetId"]
                       for c in actual["clips"])
            assert digest(document) == saved_sha
            assert digest(original) == image_sha and digest(tone) == tone_sha
        print("ACTUAL_OWNER_UNIFIED_GRAPH_NATIVE_AV " + json.dumps({
            "one_real_editor_and_installed_body_gateway": True,
            "actual_original_editable_visual_graph": True,
            "original_generated_picture_and_audio_sha_preserved": True,
            "native_editor_imported_generated_media_and_sound": True,
            "native_editable_project_saved_and_fresh_Electron_reopened": True,
            "fully_decoded_48_video_frames_and_original_sound": True,
            "native_decoded_picture_matches_body_authored_pixels": True,
            "native_export_source_bound_verification": True,
            "genuine_model_artistry_or_professional_VFX_approved": False,
        }, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--xvfb-binary", required=True)
    parser.add_argument("--display", required=True)
    args = parser.parse_args()
    asyncio.run(exercise(args.source.resolve(strict=True),
                         args.xvfb_binary, args.display))
