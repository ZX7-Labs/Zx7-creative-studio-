"""Actual editable multilingual QuickTime/MP4 timed-text delivery.

The artist supplies text, language, timing and default selection. The original
A/V streams are copied, not re-encoded. Only plain-text timed tracks are added;
this is neither transcription, translation nor caption accessibility review.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from .body_document_schemas import validate_document
from .composite_mix import _exact_media, sealed_attested_original
from .edit_timeline import SELF_CONTAINED_VIDEO_INPUT
from .media_vault import MediaVault, sha256_file
from .body_stream_custody import _AV_FIELDS, _probe, _packet_digest, _decoded_av


# Bound authored data; full-program codec verification is streamed to disk.
_MAX_PLAN_BYTES = 4 * 1024 * 1024
_MOVIE_MIMES = {"video/mp4": ".mp4", "video/quicktime": ".mov"}
def _timestamp(ms):
    hours, remaining = divmod(ms, 3600000)
    minutes, remaining = divmod(remaining, 60000)
    seconds, millis = divmod(remaining, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def _srt(track, picture_duration):
    blocks = []
    previous = 0
    for i, cue in enumerate(track["cues"], 1):
        start, end, text = cue["start_ms"], cue["end_ms"], cue["text"]
        if start < previous or end <= start or Fraction(end, 1000) > picture_duration:
            raise ValueError("Subtitle cues must be ordered, non-overlapping and within the original picture")
        if (len(text.encode("utf-8")) > 8192 or any(not line.strip() for line in text.split("\n"))
                or any(c in text for c in "<>{}") or any(ord(c) < 32 and c != "\n" for c in text)):
            raise ValueError("Only nonempty plain-text subtitle lines without markup/control characters are supported")
        blocks.append(f"{i}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n\n")
        previous = end
    return "".join(blocks)


def render_subtitle_delivery(plan_file, workspace, vault_root, output):
    root = Path(workspace).resolve()
    source = Path(plan_file).resolve()
    output = Path(output).absolute()
    if (not source.is_relative_to(root) or not source.is_file() or
            source.stat().st_size > _MAX_PLAN_BYTES or
            not output.parent.resolve().is_relative_to(root) or output.exists() or output.is_symlink()):
        raise ValueError("Subtitle delivery requires a bounded owner plan and a new workspace output")
    raw = source.read_bytes()
    if len(raw) > _MAX_PLAN_BYTES:
        raise ValueError("Subtitle plan exceeds its bounded document size")
    plan_sha = hashlib.sha256(raw).hexdigest()
    plan = json.loads(raw)
    validate_document("body.subtitle_delivery", plan)
    # MOV/MP4 muxers can silently enable the first text track when none is
    # selected. Require an explicit single default rather than choose for art.
    if sum(t["default"] for t in plan["tracks"]) != 1:
        raise ValueError("Exactly one explicitly authored default subtitle track required")
    media = plan["media"]
    vault = MediaVault(vault_root)
    original = _exact_media(media, vault, root, need="video")
    digest, attestation = media["asset_id"], media["attestation_id"]
    record = vault.inspect(digest, attestation_id=attestation)
    if _MOVIE_MIMES.get(record["mime"]) != output.suffix.lower():
        raise ValueError("Only same-container MP4/QuickTime subtitle delivery is supported")

    def source_unchanged(frozen):
        if (sha256_file(source) != plan_sha or sha256_file(original) != digest or
                sha256_file(frozen) != digest):
            raise ValueError("Original film or authored subtitle plan changed during delivery")
        vault.inspect(digest, attestation_id=attestation)

    with tempfile.TemporaryDirectory(prefix=".zx7-subtitle-", dir=root) as working:
        private = Path(working)
        frozen = sealed_attested_original(vault, digest, attestation, private, {})
        source_unchanged(frozen)
        info = _probe(frozen)
        streams = info["streams"]
        videos = [s for s in streams if s["codec_type"] == "video"]
        if (len(videos) != 1 or any(s["codec_type"] not in ("video", "audio") for s in streams)
                or videos[0].get("disposition", {}).get("attached_pic") or info.get("chapters")):
            raise ValueError("One picture stream, optional audio, and no existing non-A/V streams or chapters required")
        video = videos[0]
        if video.get("start_pts") != 0 or not isinstance(video.get("duration_ts"), int):
            raise ValueError("Subtitle timing requires an exact zero-origin picture clock")
        duration = video["duration_ts"] * Fraction(video["time_base"])
        if duration <= 0:
            raise ValueError("Original picture has no positive exact duration")
        expected = [_srt(track, duration) for track in plan["tracks"]]
        args = ["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-n", "-copyts",
                *SELF_CONTAINED_VIDEO_INPUT, "-i", str(frozen)]
        for i, content in enumerate(expected):
            cue_file = private / f"track-{i}.srt"
            cue_file.write_text(content, encoding="utf-8")
            args.extend(["-protocol_whitelist", "file,pipe", "-f", "srt", "-i", str(cue_file)])
        args.extend(["-map", "0"])
        for i in range(len(expected)):
            args.extend(["-map", f"{i+1}:0"])
        args.extend(["-c", "copy", "-c:s", "mov_text", "-map_metadata", "0", "-map_chapters", "0"])
        for i, track in enumerate(plan["tracks"]):
            args.extend([f"-metadata:s:s:{i}", f"language={track['language']}",
                         f"-disposition:s:{i}", "default" if track["default"] else "0"])
        movie = private / ("delivered" + output.suffix.lower())
        subprocess.run(args + [str(movie)], check=True, capture_output=True, timeout=7200)
        actual = _probe(movie)["streams"]
        if len(actual) != len(streams) + len(expected):
            raise ValueError("Native mux lost an original stream or authored subtitle track")
        for before, after in zip(streams, actual):
            if (any(before.get(k) != after.get(k) for k in _AV_FIELDS) or
                    any(before.get("tags", {}).get(k) != after.get("tags", {}).get(k)
                        for k in ("language", "title", "handler_name")) or
                    _packet_digest(frozen, before["index"], private / "packets-before") !=
                    _packet_digest(movie, after["index"], private / "packets-after")):
                raise ValueError("Subtitle mux changed original A/V codec parameters, time or packets")
        audio_count = len(streams) - 1
        if _decoded_av(frozen, video, audio_count) != _decoded_av(movie, video, audio_count):
            raise ValueError("Subtitle mux changed decoded original picture or sound")
        for i, (track, content, stream) in enumerate(zip(plan["tracks"], expected, actual[len(streams):])):
            if (stream.get("codec_type") != "subtitle" or stream.get("codec_name") != "mov_text" or
                    stream.get("tags", {}).get("language") != track["language"] or
                    bool(stream.get("disposition", {}).get("default")) != track["default"]):
                raise ValueError("Native timed-text track lost its codec, language or selection")
            decoded = subprocess.check_output(["ffmpeg", "-v", "error", "-xerror", "-nostdin",
                *SELF_CONTAINED_VIDEO_INPUT, "-i", str(movie), "-map", f"0:s:{i}",
                "-f", "srt", "-"], timeout=7200).decode("utf-8").replace("\r\n", "\n")
            if decoded.rstrip("\n") != content.rstrip("\n"):
                raise ValueError("Decoded subtitle text or authored millisecond timing changed")
        source_unchanged(frozen)
        os.link(movie, output)
    return {"subtitle_tracks": len(expected), "original_av_streams": len(streams),
            "original_source_sha256": digest, "editable_plan_sha256": plan_sha,
            "actual_encoded_packets_and_decoded_av_preserved": True,
            "actual_timed_text_roundtrip_verified": True,
            "transcription_translation_or_accessibility_reviewed": False}
