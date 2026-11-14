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


async def exercise(source: Path, xvfb: str, display: str, *, with_blender=False):
    assert shutil.which("ffmpeg") and shutil.which("ffprobe")
    assert source.is_dir() and (source / "dist/index.html").is_file()
    with tempfile.TemporaryDirectory(prefix="zx7-unified-owner-native-") as temp:
        root = Path(temp) / "studio"
        root.mkdir(mode=0o700)
        for name in ("projects", "staging", "outputs", "state"):
            (root / name).mkdir(mode=0o700)
        # Source must first be authored through the real model-visible BODY
        # operation, never quietly pre-created by this test fixture.
        plan = root / "creative-graphs" / "original-art.json"
        revised_plan = root / "creative-graphs" / "original-art-v2.json"
        revised_image = root / "staging" / "revised-art.png"
        tone = root / "staging" / "original-tone.wav"
        decode(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi",
                "-i", "sine=f=440:sample_rate=48000:duration=2",
                "-ac", "2", str(tone)])
        tone_sha = digest(tone)
        if with_blender:
            from studio_next.body_motion_proof import fixture_job
            from studio_next.body_motion_project import verify_motion_bundle
            original_job = fixture_job()
            # Real 1-second camera/type/geometry-nodes animation at 12fps.
            original_job["renders"] = [
                {"scene": "Scene", "frame": frame, "format": "png"}
                for frame in range(1, 13)]
            revision_job = {
                "version": original_job["version"],
                "project": "staging/native-3d-original.zxmotion",
                "actions": [
                    {"op": "set", "path": ["data", "curves", "Typography", "body"],
                     "value": "REVISED"},
                    {"op": "read", "path": ["data", "curves", "Typography", "body"]},
                ],
                "renders": [{"scene": "Scene", "frame": 3, "format": "png"}],
            }
            original_job_path = root / "staging" / "native-3d-original.json"
            revised_job_path = root / "staging" / "native-3d-revision.json"
            original_job_path.write_text(json.dumps(original_job), encoding="utf-8")
            revised_job_path.write_text(json.dumps(revision_job), encoding="utf-8")
            original_job_sha = digest(original_job_path)
            revised_job_sha = digest(revised_job_path)
            original_bundle = root / "staging" / "native-3d-original.zxmotion"
            revised_bundle = root / "staging" / "native-3d-revision.zxmotion"
            original_3d_video = root / "staging" / "native-3d-original.mp4"
            revised_3d_image = root / "staging" / "native-3d-revision.png"
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
                    assert {"body.visual_author", "body.visual_document",
                            "body.visual_graph", "create_project",
                            "import_asset_from_path", "get_timeline",
                            "get_project", "add_asset_to_timeline", "save_project",
                            "export_timeline", "zx7_verify_native_export"}.issubset(discovered), discovered
                    assert "body.research_assets" not in discovered, (
                        "This local creative-source mode cannot silently authorize network research")
                    if with_blender:
                        assert {"body.motion_project", "body.motion_export"}.issubset(
                            discovered), ("Installed Blender 4.5+ and native source controls required", discovered)
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
            first_document = graphic_plan()
            authored = await invoke(studio, "body.visual_author", {
                "document": first_document,
                "out": "creative-graphs/original-art.json",
            })
            assert authored["editable_source_file_committed"] is True
            graph_sha = authored["sha256"]
            assert plan.is_file() and digest(plan) == graph_sha
            source_read = await invoke(studio, "body.visual_document", {
                "plan": authored["relative_path"]})
            assert source_read["graph"] == first_document
            assert source_read["sha256"] == graph_sha

            # Real distinct authored revision; no original overwrite.
            revision = json.loads(json.dumps(first_document))
            revision["nodes"][0]["params"]["channels"]["r"] = "1-u"
            revision_receipt = await invoke(studio, "body.visual_author", {
                "document": revision,
                "out": "creative-graphs/original-art-v2.json",
                "base": authored["relative_path"],
                "expected_sha256": authored["sha256"],
            })
            assert revision_receipt["previous"]["sha256"] == graph_sha
            assert revised_plan.is_file() and digest(plan) == graph_sha
            reread = await invoke(studio, "body.visual_document", {
                "plan": revision_receipt["relative_path"]})
            assert reread["graph"] == revision
            assert reread["sha256"] == revision_receipt["sha256"]
            await invoke(studio, "body.visual_graph", {
                "plan": revision_receipt["relative_path"],
                "out": "staging/revised-art.png",
            })
            assert revised_image.is_file()
            result = await invoke(studio, "body.visual_graph", {
                "plan": authored["relative_path"],
                "out": "staging/original-art.png",
            })
            assert revised_image.read_bytes() != original.read_bytes()
            assert digest(plan) == graph_sha
            assert digest(revised_plan) == revision_receipt["sha256"]
            assert result and original.is_file()
            image_sha = digest(original)
            assert len(image_sha) == 64 and digest(plan) == graph_sha
            image_decoded = decode(["ffmpeg", "-nostdin", "-v", "error",
                                   "-i", str(original), "-pix_fmt", "rgb24",
                                   "-f", "rawvideo", "-"])
            assert len(image_decoded) == 320 * 180 * 3
            assert len(set(image_decoded)) > 64, "A fake/blank generated image is not evidence"

            if with_blender:
                from zipfile import ZipFile
                receipt = await invoke(studio, "body.motion_project", {
                    "plan": "staging/native-3d-original.json",
                    "out": "staging/native-3d-original.zxmotion",
                })
                assert receipt["native_project_observations"]["renders"]
                native_original = verify_motion_bundle(original_bundle)
                original_bundle_sha = digest(original_bundle)
                assert len(native_original["native"]["renders"]) == 12
                assert {"Camera", "Title", "Bar"}.issubset(
                    {item["name"] for item in native_original["native"]["objects"]})
                assert all((item["width"], item["height"]) == (96, 64)
                           for item in native_original["native"]["renders"])
                with ZipFile(original_bundle) as bundle:
                    assert bundle.read("project.blend").startswith(b"BLENDER")
                    first_3d_render = bundle.read("render_000001.png")
                    assert first_3d_render != bundle.read("render_000004.png"), (
                        "Native 3D animation must produce visibly different frame bytes")
                changed = await invoke(studio, "body.motion_project", {
                    "plan": "staging/native-3d-revision.json",
                    "out": "staging/native-3d-revision.zxmotion",
                })
                native_revised = verify_motion_bundle(revised_bundle)
                assert native_revised["parent_bundle_sha256"] == original_bundle_sha
                assert native_revised["native"]["actions"][1]["result"] == "REVISED"
                with ZipFile(revised_bundle) as bundle:
                    assert bundle.read("project.blend").startswith(b"BLENDER")
                    assert bundle.read("render_000000.png") != first_3d_render
                assert digest(original_bundle) == original_bundle_sha
                assert digest(original_job_path) == original_job_sha
                assert digest(revised_job_path) == revised_job_sha
                await invoke(studio, "body.motion_export", {
                    "bundle": "staging/native-3d-original.zxmotion",
                    "out": "staging/native-3d-original.mp4",
                    "fps": 12})
                await invoke(studio, "body.motion_export", {
                    "bundle": "staging/native-3d-revision.zxmotion",
                    "out": "staging/native-3d-revision.png", "fps": 12})
                assert original_3d_video.is_file() and revised_3d_image.is_file()
                motion_video_sha = digest(original_3d_video)
                movie_rgb = decode(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
                    "-i", str(original_3d_video), "-map", "0:v:0", "-pix_fmt",
                    "rgb24", "-f", "rawvideo", "-"])
                assert len(movie_rgb) == 12 * 96 * 64 * 3
                assert movie_rgb[:96 * 64 * 3] != movie_rgb[4*96*64*3:5*96*64*3]
                assert len(set(movie_rgb)) > 50

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
                (s.get("currentTimeline") or {}).get("clipCount") == 1)
            await invoke(studio, "get_project")
            await invoke(studio, "add_asset_to_timeline", {
                "assetName": tone.name, "startSeconds": 0,
                "previewOnly": False})
            await read_until(studio, lambda s:
                (s.get("currentTimeline") or {}).get("clipCount") == 2)
            if with_blender:
                await invoke(studio, "get_project")
                await invoke(studio, "import_asset_from_path", {
                    "path": str(original_3d_video), "previewOnly": False})
                await read_until(studio, lambda s: s.get("assetCount") == 3)
                await invoke(studio, "get_project")
                await invoke(studio, "add_asset_to_timeline", {
                    "assetName": original_3d_video.name,
                    "trackId": video_track,
                    "startSeconds": 2, "durationSeconds": 1,
                    "includeAudio": False, "previewOnly": False})
                await read_until(studio, lambda s:
                    (s.get("currentTimeline") or {}).get("clipCount") == 3)
            timeline = await invoke(studio, "get_timeline", {"includeClips": True})
            assert len(timeline["clips"]) == (3 if with_blender else 2)
            if with_blender:
                assert any(abs(c.get("startTime", -1) - 2) < .001
                           and c["type"] == "video" for c in timeline["clips"]), (
                    "Native timeline must retain genuine Blender movie in a distinct editable clip")
            clip_types = {c["type"] for c in timeline["clips"]}
            assert "audio" in clip_types and clip_types.intersection({"image", "video"}), (
                "Native imported PNG and original tone must remain separate editable tracks",
                clip_types)
            assert digest(original) == image_sha and digest(tone) == tone_sha
            save = await invoke(studio, "save_project", {"previewOnly": False})
            document = project / "project.comfystudio"
            assert document.is_file() and not document.is_symlink()
            actual_saved = json.loads(document.read_text(encoding="utf-8"))
            assert actual_saved["modified"] == save["result"]["project"]["modified"]
            assert any(len(t.get("clips") or []) == (
                3 if with_blender else 2) for t in actual_saved["timelines"])
            saved_sha = digest(document)
            # A native render must be physically decoded, including sound.
            await invoke(studio, "export_timeline", {
                "outputPath": str(export), "target": "h264_project",
                "width": 320, "height": 180, "fps": 24,
                "range": "custom", "startSeconds": 0,
                "endSeconds": 3 if with_blender else 2,
                "includeAudio": True,
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
            assert len(video_pcm) == (72 if with_blender else 48) * 320 * 180 * 3
            assert len(audio_pcm) >= 48000 and any(audio_pcm), (
                "The original authored sound source was absent/silent")
            assert len(set(video_pcm[:320 * 180 * 3])) > 64
            # The encoded first frame must *visually correspond* to BODY's
            # independently decoded original graphic, not just be nonblank.
            # Lossy H.264 chroma/resampling may differ slightly by design.
            first_frame = video_pcm[:len(image_decoded)]
            assert len(first_frame) == len(image_decoded)
            if with_blender:
                # A rendered/encoded native CGI shot must actually appear in
                # the final timeline at the authored time, not just be stored.
                last_frame = video_pcm[60 * 320 * 180 * 3:61 * 320 * 180 * 3]
                assert len(last_frame) == len(first_frame)
                assert len(set(last_frame)) > 32 and last_frame != first_frame, (
                    "Rendered Blender 3D was omitted/black/identical in native final")
                assert digest(original_bundle) == original_bundle_sha
                assert digest(original_3d_video) == motion_video_sha
            mean_abs_pixel_error = sum(
                abs(a - b) for a, b in zip(first_frame, image_decoded)
            ) / len(image_decoded)
            assert mean_abs_pixel_error < 25, (
                "The native picture does not resemble the BODY-authored graphic",
                round(mean_abs_pixel_error, 2))
            verification = await invoke(studio, "zx7_verify_native_export", {
                "path": str(export), "expected": {
                    "width": 320, "height": 180,
                    "duration_seconds": 3 if with_blender else 2,
                    "require_audio": True}})
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
                (s.get("currentTimeline") or {}).get("clipCount") == (
                    3 if with_blender else 2))
            actual = await invoke(reopened, "get_timeline", {"includeClips": True})
            assert len(actual["clips"]) == (3 if with_blender else 2)
            if with_blender:
                assert any(abs(c.get("startTime", -1) - 2) < .001
                           and c["type"] == "video" for c in actual["clips"])
                assert digest(original_bundle) == original_bundle_sha
                assert digest(revised_job_path) == revised_job_sha
            assert any(c["assetId"] == timeline["clips"][0]["assetId"]
                       for c in actual["clips"])
            assert digest(document) == saved_sha
            assert digest(original) == image_sha and digest(tone) == tone_sha
        print(("ACTUAL_OWNER_UNIFIED_GRAPH_BLENDER_NATIVE_AV "
               if with_blender else "ACTUAL_OWNER_UNIFIED_GRAPH_NATIVE_AV ") + json.dumps({
            "actual_editable_blender_3d_and_native_revision_preserved": (
                True if with_blender else None),
            "fully_decoded_3d_motion_in_native_movie_with_original_audio": (
                True if with_blender else None),
            "one_real_editor_and_installed_body_gateway": True,
            "actual_original_editable_visual_graph": True,
            "brain_visible_typed_source_authoring_and_readback": True,
            "non_destructive_native_graph_revision_rendered_distinct_pixels": True,
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
    parser.add_argument("--with-blender", action="store_true",
                        help="Also prove genuine editable Blender 4.5+ motion in native Studio")
    args = parser.parse_args()
    asyncio.run(exercise(args.source.resolve(strict=True),
                         args.xvfb_binary, args.display,
                         with_blender=args.with_blender))
