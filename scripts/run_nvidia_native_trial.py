"""One bounded, actual NVIDIA Brain -> genuine native editor creative evaluation.

Only original generated neutral footage is staged. The neural model chooses
all creative edits; the harness never sends a predetermined edit operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
_SOURCE_EDITOR = ROOT / "third_party" / "velorn"
_EDITOR_CLIENT = ROOT / "engines" / "velorn" / "native-model-client.py"
_EXAMPLE = ROOT / "engines" / "velorn" / "editor.example.json"
_PINNED_EDITOR = "b3c02adbd5c0779feb8abf34978299e9502cc0e7"
_ALLOWED_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
_HOST_ALLOWED = frozenset({
    "get_project", "get_timeline", "get_assets", "check_export_readiness",
    "inspect_export_file", "inspect_timeline_frame", "find_timeline_items",
    "create_project", "create_timeline", "import_asset_from_path",
    "add_asset_to_timeline", "add_text_clip", "update_text_clip",
    "add_shape_clip", "update_shape_clip", "set_clip_style",
    "save_project", "export_timeline", "move_clips",
})


def _no_cloud_credentials():
    """Never let ordinary FFmpeg or Git worker subprocesses read API keys."""
    return {k: v for k, v in os.environ.items() if k != "NVIDIA_API_KEY"}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def prepare_trial(workspace: Path, *, source: Path):
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
    # This is source footage, not a shot plan, a generated finished film,
    # a model response, or an authorized creative editing decision.
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
         "gradients=s=640x360:r=24:d=4:c0=0x20364c:c1=0x85bbc1:seed=13",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(image_path)],
        check=True, timeout=90, env=_no_cloud_credentials())
    source_ledger = [{
        "path": str(image_path),
        "sha256": _sha256(image_path),
        "rights": "original locally generated neutral creative test source",
        "preauthored_timeline": False,
    }]
    (workspace / "source-ledger.json").write_text(
        json.dumps(source_ledger, indent=2), encoding="utf-8")
    config = json.loads(_EXAMPLE.read_text(encoding="utf-8"))
    installed = config.get("allowed_tools")
    if not isinstance(installed, dict):
        raise ValueError("Native editor host grant catalog missing")
    grant = {k: v for k, v in installed.items() if k in _HOST_ALLOWED}
    if set(grant) != _HOST_ALLOWED or grant.get("create_project") != "write":
        raise ValueError("Pinned native host grant inventory changed")
    config.update(
        projects_root=str(roots["projects"]),
        staging_root=str(roots["staging"]),
        outputs_root=str(roots["outputs"]),
        verify_native_exports=True,
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
        "revised export. Do not repeat an uncertain native write. "
        "This is a bounded synthetic engineering trial: video up to six "
        "seconds, resolution 640x360, 24 fps. No model-generated footage, "
        "external sources, downloaded media or private user assets are needed. "
        "The synthetic source is locally generated and may be inspected by "
        "this remote vision model. Final quality still requires independent "
        "artistic judgment. "
        f"Native projects root: {roots['projects']}. "
        f"Authorized output root: {roots['outputs']}. "
        "Actual original available source assets: " + json.dumps(source_ledger)
    )
    (workspace / "brief.txt").write_text(brief, encoding="utf-8")
    return roots, cfg



def verify_saved_native_trial(workspace: Path):
    """Independent structural proof: the CURRENT saved native timeline uses
    a physically intact copied original video clip. This is NOT a creative
    quality score and cannot replace export decode/visual inspection.
    """
    workspace = Path(workspace).resolve()
    ledger_path = workspace / "source-ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if (type(ledger) is not list or len(ledger) != 1 or
            type(ledger[0]) is not dict or
            type(ledger[0].get("path")) is not str or
            type(ledger[0].get("sha256")) is not str):
        raise ValueError("Missing unique owner-original source ledger")
    original = Path(ledger[0]["path"]).resolve(strict=True)
    if (not original.is_file() or
            original != (workspace / "staging" / original.name).resolve() or
            _sha256(original) != ledger[0]["sha256"]):
        raise ValueError("Original staged video differs from owner SHA ledger")
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
    active = next(t for t in timelines if t.get("id") == active_id)
    clips, tracks, assets = (active.get("clips"), active.get("tracks"),
                            native.get("assets"))
    if (type(clips) is not list or not clips or
            type(tracks) is not list or type(assets) is not list):
        raise ValueError("Native saved active timeline has no editable clips")
    video_tracks = {t["id"] for t in tracks if
                    type(t) is dict and type(t.get("id")) is str and
                    t.get("type") == "video"}
    valid_assets = {}
    for asset in assets:
        if type(asset) is not dict:
            raise ValueError("Malformed native project asset")
        aid = asset.get("id")
        if type(aid) is not str or not aid or aid in valid_assets:
            raise ValueError("Ambiguous native project asset identities")
        valid_assets[aid] = asset
    real_original_clips = 0
    for clip in clips:
        if type(clip) is not dict:
            raise ValueError("Malformed native project clip")
        if (clip.get("trackId") not in video_tracks or
                type(clip.get("assetId")) is not str):
            continue
        asset = valid_assets.get(clip["assetId"])
        if not asset or asset.get("type") != "video":
            continue
        metadata = asset.get("settings")
        if (type(metadata) is not dict or
                metadata.get("sourcePath") != str(original)):
            continue
        relative = asset.get("path")
        if (type(relative) is not str or not relative or
                Path(relative).is_absolute()):
            raise ValueError("Untrusted native source copy location")
        project_dir = project_file.parent.resolve(strict=True)
        copied = (project_dir / relative).resolve(strict=True)
        if (not copied.is_relative_to(project_dir) or
                not copied.is_file() or _sha256(copied) != ledger[0]["sha256"]):
            raise ValueError("Native original source bytes differ from ledger")
        duration = clip.get("duration")
        if (type(duration) not in (int, float) or
                not 0 < duration <= 6):
            raise ValueError("Invalid placed original video duration")
        real_original_clips += 1
    if not real_original_clips:
        raise ValueError("No physically source-backed video clip on saved active timeline")
    return {
        "native_project_sha256": _sha256(project_file),
        "active_native_timeline_id": active_id,
        "saved_active_clip_count": len(clips),
        "verified_source_backed_video_clips": real_original_clips,
        "artistic_quality_approved": False,
    }

def decoded_video_frames_sha256(path: Path):
    """Hash decoded RGB frames, not compressed MP4 bytes or container metadata.

    This deliberately compares the physical visible frame sequence. Rewrapping
    the same footage or changing export metadata cannot impersonate an
    independently visible model-selected creative revision. Human artistic
    approval is a separate judgment.
    """
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error",
         "-i", str(path), "-map", "0:v:0",
         "-vf", "format=rgb24",
         "-f", "framehash", "-hash", "SHA256", "-"],
        check=True, capture_output=True, text=True, timeout=90,
        env=_no_cloud_credentials())
    if len(result.stdout.encode("utf-8")) > 128_000:
        raise ValueError("Native video frame evidence exceeds safe output budget")
    hashes = []
    for line in result.stdout.splitlines():
        if line.startswith("#"):
            continue
        fields = [part.strip() for part in line.split(",")]
        if (len(fields) != 6 or fields[0] != "0" or
                not fields[5] or len(fields[5]) != 64 or
                any(char not in "0123456789abcdef" for char in fields[5]) or
                not fields[4].isdigit() or int(fields[4]) <= 0):
            raise ValueError("Malformed native decoded-frame SHA256 receipt")
        hashes.append(fields[5])
        if len(hashes) > 240:
            raise ValueError("Synthetic trial exceeds bounded decoded video frames")
    if not hashes:
        raise ValueError("Native output contains no decoded video frames")
    return tuple(hashes)


def run_trial(workspace: Path, *, model_id: str, xvfb_binary: str, display: str):
    if model_id != _ALLOWED_MODEL:
        raise ValueError("NVIDIA native trial model must match audited fixed catalog identity")
    roots, cfg = prepare_trial(workspace, source=_SOURCE_EDITOR)
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
        "--evaluation-evidence", "reviewed-revision",
        "--max-turns", "40",
        "--model-timeout", "90",
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
            cwd=ROOT, timeout=960)
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
    decoded_frame_sequences = []
    for path in mp4s:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
            check=True, timeout=90, env=_no_cloud_credentials())
        decoded_frame_sequences.append(decoded_video_frames_sha256(path))
        media.append({"path": str(path), "sha256": _sha256(path),
                      "bytes": path.stat().st_size,
                      "decoded_video_frames": len(decoded_frame_sequences[-1]),
                      "decoded_rgb_frame_sequence_sha256": hashlib.sha256(
                          json.dumps(decoded_frame_sequences[-1],
                                     separators=(",", ":")).encode()).hexdigest()})
    # Preserve forensic evidence even when final native state fails acceptance.
    # Never let an empty timeline disappear behind an early RuntimeError.
    try:
        saved_native = {
            **verify_saved_native_trial(workspace),
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
    independently_different_picture_exports = len(set(decoded_frame_sequences))
    evaluated = {
        **saved_native,
        "different_decoded_export_count": export_variants,
        "different_decoded_picture_sequence_count": independently_different_picture_exports,
        "status": summary.get("status"),
        "host_evidence_satisfied": summary.get("evaluation_evidence_satisfied") is True,
        "model_selected_write_receipts": summary.get("model_selected_write_receipts"),
        "physical_export_verify_receipts": summary.get("independently_verified_export_receipts"),
        "decoded_real_exports": media,
        "original_media_sent_to_model": False,
        "synthetic_frame_upload_explicitly_authorized": True,
        "artistic_quality_approved": False,
    }
    (workspace / "native-evaluation.json").write_text(
        json.dumps(evaluated, indent=2), encoding="utf-8")
    print(json.dumps(evaluated, ensure_ascii=False))
    if (summary.get("status") != "model_finished_unverified" or
            summary.get("evaluation_evidence_satisfied") is not True or
            len(media) < 2 or
            export_variants < 2 or
            independently_different_picture_exports < 2 or
            saved_native["native_saved_project_verified"] is not True):
        raise RuntimeError("Model did not meet full real-native visual-revision-export proof")
    return evaluated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--model-id", default=_ALLOWED_MODEL)
    parser.add_argument("--xvfb-binary", default="/usr/bin/Xvfb")
    parser.add_argument("--display", default="127.0.0.1:95")
    args = parser.parse_args(argv)
    run_trial(args.workspace, model_id=args.model_id,
              xvfb_binary=args.xvfb_binary, display=args.display)


if __name__ == "__main__":
    main()
