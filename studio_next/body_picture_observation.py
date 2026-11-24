"""Bounded local picture sensor for existing BODY-authored or owner-granted PNGs.

Read permission and workspace scope authorize observation; the expected digest
only binds the observed bytes, never establishes rights or creative quality.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import re
import stat

from .body_editor_frame import _verified_png_dimensions

TOOL = "body.observe_picture"
SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["source", "source_sha256"], "properties": {
              "source": {"type": "string"},
              "source_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"}}}
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_MAX_SOURCE = 40 * 1024 * 1024
_MAX_PIXELS = 16 * 1024 * 1024
_MAX_PREVIEW = 4 * 1024 * 1024
_PRIVATE_ROOTS = frozenset({"state", "sessions", "vault"})


def observe_picture(workspace, inputs):
    """Read one exact local PNG through no-follow directory descriptors."""
    from PIL import Image

    if (not isinstance(inputs, dict) or set(inputs) != {"source", "source_sha256"}
            or not isinstance(inputs["source"], str)
            or not isinstance(inputs["source_sha256"], str)
            or not _DIGEST.fullmatch(inputs["source_sha256"])):
        raise ValueError("Picture observation needs an exact workspace source and SHA256")
    source = inputs["source"]
    parts = source.split("/")
    if (not parts or any(not p or p.startswith(".") or "\\" in p for p in parts)
            or parts[0] in _PRIVATE_ROOTS or Path(source).suffix.lower() != ".png"):
        raise ValueError("Only non-private, relative workspace PNG sources are observable")
    fd = None
    try:
        fd = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        image_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(image_fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= _MAX_SOURCE:
                raise ValueError("Picture source must be a bounded regular file")
            encoded = stream.read(_MAX_SOURCE + 1)
            after = os.fstat(stream.fileno())
            if (len(encoded) != before.st_size or len(encoded) > _MAX_SOURCE or
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                raise ValueError("Picture source changed while observing")
    except OSError as exc:
        raise ValueError("Picture source unavailable or linked outside its owner scope") from exc
    finally:
        if fd is not None:
            os.close(fd)
    sha = hashlib.sha256(encoded).hexdigest()
    if sha != inputs["source_sha256"]:
        raise ValueError("Picture source no longer matches the requested digest")
    with Image.open(io.BytesIO(encoded)) as original:
        width, height = original.size
        if (original.format != "PNG" or getattr(original, "n_frames", 1) != 1
                or not 0 < width * height <= _MAX_PIXELS):
            raise ValueError("Picture observation needs a bounded single-frame PNG")
        original.load()
        converted = original.convert("RGBA")
        converted.thumbnail((768, 768), Image.Resampling.LANCZOS)
        # Copy pixels only; do not forward arbitrary source metadata/chunks.
        clean = Image.frombytes("RGBA", converted.size, converted.tobytes())
        out = io.BytesIO()
        clean.save(out, format="PNG")
    picture = out.getvalue()
    if len(picture) > _MAX_PREVIEW:
        raise ValueError("Picture preview exceeds the model evidence budget")
    pw, ph = _verified_png_dimensions(picture)
    receipt = {"schema": 1, "kind": "body_source_picture_preview",
               "source_sha256": sha, "png_sha256": hashlib.sha256(picture).hexdigest(),
               "source_width": width, "source_height": height,
               "preview_width": pw, "preview_height": ph,
               "physical_video_export_verified": False,
               "human_or_artistic_quality_approved": False}
    return picture, receipt


def validate_picture_receipt(receipt, picture, expected_sha256):
    """Bind the exact sensor payload, without crediting native export proof."""
    fields = {"schema", "kind", "source_sha256", "png_sha256", "source_width",
              "source_height", "preview_width", "preview_height",
              "physical_video_export_verified", "human_or_artistic_quality_approved"}
    if (not isinstance(receipt, dict) or set(receipt) != fields or
            type(receipt["schema"]) is not int or receipt["schema"] != 1 or
            receipt["kind"] != "body_source_picture_preview" or
            not isinstance(expected_sha256, str) or not _DIGEST.fullmatch(expected_sha256) or
            receipt["source_sha256"] != expected_sha256 or
            not isinstance(picture, bytes) or len(picture) > _MAX_PREVIEW or
            receipt["png_sha256"] != hashlib.sha256(picture).hexdigest() or
            receipt["physical_video_export_verified"] is not False or
            receipt["human_or_artistic_quality_approved"] is not False or
            any(type(receipt[key]) is not int or receipt[key] <= 0 for key in (
                "source_width", "source_height", "preview_width", "preview_height")) or
            receipt["source_width"] * receipt["source_height"] > _MAX_PIXELS or
            _verified_png_dimensions(picture) != (receipt["preview_width"], receipt["preview_height"]) or
            receipt["preview_width"] > receipt["source_width"] or
            receipt["preview_height"] > receipt["source_height"]):
        raise ValueError("BODY picture receipt does not match its source-bound pixels")
    return receipt["png_sha256"]
