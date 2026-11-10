"""Link source-attested render, verification and review receipts without raw paths."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


REVIEWED_RENDER_PAIR = "reviewed_native_render_pair_verified"
REVIEWED_AV_PAIR = "reviewed_native_audiovisual_pair_verified"
REVIEWED_NATIVE_EVIDENCE = (
    "native_write_acknowledged", "physical_export_verified",
    "post_observation_native_write_acknowledged", "verified_export_frame_observed",
    REVIEWED_RENDER_PAIR,
)
TIMED_FRAMES = "zx7_observe_verified_export_samples"
AUDIO_ENVELOPE = "zx7_observe_verified_export_audio_timeline"
FRAME_TOOLS = frozenset({"zx7_observe_verified_export_frame", TIMED_FRAMES})
RENDER_TOOL = "export_timeline"
VERIFY_TOOL = "zx7_verify_native_export"
DESTINATION_FIELD = "native_export_destination_sha256"
SCOPE_FIELD = "native_export_timeline_sha256"
AV_REVIEW_FIELD = "native_av_review"


def valid_av_review_values(tool, values):
    if (type(values) is not list or any(
            type(value) not in (int, float) or not 0 <= value <= 300.02
            for value in values)):
        return False
    if tool == VERIFY_TOOL:
        return len(values) == 1 and 0 < values[0] <= 300
    if tool == TIMED_FRAMES:
        return 2 <= len(values) <= 4 and all(
            first < second for first, second in zip(values, values[1:]))
    if tool == AUDIO_ENVELOPE:
        return len(values) == 2 and values[1] > values[0]
    return False


def av_review_values(tool, receipt):
    """Retain bounded decoder facts without logging paths or sensor content."""
    if tool == VERIFY_TOOL:
        observation = receipt.get("observation")
        if (not isinstance(observation, dict) or
                observation.get("audio_present") is not True or
                observation.get("full_picture_and_sound_decoder_completed") is not True):
            return None
        values = [observation.get("duration_seconds")]
    elif tool == TIMED_FRAMES:
        samples = receipt.get("samples")
        if not isinstance(samples, list) or not all(isinstance(item, dict) for item in samples):
            return None
        values = [item.get("sampled_video_seconds_requested") for item in samples]
    elif tool == AUDIO_ENVELOPE:
        intervals = receipt.get("intervals")
        start = receipt.get("requested_start_seconds")
        count = receipt.get("observed_pcm_samples")
        rate = receipt.get("preview_sample_rate")
        if (not isinstance(intervals, list) or
                not any(isinstance(item, dict) and item.get("no_nonzero_mono_samples") is False
                        for item in intervals) or
                type(start) not in (int, float) or not 0 <= start <= 300 or
                type(count) is not int or not 0 < count <= 2_400_160 or
                type(rate) is not int or rate != 8000):
            return None
        values = [start, start + count / rate]
    else:
        return None
    return values if valid_av_review_values(tool, values) else None


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


def reviewed_render_pair(events, revision_tools, *, audiovisual=False):
    """Return the latest qualifying pair of file receipts from one timeline."""
    rendered, used_destinations, verified = {}, set(), {}
    first_verification = {}
    av_reviews = {}
    review_tools = {TIMED_FRAMES, AUDIO_ENVELOPE} if audiovisual else FRAME_TOOLS
    invalidating_reads = FRAME_TOOLS | {VERIFY_TOOL}
    if audiovisual:
        invalidating_reads |= {AUDIO_ENVELOPE}
    last_review = before_revision = pair = None
    for event in events:
        tool, path = event.get("tool"), event.get(DESTINATION_FIELD)
        if event.get("kind") == "native_read_tool_reported_error":
            # A failed trusted verifier/decoder observation contradicts any
            # older acceptance of this destination until fresh evidence is
            # obtained. Its raw path/error text is never placed in the journal.
            if path is not None and tool in invalidating_reads:
                verified.pop(path, None)
                av_reviews.pop(path, None)
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
            av_reviews.clear()
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
                av_reviews.pop(path, None)
                if last_review is not None and last_review[1] == path:
                    last_review = None
                if before_revision is not None and before_revision[1] == path:
                    before_revision = None
                if pair is not None and any(item["destination_sha256"] == path for item in pair):
                    pair = None
            elif path in rendered:
                first_verification[path] = digest
                verified[path] = digest
                if audiovisual and valid_av_review_values(tool, event.get(AV_REVIEW_FIELD)):
                    av_reviews.setdefault(path, {})[VERIFY_TOOL] = event[AV_REVIEW_FIELD]
        elif tool in review_tools and path in verified:
            digest = event.get("observed_export_sha256")
            if digest != verified[path] or (tool in FRAME_TOOLS and not event.get("image_sha256")):
                continue
            if audiovisual:
                values = event.get(AV_REVIEW_FIELD)
                if not valid_av_review_values(tool, values):
                    continue
                review = av_reviews.setdefault(path, {})
                review[tool] = values
                if not {VERIFY_TOOL, TIMED_FRAMES, AUDIO_ENVELOPE}.issubset(review):
                    continue
                duration, = review[VERIFY_TOOL]
                times = review[TIMED_FRAMES]
                start, end = review[AUDIO_ENVELOPE]
                # Cover separated moments and the full soundtrack, allowing
                # 20 ms at the audio tail for bounded decoder rounding.
                if (times[-1] >= duration or times[-1] - times[0] < duration / 3 or
                        start != 0 or abs(end - duration) > 0.02):
                    continue
            last_review = (rendered[path], path, digest)
            if (before_revision is not None and before_revision[0] == rendered[path] and
                    before_revision[1] != path and before_revision[2] != digest):
                pair = [
                    {"destination_sha256": output_path, "export_sha256": output_digest,
                     "timeline_sha256": scope}
                    for scope, output_path, output_digest in (before_revision, last_review)
                ]
    return pair
