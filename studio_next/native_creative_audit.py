"""Independently audit the *technical* model-to-native-editor journal.

The audit is deliberately not an evaluator of creativity or model identity:
a passing journal only proves internal ordering and source-bound custody fields
under the host-issued MCP protocol. No manually fabricated model responses are
transformed into evidence of independent neural intelligence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

from .native_state_evidence import (
    _PINNED_NO_IMAGE_SEQUENCE_ERROR,
    _PINNED_UNKNOWN_BETWEEN_TRANSITION_CLIPS,
    _SOURCE_REVIEWED_NONMUTATING_PREVIEWS)


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
# Exact source-pinned no-write error normalized as the controller serializes
# MCP text observations. Arbitrary tool failures cannot impersonate it.
_PINNED_NO_SEQUENCE_ERROR_DIGEST = hashlib.sha256(json.dumps(
    [_PINNED_NO_IMAGE_SEQUENCE_ERROR], sort_keys=True,
    ensure_ascii=False, allow_nan=False, separators=(",", ":")
).encode("utf-8")).hexdigest()
_PINNED_NO_TRANSITION_CLIPS_DIGEST = hashlib.sha256(json.dumps(
    [_PINNED_UNKNOWN_BETWEEN_TRANSITION_CLIPS], sort_keys=True,
    ensure_ascii=False, allow_nan=False, separators=(",", ":")
).encode("utf-8")).hexdigest()
_OBSERVERS = frozenset({
    "zx7_observe_verified_export_frame",
    "zx7_observe_verified_export_samples",
    "zx7_observe_verified_export_audio",
    "zx7_observe_verified_export_audio_timeline",
})
_FRAME_OBSERVERS = frozenset({
    "zx7_observe_verified_export_frame",
    "zx7_observe_verified_export_samples",
})
_EXPORT = "zx7_verify_native_export"
_COMPLETION_EVIDENCE_TYPES = frozenset({
    "native_write_acknowledged", "physical_export_verified",
    "post_observation_native_write_acknowledged",
    "verified_export_frame_observed",
})
_AUDIO = "zx7_observe_verified_export_audio"
_CRITICAL_END = frozenset({
    "native_tool_reported_error", "native_tool_uncertain_outcome",
    "native_observation_rejected", "model_finished",
    "model_decision_failed",
})


class NativeJournalError(ValueError):
    """Untrusted or incomplete native session ledger cannot be certified."""


def _sha(value):
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _strict_json(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise NativeJournalError("Duplicate journal JSON key")
            result[key] = item
        return result
    def finite_float(raw):
        value = float(raw)
        if not math.isfinite(value):
            raise NativeJournalError("Overflowed journal number")
        return value
    def reject_constant(_):
        raise NativeJournalError("Nonfinite journal number")
    try:
        return json.loads(value, object_pairs_hook=unique, parse_float=finite_float,
                          parse_constant=reject_constant)
    except NativeJournalError:
        # Preserve specific evidence of duplicate or nonfinite source fields.
        raise
    except (ValueError, RecursionError, UnicodeDecodeError) as exc:
        raise NativeJournalError("Invalid journal JSON") from exc


def read_native_journal(path: Path):
    """Read immutable private JSONL within a strict budget; never follow a symlink."""
    path = Path(path)
    if path.is_symlink():
        raise NativeJournalError("Journal cannot be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise NativeJournalError("Journal could not be opened as a regular file") from exc
    try:
        source_stat = os.fstat(fd)
        if (not stat.S_ISREG(source_stat.st_mode) or
                source_stat.st_size > 16 * 1024 * 1024):
            raise NativeJournalError("Journal must be a bounded regular file")
        with os.fdopen(fd, "rb", closefd=False) as source:
            raw = source.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise NativeJournalError("Journal grew past the audit limit")
    finally:
        os.close(fd)
    lines = raw.splitlines()
    if not lines or len(lines) > 1024 or any(not line or len(line) > 128 * 1024
                                              for line in lines):
        raise NativeJournalError("Journal exceeds audit limits or has empty records")
    try:
        events = [_strict_json(line.decode("utf-8")) for line in lines]
    except UnicodeDecodeError as exc:
        raise NativeJournalError("Journal is not UTF-8") from exc
    return events


def audit_native_journal(events, *, host_tool_access, expected_required_evidence=None,
                         host_content_revision_tools=()):
    """Check every transition and trace real export-to-observation identity.

    host_tool_access comes from the trusted owner grants, not from model text.
    A technically coherent journal is *not* proof of a real neural model, genuine
    edits or human-approved audiovisual quality: independent artifact/weight
    witnesses are a separate acceptance stage.
    """
    if (not isinstance(events, list) or not 1 <= len(events) <= 1024 or
            not isinstance(host_tool_access, dict) or
            any(not isinstance(k, str) or v not in ("read", "write")
                for k, v in host_tool_access.items())):
        raise NativeJournalError("Invalid event sequence or host access inventory")
    if not isinstance(events[0], dict) or events[0].get("kind") != "session_started":
        raise NativeJournalError("Journal lacks a session identity")
    required = events[0].get("required_completion_evidence", [])
    if (not isinstance(required, list) or
            any(not isinstance(item, str) or item not in _COMPLETION_EVIDENCE_TYPES
                for item in required) or required != sorted(set(required))):
        raise NativeJournalError("Unknown or malformed host completion requirements")
    # Independent policy witness is supplied by the trusted host caller, not
    # copied from the journal being evaluated. Existing callers may omit it,
    # but that omission cannot certify the configured completion policy.
    if expected_required_evidence is not None:
        if (not isinstance(expected_required_evidence, (list, tuple, frozenset)) or
                any(not isinstance(item, str) or
                    item not in _COMPLETION_EVIDENCE_TYPES
                    for item in expected_required_evidence) or
                len(set(expected_required_evidence)) != len(expected_required_evidence)):
            raise NativeJournalError("Invalid independent host completion policy")
        if required != sorted(expected_required_evidence):
            raise NativeJournalError("Journal completion policy differs from trusted host")
    if (not isinstance(host_content_revision_tools, (list, tuple, frozenset)) or
            any(not isinstance(name, str) or not name or
                host_tool_access.get(name) != "write"
                for name in host_content_revision_tools) or
            len(set(host_content_revision_tools)) != len(host_content_revision_tools) or
            ("post_observation_native_write_acknowledged" in required
             and not host_content_revision_tools)):
        raise NativeJournalError(
            "Independent review revision roles require trusted native write grants")
    host_content_revision_tools = frozenset(host_content_revision_tools)
    pending = None
    verified = set()
    observed = {}
    # Current-edit proof, distinct from the immutable historical custody ledger.
    fresh_verified = set()
    fresh_frames = set()
    saw_verified_frame = False
    post_observation_write = False
    writes = []
    observed_then_written = []
    # Distinguish source-backed, non-invokable tied examples from
    # executable search matches; no journal claim creates host authority.
    latest_inspectable_tied_candidates = []
    model_protocol_rejections = 0
    last_model_protocol_rejection_turn = -1
    finished = False
    terminal = None

    def missing_evidence():
        proven = set()
        if writes:
            proven.add("native_write_acknowledged")
        if post_observation_write:
            proven.add("post_observation_native_write_acknowledged")
        if fresh_verified:
            proven.add("physical_export_verified")
        if fresh_frames:
            proven.add("verified_export_frame_observed")
        return sorted(set(required) - proven)

    for i, event in enumerate(events):
        if not isinstance(event, dict) or type(event.get("sequence")) is not int or event["sequence"] != i:
            raise NativeJournalError("Journal event sequence is broken")
        kind = event.get("kind")
        if not isinstance(kind, str):
            raise NativeJournalError("Journal event kind missing")
        if finished:
            raise NativeJournalError("Unexpected events after a terminal outcome")
        if kind == "session_started":
            if i != 0 or not _sha(event.get("brief_sha256")):
                raise NativeJournalError("Duplicate or unbound creative session")
            continue
        if i == 0:
            continue
        if kind in ("host_project_bootstrap_observation", "host_project_bootstrap_error"):
            if (i != 1 or pending is not None or
                    event.get("tool") != "get_project" or
                    host_tool_access.get("get_project") != "read" or
                    event.get("host_attested_read_only") is not True):
                raise NativeJournalError("Host bootstrap project read lacks read-only evidence")
            if kind == "host_project_bootstrap_observation":
                text_hashes = event.get("text_sha256")
                if (not isinstance(text_hashes, list) or len(text_hashes) != 1 or
                        not all(_sha(x) for x in text_hashes) or
                        event.get("project_presence") not in ("unknown", "absent", "present") or
                        event.get("no_model_selected_mutation") is not True):
                    raise NativeJournalError("Project bootstrap did not preserve bounded host read proof")
            else:
                digest = event.get("error_sha256")
                oversized = event.get("error_text_exceeded_evidence_budget")
                etype = event.get("error_type")
                reported = (type(oversized) is bool and
                            ((digest is None) == oversized) and
                            (digest is None or _sha(digest)) and etype is None)
                exception = (isinstance(etype, str) and bool(etype) and
                             digest is None and oversized is None)
                if not (reported or exception):
                    raise NativeJournalError("Malformed failed project bootstrap evidence")
            continue
        if kind in ("host_project_post_write_observation",
                    "host_project_post_write_error"):
            previous = events[i - 1] if i > 0 else {}
            # Old receipts were never independently versioned; a missing
            # attempt is not a valid new bounded-read claim. Historical
            # artifacts must be examined with their original source version.
            attempt = event.get("read_attempt")
            if type(attempt) is not int or attempt not in (1, 2):
                raise NativeJournalError("Unbounded post-write read attempt")
            original_write = previous
            if attempt == 2:
                # Only an immediately preceding first host read attesting
                # ABSENCE may authorize one more READ. No repeated write,
                # unsigned state claim or fabricated third observation.
                original_write = events[i - 2] if i >= 2 else {}
                if (previous.get("kind") != "host_project_post_write_observation" or
                        previous.get("read_attempt") != 1 or
                        previous.get("project_presence") != "absent"):
                    raise NativeJournalError("Second host read lacks a contradictory first read")
            elif previous.get("kind") != "native_tool_result":
                raise NativeJournalError("First project read lacks acknowledged native write")
            if (pending is not None or
                    original_write.get("kind") != "native_tool_result" or
                    event.get("triggered_by_native_tool") != original_write.get("tool") or
                    host_tool_access.get(original_write.get("tool")) != "write" or
                    host_tool_access.get("get_project") != "read" or
                    event.get("tool") != "get_project" or
                    event.get("host_attested_read_only") is not True or
                    event.get("no_model_selected_mutation") is not True):
                raise NativeJournalError(
                    "Post-write project observation lacks a trusted read-after-write")
            if kind == "host_project_post_write_observation":
                hashes = event.get("text_sha256")
                if (not isinstance(hashes, list) or len(hashes) != 1 or
                        any(not _sha(x) for x in hashes) or
                        event.get("project_presence") not in ("unknown", "absent", "present")):
                    raise NativeJournalError("Post-write project state proof malformed")
            else:
                digest = event.get("error_sha256")
                oversized = event.get("error_text_exceeded_evidence_budget")
                etype = event.get("error_type")
                reported = (type(oversized) is bool and
                            ((digest is None) == oversized) and
                            (digest is None or _sha(digest)) and etype is None)
                exception = (isinstance(etype, str) and bool(etype) and
                             digest is None and oversized is None)
                if not (reported or exception):
                    raise NativeJournalError("Untrusted failed post-write project read")
            continue
        if kind == "host_project_post_write_inconsistent":
            # Two READ observations saying absent after an acknowledged
            # project-opening write are contradictory, not proof of absence
            # and certainly not a license to replay the write.
            latest = events[i - 1] if i > 0 else {}
            first = events[i - 2] if i > 1 else {}
            applied = events[i - 3] if i > 2 else {}
            if (pending is not None or
                    latest.get("kind") != "host_project_post_write_observation" or
                    latest.get("read_attempt") != 2 or
                    latest.get("project_presence") != "absent" or
                    first.get("kind") != "host_project_post_write_observation" or
                    first.get("read_attempt") != 1 or
                    first.get("project_presence") != "absent" or
                    applied.get("kind") != "native_tool_result" or
                    host_tool_access.get(applied.get("tool")) != "write" or
                    latest.get("triggered_by_native_tool") != applied.get("tool") or
                    first.get("triggered_by_native_tool") != applied.get("tool") or
                    event.get("triggered_by_native_tool") != applied.get("tool") or
                    event.get("bounded_read_attempts") != 2 or
                    event.get("claimed_project_success_unconfirmed") is not True or
                    event.get("no_model_selected_mutation") is not True or
                    event.get("no_automatic_write_retry") is not True):
                raise NativeJournalError("Untrusted inconsistent post-write state claim")
            continue
        if kind == "model_protocol_response_rejected":
            # A malformed actual model JSON object is not a selected tool
            # action. Exactly two bounded text-only correction opportunities,
            # no native dispatch, no invented project state or write evidence.
            model_protocol_rejections += 1
            duration = event.get("measured_model_wall_ms")
            turn = event.get("turn")
            if (pending is not None or model_protocol_rejections > 2 or
                    type(turn) is not int or turn <= last_model_protocol_rejection_turn or
                    type(duration) not in (int, float) or
                    not math.isfinite(duration) or duration < 0 or
                    event.get("reason_code") not in (
                        "duplicate_json_field", "invalid_json", "truncated_response",
                        "empty_response", "non_object_json") or
                    event.get("no_native_dispatch") is not True or
                    event.get("remaining_model_output_corrections") != (
                        2 - model_protocol_rejections) or
                    event.get("creative_quality_independently_approved") is not False):
                raise NativeJournalError("Unsafe or fabricated model-output recovery record")
            last_model_protocol_rejection_turn = turn
            continue
        if kind == "model_decision_failed":
            duration = event.get("measured_model_wall_ms")
            if (pending is not None or i != len(events) - 1 or
                    event.get("no_automatic_retry") is not True or
                    event.get("creative_quality_independently_approved") is not False or
                    not isinstance(event.get("error_type"), str) or
                    not event["error_type"] or
                    type(duration) not in (int, float) or
                    not math.isfinite(duration) or duration < 0):
                raise NativeJournalError("Model inference failure has invalid terminal evidence")
            terminal = kind
            finished = True
            continue
        if kind in ("discovered", "native_tool_schema"):
            if pending is not None:
                raise NativeJournalError("Tool catalog interleaved with unfinished native operation")
            if kind == "native_tool_schema":
                tied = event.get("selected_from_noninvokable_search_tie")
                if tied not in (None, False, True) or type(tied) not in (type(None), bool):
                    raise NativeJournalError("Malformed ambiguous candidate inspection claim")
                if tied is True:
                    if event.get("tool") not in latest_inspectable_tied_candidates:
                        raise NativeJournalError(
                            "Native schema was not chosen from a host-granted tied candidate")
                    latest_inspectable_tied_candidates = []
            continue
        if kind == "host_capability_frontier":
            tools = event.get("result_tool_names")
            prior = events[i - 1] if i > 0 else {}
            if (i != 2 or pending is not None or
                    prior.get("kind") != "host_project_bootstrap_observation" or
                    prior.get("project_presence") != "absent" or
                    event.get("trusted_machine_fact") != "project_open" or
                    event.get("host_observed_value") is not False or
                    not _sha(event.get("catalog_revision")) or
                    event.get("no_native_dispatch") is not True or
                    not isinstance(tools, list) or not 1 <= len(tools) <= 4 or
                    any(not isinstance(tool, str) or tool not in host_tool_access
                        for tool in tools) or len(set(tools)) != len(tools)):
                raise NativeJournalError("Untrusted or fabricated initial machine affordance")
            continue
        if kind == "host_native_empty_asset_frontier":
            # A real native get_project snapshot was followed immediately by a
            # host-granted READ of get_assets. It reported an EMPTY complete
            # inventory. Advertise possible tools only; no native write or
            # model-authored operation is performed by this frontier.
            tools = event.get("result_tool_names")
            inventory = events[i - 1] if i >= 1 else {}
            state = events[i - 2] if i >= 2 else {}
            if (pending is not None or
                    host_tool_access.get("get_assets") != "read" or
                    state.get("kind") not in
                    ("host_project_bootstrap_observation",
                     "host_native_state_progress_observation",
                     "host_project_post_write_observation") or
                    (state.get("kind") == "host_project_post_write_observation" and
                     state.get("project_presence") != "present") or
                    (state.get("kind") == "host_project_bootstrap_observation" and
                     state.get("project_presence") != "present") or
                    inventory.get("kind") != "host_native_asset_inventory_observed" or
                    inventory.get("tool") != "get_assets" or
                    inventory.get("host_attested_read_only") is not True or
                    not _sha(inventory.get("text_sha256")) or
                    type(event.get("turn")) is not int or
                    event["turn"] < 0 or
                    event.get("trusted_machine_fact") != "project_asset_available" or
                    event.get("host_observed_value") is not False or
                    event.get("native_project_asset_count") != 0 or
                    event.get("no_native_dispatch") is not True or
                    not _sha(event.get("catalog_revision")) or
                    not isinstance(tools, list) or not 1 <= len(tools) <= 4 or
                    any(not isinstance(tool, str) or
                        host_tool_access.get(tool) != "write" for tool in tools) or
                    len(tools) != len(set(tools))):
                raise NativeJournalError("Empty-project source frontier lacked native custody")
            continue
        if kind == "host_native_asset_capability_frontier":
            # This is never a native tool call. The controller saw a real
            # host-granted get_assets EMPTY catalog and refused a model's
            # nonexistent asset ID. Advertised possible asset-producing
            # operations come exclusively from host effect grants, not from
            # model-authored names or a fixed creative script.
            tools = event.get("result_tool_names")
            rejected = events[i - 1] if i >= 1 else {}
            inventory = events[i - 2] if i >= 2 else {}
            if (pending is not None or
                    host_tool_access.get("get_assets") != "read" or
                    rejected.get("kind") != "model_action_rejected" or
                    rejected.get("validation_keyword") != "native_asset_not_imported" or
                    inventory.get("kind") != "host_native_asset_inventory_observed" or
                    inventory.get("tool") != "get_assets" or
                    event.get("turn") != rejected.get("turn") or
                    event.get("trusted_machine_fact") != "project_asset_available" or
                    event.get("host_observed_value") is not False or
                    event.get("native_project_asset_count") != 0 or
                    event.get("no_native_dispatch") is not True or
                    not _sha(event.get("catalog_revision")) or
                    not isinstance(tools, list) or not 1 <= len(tools) <= 4 or
                    any(not isinstance(tool, str) or
                            host_tool_access.get(tool) != "write" for tool in tools) or
                    len(tools) != len(set(tools))):
                raise NativeJournalError("Host asset-effect frontier lacked physical inventory")
            continue
        if kind in ("host_native_asset_inventory_observed",
                    "host_native_asset_inventory_read_error",
                    "host_native_timeline_inventory_observed",
                    "host_native_timeline_inventory_read_error"):
            # Evidence-only source object inventory obtained via a granted
            # native READ. It does not authorize a mutating operation or
            # certify an asset, clip or track referenced by model text.
            expected_tool = ("get_assets" if "asset" in kind else "get_timeline")
            inventory_observed = kind.endswith("_observed")
            if (pending is not None or
                    event.get("tool") != expected_tool or
                    host_tool_access.get(expected_tool) != "read" or
                    event.get("host_attested_read_only") is not True or
                    event.get("no_native_dispatch") is not True):
                raise NativeJournalError("Native object inventory read lacks host custody")
            if inventory_observed:
                if (not _sha(event.get("text_sha256")) or
                        event.get("error_type") is not None):
                    raise NativeJournalError("Native inventory lacks receipt digest")
            elif (not isinstance(event.get("error_type"), str) or
                  not 1 <= len(event["error_type"]) <= 128 or
                  event.get("text_sha256") is not None):
                raise NativeJournalError("Failed native inventory was misreported")
            continue
        if kind in ("host_native_state_progress_observation",
                    "host_native_state_progress_read_error"):
            # Independent, non-mutating post-write project counts. They
            # neither validate creativity nor author a native tool call.
            if (pending is not None or event.get("tool") != "get_project" or
                    host_tool_access.get("get_project") != "read" or
                    event.get("host_attested_read_only") is not True or
                    event.get("no_model_selected_mutation") is not True or
                    not writes):
                raise NativeJournalError("Post-write native progress lacks grounded read")
            if kind == "host_native_state_progress_observation":
                if (not _sha(event.get("text_sha256")) or
                        not _sha(event.get("summary_sha256")) or
                        event.get("error_type") is not None):
                    raise NativeJournalError("Native progress omitted source or summary digest")
            elif (not isinstance(event.get("error_type"), str) or
                  not 1 <= len(event["error_type"]) <= 128 or
                  event.get("text_sha256") is not None or
                  event.get("summary_sha256") is not None):
                raise NativeJournalError("Failed native project read was misreported")
            continue
        if kind == "capability_searched":
            tools = event.get("result_tool_names")
            inspected = event.get("inspectable_candidate_tool_names", [])
            if (pending is not None or
                    not _sha(event.get("query_sha256")) or
                    not _sha(event.get("catalog_revision")) or
                    event.get("no_native_dispatch") is not True or
                    not isinstance(tools, list) or len(tools) > 8 or
                    any(not isinstance(tool, str) or tool not in host_tool_access
                        for tool in tools) or len(set(tools)) != len(tools) or
                    not isinstance(inspected, list) or len(inspected) > 6 or
                    any(not isinstance(tool, str) or tool not in host_tool_access
                        for tool in inspected) or len(set(inspected)) != len(inspected) or
                    (inspected and (tools or set(inspected).intersection(tools)))):
                raise NativeJournalError("Search fabricated an ungranted native capability")
            latest_inspectable_tied_candidates = inspected[:]
            continue
        if kind == "model_finish_rejected":
            # This is a model-selected finish REFUSED by the owner host: no
            # native dispatch and no claim that artistic work was completed.
            if (pending is not None or event.get("no_native_dispatch") is not True or
                    not missing_evidence() or
                    event.get("missing_completion_evidence") != missing_evidence()):
                raise NativeJournalError("Unproven or fabricated completion refusal")
            continue
        if kind == "model_action_rejected":
            # Input-schema preflight rejected a model proposal BEFORE any RPC.
            # This is safe to correct, unlike an unknown native write result.
            # Never count preflight rejection as an editor operation.
            if (pending is not None or
                    event.get("tool") not in host_tool_access or
                    not _sha(event.get("inputs_sha256")) or
                    event.get("no_native_dispatch") is not True or
                    not isinstance(event.get("validation_keyword"), str) or
                    not 1 <= len(event["validation_keyword"]) <= 64 or
                    (event.get("schema_location") is not None and
                     (not isinstance(event["schema_location"], str) or
                      len(event["schema_location"]) > 512))):
                raise NativeJournalError("Model preflight rejection lacks proof of no native dispatch")
            continue
        if kind == "native_tool_submitted":
            if pending is not None:
                raise NativeJournalError("Second tool submitted before native outcome")
            tool = event.get("tool")
            # Historic receipts carry a plaintext reason. New receipts carry
            # a digest and exact byte length, so model-authored text (which
            # might quote private briefs/assets) does not leak into journals.
            old_reason = event.get("model_reason")
            private_reason = event.get("model_reason_sha256")
            private_len = event.get("model_reason_utf8_bytes")
            legacy = (isinstance(old_reason, str) and bool(old_reason.strip()) and
                      private_reason is None and private_len is None)
            hashed = (_sha(private_reason) and type(private_len) is int and
                      1 <= private_len <= 262144 and old_reason is None)
            if (not isinstance(tool, str) or tool not in host_tool_access or
                    not _sha(event.get("inputs_sha256")) or not (legacy or hashed)):
                raise NativeJournalError("Native operation lacks model intent or host grant")
            pending = (event.get("turn"), tool, host_tool_access[tool])
            continue
        if kind in ("native_tool_result", "native_tool_preview",
                    "native_tool_reported_error", "native_tool_uncertain_outcome",
                    "native_observation_rejected", "native_read_tool_reported_error",
                    "native_source_preview_reported_error",
                    "native_source_preimport_reported_error",
                    "native_source_pretransition_reported_error"):
            if pending is None or (event.get("turn"), event.get("tool")) != pending[:2]:
                raise NativeJournalError("Native outcome does not match a submitted call")
            turn, tool, access = pending
            pending = None
            if kind == "native_tool_preview":
                # The native application acknowledged *a proposed plan*, not
                # an applied edit. It has no authority to advance write proof.
                # Its exact bounded text remains hash-attested; physical
                # mutation proof requires a distinct later native result.
                hashes = event.get("text_sha256")
                if (access != "write" or
                        event.get("host_reported_preview_only") is not True or
                        event.get("no_accepted_write_evidence") is not True or
                        event.get("human_or_artistic_quality_approved") is not False or
                        not isinstance(hashes, list) or len(hashes) != 1 or
                        not all(_sha(x) for x in hashes)):
                    raise NativeJournalError("Native preview was forged as an applied write")
                continue
            if kind == "native_source_preview_reported_error":
                # The pinned native adapter's explicit non-mutating preview
                # path was source-reviewed; this is not a native WRITE result.
                # Its error digest cannot certify completed editing work.
                digest = event.get("error_sha256")
                exceeded = event.get("error_text_exceeded_evidence_budget")
                if (access != "write" or
                        tool not in _SOURCE_REVIEWED_NONMUTATING_PREVIEWS or
                        event.get("host_source_proved_readonly_preview") is not True or
                        event.get("no_accepted_write_evidence") is not True or
                        type(exceeded) is not bool or
                        ((digest is None) != exceeded) or
                        (digest is not None and not _sha(digest))):
                    raise NativeJournalError("Native preview failure was misrepresented")
                continue
            if kind == "native_source_preimport_reported_error":
                # Pinned Velorn forced-sequence detection happens BEFORE
                # importAsset, addAsset, and project save. This failure has
                # no completed native write and can be corrected by the model.
                if (access != "write" or tool != "import_asset_from_path" or
                        event.get("error_sha256") !=
                            _PINNED_NO_SEQUENCE_ERROR_DIGEST or
                        event.get("error_text_exceeded_evidence_budget") is not False or
                        event.get("host_source_proved_no_import_attempt") is not True or
                        event.get("no_accepted_write_evidence") is not True):
                    raise NativeJournalError(
                        "Native import error lacks source-attested no-write proof")
                continue
            if kind == "native_source_pretransition_reported_error":
                # Pinned addTransition resolves two clip IDs before mutation.
                # Only exact source-digested no-write errors may continue.
                if (access != "write" or tool != "add_transition" or
                        event.get("error_sha256") !=
                            _PINNED_NO_TRANSITION_CLIPS_DIGEST or
                        event.get("error_text_exceeded_evidence_budget") is not False or
                        event.get("host_source_proved_no_transition_mutation") is not True or
                        event.get("no_accepted_write_evidence") is not True):
                    raise NativeJournalError(
                        "Native transition error lacks exact no-write source proof")
                continue
            if kind == "native_read_tool_reported_error":
                # This branch is only valid for a host-attested READ. Failed
                # reads are not positive native evidence and grant no ability
                # to advance artistic/export/source-completion counters.
                digest = event.get("error_sha256")
                flag = event.get("error_text_exceeded_evidence_budget")
                if (access != "read" or
                        event.get("host_attested_read_only") is not True or
                        event.get("no_successful_native_observation") is not True or
                        type(flag) is not bool or
                        ((digest is None) != flag) or
                        (digest is not None and not _sha(digest))):
                    raise NativeJournalError("Untrusted or malformed recoverable read failure")
                continue
            if kind == "native_tool_result":
                if event.get("human_or_artistic_quality_approved") is not False:
                    raise NativeJournalError("Technical tool output cannot assert artistic approval")
                if (not isinstance(event.get("text_sha256"), list) or
                        any(not _sha(d) for d in event["text_sha256"]) or
                        not isinstance(event.get("image_sha256"), list) or
                        any(not _sha(d) for d in event["image_sha256"])):
                    raise NativeJournalError("Native data has malformed source checksums")
                new_sha = event.get("independently_verified_export_sha256")
                seen_sha = event.get("observed_export_sha256")
                if access == "write":
                    latest_inspectable_tied_candidates = []
                    # This auditor reads a bounded journal, not the raw host
                    # connection. Demand the control loop's explicit app-level
                    # acknowledgment and tie its receipt hash to the recorded
                    # native response digest before crediting a write. This
                    # remains journal *internal* proof, not a cryptographic
                    # signature from the upstream editor.
                    if (event.get("host_application_write_acknowledged") is not True or
                            len(event["text_sha256"]) != 1 or
                            event.get("host_application_write_receipt_sha256") !=
                            event["text_sha256"][0] or
                            event["image_sha256"] or
                            event.get("audio_sha256") is not None):
                        raise NativeJournalError(
                            "Native write has no bounded application acknowledgment receipt")
                    writes.append((i, tool))
                    if saw_verified_frame and tool in host_content_revision_tools:
                        post_observation_write = True
                    if observed:
                        observed_then_written.append((i, tool))
                    fresh_verified.clear()
                    fresh_frames.clear()
                if new_sha is not None:
                    if tool != _EXPORT or not _sha(new_sha):
                        raise NativeJournalError("Fake physical export verification attribution")
                    verified.add(new_sha)
                    fresh_verified.add(new_sha)
                if seen_sha is not None:
                    if tool not in _OBSERVERS or not _sha(seen_sha) or seen_sha not in verified:
                        raise NativeJournalError("Unverified exported media was observed")
                    observed.setdefault(seen_sha, set()).add(tool)
                    if seen_sha in fresh_verified and tool in _FRAME_OBSERVERS:
                        fresh_frames.add(seen_sha)
                        saw_verified_frame = True
                if tool == _EXPORT and new_sha is None:
                    raise NativeJournalError("No physical export proof on successful verification")
                if tool in _OBSERVERS and seen_sha is None:
                    raise NativeJournalError("Native A/V observation lacks export provenance")
                if bool(event.get("image_sha256")) != (tool in _FRAME_OBSERVERS):
                    raise NativeJournalError("Native visual evidence mismatches sensor identity")
                audio_sha = event.get("audio_sha256")
                if audio_sha is not None:
                    if tool != _AUDIO or not _sha(audio_sha):
                        raise NativeJournalError("Unknown tool forged an audio recording")
                if tool == _AUDIO and audio_sha is None:
                    raise NativeJournalError("Native WAV is absent")
            else:
                if access == "write" and kind == "native_observation_rejected":
                    # A rejected result might follow a completed write; cannot
                    # assume it was rolled back. Always terminate.
                    pass
                if not event.get("must_reconcile_native_state"):
                    raise NativeJournalError("Failed operation lacks reconciliation warning")
                if i != len(events) - 1:
                    raise NativeJournalError("Native error was followed by unsafe operations")
                terminal = kind
                finished = True
            continue
        if kind == "model_finished":
            if pending is not None or missing_evidence():
                raise NativeJournalError("Model finished with an unresolved native write")
            # Preserve old valid journal compatibility, but require new
            # private-summary receipts to have a real SHA and length, never
            # a mixture that hides an unexamined raw-text leakage.
            old_summary = event.get("summary")
            private_sha = event.get("summary_sha256")
            private_len = event.get("summary_utf8_bytes")
            legacy = (isinstance(old_summary, str) and bool(old_summary.strip()) and
                      private_sha is None and private_len is None)
            hashed = (_sha(private_sha) and type(private_len) is int and
                      1 <= private_len <= 262144 and old_summary is None)
            if (event.get("creative_quality_independently_approved") is not False or
                    i != len(events) - 1 or not (legacy or hashed)):
                raise NativeJournalError("Model statement cannot approve artistic quality")
            terminal = kind
            finished = True
            continue
        raise NativeJournalError("Unknown or unreviewed native journal event")

    if pending is not None:
        raise NativeJournalError("Native outcome absent; the last write may have occurred")
    return {
        "schema": 1,
        "journal_chain_structurally_valid": True,
        "host_completion_policy_independently_matched": expected_required_evidence is not None,
        "event_count": len(events),
        "recorded_native_write_result_count": len(writes),
        "export_digests_independently_reported_by_native_host": sorted(verified),
        "observed_verified_export_digests": sorted(observed),
        "model_selected_writes_after_first_verified_observation": len(observed_then_written),
        "model_reported_end_state": terminal or "turn_budget_without_explicit_finish",
        "real_neural_model_weights_or_inference_independently_attested": False,
        "physical_media_bytes_redecoded_by_this_audit": False,
        "source_rights_independently_verified": False,
        "video_editing_capability_complete": False,
        "human_or_artistic_quality_approved": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--host-editor-config", type=Path, required=True)
    args = p.parse_args()
    from .body_editor_policy import load_editor_config
    # The SAME real policy loader that launches the editor validates grants
    # and roots. Extra ZX7 sensor names are inserted ONLY when the actual
    # host config enabled them and the read capability was owner-granted.
    config = load_editor_config(args.host_editor_config)
    grants = dict(config.allowed_tools)
    if config.verify_native_exports and "read" in config.allowed_access:
        extras = {_EXPORT, *_OBSERVERS}
        if any(name in grants for name in extras):
            raise NativeJournalError("Namespaced BODY sensors collide with native grants")
        grants.update({name: "read" for name in extras})
    outcome = audit_native_journal(read_native_journal(args.journal),
                                   host_tool_access=grants)
    print(json.dumps(outcome, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
