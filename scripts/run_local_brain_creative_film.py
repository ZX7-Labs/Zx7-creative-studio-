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
from studio_next.model_film_revision import (
    ModelFilmRevisionError, apply_model_selected_revision,
    encoded_film_contact_sheet)

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
    # Search the model's actual research topics. Category:CC-Zero is an
    # alphabetical category listing, NOT a search index; using its sort-key
    # prefix previously supplied unrelated images under a valid CC0 license.
    themes=[]
    for qi, phrase in enumerate(queries):
        tokens=re.findall(r"[A-Za-z]{3,}",phrase)
        if len(tokens)<1:
            raise ValueError("Creative source theme lacks meaningful search terms")
        for term in dict.fromkeys((phrase," ".join(tokens[:2]))):
            themes.append((qi,term))
    records={}
    query_pools=[[] for _ in queries]
    for qi,term in themes:
        params={
            "action":"query","format":"json",
            "generator":"search","gsrsearch":term,
            "gsrnamespace":6,"gsrlimit":50,
            "prop":"imageinfo","iiprop":"url|mime|extmetadata",
            "iiurlwidth":1280,
            "iiextmetadatafilter":"LicenseShortName|LicenseUrl"}
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
        for rec in sorted(pages.values(),key=lambda p: p.get("index",10000) if isinstance(p,dict) else 10000):
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
            # Commons often records the *canonical Creative Commons license*
            # as http:// rather than https://. A page URL is NOT fetched by
            # this check: require the exact CC0 license host and path, not a
            # risky startswith() comparison or a provider-controlled domain.
            if not isinstance(urlstr,str):
                continue
            license_uri=urllib.parse.urlsplit(urlstr)
            if (license_uri.scheme not in ("http","https")
                    or license_uri.hostname!="creativecommons.org"
                    or license_uri.username or license_uri.password
                    or license_uri.query or license_uri.fragment
                    or license_uri.path not in (
                        "/publicdomain/zero/1.0/",
                        "/publicdomain/zero/1.0/deed.en")):
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
            if ident not in records:
                records[ident]={
                    "id":ident,"title":str(rec.get("title","")).removeprefix("File:")[:150],
                    "artist":"","image_url":image,"page":page,
                    "public_domain_flag":True,"declared_license":"CC0",
                    "license_url":urlstr,
                    "provider":"Wikimedia_Commons_CC_Zero",
                    "original_mime":info["mime"],
                    "search_hit_for_queries":[]}
            if queries[qi] not in records[ident]["search_hit_for_queries"]:
                records[ident]["search_hit_for_queries"].append(queries[qi])
            if ident not in query_pools[qi]:
                query_pools[qi].append(ident)
            admitted+=1
        print("Live Commons topic search",repr(term),
              "CC0 eligible matches",admitted,"overall",len(records),flush=True)
    covered=sum(bool(pool) for pool in query_pools)
    if len(records)<6 or covered<2:
        raise ValueError("Not enough CC0 media matched distinct creative search themes; refusing unrelated substitutes")
    # Diversify across the director's search intentions instead of filling
    # nine consecutive source slots from the first lexicographic neighborhood.
    candidate_ids=[]
    seen=set()
    for offset in range(max(map(len,query_pools),default=0)):
        for pool in query_pools:
            if offset<len(pool) and pool[offset] not in seen:
                seen.add(pool[offset])
                candidate_ids.append(pool[offset])
    source=[]
    for record in (records[i] for i in candidate_ids[:90]):
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
        if (type(beat.get("weight")) not in (int,float) or
                not math.isfinite(beat["weight"]) or
                not 0 < beat["weight"] <= 1_000_000):
            raise ValueError("Model relative pacing weight must be positive and finite")
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
    if sum(ints)!=FRAMES or min(ints)<1:
        raise ValueError("Model selected an invisible beat with no physical video frames")
    return ints

def _fit_film_caption(draw, caption, *, max_width, max_height,
                      largest_px=42, smallest_px=17):
    """Fit the *whole* neural caption inside an available typographic box.

    Never truncate text, shrink outside explicit legibility bounds, or
    silently paint text beyond the frame. Return exact measured geometry.
    Caption words are creative data; no fixed script or artistic sentences.
    """
    if (not isinstance(caption, str) or not caption.strip() or
            "\\n" in caption or "\\r" in caption or
            not 50 <= max_width <= 10_000 or
            not 20 <= max_height <= 10_000):
        raise ValueError("Invalid physical caption or title-safe geometry")
    text = caption.strip()
    for px in range(largest_px, smallest_px-1, -1):
        font = _font(px)
        lines = []
        current = ""
        for word in text.split():
            proposed = f"{current} {word}" if current else word
            if draw.textbbox((0, 0), proposed, font=font)[2] <= max_width:
                current = proposed
            else:
                if not current:
                    break  # A single unbreakable word exceeds the safe area.
                lines.append(current)
                current = word
        else:
            if current:
                lines.append(current)
            if 1 <= len(lines) <= 2:
                spacing = max(5, round(px*0.16))
                block = "\\n".join(lines)
                left, top, right, bottom = draw.multiline_textbbox(
                    (0, 0), block, font=font, spacing=spacing)
                if (right-left <= max_width and
                        bottom-top <= max_height and
                        all(draw.textbbox((0,0), line, font=font)[2]
                            <= max_width for line in lines)):
                    return {
                        "text":block,"font":font, "font_px":px,
                        "spacing":spacing,"bbox":(left, top, right, bottom),
                        "lines":lines,
                    }
    raise ValueError(
        "Model-authored caption cannot fit without clipping or unreadable type")


def _title_overlay(title, caption, number, count, dest):
    W,H = SIZE
    im = Image.new("RGBA", (W,H))
    draw = ImageDraw.Draw(im)
    # Bottom gradient for reliable foreground contrast on source images.
    # This is a renderer safety layer, not the model's visual-art direction.
    for y in range(370,H):
        alpha=int(205*((y-370)/(H-370))**1.4)
        draw.line((0,y,W,y),fill=(8,11,19,alpha),width=1)
    gutter=max(48,round(W*.06))
    right=W-gutter
    if type(number) is not int or type(count) is not int or not 0<=number<count:
        raise ValueError("Invalid actual native editorial beat index")
    if not isinstance(title,str) or not title.strip():
        raise ValueError("Missing original model-authored film title")
    headline_font = _font(19)
    headline = title.upper()
    box = draw.textbbox((0,0),headline,font=headline_font)
    if box[2]-box[0] > right-gutter:
        raise ValueError("Film title exceeds measured safe area")
    draw.text((gutter,478),headline,font=headline_font,fill=(215,206,187,225))
    layout = _fit_film_caption(
        draw,caption,max_width=right-gutter,max_height=112)
    draw.multiline_text(
        (gutter,514-layout["bbox"][1]),layout["text"],
        font=layout["font"],spacing=layout["spacing"],
        fill=(255,252,247,245))
    draw.rectangle((gutter,644,gutter+int((right-gutter)*(number+1)/count),647),
                   fill=(214,167,106,225))
    draw.text((gutter,667),f"{number+1:02d} / {count:02d}",
              font=_font(15),fill=(223,224,225,218))
    im.save(dest,format="PNG")


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


def _review_encoded_film_and_revise(*, brain, plan, assets, ordered,
                                    native, music_att, video_path,
                                    observation, workspace, vault,
                                    transcript, dest, alternate_cut_requested=False):
    """Actual encoded visual evidence -> independent model-selected native edit.

    Keep both native project versions and both decoded movies. No host-authored
    creative revision, no automatic approval and no invented soundtrack hearing.
    A model's decision to retain its first edit is recorded, not treated as
    proof of an actual post-observation edit.
    """
    first_frames = [n for n, _ in ordered]
    review_image = workspace/"effects"/"first-encoded-film-preview.png"
    preview = encoded_film_contact_sheet(
        video_path, first_frames, review_image, fps=FPS)
    if preview["source_sha256"] != sha256_file(video_path):
        raise RuntimeError("Observed visual preview is not bound to decoded export")
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["action", "beat_index", "field", "value",
                     "expected_before", "reason"],
        "properties": {
            "action": {"type":"string", "enum":["keep", "revise"]},
            "beat_index": {"type":"integer", "minimum":0,
                           "maximum":len(plan["beats"])-1},
            "field": {"type":"string",
                      "enum":["caption", "camera", "artwork", "weight"]},
            "value": {"type":"string", "minLength":1, "maxLength":100},
            "expected_before": {"type":"string", "minLength":1, "maxLength":100},
            "reason": {"type":"string", "minLength":12, "maxLength":600},
        },
    }
    brain.settings.sampling["response_format"] = {
        "type":"json_schema",
        "json_schema":{"name":"zx7_native_film_observation_revision",
                       "strict":True, "schema":schema}
    }
    film_identity = sha256_file(video_path)
    request = {
        "phase": "actual_encoded_output_review",
        "task": (
            "You are reviewing the real decoded output of the film that YOU "
            "independently directed. The attached indexed storyboard samples "
            "actual decoded frames at the center of every authored beat; it "
            "is not original still artwork. Inspect composition, legibility, "
            "visual continuity and editorial pacing. Sound measurements "
            "describe physical levels only: you have NOT listened to the "
            "music and must not claim you have. Independently decide whether "
            "a concrete visual or pacing repair is warranted. If so, pick "
            "exactly one beat and one editable field to revise. Reply as "
            "{action:revise,beat_index:integer,field:caption|camera|artwork|weight,"
            "value:string,expected_before:string,reason:string}. "
            "Beat N in the picture is beat_index=N-1 in the editable plan; "
            "do not confuse the content of neighboring beats. "
            "expected_before MUST exactly reproduce the current field value "
            "at the chosen beat_index from current_edit_plan; this is a "
            "source-state precondition, not an artistic opinion. "
            "When revising a caption, the artwork title/source inventory is "
            "the only attached image's explicit factual metadata. Never "
            "borrow the date, museum, origin or identity of another artwork, "
            "or fabricate new dates, credits or numeric catalog identifiers. "
            "Creative imagery and metaphors are allowed, but unverified "
            "factual attribution will be rejected by the native host. "
            "The value is the proposed new "
            "caption, registered camera name, decimal relative beat weight, "
            "or source inventory index as a string. If actual evidence does "
            "not justify an edit, choose action:keep; the other fields must "
            "still be present but no change will occur. You must not fabricate "
            "frames, audio impressions, licenses, results or professional approval."
        ),
        "actual_movie_sha256": film_identity,
        "physical_delivery": {
            "duration_seconds": observation["duration_seconds"],
            "full_picture_and_sound_decoder_completed":
                observation["full_picture_and_sound_decoder_completed"],
            "audio_measurements": observation["audio_measurements"],
            "audio_understanding_or_artistic_quality_approved": False,
        },
        "picture_evidence": [{
            "job_id": film_identity,
            "path": str(review_image),
            "sha256": preview["preview_sha256"],
        }],
        "preview_limitations": {
            "temporal_sampling_only": True,
            "continuous_motion_analysis_not_proven": True,
            "audio_has_not_been_listened_to": True,
        },
        "current_edit_plan": plan,
        "source_inventory": [
            {"index":i,"sha256":item["sha256"],"title":item["title"]}
            for i,item in enumerate(assets)
        ],
    }
    if alternate_cut_requested:
        # An explicit alternate-cut workload is different from an autonomous
        # decision to self-revise. No author-picked field/value/scene is passed
        # to the model, and a model refusal remains a real failed trial.
        request["alternate_cut_experiment_requested"] = True
        request["task"] += (
            " Additional separate trial instruction: deliver one genuinely "
            "different editorial version after seeing the source-attested "
            "first render. Independently choose whichever native beat and "
            "field would best strengthen your current idea. Prefer action:revise "
            "when a safe meaningful change is possible. Keep the original "
            "unchanged as version one. This is a technical alternate-cut "
            "request, not evidence that the original was artistically bad.")
    # A small local model has previously confused two neighboring beats and
    # asserted a previous caption that was not on its selected target. Reject
    # that stale or hallucinated before-value, and let the neural model inspect
    # the actual native state again. Never invent or auto-apply a creative edit.
    for review_attempt in range(3):
        decision = _call(brain, request, transcript, with_image=review_image)
        try:
            revised, model_edit = apply_model_selected_revision(
                plan, decision, asset_count=len(assets),
                source_titles=[asset["title"] for asset in assets])
        except ModelFilmRevisionError as exc:
            transcript[-1]["source_precondition_or_edit_validation_failed"] = str(exc)
            if review_attempt == 2:
                raise
            request["retry_feedback"] = {
                "rejected_edit_reason":str(exc),
                "read_actual_beat_index_and_exact_before_field":True,
                "native_beats_now":[
                    {"beat_index":i, **beat}
                    for i, beat in enumerate(plan["beats"])
                ],
                "model_must_choose_its_own_correct_source_bound_edit":True,
            }
            continue
        break
    (dest/"model-original-export-review.json").write_text(
        json.dumps({"visual_preview":preview, "model_decision":decision,
                    "validated_edit":model_edit,
                    "initial_movie":receipt(video_path),
                    "quality_certified":False}, indent=2, ensure_ascii=False))
    if not model_edit["revision_applied"]:
        return {"status":("model_declined_requested_alternate_cut"
                          if alternate_cut_requested else
                          "model_kept_original_after_visual_review"),
                "visual_preview":preview, "model_selected_edit":model_edit,
                "post_observation_native_write":False,
                "semantic_audio_review_verified":False}

    _validate_decision(revised, assets)
    frame_lengths = _weights_to_frames(revised["beats"])
    selected_index = model_edit["beat_index"]
    revision_dir = workspace/"revision-01"
    revision_dir.mkdir(exist_ok=False)
    shot_dir = revision_dir/"source"
    shot_dir.mkdir()
    effect_dir = revision_dir/"effects"
    effect_dir.mkdir()
    actual_revisions = []
    new_ordered = []
    for index,(beat, frames) in enumerate(zip(revised["beats"],frame_lengths)):
        if beat == plan["beats"][index] and frames == first_frames[index]:
            new_ordered.append(ordered[index])
            continue
        asset = assets[beat["artwork"]]
        overlay = effect_dir / f"titles-{index:02d}.png"
        _title_overlay(revised["title"], beat["caption"], index,
                       len(frame_lengths), overlay)
        shot = shot_dir / f"model-revised-shot-{index:02d}.mp4"
        _render_segment(asset["local"], overlay, beat["camera"], frames, shot)
        att = vault.ingest(
            shot, mime="video/mp4", rights="generated_original",
            source_type="trusted_renderer",
            source_id="zx7-local-model-source-custodied-revision",
            evidence=(f"Real post-observation selected native revision beat={selected_index} "
                      f"changed_rendered_beat={index}; Commons source id={asset['id']} "
                      f"art_sha256={asset['sha256']}; CC0 metadata is not legal clearance"),
            owner_or_generator="ZX7 BODY local-model selected original visual revision")
        new_ordered.append((frames, att))
        actual_revisions.append({
            "beat":index, "source_art_sha256":asset["sha256"],
            "previous_asset_id":ordered[index][1]["asset_id"],
            "revised_asset_id":att["asset_id"], "source_shot":receipt(shot),
            "reused_original_source":False,
        })
    if not actual_revisions:
        raise RuntimeError("Model-selected revision generated no new native shot")
    cursor = 0
    clips = []
    for nframes, att in new_ordered:
        clips.append({"source":"zx7:sha256:"+att["asset_id"],
                      "asset_id":att["asset_id"],
                      "attestation_id":att["attestation_id"],
                      "position_frame":cursor, "first_frame":0,
                      "end_frame":nframes, "audio":"intentional_silence"})
        cursor += nframes
    if cursor != FRAMES:
        raise RuntimeError("Revision breaks the exact rational native picture clock")
    second_native = {
        "frame_rate":native["frame_rate"],"frame_size":native["frame_size"],
        "tracks":[{"clips":clips}],
        "audio_tracks":native["audio_tracks"],
    }
    plan_file = workspace/"model-to-native-mlt-revised.json"
    plan_file.write_text(json.dumps(second_native, indent=2))
    second_project = workspace/"zx7-model-native-edit-revised.mlt"
    native_receipt = export_owned_mlt(
        plan_file, workspace, workspace/"vault", second_project)
    second_movie = workspace/"ZX7-LOCAL-AI-ONE-MINUTE-REVISED.mp4"
    render_receipt = render_owned_mlt(second_project,workspace,second_movie)
    decoded = full_decode_inspection(second_movie, expected={
        "width":SIZE[0],"height":SIZE[1],"duration_seconds":SECONDS,
        "require_audio":True,
    })
    if not decoded["technical_delivery_verified"]:
        raise RuntimeError("Model-selected revision did not pass full A/V decode")
    if sha256_file(second_movie) == film_identity:
        raise RuntimeError("Model selected edit but actual decoded export has unchanged bytes")
    revised_plan_path = dest/"model-authored-revised-film-plan.json"
    revised_plan_path.write_text(json.dumps(revised, indent=2, ensure_ascii=False))
    return {
        "status":"model_revised_real_native_edit_after_visual_review",
        "visual_preview":preview, "model_selected_edit":model_edit,
        "revised_plan":receipt(revised_plan_path),
        "native_project":native_receipt,
        "native_render":render_receipt,
        "full_decode":decoded,
        "movie":receipt(second_movie),
        "project":receipt(second_project),
        "source_revisions":actual_revisions,
        "source_movie_preserved":receipt(video_path),
        "independent_artistic_quality_certified":False,
        "semantic_audio_review_verified":False,
        "post_observation_native_write":True,
        "alternate_cut_experiment":alternate_cut_requested,
    }

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
            assets=None
            source_trials=[]
            for attempt in range(4):
                task={
                    "phase":"creative_research",
                    "task":"Choose an original film title, concept, and 3 artistic "
                           "source search themes for a one-minute public-domain "
                           "museum-art film. Use broad, concrete, independently "
                           "searchable 1–3 word subjects, not multi-clause visual "
                           "prompts, camera instructions or scene descriptions. "
                           "Actual images must match your artistic intentions "
                           "and self-declare CC0 at their source page. "
                           "Return JSON: {\"working_title\":string,"
                           "\"search_queries\":[string,string,string]}. "
                           "You choose all subjects; there is no host-selected genre.",
                }
                if source_trials:
                    task["previous_trials"] = source_trials[-2:]
                    task["failure_feedback"] = (
                        "Your previous independent Commons source search "
                        "did not yield enough real CC0-downloadable images. "
                        "Choose NEW broad concrete topics with more likely "
                        "public-source coverage; do not invent source URLs, "
                        "license clearance or search results.")
                decision=_call(brain,task,transcript)
                try:
                    queries=decision["search_queries"]
                    if (not isinstance(queries,list) or
                            not 2<=len(queries)<=5 or
                            any(not isinstance(q,str) or
                                not 2<=len(q)<=160 for q in queries)):
                        raise ValueError("Unusable creative source-query format")
                except (ValueError,KeyError,TypeError) as exc:
                    source_trials.append({
                        "attempt":attempt + 1,"status":"invalid_model_queries",
                        "failure":str(exc)})
                    transcript[-1]["research_validation_failure"]=str(exc)
                    continue
                # Never replace the neural model's subject with engineer-
                # chosen stock footage. New research is another *actual*
                # local neural decision. Retain all failed source trials.
                attempt_dir=art/f"model-search-{attempt + 1:02d}"
                attempt_dir.mkdir(exist_ok=False)
                try:
                    current_assets=_museum_images(queries,attempt_dir)
                except (ValueError,OSError) as exc:
                    source_trials.append({
                        "attempt":attempt + 1,
                        "status":"no_sufficient_rights-declared_physical_assets",
                        "model_queries":queries,
                        "failure_type":type(exc).__name__,
                        "failure":str(exc)[:240]})
                    transcript[-1]["research_source_failure"]=str(exc)[:240]
                    continue
                topic=decision
                assets=current_assets
                source_trials.append({
                    "attempt":attempt + 1,"status":"physically_downloaded",
                    "model_queries":queries,
                    "source_count":len(assets)})
                break
            evidence["model_selected_source_trials"]=source_trials
            if topic is None or assets is None:
                raise RuntimeError(
                    "Local creative Brain could not identify sufficient "
                    "physical CC0-declared source artwork after explicit retries")
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
            # Grammar-guided transport, not a prewritten film. The real
            # neural model still selects every artwork, caption, arc, beat,
            # camera, duration weight and original musical direction.
            # The pinned llama.cpp backend supports JSON-schema output and
            # this prevents the CPU model from omitting the entire soundtrack.
            brain.settings.sampling["response_format"]={
                "type":"json_schema",
                "json_schema":{"name":"zx7_original_one_minute_film",
                               "strict":True,
                               "schema":{
                    "type":"object","additionalProperties":False,
                    "required":["title","story","beats","music"],
                    "properties":{
                        "title":{"type":"string","minLength":3,"maxLength":70},
                        "story":{"type":"string","minLength":20,"maxLength":800},
                        "beats":{"type":"array","minItems":6,"maxItems":12,
                                 "items":{"type":"object","additionalProperties":False,
                                          "required":["artwork","caption","camera","weight"],
                                          "properties":{
                                              "artwork":{"type":"integer","minimum":0,
                                                         "maximum":len(assets)-1},
                                              "caption":{"type":"string","minLength":3,
                                                         "maxLength":100},
                                              "camera":{"type":"string","enum":[
                                                  "push","pull","drift_left",
                                                  "drift_right","still"]},
                                              "weight":{"type":"number",
                                                        "exclusiveMinimum":0,
                                                        "maximum":1000000}}}},
                        "music":{"type":"object","additionalProperties":False,
                                 "required":["bpm","root_midi","mode","progression"],
                                 "properties":{
                                     "bpm":{"type":"integer","minimum":55,"maximum":155},
                                     "root_midi":{"type":"integer","minimum":40,"maximum":72},
                                     "mode":{"type":"string","enum":["major","minor"]},
                                     "progression":{"type":"array","minItems":2,
                                                    "maxItems":8,
                                                    "items":{"type":"integer",
                                                             "minimum":0,"maximum":6}}}}
                    }}}}
            plan=None
            last_validation_failure=None
            for attempt in range(3):
                incoming=dict(brief)
                if attempt:
                    incoming["retry_feedback"]=(
                      "Previous film plan failed: "+str(last_validation_failure)+
                      ". Please supply a complete revised JSON with all required "
                      "film fields, original music and 6–12 actual editorial beats. "
                      "Relative weights can be positive decimals. No invented asset IDs.")
                decision=_call(brain,incoming,transcript,with_image=sheet)
                try:
                    plan=_validate_decision(decision,assets)
                    _weights_to_frames(plan["beats"])
                    break
                except (ValueError,KeyError,TypeError) as exc:
                    transcript[-1]["validation_failure"]=str(exc)
                    last_validation_failure=str(exc)
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
            # This stage is driven by an actual separate local neural turn
            # supplied with the exact rendered movie's decoded preview.
            evidence["post_export_creative_review"] = _review_encoded_film_and_revise(
                brain=brain, plan=plan, assets=assets, ordered=ordered,
                native=native, music_att=music_att, video_path=video_path,
                observation=observation, workspace=workspace, vault=vault,
                transcript=transcript, dest=dest,
                alternate_cut_requested=args.alternate_cut)
            if args.alternate_cut and not evidence[
                    "post_export_creative_review"]["post_observation_native_write"]:
                raise RuntimeError(
                    "Explicit alternate-cut trial requested, but the genuine "
                    "model chose no native revision; refusing a false proof")
            evidence["status"] = (
                "rendered_revised_not_art_director_approved"
                if evidence["post_export_creative_review"]["post_observation_native_write"]
                else "rendered_not_art_director_approved")
            # Independent source comparison: every movie frame can be decoded.
            # Do NOT claim source rights or creative quality independently proven.
            final_receipts = {
                "original_movie":receipt(video_path),
                "original_native_project":receipt(project_path),
                "original_model_plan":receipt(dest/"model-authored-film-plan.json"),
                "original_music":receipt(music_path),
                "creative_quality_independently_approved":False,
            }
            if evidence["post_export_creative_review"]["post_observation_native_write"]:
                final_receipts["model_selected_revised_movie"] = (
                    evidence["post_export_creative_review"]["movie"])
                final_receipts["revised_native_project"] = (
                    evidence["post_export_creative_review"]["project"])
                final_receipts["revised_model_plan"] = (
                    evidence["post_export_creative_review"]["revised_plan"])
            (dest/"FINAL-MOVIE-RECEIPT.json").write_text(
                json.dumps(final_receipts,indent=2))
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
    if evidence["status"] not in (
            "rendered_not_art_director_approved",
            "rendered_revised_not_art_director_approved"):
        raise RuntimeError("No actual full one-minute neural-directed ZX7 native film was produced")


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-lock",required=True)
    p.add_argument("--runtime",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--alternate-cut",action="store_true",
                   help="Explicit experimental request for a neural alternative "
                        "after reviewing the genuinely encoded first film")
    args=p.parse_args(argv)
    produce(args)

if __name__=="__main__":
    main()
