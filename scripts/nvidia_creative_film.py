"""Real NVIDIA-directed original audiovisual film, no prewritten shots or music.

The remote model authors every visual asset, caption, layer animation, scene
duration, synthesizer spectrum and mix as one original Film IR. Existing ZX7
renderers execute and independently decode/verify the delivered movie.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

from studio_next.nvidia_model import NvidiaCreativeModel, NvidiaModelSettings
from studio_next.motion_bridge import compile_motion_project
from studio_next.silent_audio import make_silent_timing
from motion_studio.render import render


SYSTEM = """You are a creative director, animated typography artist and original
sound composer commissioned to author an ORIGINAL ZX7 Creative Studio ident.
This is cinema about independent creative work, not a fake product UI.
Invent your OWN visual idea, typography, transformations, sound spectrum,
rhythms and sequence with purpose and craft. There are NO prewritten scenes,
assets, music, colours, text, camera paths or style templates.
Avoid cliched glowing AI brains, circuit boards, stock footage or slideshow
cards. Originality and emotional meaning matter more than decoration.

Return exactly ONE JSON object: a fully executable ZX7 Film IR. Only the
following technical ABI limits your execution, NOT its creative content:
Top-level EXACT keys: project, assets, shots, tool_graph.
project: {title:string,creative_intent:string,width:integer,height:integer,
 background:'#RRGGBB',voice:'no_voice',score:[],
 background_noise:{gain:number 0..5,seed:nonnegative integer},
 audio_mix:{fade_in_seconds:number,fade_out_seconds:number,
 peak_ceiling:number in (0,1]}}.
Choose 640x360 landscape OR 360x640 portrait. This isolated CPU test has no
verified TTS, so express your story with your own moving typography and sound;
no narration. Do not imitate a voice using silent WAV.
assets: 1..10 independent, original inline vector drawings. Each item:
 {id:'unique_safe_id',status:'verified',rights:'generated_original',
 location:'inline://unique_safe_id',
 artwork:{size:[positive_width,positive_height],items:[drawable,...]}}.
Drawables may be:
 {type:'rect',box:[left,top,right,bottom],fill:'#RRGGBB',radius?:number},
 {type:'ellipse',box:[left,top,right,bottom],fill:'#RRGGBB'},
 {type:'line',points:[[x,y],[x,y],...],fill:'#RRGGBB',width?:number},
 {type:'polygon',points:[[x,y],[x,y],[x,y],...],fill:'#RRGGBB'},
 {type:'text',text:'your original title/copy',at:[x,y],size:number,
 fill:'#RRGGBB',font:'sans'|'bold'|'serif'|'mono',
 align?:'left'|'center'|'right'}.
Choose YOUR geometry, colours, type hierarchy and words. Coordinates are
local to the asset size; canvas centres are relative to project width/height.
shots: 2..4 distinct model-authored scenes, total 5..16 seconds. Each:
 {id:'unique_safe_id',purpose:'dramatic scene purpose',duration_seconds:number 1..6,
 narration:'',asset_refs:[every asset id actually used here],fact_refs:[],
 layers:[{asset:'existing asset id',x:number,y:number,animate?:{
 opacity?:[[time,value],...],x?:[[time,value],...],
 y?:[[time,value],...],scale?:[[time,value],...],
 angle?:[[time,value],...],reveal?:[[time,value],...]
 }},...],
 IMPORTANT: every layer scale, scale_x, scale_y and EVERY scale animation
 keyframe value MUST be >=0.01 and <=30. ZERO (0) scale is INVALID and
 causes a physical render failure. For an appearance or disappearance use
 OPACITY 0..1 and a positive scale such as 0.05, NOT zero scale.
 All time keyframes are strictly increasing, >=0 and <=shot duration.
 Every opacity, reveal value MUST be 0..1; font/text sizes 2..256.
 cues:[{type:'synth',at:number,seconds:number,gain:number,noise_gain:number,
 seed:integer,partials:[{start_hz:number,end_hz:number,amplitude:number,
 phase_radians:number},...],envelope:[[0,amplitude],...,[seconds,amplitude]]},...] }.
Every referenced asset, animation time, sonic event and envelope must be real,
finite, consistent, and inside its scene duration. Frequency <24000Hz.
Make at least one caption visibly move and at least one original synth
cue physically audible. Specify original spectral harmonics and envelope;
DO NOT use preset tap/paper/ink noises or prerecorded music. The engineer
doesn't pick audio notes. You own all text, motion, music and edit rhythm.
tool_graph: exactly [{id:'composite',tool_id:'motion_studio.composite',
 inputs:{},purpose:'your reason to compose original audiovisual art',
 depends_on:[]}].
Only model-authored inline art. No external media, fixed soundtrack,
hardcoded sentence, arbitrary code, scripts, shell instructions, URLs or
claimed output files. Return strict JSON, no commentary or markdown.
"""

OWNER = {
    "request": "Create one exceptional original audiovisual ident about an idea gaining agency and becoming tangible creative work, for the experimental ZX7 Creative Studio project.",
    "audience": "independent makers and filmmakers, global",
    "verified_fact": "ZX7 is an ongoing experimental project, not a completed publicly released product.",
    "technical_tools": "model-authored inline vector drawing, animation, synthesized original audio, FFmpeg",
    "no_real_product_claims": True,
}


class FilmProofError(ValueError):
    pass


def _sha(path):
    with Path(path).open("rb") as reader:
        return hashlib.file_digest(reader, "sha256").hexdigest()


def validate_artistic_control(ir):
    """CPU/privacy ceilings only. Never supply or substitute creative values."""
    if type(ir) is not dict or set(ir) != {"project", "assets", "shots", "tool_graph"}:
        raise FilmProofError("The director must return a complete exact Film IR")
    meta, assets, shots = ir["project"], ir["assets"], ir["shots"]
    if type(meta) is not dict or (meta.get("width"), meta.get("height")) not in (
            (640, 360), (360, 640)):
        raise FilmProofError("Physical canvas exceeds approved proof dimensions")
    if meta.get("voice") != "no_voice" or meta.get("score") != []:
        raise FilmProofError("No fake voice or preset-timbre score; author actual sound cues")
    noise=meta.get("background_noise")
    if (type(noise) is not dict or set(noise) != {"gain", "seed"} or
            type(noise["seed"]) is not int or noise["seed"] < 0 or
            type(noise["gain"]) not in (int,float) or
            not 0 <= noise["gain"] <= 5):
        raise FilmProofError("The model must select the actual grain (or none)")
    mix=meta.get("audio_mix")
    if type(mix) is not dict or not {"fade_in_seconds","fade_out_seconds","peak_ceiling"}.issubset(mix):
        raise FilmProofError("The model must design the original audio mix")
    if type(assets) is not list or not 1 <= len(assets) <= 10:
        raise FilmProofError("Original art inventory exceeds the evaluation bound")
    if type(shots) is not list or not 2 <= len(shots) <= 4:
        raise FilmProofError("The original film needs 2-4 real model-edited shots")
    text_assets=set()
    count=0
    for item in assets:
        if type(item) is not dict or type(item.get("artwork")) is not dict:
            raise FilmProofError("Original vector source missing")
        shapes=item["artwork"].get("items")
        if type(shapes) is not list or not shapes or len(shapes)>24:
            raise FilmProofError("Original art exceeds one drawing's CPU bound")
        count+=len(shapes)
        if any(type(x) is dict and x.get("type")=="text" for x in shapes):
            text_assets.add(item.get("id"))
    if count>72:
        raise FilmProofError("Total model-authored source art exceeds CPU bound")
    text_animated=False
    audio_events=0
    total=0.
    for shot in shots:
        if type(shot) is not dict:raise FilmProofError("No malformed story shot")
        duration=shot.get("duration_seconds")
        if type(duration) not in (int,float) or not math.isfinite(duration) or not 1<=duration<=6:
            raise FilmProofError("Shot rhythm outside bounded technical session")
        total+=duration
        if shot.get("narration")!="":
            raise FilmProofError("No installed narrator: do not fake voiced dialogue")
        for layer in shot.get("layers",[]):
            if (type(layer) is dict and layer.get("asset") in text_assets and
                    type(layer.get("animate")) is dict and layer["animate"]):
                text_animated=True
        for cue in shot.get("cues",[]):
            if type(cue) is not dict or cue.get("type")!="synth":
                raise FilmProofError("Any sound must be genuinely model-designed synth")
            partials=cue.get("partials")
            if (type(partials) is not list or not partials or not any(
                    type(p) is dict and type(p.get("amplitude")) in (int,float) and
                    p["amplitude"]>0 for p in partials)):
                raise FilmProofError("Authored sound must define audible spectral partials")
            audio_events+=1
    if not 5<=total<=16 or not text_animated or not audio_events:
        raise FilmProofError("Proof needs original timing, moving copy and composed sound")
    return compile_motion_project(ir, fact_ids=frozenset())


def author_film(model, out):
    context={"owner": OWNER, "instruction": "Independently choose and author one complete original executable Film IR."}
    attempts=[]
    previous=None
    for turn in range(3):
        started=time.monotonic()
        try:
            proposal=model.decide(context)
            previous=proposal
            project=validate_artistic_control(proposal)
        except (ValueError,TypeError,KeyError) as error:
            # Technical validator feedback never selects a visual or sound for AI.
            kind=type(error).__name__
            message=(str(error)[:650] if kind in ("FilmProofError","UnsupportedMotionPlan")
                     else "Invalid Film IR contract: "+kind)
            attempts.append({"round":turn,"accepted":False,"validator":kind,
                             "problem":message})
            context={"owner":OWNER,"technical_contract":SYSTEM,
                     "previous_draft":previous,
                     "validator_feedback":message,
                     "instruction":"Repair the EXACT listed invalid numeric parameter(s) in your own original IR. Do not repeat an invalid scale=0. Scale and scale keyframes must be between 0.01 and 30. Preserve your original artistic intent, decisions and sound. Return the complete corrected Film IR."}
            continue
        attempts.append({"round":turn,"accepted":True,
                         "elapsed_seconds":round(time.monotonic()-started,3),
                         "provider_reported_tokens":model.last_call_usage})
        (out/"model-authored-film-ir.json").write_text(
            json.dumps(proposal,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (out/"compiled-render-project.json").write_text(
            json.dumps(project,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (out/"decision-attempts.json").write_text(
            json.dumps(attempts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        return proposal,project,attempts
    (out/"decision-attempts.json").write_text(
        json.dumps(attempts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    raise FilmProofError("The actual NVIDIA creative brain never produced executable original Film IR")


def _frame_sha(movie, t):
    raw=subprocess.check_output(
        ["ffmpeg","-v","error","-ss",f"{t:.3f}","-i",str(movie),
         "-frames:v","1","-f","image2pipe","-vcodec","png","pipe:1"],timeout=75)
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise FilmProofError("No real independently decoded frame")
    return hashlib.sha256(raw).hexdigest()


def physical_proof(movie, duration):
    info=json.loads(subprocess.check_output(
        ["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(movie)],
        timeout=60))
    v=[x for x in info["streams"] if x.get("codec_type")=="video"]
    a=[x for x in info["streams"] if x.get("codec_type")=="audio"]
    if len(v)!=1 or len(a)!=1:
        raise FilmProofError("Physical encoded video and audio both required")
    seconds=float(info["format"]["duration"])
    if abs(seconds-duration)>.2:
        raise FilmProofError("Physical rhythm changed without the model's decision")
    subprocess.run(["ffmpeg","-v","error","-i",str(movie),"-f","null","-"],
                   check=True,timeout=120)
    before=_frame_sha(movie,duration*.2)
    after=_frame_sha(movie,duration*.75)
    if before==after:
        raise FilmProofError("The real film had no independent sampled motion/change")
    raw=subprocess.check_output([
        "ffmpeg","-v","error","-i",str(movie),"-vn",
        "-ac","1","-ar","16000","-f","f32le","pipe:1"],timeout=75)
    import numpy as np
    samples=np.frombuffer(raw,dtype="<f4")
    if len(samples)<8000 or not np.isfinite(samples).all():
        raise FilmProofError("Original soundtrack failed physical PCM decode")
    rms=float(np.sqrt(np.mean(samples.astype("float64")**2)))
    if rms<.00001:
        raise FilmProofError("Synth score not actually audible in the delivered video")
    return {"movie_sha256":_sha(movie),"bytes":movie.stat().st_size,
            "width":v[0]["width"],"height":v[0]["height"],
            "actual_seconds":seconds,"model_selected_seconds":duration,
            "video_codec":v[0]["codec_name"],"audio_codec":a[0]["codec_name"],
            "full_decode_passed":True,
            "first_real_frame_sha256":before,"second_real_frame_sha256":after,
            "decoded_soundtrack_rms":rms,"artistic_quality_independently_approved":False}


def run(out):
    out=Path(out).resolve()
    if out.exists(): raise FilmProofError("Refuse to overwrite a prior trial")
    out.mkdir(parents=True,mode=0o700)
    model=NvidiaCreativeModel(NvidiaModelSettings(
        max_tokens=4096,timeout_seconds=90,
        sampling={"temperature":0.6,"top_p":0.95,
                  "chat_template_kwargs":{"enable_thinking":False}}),
        system_prompt=SYSTEM)
    model.verify_host_credentials()
    authored,compiled,attempts=author_film(model,out)
    # No NVIDIA credential reaches FFmpeg, fonts, audio encoders, or subprocesses.
    os.environ.pop("NVIDIA_API_KEY",None)
    render_dir=out/"render"
    make_silent_timing(out/"compiled-render-project.json",render_dir)
    rendered=render(out/"compiled-render-project.json",render_dir,
                    width=authored["project"]["width"],fps=24)
    final=out/"zx7-model-directed-original-film.mp4"
    shutil.copy2(rendered,final)
    total=sum(s["duration_seconds"] for s in authored["shots"])
    verified=physical_proof(final,total)
    receipt={
        "status":"original_model_authored_audiovisual_film_physically_verified",
        "provider_model":"nvidia/nemotron-3.5-super-vl-120b-a12b",
        "model_ir_sha256":_sha(out/"model-authored-film-ir.json"),
        "model_chose":{"story_text_shapes_colours_typography":True,
                       "all_shot_durations_and_animations":True,
                       "synth_spectral_partials_envelopes_mixes":True,
                       "canvas_orientation":True},
        "original_media_source":"Model-authored inline vector drawing only; no external footage",
        "fixed_preselected_song_or_sound":False,
        "voice_capability_available":False,
        "native_editor_tool_control_proven_by_this_renderer":False,
        "renderer":"Existing ZX7 motion_studio compositor + FFmpeg; model supplied Film IR",
        "provider_calls":attempts,
        "physical_evidence":verified,
    }
    (out/"model-authorship-and-evidence.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False))
    return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    run(args.out)


if __name__=="__main__":
    main()
