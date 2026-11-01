"""Source-attested visual review and one model-selected, sparse editorial revision.

This is a reusable technical instrument, not an art critic, sound listener, or
relabelled storyboard. Preview samples come from the actually encoded movie.
A model's edit request cannot execute code or grant itself media identities.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import math
import os
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw


class ModelFilmRevisionError(ValueError):
    """A proposed creative revision is malformed or lacks physical evidence."""


_EDITABLE_FIELDS = frozenset({"artwork", "caption", "camera", "weight"})
_CAMERA_CONTROLS = frozenset({
    "push", "pull", "drift_left", "drift_right", "still"
})


def apply_model_selected_revision(plan, decision, *, asset_count):
    """Return a *new* plan and a truthfully classified sparse edit receipt.

    The caller must still validate full film semantics, render, decode and
    compare real source-bound artifacts before claiming that anything changed.
    """
    if (not isinstance(plan, dict) or not isinstance(plan.get("beats"), list)
            or not plan["beats"] or not isinstance(decision, dict)
            or type(asset_count) is not int or asset_count <= 0):
        raise ModelFilmRevisionError("Valid original plan, decision and asset inventory required")
    if set(decision) != {"action", "beat_index", "field", "value", "reason",
                         "expected_before"}:
        raise ModelFilmRevisionError("Model revision must match exact admitted fields")
    if (decision["action"] not in ("keep", "revise")
            or type(decision["beat_index"]) is not int
            or not 0 <= decision["beat_index"] < len(plan["beats"])
            or not isinstance(decision["field"], str)
            or decision["field"] not in _EDITABLE_FIELDS
            or not isinstance(decision["value"], str)
            or not isinstance(decision["expected_before"], str)
            or not isinstance(decision["reason"], str)
            or not 12 <= len(decision["reason"].strip()) <= 600):
        raise ModelFilmRevisionError("Model must give a bounded, grounded editorial decision")
    if decision["action"] == "keep":
        return deepcopy(plan), {
            "action": "keep", "revision_applied": False,
            "reason": decision["reason"], "changed_fields": []
        }

    beat_index = decision["beat_index"]
    field = decision["field"]
    value = decision["value"]
    updated = deepcopy(plan)
    beat = updated["beats"][beat_index]
    if not isinstance(beat, dict) or field not in beat:
        raise ModelFilmRevisionError("Target beat is not a native editable field")
    previous = beat[field]
    # Compare-and-swap over actual native source state, not a model's imagined
    # prior caption/parameter. In an actual neural run the model confused an
    # adjacent silhouette beat with a textile beat. An unverified critique
    # cannot be authority for rewriting a different object's native state.
    if decision["expected_before"] != str(previous):
        raise ModelFilmRevisionError(
            "Model's previous field value does not match target native beat")
    if field == "caption":
        if not 3 <= len(value) <= 100 or not value.strip():
            raise ModelFilmRevisionError("Caption revision must be visible and bounded")
        replacement = value
    elif field == "camera":
        if value not in _CAMERA_CONTROLS:
            raise ModelFilmRevisionError("Camera revision must use a real registered control")
        replacement = value
    elif field == "artwork":
        if not value.isascii() or not value.isdecimal() or str(int(value)) != value:
            raise ModelFilmRevisionError("Art source index must be a canonical integer")
        replacement = int(value)
        if replacement >= asset_count:
            raise ModelFilmRevisionError("Requested artwork is absent from the verified inventory")
    else:
        try:
            decimal = Decimal(value)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ModelFilmRevisionError("Pacing change must be an ordinary finite decimal") from exc
        if (not decimal.is_finite() or decimal <= 0 or decimal > 1000000
                or len(value) > 48):
            raise ModelFilmRevisionError("Pacing change is outside the native edit budget")
        replacement = float(decimal)
        if not math.isfinite(replacement) or replacement <= 0:
            raise ModelFilmRevisionError("Pacing change is not representable by native render")
    if previous == replacement:
        raise ModelFilmRevisionError("Model selected a no-op, not an actual revision")
    beat[field] = replacement
    return updated, {
        "action": "revise", "revision_applied": True,
        "reason": decision["reason"], "beat_index": beat_index,
        "field": field, "before": previous, "after": replacement,
        "previous_field_model_attested_to_host_state":True,
        "model_reason_is_not_independently_verified_artistic_quality":True,
        "changed_fields": [f"beats[{beat_index}].{field}"]
    }


def encoded_film_contact_sheet(movie, beat_frames, destination, *, fps,
                               sample_width=320):
    """Sample actual encoded middle frames, not source stills or plan mockups.

    Source identity is independently checked before and after all frame reads.
    Each sampled frame is retained only in the returned compact PNG collage.
    """
    if (not isinstance(beat_frames, list) or not 1 <= len(beat_frames) <= 32
            or any(type(n) is not int or n < 2 for n in beat_frames)
            or type(fps) is not int or not 1 <= fps <= 120
            or type(sample_width) is not int or not 128 <= sample_width <= 640):
        raise ModelFilmRevisionError("Invalid actual film preview timing or physical budget")
    movie = Path(movie).resolve(strict=True)
    if not movie.is_file():
        raise ModelFilmRevisionError("Preview must read an actual encoded movie")
    with movie.open("rb") as stream:
        original_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    cols = min(4, len(beat_frames))
    rows = math.ceil(len(beat_frames) / cols)
    tile_height = round(sample_width * 9 / 16)
    label_height = 32
    sheet = Image.new("RGB", (cols * sample_width,
                              rows * (tile_height + label_height)), "#10151d")
    draw = ImageDraw.Draw(sheet)
    cursor = 0
    for index, nframes in enumerate(beat_frames):
        # Pick a frame inside the actual decoded interval, not on a cut edge.
        middle_frame = cursor + nframes // 2
        at_seconds = middle_frame / fps
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-protocol_whitelist", "file,pipe",
            "-ss", format(at_seconds, ".9f"), "-i", str(movie),
            "-map", "0:v:0", "-frames:v", "1", "-an",
            "-vf", f"scale={sample_width}:{tile_height}:flags=fast_bilinear",
            "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
        ]
        try:
            decoded = subprocess.run(
                command, capture_output=True, timeout=45, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ModelFilmRevisionError("Unable to decode real review frame") from exc
        if not 200 <= len(decoded.stdout) <= 2_000_000:
            raise ModelFilmRevisionError("Decoded review frame unavailable or oversized")
        from io import BytesIO
        try:
            with Image.open(BytesIO(decoded.stdout)) as frame:
                frame.load()
                if frame.size != (sample_width, tile_height):
                    raise ModelFilmRevisionError("Decoded preview geometry mismatch")
                tile = frame.convert("RGB")
        except (OSError, ValueError) as exc:
            raise ModelFilmRevisionError("Malformed decoded native review frame") from exc
        x = (index % cols) * sample_width
        y = (index // cols) * (tile_height + label_height)
        sheet.paste(tile, (x, y))
        # Only physical index/time metadata; no invented image understanding.
        draw.text((x + 8, y + tile_height + 7),
                  f"Beat {index + 1} | {at_seconds:.2f}s",
                  fill="#f2f2f2")
        cursor += nframes
    with movie.open("rb") as stream:
        final_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    if original_sha != final_sha:
        raise ModelFilmRevisionError("Source movie changed during decoded review")
    destination = Path(destination)
    # O_EXCL|O_NOFOLLOW closes the dangling-symlink and check/create races:
    # a preview is a new immutable evidence file, never an overwrite.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(destination, flags, 0o600)
    except OSError as exc:
        raise ModelFilmRevisionError(
            "Review destination already exists or cannot be created safely") from exc
    try:
        with os.fdopen(descriptor, "wb") as sink:
            sheet.save(sink, format="PNG")
            sink.flush()
            os.fsync(sink.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    with destination.open("rb") as stream:
        sheet_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"source_sha256": original_sha,
            "preview_sha256": sheet_sha,
            "preview_path": str(destination),
            "decoded_frame_count": len(beat_frames),
            "source_frame_count": cursor,
            "fps": fps,
            "picture_is_a_temporal_sample_not_continuous_motion": True,
            "audio_has_not_been_listened_to": True,
            "artistic_quality_not_certified": True}
