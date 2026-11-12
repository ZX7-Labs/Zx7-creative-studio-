"""Host-attested, bounded native revision evidence exposed as READ MCP tools.

The creative Brain chooses whether to inspect. Registration is **host-only**
after an actual saved-render capture by the existing native control loop.
The model never supplies filesystem paths, changes native sources, merges
candidates, or gains permission from retrieved content. The real editor and
CapabilityGateway remain the sole native state/write authorities.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat

from .native_creative_revision import (
    NativeRevisionReviewError, compare_native_revisions,
    load_native_revision, review_native_collaboration,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_SNAPSHOTS = 16
_MAX_CALLS = 32
_MAX_ITEMS_PER_PAGE = 20
_MAX_FIELD_PATHS = 24
_MAX_TOOL_RESPONSE = 32_000

_LIST = "zx7_list_saved_render_revisions"
_COMPARE = "zx7_compare_saved_render_revisions"
_COLLAB = "zx7_review_saved_render_candidates"

_SCHEMA_ID = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_PAGING = {
    "offset": {"type": "integer", "minimum": 0, "maximum": 5000},
    "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_ITEMS_PER_PAGE},
}
_DEFINITIONS = (
    (_LIST,
     "List only host-captured native project revisions tied to actual saved export submissions. "
     "SHA-bound metadata, not creative approval, source licence or a new edit.",
     {"type": "object", "properties": {}, "additionalProperties": False}),
    (_COMPARE,
     "Read-only compare exact host-captured native editable project revisions. "
     "Returns paginated changed native object IDs, paths and digests, not artwork, media, "
     "private text, an approved merge, or a verified artistic improvement.",
     {"type": "object", "properties": {
         "before_export_id": _SCHEMA_ID, "after_export_id": _SCHEMA_ID,
         **_PAGING}, "required": ["before_export_id", "after_export_id"],
      "additionalProperties": False}),
    (_COLLAB,
     "Read-only three-way overlap review of three host-captured native revisions. "
     "Human and AI origin labels are NOT authenticated. A no-known-overlap result "
     "never permits automatic merging or bypassing current native revision guards.",
     {"type": "object", "properties": {
         "base_export_id": _SCHEMA_ID, "human_candidate_export_id": _SCHEMA_ID,
         "ai_candidate_export_id": _SCHEMA_ID,
         **_PAGING},
      "required": ["base_export_id", "human_candidate_export_id",
                   "ai_candidate_export_id"],
      "additionalProperties": False}),
)


def _sha(value):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise NativeRevisionReviewError("Invalid host export or native project identity")
    return value


def _bounded_page(rows, arguments, *, full_count):
    start, limit = arguments.get("offset", 0), arguments.get("limit", 12)
    entries = []
    for item in rows[start:start + limit]:
        entry = dict(item)
        if "changed_fields" in entry:
            fields = entry["changed_fields"]
            entry["changed_fields"] = fields[:_MAX_FIELD_PATHS]
            entry["changed_field_count"] = len(fields)
            entry["changed_field_paths_complete"] = len(fields) <= _MAX_FIELD_PATHS
        entries.append(entry)
    return {
        "total_count": full_count, "offset": start, "returned_count": len(entries),
        "entries": entries,
        "has_more_entries": start + len(entries) < full_count,
        "next_offset": start + len(entries) if start + len(entries) < full_count else None,
        "no_automatic_merge_or_native_write": True,
    }


class NativeRevisionObservationMcpSession:
    """One in-memory host-only registry; registered files stay in existing snapshots.

    Caller must register AFTER capture_render_project has physically saved,
    validated and source-bound a native document to a specific export receipt.
    A new session starts empty; no stale register/replay after restart.
    """

    def __init__(self, snapshots_root):
        import jsonschema
        from mcp import types

        root = Path(snapshots_root).absolute()
        if (root.is_symlink() or not root.is_dir() or
                root.stat().st_uid != os.getuid() or
                stat.S_IMODE(root.stat().st_mode) & 0o077):
            raise NativeRevisionReviewError(
                "Native revision observation needs private owned snapshot directory")
        self._root = root
        self._records = {}
        self._calls = 0
        self._validators = {
            name: jsonschema.Draft202012Validator(schema)
            for name, _, schema in _DEFINITIONS
        }
        self._tools = [
            types.Tool(name=name, description=description, inputSchema=schema)
            for name, description, schema in _DEFINITIONS
        ]

    @property
    def grants(self):
        return {tool.name: "read" for tool in self._tools}

    def register_host_captured_render(self, export_id, project_sha256, options_sha256):
        """Only the trusted native capture callback should call this method."""
        export_id, project_sha256, options_sha256 = (
            _sha(export_id), _sha(project_sha256), _sha(options_sha256))
        if export_id in self._records or len(self._records) >= _MAX_SNAPSHOTS:
            raise NativeRevisionReviewError(
                "Duplicate or exhausted host-captured native revision registry")
        # The observed file path derives exclusively from the trusted export
        # destination digest. Model arguments NEVER choose a path or export ID.
        file = self._root / (export_id + ".comfystudio")
        snapshot = load_native_revision(file)
        if snapshot.sha256 != project_sha256:
            raise NativeRevisionReviewError(
                "Host-captured native project bytes differ from the render receipt")
        self._records[export_id] = (project_sha256, options_sha256)
        return {"export_id": export_id, "project_sha256": project_sha256,
                "options_sha256": options_sha256,
                "registered_after_native_save_capture": True}

    def _registered(self, export_id):
        export_id = _sha(export_id)
        record = self._records.get(export_id)
        if record is None:
            raise NativeRevisionReviewError("Unknown host-registered native render")
        file = self._root / (export_id + ".comfystudio")
        observed = load_native_revision(file)
        if observed.sha256 != record[0]:
            raise NativeRevisionReviewError("Saved native revision changed after registration")
        return file, observed, record[1]

    async def list_tools(self):
        from mcp import types
        return types.ListToolsResult(tools=self._tools)

    async def call_tool(self, name, arguments):
        from mcp import types

        def refusal():
            return types.CallToolResult(is_error=True, content=[
                types.TextContent(type="text", text="Native revision review unavailable or refused")])

        if not isinstance(arguments, dict) or name not in self._validators or (
                not self._validators[name].is_valid(arguments)):
            return refusal()
        if self._calls >= _MAX_CALLS:
            return refusal()
        self._calls += 1
        try:
            if name == _LIST:
                snapshots = []
                for export_id in sorted(self._records):
                    _, source, opts_sha = self._registered(export_id)
                    snapshots.append({
                        "export_id": export_id,
                        "project_sha256": source.sha256,
                        "render_options_sha256": opts_sha,
                        "native_version": source.version,
                        "counts": source.counts,
                    })
                result = {
                    "schema": "zx7-model-visible-native-captured-revisions-v1",
                    "snapshots": snapshots, "count": len(snapshots),
                    "captured_after_native_save_and_render_ack": True,
                    "full_physical_export_or_artistic_acceptance": False,
                    "owner_media_or_paths_included": False,
                }
            elif name == _COMPARE:
                p0, b, _ = self._registered(arguments["before_export_id"])
                p1, a, _ = self._registered(arguments["after_export_id"])
                diff = compare_native_revisions(p0, p1)
                # compare_native_revisions reads the exact files once more.
                # Never promote evidence from bytes that changed between the
                # registry check and that read, even in a concurrent GUI race.
                if (diff["before"]["sha256"] != b.sha256 or
                        diff["after"]["sha256"] != a.sha256):
                    raise NativeRevisionReviewError(
                        "Native project changed while comparing render captures")
                result = {
                    "schema": "zx7-model-visible-native-compare-v1",
                    "before": b.public(), "after": a.public(),
                    "before_export_id": arguments["before_export_id"],
                    "after_export_id": arguments["after_export_id"],
                    "native_lineage_hint_only": diff["native_lineage_hint_only"],
                    "impact": diff["impact"],
                    "review": _bounded_page(
                        diff["changes"], arguments,
                        full_count=diff["change_count"]),
                    "native_source_binding_verified_for_both": True,
                    "not_an_authorization_to_apply_edits": True,
                }
            else:
                selected = [self._registered(arguments[key]) for key in (
                    "base_export_id", "human_candidate_export_id",
                    "ai_candidate_export_id")]
                collab = review_native_collaboration(*(row[0] for row in selected))
                if any(collab[key]["sha256"] != row[1].sha256
                       for key, row in zip(("base", "human", "ai_candidate"),
                                           selected, strict=True)):
                    raise NativeRevisionReviewError(
                        "Native project changed while reviewing saved candidates")
                result = {
                    "schema": "zx7-model-visible-native-three-way-v1",
                    "base": collab["base"], "human": collab["human"],
                    "ai_candidate": collab["ai_candidate"],
                    "status": collab["status"],
                    "human_changed_objects": collab["human_changed_objects"],
                    "ai_changed_objects": collab["ai_changed_objects"],
                    "review": _bounded_page(
                        collab["intersections"], arguments,
                        full_count=len(collab["intersections"])),
                    "origin_role_labels_not_authenticated": True,
                    "automatic_merge_permitted": False,
                    "live_native_revision_CAS_required_for_every_write": True,
                    "source_rights_and_artistic_quality_unverified": True,
                }
            raw = json.dumps(result, ensure_ascii=False,
                             sort_keys=True, allow_nan=False)
            if len(raw.encode("utf-8")) > _MAX_TOOL_RESPONSE:
                raise NativeRevisionReviewError("Native revision result exceeded budget")
        except (NativeRevisionReviewError, ValueError, OSError,
                RecursionError, TypeError):
            return refusal()
        return types.CallToolResult(is_error=False, content=[
            types.TextContent(type="text", text=raw)])
