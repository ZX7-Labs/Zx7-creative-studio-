"""Read-only owner delivery verification of a completed native audiovisual session.

This is a *fresh* physical post-run check of saved native source and actual
reviewed output files, not a replay of model actions, a signer, an artistic
quality evaluation, or a license grant.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import re
import stat

from .body_editor_client import _load_json
from .body_editor_export import VIDEO_EXTENSIONS, native_export_file_identity, verify_native_editor_export
from .body_editor_policy import EditorPathPolicy
from .native_render_evidence import REVIEWED_AV_PAIR, destination_digest, timeline_scope_digest

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SID = re.compile(r"[0-9a-f]{24}\Z")
_MAX_PROJECT_BYTES = 16 * 1024 * 1024
_MAX_SCAN_ENTRIES = 512
# FFmpeg 7.1.5 reports a silent AAC fixture around -91 dBFS after codec
# quantization; -110 would wrongly classify coded silence as an audible edit.
# This conservative evidence floor is NOT a universal music/dialogue loudness
# target. Quiet intentional content needs separate calibrated listening review.
_MIN_AUDIBLE_PEAK_DBFS = -80.0


def _stable_identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_original_no_follow(path):
    return os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW |
                            getattr(os, "O_CLOEXEC", 0)), "rb")


def _bounded_native_project(path):
    if path.is_symlink():
        raise ValueError("Native editable document is linked")
    with _open_original_no_follow(path) as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= _MAX_PROJECT_BYTES:
            raise ValueError("Native editable document is missing or oversized")
        raw = stream.read(_MAX_PROJECT_BYTES + 1)
        after = os.fstat(stream.fileno())
    if (len(raw) != before.st_size or
            _stable_identity(before) != _stable_identity(after) or
            _stable_identity(after) != _stable_identity(path.stat(follow_symlinks=False))):
        raise ValueError("Native project changed during physical verification")
    doc = _load_json(raw.decode("utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("currentTimelineId"), str):
        raise ValueError("Native project has no current editable timeline")
    if not isinstance(doc.get("timelines"), list):
        raise ValueError("Native project has no editable timelines")
    active = [t for t in doc["timelines"] if
              isinstance(t, dict) and t.get("id") == doc["currentTimelineId"]]
    if len(active) != 1 or not isinstance(active[0].get("clips"), list) or not active[0]["clips"]:
        raise ValueError("Native project has no unique populated active timeline")
    return doc, hashlib.sha256(raw).hexdigest()


def _sha256(path):
    sha = hashlib.sha256()
    with _open_original_no_follow(path) as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            raise ValueError("Original source is not a nonempty regular file")
        count = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            count += len(chunk)
            sha.update(chunk)
        after = os.fstat(stream.fileno())
    if (count != before.st_size or
            _stable_identity(before) != _stable_identity(after) or
            _stable_identity(after) != _stable_identity(path.stat(follow_symlinks=False))):
        raise ValueError("Original source changed during verification")
    return sha.hexdigest()


def _verify_staged_sources(root, session, ledger):
    if not isinstance(ledger, list) or len(ledger) > 64:
        raise ValueError("Untrusted staged owner source ledger")
    staging = root / "staging" / session
    if staging.is_symlink() or not staging.is_dir():
        raise ValueError("Session staging root is unavailable")
    for item in ledger:
        if not isinstance(item, dict) or set(item) != {
                "path", "sha256", "bytes", "rights", "rights_independently_verified"}:
            raise ValueError("Invalid original asset custody record")
        source = Path(item["path"])
        if (not source.is_absolute() or source.parent != staging or source.is_symlink() or
                not source.is_file() or not _SHA.fullmatch(item["sha256"]) or
                type(item["bytes"]) is not int or item["bytes"] <= 0 or
                item["rights_independently_verified"] is not False or
                type(item["rights"]) is not str):
            raise ValueError("Owner original is not a safe source with stated rights")
        if source.stat().st_size != item["bytes"] or _sha256(source) != item["sha256"]:
            raise ValueError("Original source bytes differ from session ledger")
    return len(ledger)


def _verify_native_project_media_closure(project: Path, doc: dict):
    """Rehash referenced physical native sources, not just a saved JSON receipt.

    This is an owner-local read-only availability/integrity check at verify
    time. It cannot authenticate the media's creative origin or prove that
    those exact bytes contributed to an earlier render. Keep those separate.
    """
    inventory = doc.get("assets")
    if not isinstance(inventory, list) or len(inventory) > _MAX_SCAN_ENTRIES:
        raise ValueError("Native project source media inventory is missing or excessive")
    sources = {}
    for asset in inventory:
        if not isinstance(asset, dict):
            raise ValueError("Native project media entry is malformed")
        ident = asset.get("id")
        if type(ident) is not str or not ident or len(ident) > 256 or ident in sources:
            raise ValueError("Native project has ambiguous media source identity")
        sources[ident] = asset
    active = next(
        t for t in doc["timelines"] if isinstance(t, dict)
        and t.get("id") == doc["currentTimelineId"])
    referenced = set()
    for clip in active["clips"]:
        if not isinstance(clip, dict):
            raise ValueError("Native timeline clip is malformed")
        source_id = clip.get("assetId")
        if source_id is None:
            if clip.get("type") in ("video", "audio", "image"):
                raise ValueError("Native media clip is missing its source identity")
            continue
        if type(source_id) is not str or source_id not in sources:
            raise ValueError("Native timeline references an absent source media identity")
        referenced.add(source_id)
    # All imported inventory matters to an editable project, even if a clip
    # is currently disabled/unused: omission would silently break human edits.
    observation = hashlib.sha256()
    total_bytes = 0
    for source_id in sorted(sources):
        asset = sources[source_id]
        named, expected_bytes = asset.get("path"), asset.get("size")
        if (type(named) is not str or not 1 <= len(named) <= 4096 or
                "\\" in named or "\x00" in named or
                type(expected_bytes) is not int or expected_bytes <= 0):
            raise ValueError("Native media file path or byte count is invalid")
        parts = named.split("/")
        if (len(parts) < 3 or parts[0] != "assets" or
                any(part in ("", ".", "..") for part in parts)):
            raise ValueError("Native media file must remain within its project assets")
        candidate = project.joinpath(*parts)
        if (candidate.is_symlink() or
                any(candidate.parents[i].is_symlink() for i in range(len(parts))) or
                not candidate.is_file()):
            raise ValueError("Native project source media is missing or linked")
        actual = candidate.stat(follow_symlinks=False)
        if not stat.S_ISREG(actual.st_mode) or actual.st_size != expected_bytes:
            raise ValueError("Native project source media bytes differ from saved inventory")
        current_sha = _sha256(candidate)
        observation.update(source_id.encode("utf-8"))
        observation.update(b"\x00")
        observation.update(named.encode("utf-8"))
        observation.update(b"\x00")
        observation.update(current_sha.encode("ascii"))
        observation.update(b"\n")
        total_bytes += expected_bytes
    return {
        "native_media_source_closure_verified": True,
        "native_media_asset_inventory_count": len(sources),
        "native_media_used_asset_count": len(referenced),
        "native_media_bytes_observed": total_bytes,
        "native_media_observation_sha256": observation.hexdigest(),
        "native_media_origin_or_export_contribution_proven": False,
    }


def validate_owner_delivery_target(target):
    """Validate an explicit operator target before any neural or native write.

    Target controls physical delivery, not the Brain's aesthetic decisions.
    Missing target is permitted for exploratory runs but never counted as
    independently verified brief/profile conformance.
    """
    if target is None:
        return None
    if type(target) is not dict or set(target) != {
            "width", "height", "duration_seconds"}:
        raise ValueError("Owner delivery target needs width, height and duration_seconds")
    width, height, seconds = (target[k] for k in (
        "width", "height", "duration_seconds"))
    if (type(width) is not int or not 1 <= width <= 8192 or
            type(height) is not int or not 1 <= height <= 8192 or
            type(seconds) not in (int, float) or not math.isfinite(seconds) or
            not 0 < seconds <= 300):
        raise ValueError("Owner delivery target must have finite positive dimensions and duration")
    return {"width": width, "height": height, "duration_seconds": float(seconds)}


def verify_owner_audiovisual_delivery(workspace, session_id, *, max_decode_seconds=900):
    """Re-decode both immutable-in-session MP4s and locate the matching native project.

    No model/network/editor calls, no file publication, and no session mutation.
    Does not establish source contribution, human edit fidelity or professional art.
    """
    if not isinstance(session_id, str) or not _SID.fullmatch(session_id):
        raise ValueError("Provide a valid 24-hex owner session ID")
    if (type(max_decode_seconds) not in (int, float) or
            not math.isfinite(max_decode_seconds) or not 1 <= max_decode_seconds <= 7200):
        raise ValueError("Choose a finite physical decode budget of 1–7200 seconds")
    from .studio_cli import _read_private, load_workspace
    root, _, _ = load_workspace(workspace)
    session = root / "sessions" / session_id
    if session.is_symlink() or not session.is_dir():
        raise ValueError("Session is missing or linked outside its workspace")
    status = _read_private(session / "status.json")
    result = status.get("result") if isinstance(status, dict) else None
    required = (result.get("required_evaluation_evidence")
                if isinstance(result, dict) else None)
    if (not isinstance(status, dict) or
            status.get("session_id") != session_id or status.get("state") != "completed" or
            not isinstance(result, dict) or result.get("evaluation_evidence_satisfied") is not True or
            result.get("status") != "model_finished_unverified" or
            not isinstance(required, list) or
            REVIEWED_AV_PAIR not in required):
        raise ValueError("No completed host-required audiovisual review evidence")
    # This is owner-declared state, not a model-authored verifier target.
    # An omitted target cannot establish brief-compliant width/duration.
    owner_target = validate_owner_delivery_target(status.get("owner_delivery_target"))
    pair = result.get("reviewed_native_audiovisual_pair")
    if not isinstance(pair, list) or len(pair) != 2:
        raise ValueError("No exact two-export audiovisual review pair")
    paths = set()
    digests = set()
    timelines = set()
    for record in pair:
        if not isinstance(record, dict) or set(record) != {
                "destination_sha256", "export_sha256", "timeline_sha256"}:
            raise ValueError("Malformed audiovisual review binding")
        if any(not isinstance(value, str) or not _SHA.fullmatch(value)
               for value in record.values()):
            raise ValueError("Invalid audiovisual receipt hashes")
        paths.add(record["destination_sha256"])
        digests.add(record["export_sha256"])
        timelines.add(record["timeline_sha256"])
    if len(paths) != 2 or len(digests) != 2 or len(timelines) != 1:
        raise ValueError("Review needs two distinct physical outputs on the same timeline")

    ledger = _read_private(session / "sources.json")
    original_count = _verify_staged_sources(root, session_id, ledger)

    outputs = root / "outputs" / session_id
    if outputs.is_symlink() or not outputs.is_dir():
        raise ValueError("Physical output session root unavailable")
    candidates = {}
    visited = 0
    for file in outputs.rglob("*"):
        visited += 1
        if visited > _MAX_SCAN_ENTRIES:
            raise ValueError("Native output inventory exceeds safety budget")
        if file.is_symlink():
            raise ValueError("Symbolic-link output cannot be verified")
        if file.is_dir():
            continue
        if not file.is_file() or file.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        path_hash = destination_digest(str(file))
        if path_hash in paths:
            if path_hash in candidates:
                raise ValueError("Ambiguous physical output destination")
            candidates[path_hash] = file
    if set(candidates) != paths:
        raise ValueError("Physically reviewed export was removed or moved")

    policy = EditorPathPolicy(root / "projects", root / "staging" / session_id, outputs)
    verified = []
    for binding in pair:
        item = candidates[binding["destination_sha256"]]
        before = native_export_file_identity(item)
        if before[-1] != binding["export_sha256"]:
            raise ValueError("Physical output differs from reviewed native receipt")
        inspection = verify_native_editor_export(
            str(item), policy=policy,
            expected={"require_audio": True, **(owner_target or {})},
            max_seconds=max_decode_seconds)
        after = native_export_file_identity(item)
        if before != after or inspection["native_export_sha256"] != binding["export_sha256"]:
            raise ValueError("Physical output mutated during owner verification")
        observed = inspection["observation"]
        audio = observed.get("audio_measurements")
        try:
            peak = float(audio["max_volume_dbfs"])
        except (TypeError, ValueError, KeyError):
            raise ValueError("Full soundtrack has no bounded decoded peak measurement") from None
        if not math.isfinite(peak) or peak < _MIN_AUDIBLE_PEAK_DBFS:
            raise ValueError("Review output has silent or unmeasurable audio")
        verified.append({
            "path_relative_to_workspace": str(item.relative_to(root)),
            "sha256": before[-1], "bytes": before[2],
            "width": observed["width"], "height": observed["height"],
            "duration_seconds": observed["duration_seconds"],
            "audio_decoded_and_non_silent": True,
        })

    projects = root / "projects"
    matches = []
    visited = 0
    for entry in projects.iterdir():
        visited += 1
        if visited > _MAX_SCAN_ENTRIES:
            raise ValueError("Project inventory exceeds safety budget")
        if entry.is_symlink():
            raise ValueError("Linked native project is not trusted")
        if not entry.is_dir():
            continue
        saved = entry / "project.comfystudio"
        if not saved.exists():
            continue
        document, saved_sha = _bounded_native_project(saved)
        if timeline_scope_digest(str(entry), document["currentTimelineId"]) in timelines:
            matches.append((saved, document["currentTimelineId"], saved_sha, document))
    if len(matches) != 1:
        raise ValueError("No unique editable saved project matches the reviewed timeline")
    saved, timeline_id, saved_sha, native_doc = matches[0]
    native_media_observation = _verify_native_project_media_closure(
        saved.parent, native_doc)
    if _bounded_native_project(saved)[1] != saved_sha:
        raise ValueError("Native project changed while checking its source media")
    snapshots_required = status.get("render_snapshots_required", False)
    if type(snapshots_required) is not bool:
        raise ValueError("Malformed owner render snapshot requirement")
    snapshot_bound = False
    if snapshots_required:
        expected_snapshot_hashes = result.get("reviewed_native_snapshot_sha256")
        if (type(expected_snapshot_hashes) is not list or
                len(expected_snapshot_hashes) != 2 or
                any(type(item) is not str or not _SHA.fullmatch(item)
                    for item in expected_snapshot_hashes)):
            raise ValueError("Host-required native render snapshot digests are missing")
        snapshots_root = root / "state" / session_id / "av-project-snapshots"
        if snapshots_root.is_symlink() or not snapshots_root.is_dir():
            raise ValueError("Host-required native render snapshots are missing")
        expected_media_hashes = result.get("reviewed_native_media_sha256")
        if (type(expected_media_hashes) is not list or len(expected_media_hashes) != 2 or
                any(type(value) is not str or not _SHA.fullmatch(value)
                    for value in expected_media_hashes)):
            raise ValueError("Host-required render-time native media digests are missing")
        revisions = []
        for index, (binding, captured_sha) in enumerate(zip(
                pair, expected_snapshot_hashes, strict=True)):
            snapshot = snapshots_root / (binding["destination_sha256"] + ".comfystudio")
            if not snapshot.is_file() or snapshot.is_symlink():
                raise ValueError("Host-required render snapshot is missing or linked")
            snapshot_doc, snapshot_sha = _bounded_native_project(snapshot)
            if snapshot_doc["currentTimelineId"] != timeline_id:
                raise ValueError("Native snapshot timeline differs from reviewed project")
            if snapshot_sha != captured_sha:
                raise ValueError(
                    "Native render snapshot digest differs from original render-time source")
            # The first editable revision may reference media that the final
            # revision no longer needs. Verifying only the final media closure
            # would incorrectly accept an irrecoverable first saved project.
            # Each render-time media digest was captured independently by the
            # host; rehash each snapshot's *own* asset inventory, not the
            # final inventory (which may legitimately add new native assets).
            observed_media = (native_media_observation if index == len(pair) - 1
                else _verify_native_project_media_closure(saved.parent, snapshot_doc))
            if (observed_media["native_media_observation_sha256"] !=
                    expected_media_hashes[index]):
                raise ValueError(
                    "Native snapshot source media differ from original render-time custody")
            revisions.append(snapshot_sha)
        if revisions[0] == revisions[1]:
            raise ValueError("Native snapshots do not establish an editable revision")
        if revisions[-1] != saved_sha:
            raise ValueError("Final saved native source differs from the reviewed render")
        if (native_media_observation["native_media_observation_sha256"] !=
                expected_media_hashes[-1]):
            raise ValueError("Native media source bytes changed since original final render")
        snapshot_bound = True
    return {
        "schema": 1, "kind": "zx7_owner_native_av_delivery_check",
        **native_media_observation,
        "session_id": session_id, "physical_audiovisual_pair_verified": True,
        "owner_delivery_profile_verified": owner_target is not None,
        "owner_delivery_target": owner_target,
        "source_staging_sha256_verified": True, "owner_stated_original_count": original_count,
        "owner_rights_independently_verified": False,
        "original_media_visible_in_exports_proven": False,
        "editable_native_project_relative_to_workspace": str(saved.relative_to(root)),
        "editable_native_project_sha256": saved_sha,
        "saved_native_matches_last_render_snapshot": snapshot_bound,
        "native_media_matches_final_render_capture": snapshot_bound,
        "render_snapshot_media_closure_verified": snapshot_bound,
        "native_render_snapshot_match_not_tested": not snapshots_required,
        "rendered_exports": verified,
        "model_autonomy_independently_evaluated": False,
        "artistic_quality_independently_approved": False,
        "human_live_collaboration_accepted": False,
        "host_status_is_not_a_cryptographic_signature": True,
    }
