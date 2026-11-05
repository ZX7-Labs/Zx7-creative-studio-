"""Rights-conservative, direct-original camera source for the native Velorn brain.

No model-authored edit or full legal clearance is implied. Source bytes stay
unchanged and the native editor receives the actual camera recording, not
FFmpeg-prebaked cut segments.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from .raw_temporal_observer import (
    inspect_raw_temporal_source, render_camera_contact_sheet,
)


class NativeCameraSeedError(ValueError):
    """Original source/rights/physical evidence was absent or contradictory."""


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stage_attested_camera(camera, rights_manifest, staging, evidence_root):
    """Prepare one verified camera recording for direct native editor import.

    Source rights remain *claims* supplied by a source manifest. This requires
    an exact matching media SHA; it does not independently establish ownership.
    """
    camera = Path(camera)
    rights_manifest = Path(rights_manifest)
    staging = Path(staging)
    evidence_root = Path(evidence_root)
    if not camera.is_file() or camera.is_symlink():
        raise NativeCameraSeedError("Camera source must be one real source file")
    if camera.suffix.lower() not in (".webm", ".mp4", ".mov", ".mkv"):
        raise NativeCameraSeedError("Camera container unsupported in native pilot")
    if not staging.is_dir() or not evidence_root.is_dir():
        raise NativeCameraSeedError("Trusted empty media/evidence folders required")
    try:
        manifest = json.loads(rights_manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NativeCameraSeedError("Rights evidence is not readable JSON") from exc
    if (not isinstance(manifest, dict) or
            manifest.get("license_declared_by_source") not in ("CC0", "CC0 1.0") or
            manifest.get("full_picture_decode_completed") is not True or
            not isinstance(manifest.get("sha256"), str) or
            re.fullmatch("[0-9a-f]{64}", manifest["sha256"]) is None):
        raise NativeCameraSeedError("No exact source attestation or declared rights")
    target = staging / ("native-original-camera" + camera.suffix.lower())
    # Exclusive destination never replaces or follows an existing user file.
    with camera.open("rb") as original, target.open("xb") as staged:
        for block in iter(lambda: original.read(1024 * 1024), b""):
            staged.write(block)
    digest = _sha(target)
    if digest != manifest["sha256"]:
        target.unlink()
        raise NativeCameraSeedError("Staged camera bytes differ from attested original")
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height",
             "-of", "json", str(target)],
            capture_output=True, text=True, check=True, timeout=60)
        info = json.loads(probe.stdout)
        streams = info["streams"]
        video = next(stream for stream in streams
                     if stream.get("codec_type") == "video")
        duration = float(info["format"]["duration"])
        if (not math.isfinite(duration) or not 30 <= duration <= 1200 or
                type(video.get("width")) is not int or video["width"] <= 0 or
                type(video.get("height")) is not int or video["height"] <= 0):
            raise NativeCameraSeedError("Camera stream lacks valid video geometry")
        claimed_duration = manifest.get("duration_seconds")
        if (type(claimed_duration) in (int, float) and
                abs(claimed_duration - duration) > .25):
            raise NativeCameraSeedError("Camera stream disagrees with source manifest")
        timeline = inspect_raw_temporal_source(target, duration)
        picture = evidence_root / "native-camera-contact-sheet.png"
        receipt = render_camera_contact_sheet(
            target, duration, timeline["contact_sheet_sample_times_seconds"], picture)
        if receipt["actual_video_sha256"] != digest:
            raise NativeCameraSeedError("Camera changed during physical observation")
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, StopIteration) as exc:
        if isinstance(exc, NativeCameraSeedError):
            raise
        raise NativeCameraSeedError("Source/physical temporal observation failed") from exc

    record = {
        "path": str(target), "sha256": digest,
        "rights": "CC0 declared in source metadata; legal clearance not independently proved",
        "media_origin": "unaltered_authorized_original_camera_recording",
        "source_duration_seconds": duration,
        "source_dimensions": [video["width"], video["height"]],
        "source_has_audio": any(s.get("codec_type") == "audio" for s in streams),
        "camera_preview_path": str(picture),
        "camera_preview_sha256": receipt["thumbnail_sha256"],
        "temporal_observation": timeline,
        "original_manifest_full_decode_claim_not_repeated_as_a_new_full_decode": True,
        "native_import_uses_original_bytes_not_prebaked_edit_segments": True,
    }
    (evidence_root / "native-camera-evidence.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")
    return record
