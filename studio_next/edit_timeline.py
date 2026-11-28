"""Render an editable, director-ordered multi-engine cut through trusted FFmpeg.

Input shots may come from 2D, true 3D, licensed camera footage or generative
video. No '2D only' studio rule; different engines can share the same film.
Framing is explicit. Existing audio is preserved or a *declared* silence is used.
This adapter does not itself make creative choices or certify story quality.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import subprocess
from pathlib import Path

_ID = re.compile(r"^[a-zA-Z0-9_.-]+$")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

# A content digest attests one self-contained movie, not a playlist or
# manifest which can open unowned secondary sources. Apply before opening
# each input, including content-addressed files with no filename extension.
SELF_CONTAINED_VIDEO_INPUT = ("-protocol_whitelist", "file,pipe",
                              "-format_whitelist", "mov,matroska,webm")


def _require(x, message):
    if not x: raise ValueError(message)


def _path_within(root: Path, value: str, *, exists: bool):
    _require(isinstance(value,str) and value and not Path(value).is_absolute(),
             "Only relative media paths in trusted workspace")
    _require(all(p not in (".","..") for p in Path(value).parts),
             "Path escapes trusted workspace")
    root=Path(root).resolve()
    out=(root/value).resolve()
    _require(out.is_relative_to(root),"Path outside trusted workspace")
    if exists:
        _require(out.is_file(),"Media missing: "+value)
    return out


def validate_edit(edit, root, *, check_sources=True):
    _require(isinstance(edit,dict) and set(edit)=={"format","clips"},
             "Edit must contain director format and ordered clips")
    fmt=edit["format"]
    _require(isinstance(fmt,dict) and set(fmt)=={"width","height","fps","framing","background"},
             "Director must specify complete export/framing choices")
    for field in ("width","height","fps"):
        v=fmt[field]
        _require(isinstance(v,int) and not isinstance(v,bool) and v>0,
                 field+" must be positive integer")
    _require(fmt["framing"] in ("fit","fill"),"Director must choose fit or fill")
    _require(isinstance(fmt["background"],str) and _COLOR.fullmatch(fmt["background"]),
             "Director must choose exact background color")
    clips=edit["clips"]
    _require(isinstance(clips,list) and clips,
             "No film clips")
    ids=set()
    for i,c in enumerate(clips):
        _require(isinstance(c,dict) and set(c)=={"id","source","rights","audio"},
                 f"Clip {i} incomplete")
        name=c["id"]
        _require(isinstance(name,str) and _ID.fullmatch(name) and name not in ids,
                 "Missing or duplicate clip ID")
        ids.add(name)
        _require(c["rights"] in ("owner_supplied","generated_original","appropriately_licensed"),
                 name+": source license unverified")
        _require(c["audio"] in ("preserve_source","intentional_silence"),
                 name+": no implicit narration deletion")
        path=_path_within(root,c["source"],exists=check_sources)
        _require(path.suffix.lower() in (".mp4",".mov",".mkv",".webm"),
                 name+": media format must be a known video container")
    return edit


def probe_media(path):
    raw=subprocess.check_output(["ffprobe","-v","error",*SELF_CONTAINED_VIDEO_INPUT,"-show_streams","-show_format",
                                  "-of","json",str(path)],timeout=45)
    data=json.loads(raw)
    videos=[x for x in data["streams"] if x.get("codec_type")=="video"]
    audio=[x for x in data["streams"] if x.get("codec_type")=="audio"]
    _require(len(videos)>=1,"Source has no real video stream")
    duration=float(data["format"]["duration"])
    _require(math.isfinite(duration) and duration>0,"Invalid clip duration")
    return {"seconds":duration,"audio":bool(audio),"codec":videos[0].get("codec_name")}


def edit_ffmpeg_command(edit, root, dest, *, source_info):
    """Build an audited argv and filtergraph, not a model-supplied shell command."""
    validate_edit(edit,root)
    _require(isinstance(source_info,list) and len(source_info)==len(edit["clips"]),
             "Measured input metadata required for each original clip")
    fmt=edit["format"]
    w,h,fps=fmt["width"],fmt["height"],fmt["fps"]
    frags=[]
    concat=[]
    argv=["ffmpeg","-hide_banner","-loglevel","error","-y"]
    for i,(clip,info) in enumerate(zip(edit["clips"],source_info)):
        path=_path_within(root,clip["source"],exists=True)
        secs=info.get("seconds")
        _require(isinstance(secs,(int,float)) and not isinstance(secs,bool)
                 and math.isfinite(secs) and secs>0,"Unproven source duration")
        has_audio=info.get("audio")
        _require(isinstance(has_audio,bool),"Audio presence must be measured")
        if clip["audio"]=="preserve_source":
            _require(has_audio,clip["id"]+": cannot pretend narration exists")
        argv+=[*SELF_CONTAINED_VIDEO_INPUT,"-i",str(path)]
        if fmt["framing"]=="fit":
            resizing=(f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                      f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:"
                      f"color=0x{fmt['background'][1:]}")
        else:
            resizing=(f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                      f"crop={w}:{h}:(iw-ow)/2:(ih-oh)/2")
        frags.append(f"[{i}:v:0]{resizing},fps={fps},"
                     f"trim=duration={secs:.5f},setpts=PTS-STARTPTS[v{i}]")
        if clip["audio"]=="preserve_source":
            frags.append(f"[{i}:a:0]aresample=48000,aformat=sample_fmts=fltp:"
                         f"channel_layouts=stereo,apad,atrim=duration={secs:.5f},"
                         f"asetpts=PTS-STARTPTS[a{i}]")
        else:
            frags.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={secs:.5f},"
                         f"asetpts=PTS-STARTPTS[a{i}]")
        concat.append(f"[v{i}][a{i}]")
    frags.append("".join(concat)+f"concat=n={len(edit['clips'])}:v=1:a=1[v][a]")
    argv+=["-filter_complex",";".join(frags),"-map","[v]","-map","[a]",
           "-c:v","libx264","-pix_fmt","yuv420p","-crf","20",
           "-c:a","aac","-b:a","160k",
           # Preserve timestamps and fill only omitted packet durations
           # using the explicitly authored frame clock, not a CFR conversion.
           "-bsf:v",f"setts=duration=if(gt(DURATION\\,0)\\,DURATION\\,round(1/({fps}*TB))):pts=PTS:dts=DTS",
           "-movflags","+faststart",str(dest)]
    return argv


def render_edit(edit_path, root, dest):
    edit=json.loads(Path(edit_path).read_text(encoding="utf-8"))
    validate_edit(edit,root)
    info=[probe_media(_path_within(root,clip["source"],exists=True))
          for clip in edit["clips"]]
    dest=Path(dest).resolve()
    _require(dest.suffix.lower()==".mp4","Output must be MP4")
    dest.parent.mkdir(parents=True,exist_ok=True)
    cmd=edit_ffmpeg_command(edit,root,dest,source_info=info)
    subprocess.run(cmd,check=True,timeout=3600)
    final=probe_media(dest)
    _require(final["audio"],"Rendered edit missing audio stream")
    report={"engine":"FFmpeg authored multi-source timeline","source_engines":
            [c["id"] for c in edit["clips"]],"source_media":info,"export":str(dest),
            "output":final,"claim":"Real encoded edit, not creative/human-quality certification"}
    (dest.parent/"edit-manifest.json").write_text(json.dumps(report,indent=2))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--edit",type=Path,required=True)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    x=p.parse_args()
    print(json.dumps(render_edit(x.edit,x.root,x.out),indent=2))


if __name__=="__main__":main()
