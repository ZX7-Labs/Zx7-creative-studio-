"""Physical owner-media custody for genuine model-to-editor technical trials.

A native model can create a project, markers, solids and titles without using
the caller's actual video. These are not evidence that it edited source footage.
This verifier proves a *project-owned byte-exact copy* of a host-supplied video
is present as a real timeline clip in a native saved project. It never decides
a creative operation or inserts media. Only test-runner acceptance uses it.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path


def _unique_project_json_fields(pairs):
    """Reject ambiguous persisted identity before any custody verdict.

    Native JSON.stringify never emits duplicate object keys; accepting a
    manually constructed duplicate-id receipt would create parser-dependent
    source evidence.
    """
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("Native project contains duplicate JSON fields")
        values[key] = value
    return values


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_unique_native_ids(items: list, label: str) -> None:
    """Refuse ambiguous IDs rather than infer how an editor resolves duplicates."""
    ids = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError(f"Native {label} identity is missing or ambiguous")
        ids.append(item["id"])
    if len(ids) != len(set(ids)):
        raise ValueError(f"Native {label} identity is ambiguous")


def _finite_real(value) -> bool:
    # Native timeline clock fields must be finite numeric values. Python's
    # bool is not a time position; huge integers must not overflow isfinite.
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _native_clip_playback_window(clip: dict) -> tuple[float, float] | None:
    """Mirror pinned Electron getClipPlaybackWindow and reject malformed clocks.

    The native exporter restricts clip frame eligibility to the intersected
    authored/playback window. Its Number coercions are not sufficient as
    independent original-footage provenance, so accept finite numbers only.
    """
    origin, length = clip.get("startTime"), clip.get("duration")
    if (not _finite_real(origin) or not _finite_real(length) or
            not 0 < length <= 1_000_000):
        return None
    end = origin + length
    if not math.isfinite(end):
        return None
    lower = clip.get("playbackWindowStart", origin)
    upper = clip.get("playbackWindowEnd", end)
    if not _finite_real(lower) or not _finite_real(upper):
        return None
    beginning, finish = max(origin, lower), min(end, upper)
    if beginning >= finish:
        return None
    return beginning, finish


def _static_native_video_visibility(clip: dict) -> bool:
    """Reject a source video invisible from its own saved transform.

    Pinned Velorn src/services/exporter.js computes video base opacity as
    transform.opacity/100, default 100. Zero is transparent. This is a
    conservative proof rule: animated opacity and occlusion by other tracks
    still require rendered-frame inspection.
    """
    transform = clip.get("transform", {})
    if not isinstance(transform, dict):
        return False
    opacity = transform.get("opacity", 100)
    if not _finite_real(opacity) or opacity <= 0:
        return False
    # Pinned exporter.js applyClipCrop clips against a nonnegative crop
    # rectangle. Opposing trims that consume the entire height/width leave
    # exactly ZERO original-video pixels, regardless of import provenance.
    # getVisibleLocalRect also clamps crop percentages into [0,100].
    for first, second in (("cropLeft", "cropRight"),
                          ("cropTop", "cropBottom")):
        a, b = transform.get(first, 0), transform.get(second, 0)
        if not _finite_real(a) or not _finite_real(b):
            return False
        if max(0, min(100, a)) + max(0, min(100, b)) >= 100:
            return False
    return True


def verify_original_footage_on_native_timeline(
        projects_root: Path, project_paths: list[Path],
        caller_source_assets: list[dict],
        host_verified_export_windows: list[dict] | None = None) -> dict:
    """Produce independently checkable technical provenance, never QA approval.

    Require both the host-owned original video SHA and the *copied* project
    asset to be byte-identical; source provenance alone could be forged.
    The native project must reference that exact copied asset through a
    real clip on a timeline; synthetic shapes/text are insufficient.

    If the trusted runner supplies source-bound physical export windows, each
    candidate clip must intersect one of those output intervals. A caller may
    NOT populate these windows from unverified model text. With no windows,
    report native-timeline custody only, not visible export-frame certainty.
    """
    root = Path(projects_root).resolve(strict=True)
    if not root.is_dir() or not isinstance(project_paths, list) or not isinstance(
            caller_source_assets, list):
        raise ValueError("Real editor projects and source manifest required")
    sources = {}
    for item in caller_source_assets:
        if not isinstance(item, dict):
            raise ValueError("Untrusted source manifest object")
        raw, expected = item.get("path"), item.get("sha256")
        if (not isinstance(raw, str) or not isinstance(expected, str) or
                len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected)):
            raise ValueError("Original source must have a host-attested SHA-256")
        source = Path(raw)
        if not source.is_absolute():
            raise ValueError("Original input must be an absolute host path")
        source = source.resolve(strict=True)
        if not source.is_file() or source.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm"}:
            raise ValueError("Original video source missing")
        if _sha256(source) != expected:
            raise ValueError("Original source bytes changed after host hash")
        # The host may bind a measured video-stream duration to the exact
        # byte-verified original. A file extension or SHA alone cannot prove
        # whether the editor is sampling beyond the available source frames.
        # An absent duration is acceptable for project-only custody, never
        # for delivered-footage proof that relies on sampled source time.
        measured_duration = item.get("video_duration_seconds")
        if measured_duration is not None and (
                not _finite_real(measured_duration) or
                not 0 < measured_duration <= 1_000_000):
            raise ValueError("Invalid host-measured original video duration")
        sources[str(source)] = {
            "sha256": expected, "video_duration_seconds": measured_duration,
        }
    # A delivered render cannot be attributed to one of several saved
    # projects merely because a matching clip exists SOMEWHERE in the trial.
    # The runner presently supplies independently verified MP4 time windows,
    # but not an immutable per-project export-identity receipt. In this scope,
    # accept a single unambiguous project or withhold delivered-source proof.
    # Multi-project projects remain valid native workspaces; they require a
    # separate exact active-project/export binding for final certification.
    if host_verified_export_windows is not None and len(project_paths) > 1:
        raise ValueError(
            "Verified export source identity is ambiguous across native projects")
    # A non-None empty list deliberately proves no delivered export.
    # This is a host/runner input, never extracted from mutable project JSON.
    if host_verified_export_windows is not None:
        if (not isinstance(host_verified_export_windows, list) or
                len(host_verified_export_windows) > 64):
            raise ValueError("Host export windows must be a bounded list")
        checked_windows = []
        for interval in host_verified_export_windows:
            if (not isinstance(interval, dict) or
                    set(interval) != {"start_seconds", "end_seconds"} or
                    not _finite_real(interval["start_seconds"]) or
                    not _finite_real(interval["end_seconds"]) or
                    not 0 <= interval["start_seconds"] < interval["end_seconds"]):
                raise ValueError("Invalid independently verified export interval")
            checked_windows.append((
                interval["start_seconds"], interval["end_seconds"]))
    else:
        checked_windows = None
    accepted = []
    for path in project_paths:
        project = Path(path).resolve(strict=True)
        if (not project.is_file() or not project.is_relative_to(root) or
                project.name != "project.comfystudio"):
            raise ValueError("Native project is outside owned test root")
        # Trial projects and original source manifest are host-created; the
        # model controls only native editor operations, never these files.
        # Guard parser resource consumption; the bounded CPU acceptance trial
        # never requires a multi-gigabyte saved project.
        if project.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Native project exceeds technical proof size limit")
        data = json.loads(project.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_project_json_fields)
        if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
            raise ValueError("Native project assets are absent or invalid")
        timelines = data.get("timelines")
        if not isinstance(timelines, list):
            raise ValueError("Native project timeline inventory is invalid")
        # Resolve native identity ambiguity before using any asset/timeline
        # reference to certify footage custody.
        _require_unique_native_ids(data["assets"], "asset")
        _require_unique_native_ids(timelines, "timeline")
        # The editor exports the ACTIVE timeline. A source imported into a
        # dormant timeline, or a disabled/muted picture lane, is not proof
        # that the delivered movie actually used original video footage.
        current_timeline_id = data.get("currentTimelineId")
        if not isinstance(current_timeline_id, str) or not current_timeline_id:
            raise ValueError("Saved native project has no active timeline identity")
        # The same imported asset may legitimately occur in several distinct
        # native clips. An asset count is not a clip count.
        placed = {}
        found_active = False
        for timeline in timelines:
            if not isinstance(timeline, dict) or not isinstance(timeline.get("clips"), list):
                raise ValueError("Native timeline clips malformed")
            if timeline.get("id") != current_timeline_id:
                continue
            found_active = True
            active_duration = timeline.get("duration")
            if not _finite_real(active_duration) or active_duration <= 0:
                raise ValueError("Active native timeline has no finite positive duration")
            tracks = timeline.get("tracks")
            if not isinstance(tracks, list):
                raise ValueError("Native active track inventory is missing")
            _require_unique_native_ids(tracks, "active track")
            _require_unique_native_ids(timeline["clips"], "active clip")
            # Native store persists boolean flags. On malformed saved JSON
            # pinned JavaScript fallback `!== false` can treat nonbooleans
            # as visible; independent proof requires actual boolean state.
            # Pinned native export default range is [0, max(project
            # timeline.duration, every saved clip start + duration)] in
            # electron/mcpServer.js:resolveExportDeliveryPlan. A clip after
            # the displayed timeline duration therefore extends a FULL export.
            # Never infer actual custom export range from this metadata alone.
            full_export_end = active_duration
            for entry in timeline["clips"]:
                if (isinstance(entry, dict) and
                        _finite_real(entry.get("startTime")) and
                        _finite_real(entry.get("duration"))):
                    end = entry["startTime"] + entry["duration"]
                    if math.isfinite(end):
                        full_export_end = max(full_export_end, end)
            effective_windows = (checked_windows if checked_windows is not None
                                 else [(0, full_export_end)])
            # The actual pinned renderer filters tracks with
            # src/utils/videoTrackVisibility.js:isVideoTrackVisible.
            # A video track marked muted contributes NO pixels, and an
            # independently soloed video track hides every other video
            # track even when their eye/visible flag remains true.
            # Do not claim caller-original footage when the native
            # compositor cannot select that track.
            any_video_solo = any(
                isinstance(track, dict) and
                track.get("type") == "video" and
                track.get("solo", False) is True
                for track in tracks)
            visible_video_tracks = {
                track["id"] for track in tracks
                if isinstance(track, dict) and
                isinstance(track.get("id"), str) and
                track.get("type") == "video" and
                track.get("visible", True) is True and
                track.get("muted", False) is False and
                type(track.get("solo", False)) is bool and
                (not any_video_solo or track.get("solo", False) is True)}
            for clip in timeline["clips"]:
                playback_window = (_native_clip_playback_window(clip)
                                   if isinstance(clip, dict) else None)
                if (isinstance(clip, dict) and
                        clip.get("type") == "video" and
                        clip.get("enabled", True) is True and
                        _static_native_video_visibility(clip) and
                        # With useCachedRenders enabled, pinned exporter.js
                        # replaces even a VIDEO clip's actual source decoder
                        # with clip.cacheUrl/cachePath when status='cached'.
                        # An unverified baked/legacy cache can carry entirely
                        # unrelated pixels. Its presence cannot certify that
                        # owner-original BYTES entered the delivered movie.
                        # Preserve project-only custody separately.
                        not (checked_windows is not None and
                             clip.get("cacheStatus") == "cached" and
                             (clip.get("cacheUrl") or clip.get("cachePath"))) and
                        clip.get("trackId") in visible_video_tracks and
                        isinstance(clip.get("assetId"), str) and
                        playback_window is not None and
                        any(playback_window[0] < finish and
                            playback_window[1] > begin
                            for begin, finish in effective_windows)):
                    placed.setdefault(clip["assetId"], []).append(clip)
        if not found_active:
            raise ValueError("Active native timeline was not saved")
        for asset in data["assets"]:
            if not isinstance(asset, dict) or asset.get("type") != "video":
                continue
            asset_id = asset.get("id")
            settings = asset.get("settings")
            if (not isinstance(asset_id, str) or asset_id not in placed or
                    not isinstance(settings, dict) or
                    settings.get("importedViaMcp") is not True):
                continue
            previous = settings.get("sourcePath")
            if not isinstance(previous, str):
                continue
            # A saved editor project is not authority to make the trial
            # verifier open arbitrary host paths. Check the exact caller-
            # attested source identity BEFORE resolving or accessing it.
            original_record = sources.get(previous)
            if not original_record:
                continue
            owner_hash = original_record["sha256"]
            original_duration = original_record["video_duration_seconds"]
            original = Path(previous)
            # Pinned Velorn src/services/exporter.js:getExportAssetPath
            # prioritizes a nonempty absolutePath over path. The former
            # verifier tried both independently: a forged invalid
            # absolutePath could be "rescued" by a different, honest path
            # even though the native renderer would select absolutePath.
            # Never borrow source custody from a fallback that the actual
            # application is not known to render.
            absolute = asset.get("absolutePath")
            asset_location = (absolute if isinstance(absolute, str) and
                              absolute.strip() else asset.get("path"))
            if not isinstance(asset_location, str) or not asset_location.strip():
                continue
            if "://" in asset_location:
                continue
            owned = Path(asset_location)
            if not owned.is_absolute():
                owned = project.parent / owned
            owned = owned.resolve(strict=False)
            if (owned == original or
                    not owned.is_relative_to(project.parent) or
                    not owned.is_file()):
                continue
            # A hard link aliases the original inode; the native project
            # must own an independent copy before any edit is accepted.
            if os.path.samefile(owned, original):
                continue
            if _sha256(owned) != owner_hash:
                continue
            for native_clip in placed[asset_id]:
                # Original source frames must remain in-range after trim.
                source_in = native_clip.get("trimStart", 0)
                if (not _finite_real(source_in) or source_in < 0 or
                        (checked_windows is not None and
                         (original_duration is None or
                          source_in >= original_duration))):
                    continue
                accepted.append({
                    "relative_native_project_file": str(project.relative_to(root)),
                    "native_asset_id": asset_id,
                    "native_clip_id": native_clip["id"],
                    "source_trim_start_seconds": source_in,
                    "source_sha256": owner_hash,
                    "project_owned_copy_sha256": owner_hash,
                })
    return {
        "actual_original_video_used_on_native_timeline": bool(accepted),
        "physically_verified_native_source_clip_count": len(accepted),
        "verified_native_source_clip_proof": accepted,
        "professional_artistic_quality_approved": False,
    }
