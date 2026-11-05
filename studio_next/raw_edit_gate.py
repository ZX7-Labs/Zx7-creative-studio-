"""Provenance-grounded minimum editorial evidence for unsupervised raw-camera tests.

This is NOT a creative score. It rejects a mechanically unmodified prefix,
which the real 2B model emitted after viewing a 240-second source. Failure
returns observable diagnostics to the model for an independently chosen retry.
No cuts, colors, titles, genres, musical choices or durations are prescribed.
"""
from __future__ import annotations
import math


class InsufficientEditorialEvidence(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__(
            "Model returned only contiguous original source playback with neutral "
            "controls, no graphic intervention and no sound choice. This is "
            "technically valid transcoding, not evidence of an independently "
            "selected edit. Review actual source picture observations and "
            "make your own creative choices; do not copy a host-suggested shot list."
        )


def assess_minimum_editorial_evidence(edit, *, source_seconds, output_fps):
    """Detect zero-intervention playback, not assign a subjective quality score.

    A selective trim from elsewhere in a source can pass this minimum signal;
    it is NOT independently proven compelling. An unchanged contiguous excerpt
    starting at the beginning cannot be reported as autonomous editing merely
    because it was split into 12 one-second parts.
    """
    if (not isinstance(edit, dict) or
            type(source_seconds) not in (int, float) or
            not math.isfinite(source_seconds) or source_seconds <= 0 or
            type(output_fps) not in (int, float) or
            not math.isfinite(output_fps) or not 1 <= output_fps <= 240):
        raise ValueError("Valid model edit and physical source duration required")
    cuts = edit.get("cuts")
    if not isinstance(cuts, list) or not cuts:
        raise ValueError("Actual source cuts required")
    for clip in cuts:
        if (not isinstance(clip, dict) or
                any(type(clip.get(key)) not in (int, float) or
                    not math.isfinite(clip[key]) for key in (
                        "source_in", "source_out", "speed", "contrast", "saturation"))):
            raise ValueError("Cannot audit unvalidated native source span")
        if (not 0 <= clip["source_in"] < clip["source_out"] <= source_seconds
                or not 0.5 <= clip["speed"] <= 2.0
                or not 0.6 <= clip["contrast"] <= 1.5
                or not 0 <= clip["saturation"] <= 2.0):
            raise ValueError("Native source and render controls must be physically admissible")
    beginning = cuts[0]["source_in"]
    ending = cuts[-1]["source_out"]
    contiguous = all(
        abs(prev["source_out"] - later["source_in"]) < 1e-5
        for prev, later in zip(cuts, cuts[1:]))
    # A speed change is measurable only if the native render's rounded
    # output-frame count changes; the real renderer uses round(span/speed*RATE).
    # Sub-8-bit color tweaks are not reliable evidence of any pixel change.
    # These are conservative physical significance checks, not art scoring.
    controls_neutral = all(
        round((clip["source_out"] - clip["source_in"]) /
              clip["speed"] * output_fps) ==
        round((clip["source_out"] - clip["source_in"]) * output_fps)
        and abs(clip["contrast"] - 1.0) < 1.0 / 255
        and abs(clip["saturation"] - 1.0) < 1.0 / 255
        for clip in cuts)
    no_graphics = edit.get("graphics") == []
    music = edit.get("music")
    no_music = isinstance(music, dict) and music.get("enabled") is False
    unmodified_at_start = (
        abs(beginning) < 1e-5 and contiguous and controls_neutral
        and no_graphics and no_music
    )
    unmodified_prefix = unmodified_at_start and ending < source_seconds - 1e-5
    full_source_unmodified = unmodified_at_start and not unmodified_prefix
    results = {
        "kind": "independent_mechanical_edit_evidence_only",
        "source_duration_seconds": source_seconds,
        "source_clip_count": len(cuts),
        "physically_checked_output_fps": output_fps,
        "first_selected_source_second": beginning,
        "last_selected_source_second": ending,
        "source_selection_is_contiguous": contiguous,
        "all_picture_controls_neutral": controls_neutral,
        "graphics_disabled": no_graphics,
        "music_disabled": no_music,
        "unmodified_source_prefix_detected": unmodified_prefix,
        "unmodified_full_source_playback_detected": full_source_unmodified,
        "passes_minimum_editorial_evidence": not unmodified_at_start,
        "artistic_quality_certified": False,
    }
    if unmodified_at_start:
        raise InsufficientEditorialEvidence(results)
    return results
