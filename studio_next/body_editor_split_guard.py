"""Conservative, source-introspected gate against destructive native razor edits.

The pinned native editor currently creates the right-hand clip without copying
general effects or keyframes. This gate protects the BODY MCP path until real,
lossless editor-native split behavior is proven. A blocked creative operation
remains available to redesign/fix; it must not silently degrade the artwork.

This is not an OS sandbox and does not guard a separately accessed raw native
MCP endpoint or edits directly inside the host GUI.
"""
from __future__ import annotations

import json
import math

from .body_editor_client import EditorAccessError, EditorProtocolError, _load_json


# This is an inventory of reviewed plain source-clip fields from the pinned
# native application. Any new creative field on an upstream revision must
# be assessed rather than silently discarded on the right of a split.
_PLAIN_FIELDS = frozenset({
    "id", "trackId", "assetId", "name", "startTime", "duration",
    "sourceDuration", "trimStart", "trimEnd", "sourceFps",
    "timelineFps", "sourceTimeScale", "speed", "reverse",
    "frameSampling", "color", "type", "enabled",
    "compositeLowerLayers", "url", "thumbnail", "metadata",
    "transform", "labelColor", "gainDb", "fadeIn", "fadeOut",
    # Real pinned inspect_clip summaries include these; unknown fields remain
    # forbidden. These known fields are validated for authored state below.
    "text", "lockMode", "syncLock",
})
_NONLOSSY_SOURCE_TYPES = frozenset({"video", "audio"})


def _native_json(result: dict, label: str) -> dict:
    """Require one complete JSON source observation, never a preview/truncation."""
    if not isinstance(result, dict) or result.get("isError"):
        raise EditorAccessError(label + " did not return trusted native state")
    blocks = result.get("content")
    if not isinstance(blocks, list):
        raise EditorProtocolError(label + " returned malformed MCP content")
    texts = [block["text"] for block in blocks
             if isinstance(block, dict) and block.get("type") == "text"
             and isinstance(block.get("text"), str)]
    if len(texts) != 1:
        raise EditorAccessError(label + " requires one full native JSON observation")
    try:
        value = _load_json(texts[0])
    except (ValueError, TypeError, RecursionError) as exc:
        raise EditorAccessError(label + " had no valid native JSON state") from exc
    if not isinstance(value, dict) or value.get("truncated") or value.get("success") is False:
        raise EditorAccessError(label + " was truncated or unsuccessful")
    return value


def _finite_time(value) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise EditorAccessError("A split requires a finite nonnegative explicit time")
    return float(value)


def _unsafe_features(clip: dict) -> list[str]:
    """Conservatively identify state the pinned razor does NOT safely clone.

    Do not confuse a default clip transform (which the native razor copies)
    with animated/unknown effect state (which it does not). Reject less common
    media types and undocumented metadata instead of pretending to preserve.
    """
    if not isinstance(clip, dict) or not isinstance(clip.get("id"), str):
        raise EditorAccessError("Native clip inspection returned no clip identity")
    reasons = []
    if clip.get("type") not in _NONLOSSY_SOURCE_TYPES:
        reasons.append("non-source clip type")
    if clip.get("text") not in (None, ""):
        reasons.append("authored clip text")
    if clip.get("lockMode") not in (None, "", False):
        reasons.append("clip lock mode")
    if clip.get("syncLock") not in (None, False, [], {}):
        reasons.append("clip synchronization state")
    extra = set(clip) - _PLAIN_FIELDS
    if extra:
        reasons.append("unknown or enhanced fields: " + ", ".join(sorted(extra)[:15]))
    if clip.get("speed", 1) != 1 or clip.get("reverse", False) is not False:
        reasons.append("retimed or reversed source")
    if clip.get("sourceTimeScale", 1) != 1 or clip.get("frameSampling", "frame") != "frame":
        reasons.append("non-default source sampling/time scale")
    if clip.get("compositeLowerLayers", "auto") != "auto":
        reasons.append("non-default compositing behavior")
    if clip.get("type") == "audio" and any(clip.get(k, 0) != 0
                                          for k in ("gainDb", "fadeIn", "fadeOut")):
        reasons.append("authored audio dynamics")
    metadata = clip.get("metadata")
    if metadata not in (None, {}) and (
            not isinstance(metadata, dict) or
            set(metadata) - {"addedByMcp", "addedAt", "sourceTool"}):
        reasons.append("unreviewed clip metadata")
    if "transform" in clip and clip["transform"] is not None and not isinstance(clip["transform"], dict):
        reasons.append("uninspectable transform")
    return reasons


def preflight_non_destructive_native_split(client, arguments: dict, *,
                                           allowed_access) -> dict:
    """Refuse an editor split unless selected source clips are plainly safe.

    Called within the existing single-project write lock. Read dependencies
    and exact full clip inspection must be host-granted. Explicit target IDs
    and the editor's supported automatic time-based targeting are both checked.
    A clip whose attributes are unknown is not assumed lossless.
    """
    if "read" not in allowed_access or client.allowed_tools.get("inspect_clip") != "read":
        raise EditorAccessError("Native split requires host-granted read inspection; no unsafe fallback")
    if not isinstance(arguments, dict):
        raise EditorAccessError("Native split requires object arguments")
    time_value = arguments.get("timeSeconds", arguments.get("time"))
    if time_value is None:
        raise EditorAccessError("Explicit split time needed for non-destructive target inspection")
    at = _finite_time(time_value)
    if arguments.get("clipId") is not None:
        ids = [arguments["clipId"]]
    elif arguments.get("clipIds") is not None:
        ids = arguments["clipIds"]
    else:
        # Implicit targeting at the playhead requires the WHOLE timeline;
        # never guess which clips a native razor might modify.
        if client.allowed_tools.get("get_timeline") != "read":
            raise EditorAccessError("Automatic split targets require host-granted full timeline inspection")
        timeline_data = _native_json(client.call(
            "get_timeline", {"includeClips": True, "limit": 1000},
            allowed_access=allowed_access), "get_timeline")
        timeline = (timeline_data if isinstance(timeline_data.get("clips"), list)
                    else timeline_data.get("timeline"))
        if (not isinstance(timeline, dict) or
                not isinstance(timeline.get("clips"), list) or
                timeline.get("clipLimitApplied") is not False):
            raise EditorAccessError("Native split requires a complete untruncated timeline")
        clips = timeline["clips"]
        if not all(isinstance(c, dict) and isinstance(c.get("id"), str) and
                   type(c.get("startTime")) in (int, float) and
                   type(c.get("duration")) in (int, float) and
                   math.isfinite(c["startTime"]) and
                   math.isfinite(c["duration"]) for c in clips):
            raise EditorAccessError("Native timeline has incomplete clip references")
        if len({clip["id"] for clip in clips}) != len(clips):
            raise EditorAccessError("Native timeline has ambiguous duplicate clip identity")
        ids = [clip["id"] for clip in clips if
               clip["startTime"] < at < clip["startTime"] + clip["duration"]]
    if (not isinstance(ids, list) or not ids or len(ids) > 1000 or
            any(not isinstance(i, str) or not i for i in ids) or
            len(set(ids)) != len(ids)):
        raise EditorAccessError("Native split targets must resolve uniquely")
    checked = []
    for identity in ids:
        try:
            detail = _native_json(client.call(
                "inspect_clip", {"clipId": identity}, allowed_access=allowed_access), "inspect_clip")
        except (ValueError, KeyError, StopIteration) as exc:
            raise EditorAccessError("Native split target does not exist or cannot be inspected") from exc
        clip = detail.get("clip", detail)
        if not isinstance(clip, dict) or clip.get("id") != identity:
            raise EditorAccessError("Native split inspection changed clip identity")
        start, duration = clip.get("startTime"), clip.get("duration")
        if (type(start) not in (int, float) or type(duration) not in (int, float) or
                not math.isfinite(start) or not math.isfinite(duration) or
                not start < at < start + duration):
            raise EditorAccessError("Native split time is not strictly inside the inspected clip")
        reasons = _unsafe_features(clip)
        if reasons:
            raise EditorAccessError(
                "Native split refused to discard editable clip state on " + identity +
                ": " + "; ".join(reasons) +
                ". Preserve this revision and use a loss-aware native split implementation.")
        checked.append(identity)
    return {"preflighted_plain_source_clips": checked,
            "native_producer_was_not_modified": True,
            "professional_lossless_split_proven": False}
