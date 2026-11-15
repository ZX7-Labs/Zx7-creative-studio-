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
from pathlib import Path, PurePosixPath
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
from studio_next.native_editor_project import capture_render_project
from studio_next.native_render_evidence import native_render_binding, DESTINATION_FIELD


def digest(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()


def native_autosave_digests(project: Path) -> set[str]:
    """Read actual source-editor recovery snapshots, not an MCP save receipt."""
    directory = project / "autosave"
    assert directory.is_dir() and not directory.is_symlink(), (
        "Installed native editor did not create its autosave recovery directory")
    snapshots = sorted(directory.glob("project-*.comfystudio"))
    assert snapshots, "Native project save succeeded without a recovery snapshot"
    observed = set()
    for path in snapshots:
        assert path.is_file() and not path.is_symlink(), (
            "Native recovery snapshot must be a regular project file", path)
        parsed = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict) and isinstance(parsed.get("timelines"), list), (
            "Native recovery snapshot is not an editable project", path)
        observed.add(digest(path))
    return observed


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


async def exercise(source: Path, xvfb: str, display: str, *, with_blender=False,
                   with_atomic_range=False, evidence_out=None):
    if with_atomic_range and not with_blender:
        raise ValueError("Atomic cross-engine range acceptance requires real Blender footage")
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
                "-i", "sine=f=440:sample_rate=48000:duration=3" if with_atomic_range else
                 "sine=f=440:sample_rate=48000:duration=2",
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
                    if with_atomic_range:
                        assert "extract_range" in discovered and "extract_range" in identity["fence"], (
                            "Current source-native atomic editor and trusted commit fence required")
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
            initial_snapshots = native_autosave_digests(project)
            assert saved_sha in initial_snapshots, (
                "First committed native project is missing from autosave recovery")
            # A native render must be physically decoded, including sound.
            first_render = await invoke(studio, "export_timeline", {
                "outputPath": str(export), "target": "h264_project",
                "width": 320, "height": 180, "fps": 24,
                "range": "custom", "startSeconds": 0,
                "endSeconds": 3 if with_blender else 2,
                "includeAudio": True,
                "previewOnly": False})
            if with_atomic_range:
                # Reuse exactly the host callback exercised by native Brain
                # sessions; this is a physical source-custody check, NOT a
                # synthetic model decision or professional creative rating.
                render_snapshots = root / "state" / "native-owner-render-bindings"
                render_snapshots.mkdir(mode=0o700)
                first_binding = native_render_binding(str(export), first_render)
                assert first_binding, "Native renderer did not bind real export to actual timeline"
                first_native_sha, first_options_sha = capture_render_project(
                    root / "projects", render_snapshots, first_render, first_binding,
                    (str(project), save["result"]["project"]["modified"]),
                    expected_project=project)
                assert first_native_sha == saved_sha
                assert digest(render_snapshots /
                    (first_binding[DESTINATION_FIELD] + ".comfystudio")) == saved_sha
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
            if with_atomic_range:
                # One real owner project, one host-owned gateway, one native
                # timeline. Do not flatten the Blender or original graph source.
                # Picture: graph [0,2), CGI [2,3); original tone [0,3).
                previous_source = root / "state" / "before-range.comfystudio"
                shutil.copy2(document, previous_source)
                assert digest(previous_source) == saved_sha
                prior = await invoke(studio, "get_timeline", {
                    "includeClips": True, "limit": 1000})
                assert len(prior["clips"]) == 3
                graph_clip = next(c for c in prior["clips"]
                                  if c["assetId"] == timeline["clips"][0]["assetId"])
                cg_clip = next(c for c in prior["clips"]
                               if c["type"] == "video"
                               and abs(c["startTime"] - 2) < 1e-6)
                sound_clip = next(c for c in prior["clips"] if c["type"] == "audio")
                assert abs(sound_clip["duration"] - 3) < 1e-4
                assert abs(cg_clip["duration"] - 1) < 1e-4
                assert graph_clip["startTime"] == 0
                chosen = {"startSeconds": 2.25, "endSeconds": 2.5,
                          "ripple": True}
                preview = await invoke(studio, "extract_range", {
                    **chosen, "previewOnly": True})
                assert preview["previewOnly"] is True
                assert preview["result"]["plan"]["removeCount"] == 2
                assert preview["result"]["plan"]["shiftCount"] == 2
                # Fresh real native project observation is a commit precondition
                # for the same permissioned Brain-visible editor gateway.
                await invoke(studio, "get_project")
                applied = await invoke(studio, "extract_range", {
                    **chosen, "previewOnly": False})
                assert applied["success"] is True
                assert applied["result"]["shiftedClipCount"] == 2
                await read_until(studio, lambda state:
                    (state.get("currentTimeline") or {}).get("clipCount") == 5)
                actual = await invoke(studio, "get_timeline", {
                    "includeClips": True, "limit": 1000})
                assert len(actual["clips"]) == 5
                assert next(c for c in actual["clips"]
                            if c["id"] == graph_clip["id"]) == graph_clip, (
                    "Atomic video/audio edit altered original authored graphics")
                cg_parts = sorted((c for c in actual["clips"]
                                   if c["assetId"] == cg_clip["assetId"]),
                                  key=lambda c: c["startTime"])
                sound_parts = sorted((c for c in actual["clips"]
                                      if c["assetId"] == sound_clip["assetId"]),
                                     key=lambda c: c["startTime"])
                assert len(cg_parts) == len(sound_parts) == 2
                assert abs(cg_parts[0]["startTime"] - 2) < 1e-5
                assert abs(sound_parts[0]["startTime"]) < 1e-5
                for parts, expected_source in ((cg_parts, .5), (sound_parts, 2.5)):
                    assert abs(parts[1]["startTime"] - 2.25) < 1e-5
                    assert abs(parts[1]["trimStart"] - expected_source) < 1e-4
                assert digest(original_bundle) == original_bundle_sha
                assert digest(original_3d_video) == motion_video_sha
                assert digest(original) == image_sha and digest(tone) == tone_sha
                updated_save = await invoke(studio, "save_project", {
                    "previewOnly": False})
                updated_sha = digest(document)
                assert updated_sha != saved_sha
                recovery_snapshots = native_autosave_digests(project)
                assert saved_sha in recovery_snapshots, (
                    "Native edit discarded the previous recoverable source")
                assert updated_sha in recovery_snapshots, (
                    "Revised native document has no recoverable source snapshot")
                assert digest(previous_source) == saved_sha
                persisted = json.loads(document.read_text(encoding="utf-8"))
                assert persisted["modified"] == updated_save["result"]["project"]["modified"]
                assert any(len(t.get("clips") or []) == 5 for t in persisted["timelines"])
                edited_export = root / "outputs" / "graph-cgi-atomic-range.mp4"
                final_render = await invoke(studio, "export_timeline", {
                    "outputPath": str(edited_export), "target": "h264_project",
                    "width": 320, "height": 180, "fps": 24,
                    "range": "custom", "startSeconds": 0,
                    "endSeconds": 2.75, "includeAudio": True,
                    "previewOnly": False})
                final_binding = native_render_binding(str(edited_export), final_render)
                assert final_binding, "Second native render lacks actual project binding"
                revised_native_sha, revised_options_sha = capture_render_project(
                    root / "projects", render_snapshots, final_render, final_binding,
                    (str(project), updated_save["result"]["project"]["modified"]),
                    expected_project=project)
                assert revised_native_sha == updated_sha != first_native_sha
                assert len(first_options_sha) == len(revised_options_sha) == 64
                assert digest(render_snapshots /
                    (final_binding[DESTINATION_FIELD] + ".comfystudio")) == updated_sha
                assert digest(render_snapshots /
                    (first_binding[DESTINATION_FIELD] + ".comfystudio")) == saved_sha
                assert first_binding[DESTINATION_FIELD] != final_binding[DESTINATION_FIELD]
                edited_rgb = edited_pcm = None
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    try:
                        if edited_export.is_file() and edited_export.stat().st_size > 4000:
                            edited_rgb = decode(["ffmpeg", "-nostdin", "-v", "error",
                                "-xerror", "-i", str(edited_export), "-map", "0:v:0",
                                "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
                            edited_pcm = decode(["ffmpeg", "-nostdin", "-v", "error",
                                "-xerror", "-i", str(edited_export), "-map", "0:a:0",
                                "-ac", "1", "-ar", "16000", "-f", "s16le", "-"])
                            break
                    except (subprocess.CalledProcessError, OSError):
                        pass
                    await asyncio.sleep(.35)
                assert edited_rgb is not None and edited_pcm is not None
                assert len(edited_rgb) == 66 * 320 * 180 * 3
                assert len(edited_pcm) >= 2 * 16000 * 2 and any(edited_pcm)
                assert len(video_pcm) == 72 * 320 * 180 * 3
                assert edited_rgb != video_pcm and edited_pcm != audio_pcm
                # Neither presence of clips nor successful RPC means the
                # original graph and CGI actually appear in the final picture.
                frame_bytes = 320 * 180 * 3
                assert sum(abs(a-b) for a, b in zip(
                    edited_rgb[:frame_bytes], image_decoded)) / frame_bytes < 25
                cg_frame = edited_rgb[55*frame_bytes:56*frame_bytes]
                assert len(cg_frame) == frame_bytes
                assert len(set(cg_frame)) > 32 and cg_frame != edited_rgb[:frame_bytes]
                proven = await invoke(studio, "zx7_verify_native_export", {
                    "path": str(edited_export), "expected": {
                        "width": 320, "height": 180,
                        "duration_seconds": 2.75, "require_audio": True}})
                assert proven["physical_export_verified"] is True
                assert proven["native_export_sha256"] == digest(edited_export)
                assert digest(document) == updated_sha
                saved_sha = updated_sha
        # New real Electron session, not one fake in-memory project document.
        async with connected() as (reopened, _):
            await invoke(reopened, "open_project", {
                "projectPath": str(project), "previewOnly": False})
            await read_until(reopened, lambda s:
                (s.get("currentTimeline") or {}).get("clipCount") == (
                    5 if with_atomic_range else 3 if with_blender else 2))
            actual = await invoke(reopened, "get_timeline", {"includeClips": True})
            assert len(actual["clips"]) == (5 if with_atomic_range else 3 if with_blender else 2)
            if with_blender:
                assert any(abs(c.get("startTime", -1) - 2) < .001
                           and c["type"] == "video" for c in actual["clips"])
                assert digest(original_bundle) == original_bundle_sha
                assert digest(revised_job_path) == revised_job_sha
            assert any(c["assetId"] == timeline["clips"][0]["assetId"]
                       for c in actual["clips"])
            assert digest(document) == saved_sha
            assert saved_sha in native_autosave_digests(project), (
                "Fresh native reopen lost its committed recovery snapshot")
            assert digest(original) == image_sha and digest(tone) == tone_sha
        if evidence_out is not None:
            # This is deliberately a *synthetic, scripted technical sample*.
            # Preserve exact source-native materials for external inspection;
            # never call it a Brain-authored film or approved professional art.
            if not (with_atomic_range and with_blender):
                raise ValueError("Synthetic native delivery requires real Blender and atomic A/V")
            destination = Path(evidence_out)
            if not destination.is_absolute() or destination.is_symlink() or destination.exists():
                raise ValueError("Synthetic delivery output must be a fresh absolute directory")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.mkdir(mode=0o700)
            copies = (
                ("first-native-picture-sound.mp4", export),
                ("revised-native-picture-sound.mp4", edited_export),
                ("final-editable-project.comfystudio", document),
                ("first-render-native-project.comfystudio",
                 render_snapshots / (first_binding[DESTINATION_FIELD] + ".comfystudio")),
                ("revised-render-native-project.comfystudio",
                 render_snapshots / (final_binding[DESTINATION_FIELD] + ".comfystudio")),
                ("original-editable-visual-graph.json", plan),
                ("revised-editable-visual-graph.json", revised_plan),
                ("original-graph-source.png", original),
                ("original-sound-source.wav", tone),
                ("original-native-Blender-bundle.zxmotion", original_bundle),
                ("revised-native-Blender-bundle.zxmotion", revised_bundle),
            )
            witnesses = []
            for name, source_file in copies:
                if not source_file.is_file() or source_file.is_symlink():
                    raise AssertionError("Synthetic source/native evidence is unavailable", name)
                replica = destination / name
                shutil.copyfile(source_file, replica)
                current = digest(source_file)
                assert digest(replica) == current, (
                    "Archived synthetic evidence differs from actual verified source", name)
                witnesses.append({
                    "file": name, "sha256": current, "bytes": replica.stat().st_size})
            # Independent relocation must retain the native editor's complete
            # referenced media closure, not only a JSON .comfystudio receipt.
            # A project with missing asset blobs is NOT portable/editable
            # outside the temporary CI installation.
            portable = destination / "portable-native-project"
            portable.mkdir(mode=0o700)
            native_document = json.loads(document.read_text(encoding="utf-8"))
            media = native_document.get("assets")
            if not isinstance(media, list) or len(media) < 3:
                raise AssertionError("Native deliverable has no real media asset inventory")
            source_ids = set()
            original_media_sha = {
                "original-art.png": image_sha,
                "original-tone.wav": tone_sha,
                "native-3d-original.mp4": motion_video_sha,
            }
            original_media_seen = set()
            for asset in media:
                if not isinstance(asset, dict):
                    raise AssertionError("Native media inventory has invalid source")
                identity, named = asset.get("id"), asset.get("path")
                if (not isinstance(identity, str) or not identity or
                        identity in source_ids or not isinstance(named, str) or
                        not named or "\\" in named or "\x00" in named or
                        any(bit in ("", ".", "..") for bit in named.split("/"))):
                    raise AssertionError("Native media source identity/path unsafe")
                source_ids.add(identity)
                relative = PurePosixPath(named)
                if (relative.is_absolute() or len(relative.parts) < 3 or
                        relative.parts[0] != "assets"):
                    raise AssertionError("Native source escapes owned relative asset directory")
                original_asset = project.joinpath(*relative.parts)
                if (not original_asset.is_file() or
                        any(original_asset.parents[i].is_symlink()
                            for i in range(len(relative.parts))) or
                        original_asset.is_symlink() or
                        not original_asset.resolve(strict=True).is_relative_to(
                            project.resolve(strict=True))):
                    raise AssertionError("Native media source cannot be safely relocated")
                copied = portable.joinpath(*relative.parts)
                copied.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                shutil.copyfile(original_asset, copied)
                actual_sha = digest(original_asset)
                original_name = asset.get("name")
                if (not isinstance(original_name, str) or
                        original_name not in original_media_sha or
                        original_name in original_media_seen or
                        actual_sha != original_media_sha[original_name]):
                    raise AssertionError("Native imported copy differs from owner-authored source")
                original_media_seen.add(original_name)
                if digest(copied) != actual_sha or not copied.stat().st_size:
                    raise AssertionError("Portable native asset is missing or mutated")
                witnesses.append({
                    "file": copied.relative_to(destination).as_posix(),
                    "sha256": actual_sha, "bytes": copied.stat().st_size})
            assert original_media_seen == set(original_media_sha)
            if not all(
                    isinstance(clip, dict) and clip.get("assetId") in source_ids
                    for timeline in native_document.get("timelines", [])
                    for clip in timeline.get("clips", [])):
                raise AssertionError("Saved native timeline refers to missing media identity")
            portable_doc = portable / "project.comfystudio"
            shutil.copyfile(document, portable_doc)
            assert digest(portable_doc) == updated_sha
            witnesses.append({
                "file": portable_doc.relative_to(destination).as_posix(),
                "sha256": updated_sha, "bytes": portable_doc.stat().st_size})
            # saved_sha now refers to the *final* revision after fresh
            # reopen; the first real render keeps its own immutable receipt.
            assert witnesses[3]["sha256"] == first_native_sha
            assert first_native_sha != updated_sha
            assert witnesses[4]["sha256"] == updated_sha
            assert witnesses[2]["sha256"] == updated_sha
            # Actual relocation test: do not confuse a SHA-complete archive
            # with a working native project on a fresh editor process.
            relocated = root / "projects" / "relocated-from-physical-evidence"
            assert not relocated.exists()
            shutil.copytree(portable, relocated, symlinks=False)
            assert digest(relocated / "project.comfystudio") == updated_sha
            for asset in media:
                relative = PurePosixPath(asset["path"])
                assert digest(relocated.joinpath(*relative.parts)) == digest(
                    portable.joinpath(*relative.parts))
            relocated_movie = root / "outputs" / "independently-reopened-native.mp4"
            async with connected() as (relocated_editor, _):
                reopened = await invoke(relocated_editor, "open_project", {
                    "projectPath": str(relocated), "previewOnly": False})
                assert reopened is not None
                recovered = await read_until(relocated_editor, lambda state:
                    state.get("project", {}).get("path") == str(relocated) and
                    state.get("assetCount") == len(media) and
                    (state.get("currentTimeline") or {}).get("clipCount") == 5)
                assert recovered["project"]["path"] == str(relocated)
                recovered_timeline = await invoke(relocated_editor, "get_timeline", {
                    "includeClips": True, "limit": 1000})
                assert len(recovered_timeline["clips"]) == 5
                assert {clip["assetId"] for clip in recovered_timeline["clips"]} == source_ids
                await invoke(relocated_editor, "get_project")
                await invoke(relocated_editor, "export_timeline", {
                    "outputPath": str(relocated_movie), "target": "h264_project",
                    "width": 320, "height": 180, "fps": 24,
                    "range": "custom", "startSeconds": 0,
                    "endSeconds": 2.75, "includeAudio": True,
                    "previewOnly": False})
                independent_rgb = independent_pcm = None
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    try:
                        if relocated_movie.is_file() and relocated_movie.stat().st_size > 4000:
                            independent_rgb = decode(["ffmpeg", "-nostdin", "-v", "error",
                                "-xerror", "-i", str(relocated_movie), "-map", "0:v:0",
                                "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
                            independent_pcm = decode(["ffmpeg", "-nostdin", "-v", "error",
                                "-xerror", "-i", str(relocated_movie), "-map", "0:a:0",
                                "-ac", "1", "-ar", "16000", "-f", "s16le", "-"])
                            break
                    except (subprocess.CalledProcessError, OSError):
                        pass
                    await asyncio.sleep(.35)
                assert independent_rgb is not None and independent_pcm is not None
                assert independent_rgb == edited_rgb, (
                    "Relocated native project changed actual decoded picture")
                assert independent_pcm == edited_pcm and any(independent_pcm), (
                    "Relocated native project changed or lost original sound")
                certified = await invoke(relocated_editor, "zx7_verify_native_export", {
                    "path": str(relocated_movie), "expected": {
                        "width": 320, "height": 180,
                        "duration_seconds": 2.75, "require_audio": True}})
                assert certified["physical_export_verified"] is True
                assert certified["native_export_sha256"] == digest(relocated_movie)
            assert digest(portable_doc) == updated_sha
            assert digest(document) == updated_sha
            relocated_copy = destination / "relocated-native-picture-sound.mp4"
            shutil.copyfile(relocated_movie, relocated_copy)
            assert digest(relocated_copy) == digest(relocated_movie)
            witnesses.append({
                "file": relocated_copy.name, "sha256": digest(relocated_copy),
                "bytes": relocated_copy.stat().st_size})
            manifest = {
                "schema": 2,
                "kind": "zx7_synthetic_native_blender_graph_av_revision",
                "synthetic_only": True,
                "scripted_engine_decisions_not_neural": True,
                "native_editor_source_identity_verified": True,
                "first_and_revised_render_snapshots_sha_verified": True,
                "physical_picture_and_non_silent_audio_decoded": True,
                "editable_native_project_reopened": True,
                "portable_native_project_source_closure_verified": True,
                "portable_native_project_reopened_after_extraction": True,
                "relocated_export_matches_revision_picture_and_audio": True,
                "genuine_model_artistry_verified": False,
                "independent_professional_review": False,
                "files": witnesses,
            }
            (destination / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            assert len(list(destination.iterdir())) == len(copies) + 3
        print(("ACTUAL_OWNER_UNIFIED_GRAPH_BLENDER_ATOMIC_AV "
               if with_atomic_range else "ACTUAL_OWNER_UNIFIED_GRAPH_BLENDER_NATIVE_AV "
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
            "fully_decoded_native_video_frame_count": (
                66 if with_atomic_range else 72 if with_blender else 48),
            "original_sound_independently_decoded": True,
            "native_atomic_cross_engine_range_preserved_sources": (
                True if with_atomic_range else None),
            "native_decoded_picture_matches_body_authored_pixels": True,
            "native_export_source_bound_verification": True,
            "two_actual_render_time_saved_native_snapshots_bound": (
                True if with_atomic_range else None),
            "genuine_model_artistry_or_professional_VFX_approved": False,
        }, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--xvfb-binary", required=True)
    parser.add_argument("--display", required=True)
    parser.add_argument("--with-blender", action="store_true",
                        help="Also prove genuine editable Blender 4.5+ motion in native Studio")
    parser.add_argument("--with-atomic-range", action="store_true",
                        help="Cross-engine source-native ripple, double export and editable reopen")
    parser.add_argument("--evidence-out", type=Path,
                        help="Save only this synthetic physical native sample for external inspection")
    args = parser.parse_args()
    asyncio.run(exercise(args.source.resolve(strict=True),
                         args.xvfb_binary, args.display,
                         with_blender=args.with_blender,
                         with_atomic_range=args.with_atomic_range,
                         evidence_out=args.evidence_out))
