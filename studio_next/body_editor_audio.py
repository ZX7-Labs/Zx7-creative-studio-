"""Short, source-bound real WAV observation of an already verified video export.

This is the native editor's read-only audio *hearing* interface, not a promise
that a model can understand music, speech, sync, mastering or full-film quality.
Return an actual playable, bounded PCM WAV using the existing host-root policy.
"""
from __future__ import annotations

from array import array
import hashlib
import io
import math
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import wave

from .body_editor_client import EditorAccessError
from .body_editor_policy import EditorPathPolicy
from .body_editor_export import _no_path_symlinks, VIDEO_EXTENSIONS
from .delivery_audit import _probe_details
from .edit_timeline import SELF_CONTAINED_VIDEO_INPUT
from .media_vault import sha256_file

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_SAMPLE_RATE = 16000
_MAX_SECONDS = 3.0
_MAX_PCM_BYTES = _SAMPLE_RATE * 2 * 3 + 4096


def observe_verified_export_audio(
    path: str, *, policy: EditorPathPolicy, verified_sha256: str,
    start_seconds: float, duration_seconds: float, timeout: int = 60,
) -> tuple[bytes, dict]:
    """Return <=3 seconds of decoded mono 16kHz PCM WAV and factual receipt.

    Preserve exact original video bytes. The preview explicitly downmixes and
    resamples, so it is unsuitable for judging final spatial mixes or masters.
    """
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise EditorAccessError("Audio observation needs an absolute authorized export")
    if not isinstance(policy, EditorPathPolicy) or not policy(
            "inspect_export_file", {"path": path}, "read"):
        raise EditorAccessError("Audio observation denied by the host's editor policy")
    source = Path(path)
    if (not source.resolve().is_relative_to(policy.outputs_root) or
            source.suffix.lower() not in VIDEO_EXTENSIONS or
            not _no_path_symlinks(source, (policy.outputs_root,))):
        raise EditorAccessError("Audio observation refuses linked or unauthorized media")
    if not isinstance(verified_sha256, str) or not _DIGEST.fullmatch(verified_sha256):
        raise ValueError("An issued native export SHA256 is required")
    for name, value in (("start", start_seconds), ("duration", duration_seconds)):
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError("Audio " + name + " must be a finite number")
    if start_seconds < 0 or not 0 < duration_seconds <= _MAX_SECONDS:
        raise ValueError("Audio excerpt must be within the bounded duration and start")
    before = source.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("Native export is not a real regular video")
    probe = _probe_details(source)
    if probe["video_sha256"] != verified_sha256:
        raise ValueError("Native export changed since full physical verification")
    if not probe["audio_stream_present"]:
        raise ValueError("Completed export has no physical audio stream")
    if start_seconds + duration_seconds > probe["duration_seconds"]:
        raise ValueError("Audio excerpt exceeds the measured export duration")

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        *SELF_CONTAINED_VIDEO_INPUT,
        "-ss", format(start_seconds, ".9f"), "-i", str(source),
        "-map", "0:a:0", "-t", format(duration_seconds, ".9f"),
        "-vn", "-ac", "1", "-ar", str(_SAMPLE_RATE), "-c:a", "pcm_s16le",
        "-f", "s16le", "-fs", str(_MAX_PCM_BYTES), "pipe:1",
    ]
    # Spool to disk: never buffer an unbounded native decoder stdout in RAM.
    with tempfile.TemporaryFile() as sink:
        result = subprocess.run(command, stdout=sink, stderr=subprocess.DEVNULL,
                                timeout=timeout, check=False)
        size = sink.tell()
        if result.returncode or size < 2 or size > _MAX_PCM_BYTES or size % 2:
            raise ValueError("Native video audio could not be safely decoded")
        sink.seek(0)
        pcm = sink.read(_MAX_PCM_BYTES + 1)
    if not pcm or len(pcm) > _MAX_PCM_BYTES or len(pcm) % 2:
        raise ValueError("Native decoded PCM exceeded the bounded audio excerpt")
    # FFmpeg's raw PCM output has no trustworthy RIFF size, so write a complete
    # seekable WAV header ourselves. Python wave consumes bounded PCM only.
    memory = io.BytesIO()
    with wave.open(memory, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_SAMPLE_RATE)
        wav.writeframes(pcm)
    audio_wav = memory.getvalue()
    with wave.open(io.BytesIO(audio_wav), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(),
                wav.getnframes()) != (1, 2, _SAMPLE_RATE, len(pcm) // 2):
            raise ValueError("Bounded preview WAV failed independent PCM framing")
    if sys.byteorder == "little":
        samples = array("h")
        samples.frombytes(pcm)
        power = sum(int(s) ** 2 for s in samples)
        peak = max(abs(int(s)) for s in samples)
    else:
        from struct import iter_unpack
        values = [sample for (sample,) in iter_unpack("<h", pcm)]
        power = sum(s * s for s in values)
        peak = max(abs(s) for s in values)
    after = source.stat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or sha256_file(source) != verified_sha256):
        raise ValueError("Native export changed while audio was observed")
    return audio_wav, {
        "schema": 1,
        "kind": "verified_native_editor_bounded_audio_excerpt",
        "export_sha256": verified_sha256,
        "requested_start_seconds": start_seconds,
        "requested_duration_seconds": duration_seconds,
        "exact_original_audio_pts_proven": False,
        "observed_pcm_frames": len(pcm) // 2,
        "observed_audio_duration_seconds": len(pcm) // (2 * _SAMPLE_RATE),
        "preview_sample_rate": _SAMPLE_RATE,
        "preview_channels": 1,
        "preview_sample_bits": 16,
        "preview_downmixed_and_resampled": True,
        "preview_is_silent": power == 0,
        "preview_rms_dbfs": None if power == 0 else 20 * math.log10(
            math.sqrt(power / (len(pcm) // 2)) / 32768),
        "preview_peak_normalized": peak / 32768,
        "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
        "wav_sha256": hashlib.sha256(audio_wav).hexdigest(),
        "full_film_listening_or_spatial_mix_verified": False,
        "human_or_artistic_quality_approved": False,
    }
