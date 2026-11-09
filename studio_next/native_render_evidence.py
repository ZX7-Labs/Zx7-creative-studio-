"""Link source-attested render, verification and review receipts without raw paths."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


REVIEWED_RENDER_PAIR = "reviewed_native_render_pair_verified"
REVIEWED_NATIVE_EVIDENCE = (
    "native_write_acknowledged", "physical_export_verified",
    "post_observation_native_write_acknowledged", "verified_export_frame_observed",
    REVIEWED_RENDER_PAIR,
)
FRAME_TOOLS = frozenset({"zx7_observe_verified_export_frame", "zx7_observe_verified_export_samples"})
RENDER_TOOL = "export_timeline"
VERIFY_TOOL = "zx7_verify_native_export"
DESTINATION_FIELD = "native_export_destination_sha256"
SCOPE_FIELD = "native_export_timeline_sha256"


def destination_digest(path):
    if not isinstance(path, str) or not Path(path).is_absolute():
        return None
    try:
        return hashlib.sha256(str(Path(path).resolve()).encode("utf-8")).hexdigest()
    except (OSError, RuntimeError, ValueError):
        return None


def timeline_scope_digest(project_path, timeline_id):
    project = destination_digest(project_path)
    if project is None or not isinstance(timeline_id, str) or not 1 <= len(timeline_id) <= 128:
        return None
    return hashlib.sha256(json.dumps([project, timeline_id]).encode("utf-8")).hexdigest()


def native_render_binding(requested, receipt):
    """Bind the approved destination to the pinned editor and worker ACKs."""
    destination = destination_digest(requested)
    if (destination is None or not isinstance(receipt, dict) or
            receipt.get("action") != RENDER_TOOL or receipt.get("success") is not True or
            destination_digest(receipt.get("outputPath")) != destination):
        return {}
    worker, timeline = receipt.get("result"), receipt.get("timeline")
    if (not isinstance(worker, dict) or worker.get("started") is not True or
            destination_digest(worker.get("outputPath")) != destination or
            not isinstance(timeline, dict)):
        return {}
    scope = timeline_scope_digest(receipt.get("projectPath"), timeline.get("id"))
    if scope is None:
        return {}
    return {DESTINATION_FIELD: destination, SCOPE_FIELD: scope}


def reviewed_render_pair(events, revision_tools):
    """Return the latest qualifying pair of file receipts from one timeline."""
    rendered, used_destinations, verified = {}, set(), {}
    first_verification = {}
    last_review = before_revision = pair = None
    for event in events:
        tool, path = event.get("tool"), event.get(DESTINATION_FIELD)
        if event.get("kind") == "native_read_tool_reported_error":
            # A failed trusted verifier/decoder observation contradicts any
            # older acceptance of this destination until fresh evidence is
            # obtained. Its raw path/error text is never placed in the journal.
            if path is not None and (tool == VERIFY_TOOL or tool in FRAME_TOOLS):
                verified.pop(path, None)
                if last_review is not None and last_review[1] == path:
                    last_review = None
                if before_revision is not None and before_revision[1] == path:
                    before_revision = None
                if pair is not None and any(item["destination_sha256"] == path for item in pair):
                    pair = None
            continue
        if event.get("kind") != "native_tool_result":
            continue
        if event.get("host_application_write_acknowledged") is True:
            pair = None
            verified.clear()
            if tool == RENDER_TOOL:
                scope = event.get(SCOPE_FIELD)
                if path in used_destinations:
                    rendered.pop(path, None)
                elif path is not None and scope is not None:
                    used_destinations.add(path)
                    rendered[path] = scope
            elif tool != "save_project":
                rendered.clear()
                if tool in revision_tools:
                    before_revision = last_review or before_revision
                else:
                    # A write with an unknown effect may have switched projects.
                    before_revision = None
                last_review = None
        elif tool == VERIFY_TOOL and path is not None:
            digest = event.get("independently_verified_export_sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                continue
            if path in first_verification and first_verification[path] != digest:
                rendered.pop(path, None)
                verified.pop(path, None)
                if last_review is not None and last_review[1] == path:
                    last_review = None
                if before_revision is not None and before_revision[1] == path:
                    before_revision = None
                if pair is not None and any(item["destination_sha256"] == path for item in pair):
                    pair = None
            elif path in rendered:
                first_verification[path] = digest
                verified[path] = digest
        elif tool in FRAME_TOOLS and event.get("image_sha256") and path in verified:
            digest = event.get("observed_export_sha256")
            if digest == verified[path]:
                last_review = (rendered[path], path, digest)
                if (before_revision is not None and before_revision[0] == rendered[path] and
                        before_revision[1] != path and before_revision[2] != digest):
                    pair = [
                        {"destination_sha256": output_path, "export_sha256": output_digest,
                         "timeline_sha256": scope}
                        for scope, output_path, output_digest in (before_revision, last_review)
                    ]
    return pair
