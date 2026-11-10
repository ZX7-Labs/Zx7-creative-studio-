"""Owner-authorized delivery constraint and real native export plan validation.

This finite contract describes the *owner's requested deliverable*, never a
model-authored decision or a predetermined creative edit. Without opt-in, the
native editor's own export resolution/aspect/preset semantics are unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from types import MappingProxyType


DELIVERY_KEYS = frozenset({"width", "height", "fps", "max_duration", "video_codec"})


def admitted_owner_delivery(value):
    """Return a frozen validated profile or None; reject any ambiguous fields."""
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != DELIVERY_KEYS:
        raise ValueError("Owner export delivery contract fields are missing or unknown")
    for field in ("width", "height"):
        size = value[field]
        if type(size) is not int or size < 2 or size > 16384 or size % 2:
            raise ValueError("Owner export dimensions must be even bounded integers")
    fps, duration = value["fps"], value["max_duration"]
    if (type(fps) not in (int, float) or not math.isfinite(fps)
            or not 1 <= fps <= 240):
        raise ValueError("Owner export FPS must be finite and bounded")
    if (type(duration) not in (int, float) or not math.isfinite(duration)
            or not 0 < duration <= 7200):
        raise ValueError("Owner maximum export duration must be finite and bounded")
    if value["video_codec"] not in ("h264", "h265"):
        raise ValueError("Owner video codec must be an admitted native delivery codec")
    return MappingProxyType(dict(value))


def native_delivery_matches(native_readiness, approved):
    """Compare the actual pinned editor's *read-only* export deliveryTarget.

    Strict numeric types prevent '640', True and NaN from masquerading as
    physical dimensions. This NEVER certifies output bytes: separate FFprobe
    and full-decode inspection are still required after each real export.
    """
    if not isinstance(native_readiness, dict) or not isinstance(approved, Mapping):
        return False
    observed = native_readiness.get("deliveryTarget")
    if not isinstance(observed, dict):
        return False
    if observed.get("container") != "mp4" or observed.get("videoCodec") != approved["video_codec"]:
        return False
    for name in ("width", "height"):
        if type(observed.get(name)) is not int or observed[name] != approved[name]:
            return False
    for name in ("fps", "duration"):
        item = observed.get(name)
        if type(item) not in (int, float) or not math.isfinite(item):
            return False
    if not math.isclose(observed["fps"], approved["fps"], rel_tol=0, abs_tol=0.001):
        return False
    if observed["duration"] <= 0 or observed["duration"] > approved["max_duration"] + 1e-6:
        return False
    return True
