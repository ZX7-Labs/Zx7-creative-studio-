"""Read-only factual diagnostics for source coverage in a model-authored edit.

The inputs are an attested camera source, the proposed edit and the native
project's source manifest. This does not assess artistic quality or inspect
encoded media; the physical render and source-custody gates remain separate.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence


class EditCoverageError(ValueError):
    """Insufficient or contradictory edit evidence."""


def _finite_number(value: object, name: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise EditCoverageError(f"{name} must be a finite number")
    return float(value)


def assess_raw_edit_coverage(
    *, source_duration_seconds: float, source_sha256: str,
    source_has_audio: bool, sample_times_seconds: Sequence[float],
    edit: Mapping, native_plan: Mapping,
) -> dict:
    """Describe actual claimed source selection, without a creative score.

    Direct original references refer ONLY to the supplied native plan, not to
    a reopened .mlt or physical output. No favorable field certifies quality.
    """
    duration = _finite_number(source_duration_seconds, "source duration")
    if not 0 < duration <= 24 * 3600:
        raise EditCoverageError("source duration outside bounded evidence scope")
    if (not isinstance(source_sha256, str) or
            re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None):
        raise EditCoverageError("source SHA-256 must be canonical")
    if type(source_has_audio) is not bool:
        raise EditCoverageError("source audio presence must be measured")
    if (not isinstance(sample_times_seconds, (tuple, list)) or
            len(sample_times_seconds) > 10_000):
        raise EditCoverageError("invalid sampled-frame evidence")
    times = [_finite_number(t, "sample time") for t in sample_times_seconds]
    if any(t < 0 or t >= duration for t in times):
        raise EditCoverageError("sample is outside original video duration")
    if not isinstance(edit, Mapping) or not isinstance(edit.get("cuts"), list):
        raise EditCoverageError("edit has no source cut list")
    cuts = edit["cuts"]
    if not 1 <= len(cuts) <= 100_000:
        raise EditCoverageError("invalid cut count")
    intervals = []
    for index, cut in enumerate(cuts):
        if not isinstance(cut, Mapping):
            raise EditCoverageError(f"cut {index} is not a mapping")
        begin = _finite_number(cut.get("source_in"), f"cut {index} in")
        end = _finite_number(cut.get("source_out"), f"cut {index} out")
        if not 0 <= begin < end <= duration:
            raise EditCoverageError(f"cut {index} exceeds original source")
        intervals.append((begin, end))
    merged: list[list[float]] = []
    for begin, end in sorted(intervals):
        if merged and begin <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([begin, end])
    distinct = sum(end - begin for begin, end in merged)

    if not isinstance(native_plan, Mapping):
        raise EditCoverageError("native plan is missing")
    tracks = native_plan.get("tracks")
    audio_tracks = native_plan.get("audio_tracks")
    if not isinstance(tracks, list) or not isinstance(audio_tracks, list):
        raise EditCoverageError("native picture/audio tracks must be explicit")
    native_clips = []
    for track in tracks:
        if not isinstance(track, Mapping) or not isinstance(track.get("clips"), list):
            raise EditCoverageError("invalid native picture track")
        native_clips.extend(track["clips"])
    if len(native_clips) != len(cuts):
        raise EditCoverageError("source decision and native clip counts diverge")
    if any(not isinstance(clip, Mapping) or
           not isinstance(clip.get("source"), str) for clip in native_clips):
        raise EditCoverageError("native clips lack source references")
    original_ref = "zx7:sha256:" + source_sha256
    direct_count = sum(clip["source"] == original_ref for clip in native_clips)
    silence_only = all(clip.get("audio") == "intentional_silence"
                       for clip in native_clips)
    source_audio_absent_from_plan = not audio_tracks and silence_only

    limitations = ["Sparse decoded stills are not full motion or audio understanding",
                   "Native manifest references are not proof of reopened project fidelity",
                   "No artistic quality is assessed by this diagnostic"]
    if direct_count < len(native_clips):
        limitations.append("Some native clips do not directly reference the original source")
    if source_has_audio and source_audio_absent_from_plan:
        limitations.append("Input audio exists, but native plan does not preserve it")

    return {
        "evidence_type": "source_selection_and_native_plan_only",
        "source_duration_seconds": duration,
        "selected_cut_count": len(cuts),
        "distinct_selected_source_seconds": round(distinct, 6),
        "distinct_source_coverage_fraction": round(distinct / duration, 8),
        "earliest_selected_source_second": min(a for a, _ in intervals),
        "latest_selected_source_second": max(b for _, b in intervals),
        "sampled_still_frame_count": len(times),
        "native_plan_picture_clip_count": len(native_clips),
        "native_plan_direct_original_source_clip_count": direct_count,
        "source_audio_present": source_has_audio,
        "native_plan_preserves_source_audio": (
            False if source_has_audio and source_audio_absent_from_plan else None),
        "artistic_quality_certified": False,
        "limitations": limitations,
    }
