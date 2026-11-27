"""Bounded, source-bound *temporal* loudness evidence for a native video export.

A segment-level 8 kHz mono diagnostic; NOT final multichannel loudness,
LUFS, true peak, exact audio PTS, audio quality, or creative assessment.
The controller must have independently verified the exact video SHA first.
"""
from __future__ import annotations

from array import array
import hashlib
import math
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

from .body_editor_client import EditorAccessError
from .body_editor_policy import EditorPathPolicy
from .body_editor_export import _no_path_symlinks, VIDEO_EXTENSIONS
from .delivery_audit import _probe_details
from .edit_timeline import SELF_CONTAINED_VIDEO_INPUT
from .media_vault import sha256_file

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_RATE = 8000
_MAX_DURATION = 300.0  # request budget, not a creative video-length limit
_MAX_BINS = 256
_MAX_PCM_BYTES = int(_MAX_DURATION * _RATE * 2) + 4096


def observe_verified_export_audio_timeline(
    path: str, *, policy: EditorPathPolicy, verified_sha256: str,
    start_seconds: float, duration_seconds: float, bins: int = 64,
    timeout: int = 120,
) -> dict:
    """Return real decoded mono peak/RMS evidence, without retaining audio.

    The data describes sampled decode-relative intervals, NOT exact original
    stream presentation timestamps; each original channel is downmixed.
    Small windows can be chosen anywhere in a long project without imposing
    a project-duration limit.
    """
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise EditorAccessError("Audio timeline requires an absolute owned video export")
    source = Path(path)
    if (not isinstance(policy, EditorPathPolicy) or
            not policy("inspect_export_file", {"path": path}, "read") or
            not source.resolve().is_relative_to(policy.outputs_root) or
            source.suffix.lower() not in VIDEO_EXTENSIONS or
            not _no_path_symlinks(source, (policy.outputs_root,))):
        raise EditorAccessError("Audio timeline refuses unauthorized or linked exports")
    if not isinstance(verified_sha256, str) or not _DIGEST.fullmatch(verified_sha256):
        raise ValueError("Audio timeline requires a trusted SHA256")
    for label, v in (("start", start_seconds), ("duration", duration_seconds)):
        if type(v) not in (float, int) or not math.isfinite(v):
            raise ValueError(f"Audio timeline {label} must be finite")
    if not 0 <= start_seconds or not 0 < duration_seconds <= _MAX_DURATION:
        raise ValueError("Audio timeline interval exceeds its bounded resource budget")
    if type(bins) is not int or not 2 <= bins <= _MAX_BINS:
        raise ValueError("Audio timeline needs 2..256 integral time bins")
    # Reject excessive tiny bin sizes instead of manufacturing time fidelity.
    estimated = round(duration_seconds * _RATE)
    if estimated < bins * 8:
        raise ValueError("Audio timeline request has insufficient samples per bin")
    before = source.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("Native video export is not a regular file")
    details = _probe_details(source)
    if details["video_sha256"] != verified_sha256:
        raise ValueError("Native export changed since full independent verification")
    if not details["audio_stream_present"]:
        raise ValueError("Native video has no actual audio track")
    if start_seconds + duration_seconds > details["duration_seconds"] + 0.000001:
        raise ValueError("Audio timeline interval exceeds measured video")
    argv = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            *SELF_CONTAINED_VIDEO_INPUT,
            "-ss", format(start_seconds, ".9f"), "-i", str(source),
            "-map", "0:a:0", "-t", format(duration_seconds, ".9f"),
            "-vn", "-ac", "1", "-ar", str(_RATE), "-c:a", "pcm_s16le",
            "-f", "s16le", "-fs", str(_MAX_PCM_BYTES), "pipe:1"]
    # FFmpeg writes only to a temporary disk file; no unbounded RAM capture.
    with tempfile.TemporaryFile() as sink:
        result = subprocess.run(argv, stdout=sink, stderr=subprocess.DEVNULL,
                                timeout=timeout, check=False)
        byte_count = sink.tell()
        if result.returncode or byte_count % 2 or not 0 < byte_count <= _MAX_PCM_BYTES:
            raise ValueError("Native audio timeline was not safely decoded")
        total = byte_count // 2
        # A half-sample-level audio origin is not asserted. Significant
        # under/over-decode must fail rather than describing a truncated film.
        tolerance = max(128, round(0.02 * _RATE))
        if abs(total - estimated) > tolerance:
            raise ValueError("Decoded audio timeline has unexpected sample count")
        sink.seek(0)
        counts = [0] * bins
        powers = [0] * bins
        peaks = [0] * bins
        pcm_digest = hashlib.sha256()
        position = 0
        while True:
            chunk = sink.read(32768)
            if not chunk:
                break
            if len(chunk) % 2:
                raise ValueError("Native audio contains a partial PCM frame")
            pcm_digest.update(chunk)
            if sys.byteorder == "little":
                samples = array("h")
                samples.frombytes(chunk)
            else:
                from struct import iter_unpack
                samples = (s for (s,) in iter_unpack("<h", chunk))
            for sample in samples:
                index = min(bins - 1, position * bins // total)
                sample = int(sample)
                counts[index] += 1
                powers[index] += sample * sample
                peaks[index] = max(peaks[index], abs(sample))
                position += 1
        if position != total or any(count == 0 for count in counts):
            raise ValueError("Native timeline has missing decoded sample buckets")
    after = source.stat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or sha256_file(source) != verified_sha256):
        raise ValueError("Native export changed during audio timeline observation")
    intervals = []
    for i in range(bins):
        rms = math.sqrt(powers[i] / counts[i]) / 32768
        intervals.append({
            "decode_relative_start_seconds": (i * total // bins) / _RATE,
            "decode_relative_end_seconds": ((i+1) * total // bins) / _RATE,
            "rms_dbfs": 20 * math.log10(rms) if rms else None,
            "sample_peak_normalized": peaks[i] / 32768,
            "no_nonzero_mono_samples": powers[i] == 0,
        })
    return {
        "schema": 1,
        "kind": "verified_native_editor_audio_temporal_envelope",
        "export_sha256": verified_sha256,
        "requested_start_seconds": start_seconds,
        "requested_duration_seconds": duration_seconds,
        "observed_pcm_samples": total,
        "preview_sample_rate": _RATE,
        "preview_channels": 1,
        "preview_downmixed_and_resampled": True,
        "preview_pcm_sha256": pcm_digest.hexdigest(),
        "intervals": intervals,
        "exact_original_audio_pts_proven": False,
        "full_resolution_or_multichannel_audio_proven": False,
        "integrated_lufs_or_true_peak_proven": False,
        "human_or_artistic_quality_approved": False,
    }
