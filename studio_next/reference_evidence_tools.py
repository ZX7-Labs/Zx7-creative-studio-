"""Host-granted compact editing graphs for a reference AI is allowed to study.

A user supplies local media within a host-owned root. No network video is
downloaded; model input cannot expand its filesystem authority. Only numeric
traces are returned, not private original frames or PCM audio.
"""
from __future__ import annotations

from pathlib import Path
from .reference_observatory import ReferenceObservationError, observe_reference


def inspect_authorized_reference(reference_root, reference, *, bins=64):
    if type(bins) is not int or not 8 <= bins <= 256:
        raise ReferenceObservationError("Invalid editing graph bin count")
    if not isinstance(reference, str) or not reference or len(reference) > 1024:
        raise ReferenceObservationError("Authorized relative reference path required")
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts:
        raise ReferenceObservationError("Reference escapes host root")
    root = Path(reference_root).resolve(strict=True)
    if not root.is_dir():
        raise ReferenceObservationError("Host reference root is not a directory")
    try:
        path = (root/relative).resolve(strict=True)
    except OSError as exc:
        raise ReferenceObservationError("Reference not found within host root") from exc
    if not path.is_relative_to(root) or not path.is_file():
        raise ReferenceObservationError("Reference outside host-approved workspace")
    report = observe_reference(path)
    duration = report["duration_seconds"]
    visual = [{"count": 0, "difference_total": 0., "difference_max": 0.,
               "luma_total": 0., "chroma_total": 0.,
               "rgb_total": [0., 0., 0.]} for _ in range(bins)]
    sound = [{"count": 0, "rms_dbfs_total": 0., "peak_dbfs_max": -120.}
             for _ in range(bins)]
    for item in report["visual_observations"]:
        index = min(bins-1, int(item["second"]*bins/duration))
        value = visual[index]
        value["count"] += 1
        value["difference_total"] += item["frame_difference"]
        value["luma_total"] += item["luma"]
        value["chroma_total"] += item["mean_chroma"]
        value["rgb_total"] = [a+b for a,b in zip(value["rgb_total"], item["mean_rgb"])]
        value["difference_max"] = max(value["difference_max"],
                                      item["frame_difference"])
    for item in report["audio_observations"]:
        index = min(bins-1, int(item["second"]*bins/duration))
        value = sound[index]
        value["count"] += 1
        value["rms_dbfs_total"] += item["rms_dbfs"]
        value["peak_dbfs_max"] = max(value["peak_dbfs_max"], item["peak_dbfs"])
    graph = []
    for index, (v, a) in enumerate(zip(visual, sound)):
        graph.append({
            "from_seconds": round(index*duration/bins, 3),
            "motion_energy_mean":
                round(v["difference_total"]/v["count"], 4) if v["count"] else None,
            "motion_energy_peak":
                round(v["difference_max"], 4) if v["count"] else None,
            "mean_luminance":
                round(v["luma_total"]/v["count"], 4) if v["count"] else None,
            "mean_chroma":
                round(v["chroma_total"]/v["count"], 4) if v["count"] else None,
            "mean_rgb":
                [round(x/v["count"], 4) for x in v["rgb_total"]] if v["count"] else None,
            "audio_rms_dbfs":
                round(a["rms_dbfs_total"]/a["count"], 2) if a["count"] else None,
            "audio_peak_dbfs":
                round(a["peak_dbfs_max"], 2) if a["count"] else None,
        })
    cut_times = report["cut_candidates_seconds"]
    return {
        "schema": "ZX7_AUTHORIZED_REFERENCE_GRAPH_V1",
        "source_sha256": report["source_sha256"],
        "duration_seconds": duration,
        "source_resolution": report["source_resolution"],
        "has_audio": report["has_audio"],
        "visual_sample_fps": report["visual_sample_fps"],
        "cut_candidate_count": len(cut_times),
        "cut_candidate_samples": cut_times[:256],
        "cut_candidate_samples_truncated": len(cut_times) > 256,
        "graph": graph,
        "limits": report["limits"],
        "original_video_bytes_retained": False,
        "model_has_understood_story_or_editing_intent": False,
    }
