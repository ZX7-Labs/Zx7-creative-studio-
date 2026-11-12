"""Bounded real Velorn MCP object inventory for host-only native write admission.

This is a pinned-source adapter, not a universal creative language or an
artistic decision router. It consumes the *actual installed* editor's
get_project/get_timeline/get_assets observations; never model text, a cache,
or guessed IDs. Human edits can still race after this preflight: installed
native revision/preview semantics remain a separate last-mile invariant.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from .native_editor_source_pin import (
    _source_matches_pinned_electron_mcp,
    _source_matches_pinned_native_collaboration,
    _source_matches_pinned_native_scene,
)

_MAX_TEXT = 6_000_000
_MAX_ITEMS = 1_000
_READ_NAMES = ("get_project", "get_timeline", "get_assets")

# Exact parameter locations in pinned upstream electron/mcpServer.js.
# The model still chooses the editor operation AND all artistic parameters.
# Only supplied IDs of existing assets/clips/tracks are verified.
_NATIVE_REFERENCES = {
    "add_asset_to_timeline": {"/assetId": "assets", "/trackId": "tracks"},
    "add_assets_to_timeline": {
        "/assets/*/assetId": "assets", "/assetIds/*": "assets",
        "/trackId": "tracks"},
    "replace_clip_with_asset": {
        "/clipId": "clips", "/targetClipId": "clips",
        "/assetId": "assets", "/replacementAssetId": "assets"},
    "add_text_clip": {"/trackId": "tracks"},
    "update_text_clip": {"/clipId": "clips", "/trackId": "tracks"},
    "add_shape_clip": {"/trackId": "tracks"},
    "update_shape_clip": {"/clipId": "clips", "/trackId": "tracks"},
    "add_adjustment_clip": {"/trackId": "tracks"},
    "duplicate_clip": {"/clipId": "clips", "/trackId": "tracks"},
    "move_clips": {
        "/clipId": "clips", "/trackId": "tracks",
        "/clips/*/clipId": "clips", "/clips/*/trackId": "tracks"},
    "trim_clips": {"/clipId": "clips", "/clips/*/clipId": "clips"},
    "delete_clips": {"/clipId": "clips", "/clipIds/*": "clips"},
    "add_transition": {
        "/clipAId": "clips", "/clipBId": "clips", "/clipId": "clips"},
    "update_track": {"/trackId": "tracks"},
    "remove_track": {"/trackId": "tracks"},
    "set_clip_audio": {"/clipId": "clips", "/clipIds/*": "clips"},
    "set_clip_mask": {
        "/clipId": "clips", "/clipIds/*": "clips",
        "/trackId": "tracks", "/maskAssetId": "assets"},
    "set_clips_enabled": {"/clipIds/*": "clips"},
    "set_clip_keyframes": {"/clipId": "clips"},
    "set_clip_style": {"/clipId": "clips", "/clipIds/*": "clips"},
}


def _value(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _read_json_result(result):
    """Accept one bounded valid JSON MCP text block with a non-error status."""
    statuses = [_value(result, name) for name in ("is_error", "isError")
                if _value(result, name) is not None]
    if not statuses or any(type(v) is not bool or v for v in statuses):
        raise ValueError("native_identity_read_failed")
    content = _value(result, "content")
    if (not isinstance(content, (list, tuple)) or len(content) != 1 or
            _value(content[0], "type") != "text"):
        raise ValueError("native_identity_read_malformed")
    payload = _value(content[0], "text")
    if not isinstance(payload, str) or not 1 <= len(payload) <= _MAX_TEXT:
        raise ValueError("native_identity_read_oversize")
    try:
        obj = json.loads(payload, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("native_identity_read_malformed") from exc
    if not isinstance(obj, dict):
        raise ValueError("native_identity_read_malformed")
    return obj


def _ids(rows):
    if not isinstance(rows, list) or len(rows) > _MAX_ITEMS:
        raise ValueError("native_identity_read_incomplete")
    result = []
    for row in rows:
        value = row.get("id") if isinstance(row, dict) else None
        if not isinstance(value, str) or not 0 < len(value) <= 240:
            raise ValueError("native_identity_read_malformed")
        result.append(value)
    if len(result) != len(set(result)):
        raise ValueError("native_identity_read_malformed")
    return result


def _project_state(obj):
    project, timeline = obj.get("project"), obj.get("currentTimeline")
    if not isinstance(project, dict) or not isinstance(timeline, dict):
        raise ValueError("native_identity_project_unavailable")
    # Verified upstream src/services/mcpSnapshot.js supplies NO project.id.
    # Its authoritative currentTimelineId must match get_project's timeline,
    # and the MCP bridge must positively attest that a project is open.
    mcp = obj.get("mcp")
    if (not isinstance(mcp, dict) or mcp.get("hasProject") is not True or
            not isinstance(timeline.get("id"), str) or
            not isinstance(project.get("currentTimelineId"), str) or
            not project["currentTimelineId"] or
            project["currentTimelineId"] != timeline["id"] or
            not isinstance(project.get("name"), str)):
        raise ValueError("native_identity_project_unavailable")
    # Electron's get_project reports a snapshot.generatedAt when available,
    # but the actual bridge also exposes host-owned mcp.lastSnapshotAt.
    # A null producer-generated timestamp must not erase real project state.
    marker = obj.get("generatedAt")
    if not isinstance(marker, str) or not marker:
        mcp = obj.get("mcp")
        marker = mcp.get("lastSnapshotAt") if isinstance(mcp, dict) else None
    if not isinstance(marker, str) or not marker:
        raise ValueError("native_identity_project_unavailable")
    counts = (timeline.get("trackCount"), timeline.get("clipCount"),
              obj.get("assetCount"))
    if any(type(x) is not int or x < 0 for x in counts):
        raise ValueError("native_identity_read_malformed")
    # Project path is potentially private. Digest the stable source-owned
    # identity material; no original path leaves this trusted reader.
    source_identity = {
        "project_name": project["name"],
        "project_path": project.get("path"),
        "project_created": project.get("created"),
        "current_timeline_id": timeline["id"],
    }
    try:
        identity = hashlib.sha256(json.dumps(
            source_identity, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()
    except (TypeError, ValueError, RecursionError):
        raise ValueError("native_identity_project_unavailable") from None
    return (identity, timeline["id"], marker, *counts)


class NativeEditorIdentityReader:
    """One project-source read transaction per proposed native write.

    The caller supplies an already connected, host-owned MCP session. Optional
    reserve_read is a trusted reservation callback; in real native sessions it
    charges all internal observations to the shared per-session call budget.
    """

    def __init__(self, session, grants, *, reserve_read=None,
                 require_live_revision=False):
        if (not callable(getattr(session, "call_tool", None)) or
                not isinstance(grants, Mapping) or
                any(grants.get(name) != "read" for name in _READ_NAMES) or
                (reserve_read is not None and not callable(reserve_read))):
            raise ValueError("native_identity_requires_three_granted_read_tools")
        self._session = session
        self._reserve = reserve_read
        self._require_live_revision = require_live_revision

    async def _read(self, name, args):
        if self._reserve is not None:
            self._reserve()
        return _read_json_result(await self._session.call_tool(name, args))

    async def __call__(self):
        before_object = await self._read("get_project", {})
        before = _project_state(before_object)
        timeline = await self._read(
            "get_timeline", {"includeClips": True, "limit": _MAX_ITEMS})
        assets = await self._read("get_assets", {"limit": _MAX_ITEMS})
        after_object = await self._read("get_project", {})
        after = _project_state(after_object)
        # A renderer changed source/head during observation: never authorize
        # the caller's old object references on a mixed project snapshot.
        if before != after:
            raise ValueError("native_identity_project_changed_during_read")
        live_revision = None
        if self._require_live_revision:
            first = before_object.get("zx7NativeRevision")
            last = after_object.get("zx7NativeRevision")
            if (not isinstance(first, str) or
                    not 38 <= len(first) <= 80 or
                    not isinstance(last, str) or
                    not 38 <= len(last) <= 80 or
                    any(ord(ch) < 33 or ord(ch) > 126 for ch in first + last)):
                raise ValueError("native_identity_live_revision_unavailable")
            if first != last:
                raise ValueError("native_identity_project_changed_during_read")
            live_revision = last
        if timeline.get("clipLimitApplied") is not False:
            raise ValueError("native_identity_read_incomplete")
        if assets.get("limitApplied") is not False:
            raise ValueError("native_identity_read_incomplete")
        tracks = _ids(timeline.get("tracks"))
        clips = _ids(timeline.get("clips"))
        asset_ids = _ids(assets.get("assets"))
        if (before[1] != timeline.get("id") or
                (len(tracks), len(clips), len(asset_ids)) != before[3:] or
                type(assets.get("count")) is not int or
                assets["count"] != len(asset_ids)):
            raise ValueError("native_identity_source_counts_changed")
        inventory = {
            "tracks": {"ids": tracks, "complete": True},
            "clips": {"ids": clips, "complete": True},
            "assets": {"ids": asset_ids, "complete": True},
        }
        if live_revision is not None:
            inventory["__zx7_live_revision"] = live_revision
        return inventory


def pinned_native_editor_identity_policy(source: Path, grants, session, *,
                                         reserve_read=None):
    """Host-only opt-in; clean source pin and full read grants are mandatory.

    Unsupported/modified source means no claims of pin-verified ID checking,
    rather than pretending an arbitrary fork uses this exact native contract.
    """
    if not isinstance(source, Path) or not isinstance(grants, Mapping):
        raise ValueError("native_identity_requires_host_source_and_grants")
    candidates = {name: dict(rules) for name, rules in _NATIVE_REFERENCES.items()
                  if grants.get(name) == "write"}
    if not candidates:
        return None
    # The host must explicitly grant every required inventory read. A partial
    # read catalog cannot be silently promoted or advertised as validated.
    # Preserve the existing editor control path and report preflight disabled.
    if any(grants.get(name) != "read" for name in _READ_NAMES):
        return None
    if not _source_matches_pinned_electron_mcp(source):
        return None
    source_fenced = _source_matches_pinned_native_collaboration(source)
    scene_fenced = (_source_matches_pinned_native_scene(source)
                    if source_fenced else False)
    fenced_names = (
        (["update_text_clip"] if source_fenced else []) +
        (["update_shape_clip", "set_clip_keyframes"] if scene_fenced else [])
    )
    fenced_names = [name for name in fenced_names
                    if grants.get(name) == "write"]
    reader = NativeEditorIdentityReader(
        session, grants, reserve_read=reserve_read,
        require_live_revision=bool(fenced_names))
    policy = {"reader": reader, "rules": candidates}
    if fenced_names:
        # The model chooses creative parameters. Only source-vetted actions
        # get a hidden host-owned revision, checked at the synchronous writer.
        policy["fence"] = {name: {
            "inventory_key": "__zx7_live_revision",
            "argument_key": "__zx7ExpectedRevision",
            "rejected_code": "ZX7_STALE_NATIVE_REVISION",
        } for name in fenced_names}
    return policy
