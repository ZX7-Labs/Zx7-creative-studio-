"""Licensed local-only full-frame shot detection via independent PySceneDetect.

The model selects whether to inspect an authorized reference. This is factual
shot-transition instrumentation, not a creative grade, causal audience claim,
internet downloader or permission to reuse another author's footage.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from .reference_observatory import ReferenceObservationError, _probe


def detect_authorized_shots(reference_root, reference, *,
                            method="adaptive", max_seconds=3600, max_scenes=2048):
    """Use PySceneDetect v0.7, rather than inventing another shot algorithm."""
    if (not isinstance(reference, str) or not 1 <= len(reference) <= 1024
            or type(max_seconds) is not int or not 1 <= max_seconds <= 86400
            or type(max_scenes) is not int or not 1 <= max_scenes <= 16384):
        raise ReferenceObservationError("Invalid bounded host reference request")
    if method not in ("adaptive", "content", "fade_to_black"):
        raise ReferenceObservationError("Unregistered shot detection method")
    candidate = Path(reference)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ReferenceObservationError("Reference path must stay inside host grant")
    root = Path(reference_root).resolve(strict=True)
    if not root.is_dir():
        raise ReferenceObservationError("Missing local host reference folder")
    try:
        movie = (root / candidate).resolve(strict=True)
    except OSError as exc:
        raise ReferenceObservationError("Reference media is unavailable") from exc
    if not movie.is_relative_to(root) or not movie.is_file():
        raise ReferenceObservationError("Reference escaped host's granted folder")
    duration, _, video = _probe(movie)
    if duration > max_seconds:
        raise ReferenceObservationError("Full-frame shot scan exceeds host duration budget")
    try:
        import scenedetect
        from scenedetect import AdaptiveDetector, ContentDetector, ThresholdDetector
    except ImportError as exc:
        raise ReferenceObservationError(
            "Install the open-source research_video extra for full-frame scene detection") from exc
    detectors = {
        "adaptive": lambda: AdaptiveDetector(
            adaptive_threshold=3.0, min_content_val=15.0, min_scene_len="0.25s"),
        "content": lambda: ContentDetector(
            threshold=27.0, min_scene_len="0.25s"),
        "fade_to_black": lambda: ThresholdDetector(
            threshold=12, min_scene_len="0.25s")
    }
    try:
        scenes = scenedetect.detect(str(movie), detectors[method](),
                                   show_progress=False, backend="opencv")
    except Exception as exc:
        raise ReferenceObservationError("Open-source shot detector could not decode input") from exc
    if not scenes:
        raise ReferenceObservationError("No decodable shot intervals")
    if len(scenes) > max_scenes:
        raise ReferenceObservationError("Scene count exceeds host observation budget")
    starts, ranges = [], []
    last_end = None
    for i, (start, end) in enumerate(scenes):
        s, e = float(start.get_seconds()), float(end.get_seconds())
        if (not math.isfinite(s) or not math.isfinite(e)
                or s < 0 or e <= s
                or (last_end is not None and abs(s-last_end) > 0.2)):
            raise ReferenceObservationError("Detector returned invalid shot boundaries")
        last_end = e
        ranges.append({"start_seconds": round(s, 4), "end_seconds": round(e, 4)})
        if i:
            starts.append(round(s, 4))
    with movie.open("rb") as original:
        digest = hashlib.file_digest(original, "sha256").hexdigest()
    return {
        "schema": "ZX7_PYSCENEDETECT_SHOT_EVIDENCE_V1",
        "source_sha256": digest,
        "duration_seconds": round(duration, 4),
        "source_resolution": [video["width"], video["height"]],
        "library": "PySceneDetect",
        "library_version": getattr(scenedetect, "__version__", "unknown"),
        "detector": method,
        "detector_follows_decoded_frame_clock": True,
        "shot_intervals": ranges,
        "cut_candidates_seconds": starts,
        "creative_quality_certified": False,
        "human_engagement_or_causality_measured": False,
        "rights_to_reuse_original_footage_verified": False,
        "limits": "Shot breaks are estimates, fades and fast camera motion can confuse algorithms",
    }
