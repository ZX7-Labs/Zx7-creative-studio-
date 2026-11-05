"""Independent local-neural edit of a REAL unedited recorded camera take.

Only creative user brief passed to the model: "Edit this video."
The tool grammar advertises available native operations, never an editorial
style, story, camera, text, transition, or music choice. A failure cannot
masquerade as an edited film.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from io import BytesIO

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PIL import Image, ImageDraw, ImageFont

from studio_next.providers import LocalCreativeModel,LocalModelSettings
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.raw_edit_coverage import assess_raw_edit_coverage
from studio_next.raw_temporal_observer import inspect_raw_temporal_source, render_camera_contact_sheet
from studio_next.body_mlt_editor import export_owned_mlt
from studio_next.body_mlt_render import render_owned_mlt
from studio_next.production_qc import full_decode_inspection
from scripts.run_local_brain_creative_film import _await_model,_render_music

RATE=24
WIDTH=1280
HEIGHT=720
MAX_MOVIE_SECONDS=120
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SYSTEM="You are the editor. You decide every creative choice. Return only a JSON edit decision for the actual input video. Never invent media, rights, footage, or commands."

def run(argv,*,timeout=120):
    return subprocess.run(argv,capture_output=True,text=True,check=True,timeout=timeout)

def safe_json(path,value):
    with Path(path).open("x",encoding="utf-8") as file:
        json.dump(value,file,ensure_ascii=False,indent=2)

def probe(path):
    result=json.loads(run([
        "ffprobe","-v","error","-show_entries",
        "format=duration:stream=codec_type,width,height,r_frame_rate",
        "-of","json",str(path)],timeout=55).stdout)
    video=next(s for s in result["streams"] if s["codec_type"]=="video")
    return {"duration":float(result["format"]["duration"]),
            "width":video["width"],"height":video["height"],
            "fps":video["r_frame_rate"],
            "has_audio":any(s["codec_type"]=="audio" for s in result["streams"])}

def receipt(path):
    p=Path(path)
    return {"path":str(p),"sha256":sha256_file(p),"bytes":p.stat().st_size}

def shot_reel(raw,info,out,*,sample_times_seconds):
    """Source-bound camera contact sheet; observations are not story understanding."""
    return render_camera_contact_sheet(raw,info["duration"],sample_times_seconds,out)


def plan_schema(length):
    max_second=min(1200,math.ceil(length))
    return {
        "type":"object","additionalProperties":False,
        "required":["cuts","graphics","music"],
        "properties":{
          "cuts":{"type":"array","minItems":1,"maxItems":12,
                  "items":{"type":"object","additionalProperties":False,
                           "required":["source_in","source_out","speed","contrast","saturation"],
                           "properties":{
                             "source_in":{"type":"number","minimum":0,"maximum":max_second},
                             "source_out":{"type":"number","minimum":0,"maximum":max_second},
                             "speed":{"type":"number","minimum":0.5,"maximum":2.0},
                             "contrast":{"type":"number","minimum":0.6,"maximum":1.5},
                             "saturation":{"type":"number","minimum":0.0,"maximum":2.0},
                           }}},
          "graphics":{"type":"array","minItems":0,"maxItems":8,
                     "items":{"type":"object","additionalProperties":False,
                              "required":["text","start","end","x0","y0","x1","y1",
                                          "size","red","green","blue"],
                              "properties":{
                                "text":{"type":"string","minLength":1,"maxLength":70},
                                "start":{"type":"number","minimum":0,"maximum":MAX_MOVIE_SECONDS},
                                "end":{"type":"number","minimum":0,"maximum":MAX_MOVIE_SECONDS},
                                "x0":{"type":"integer","minimum":0,"maximum":1100},
                                "y0":{"type":"integer","minimum":0,"maximum":620},
                                "x1":{"type":"integer","minimum":0,"maximum":1100},
                                "y1":{"type":"integer","minimum":0,"maximum":620},
                                "size":{"type":"integer","minimum":18,"maximum":80},
                                "red":{"type":"integer","minimum":0,"maximum":255},
                                "green":{"type":"integer","minimum":0,"maximum":255},
                                "blue":{"type":"integer","minimum":0,"maximum":255},
                              }}},
          "music":{"type":"object","additionalProperties":False,
                   "required":["enabled","bpm","root_midi","mode","progression"],
                   "properties":{
                    "enabled":{"type":"boolean"},
                    "bpm":{"type":"integer","minimum":55,"maximum":155},
                    "root_midi":{"type":"integer","minimum":40,"maximum":72},
                    "mode":{"type":"string","enum":["minor","major"]},
                    "progression":{"type":"array","minItems":2,"maxItems":8,
                                   "items":{"type":"integer","minimum":0,"maximum":6}},
                   }},
        }}

def validate_edit(plan,source_seconds):
    if type(plan) is not dict or set(plan)!={"cuts","graphics","music"}:
        raise ValueError("Local model must supply its own exact admissible edit")
    cuts=plan["cuts"];graphics=plan["graphics"]
    if not isinstance(cuts,list) or not 1<=len(cuts)<=12:
        raise ValueError("Model did not choose a bounded native edit")
    total=0
    for clip in cuts:
        if type(clip) is not dict or set(clip)!={"source_in","source_out","speed","contrast","saturation"}:
            raise ValueError("A neural clip does not match original native controls")
        for key,lo,hi in [
            ("source_in",0,source_seconds),("source_out",0,source_seconds),
            ("speed",0.5,2.0),("contrast",0.6,1.5),("saturation",0,2.0)]:
            v=clip[key]
            if type(v) not in (float,int) or not math.isfinite(v) or not lo<=v<=hi:
                raise ValueError("Model supplied an impossible physical clip value: "+key)
        if clip["source_out"]-clip["source_in"]<1.0:
            raise ValueError("Neural cut has no observable source duration")
        total+=(clip["source_out"]-clip["source_in"])/clip["speed"]
    if total>MAX_MOVIE_SECONDS or total<2:
        raise ValueError("Model timeline exceeds physically available free rendering budget")
    if not isinstance(graphics,list) or len(graphics)>8:
        raise ValueError("Model graphic track exceeds physical compositor budget")
    for item in graphics:
        if type(item) is not dict or set(item)!={
            "text","start","end","x0","y0","x1","y1","size","red","green","blue"}:
            raise ValueError("Unregistered native graphic operation")
        if not isinstance(item["text"],str) or not 1<=len(item["text"])<=70:
            raise ValueError("Unrenderable text")
        if not all(type(item[k]) in (int,float) and math.isfinite(item[k])
                   for k in ("start","end")) or not 0<=item["start"]<item["end"]<=total:
            raise ValueError("Graphic exceeds selected raw edit's film clock")
        for key,low,high in (
            ("x0",0,1100),("y0",0,620),("x1",0,1100),("y1",0,620),
            ("size",18,80),("red",0,255),("green",0,255),("blue",0,255)):
            if type(item[key]) is not int or not low<=item[key]<=high:
                raise ValueError("Model-authored graphic geometry is not executable")
    m=plan["music"]
    if type(m) is not dict or set(m)!={"enabled","bpm","root_midi","mode","progression"}:
        raise ValueError("Incomplete creative soundtrack choice")
    if type(m["enabled"]) is not bool:
        raise ValueError("Soundtrack enable requires neural boolean")
    if type(m["bpm"]) is not int or not 55<=m["bpm"]<=155 or (
        type(m["root_midi"]) is not int or not 40<=m["root_midi"]<=72
        or m["mode"] not in ("minor","major")
        or type(m["progression"]) is not list or not 2<=len(m["progression"])<=8
        or any(type(x) is not int or not 0<=x<=6 for x in m["progression"])):
        raise ValueError("Local AI musical decision exceeds actual renderer abilities")
    return total

def create_graphic(item,path):
    text=item["text"]
    font=ImageFont.truetype(FONT,item["size"])
    probe=ImageDraw.Draw(Image.new("RGBA",(1280,720)))
    bounds=probe.textbbox((0,0),text,font=font,stroke_width=0)
    w=bounds[2]-bounds[0]+22;h=bounds[3]-bounds[1]+22
    if w>WIDTH or h>HEIGHT:
        raise ValueError("Text cannot fit in native render; do not truncate neural creation")
    img=Image.new("RGBA",(w,h),(0,0,0,0))
    draw=ImageDraw.Draw(img)
    draw.text((11-bounds[0],11-bounds[1]),text,font=font,
              fill=(item["red"],item["green"],item["blue"],255),
              stroke_width=2,stroke_fill=(5,9,15,240))
    img.save(path,format="PNG")
    return w,h

def overlay_graphics(movie,graphics,dest,temp):
    if not graphics:
        # No host-invented titles or effects: model may choose no graphics.
        os.link(movie,dest)
        return {"authored_graphics":0,"applied":False}
    argv=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-i",str(movie)]
    filters=[]
    prev="[0:v]"
    for index,item in enumerate(graphics):
        png=temp/f"author-title-{index:02d}.png"
        w,h=create_graphic(item,png)
        if max(item["x0"],item["x1"])+w>WIDTH or max(item["y0"],item["y1"])+h>HEIGHT:
            raise ValueError("Neural graphic would overflow actual picture; no clipping permitted")
        argv+=["-loop","1","-framerate",str(RATE),"-i",str(png)]
        duration=item["end"]-item["start"]
        dx=item["x1"]-item["x0"];dy=item["y1"]-item["y0"]
        # Only numeric, typed, host-generated native expressions.
        progress=f"min(max((t-{item['start']:.6f})/{duration:.6f},0),1)"
        posx=f"{item['x0']}+({dx})*{progress}"
        posy=f"{item['y0']}+({dy})*{progress}"
        nextref=f"[layer{index}]"
        filters.append(prev+f"[{index+1}:v]overlay=x='{posx}':y='{posy}':"+
                       f"enable='between(t,{item['start']:.6f},{item['end']:.6f})'"+
                       f":format=auto{nextref}")
        prev=nextref
    # PNG overlays loop forever. Without a frame-exact output clock,
    # FFmpeg overlay continues encoding the frozen last source frame forever.
    # Derive the bound from independently decoded original source frames,
    # never from the model's asserted duration or an arbitrary timeout.
    measured=json.loads(run([
        "ffprobe","-v","error","-count_frames","-select_streams","v:0",
        "-show_entries","stream=nb_read_frames","-of","json",str(movie)],
        timeout=60).stdout)
    actual_frames=int(measured["streams"][0]["nb_read_frames"])
    if not 1<=actual_frames<=MAX_MOVIE_SECONDS*RATE:
        raise ValueError("Real movie has no bounded original video frame clock")
    argv+=["-filter_complex",";".join(filters),"-map",prev,"-an",
           "-c:v","libx264","-preset","veryfast","-crf","18",
           "-frames:v",str(actual_frames),
           "-pix_fmt","yuv420p","-r",str(RATE),"-movflags","+faststart",str(dest)]
    run(argv,timeout=480)
    return {"authored_graphics":len(graphics),"applied":True}

def produce(args):
    out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    root=out/"workspace";root.mkdir()
    src=Path(args.source).resolve(strict=True)
    manifest=json.loads(Path(args.rights).read_text())
    if manifest.get("license_declared_by_source") not in ("CC0","CC0 1.0"):
        raise ValueError("Video must have official source CC0 rights evidence")
    if not manifest.get("full_picture_decode_completed"):
        raise ValueError("No physically decoded unedited human camera source")
    if manifest.get("sha256")!=sha256_file(src):
        raise ValueError("Source bytes do not match original published evidence")
    spec=probe(src)
    if not 30<=spec["duration"]<=1200:
        raise ValueError("Raw video has no adequate original camera timeline")
    evidence={"source":receipt(src),"source_facts":spec,
              "recording_not_camera_sensor_raw":True,
              "model_edited":False,"artistic_quality_not_certified":True}
    transcript=[]
    model_proc=None
    model_archive=Path(args.model_runtime).resolve()
    model_archive.mkdir(exist_ok=True)
    try:
        frame_sheet=root/"camera-original-contact-sheet.png"
        temporal=inspect_raw_temporal_source(src,spec["duration"])
        evidence["physical_temporal_observation"]=temporal
        safe_json(out/"raw-temporal-source-evidence.json",temporal)
        original_visual=shot_reel(src,spec,frame_sheet,
            sample_times_seconds=temporal["contact_sheet_sample_times_seconds"])
        evidence["physical_source_observation"]=original_visual
        lock=json.loads(Path(args.model_lock).read_text())
        with (out/"local-model-server.log").open("w") as log:
            model_proc,weights=_await_model(lock,model_archive,log)
            evidence["model_weights"]=weights
            brain=LocalCreativeModel(LocalModelSettings(
                model_id=lock["server"]["alias"],
                base_url="http://127.0.0.1:8080",
                timeout_seconds=300,
                sampling={"temperature":.7,"max_tokens":1800}
            ),SYSTEM)
            brain.settings.sampling["response_format"]={
                "type":"json_schema","json_schema":{
                    "name":"zx7_raw_camera_self_directed_edit",
                    "strict":True,"schema":plan_schema(spec["duration"])}}
            request={"task":"Edit this video.",
                     "source":{
                         "sha256":sha256_file(src),
                         "duration_seconds":spec["duration"],
                         "resolution":[spec["width"],spec["height"]],
                         "has_audio":spec["has_audio"],
                     },
                     "advertised_editor_schema":plan_schema(spec["duration"]),
                     "picture_evidence":[{
                         "job_id":sha256_file(src),"path":str(frame_sheet),
                         "sha256":original_visual["thumbnail_sha256"],
                     }],
                     "sample_times_seconds":original_visual["sample_times_seconds"],
                     "source_motion_observation":{
                         "kind":temporal["kind"],
                         "decoded_one_fps_frame_count":temporal["decoded_one_fps_frame_count"],
                         "mean_adjacent_grayscale_delta_0_to_255":temporal["mean_adjacent_grayscale_delta_0_to_255"],
                         "highest_change_seconds":temporal["highest_change_seconds"],
                         "not_motion_semantics_or_artistic_quality":True,
                         "not_audio_or_continuous_scene_understanding":True},
                     "source_is_actual_unedited_camera_video":True}
            decision=None
            for attempt in range(3):
                started=time.monotonic()
                reply=brain.decide_with_images(
                    request,[("image/png",frame_sheet.read_bytes())])
                event={"input":request,"raw_model_json":reply,
                       "local_model_server_tokens":brain.last_call_usage,
                       "elapsed_seconds":round(time.monotonic()-started,2)}
                transcript.append(event)
                try:
                    length=validate_edit(reply,spec["duration"])
                    decision=reply
                    break
                except (ValueError,TypeError,KeyError) as exc:
                    event["host_rejection"]=str(exc)
                    request["previous_response_failure"]=str(exc)
            if decision is None:
                raise RuntimeError("Real model never authored a valid video edit")
            safe_json(out/"model-authored-raw-video-edit.json",decision)
            evidence["model_edit_plan"]=receipt(
                out/"model-authored-raw-video-edit.json")
            parts=root/"rendered-actual-video-parts";parts.mkdir()
            vault=MediaVault(root/"vault")
            clips=[]
            start_frame=0
            for index,clip in enumerate(decision["cuts"]):
                frames=int(round((clip["source_out"]-clip["source_in"])/
                                 clip["speed"]*RATE))
                if frames<1:raise ValueError("Model selected an invisible source cut")
                output=parts/f"native-source-{index:02d}.mp4"
                filt=("setpts=(PTS-STARTPTS)/"+str(clip["speed"])+
                      ",fps=24,scale=1280:720:force_original_aspect_ratio=decrease,"+
                      "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"+
                      "eq=contrast="+str(clip["contrast"])+
                      ":saturation="+str(clip["saturation"])+
                      ",format=yuv420p,setsar=1")
                args_ff=["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                        "-ss",str(clip["source_in"]),"-t",
                        str(clip["source_out"]-clip["source_in"]),
                        "-i",str(src),"-vf",filt,"-frames:v",str(frames),
                        "-an","-c:v","libx264","-preset","veryfast",
                        "-crf","18","-pix_fmt","yuv420p","-r","24",
                        "-color_primaries","bt709","-color_trc","bt709",
                        "-colorspace","bt709",str(output)]
                run(args_ff,timeout=500)
                stats=json.loads(run(["ffprobe","-v","error",
                    "-count_frames","-select_streams","v:0",
                    "-show_entries","stream=nb_read_frames",
                    "-of","json",str(output)],timeout=45).stdout)
                count=int(stats["streams"][0]["nb_read_frames"])
                if count!=frames:
                    raise RuntimeError("Real native cut did not produce authored frame count")
                att=vault.ingest(output,mime="video/mp4",
                    rights="generated_original",source_type="trusted_renderer",
                    source_id="zx7-camera-real-raw-source-render",
                    evidence=f"Model decision {index}; raw_sha256={sha256_file(src)}; original license CC0, input span {clip['source_in']}..{clip['source_out']}, speed {clip['speed']}",
                    owner_or_generator="ZX7 installed native video engine driven by genuine local model")
                clips.append({"source":"zx7:sha256:"+att["asset_id"],
                   "asset_id":att["asset_id"],"attestation_id":att["attestation_id"],
                   "position_frame":start_frame,"first_frame":0,"end_frame":count,
                   "audio":"intentional_silence"})
                start_frame+=count
            native={"frame_rate":{"numerator":24,"denominator":1},
                    "frame_size":{"width":WIDTH,"height":HEIGHT},
                    "tracks":[{"clips":clips}],"audio_tracks":[]}
            coverage=assess_raw_edit_coverage(
                source_duration_seconds=spec["duration"],
                source_sha256=evidence["source"]["sha256"],
                source_has_audio=spec["has_audio"],
                sample_times_seconds=original_visual["sample_times_seconds"],
                edit=decision,native_plan=native)
            evidence["source_selection_diagnostics"]=coverage
            safe_json(out/"source-selection-diagnostics.json",coverage)
            native_source=root/"model-authored-native-edit.json"
            safe_json(native_source,native)
            native_project=root/"self-directed-camera-edit.mlt"
            evidence["native_project"]=export_owned_mlt(
                native_source,root,root/"vault",native_project)
            original_cut=root/"native-editor-real-raw-cut.mp4"
            evidence["native_movie"]=render_owned_mlt(
                native_project,root,original_cut)
            graphics_movie=root/"self-directed-graphics.mp4"
            evidence["graphic_operation"]=overlay_graphics(
                original_cut,decision["graphics"],graphics_movie,root)
            final=out/"ZX7-GENUINE-RAW-VIDEO-SELF-DIRECTED-EDIT.mp4"
            if decision["music"]["enabled"]:
                wav=root/"original-model-directed-music.wav"
                _render_music(decision["music"],wav,
                              duration_seconds=math.ceil(start_frame/RATE))
                run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                     "-i",str(graphics_movie),"-i",str(wav),
                     "-map","0:v:0","-map","1:a:0","-c:v","copy",
                     "-c:a","aac","-b:a","192k","-af","afade=t=out:st="+
                     str(max(0,start_frame/RATE-1))+
                     ":d=1","-t",str(start_frame/RATE),"-movflags",
                     "+faststart",str(final)],timeout=250)
            else:
                os.link(graphics_movie,final)
            decoded=full_decode_inspection(final,expected={
                "width":WIDTH,"height":HEIGHT,
                "duration_seconds":start_frame/RATE,
                "require_audio":decision["music"]["enabled"]})
            if not decoded["technical_delivery_verified"]:
                raise RuntimeError("Real raw video edited export failed physical A/V decode")
            if sha256_file(final)==sha256_file(src):
                raise RuntimeError("No changed output bytes from actual camera source")
            evidence["model_edited"]=True
            evidence["native_clock_frames"]=start_frame
            evidence["final_movie"]=receipt(final)
            evidence["full_decode"]=decoded
            evidence["model_decisions_not_authored_by_host"]=True
            evidence["semantic_or_professional_quality_not_certified"]=True
    except BaseException as exc:
        evidence["failure_type"]=type(exc).__name__
        evidence["failure_text"]=str(exc)[:1200]
        raise
    finally:
        safe_json(out/"edit-evidence.json",evidence)
        safe_json(out/"local-model-transcript.json",transcript)
        if model_proc:
            model_proc.terminate()
            try:model_proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                model_proc.kill();model_proc.wait()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    parser.add_argument("--rights",required=True)
    parser.add_argument("--model-lock",required=True)
    parser.add_argument("--model-runtime",required=True)
    parser.add_argument("--output",required=True)
    produce(parser.parse_args())

if __name__=="__main__":main()
