"""One bounded, actual NVIDIA Brain -> genuine native editor creative evaluation.

Only original generated neutral footage is staged. The neural model chooses
all creative edits; the harness never sends a predetermined edit operation.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import struct
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import NamedTuple

from studio_next.native_render_evidence import destination_digest, timeline_scope_digest
from studio_next.body_editor_export import native_export_file_identity

ROOT = Path(__file__).resolve().parents[1]
_SOURCE_EDITOR = ROOT / "third_party" / "velorn"
_EDITOR_CLIENT = ROOT / "engines" / "velorn" / "native-model-client.py"
_EXAMPLE = ROOT / "engines" / "velorn" / "editor.example.json"
_PINNED_EDITOR = "b3c02adbd5c0779feb8abf34978299e9502cc0e7"
_ALLOWED_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
# A previous genuine 40-turn hosted run verified two real exports and observed
# their frames, but spent its last turns exporting a post-review revision and
# could not independently verify that final output. The 48-turn experiment is
# still strictly bounded, synthetic-only and host-permissioned.
_TRIAL_MAX_TURNS = 48
# A genuine Super-VL 120B request in #42669603529 generated 6,616
# completion tokens in 87.3 seconds; turn 16 exceeded the 90-second
# HTTP limit. Keep ONE non-retried request per model decision and a
# strict whole-session cap inside the 35-minute CI job.
_TRIAL_MODEL_TIMEOUT_SECONDS = 180
_TRIAL_PROCESS_TIMEOUT_SECONDS = 1500
_TRIAL_WIDTH = 640
_TRIAL_HEIGHT = 360
_TRIAL_FPS = 24
_TRIAL_MAX_SECONDS = 6
_PICTURE_PROFILE_FIELDS = (
    "width", "height", "sample_aspect_ratio", "codec_name", "pix_fmt",
    "color_range", "color_space", "color_transfer", "color_primaries",
    "chroma_location", "field_order",
)
_HOST_ALLOWED = frozenset({
    "get_project", "get_timeline", "get_assets", "check_export_readiness",
    "inspect_export_file", "inspect_timeline_frame", "find_timeline_items",
    "create_project", "create_timeline", "import_asset_from_path",
    "add_asset_to_timeline", "add_text_clip", "update_text_clip",
    "add_shape_clip", "update_shape_clip", "set_clip_style",
    "save_project", "export_timeline", "move_clips",
})
AV_TRIAL_REVISION_TOOLS = frozenset({
    "add_asset_to_timeline", "add_text_clip", "update_text_clip", "add_shape_clip",
    "update_shape_clip", "set_clip_style", "move_clips", "set_clip_audio",
})


def synthetic_trial_delivery_requirement(*, max_seconds):
    """Tell the model the same delivery settings the physical checker enforces."""
    return (f"Deliver H.264 MP4 at {_TRIAL_WIDTH}x{_TRIAL_HEIGHT}, {_TRIAL_FPS} fps, "
            f"at most {max_seconds} seconds. Use those picture settings for the "
            "project and both exports.")


def _no_cloud_credentials():
    """Never let ordinary FFmpeg or Git worker subprocesses read API keys."""
    return {k: v for k, v in os.environ.items() if k != "NVIDIA_API_KEY"}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def prepare_trial(workspace: Path, *, source: Path, audiovisual=False):
    """Private, non-overwriting real media and host grants; no user footage."""
    workspace = Path(workspace).resolve()
    source = Path(source).resolve()
    if workspace.exists():
        raise ValueError("Native trial workspace must not preexist or overwrite artifacts")
    if not source.is_dir():
        raise ValueError("Pinned native editor source checkout missing")
    rev = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True, timeout=15,
                         env=_no_cloud_credentials()).stdout.strip()
    if rev != _PINNED_EDITOR:
        raise ValueError("Unpinned native editor source cannot enter trial")
    os.umask(0o077)
    workspace.mkdir(mode=0o700)
    roots = {name: workspace / name for name in ("projects", "staging", "outputs", "state")}
    for location in roots.values():
        location.mkdir(mode=0o700)
    image_path = roots["staging"] / "original-neutral-gradient.mp4"
    source_seconds = _TRIAL_MAX_SECONDS if audiovisual else 4
    # This is source footage, not a shot plan, a generated finished film,
    # a model response, or an authorized creative editing decision.
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
         f"gradients=s=640x360:r=24:d={source_seconds}:c0=0x20364c:c1=0x85bbc1:seed=13",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(image_path)],
        check=True, timeout=90, env=_no_cloud_credentials())
    source_ledger = [{
        "path": str(image_path),
        "sha256": _sha256(image_path),
        "media_kind": "video",
        "rights": "original locally generated neutral creative test source",
        "preauthored_timeline": False,
    }]
    if audiovisual:
        audio_path = roots["staging"] / "original-synthetic-sound.wav"
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
             "aevalsrc=0.18*sin(2*PI*(440+25*t)*t)*(0.55+0.4*sin(2*PI*t))"
             f":s=48000:d={source_seconds}",
             "-c:a", "pcm_s16le", str(audio_path)],
            check=True, timeout=30, env=_no_cloud_credentials())
        source_ledger.append({
            "path": str(audio_path),
            "sha256": _sha256(audio_path),
            "media_kind": "audio",
            "rights": "original locally generated synthetic audio test source",
            "preauthored_timeline": False,
        })
    (workspace / "source-ledger.json").write_text(
        json.dumps(source_ledger, indent=2), encoding="utf-8")
    config = json.loads(_EXAMPLE.read_text(encoding="utf-8"))
    installed = config.get("allowed_tools")
    if not isinstance(installed, dict):
        raise ValueError("Native editor host grant catalog missing")
    allowed = _HOST_ALLOWED | AV_TRIAL_REVISION_TOOLS if audiovisual else _HOST_ALLOWED
    grant = {k: v for k, v in installed.items() if k in allowed}
    if set(grant) != allowed or grant.get("create_project") != "write":
        raise ValueError("Pinned native host grant inventory changed")
    config.update(
        projects_root=str(roots["projects"]),
        staging_root=str(roots["staging"]),
        outputs_root=str(roots["outputs"]),
        verify_native_exports=True,
        # Owner's synthetic delivery acceptance, NOT an artistic action plan.
        # This contract is private to BODY; the model still chooses the native
        # target and editing steps. The source-native preflight prevents bad
        # 1080p default exports before any write is attempted.
        required_export_delivery={
            "width": _TRIAL_WIDTH, "height": _TRIAL_HEIGHT,
            "fps": _TRIAL_FPS, "max_duration": _TRIAL_MAX_SECONDS,
            "video_codec": "h264",
        },
        allowed_tools=grant,
    )
    cfg = workspace / "host-grants.json"
    cfg.write_text(json.dumps(config, indent=2), encoding="utf-8")
    brief = (
        "Create an ORIGINAL, editable short motion piece about finding momentum "
        "through small changes. Independently decide the story, composition, "
        "type, timing and visual treatment. Use the one provided original "
        "neutral video as real source footage, not as a precut storyboard. "
        "You are controlling an actual installed video editor; use discovered "
        "tool schemas and never invent project state. "
        "Create and save the native project, export an actual MP4, verify its "
        "physical bytes with the installed independent export verifier, and "
        "inspect at least one genuine export frame. After seeing the frame, "
        "choose a meaningful editable creative improvement yourself, apply "
        "that native revision, export to a NEW file and physically verify the "
        "revised export. Keep the export settings identical to the first "
        "export so the editorial change can be compared. "
        "Do not repeat an uncertain native write. "
        "This is a bounded synthetic engineering trial. "
        f"{synthetic_trial_delivery_requirement(max_seconds=_TRIAL_MAX_SECONDS)} "
        "No model-generated footage, "
        "external sources, downloaded media or private user assets are needed. "
        "The synthetic source is locally generated and may be inspected by "
        "this remote vision model. Final quality still requires independent "
        "artistic judgment. "
        f"Native projects root: {roots['projects']}. "
        f"Authorized output root: {roots['outputs']}. "
        "Actual original available source assets: " + json.dumps(source_ledger)
    )
    if audiovisual:
        brief = (
            "Create an original editable six-second piece that turns a hesitation "
            "into momentum. Use the generated footage and audible generated sound as "
            "source materials. Independently choose the composition, sequence, type, "
            "and relationship of movement and sound. Save and export the first cut. "
            "Inspect decoded frames and timed sound diagnostics, then choose and save "
            "a meaningful editable revision. Export to a new path with the same "
            "zero-to-six-second range and encoding settings. Both files must be "
            "640x360 H.264 MP4 at exactly 24 fps with audible sound. Independently "
            "verify both files and observe matching frame times and the full sound "
            "window for each. "
            f"Native projects root: {roots['projects']}. "
            f"Authorized output root: {roots['outputs']}. "
            "Generated originals: " + json.dumps(source_ledger)
        )
    (workspace / "brief.txt").write_text(brief, encoding="utf-8")
    return roots, cfg



def verify_saved_native_trial(workspace: Path, *, source_ledger=None, max_clip_duration=6,
                              require_audio=False):
    """Prove that the active saved timeline uses an intact staged original."""
    workspace = Path(workspace).resolve()
    if source_ledger is None:
        source_ledger = json.loads((workspace / "source-ledger.json").read_text(encoding="utf-8"))
        expected = 2 if require_audio else 1
        if type(source_ledger) is not list or len(source_ledger) != expected:
            raise ValueError("Missing required owner-original source ledger")
    if type(source_ledger) is not list or not 1 <= len(source_ledger) <= 32:
        raise ValueError("Missing bounded owner-original source ledger")
    source_hashes = {}
    source_kinds = {}
    staging = (workspace / "staging").resolve(strict=True)
    for entry in source_ledger:
        if (type(entry) is not dict or type(entry.get("path")) is not str or
                type(entry.get("sha256")) is not str):
            raise ValueError("Malformed owner-original source ledger")
        candidate = Path(entry["path"])
        original = candidate.resolve(strict=True)
        if (candidate.is_symlink() or original.parent != staging or
                str(original) in source_hashes or not original.is_file() or
                _sha256(original) != entry["sha256"]):
            raise ValueError("Original staged video differs from owner SHA ledger")
        source_hashes[str(original)] = entry["sha256"]
        if require_audio:
            kind = entry.get("media_kind")
            if kind not in ("video", "audio"):
                raise ValueError("Audiovisual original requires host-declared media kind")
            source_kinds[str(original)] = kind
    if require_audio and sorted(source_kinds.values()) != ["audio", "video"]:
        raise ValueError("Audiovisual source pack must contain one video and one sound")
    root = workspace / "projects"
    candidates = list(root.glob("*/project.comfystudio"))
    if len(candidates) != 1:
        raise ValueError("Native trial requires exactly one saved active project")
    project_file = candidates[0]
    if (project_file.is_symlink() or
            not project_file.resolve().is_relative_to(root.resolve()) or
            not project_file.is_file() or
            not 0 < project_file.stat().st_size <= 16 * 1024 * 1024):
        raise ValueError("Native saved project is missing, redirected or oversized")
    def reject_duplicates(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Ambiguous duplicate native project JSON field")
            obj[key] = value
        return obj
    def reject_nonfinite(value):
        raise ValueError("Nonfinite native project JSON")
    native = json.loads(
        project_file.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicates, parse_constant=reject_nonfinite)
    if type(native) is not dict:
        raise ValueError("Invalid native saved project")
    timelines = native.get("timelines")
    active_id = native.get("currentTimelineId")
    if (type(timelines) is not list or not timelines or
            type(active_id) is not str or not active_id or
            sum(type(t) is dict and t.get("id") == active_id
                for t in timelines) != 1):
        raise ValueError("No single saved active native timeline")
    active = next(t for t in timelines if type(t) is dict and t.get("id") == active_id)
    clips, tracks, assets = (active.get("clips"), active.get("tracks"),
                            native.get("assets"))
    if (type(clips) is not list or not clips or
            type(tracks) is not list or type(assets) is not list):
        raise ValueError("Native saved active timeline has no editable clips")
    # A copied source on a hidden track or disabled clip is not active
    # picture evidence. Reject ambiguous IDs before associating source clips.
    track_ids = set()
    video_tracks = set()
    audio_tracks = set()
    for track in tracks:
        if (type(track) is not dict or
                type(track.get("id")) is not str or not track["id"] or
                track["id"] in track_ids):
            raise ValueError("Ambiguous native timeline track identities")
        track_ids.add(track["id"])
        if track.get("type") == "video" and track.get("visible") is not False:
            video_tracks.add(track["id"])
        if track.get("type") == "audio" and track.get("muted") is not True:
            audio_tracks.add(track["id"])
    valid_assets = {}
    for asset in assets:
        if type(asset) is not dict:
            raise ValueError("Malformed native project asset")
        aid = asset.get("id")
        if type(aid) is not str or not aid or aid in valid_assets:
            raise ValueError("Ambiguous native project asset identities")
        valid_assets[aid] = asset
    real_original_clips = 0
    real_original_audio_clips = 0
    for clip in clips:
        if type(clip) is not dict:
            raise ValueError("Malformed native project clip")
        if (clip.get("enabled") is False or
                type(clip.get("assetId")) is not str):
            continue
        is_video = clip.get("trackId") in video_tracks
        is_audio = (require_audio and clip.get("trackId") in audio_tracks)
        if not (is_video or is_audio):
            continue
        asset = valid_assets.get(clip["assetId"])
        if not asset or asset.get("type") != ("video" if is_video else "audio"):
            continue
        metadata = asset.get("settings")
        source_path = metadata.get("sourcePath") if type(metadata) is dict else None
        if type(source_path) is not str or source_path not in source_hashes:
            continue
        if require_audio and source_kinds[source_path] != asset.get("type"):
            raise ValueError("Native asset type contradicts original source manifest")
        relative = asset.get("path")
        if (type(relative) is not str or not relative or
                Path(relative).is_absolute()):
            raise ValueError("Untrusted native source copy location")
        project_dir = project_file.parent.resolve(strict=True)
        copied = (project_dir / relative).resolve(strict=True)
        if (not copied.is_relative_to(project_dir) or
                not copied.is_file() or _sha256(copied) != source_hashes[source_path]):
            raise ValueError("Native original source bytes differ from ledger")
        duration = clip.get("duration")
        if (type(duration) not in (int, float) or
                not 0 < duration <= max_clip_duration or
                (type(duration) is float and not math.isfinite(duration))):
            raise ValueError("Invalid placed original video duration")
        # Structural source custody alone is not proof that owner footage
        # contributes to this bounded synthetic export. The pinned editor
        # stores source placement in timeline seconds as startTime; missing,
        # nonnumeric or nonfinite placement cannot prove an active picture.
        # This gates only the 6/8-second evaluation interval, not arbitrary
        # durations or layouts in the production editor.
        start = clip.get("startTime")
        if (type(start) not in (int, float) or start < 0 or
                (type(start) is float and not math.isfinite(start))):
            raise ValueError("Invalid native source clip timeline placement")
        if start >= max_clip_duration:
            continue
        if is_video:
            real_original_clips += 1
        elif source_kinds.get(source_path) == "audio":
            real_original_audio_clips += 1
    if require_audio and not real_original_audio_clips:
        raise ValueError("No intact source-backed audible clip on active native audio track")
    if not real_original_clips:
        raise ValueError("No physically source-backed video clip on saved active timeline")
    result = {
        "native_project_sha256": _sha256(project_file),
        "active_native_timeline_id": active_id,
        "saved_native_timeline_sha256": timeline_scope_digest(str(project_file.parent), active_id),
        "saved_active_clip_count": len(clips),
        "verified_source_backed_video_clips": real_original_clips,
        "artistic_quality_approved": False,
    }
    if require_audio:
        result["verified_source_backed_audio_clips"] = real_original_audio_clips
    return result

def decoded_video_frames_sha256(path: Path, *, max_frames=240):
    """Hash exact-time presented decoded RGB frames, not container metadata.

    Genuine native retiming changes physical presentation even when RGB frames
    are identical. Different MP4 metadata/codec bytes with identical physical
    picture and timing must not impersonate a model-selected revision.
    Human artistic approval is a separate judgment.
    """
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-xerror",
         "-i", str(path), "-map", "0:v:0",
         "-vf", "format=rgb24", "-fps_mode", "passthrough",
         "-frames:v", str(max_frames + 1),
         "-f", "framehash", "-hash", "SHA256", "-"],
        check=True, capture_output=True, text=True, timeout=90,
        env=_no_cloud_credentials())
    if len(result.stdout.encode("utf-8")) > 128_000:
        raise ValueError("Native video frame evidence exceeds safe output budget")
    # Preserve actual presentation time as exact rational seconds. Two
    # frame-identical edits with different timing ARE genuinely different
    # videos; an MP4 container timescale rewrite is NOT.
    timebases = [line.split(":", 1)[1].strip()
                 for line in result.stdout.splitlines()
                 if line.startswith("#tb 0:")]
    if len(timebases) != 1:
        raise ValueError("Missing unique native video decoder timebase")
    try:
        timebase = Fraction(timebases[0])
    except (ValueError, ZeroDivisionError):
        raise ValueError("Malformed native video timebase") from None
    if timebase <= 0:
        raise ValueError("Native video timebase must be positive")
    presentations = []
    for line in result.stdout.splitlines():
        if line.startswith("#"):
            continue
        fields = [part.strip() for part in line.split(",")]
        if (len(fields) != 6 or fields[0] != "0" or
                len(fields[5]) != 64 or
                any(char not in "0123456789abcdef" for char in fields[5]) or
                not fields[4].isdigit() or int(fields[4]) <= 0):
            raise ValueError("Malformed native decoded-frame SHA256 receipt")
        try:
            pts = int(fields[2])
            duration = int(fields[3])
        except ValueError:
            raise ValueError("Malformed native frame presentation time") from None
        if duration <= 0:
            raise ValueError("Native output has nonpositive frame duration")
        presentations.append((
            str(pts * timebase), str(duration * timebase), fields[5]))
        if len(presentations) > max_frames:
            raise ValueError("Synthetic trial exceeds bounded decoded video frames")
    if not presentations:
        raise ValueError("Native output contains no decoded video frames")
    return tuple(presentations)



class DecodedTrialAudio(NamedTuple):
    """Physical PCM observation, not semantic listening or artistic acceptance."""
    pcm_sha256: str
    sample_rate: int
    sample_count: int
    duration_seconds: float
    rms: float
    audible: bool


def decode_trial_audio(path: Path, *, expected_video_seconds: float,
                       sample_rate=8000, max_seconds=_TRIAL_MAX_SECONDS):
    """Fully decode actual export audio, reject missing/silent/misaligned sound.

    The bounded trial resource budget does NOT constrain production soundtracks.
    We never infer emotion, speech intelligibility, licensing or mix quality
    from PCM energy; those require a compatible reviewer and human listening.
    """
    if (type(expected_video_seconds) not in (int, float) or
            not 0 < expected_video_seconds <= max_seconds or
            type(sample_rate) is not int or sample_rate != 8000):
        raise ValueError("Invalid physical A/V observation budget")
    try:
        decoded = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-xerror",
             "-i", str(path), "-map", "0:a:0", "-vn", "-ac", "1",
             "-ar", str(sample_rate), "-f", "s16le", "pipe:1"],
            check=True, capture_output=True, timeout=90,
            env=_no_cloud_credentials()).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise ValueError("Physical export audio is missing or cannot be decoded") from None
    max_bytes = (max_seconds + 1) * sample_rate * 2
    if (not decoded or len(decoded) % 2 or len(decoded) > max_bytes):
        raise ValueError("Invalid bounded decoded export PCM")
    sample_count = len(decoded) // 2
    duration = sample_count / sample_rate
    if abs(duration - expected_video_seconds) > 0.10:
        raise ValueError("Decoded audio duration is not aligned with picture")
    power = sum(value[0] * value[0]
                for value in struct.iter_unpack("<h", decoded))
    rms = (power / sample_count) ** 0.5 / 32768.0
    return DecodedTrialAudio(
        hashlib.sha256(decoded).hexdigest(), sample_rate, sample_count,
        duration, rms, rms >= 0.005)



class DecodedTrialExport(NamedTuple):
    identity: tuple
    presentation: tuple
    picture_profile: dict


def _probe_trial_picture_profile(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=" + ",".join(_PICTURE_PROFILE_FIELDS),
         "-of", "json", str(path)],
        check=True, capture_output=True, timeout=30, env=_no_cloud_credentials())
    if len(result.stdout) > 8192:
        raise ValueError("Native video picture profile exceeds safe output budget")
    streams = json.loads(result.stdout).get("streams")
    if not isinstance(streams, list) or len(streams) != 1 or not isinstance(streams[0], dict):
        raise ValueError("Native video needs one probed primary picture stream")
    profile = {field: streams[0].get(field) for field in _PICTURE_PROFILE_FIELDS}
    if (any(type(profile[field]) is not int or profile[field] <= 0
            for field in ("width", "height")) or
            any(not isinstance(profile[field], str) or not profile[field]
                for field in ("codec_name", "pix_fmt"))):
        raise ValueError("Native video has no valid primary picture profile")
    return profile


def decode_trial_export(path, *, expected_sha256=None, max_frames=240):
    """Independently decode the same physical bytes as the earlier receipt."""
    identity = native_export_file_identity(path)
    if expected_sha256 is not None and identity[-1] != expected_sha256:
        raise ValueError("Native trial export differs from its verification receipt")
    picture_profile = _probe_trial_picture_profile(path)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
        check=True, timeout=90, env=_no_cloud_credentials())
    presentation = decoded_video_frames_sha256(path, max_frames=max_frames)
    if native_export_file_identity(path) != identity:
        raise ValueError("Native trial export changed during decoding")
    return DecodedTrialExport(identity, presentation, picture_profile)


def trial_picture_changed(before, after):
    """Compare presented picture or timing only across matching export profiles."""
    return (before is not None and after is not None and
            before.picture_profile == after.picture_profile and
            before.presentation != after.presentation)


def trial_delivery_profile_compliant(
        decoded, *, width=_TRIAL_WIDTH, height=_TRIAL_HEIGHT,
        fps=_TRIAL_FPS, max_seconds=_TRIAL_MAX_SECONDS):
    """Independently enforce this *experiment's* declared resource profile.

    This is NOT a ZX7 product-wide resolution, duration or aesthetic limit.
    Comparable but identically mis-sized renders cannot pass a trial that
    explicitly required 640x360, 24 fps and a bounded physical duration.
    """
    if (not isinstance(decoded, DecodedTrialExport) or
            decoded.picture_profile.get("width") != width or
            decoded.picture_profile.get("height") != height or
            decoded.picture_profile.get("codec_name") != "h264" or
            # The actual pinned Velorn 640x360 H.264 export omits SAR
            # metadata (the ordinary implicit-square presentation); explicit
            # anamorphic SAR is not acceptable for this fixed-format trial.
            decoded.picture_profile.get("sample_aspect_ratio") not in (None, "1:1") or
            not isinstance(decoded.presentation, tuple) or
            not 0 < len(decoded.presentation) <= max_seconds * fps):
        return False
    frame_duration = Fraction(1, fps)
    for index, frame in enumerate(decoded.presentation):
        if not isinstance(frame, tuple) or len(frame) != 3:
            return False
        try:
            pts, duration = Fraction(frame[0]), Fraction(frame[1])
        except (ValueError, TypeError, ZeroDivisionError):
            return False
        if pts != index * frame_duration or duration != frame_duration:
            return False
    return True


def run_trial(workspace: Path, *, model_id: str, xvfb_binary: str, display: str,
              audiovisual=False):
    if model_id != _ALLOWED_MODEL:
        raise ValueError("NVIDIA native trial model must match audited fixed catalog identity")
    roots, cfg = prepare_trial(workspace, source=_SOURCE_EDITOR,
                               audiovisual=audiovisual)
    workspace = Path(workspace).resolve()
    receipt = workspace / "native-journal.jsonl"
    command = [
        sys.executable, str(_EDITOR_CLIENT),
        "--provider", "nvidia",
        "--model-id", model_id,
        "--allow-cloud-image-upload",
        # The real 120B NVIDIA run #42383427031 burned 30 of 40
        # model decisions re-searching ambiguous tools while only 24 actual
        # host-granted tools existed. Full catalog is the cheaper honest
        # transport for this trial; all BODY grants/schema checks remain.
        # There is NO host-authored creative edit or automatic invocation.
        "--structured-actions",
        "--fresh-trial-project",
        "--evaluation-evidence", (
            "reviewed-av-revision" if audiovisual else "reviewed-revision"),
        *(["--allow-cloud-audio-diagnostics", "--record-av-project-snapshots"]
          if audiovisual else []),
        "--max-turns", str(_TRIAL_MAX_TURNS),
        "--model-timeout", str(_TRIAL_MODEL_TIMEOUT_SECONDS),
        "--source", str(_SOURCE_EDITOR),
        "--config", str(cfg),
        "--state", str(roots["state"]),
        "--brief-file", str(workspace / "brief.txt"),
        "--receipt", str(receipt),
        "--xvfb-binary", xvfb_binary,
        "--display", display,
    ]
    try:
        completed = subprocess.run(
            command, check=False, capture_output=True, text=True,
            cwd=ROOT, timeout=_TRIAL_PROCESS_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Native creative evaluation exceeded bounded host wall time") from None
    # Synthetic-only paths and redacted native events may be preserved
    # for independent investigation. No raw provider Authorization headers.
    (workspace / "native-client-stdout.txt").write_text(
        completed.stdout, encoding="utf-8")
    (workspace / "native-client-stderr.txt").write_text(
        completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError("Real model/native editor trial failed; read private test artifacts")
    try:
        summary = json.loads(completed.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError("Real native client has no final structured status") from None
    mp4s = sorted(roots["outputs"].rglob("*.mp4"))
    media = []
    decoded_exports = {}
    audio_exports = {}
    audio_rejections = {}
    for path in mp4s:
        decoded = decode_trial_export(path)
        identity = decoded.identity
        pair_key = (destination_digest(str(path)), identity[-1])
        decoded_exports[pair_key] = decoded
        if audiovisual:
            try:
                audio_exports[pair_key] = decode_trial_audio(
                    path, expected_video_seconds=len(decoded.presentation) / _TRIAL_FPS)
            except ValueError:
                # Missing, silent or mistimed source sound must not erase the
                # physical investigation. Save a bounded negative receipt
                # and fail final acceptance, never invent a valid audio hash.
                audio_rejections[pair_key] = "audio_missing_or_decode_or_sync_failed"
        media.append({"path": str(path), "sha256": identity[-1],
                      "bytes": identity[2],
                      "decoded_picture_profile": decoded.picture_profile,
                      "synthetic_trial_delivery_profile_compliant":
                          trial_delivery_profile_compliant(decoded),
                      "decoded_video_frames": len(decoded.presentation),
                      "decoded_rgb_frame_sequence_sha256": hashlib.sha256(
                          json.dumps(decoded.presentation,
                                     separators=(",", ":")).encode()).hexdigest(),
                      **({"decoded_audio_pcm_sha256": audio_exports[pair_key].pcm_sha256,
                          "decoded_audio_duration_seconds": audio_exports[pair_key].duration_seconds,
                          "decoded_audio_rms": audio_exports[pair_key].rms,
                          "decoded_audio_audible": audio_exports[pair_key].audible}
                         if audiovisual and pair_key in audio_exports else {}),
                      **({"decoded_audio_rejection": audio_rejections[pair_key]}
                         if pair_key in audio_rejections else {})})
    # Preserve forensic evidence even when final native state fails acceptance.
    # Never let an empty timeline disappear behind an early RuntimeError.
    try:
        saved_native = {
            **verify_saved_native_trial(workspace, require_audio=audiovisual),
            "native_saved_project_verified": True,
        }
    except ValueError as exc:
        saved_native = {
            "native_saved_project_verified": False,
            "native_project_rejection": str(exc)[:256],
        }
    except OSError as exc:
        # Raw OS messages can include sensitive workspace paths.
        saved_native = {
            "native_saved_project_verified": False,
            "native_project_rejection_type": type(exc).__name__,
        }
    export_variants = len({entry["sha256"] for entry in media})
    independently_different_picture_exports = len({
        item.presentation for item in decoded_exports.values()})
    pair = summary.get(
        "reviewed_native_audiovisual_pair" if audiovisual else
        "reviewed_native_render_pair")
    changed_reviewed_picture = False
    changed_reviewed_audio = False
    reviewed_pair_audio_acceptable = False
    reviewed_pair_delivery_profile_compliant = False
    if pair and pair[1]["timeline_sha256"] == saved_native.get("saved_native_timeline_sha256"):
        before, after = (decoded_exports.get((item["destination_sha256"], item["export_sha256"]))
                         for item in pair)
        changed_reviewed_picture = trial_picture_changed(before, after)
        reviewed_pair_delivery_profile_compliant = (
            trial_delivery_profile_compliant(before) and
            trial_delivery_profile_compliant(after))
        if audiovisual:
            a, b = (audio_exports.get((item["destination_sha256"], item["export_sha256"]))
                    for item in pair)
            reviewed_pair_audio_acceptable = bool(
                a and b and a.audible and b.audible)
            changed_reviewed_audio = bool(
                reviewed_pair_audio_acceptable and
                a.pcm_sha256 != b.pcm_sha256)
    evaluated = {
        **saved_native,
        "different_decoded_export_count": export_variants,
        "different_decoded_picture_sequence_count": independently_different_picture_exports,
        "status": summary.get("status"),
        "host_evidence_satisfied": summary.get("evaluation_evidence_satisfied") is True,
        "reviewed_native_render_pair": None if audiovisual else pair,
        "reviewed_native_audiovisual_pair": pair if audiovisual else None,
        "decoded_reviewed_picture_changed": changed_reviewed_picture,
        "decoded_reviewed_audio_changed": changed_reviewed_audio,
        "reviewed_pair_audible_audio_acceptable": (
            reviewed_pair_audio_acceptable if audiovisual else None),
        "reviewed_pair_synthetic_delivery_profile_compliant":
            reviewed_pair_delivery_profile_compliant,
        "model_selected_write_receipts": summary.get("model_selected_write_receipts"),
        "physical_export_verify_receipts": summary.get("independently_verified_export_receipts"),
        "decoded_real_exports": media,
        "decoded_audio_errors": len(audio_rejections) if audiovisual else None,
        "original_media_sent_to_model": False,
        "synthetic_frame_upload_explicitly_authorized": True,
        "artistic_quality_approved": False,
    }
    (workspace / "native-evaluation.json").write_text(
        json.dumps(evaluated, indent=2), encoding="utf-8")
    print(json.dumps(evaluated, ensure_ascii=False))
    if (summary.get("status") != "model_finished_unverified" or
            summary.get("evaluation_evidence_satisfied") is not True or
            not (changed_reviewed_picture or
                 (audiovisual and changed_reviewed_audio)) or
            (audiovisual and (
                not reviewed_pair_audio_acceptable or bool(audio_rejections))) or
            not reviewed_pair_delivery_profile_compliant or
            saved_native["native_saved_project_verified"] is not True):
        raise RuntimeError("Model did not meet full real-native visual-revision-export proof")
    return evaluated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--model-id", default=_ALLOWED_MODEL)
    parser.add_argument("--xvfb-binary", default="/usr/bin/Xvfb")
    parser.add_argument("--display", default="127.0.0.1:95")
    parser.add_argument("--prepare-audiovisual-only", action="store_true",
                        help="Stage generated picture and sound without launching any model")
    parser.add_argument("--audiovisual-trial", action="store_true",
                        help="Opt in to a model-driven trial with physically decoded sound")
    parser.add_argument("--allow-cloud-audio-diagnostics", action="store_true",
                        help="Separate consent for sending synthetic audio statistics to NVIDIA")
    args = parser.parse_args(argv)
    if args.prepare_audiovisual_only:
        prepare_trial(args.workspace, source=_SOURCE_EDITOR, audiovisual=True)
        return
    if args.audiovisual_trial and not args.allow_cloud_audio_diagnostics:
        parser.error("Audiovisual NVIDIA trial requires explicit cloud audio diagnostics consent")
    if args.allow_cloud_audio_diagnostics and not args.audiovisual_trial:
        parser.error("Audio diagnostics consent is valid only for audiovisual trial")
    run_trial(args.workspace, model_id=args.model_id,
              xvfb_binary=args.xvfb_binary, display=args.display,
              audiovisual=args.audiovisual_trial)


if __name__ == "__main__":
    main()
