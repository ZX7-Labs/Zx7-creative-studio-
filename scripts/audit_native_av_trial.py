"""Offline evidence check for an isolated six-second native audiovisual trial."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess

from scripts.run_nvidia_native_trial import (
    _TRIAL_FPS, _TRIAL_MAX_SECONDS, _no_cloud_credentials, decode_trial_export,
    trial_delivery_profile_compliant,
)
from studio_next.body_editor_client import _load_json
from studio_next.body_editor_export import native_export_file_identity


_CLIP_FIELDS = (
    "id", "trackId", "assetId", "type", "enabled", "startTime", "duration",
    "trimStart", "trimEnd", "speed", "reverse", "frameSampling", "transform",
    "opacity", "blendMode", "textProperties", "shapeProperties", "audioProperties",
    "gainDb", "fadeIn", "fadeOut", "audioInserts", "keyframes", "effects", "masks",
)
_TRACK_FIELDS = ("id", "type", "visible", "muted", "solo", "volume", "pan", "inserts", "channels")
_TIMELINE_FIELDS = ("transitions", "masterAudioVolume", "masterAudioInserts")


def _editorial_fields(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 16 * 1024 * 1024:
        raise ValueError("Invalid saved native snapshot")
    data = _load_json(path.read_text(encoding="utf-8"))
    active_id = data.get("currentTimelineId") if isinstance(data, dict) else None
    timelines = data.get("timelines") if isinstance(data, dict) else None
    if not isinstance(active_id, str) or not active_id or not isinstance(timelines, list):
        raise ValueError("Missing active native timeline")
    active = [item for item in timelines if isinstance(item, dict) and item.get("id") == active_id]
    if len(active) != 1:
        raise ValueError("Missing unique active native timeline")
    timeline = active[0]
    fields = {name: timeline.get(name) for name in _TIMELINE_FIELDS}
    for name, names in (("clips", _CLIP_FIELDS), ("tracks", _TRACK_FIELDS)):
        items = timeline.get(name)
        if not isinstance(items, list) or not items or any(
                not isinstance(item, dict) or not isinstance(item.get("id"), str)
                or not item["id"] for item in items):
            raise ValueError("Invalid editable native timeline items")
        if len({item["id"] for item in items}) != len(items):
            raise ValueError("Ambiguous editable native timeline items")
        fields[name] = [{key: item.get(key) for key in names} for item in items]
    return active_id, fields


def _decode_sound(path):
    def run(argv):
        return subprocess.run(argv, check=True, capture_output=True, timeout=30,
                              env=_no_cloud_credentials()).stdout

    raw = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=codec_type,codec_name,sample_rate,channels,channel_layout,start_time,time_base"
               ":format_tags=major_brand",
               "-of", "json", str(path)])
    probe = json.loads(raw)
    brand = probe.get("format", {}).get("tags", {}).get("major_brand")
    if brand not in {"isom", "iso2", "mp41", "mp42"}:
        raise ValueError("Trial export is missing a supported MP4 container brand")
    streams = probe.get("streams", [])
    if sorted(stream.get("codec_type", "") for stream in streams) != ["audio", "video"]:
        raise ValueError("Trial export needs one picture and one sound stream")
    audio = next(stream for stream in streams if stream["codec_type"] == "audio")
    channels = audio.get("channels")
    rate = audio.get("sample_rate")
    if (audio.get("codec_name") != "aac" or channels not in (1, 2)
            or rate not in ("44100", "48000") or Fraction(audio.get("start_time", "-1")) != 0):
        raise ValueError("Unexpected synthetic trial sound profile")
    pcm = run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(path),
               "-map", "0:a:0", "-t", "6.1", "-c:a", "pcm_s16le", "-f", "s16le", "-"])
    samples, remainder = divmod(len(pcm), channels * 2)
    if (remainder or abs(samples - int(rate) * _TRIAL_MAX_SECONDS) > int(rate) / _TRIAL_FPS
            or not any(pcm)):
        raise ValueError("Trial sound is silent or fails the six-second clock")
    return audio, samples, hashlib.sha256(pcm).hexdigest()


def audit_pair(before_export, after_export, before_project, after_project):
    before_timeline, before_edit = _editorial_fields(before_project)
    after_timeline, after_edit = _editorial_fields(after_project)
    if before_timeline != after_timeline or before_edit == after_edit:
        raise ValueError("Saved project lacks a comparable editorial change")

    before = decode_trial_export(before_export, max_frames=_TRIAL_FPS * _TRIAL_MAX_SECONDS)
    after = decode_trial_export(after_export, max_frames=_TRIAL_FPS * _TRIAL_MAX_SECONDS)
    if (before.picture_profile != after.picture_profile or
            any(not trial_delivery_profile_compliant(item) or
                len(item.presentation) != _TRIAL_FPS * _TRIAL_MAX_SECONDS
                for item in (before, after))):
        raise ValueError("Exports lack matching six-second physical picture profiles")
    before_sound = _decode_sound(before_export)
    after_sound = _decode_sound(after_export)
    if before_sound[:2] != after_sound[:2]:
        raise ValueError("Exports lack matching decoded audio profiles and sample counts")
    if (native_export_file_identity(before_export) != before.identity or
            native_export_file_identity(after_export) != after.identity):
        raise ValueError("An export changed during independent audio decoding")
    picture_changed = before.presentation != after.presentation
    sound_changed = before_sound[2] != after_sound[2]
    if not (picture_changed or sound_changed):
        raise ValueError("No decoded picture or sound changed")
    return {
        "same_saved_active_timeline": True,
        "saved_editorial_fields_changed": True,
        "decoded_picture_changed": picture_changed,
        "decoded_sound_changed": sound_changed,
        "export_sha256": [before.identity[-1], after.identity[-1]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before_export", type=Path)
    parser.add_argument("after_export", type=Path)
    parser.add_argument("before_project", type=Path)
    parser.add_argument("after_project", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_pair(**vars(args))))


if __name__ == "__main__":
    main()
