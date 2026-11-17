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
ACTIVE_AV_WINDOW = "zx7_observe_verified_export_av_window"
AUDIO_ENVELOPE = "zx7_observe_verified_export_audio_timeline"
FRAME_TOOLS = frozenset({"zx7_observe_verified_export_frame", TIMED_FRAMES, ACTIVE_AV_WINDOW})
RENDER_TOOL = "export_timeline"
VERIFY_TOOL = "zx7_verify_native_export"
DESTINATION_FIELD = "native_export_destination_sha256"
SCOPE_FIELD = "native_export_timeline_sha256"
AV_REVIEW_FIELD = "native_av_review"
AV_PCM_FIELD = "native_av_pcm_sha256"
SAVED_RENDER_FIELD = "native_render_saved_project_sha256"
SAVED_RENDER_OPTIONS_FIELD = "native_render_options_sha256"
SAVED_RENDER_MEDIA_FIELD = "native_render_media_sha256"
SAVED_RENDER_FAILURE = "native_render_saved_project_capture_failed"


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
        pcm_sha = receipt.get("preview_pcm_sha256")
        if (not isinstance(intervals, list) or
                not any(isinstance(item, dict) and item.get("no_nonzero_mono_samples") is False
                        for item in intervals) or
                type(start) not in (int, float) or not 0 <= start <= 300 or
                type(count) is not int or not 0 < count <= 2_400_160 or
                type(rate) is not int or rate != 8000 or
                not isinstance(pcm_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", pcm_sha)):
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


def _decoded_review_changed(before, after):
    before_frames, before_audio = before
    after_frames, after_audio = after
    return (
        any(before_frames[time] != after_frames[time]
            for time in before_frames.keys() & after_frames.keys()) or
        (before_audio[:2] == after_audio[:2] and before_audio[2] != after_audio[2])
    )


def _reviewed_render_pair_state(events, revision_tools, *, audiovisual=False):
    """Shared fail-closed source-bound pairing and read-only candidate state."""
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
            decoded = None
            if audiovisual:
                values = event.get(AV_REVIEW_FIELD)
                if not valid_av_review_values(tool, values):
                    continue
                review = av_reviews.setdefault(path, {})
                if tool == TIMED_FRAMES:
                    hashes = event["image_sha256"]
                    if len(hashes) != len(values):
                        continue
                    review[tool] = dict(zip(values, hashes))
                else:
                    pcm_sha = event.get(AV_PCM_FIELD)
                    if not isinstance(pcm_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", pcm_sha):
                        continue
                    review[tool] = (*values, pcm_sha)
                if not {VERIFY_TOOL, TIMED_FRAMES, AUDIO_ENVELOPE}.issubset(review):
                    continue
                duration, = review[VERIFY_TOOL]
                times = list(review[TIMED_FRAMES])
                start, end, _ = review[AUDIO_ENVELOPE]
                # Cover separated moments and the full soundtrack, allowing
                # 20 ms at the audio tail for bounded decoder rounding.
                if (times[-1] >= duration or times[-1] - times[0] < duration / 3 or
                        start != 0 or abs(end - duration) > 0.02):
                    continue
                decoded = (review[TIMED_FRAMES], review[AUDIO_ENVELOPE])
            last_review = (rendered[path], path, digest, decoded)
            if (before_revision is not None and before_revision[0] == rendered[path] and
                    before_revision[1] != path and before_revision[2] != digest and
                    (not audiovisual or _decoded_review_changed(before_revision[3], decoded))):
                pair = [
                    {"destination_sha256": output_path, "export_sha256": output_digest,
                     "timeline_sha256": scope}
                    for scope, output_path, output_digest, _ in (before_revision, last_review)
                ]
    return pair, before_revision, rendered, verified


def reviewed_render_pair(events, revision_tools, *, audiovisual=False):
    """Return the latest qualifying pair of file receipts from one timeline."""
    pair, _, _, _ = _reviewed_render_pair_state(
        events, revision_tools, audiovisual=audiovisual)
    return pair


def reviewed_av_reference_frame_times(events, revision_tools):
    """Return exact prior-model-observed times for *another* verified A/V cut.

    Trusted receipts, real timeline identity and export SHA must all match the
    same source-bound pairing state as the acceptance gate. This is a read-only
    explanation of why identical-time samples may be needed, not a new model
    action, source attestation, artistic plan or evidence waiver. None means
    no safely comparable current export (or that the pair already qualifies).
    """
    pair, before, rendered, verified = _reviewed_render_pair_state(
        events, revision_tools, audiovisual=True)
    if pair is not None or before is None or before[3] is None:
        return None
    scope, prior_dest, prior_digest, decoded = before
    times = sorted(decoded[0])
    if (not 2 <= len(times) <= 4 or not
            valid_av_review_values(TIMED_FRAMES, times)):
        return None
    for current_dest, current_digest in verified.items():
        if (current_dest != prior_dest and current_digest != prior_digest and
                rendered.get(current_dest) == scope):
            return times
    return None


def _reviewed_host_render_hashes(events, pair, field, *, distinct=False):
    """Bind a reviewed export pair to exact trusted host-captured bytes.

    This is source/receipt consistency, NOT a signature or proof of artistic
    improvement. Later renders to an identical destination supersede prior
    receipts; unknown or missing saved hashes fail closed.
    """
    if type(pair) is not list or len(pair) != 2 or type(events) is not list:
        return None

    def is_sha(value):
        return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None

    captures = {}
    for event in events:
        if (type(event) is dict and event.get("kind") == "native_tool_result" and
                event.get("tool") == RENDER_TOOL and
                event.get("host_application_write_acknowledged") is True):
            dest = event.get(DESTINATION_FIELD)
            if is_sha(dest):
                captures[dest] = event

    shas = []
    for binding in pair:
        if type(binding) is not dict or not (
                is_sha(binding.get("destination_sha256")) and
                is_sha(binding.get("timeline_sha256"))):
            return None
        capture = captures.get(binding["destination_sha256"])
        if (capture is None or
                capture.get(SCOPE_FIELD) != binding["timeline_sha256"] or
                not is_sha(capture.get(SAVED_RENDER_FIELD)) or
                not is_sha(capture.get(SAVED_RENDER_OPTIONS_FIELD)) or
                not is_sha(capture.get(field))):
            return None
        shas.append(capture[field])
    return shas if (not distinct or shas[0] != shas[1]) else None


def reviewed_native_snapshot_hashes(events, pair):
    """The exact first and revised native project bytes captured by the host."""
    return _reviewed_host_render_hashes(events, pair, SAVED_RENDER_FIELD, distinct=True)


def reviewed_native_media_hashes(events, pair):
    """Render-time source-media closure digests for the same physical pair."""
    return _reviewed_host_render_hashes(events, pair, SAVED_RENDER_MEDIA_FIELD)
