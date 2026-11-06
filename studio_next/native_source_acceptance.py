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




def _export_samples_original_clip(playback_window, export_interval) -> bool:
    """Require a *real output frame sample* to land inside the source clip.

    Velorn src/services/exporter.js by default samples frame centers:
    rangeStart + (frameIndex + 0.5) / fps. The host runner supplies the
    independently measured H.264 video stream frame rate and decoded frame
    count. Merely overlapping an export interval for one microsecond does
    not prove any rendered frame used the original source video.
    Legacy timeline-only window fixtures without frame measurements retain
    interval-overlap custody, but CANNOT be called frame-sample proof.
    """
    begin, finish = playback_window
    start, end, fps, frame_count = export_interval
    if not (begin < end and finish > start):
        return False
    if fps is None or frame_count is None:
        return True
    # Solve the finite constant-frame-rate grid analytically instead of
    # probing a long video frame-by-frame. Frame 0 samples at half a frame.
    # The first candidate whose center is >= source clip beginning.
    earliest = max(0, math.ceil((begin - start) * fps - 0.5))
    if earliest >= frame_count:
        return False
    sample_time = start + (earliest + 0.5) / fps
    return begin <= sample_time < finish and sample_time < end




def _native_source_frame_available_at_output_sample(
        clip: dict, export_interval, original_duration: float) -> bool:
    """Conservatively bind a sampled OUTPUT frame to in-range SOURCE media.

    The pinned src/utils/clipPlaybackTiming.js maps output timeline time to
    source time via trimStart, speed, sourceTimeScale and reverse, then clamps
    into the authored trim range. The exporter uses a 0.001-second decode
    end offset. An output center that lands on a clip is NOT itself proof of
    source media: a trim can seek wholly past the last original frame.

    For optional speed-ramp keyframes, use the upstream <=16x ramp speed
    envelope (src/utils/timeRemap.js) and the clip's scalar fallback speed
    to prove a frame fits even with runtime ramp enabled/disabled. Where the
    bounds cannot prove source custody, withhold a positive verdict instead
    of approximating a model-authored creative retime.
    """
    if not _finite_real(original_duration) or original_duration <= 0:
        return False
    window = _native_clip_playback_window(clip)
    start, end, fps, count = export_interval
    if window is None or fps is None or count is None:
        return False
    begin, finish = window
    first = max(0, math.ceil((begin - start) * fps - 0.5))
    last = min(count - 1, math.ceil((finish - start) * fps - 0.5) - 1)
    if first > last:
        return False
    reverse = clip.get("reverse", False)
    if type(reverse) is not bool:
        return False
    trim_start = clip.get("trimStart", 0)
    if not _finite_real(trim_start) or trim_start < 0:
        return False
    source_scale = clip.get("sourceTimeScale")
    if source_scale is None or source_scale == 0:
        # The pinned JS source selects the FPS ratio only when *both*
        # timelineFps and sourceFps are truthy. One absent value => 1.
        timeline_fps, source_fps = (clip.get("timelineFps"),
                                    clip.get("sourceFps"))
        if timeline_fps is not None and source_fps is not None:
            if (not _finite_real(timeline_fps) or
                    not _finite_real(source_fps) or
                    timeline_fps <= 0 or source_fps <= 0):
                return False
            source_scale = timeline_fps / source_fps
        else:
            source_scale = 1
    if not _finite_real(source_scale) or not 0 < source_scale <= 1000:
        return False
    speed = clip.get("speed", 1)
    if not _finite_real(speed):
        return False
    speed = speed if speed > 0 else 1
    if not math.isfinite(speed * source_scale):
        return False
    # Pinned JS uses ?? (nullish fallback) rather than a dict-key default:
    # an EXPLICIT null trimEnd falls through to sourceDuration.
    source_end = clip.get("trimEnd")
    if source_end is None:
        source_end = clip.get("sourceDuration")
    if source_end is None:
        source_end = trim_start + clip["duration"] * speed * source_scale
    if not _finite_real(source_end):
        return False
    lower, upper = min(trim_start, source_end), max(trim_start, source_end)
    safe_max = max(lower, upper - 0.001)
    # Native playback has monotone source time under a constant-speed clip.
    # The first forward or last reverse eligible output frame minimizes the
    # resulting source timestamp. Proving this one frame in-range suffices.
    sample_index = last if reverse else first
    output_time = start + (sample_index + 0.5) / fps
    clip_local_time = output_time - clip["startTime"]
    if not 0 <= clip_local_time <= clip["duration"]:
        return False
    keyframes = clip.get("keyframes")
    ramp = (not reverse and isinstance(keyframes, dict) and
            isinstance(keyframes.get("speed"), list) and
            bool(keyframes["speed"]))
    if ramp:
        # Renderer ramps are nonnegative and capped at 16x; its runtime
        # speed-ramp switch can also fall back to this clip's scalar speed.
        # Use a guaranteed upper bound, not a guessed interpolation.
        raw_upper = (trim_start + clip_local_time * source_scale *
                     max(16, speed))
        if not math.isfinite(raw_upper):
            return False
        raw_source = raw_upper
    elif reverse:
        raw_source = source_end - clip_local_time * source_scale * speed
    else:
        raw_source = trim_start + clip_local_time * source_scale * speed
    if not math.isfinite(raw_source):
        return False
    # For ramps, this is a worst-case upper bound; a trim-clamped source
    # sample can only be at or BELOW it. For normal clips this is exact.
    source_time = max(lower, min(raw_source, safe_max))
    return 0 <= source_time < original_duration


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
    if not _finite_real(opacity):
        return False
    keyframes = clip.get("keyframes")
    if keyframes is not None and not isinstance(keyframes, dict):
        return False
    animated_opacity = (keyframes.get("opacity")
                        if isinstance(keyframes, dict) else None)
    if animated_opacity is not None:
        # Pinned src/utils/keyframes.js:getAnimatedTransform overrides
        # transform.opacity whenever keyframes.opacity is a nonempty
        # list. A clip with base opacity=100 and ONE zero alpha
        # keyframe renders fully transparent for its *entire* lifespan.
        # Any number of zero-valued keyframes also stays identically
        # zero under the native easing/interpolation algebra.
        # This rejects a source-known impossibility without guessing
        # the artist's intended animation or rewriting its keyframes.
        if (not isinstance(animated_opacity, list) or
                len(animated_opacity) > 100_000):
            return False
        if animated_opacity:
            if any(not isinstance(frame, dict) or
                   not _finite_real(frame.get("time")) or
                   not _finite_real(frame.get("value"))
                   for frame in animated_opacity):
                return False
            if all(frame["value"] == 0 for frame in animated_opacity):
                return False
    # getAnimatedTransform overrides static alpha for every frame when
    # opacity keyframes are present. A 0% base with an animated 100%
    # source is therefore valid; only a truly static/empty alpha track
    # can use the saved base value to prove permanent invisibility.
    if opacity <= 0 and not animated_opacity:
        return False
    # Pinned exporter.js applyClipCrop clips against a nonnegative crop
    # rectangle. Opposing trims that consume the entire height/width leave
    # exactly ZERO original-video pixels, regardless of import provenance.
    # getVisibleLocalRect also clamps crop percentages into [0,100].
    for first, second in (("cropLeft", "cropRight"),
                          ("cropTop", "cropBottom")):
        values = []
        for key in (first, second):
            value = transform.get(key, 0)
            if not _finite_real(value):
                return False
            animated = (keyframes.get(key)
                        if isinstance(keyframes, dict) else None)
            if animated is not None:
                # Like opacity, getAnimatedTransform overrides static crop
                # with the per-frame keyframed value. A constant animated
                # crop of 100% can remove *all* source pixels even when
                # the saved base transform says 0% crop.
                if not isinstance(animated, list) or len(animated) > 100_000:
                    return False
                if animated:
                    if any(not isinstance(frame, dict) or
                           not _finite_real(frame.get("time")) or
                           not _finite_real(frame.get("value"))
                           for frame in animated):
                        return False
                    values_set = {frame["value"] for frame in animated}
                    if len(values_set) == 1:
                        value = next(iter(values_set))
                    else:
                        # Dynamic crops can be invisible at some frames but
                        # require source-synchronized frame evidence before
                        # stronger claims; this is a conservative static gate.
                        value = transform.get(key, 0)
            values.append(max(0, min(100, value)))
        if sum(values) >= 100:
            return False
    return True


def _native_zero_alpha_at_all_exported_frame_centers(
        clip: dict, export_interval: tuple) -> bool:
    """Prove keyframed alpha stays zero over ALL physically sampled frames.

    Pinned keyframes.js:getValueAtTime interpolates between the adjacent
    keyframe values using any easing. If every enclosing keyframe across
    the actual output sample range is exactly zero, the result is zero
    irrespective of easing (including hold/cubic bezier). This uses the
    real decoded output frame grid, not guessed timeline durations. It
    never predicts pixels from unknown keyframes, clips or missing FPS.
    """
    frame_grid = export_interval
    if len(frame_grid) != 4 or frame_grid[2] is None or frame_grid[3] is None:
        return False
    keyframes = clip.get("keyframes")
    animated = keyframes.get("opacity") if isinstance(keyframes, dict) else None
    if not isinstance(animated, list) or not animated:
        return False
    if any(not isinstance(kf, dict) or
           not _finite_real(kf.get("time")) or
           not _finite_real(kf.get("value"))
           for kf in animated):
        return False
    times = [kf["time"] for kf in animated]
    # Duplicate/unspecified interpolation order has no reliable zero
    # certificate. The native editor sorts by keyframe time.
    if len(set(times)) != len(times):
        return False
    ordered = sorted(animated, key=lambda kf: kf["time"])
    playback = _native_clip_playback_window(clip)
    if playback is None:
        return False
    output_start, output_end, fps, count = frame_grid
    beginning, finish = playback
    first = max(0, math.ceil((beginning - output_start) * fps - 0.5))
    last = min(count - 1, math.ceil((finish - output_start) * fps - 0.5) - 1)
    if first > last:
        return False
    # getAnimatedTransform uses local clip time, never absolute project
    # timeline time. Include each enclosing interpolation endpoint.
    first_local = (output_start + (first + 0.5) / fps -
                   clip["startTime"])
    last_local = (output_start + (last + 0.5) / fps -
                  clip["startTime"])
    if not math.isfinite(first_local) or not math.isfinite(last_local):
        return False
    from bisect import bisect_left, bisect_right
    ordered_times = [kf["time"] for kf in ordered]
    before = max(0, bisect_right(ordered_times, first_local) - 1)
    after = min(len(ordered) - 1,
                bisect_left(ordered_times, last_local))
    if all(kf["value"] == 0 for kf in
           ordered[min(before, after):max(before, after) + 1]):
        return True
    # Pinned getValueAtTime has an explicit 'hold' case: its value stays
    # EXACTLY at the previous keyframe until the next keyframe's instant.
    # A model may animate 0% -> 100% via hold at second 1 and export
    # [0, 1); every physical frame is still completely transparent.
    # The final sample must be strictly BEFORE that positive keyframe.
    return (
        after > before and last_local < ordered[after]["time"] and
        ordered[after - 1].get("easing") == "hold" and
        all(kf["value"] == 0 for kf in ordered[before:after])
    )


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
    NOT populate these windows from unverified model text. A verified export
    selecting proxy media is NOT direct original-byte footage proof: pinned
    Velorn may substitute unrelated asset.proxyUrl or proxyPath. Without
    physical delivery windows, report project/timeline custody only.
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
                    not {"start_seconds", "end_seconds"} <= set(interval) or
                    not set(interval) <= {
                        "start_seconds", "end_seconds", "use_proxy_media",
                        "video_frame_rate", "decoded_video_frame_count"} or
                    not _finite_real(interval["start_seconds"]) or
                    not _finite_real(interval["end_seconds"]) or
                    not 0 <= interval["start_seconds"] < interval["end_seconds"] or
                    type(interval.get("use_proxy_media", False)) is not bool):
                raise ValueError("Invalid independently verified export interval")
            # The trial measures these against the *actual decoded
            # output*, not against model text or native project preferences.
            # Both fields must be present together; missing measurements in
            # historical timeline-only fixtures cannot claim frame coverage.
            has_rate = "video_frame_rate" in interval
            has_count = "decoded_video_frame_count" in interval
            if has_rate != has_count:
                raise ValueError("Invalid independently verified export frame grid")
            rate = interval.get("video_frame_rate")
            count = interval.get("decoded_video_frame_count")
            if has_rate and (
                    not _finite_real(rate) or
                    not 0 < rate <= 1000 or
                    type(count) is not int or not 0 < count <= 10_000_000 or
                    abs((interval["end_seconds"] -
                         interval["start_seconds"]) - count / rate) >
                            max(2 / rate, 0.05)):
                raise ValueError("Invalid independently verified export frame grid")
            # Source-attested pinned exporter.js: a useProxyMedia:true
            # delivery may render asset.proxyUrl/proxyPath instead of the
            # SHA-bound original. A proxy export cannot independently prove
            # original *bytes* were sampled, even if the proxy looks alike.
            # An editor without a usable proxy might fall back to original:
            # refusing it here is intentionally a conservative false negative.
            if interval.get("use_proxy_media", False):
                continue
            checked_windows.append((
                interval["start_seconds"], interval["end_seconds"],
                rate if has_rate else None, count if has_count else None))
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
                                 else [(0, full_export_end, None, None)])
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
                matching_export_windows = (
                    [window for window in effective_windows
                     if playback_window is not None and
                     _export_samples_original_clip(playback_window, window) and
                     not _native_zero_alpha_at_all_exported_frame_centers(
                         clip, window)])
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
                        # A second cache substitution exists even without
                        # cacheStatus/cached flags. Pinned exporter.js uses
                        # opticalFlowSources.get(clip.id)?.url ahead of the
                        # imported asset when frameSampling is optical-flow.
                        # That derived/cache file is NOT the byte-verified
                        # caller source, so delivery-bound original-source
                        # proof must withhold acceptance until the cache
                        # independently binds to the original media bytes.
                        not (checked_windows is not None and
                             clip.get("frameSampling") == "optical-flow") and
                        clip.get("trackId") in visible_video_tracks and
                        isinstance(clip.get("assetId"), str) and
                        playback_window is not None and
                        bool(matching_export_windows)):
                    placed.setdefault(clip["assetId"], []).append((
                        clip, matching_export_windows))
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
            for native_clip, matched_windows in placed[asset_id]:
                # An MP4 frame centered on an active clip may still decode
                # *past EOF* of the owner-original video. Check the pinned
                # source-time mapping separately from timeline visibility.
                grids = [window for window in matched_windows
                         if window[2] is not None]
                output_frame_sampled = any(
                    _native_source_frame_available_at_output_sample(
                        native_clip, window, original_duration)
                    for window in grids)
                if grids and not output_frame_sampled and not any(
                        window[2] is None for window in matched_windows):
                    continue
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
                    "sampled_at_physically_verified_output_frame":
                        output_frame_sampled,
                    "source_sha256": owner_hash,
                    "project_owned_copy_sha256": owner_hash,
                })
    sampled = sum(1 for clip in accepted if
                  clip["sampled_at_physically_verified_output_frame"])
    return {
        "actual_original_video_used_on_native_timeline": bool(accepted),
        "actual_original_video_sampled_at_verified_output_frame": sampled > 0,
        "verified_output_sampled_original_clip_count": sampled,
        "physically_verified_native_source_clip_count": len(accepted),
        "verified_native_source_clip_proof": accepted,
        "professional_artistic_quality_approved": False,
    }
