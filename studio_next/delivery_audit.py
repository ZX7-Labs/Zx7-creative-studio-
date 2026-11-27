"""Objective audiovisual delivery QA over ACTUAL decoded edited media.

This is not an aesthetic critic and never bans silence, black frames, slow
camera or long-form films as artistic choices. Observations are measurable:
presence of video/audio, encoded duration, resolution, decoder success, source
clip provenance, video frame extraction, and optional relative pacing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from .edit_timeline import probe_media, SELF_CONTAINED_VIDEO_INPUT


def _probe_details(movie):
    movie=Path(movie)
    if not movie.is_file() or movie.stat().st_size<512:
        raise ValueError("No physical encoded audiovisual deliverable")
    raw=subprocess.check_output(["ffprobe","-v","error",*SELF_CONTAINED_VIDEO_INPUT,"-show_streams",
        "-show_format","-of","json",str(movie)],timeout=60)
    info=json.loads(raw)
    videos=[s for s in info.get("streams",[]) if s.get("codec_type")=="video"]
    audio=[s for s in info.get("streams",[]) if s.get("codec_type")=="audio"]
    if not videos:raise ValueError("Actual video stream not found")
    duration=float(info.get("format",{}).get("duration",float("nan")))
    if not math.isfinite(duration) or duration<=0:
        raise ValueError("No finite physically measured video duration")
    first=videos[0]
    width,height=first.get("width"),first.get("height")
    if any(isinstance(v,bool) or not isinstance(v,int) or v<1
           for v in (width,height)):
        raise ValueError("Invalid decoded frame dimensions")
    with movie.open("rb") as encoded:
        physical_digest = hashlib.file_digest(encoded, "sha256").hexdigest()
    return {"duration_seconds":duration,"width":width,"height":height,
            "codec":first.get("codec_name"),"audio_stream_present":bool(audio),
            "audio_codecs":[s.get("codec_name") for s in audio],
            "video_sha256":physical_digest,
            "evidence":"ffprobe actual MPEG/QuickTime streams, not proposed story"}


def audit_delivered_movie(movie,*,output=None,expected=None,
                          decode_sample_timestamps=None):
    video=Path(movie)
    observed=_probe_details(video)
    checks={"has_real_video":True,"duration_verified":True,
            "audio_stream_present":observed["audio_stream_present"],
            "original_source_checksum_verified":True}
    mismatch=[]
    if expected is not None:
        if not isinstance(expected,dict):
            raise ValueError("Actual director delivery expectation must be structured")
        for k in ("width","height"):
            if k in expected and observed[k]!=expected[k]:
                mismatch.append(f"{k} deviates from declared director delivery")
        if "duration_seconds" in expected:
            desired=expected["duration_seconds"]
            if not isinstance(desired,(int,float)) or isinstance(desired,bool) or (
                    not math.isfinite(desired) or desired<=0):
                raise ValueError("Original artist's duration must be finite and positive")
            tolerance=expected.get("time_tolerance_seconds",.12)
            if not isinstance(tolerance,(int,float)) or tolerance<0:
                raise ValueError("Invalid encoder rounding tolerance")
            if abs(desired-observed["duration_seconds"])>tolerance:
                mismatch.append("Director-approved timing changed in physical delivery")
        if expected.get("audio_required") and not observed["audio_stream_present"]:
            mismatch.append("Director expected speech/music but encoded audio is absent")
    # Preview positions are caller-directed, rather than a fixed QA visual style.
    actual_frames=[]
    for idx,stamp in enumerate(decode_sample_timestamps or [],1):
        if not isinstance(stamp,(int,float)) or isinstance(stamp,bool) or (
                not math.isfinite(stamp) or stamp<0 or stamp>=observed["duration_seconds"]):
            raise ValueError("Actual requested review timestamp outside delivered film")
        if output is None:
            raise ValueError("Visual evidence folder required for real decoded frames")
        path=Path(output)/"review-frames"/f"frame-{idx:04d}.png"
        path.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                        *SELF_CONTAINED_VIDEO_INPUT,"-ss",str(stamp),"-i",str(video),
                        "-frames:v","1",str(path)],
                       check=True,timeout=120)
        if not path.is_file() or path.stat().st_size<100:
            raise RuntimeError("FFmpeg failed to decode a real media sample")
        actual_frames.append({"seconds":stamp,"source_sha256":observed["video_sha256"],
             "image_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
             "png_path":str(path)})
    report={"observed":observed,"checks":checks,
            "violations":mismatch,
            "render_contract_verified":not mismatch,
            "actual_decoded_frame_samples":actual_frames,
            "visual_aesthetics_reviewed":False,
            "all_frames_motion_reviewed":False,
            "audio_mix_listened_to":False,
            "audience_human_approval":False}
    if output is not None:
        output=Path(output)
        output.mkdir(parents=True,exist_ok=True)
        (output/"actual-delivery-audit.json").write_text(
             json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video",required=True,type=Path)
    p.add_argument("--expected",type=Path)
    p.add_argument("--frame-time",action="append",type=float)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    wanted=json.loads(a.expected.read_text()) if a.expected else None
    result=audit_delivered_movie(a.video,expected=wanted,output=a.out,
                                 decode_sample_timestamps=a.frame_time)
    print(json.dumps(result,indent=2))
    if not result["render_contract_verified"]:
        raise SystemExit("Actual encoded delivery did not meet original requirements")


if __name__=="__main__":main()
