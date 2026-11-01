"""Observe measured editing grammar of an explicitly authorized local reference.

This instrument does not download internet video, infer semantic content,
predict audience impact, or certify creative merit. It streams a tiny decoded
grayscale plane and the real audio into bounded physical evidence.
"""
from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys


class ReferenceObservationError(ValueError):
    """Reference unavailable, invalid, or outside host resource budget."""


def _local_source(value):
    path = Path(value).resolve(strict=True)
    if not path.is_file():
        raise ReferenceObservationError("Reference must be a local regular file")
    return path


def _probe(path):
    try:
        raw = subprocess.check_output([
            "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
            "-show_entries", "format=duration:stream=codec_type,width,height",
            "-of", "json", str(path)], timeout=60)
        doc = json.loads(raw)
        seconds = float(doc["format"]["duration"])
        if not math.isfinite(seconds) or seconds <= 0:
            raise ReferenceObservationError("Reference duration is not finite and positive")
        streams = doc.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        if video is None or not video.get("width") or not video.get("height"):
            raise ReferenceObservationError("A decodable picture stream is required")
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        return seconds, has_audio, video
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired,
            KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ReferenceObservationError):
            raise
        raise ReferenceObservationError("Unable to probe local reference") from exc


def _read_exact(pipe, count):
    data = bytearray()
    while len(data) < count:
        part = pipe.read(count - len(data))
        if not part:
            break
        data.extend(part)
    return bytes(data)


def _decode_video(path, fps, max_samples):
    width, height = 96, 54
    frame_size = width * height
    args = ["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
            "-i", str(path), "-map", "0:v:0", "-an",
            "-vf", f"fps={fps},scale={width}:{height}:flags=fast_bilinear,format=gray",
            "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise ReferenceObservationError("FFmpeg video decoder not installed") from exc
    rows = []
    previous = None
    try:
        while True:
            frame = _read_exact(proc.stdout, frame_size)
            if not frame:
                break
            if len(frame) != frame_size:
                raise ReferenceObservationError("Video decoder returned an incomplete frame")
            if len(rows) >= max_samples:
                raise ReferenceObservationError("Reference exceeds configured observation budget")
            brightness = sum(frame)/(255.0*frame_size)
            difference = (sum(abs(a-b) for a, b in zip(frame, previous)) /
                          (255.0*frame_size)) if previous is not None else 0.0
            rows.append({"second": round(len(rows)/fps, 4),
                         "luma": round(brightness, 4),
                         "frame_difference": round(difference, 4)})
            previous = frame
        if proc.wait(timeout=30):
            raise ReferenceObservationError("Actual full video decode failed")
        if not rows:
            raise ReferenceObservationError("Reference has no decoded samples")
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        if proc.stdout:
            proc.stdout.close()
    return rows


def _decode_audio(path, max_audio_seconds):
    rate = 8000
    args = ["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
            "-i", str(path), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(rate),
            "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"]
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise ReferenceObservationError("FFmpeg audio decoder not installed") from exc
    rows = []
    try:
        while True:
            data = _read_exact(proc.stdout, rate*4)
            if not data:
                break
            if len(data) % 4:
                raise ReferenceObservationError("Audio decoder returned a partial sample")
            if len(rows) >= max_audio_seconds:
                raise ReferenceObservationError("Audio exceeds configured observation budget")
            samples = array("f")
            samples.frombytes(data)
            if sys.byteorder != "little":
                samples.byteswap()
            if not all(math.isfinite(x) for x in samples):
                raise ReferenceObservationError("Audio decoder returned nonfinite samples")
            power = sum(x*x for x in samples)/len(samples)
            peak = max(abs(x) for x in samples)
            rows.append({"second": len(rows),
                         "rms_dbfs": round(20*math.log10(max(math.sqrt(power), 1e-6)), 2),
                         "peak_dbfs": round(20*math.log10(max(peak, 1e-6)), 2)})
        if proc.wait(timeout=30):
            raise ReferenceObservationError("Actual full audio decode failed")
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        if proc.stdout:
            proc.stdout.close()
    return rows


def observe_reference(movie, *, sample_fps=8, max_duration_seconds=28800,
                      max_video_samples=250000, output=None):
    """Scan actual picture and audio without saving original private media.

    Budgets cap host work, not art direction; hosts can raise or chunk them.
    Cuts are candidates only: flashes/fades/pans may trigger them and real
    edits between sampled frames may be missed.
    """
    if (type(sample_fps) is not int or not 1 <= sample_fps <= 24 or
            type(max_duration_seconds) is not int or max_duration_seconds <= 0 or
            type(max_video_samples) is not int or max_video_samples <= 0):
        raise ReferenceObservationError("Invalid physical observation budget")
    source = _local_source(movie)
    seconds, has_audio, stream = _probe(source)
    if seconds > max_duration_seconds or math.ceil(seconds*sample_fps) > max_video_samples:
        raise ReferenceObservationError("Reference exceeds bounded scan budget")
    video = _decode_video(source, sample_fps, max_video_samples)
    audio = _decode_audio(source, max_duration_seconds+2) if has_audio else []
    differences = sorted(x["frame_difference"] for x in video[1:])
    median = differences[len(differences)//2] if differences else 0.0
    deviations = sorted(abs(x-median) for x in differences)
    mad = deviations[len(deviations)//2] if deviations else 0.0
    threshold = max(0.10, median + 8*mad)
    candidates = [x["second"] for x in video[1:] if x["frame_difference"] >= threshold]
    with source.open("rb") as stream_bytes:
        digest = hashlib.file_digest(stream_bytes, "sha256").hexdigest()
    result = {
        "schema": "ZX7_REFERENCE_OBSERVATION_V1",
        "source_sha256": digest,
        "source_size_bytes": source.stat().st_size,
        "duration_seconds": round(seconds, 4),
        "source_resolution": [stream["width"], stream["height"]],
        "visual_sample_fps": sample_fps,
        "visual_observations": video,
        "cut_candidates_seconds": candidates,
        "cut_candidate_threshold": round(threshold, 4),
        "audio_observations": audio,
        "has_audio": has_audio,
        "limits": {
            "cut_detection": "sampled grayscale difference; missed and false cuts possible",
            "semantic_understanding": "not measured",
            "transitions": "not independently classified",
            "music_genre": "not measured",
            "audience_response": "not observed; metrics do not establish causality",
            "professional_artistic_quality": "not certified",
            "source_rights": "caller authorization required; no ownership inferred",
        },
    }
    if output is not None:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        pending = destination.with_name(destination.name + ".uncommitted")
        try:
            with pending.open("x", encoding="utf-8") as sink:
                json.dump(result, sink, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
                sink.flush()
                os.fsync(sink.fileno())
            os.replace(pending, destination)
        finally:
            pending.unlink(missing_ok=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure an authorized local video")
    parser.add_argument("movie")
    parser.add_argument("--output")
    parser.add_argument("--sample-fps", type=int, default=8)
    options = parser.parse_args(argv)
    result = observe_reference(options.movie, sample_fps=options.sample_fps,
                               output=options.output)
    print(json.dumps({
        "sha256": result["source_sha256"],
        "duration_seconds": result["duration_seconds"],
        "samples": len(result["visual_observations"]),
        "cut_candidates": len(result["cut_candidates_seconds"]),
        "audio_seconds": len(result["audio_observations"])}, sort_keys=True))


if __name__ == "__main__":
    main()
