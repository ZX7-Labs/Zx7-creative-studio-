"""Shared physical stream-copy evidence for original native media revisions."""
from __future__ import annotations

import json
import re
import subprocess

from .edit_timeline import SELF_CONTAINED_VIDEO_INPUT
from .media_vault import sha256_file


_AV_FIELDS = (
    "codec_type", "codec_name", "profile", "codec_tag_string", "width", "height",
    "pix_fmt", "sample_aspect_ratio", "field_order", "color_range", "color_space",
    "color_transfer", "color_primaries", "chroma_location", "sample_rate", "channels",
    "channel_layout", "sample_fmt", "bits_per_raw_sample", "bits_per_sample",
    "time_base", "start_pts", "duration_ts", "r_frame_rate", "avg_frame_rate",
    "nb_frames", "extradata_hash", "disposition", "side_data_list",
)


def _probe(path):
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error",
        *SELF_CONTAINED_VIDEO_INPUT, "-show_streams", "-show_format", "-show_chapters",
        "-show_data_hash", "sha256", "-of", "json", str(path)], timeout=120))


def _packet_digest(path, index, scratch):
    # Include packet time, flags, encoded payload digest and side data (e.g.
    # AAC priming). Use disk instead of holding a long film's packets in RAM.
    with scratch.open("wb") as report:
        subprocess.run(["ffprobe", "-v", "error", *SELF_CONTAINED_VIDEO_INPUT,
            "-select_streams", str(index), "-show_packets", "-show_data_hash", "sha256",
            "-show_entries", "packet=pts,dts,duration,size,flags,data_hash:packet_side_data",
            "-of", "compact=p=0", str(path)], stdout=report, stderr=subprocess.PIPE,
            timeout=7200, check=True)
    if not scratch.stat().st_size:
        raise ValueError("No original encoded A/V packets verified")
    return sha256_file(scratch)


def _decoded_av(path, video, audio_count):
    # Decode all native picture frames at original pixel precision and every
    # audio track to float64 PCM. This independently checks the packet proof.
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-xerror", "-nostdin",
        *SELF_CONTAINED_VIDEO_INPUT, "-i", str(path), "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "rawvideo", "-pix_fmt", video["pix_fmt"], "-fps_mode", "passthrough",
        "-threads:v", "1", "-c:a", "pcm_f64le", "-f", "streamhash", "-hash", "sha256", "-"],
        timeout=7200).decode("ascii")
    lines = raw.splitlines()
    if (len(lines) != 1 + audio_count or any(not re.fullmatch(
            r"\d+,[va],SHA256=[0-9a-f]{64}", line) for line in lines)):
        raise ValueError("Incomplete full-program decoded A/V proof")
    return lines


