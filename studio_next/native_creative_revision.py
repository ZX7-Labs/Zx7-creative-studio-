"""Read-only, loss-aware review of exact saved Velorn native project revisions.

This is an evidence adapter for the existing BODY, not another project format,
editor, state owner, merge engine or creative route selector. Unknown native
fields remain part of full-object hashes. Nothing in this module writes native
project bytes, executes model commands or authorizes a stale native edit.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

_MAX_BYTES = 32 * 1024 * 1024
_MAX_OBJECTS = 12000
_MAX_CHANGES = 5000
_MAX_FIELDS = 512
_MAX_DEPTH = 40
_NATIVE_COLLECTIONS = ("tracks", "clips", "transitions", "markers")
_NATIVE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}\Z")
_SAFE_FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{0,63}\Z")
_METADATA_ONLY = frozenset(("/modified",))
_MISSING = object()


class NativeRevisionReviewError(ValueError):
    """A saved native source could not safely support an evidence claim."""


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise NativeRevisionReviewError("Duplicate native JSON member")
        value[key] = item
    return value


def _reject_constant(value):
    raise NativeRevisionReviewError("Non-finite native JSON number")


def _native_id(item, *, label):
    if not isinstance(item, str) or not _NATIVE_ID.fullmatch(item):
        raise NativeRevisionReviewError("Unsafe or missing native " + label + " identity")
    return item


def _secure_read(path: Path):
    path = Path(path).expanduser().absolute()
    if path.name != "project.comfystudio" and path.is_dir():
        path = path / "project.comfystudio"
    # In addition to final-file O_NOFOLLOW, reject redirected ancestor dirs.
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise NativeRevisionReviewError("Native source path contains a symbolic link")
    if not path.is_file():
        raise NativeRevisionReviewError("Native project file is absent or not regular")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                or not 2 <= before.st_size <= _MAX_BYTES):
            raise NativeRevisionReviewError("Native project is not a bounded owner file")
        raw = stream.read(_MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    current = path.stat(follow_symlinks=False)
    identity = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
    if (len(raw) != before.st_size or identity(before) != identity(after)
            or identity(after) != identity(current)):
        raise NativeRevisionReviewError("Native project changed during evidence capture")
    return raw


def _validate_depth(value, depth=0):
    if depth > _MAX_DEPTH:
        raise NativeRevisionReviewError("Native project has excessive nesting")
    if isinstance(value, dict):
        for entry in value.values():
            _validate_depth(entry, depth + 1)
    elif isinstance(value, list):
        for entry in value:
            _validate_depth(entry, depth + 1)


def _object(value, kind):
    if type(value) is not dict:
        raise NativeRevisionReviewError(kind + " must be a native object")
    return value


def _rows(value, kind):
    if type(value) is not list or len(value) > _MAX_OBJECTS:
        raise NativeRevisionReviewError(kind + " needs a bounded native list")
    return value


def _field_token(name):
    # Never emit unchecked values or private field names into a review.
    if _SAFE_FIELD.fullmatch(name):
        return name
    return "opaque_" + _digest(name.encode("utf-8"))[:12]


def _path(parent, key):
    return parent + "/" + _field_token(key)


def _changed_fields(before, after, *, prefix="", depth=0):
    """Change paths only; arrays, opaque properties and actual text remain private."""
    if before == after:
        return []
    if depth >= _MAX_DEPTH:
        return [prefix or "/"]
    if type(before) is dict and type(after) is dict:
        paths = []
        for key in sorted(before.keys() | after.keys()):
            pointer = _path(prefix, key)
            if key not in before or key not in after:
                paths.append(pointer)
            else:
                paths.extend(_changed_fields(before[key], after[key],
                                             prefix=pointer, depth=depth + 1))
            if len(paths) > _MAX_FIELDS:
                raise NativeRevisionReviewError("Native object has excessive changed fields")
        return paths
    return [prefix or "/"]


def _record(records, key, data):
    if key in records or len(records) >= _MAX_OBJECTS:
        raise NativeRevisionReviewError("Duplicate or oversized native object inventory")
    records[key] = data


def _named_items(rows, *, kind):
    result = []
    seen = set()
    for row in _rows(rows, kind):
        row = _object(row, kind)
        identity = _native_id(row.get("id"), label=kind)
        if identity in seen:
            raise NativeRevisionReviewError("Duplicate native " + kind + " identity")
        seen.add(identity)
        result.append((identity, row))
    return result


def _inventory(document):
    document = _object(document, "project")
    if not isinstance(document.get("version"), str) or not document["version"]:
        raise NativeRevisionReviewError("Saved project has no native format version")
    asset_items = _named_items(document.get("assets"), kind="asset")
    timeline_items = _named_items(document.get("timelines"), kind="timeline")
    if not timeline_items:
        raise NativeRevisionReviewError("Saved project contains no timelines")
    current = document.get("currentTimelineId")
    if current is not None and current not in {i for i, _ in timeline_items}:
        raise NativeRevisionReviewError("Active native timeline does not exist")
    assets = {identity for identity, _ in asset_items}
    records = {}
    _record(records, ("document",), {k: v for k, v in document.items()
                                     if k not in ("assets", "timelines")})
    _record(records, ("ordering", "timelines"), [id for id, _ in timeline_items])
    _record(records, ("ordering", "assets"), [id for id, _ in asset_items])
    for identity, asset in asset_items:
        _record(records, ("asset", identity), asset)
    count = {"timelines": len(timeline_items), "assets": len(asset_items),
             "tracks": 0, "clips": 0, "transitions": 0, "markers": 0}
    for timeline_id, timeline in timeline_items:
        _record(records, ("timeline", timeline_id), {
            key: val for key, val in timeline.items()
            if key not in _NATIVE_COLLECTIONS})
        collections = {}
        for name in _NATIVE_COLLECTIONS:
            entries = _named_items(timeline.get(name, []), kind=name)
            collections[name] = entries
            count[name] += len(entries)
            _record(records, ("ordering", timeline_id, name),
                    [identity for identity, _ in entries])
            singular = {"tracks": "track", "clips": "clip",
                        "transitions": "transition", "markers": "marker"}[name]
            for identity, obj in entries:
                _record(records, (singular, timeline_id, identity), obj)
        tracks = {identity for identity, _ in collections["tracks"]}
        for _, clip in collections["clips"]:
            if clip.get("trackId") not in tracks:
                raise NativeRevisionReviewError("Clip references an absent native track")
            asset = clip.get("assetId")
            if asset is not None and asset not in assets:
                raise NativeRevisionReviewError("Clip references an absent source asset")
    return records, count


@dataclass(frozen=True)
class NativeProjectSnapshot:
    """Snapshot is derived; the original app document remains authoritative."""
    sha256: str
    size_bytes: int
    version: str
    created: str | None
    records: dict
    counts: dict

    def public(self):
        return {"sha256": self.sha256, "size_bytes": self.size_bytes,
                "native_version": self.version, "counts": dict(self.counts),
                "native_format_fields_inspected": True,
                "native_editor_origin_independently_attested": False,
                "media_rights_independently_verified": False}


def load_native_revision(location):
    raw = _secure_read(Path(location))
    try:
        document = json.loads(raw.decode("utf-8"),
                              object_pairs_hook=_unique_pairs,
                              parse_constant=_reject_constant)
        _validate_depth(document)
        records, counts = _inventory(document)
    except (UnicodeError, json.JSONDecodeError, RecursionError, TypeError) as exc:
        raise NativeRevisionReviewError("Invalid bounded native project JSON") from exc
    return NativeProjectSnapshot(
        sha256=_digest(raw), size_bytes=len(raw),
        version=document["version"], created=document.get("created")
        if isinstance(document.get("created"), str) else None,
        records=records, counts=counts)


def _public_key(key):
    if key[0] == "document":
        return {"kind": "document", "id": "project"}
    if key[0] == "ordering":
        if len(key) == 2:
            return {"kind": "native_order", "scope": "project", "id": key[1]}
        return {"kind": "native_order", "timeline_id": key[1], "id": key[2]}
    if len(key) == 2:
        return {"kind": key[0], "id": key[1]}
    return {"kind": key[0], "timeline_id": key[1], "id": key[2]}


def _changes(base, after):
    changed = {}
    for key in sorted(base.records.keys() | after.records.keys()):
        left = base.records.get(key, _MISSING)
        right = after.records.get(key, _MISSING)
        if left is not _MISSING and right is not _MISSING and left == right:
            continue
        if len(changed) >= _MAX_CHANGES:
            raise NativeRevisionReviewError("Excessive native changes; do not truncate evidence")
        action = ("added" if left is _MISSING else
                  "removed" if right is _MISSING else "modified")
        paths = ["/"] if action != "modified" else _changed_fields(left, right)
        changed[key] = {
            **_public_key(key),
            "change": action,
            "changed_fields": paths,
            "before_sha256": None if left is _MISSING else _digest(_stable(left).encode("utf-8")),
            "after_sha256": None if right is _MISSING else _digest(_stable(right).encode("utf-8")),
        }
    return changed


def _lineage(base, candidate):
    # Velorn has no universal immutable native project UUID in its saved file.
    # 'created' plus overlap is a *hint*, never a rights/lineage certificate.
    shared = bool({key for key in base.records if key[0] == "timeline"}
                  & {key for key in candidate.records if key[0] == "timeline"})
    return (base.created is not None and base.created == candidate.created
            and base.version == candidate.version and shared)


def _impact(changes):
    ids = {"asset", "clip", "timeline", "track", "transition", "marker"}
    touched = {v["kind"] for v in changes.values()}
    return {
        "editable_native_changes_detected": bool(touched & ids),
        "source_custody_or_render_review_required":
            bool(touched & {"asset", "clip", "timeline", "track", "transition"}),
        "native_order_review_required": "native_order" in touched,
        "unmodeled_document_metadata_changed": ("document",) in changes,
        "actual_media_decoded": False,
        "creative_quality_assessed": False,
    }


def compare_native_revisions(before, after):
    """Evidence about two saved files, never an authorization to apply a merge."""
    left = load_native_revision(before)
    right = load_native_revision(after)
    changes = _changes(left, right)
    impact = _impact(changes)
    return {
        "schema": "zx7-native-revision-review-v1",
        "status": "differences_observed" if changes else "identical_native_structure",
        "native_lineage_hint_only": _lineage(left, right),
        "before": left.public(), "after": right.public(),
        "change_count": len(changes),
        "changes": [changes[k] for k in sorted(changes)],
        "impact": impact,
        "not_a_native_apply_or_merge": True,
        "host_live_native_revision_CAS_still_required": True,
        "no_original_media_copied_or_uploaded": True,
    }


def _meaningful(change):
    return {field for field in change["changed_fields"] if field not in _METADATA_ONLY}


def _field_overlap(first, second):
    return any(a == b or a.startswith(b + "/") or b.startswith(a + "/")
               for a in first for b in second)


def _dependency(left_key, right_key, base, human, ai):
    """Conservative known native associations; an absence is NOT a safe merge."""
    for key, other in ((left_key, right_key), (right_key, left_key)):
        if key[0] == "document":
            return "document_scope"
        if key[0] == "timeline" and len(other) > 1 and other[1] == key[1]:
            return "timeline_scope"
        if key[0] == "track" and other[0] == "clip" and key[1] == other[1]:
            for snap in (base, human, ai):
                clip = snap.records.get(other)
                if isinstance(clip, dict) and clip.get("trackId") == key[2]:
                    return "track_clip_dependency"
        if key[0] == "asset" and other[0] == "clip":
            for snap in (base, human, ai):
                clip = snap.records.get(other)
                if isinstance(clip, dict) and clip.get("assetId") == key[1]:
                    return "asset_clip_dependency"
    return None


def review_native_collaboration(base_file, human_file, ai_file):
    """Three-way, read-only conflict *detection*. NEVER merges or applies edits.

    Human and AI candidate are saved native states on the same plausible origin.
    Even independent diffs require fresh host-granted revision CAS to execute.
    """
    base = load_native_revision(base_file)
    human = load_native_revision(human_file)
    ai = load_native_revision(ai_file)
    if not (_lineage(base, human) and _lineage(base, ai)):
        raise NativeRevisionReviewError(
            "Shared native document origin is unproven; refusing conflict claims")
    ours = _changes(base, human)
    theirs = _changes(base, ai)
    collisions = []
    for akey, human_change in sorted(ours.items()):
        hs = _meaningful(human_change)
        if not hs:
            continue
        for bkey, ai_change in sorted(theirs.items()):
            As = _meaningful(ai_change)
            if not As:
                continue
            kind = None
            if akey == bkey:
                if human_change["after_sha256"] == ai_change["after_sha256"]:
                    continue
                kind = ("same_field_conflict" if _field_overlap(hs, As)
                        else "same_object_needs_review")
            else:
                kind = _dependency(akey, bkey, base, human, ai)
            if kind is not None:
                if len(collisions) >= _MAX_CHANGES:
                    raise NativeRevisionReviewError("Too many concurrent edit intersections")
                collisions.append({"kind": kind,
                                   "human": _public_key(akey),
                                   "ai_candidate": _public_key(bkey)})
    direct = any(c["kind"] == "same_field_conflict" for c in collisions)
    # A nonempty overlap always requires human/native review; no speculative
    # auto-merge, even for disjoint fields of the same editable object.
    return {
        "schema": "zx7-native-collaboration-review-v1",
        "status": ("conflicting_changes" if direct else
                   "needs_native_review" if collisions else "no_known_overlap"),
        "base": base.public(), "human": human.public(), "ai_candidate": ai.public(),
        "human_changed_objects": len(ours), "ai_changed_objects": len(theirs),
        "intersections": collisions,
        "human_source_or_render_recheck": _impact(ours)["source_custody_or_render_review_required"],
        "ai_source_or_render_recheck": _impact(theirs)["source_custody_or_render_review_required"],
        "input_saved_files_not_modified_by_review": True,
        "native_editor_save_independently_attested": False,
        "automatic_merge_permitted": False,
        "live_native_revision_CAS_required_for_every_write": True,
        "source_rights_and_artistic_quality_unverified": True,
    }
