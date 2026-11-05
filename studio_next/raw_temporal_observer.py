"""Bounded physical temporal evidence from an entire authorized camera recording.

This is a cheap deterministic motion/change *proxy*, not optical flow, shot
semantics, sound recognition, or proof of artistic judgment. No neural model or
network service is used. Inspect every second rather than choosing a promising
looking excerpt of the source.
"""
from __future__ import annotations

import math
from pathlib import Path
import subprocess

_WIDTH = 64
_HEIGHT = 36
_FRAME_BYTES = _WIDTH * _HEIGHT
_MAX_SECONDS = 1200


class RawTemporalObservationError(ValueError):
    """Camera stream could not be physically observed within declared bounds."""


def select_temporal_samples(duration_seconds, change_scores, *, count=16):
    """Choose one actual-source time per temporal stratum.

    Even strata retain a representative midpoint; odd strata select the
    strongest grayscale image change. This keeps full-source coverage even
    when a source has no detected changes. No narrative style is prescribed.
    """
    if (type(duration_seconds) not in (float, int) or
            not math.isfinite(duration_seconds) or
            not 0 < duration_seconds <= _MAX_SECONDS):
        raise RawTemporalObservationError("Invalid source duration for bounded scan")
    if type(count) is not int or not 1 <= count <= 64:
        raise RawTemporalObservationError("Invalid contact-sheet sample budget")
    if (not isinstance(change_scores, list) or
            not 1 <= len(change_scores) <= _MAX_SECONDS or
            any(type(x) not in (float, int) or
                not math.isfinite(x) or not 0 <= x <= 255
                for x in change_scores)):
        raise RawTemporalObservationError("Invalid physically measured grayscale change")
    result = []
    for i in range(count):
        left = duration_seconds * i / count
        right = duration_seconds * (i + 1) / count
        midpoint = (left + right) / 2
        if i % 2:
            # Difference at second n compares the measured image at n with
            # n-1; report a presentation time inside that actual interval.
            candidates = [(float(score), n) for n, score in enumerate(change_scores)
                          if n >= 1 and left <= n <= right]
            if candidates:
                _, at = max(candidates, key=lambda pair: (pair[0], -pair[1]))
                midpoint = float(at)
        result.append(round(min(duration_seconds - .15,
                                max(0.0, midpoint)), 3))
    if len(set(result)) != len(result):
        raise RawTemporalObservationError("Sampling strata collapsed into duplicate frames")
    return result


def inspect_raw_temporal_source(source, duration_seconds, *, ffmpeg="ffmpeg"):
    """Decode source pictures across their full duration at 1 fps / 64x36.

    Returns factual grayscale-change magnitudes and balanced sample times,
    without claiming that a changed pixel represents an important story event.
    Large or unbounded source timelines fail closed.
    """
    if type(duration_seconds) not in (float, int) or not math.isfinite(duration_seconds):
        raise RawTemporalObservationError("Source duration must be independently probed")
    if not 30 <= duration_seconds <= _MAX_SECONDS:
        raise RawTemporalObservationError("Source duration is outside raw camera trial bounds")
    source = Path(source)
    if not source.is_file():
        raise RawTemporalObservationError("Original camera source not found")
    argv = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-i", str(source), "-map", "0:v:0", "-an",
            "-vf", f"fps=1,scale={_WIDTH}:{_HEIGHT}:flags=fast_bilinear,format=gray",
            "-frames:v", str(_MAX_SECONDS),
            "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"]
    try:
        result = subprocess.run(argv, capture_output=True, timeout=240, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RawTemporalObservationError("Actual camera temporal decode failed") from exc
    data = result.stdout
    if len(data) % _FRAME_BYTES:
        raise RawTemporalObservationError("Decoder returned a partial grayscale frame")
    frame_count = len(data) // _FRAME_BYTES
    if not 1 <= frame_count <= _MAX_SECONDS:
        raise RawTemporalObservationError("Decoder returned no bounded temporal evidence")
    changes = [0.0]
    previous = data[:_FRAME_BYTES]
    for i in range(1, frame_count):
        current = data[i * _FRAME_BYTES:(i + 1) * _FRAME_BYTES]
        average = sum(abs(a - b) for a, b in zip(current, previous)) / _FRAME_BYTES
        changes.append(round(average, 6))
        previous = current
    # A genuinely short decoded source is not equivalent to the probed duration.
    if abs(frame_count - duration_seconds) > 2.0:
        raise RawTemporalObservationError("Decoded source length disagrees with probed timeline")
    picks = select_temporal_samples(duration_seconds, changes)
    peaks = sorted(enumerate(changes), key=lambda pair: (-pair[1], pair[0]))[:8]
    return {
        "kind": "decoded_full_source_grayscale_change_proxy",
        "source_duration_seconds": duration_seconds,
        "decoded_one_fps_frame_count": frame_count,
        "decoded_scan_size": [_WIDTH, _HEIGHT],
        "contact_sheet_sample_times_seconds": picks,
        "highest_change_seconds": [
            {"source_second": n, "average_grayscale_delta_0_to_255": x}
            for n, x in sorted(peaks) if n > 0],
        "mean_adjacent_grayscale_delta_0_to_255": round(sum(changes[1:]) / max(1, len(changes) - 1), 6),
        "maximum_adjacent_grayscale_delta_0_to_255": max(changes),
        "not_motion_semantics_or_artistic_quality": True,
        "not_audio_or_continuous_scene_understanding": True,
    }
