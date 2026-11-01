"""Real local Qwen -> creative edit decision -> original public-domain art -> ZX7 native MLT film.

No scripted scene choice. A real locally loaded pinned neural model chooses the
theme, museum search terms, artwork sequence, creative text, camera, pacing and
music notes. A generic renderer compiles *that* model-authored edit; it does
not invent artistic decisions. A failure produces evidence, not a fake demo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import wave

# Script invocation must resolve the checked-out ZX7 repository itself, not a
# globally installed unrelated package or an absent scripts namespace.
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from studio_next.providers import LocalCreativeModel, LocalModelSettings
from studio_next.media_vault import MediaVault, sha256_file
from studio_next.body_mlt_editor import export_owned_mlt
from studio_next.body_mlt_render import render_owned_mlt
from studio_next.production_qc import full_decode_inspection

from scripts.run_native_model_trial import download, read_live_linux_model_peak_rss

SIZE = (1280, 720)
FPS = 24
SECONDS = 60
FRAMES = FPS * SECONDS
BASE = Path(__file__).resolve().parents[1]
SYSTEM = """You are the independent creative director/editor of a one-minute
original visual poem. You have public-domain museum artwork and your own
original procedural soundtrack tools. You—not the script—must choose the
creative story, search themes, artwork order, titles, timing, camera direction
and soundtrack harmonic parameters. Use real provided sources. No made-up
facts, false copyrighted media claims, or famous music/films imitation.
Respond only with JSON. Aim for elegant pacing and meaningful emotional
story progression, not a technical diagnostic or generic title cards.
The BODY compositor does only physical translations of your decisions.
"""

def receipt(path):
    p = Path(path)
    return {"path": str(p), "sha256": sha256_file(p), "bytes": p.stat().st_size}


def _api_json(url):
    uri = urllib.parse.urlsplit(url)
    if (uri.scheme != "https" or uri.hostname != "commons.wikimedia.org"
            or uri.username or uri.password):
        raise ValueError("Only the official Wikimedia Commons CC0 metadata API may be queried")
    req = urllib.request.Request(url, headers={
        "User-Agent": "ZX7-LocalCreativeFilm/0.1 (github.com/ZX7-Labs/Zx7-creative-studio-)",
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read(3_000_001)
    if len(data) > 3_000_000:
        raise ValueError("Museum metadata exceeds bounded response budget")
    return json.loads(data)

def _museum_images(queries, folder):
    """Decode genuinely CC0 Wikimedia media in the film's owned workspace.

    Millions of real CC0 originals are indexed in Category:CC-Zero. Verified
    2026-11-01 official thumbnail URLs return physical JPEG bytes on the same
    type of public GitHub runner that is used to run the actual local model.
    Unlike museum image CDNs, these downloads passed live reachability tests.
    """
    import re
    from html.parser import HTMLParser
    if (not isinstance(queries,list) or not 2<=len(queries)<=5 or
            any(not isinstance(q,str) or not 2<=len(q)<=160 for q in queries)):
        raise ValueError("Model-authored creative search themes invalid")
    phrases=[]
    for phrase in queries:
        tokens=re.findall(r"[A-Za-z]{4,}",phrase)
        phrases.extend(tokens[:4])
    phrases.append("") # A broad CC0 catalog for concepts with no literal title matches
    records={}
    for term in list(dict.fromkeys(phrases))[:14]:
        params={
            "action":"query","format":"json",
            "generator":"categorymembers","gcmtitle":"Category:CC-Zero",
            "gcmtype":"file","gcmlimit":50,
            "prop":"imageinfo","iiprop":"url|mime|extmetadata",
            "iiurlwidth":1280,
            "iiextmetadatafilter":"LicenseShortName|LicenseUrl"}
        if term:
            params["gcmstartsortkeyprefix"]=term
        try:
            payload=_api_json("https://commons.wikimedia.org/w/api.php?" +
                              urllib.parse.urlencode(params))
        except (OSError,ValueError,urllib.error.URLError) as exc:
            print("Official Commons CC0 search unavailable",term,
                  type(exc).__name__,flush=True)
            continue
        pages=(payload.get("query") or {}).get("pages",{})
        if not isinstance(pages,dict):
            raise ValueError("Commons query returned invalid media index")
        admitted=0
        for rec in pages.values():
            if not isinstance(rec,dict):
                continue
            info=(rec.get("imageinfo") or [{}])[0]
            if not isinstance(info,dict) or info.get("mime") not in (
                    "image/jpeg","image/png","image/webp"):
                continue
            meta=info.get("extmetadata")
            if not isinstance(meta,dict):
                continue
            lic=meta.get("LicenseShortName")
            licname=lic.get("value") if isinstance(lic,dict) else None
            if licname not in ("CC0","CC0 1.0"):
                continue
            licurl=meta.get("LicenseUrl")
            urlstr=licurl.get("value") if isinstance(licurl,dict) else ""
            if (not isinstance(urlstr,str) or
                    not urlstr.startswith("https://creativecommons.org/publicdomain/zero/1.0/")):
                continue
            image=info.get("thumburl") or info.get("url")
            page=info.get("descriptionurl")
            if not isinstance(image,str) or not isinstance(page,str):
                continue
            imageuri=urllib.parse.urlsplit(image)
            pageuri=urllib.parse.urlsplit(page)
            if (imageuri.scheme!="https" or imageuri.hostname not in (
                    "thumb.wikimedia.org","upload.wikimedia.org")
                    or pageuri.scheme!="https" or pageuri.hostname!="commons.wikimedia.org"):
                continue
            ident=rec.get("pageid")
            if type(ident) is not int or ident<=0:
                continue
            records[ident]={
                "id":ident,"title":str(rec.get("title","")).removeprefix("File:")[:150],
                "artist":"","image_url":image,"page":page,
                "public_domain_flag":True,"declared_license":"CC0",
                "license_url":urlstr,
                "provider":"Wikimedia_Commons_CC_Zero",
                "original_mime":info["mime"]}
            admitted+=1
        print("Live Commons category CC0 search",repr(term),
              "CC0 candidate images",admitted,"overall",len(records),flush=True)
        if len(records)>=100:
            break
    if len(records)<12:
        raise ValueError("Official Commons CC0 index supplied too few genuine images")
    source=[]
    for record in list(records.values())[:90]:
        url=record["image_url"]
        try:
            req=urllib.request.Request(url,headers={
                "User-Agent":"ZX7-LocalCreativeFilm/0.1 (CC0 Wikimedia Commons)"})
            with urllib.request.urlopen(req,timeout=25) as response:
                target=urllib.parse.urlsplit(response.url)
                if target.scheme!="https" or target.hostname not in (
                        "thumb.wikimedia.org","upload.wikimedia.org"):
                    raise ValueError("CC0 media redirected outside official Wikimedia media hosts")
                b=response.read(7_000_001)
            if not 5_000<len(b)<=7_000_000:
                raise ValueError("CC0 image download is empty or exceeds byte budget")
            # Normalize image container, pixels must come from the actual
            # independently downloaded, decoded Commons source.
            with Image.open(__import__("io").BytesIO(b)) as opened:
                opened.load()
                if opened.width<500 or opened.height<300:
                    continue
                decoded=opened.convert("RGB")
                if decoded.width>2400 or decoded.height>2400:
                    decoded.thumbnail((2400,2400))
                p=folder/("artwork-%02d.jpg"%len(source))
                decoded.save(p,format="JPEG",quality=93,subsampling=0)
            source.append({**record,"local":str(p),"sha256":sha256_file(p),
                           "bytes":p.stat().st_size,
                           "original_source_sha256":hashlib.sha256(b).hexdigest(),
                           "declared_rights":"CC0_Wikimedia_Commons_file_metadata"})
            print("Decoded real CC0 Commons image",record["id"],
                  source[-1]["sha256"][:12],flush=True)
        except (OSError,ValueError,urllib.error.URLError) as exc:
            print("Commons CC0 download unavailable",record["id"],
                  type(exc).__name__,getattr(exc,"code",None),flush=True)
            continue
        if len(source)>=9:
            break
    if len(source)<6:
        raise ValueError("No sufficient real downloaded and decoded CC0 source images")
    return source

def _font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path,size)
    raise RuntimeError("Free font not installed on native rendering host")

def _contact_sheet(assets, path):
    w,h=4*320,3*220
    canvas=Image.new("RGB",(w,h),(15,19,25));draw=ImageDraw.Draw(canvas)
    for n,asset in enumerate(assets):
        x=(n%4)*320;y=(n//4)*220
        with Image.open(asset["local"]) as src:
            src=src.convert("RGB")
            src.thumbnail((310,170))
            canvas.paste(src,(x+(320-src.width)//2,y))
        draw.rectangle((x,y+175,x+319,y+220),fill=(15,19,25))
        label=f'{n}: {asset["title"]}'[:37]
        draw.text((x+10,y+183),label,font=_font(15),fill=(242,238,229))
    canvas.save(path)
    return receipt(path)

def _call(model, context, evidence, *, with_image=None):
    # Every inference transcript is preserved separately. No predetermined
    # creative model reply is ever substituted.
    started=time.monotonic()
    try:
        if with_image is not None:
            decision=model.decide_with_images(context,[("image/png",with_image.read_bytes())])
        else:
            decision=model.decide(context)
        evidence.append({"context":context,
                         "model_response":decision,
                         "elapsed_seconds":round(time.monotonic()-started,3),
                         "server_reported_token_usage":model.last_call_usage,
                         "image":receipt(with_image) if with_image else None})
        return decision
    except Exception as exc:
        evidence.append({"context":context,"error_type":type(exc).__name__,
                         "elapsed_seconds":round(time.monotonic()-started,3)})
        raise

def _validate_decision(plan,assets):
    if not isinstance(plan,dict):
        raise ValueError("Creative model returned no structured original film plan")
    title=plan.get("title")
    if not isinstance(title,str) or not 3 <= len(title) <= 70:
        raise ValueError("Model must author an original short film title")
    story=plan.get("story")
    if not isinstance(story,str) or not 20 <= len(story) <= 800:
        raise ValueError("Model must author an original narrative intention")
    beats=plan.get("beats")
    if not isinstance(beats,list) or not 6 <= len(beats) <= 12:
        raise ValueError("Model must author 6–12 original editorial beats")
    for beat in beats:
        if not isinstance(beat,dict):
            raise ValueError("Creative beat must be a real object")
        if type(beat.get("artwork")) is not int or not 0<=beat["artwork"]<len(assets):
            raise ValueError("Creative beat has a nonexistent public-domain artwork")
        caption=beat.get("caption")
        if not isinstance(caption,str) or not 3<=len(caption)<=100:
            raise ValueError("Each original visual beat needs an authored short thought")
        if beat.get("camera") not in ("push","pull","drift_left","drift_right","still"):
            raise ValueError("Model requested a camera control unavailable in the physical editor")
        if type(beat.get("weight")) not in (int,float) or not 1<=beat["weight"]<=20:
            raise ValueError("Model must choose finite positive relative pacing weight")
    music=plan.get("music")
    if not isinstance(music,dict):
        raise ValueError("Model must author music decisions, not a silent film")
    if (type(music.get("bpm")) is not int or not 55<=music["bpm"]<=155 or
            type(music.get("root_midi")) is not int or not 40<=music["root_midi"]<=72 or
            music.get("mode") not in ("minor","major")):
        raise ValueError("Music tempo, root or mode outside real original synthesizer controls")
    prog=music.get("progression")
    if not isinstance(prog,list) or not 2<=len(prog)<=8 or any(
            type(p) is not int or not 0<=p<=6 for p in prog):
        raise ValueError("Original music progression missing or invalid")
    return plan

def _weights_to_frames(beats):
    total=sum(x["weight"] for x in beats)
    if total<=0:raise ValueError("Missing creative pacing")
    raw=[FRAMES*x["weight"]/total for x in beats]
    ints=[int(math.floor(x)) for x in raw]
    # Preserve model-chosen proportions, and exact 60 seconds of native CFR.
    for i in sorted(range(len(ints)),key=lambda k:raw[k]-ints[k],reverse=True)[:FRAMES-sum(ints)]:
        ints[i]+=1
    if sum(ints)!=FRAMES or min(ints)<FPS*2:
        raise ValueError("Model's chosen pacing cannot physically fit the 60s film")
    return ints

def _title_overlay(title, caption, number, count, dest):
    W,H=SIZE
    im=Image.new("RGBA",(W,H))
    px=im.load()
    # Bottom gradient for readable real credits over varied artwork.
    for y in range(370,H):
        a=int(205*((y-370)/(H-370))**1.4)
        ImageDraw.Draw(im).line((0,y,W,y),fill=(8,11,19,a),width=1)
    draw=ImageDraw.Draw(im)
    draw.text((76,478),title.upper(),font=_font(19),fill=(215,206,187,225))
    cap=caption[:100]
    draw.text((76,526),cap,font=_font(35 if len(cap)>42 else 42),fill=(255,252,247,245))
    draw.rectangle((76,644,76+int(1128*(number+1)/count),647),
                   fill=(214,167,106,225))
    draw.text((76,667),f"{number+1:02d} / {count:02d}",
              font=_font(15),fill=(223,224,225,218))
    im.save(dest)

def _render_segment(image, overlay, camera, nframes, dest):
    import shlex
    # Literal fixed physical filter grammar: the model can only select
    # registered camera operations, never execute arbitrary FFmpeg expressions.
    z = ("min(1.16,1.03+0.12*on/%d)"%nframes if camera!="pull" else
         "max(1.03,1.16-0.12*on/%d)"%nframes)
    x = ("(iw-iw/zoom)*on/%d"%nframes if camera=="drift_left" else
         "(iw-iw/zoom)*(1-on/%d)"%nframes if camera=="drift_right" else
         "(iw-iw/zoom)/2")
    y = "(ih-ih/zoom)/2"
    filt = (
        "[0:v]scale=1536:864:force_original_aspect_ratio=increase,"
        "crop=1536:864,zoompan=z='%s':x='%s':y='%s':d=1:s=1280x720:fps=24[bg];"
        "[bg][1:v]overlay=0:0:format=auto,format=yuv420p,setsar=1[out]"
        % (("1.03" if camera=="still" else z),x,y))
    argv=["ffmpeg","-hide_banner","-loglevel","error","-y",
          "-loop","1","-framerate",str(FPS),"-i",str(image),
          "-loop","1","-framerate",str(FPS),"-i",str(overlay),
          "-filter_complex",filt,"-map","[out]","-frames:v",str(nframes),
          "-an","-c:v","libx264","-preset","fast","-crf","20",
          "-pix_fmt","yuv420p","-r",str(FPS),
          "-color_primaries","bt709","-color_trc","bt709",
          "-colorspace","bt709",str(dest)]
    subprocess.run(argv,check=True,timeout=240)
    if not dest.is_file() or dest.stat().st_size < 8000:
        raise RuntimeError("Native visual segment not rendered")

def _render_music(music, output):
    root, bpm=music["root_midi"],music["bpm"]
    mode=music["mode"]
    degrees=[0,2,3,5,7,8,10] if mode=="minor" else [0,2,4,5,7,9,11]
    progression=music["progression"]
    sample_rate=48000
    n=SECONDS*sample_rate
    t=np.arange(n,dtype=np.float64)/sample_rate
    beat=60/bpm
    bar=beat*4
    chord_idx=(t/bar).astype(np.int32)%len(progression)
    audio=np.zeros(n,dtype=np.float64)
    def pitch(midi):return 440*2**((midi-69)/12)
    for index, degree in enumerate(progression):
        active=(chord_idx==index).astype(np.float64)
        barphase=(t%bar)/bar
        envelope=(0.38+0.62*np.minimum(1,barphase*6))
        key=root+degrees[degree]
        tones=(key,key+7,key+12)
        pad=sum(np.sin(2*np.pi*pitch(note)*t + (j*.37))*
                (0.31 if j==0 else .20) for j,note in enumerate(tones))
        audio+=pad*active*envelope
    pulse=(t%beat)/beat
    bassfreq=pitch(root-12)
    audio+=.14*np.sin(2*np.pi*bassfreq*t)*np.exp(-pulse*7)
    audio+=.05*np.sin(2*np.pi*(660+1200*pulse)*t)*np.exp(-pulse*24)
    fade=np.minimum(1,np.minimum(t/2.2,(SECONDS-t)/3.2)).clip(0,1)
    audio*=fade*.42
    mx=max(.01,np.max(np.abs(audio)))
    audio=np.clip(audio/max(1,mx/0.83),-.95,.95)
    left=audio
    right=.97*audio+.03*np.roll(audio,97)
    stereo=np.stack((left,right),axis=1)
    frames=(stereo*32767).astype("<i2")
    with wave.open(str(output),"wb") as w:
        w.setnchannels(2);w.setsampwidth(2)
        w.setframerate(sample_rate);w.writeframes(frames.tobytes())

def _await_model(lock, runtime, logfile):
    from scripts.run_native_model_trial import sha
    archive=download(lock["runtime"]["archive"],runtime)
    files={entry["kind"]:download(entry,runtime) for entry in lock["model"]["files"]}
    with tarfile.open(archive) as src:
        src.extractall(runtime,filter="data")
    binary=runtime/lock["runtime"]["binary_relative_path"]
    argv=[str(binary)]+[
        str(files["model"]) if arg=="MODEL_PATH" else
        str(files["vision_projector"]) if arg=="MMPROJ_PATH" else arg
        for arg in lock["server"]["args"]]
    # The pinned model may need longer creative JSON than technical probes.
    # This is an inference budget, not a programmed scene.
    if "--n-predict" in argv:
        argv[argv.index("--n-predict")+1]="1536"
    with socket.socket() as sock:sock.bind(("127.0.0.1",8080))
    proc=subprocess.Popen(argv,stdout=logfile,stderr=subprocess.STDOUT)
    started=time.monotonic()
    try:
        while time.monotonic()-started<150:
            if proc.poll() is not None:
                raise RuntimeError("Pinned local AI runtime exited before inference")
            try:
                with urllib.request.urlopen("http://127.0.0.1:8080/health",timeout=2) as response:
                    if response.status==200:
                        return proc,{kind:receipt(path) for kind,path in files.items()}
            except OSError:
                pass
            time.sleep(.4)
        raise TimeoutError("Pinned local AI could not start on available host CPU")
    except BaseException:
        proc.terminate()
        proc.wait(timeout=15)
        raise

def produce(args):
    dest=Path(args.output).resolve()
    dest.mkdir(parents=True,exist_ok=False)
    workspace=dest/"workspace";workspace.mkdir()
    art=workspace/"art";art.mkdir()
    effects=workspace/"effects";effects.mkdir()
    source_dir=workspace/"source";source_dir.mkdir()
    runtime=Path(args.runtime).resolve();runtime.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(Path(args.model_lock).read_text())
    if manifest["model"]["license"]!="Apache-2.0":
        raise ValueError("Local film Brain must use source-pinned free/open model")
    evidence={"status":"unverified","model_id":manifest["model"]["id"],
              "model_revision":manifest["model"]["revision"],
              "genuine_model_run":False,"native_mlt_rendered":False,
              "film_seconds":None,"rights_independently_cleared":False,
              "artistic_quality_approved":False}
    model_process=None
    transcript=[]
    try:
        with (dest/"model-server.log").open("w") as log:
            model_process,weights=_await_model(manifest,runtime,log)
            evidence["weights"]=weights
            brain=LocalCreativeModel(LocalModelSettings(
                model_id=manifest["server"]["alias"],
                base_url="http://127.0.0.1:8080",
                timeout_seconds=300,
                sampling={"temperature":.65,"max_tokens":1536}),SYSTEM)
            topic=None
            for attempt in range(3):
                decision=_call(brain,{"phase":"creative_research",
                    "task":"Choose original title, concept, and 3 artistic search themes "
                           "for a 60-second film made from public-domain museum visual artwork. "
                           "Return JSON: {\"working_title\":string,\"search_queries\":[string,string,string]}. "
                           "Choose freely; no preset genre or story."},transcript)
                try:
                    queries=decision["search_queries"]
                    if not isinstance(queries,list) or not 2<=len(queries)<=5 or any(
                            not isinstance(q,str) or not 2<=len(q)<=160 for q in queries):
                        raise ValueError("Invalid creative research queries")
                    topic=decision
                    break
                except (ValueError,KeyError,TypeError):
                    continue
            if topic is None:
                raise RuntimeError("Local creative Brain did not author valid asset research")
            assets=_museum_images(topic["search_queries"],art)
            (dest/"source-asset-evidence.json").write_text(
                json.dumps(assets,indent=2,ensure_ascii=False))
            sheet=effects/"contact-sheet.png"
            sheet_receipt=_contact_sheet(assets,sheet)
            evidence["contact_sheet"]=sheet_receipt
            brief={"phase":"creative_film_edit",
                  "creative_intent": topic,
                  "task":"Independently direct and edit a complete 60-second original visual poem "
                         "from these numbered public-domain artworks. Build an emotionally coherent "
                         "cinematic arc and an original musical structure. No existing movie/music copies. "
                         "Render exactly one minute by choosing relative scene weights. "
                         "Choose 6–12 beats with distinct captions, source artwork indices, camera "
                         "motions and pacing. The renderer proportionally allocates exact 1440 frames "
                         "from your chosen positive relative weights.",
                  "available_artworks":[{"index":i,"title":a["title"],"artist":a["artist"],
                      "sha256":a["sha256"],"source_page":a["page"]} for i,a in enumerate(assets)],
                  "camera_operations":["push","pull","drift_left","drift_right","still"],
                  "music_controls":{"bpm":[55,155],"root_midi":[40,72],
                      "mode":["minor","major"],"progression_degrees":[0,1,2,3,4,5,6]},
                  "exact_output_json":{"title":"film title","story":"original film narrative >20 characters",
                      "beats":[{"artwork":0,"caption":"short original caption","camera":"push",
                                "weight":8}],
                      "music":{"bpm":88,"root_midi":57,"mode":"minor",
                               "progression":[0,3,4,2]}}}
            plan=None
            for attempt in range(3):
                incoming=dict(brief)
                if attempt:incoming["retry_feedback"]="Your prior response failed strict model-owned creative plan validation. Supply your own revised, complete valid JSON film; no guessed asset IDs."
                decision=_call(brain,incoming,transcript,with_image=sheet)
                try:
                    plan=_validate_decision(decision,assets)
                    _weights_to_frames(plan["beats"])
                    break
                except (ValueError,KeyError,TypeError) as exc:
                    transcript[-1]["validation_failure"]=str(exc)
                    plan=None
            if plan is None:
                raise RuntimeError("Real local Brain did not author an executable film and soundtrack")
            evidence["genuine_model_run"]=True
            (dest/"model-authored-film-plan.json").write_text(json.dumps(plan,indent=2,ensure_ascii=False))
            weights=_weights_to_frames(plan["beats"])
            vault=MediaVault(workspace/"vault")
            ordered=[]
            for idx,(beat,nframes) in enumerate(zip(plan["beats"],weights)):
                asset=assets[beat["artwork"]]
                overlay=effects/f"titles-{idx:02d}.png"
                _title_overlay(plan["title"],beat["caption"],idx,len(weights),overlay)
                shot=source_dir/f"model-shot-{idx:02d}.mp4"
                _render_segment(asset["local"],overlay,beat["camera"],nframes,shot)
                att=vault.ingest(shot,mime="video/mp4",rights="generated_original",
                    source_type="trusted_renderer",
                    source_id="zx7-original-motion-from-public-domain-museum-art",
                    evidence=f"Model shot {idx} from artwork id={asset['id']} image sha256={asset['sha256']}; "
                             f"rights provider metadata explicit CC0 and fetched source identity; no false rights certification",
                    owner_or_generator="ZX7 BODY native shot renderer from local neural director")
                ordered.append((nframes,att))
            music_path=source_dir/"model-original-score.wav"
            _render_music(plan["music"],music_path)
            music_att=vault.ingest(music_path,mime="audio/wav",rights="generated_original",
                source_type="trusted_renderer",source_id="zx7-local-brain-original-score",
                evidence="Original algorithmic synthesis entirely from local model authored harmonic parameters",
                owner_or_generator="ZX7 BODY original soundtrack synthesis")
            cursor=0;clips=[]
            for frames,asset in ordered:
                clips.append({"source":"zx7:sha256:"+asset["asset_id"],
                              "asset_id":asset["asset_id"],
                              "attestation_id":asset["attestation_id"],
                              "position_frame":cursor,"first_frame":0,
                              "end_frame":frames,"audio":"intentional_silence"})
                cursor+=frames
            native={"frame_rate":{"numerator":FPS,"denominator":1},
                    "frame_size":{"width":SIZE[0],"height":SIZE[1]},
                    "tracks":[{"clips":clips}],
                    "audio_tracks":[{"clips":[{"source":"zx7:sha256:"+music_att["asset_id"],
                        "asset_id":music_att["asset_id"],"attestation_id":music_att["attestation_id"],
                        "position_frame":0,"first_frame":0,"end_frame":FRAMES}]}]}
            plan_path=workspace/"model-to-native-mlt.json"
            plan_path.write_text(json.dumps(native,indent=2))
            project_path=workspace/"zx7-model-native-edit.mlt"
            evidence["native_project"]=export_owned_mlt(plan_path,workspace,
                                                           workspace/"vault",project_path)
            video_path=workspace/"ZX7-LOCAL-AI-ONE-MINUTE.mp4"
            export=render_owned_mlt(project_path,workspace,video_path)
            evidence["native_render"]=export
            observation=full_decode_inspection(video_path, expected={
                "width":SIZE[0], "height":SIZE[1],
                "duration_seconds":SECONDS, "require_audio":True})
            evidence["independent_decode"]=observation
            if not observation["technical_delivery_verified"]:
                raise RuntimeError("One-minute original film did not pass complete audiovisual decode and clock")
            evidence["film_seconds"]=SECONDS
            evidence["native_mlt_rendered"]=True
            evidence["status"]="rendered_not_art_director_approved"
            # Independent source comparison: every movie frame can be decoded.
            # Do NOT claim source rights or creative quality independently proven.
            (dest/"FINAL-MOVIE-RECEIPT.json").write_text(
                json.dumps({"movie":receipt(video_path),"native_project":receipt(project_path),
                            "model_plan":receipt(dest/"model-authored-film-plan.json"),
                            "music":receipt(music_path)},indent=2))
    except BaseException as exc:
        evidence["failure_type"]=type(exc).__name__
        evidence["failure_text"]=str(exc)[:1200]
        raise
    finally:
        (dest/"actual-model-transcript.json").write_text(
            json.dumps(transcript,indent=2,ensure_ascii=False))
        if model_process is not None:
            peak=read_live_linux_model_peak_rss(model_process.pid)
            evidence["measured_model_process_rss_bytes"]=peak
            model_process.terminate()
            try:model_process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                model_process.kill();model_process.wait()
        (dest/"evidence.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False))
    if evidence["status"]!="rendered_not_art_director_approved":
        raise RuntimeError("No actual full one-minute neural-directed ZX7 native film was produced")


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-lock",required=True)
    p.add_argument("--runtime",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args(argv)
    produce(args)

if __name__=="__main__":
    main()
