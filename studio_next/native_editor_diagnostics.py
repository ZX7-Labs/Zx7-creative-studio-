"""Bounded facts from the pinned editor's live timeline, never art direction.

Invisible clips, empty lanes and silence may be intentional. These diagnostics
do not block exports, modify a project, or certify rendered/creative quality.
"""
from __future__ import annotations

import copy
import math
import os
from pathlib import Path
import subprocess

from .body_editor_client import _load_json
from .native_editor_source_pin import _source_matches_pinned_electron_mcp

CONTENT_DIAGNOSTICS_TOOL = "zx7_inspect_native_content"
_SEMANTIC_SOURCE_PATHS = (
    "electron/mcpServer.js", "src/services/mcpActions.js",
    "src/stores/timelineStore.js", "src/services/mcpSnapshot.js",
    "src/utils/textAnimationPresets.js", "src/utils/keyframes.js",
    "src/utils/effects.js", "src/services/exporter.js",
)
_VISUAL_TYPES = frozenset({"video", "image", "text", "shape", "captions"})


def native_content_diagnostics_source_verified(source: Path) -> bool:
    """Attest the pinned HEAD and every source file used for these semantics."""
    if not isinstance(source, Path) or not _source_matches_pinned_electron_mcp(source):
        return False
    env = {k: v for k, v in os.environ.items() if k not in (
        "NVIDIA_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
    try:
        clean = subprocess.run(
            ["git", "-C", str(source.resolve(strict=True)), "diff", "--quiet",
             "HEAD", "--", *_SEMANTIC_SOURCE_PATHS],
            capture_output=True, timeout=5, env=env)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return False
    return clean.returncode == 0


def describe_native_text_semantics(name: str, schema: dict) -> dict:
    """Enrich descriptions only; caller has independently attested the source.

    Keep numeric ranges/defaults, parameters and authored values unchanged.
    """
    if name not in ("add_text_clip", "update_text_clip"):
        return schema
    try:
        transform = schema["properties"]["transform"]
        opacity = transform["properties"]["opacity"]
        preset = schema["properties"]["animationPreset"]
        valid = (transform.get("type") == "object" and opacity.get("type") == "number"
                 and preset.get("type") == "string" and "fade" in preset.get("enum", []))
    except (KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise ValueError("Pinned native text schema differs from attested semantics")
    result = copy.deepcopy(schema)
    props = result["properties"]
    props["transform"]["properties"]["opacity"]["description"] = (
        "Native opacity uses percent: 0 transparent, 100 opaque. When applying "
        "a title animation preset, this base opacity is the steady-state target, "
        "not the fade's initial value. Base opacity 0 with fade produces only "
        "zero-opacity preset keyframes. Explicit opacity keyframes override the base.")
    props["animationPreset"]["description"] = (
        str(preset.get("description", "")) + " The preset is baked after transform "
        "updates and before explicit keyframes. It animates toward the base "
        "transform values, including opacity; it does not choose a new opaque target.")
    return result


def _identity(value):
    if (type(value) is not str or not 1 <= len(value) <= 128 or
            any(ord(c) < 32 for c in value)):
        raise ValueError("Native content snapshot has an invalid object identity")
    return value


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _opacity_envelope_zero(clip):
    transform = clip.get("transform")
    keyframes = clip.get("keyframes")
    transform = {} if transform is None else transform
    keyframes = {} if keyframes is None else keyframes
    if type(transform) is not dict or type(keyframes) is not dict:
        raise ValueError("Native content snapshot has malformed animation data")
    frames = keyframes.get("opacity", [])
    if type(frames) is not list or len(frames) > 4096:
        raise ValueError("Native content opacity curve is malformed or oversized")
    if frames:
        for frame in frames:
            if (type(frame) is not dict or not _number(frame.get("time")) or
                    not _number(frame.get("value"))):
                raise ValueError("Native content opacity keyframe is malformed")
        # Native interpolation holds first/last values outside the curve.
        # All-zero endpoints remain zero for every supported interpolation.
        return all(frame["value"] == 0 for frame in frames)
    opacity = transform.get("opacity", 100)
    if not _number(opacity):
        raise ValueError("Native content opacity value is malformed")
    return opacity == 0


def inspect_native_content(result: dict, *, warning_limit: int = 16) -> dict:
    """Inspect an actual get_timeline receipt without returning names/paths/text.

    Missing or truncated clip data cannot establish that audio clips are absent.
    An audio track is not proof a video asset has, or lacks, an audible stream.
    """
    if type(warning_limit) is not int or not 1 <= warning_limit <= 32:
        raise ValueError("Content warning limit must be an integer from 1 to 32")
    if type(result) is not dict:
        raise ValueError("Native content requires an actual MCP result")
    if any(type(result[k]) is not bool or result[k] for k in ("isError", "is_error") if k in result):
        raise ValueError("Native content observation failed or has malformed status")
    blocks = result.get("content")
    if (type(blocks) is not list or len(blocks) != 1 or type(blocks[0]) is not dict or
            blocks[0].get("type") != "text" or type(blocks[0].get("text")) is not str or
            len(blocks[0]["text"].encode("utf-8")) > 2 * 1024 * 1024):
        raise ValueError("Native content requires one bounded timeline JSON receipt")
    try:
        timeline = _load_json(blocks[0]["text"])
    except (ValueError, RecursionError) as exc:
        raise ValueError("Native content timeline is not finite unambiguous JSON") from exc
    if type(timeline) is not dict:
        raise ValueError("Native content timeline is not an object")
    timeline_id = _identity(timeline.get("id"))
    tracks, clips = timeline.get("tracks"), timeline.get("clips")
    if (type(tracks) is not list or len(tracks) > 256 or type(clips) is not list or
            len(clips) > 1000 or type(timeline.get("clipLimitApplied")) is not bool):
        raise ValueError("Native content timeline has missing or oversized collections")
    track_by_id = {}
    for track in tracks:
        if type(track) is not dict or track.get("type") not in ("video", "audio"):
            raise ValueError("Native content track is malformed")
        tid = _identity(track.get("id"))
        if tid in track_by_id or any(type(track[k]) is not bool for k in
                                    ("muted", "visible", "solo") if k in track):
            raise ValueError("Native content track has ambiguous identity or flags")
        track_by_id[tid] = track
    warnings, counts = [], {}
    def warn(code, **identities):
        counts[code] = counts.get(code, 0) + 1
        if len(warnings) < warning_limit:
            warnings.append({"code": code, **identities})
    audio_tracks = [t for t in tracks if t["type"] == "audio"]
    for track in audio_tracks:
        if track.get("muted") is True:
            warn("audio_track_muted", track_id=track["id"])
    if not audio_tracks:
        warn("no_audio_tracks")
    clip_ids = set()
    audio_clip_count = 0
    for clip in clips:
        if type(clip) is not dict or type(clip.get("type")) is not str:
            raise ValueError("Native content clip is malformed")
        cid, tid = _identity(clip.get("id")), _identity(clip.get("trackId"))
        if cid in clip_ids or tid not in track_by_id or (
                "enabled" in clip and type(clip["enabled"]) is not bool):
            raise ValueError("Native content clip has ambiguous identity, track or flags")
        clip_ids.add(cid)
        if clip["type"] == "audio":
            audio_clip_count += 1
        if clip["type"] not in _VISUAL_TYPES:
            continue
        if clip.get("enabled") is False:
            warn("visual_clip_disabled", clip_id=cid)
        if track_by_id[tid].get("visible") is False:
            warn("visual_track_hidden", clip_id=cid, track_id=tid)
        if _opacity_envelope_zero(clip):
            warn("opacity_envelope_zero", clip_id=cid)
    if not timeline["clipLimitApplied"] and audio_clip_count == 0:
        warn("no_audio_type_clips_embedded_video_audio_unassessed")
    return {"schema": 1, "timeline_id": timeline_id, "read_only": True,
            "native_state_only": True, "clip_inventory_complete": not timeline["clipLimitApplied"],
            "inspected_clip_count": len(clips), "audio_track_count": len(audio_tracks),
            "audio_type_clip_count": audio_clip_count, "warning_counts": counts,
            "warnings": warnings, "warnings_truncated": sum(counts.values()) > len(warnings),
            "automatic_repairs": False, "physical_output_inspected": False,
            "audio_semantically_heard": False, "artistic_quality_approved": False}
