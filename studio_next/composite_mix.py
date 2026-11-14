"""Rights-verified independent multi-layer editing, grading and audio mix.

The creative intelligence chooses ALL track positions, clip trims, opacity,
crop/frame dimensions, duration, frame rate, audio gains and color values.
FFmpeg is a trusted technical executor, not a style or editing template.

Source video and sound must have *separately attested real bytes* in MediaVault.
No arbitrary FFmpeg expressions, shell snippets, unverified URL downloads,
brand/font presets, forced scene counts or genre-based edits.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .media_vault import MediaVault,sha256_file,MediaCustodyError
from .delivery_audit import _probe_details
from .production_qc import full_decode_inspection

_COLOR=re.compile(r"^#[a-fA-F0-9]{6}$")
_ID=re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
_SURROUND_SPEAKERS = ("FL", "FR", "FC", "LFE", "BL", "BR")


def _positive(value,label,*,allow_zero=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Nonfinite "+label)
    if value<0 or (not allow_zero and value==0):
        raise ValueError("Invalid "+label)
    return float(value)


def _int(value,label):
    if isinstance(value,bool) or not isinstance(value,int) or value<=0:
        raise ValueError("Invalid "+label)
    return value


def _exact_media(layer,vault,root,*,need):
    if not isinstance(layer,dict) or not isinstance(layer.get("source"),str):
        raise ValueError("Real "+need+" media must be specified")
    asset=layer.get("asset_id")
    attestation=layer.get("attestation_id")
    if not isinstance(asset,str) or not isinstance(attestation,str):
        raise ValueError("Original footage/audio requires an exact rights attestation")
    record=vault.inspect(asset,attestation_id=attestation)
    if not record["rights_attestations"]:
        raise ValueError("Rights proof missing")
    # Machine-neutral source identity. Rendering still uses ONLY a physically
    # verified immutable blob, not an external URL or hallucinated file path.
    # Legacy director-chosen workspace paths remain supported unchanged.
    if layer["source"].startswith("zx7:sha256:"):
        if layer["source"] != "zx7:sha256:"+asset:
            raise ValueError("Original media identity URI differs from verified asset")
        file=Path(record["path"]).resolve()
        if not file.is_relative_to(root.resolve()):
            raise ValueError("Verified media is outside the protected production workspace")
    else:
        path=Path(layer["source"])
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError("Creative tool cannot escape the verified production workspace")
        file=(root/path).resolve()
        if not file.is_relative_to(root.resolve()) or not file.is_file():
            raise ValueError("Physically missing original media")
    if sha256_file(file)!=asset:
        raise ValueError("Source bytes differ from original verified licensed asset")
    return file


def _motion_expression(layer,axis):
    """Author-specified real 2D keyframe interpolation, no camera-style preset."""
    marks=layer.get("motion",[])
    if not marks:
        return str(layer[axis])
    start=float(layer["start"])
    expr=str(marks[-1][axis])
    for a,b in reversed(list(zip(marks,marks[1:]))):
        start_at=start+float(a["at_seconds"])
        end_at=start+float(b["at_seconds"])
        step=float(b["at_seconds"])-float(a["at_seconds"])
        change=b[axis]-a[axis]
        expr=(f"if(lt(t,{end_at:.8f}),"
              f"{a[axis]}+({change})*(t-{start_at:.8f})/{step:.8f},"
              f"{expr})")
    before=start+float(marks[0]["at_seconds"])
    return f"if(lt(t,{before:.8f}),{marks[0][axis]},{expr})"


def _gain_automation_expression(layer):
    """Evaluate director-authored linear-amplitude interpolation per PCM sample.

    FFmpeg aeval evaluates with t = physical time of EACH audio sample.
    This removes audio-frame-boundary stepping from the previous volume
    filter. It costs more CPU than a frame-based gain envelope.
    """
    points=layer.get("gain_keyframes")
    if not points:
        return None
    def amp(point):
        return 10**(float(point["gain_db"])/20)
    expr=format(amp(points[-1]),".12g")
    for earlier,later in reversed(list(zip(points,points[1:]))):
        a=float(earlier["at_seconds"]); b=float(later["at_seconds"])
        level=amp(earlier); delta=amp(later)-level
        expr=(f"if(lt(t,{b:.9g}),{level:.12g}+({delta:.12g})"
              f"*(t-{a:.9g})/{b-a:.9g},{expr})")
    first=points[0]
    t=float(first["at_seconds"])
    if t:
        expr=f"if(lt(t,{t:.9g}),{amp(first):.12g},{expr})"
    # Expression is numeric-only and made exclusively from validated artist
    # gain/time values. It is never arbitrary model-written FFmpeg syntax.
    return "aeval=exprs='val(ch)*("+expr+")':c=same"



def _decoded_source_duration(path,kind):
    """Measure the chosen video/audio STREAM, never the container's duration.

    A camera MP4 may have two seconds of picture but only one second of
    recorded sound. Container length is not evidence for the audio bus.
    """
    if kind not in ("video","audio"):
        raise ValueError("Only actual picture and sound clocks can be measured")
    try:
        raw=subprocess.check_output([
            "ffprobe","-v","error","-show_entries",
            "stream=codec_type,duration,duration_ts,time_base",
            "-of","json",str(path)],timeout=45)
        streams=json.loads(raw)["streams"]
        wanted="video" if kind=="video" else "audio"
        chosen=next(s for s in streams if s.get("codec_type")==wanted)
        value=chosen.get("duration")
        if value in (None,"N/A"):
            from fractions import Fraction
            duration=float(int(chosen["duration_ts"])*Fraction(chosen["time_base"]))
        else:
            duration=float(value)
    except (OSError,ValueError,TypeError,KeyError,StopIteration,
            subprocess.SubprocessError) as exc:
        raise ValueError("Actual original "+kind+" stream duration cannot be established") from exc
    if not math.isfinite(duration) or duration<=0:
        raise ValueError("Original "+kind+" stream has no finite decodable duration")
    return duration

def _audio_sample_index(seconds, rate):
    """Half-even quantization of legacy decimal seconds to integer samples.

    Float multiplication can nudge an exact half-sample to the wrong side
    of its tie. The existing validated seconds input remains unchanged.
    """
    return round(Fraction(str(seconds)) * rate)


def _decoded_audio_stream_format(path):
    """Actual first audio stream sample clock and native speaker identity.

    Codec/channel layouts are physical source facts, not model-controlled
    labels. Never advertise a surround output that a source cannot represent.
    """
    try:
        raw = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate,channels,channel_layout",
             "-of", "json", str(path)], timeout=45)
        stream = json.loads(raw)["streams"][0]
        rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
        layout = stream.get("channel_layout")
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            subprocess.SubprocessError) as exc:
        raise ValueError("Original audio sample clock/channel layout cannot be established") from exc
    if not 1 <= rate <= 768000 or not 1 <= channels <= 64:
        raise ValueError("Original audio stream has unsupported physical clock/channels")
    return rate, channels, layout


def _audio_bus_spec(canvas):
    """Opt-in sound delivery profile, preserving legacy stereo default.

    The allowlist is an *installed/physically reviewed technical* scope, not
    an artistic style or an invented audio engine. Future channel layouts
    require their own exact-input and physical speaker-isolation evidence.
    """
    bus = canvas.get("audio_bus")
    if bus is None:
        return 48000, "stereo", 2
    if (type(bus) is not dict or set(bus) != {"sample_rate", "channel_layout"}
            or type(bus["sample_rate"]) is not int
            or bus["sample_rate"] not in (48000, 96000)
            or type(bus["channel_layout"]) is not str
            or bus["channel_layout"] not in ("stereo", "5.1")):
        raise ValueError("Invalid explicit audio bus sample clock/channel layout")
    layout = bus["channel_layout"]
    return bus["sample_rate"], layout, (6 if layout == "5.1" else 2)


def validate_composition(plan,workspace,vault):
    if not isinstance(plan,dict) or set(plan)!={"canvas","video_layers","audio_tracks"}:
        raise ValueError("An actual editor-authored canvas and tracks required")
    canvas=plan["canvas"]
    expected_canvas={"width","height","fps","duration","background"}
    if not isinstance(canvas,dict) or not expected_canvas.issubset(canvas) or (
            set(canvas)-expected_canvas-{"color_semantics","audio_bus"}):
        raise ValueError("Editor must specify all physical delivery parameters")
    contract=canvas.get("color_semantics")
    if contract is not None and (
            not isinstance(contract,dict) or set(contract)!={"input","output"}
            or contract!={"input":"bt709","output":"bt709"}):
        raise ValueError("Only measured and explicitly declared BT.709 SDR compositing color is supported")
    for field in ("width","height","fps"):
        _int(canvas[field],field)
    seconds=_positive(canvas["duration"],"composition duration")
    if not isinstance(canvas["background"],str) or not _COLOR.fullmatch(canvas["background"]):
        raise ValueError("Editor must specify a valid authored color")
    bus_rate, bus_layout, bus_channels = _audio_bus_spec(canvas)
    video=plan["video_layers"]
    audio=plan["audio_tracks"]
    if not isinstance(video,list) or not isinstance(audio,list) or not (video or audio):
        raise ValueError("No verified creative media tracks")
    root=Path(workspace).resolve()
    seen=set()
    inputs=[]
    real_source_lengths={}
    for kind,items in (("video",video),("audio",audio)):
        for layer in items:
            if not isinstance(layer,dict):
                raise ValueError("Director-specified "+kind+" layer must be an object")
            required=({"id","source","asset_id","attestation_id",
                       "start","source_in","duration","x","y","width","height","opacity"}
                      if kind=="video" else
                      {"id","source","asset_id","attestation_id","start","source_in","duration","gain_db"})
            supported=required|({"motion","fade_in_seconds","fade_out_seconds","chroma_key","source_kind","matte"}
                                if kind=="video" else {"gain_keyframes","stereo_balance","speaker_gains_db"})
            if not required.issubset(layer) or not set(layer).issubset(supported):
                raise ValueError("Director-specified "+kind+" layer is incomplete or uses untrusted effects")
            identifier=layer["id"]
            if not isinstance(identifier,str) or not _ID.fullmatch(identifier) or identifier in seen:
                raise ValueError("Unsafe/duplicate audiovisual layer identifier")
            seen.add(identifier)
            start=_positive(layer["start"],"position",allow_zero=True)
            source_in=_positive(layer["source_in"],"source trim",allow_zero=True)
            duration=_positive(layer["duration"],"original layer duration")
            if start+duration>seconds+1/canvas["fps"]:
                raise ValueError("Layer exceeds editor-authored total duration")
            file=_exact_media(layer,vault,root,need=kind)
            matte_file=None
            if kind=="video" and "matte" in layer:
                matte=layer["matte"]
                if (not isinstance(matte,dict) or set(matte)!={
                        "source","asset_id","attestation_id","source_kind",
                        "source_in","invert"} or type(matte["invert"]) is not bool):
                    raise ValueError("Author-painted source matte needs exact rights and technical scope")
                if matte["source_kind"] not in ("still_image","video"):
                    raise ValueError("Uninstalled creative roto matte source kind")
                mask_time=_positive(matte["source_in"],"physical matte start",allow_zero=True)
                matte_file=_exact_media(matte,vault,root,need="original matte")
                matte_mime=vault.inspect(matte["asset_id"],
                    attestation_id=matte["attestation_id"])["mime"]
                if matte["source_kind"]=="still_image":
                    if matte_mime not in ("image/png","image/jpeg","image/webp"):
                        raise ValueError("Only decoded attested matte pictures accepted")
                    if mask_time!=0:
                        raise ValueError("A frozen 2D matte has no video trim clock")
                else:
                    if matte_mime not in ("video/mp4","video/quicktime","video/webm"):
                        raise ValueError("A moving roto matte requires actual licensed video")
                    mask_clock=(matte_file,"video")
                    if mask_clock not in real_source_lengths:
                        real_source_lengths[mask_clock]=_decoded_source_duration(
                            matte_file,"video")
                    if mask_time+duration>real_source_lengths[mask_clock]+0.015:
                        raise ValueError("Roto matte exceeds actual decoded source video duration")
            still=kind=="video" and layer.get("source_kind")=="still_image"
            if kind=="video" and layer.get("source_kind","video") not in ("video","still_image"):
                raise ValueError("Unknown source media kind; cannot invent a renderer")
            mime=vault.inspect(layer["asset_id"],
                attestation_id=layer["attestation_id"])["mime"]
            if still:
                if mime not in ("image/png","image/jpeg","image/webp"):
                    raise ValueError("Still-image layer must have a decoded, rights-attested image")
                if source_in!=0:
                    raise ValueError("Still-image layers have no physical source-time trim")
                if contract is not None:
                    raise ValueError("Unprofiled still images cannot claim certified BT.709 conversion")
            else:
                if mime.startswith("image/"):
                    raise ValueError("Image requires explicit original still-image source kind")
                clock=(file,kind)
                if clock not in real_source_lengths:
                    real_source_lengths[clock]=_decoded_source_duration(file,kind)
                if source_in+duration>real_source_lengths[clock]+0.015:
                    raise ValueError("Original source trim exceeds physically decoded footage or sound")
            if kind=="audio":
                native_rate, native_channels, native_layout = _decoded_audio_stream_format(file)
                # Legacy stereo accepts mono/stereo as before, but must NEVER
                # silently downmix an actual multichannel source. Require the
                # director to explicitly choose a physically supported bus.
                if bus_layout == "stereo" and native_channels > 2:
                    raise ValueError("Explicit multichannel audio bus required; no silent downmix")
                if bus_layout == "5.1" and (
                        native_channels != 6 or native_layout != "5.1"):
                    raise ValueError("5.1 audio bus requires physical 5.1 source channels; no upmix")
            if kind=="video" and contract is not None:
                # This is not a silent metadata label. Every incoming
                # picture must physically carry the declared SDR VUI, or
                # we cannot claim a consistent compositor output.
                from .body_color_pipeline import _actual_bt709_source
                _actual_bt709_source(file)
            for field in ("width","height"):
                if kind=="video":_int(layer[field],field)
            if kind=="video":
                for key in ("x","y"):
                    if isinstance(layer[key],bool) or not isinstance(layer[key],int):
                        raise ValueError("Creative layer position must be exact integer pixels")
                a=_positive(layer["opacity"],"opacity",allow_zero=True)
                if a>1:raise ValueError("Alpha beyond physical range")
                if "chroma_key" in layer:
                    key=layer["chroma_key"]
                    if not isinstance(key,dict) or set(key)!={"color","similarity","blend"}:
                        raise ValueError("Chroma matte needs explicitly authored color, similarity and blend")
                    if not isinstance(key["color"],str) or not _COLOR.fullmatch(key["color"]):
                        raise ValueError("Original VFX matte key color must be exact RGB")
                    sim=_positive(key["similarity"],"key similarity")
                    blend=_positive(key["blend"],"key edge blending",allow_zero=True)
                    if sim>1 or blend>1:
                        raise ValueError("VFX key compositor strength must stay in physical alpha range")
                motion=layer.get("motion",[])
                if not isinstance(motion,list):
                    raise ValueError("Actual editor motion keyframes must be an array")
                last=-1.0
                for frame in motion:
                    if not isinstance(frame,dict) or set(frame)!={"at_seconds","x","y"}:
                        raise ValueError("Motion keyframe requires original time and 2D position")
                    at=_positive(frame["at_seconds"],"motion timestamp",allow_zero=True)
                    if at<=last or at>duration:
                        raise ValueError("Artist motion keyframes must be in distinct increasing time order")
                    last=at
                    if any(type(frame[axis]) is not int for axis in ("x","y")):
                        raise ValueError("Motion position must use exact original pixel coordinates")
                incoming=_positive(layer.get("fade_in_seconds",0),"artist fade-in",allow_zero=True)
                outgoing=_positive(layer.get("fade_out_seconds",0),"artist fade-out",allow_zero=True)
                if incoming+outgoing>duration:
                    raise ValueError("Original alpha transitions exceed authored layer duration")
            else:
                gain=layer["gain_db"]
                if isinstance(gain,bool) or not isinstance(gain,(int,float)) or (
                        not math.isfinite(gain) or abs(gain)>120):
                    raise ValueError("Unsafe audio gain")
                balance=layer.get("stereo_balance",0)
                if (type(balance) not in (int,float) or
                        not math.isfinite(balance) or not -1<=balance<=1):
                    raise ValueError("Audio stereo balance must be a finite authored value in [-1,1]")
                if bus_layout != "stereo" and balance:
                    raise ValueError("Stereo balance cannot silently remap surround channels")
                speaker_gains = layer.get("speaker_gains_db")
                if speaker_gains is not None:
                    if (bus_layout != "5.1" or type(speaker_gains) is not dict
                            or set(speaker_gains) - set(_SURROUND_SPEAKERS)
                            or any(type(gain) not in (int, float)
                                   or not math.isfinite(gain) or not -96 <= gain <= 24
                                   for gain in speaker_gains.values())):
                        raise ValueError("Surround speaker gains require typed 5.1 dB controls")
                envelope=layer.get("gain_keyframes",[])
                if not isinstance(envelope,list) or len(envelope)>64:
                    raise ValueError("Original audio envelope must be a bounded list")
                previous=-1.0
                for key in envelope:
                    if not isinstance(key,dict) or set(key)!={"at_seconds","gain_db"}:
                        raise ValueError("Audio automation points need time and gain")
                    at=_positive(key["at_seconds"],"audio automation time",allow_zero=True)
                    value=key["gain_db"]
                    if (at<=previous or at>duration or
                        isinstance(value,bool) or not isinstance(value,(int,float))
                        or not math.isfinite(value) or abs(value)>120):
                        raise ValueError("Audio envelope contains out-of-range or unordered points")
                    previous=at
            inputs.append({"kind":kind,"layer":layer,"file":file,
                           "matte_file":matte_file,
                           "start":start,"source_in":source_in,"duration":duration})
    return inputs


def actual_composite_command(plan,workspace,vault,out):
    inputs=validate_composition(plan,workspace,vault)
    c=plan["canvas"]
    w,h,fps,secs=c["width"],c["height"],c["fps"],c["duration"]
    bus_rate, bus_layout, bus_channels = _audio_bus_spec(c)
    filters=[f"color=c=0x{c['background'][1:]}:s={w}x{h}:r={fps}:d={secs},format=rgba[bg]"]
    base="bg"
    args=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y"]
    music=[]
    source_audio_rates={}
    bus_end_samples=_audio_sample_index(secs,bus_rate)
    if bus_end_samples<=0:
        raise ValueError("Composition duration is shorter than one audio sample")
    native_input_index=0
    for index,row in enumerate(inputs):
        layer=row["layer"]
        source_index=native_input_index
        if row["kind"]=="video" and layer.get("source_kind")=="still_image":
            args.extend(["-loop","1","-framerate",str(fps)])
        args.extend(["-i",str(row["file"])])
        native_input_index+=1
        matte_index=None
        if row["matte_file"] is not None:
            matte_index=native_input_index
            matte=layer["matte"]
            if matte["source_kind"]=="still_image":
                args.extend(["-loop","1","-framerate",str(fps)])
            args.extend(["-i",str(row["matte_file"])])
            native_input_index+=1
        start=row["start"];source_in=row["source_in"];duration=row["duration"]
        if row["kind"]=="video":
            visual=(f"[{source_index}:v:0]trim=start={source_in}:duration={duration},"
                f"setpts=PTS-STARTPTS,scale={layer['width']}:{layer['height']}:flags=lanczos,"
                f"fps={fps},format=rgba")
            if "chroma_key" in layer:
                key=layer["chroma_key"]
                visual+=(f",colorkey=0x{key['color'][1:]}:"
                         f"similarity={key['similarity']}:blend={key['blend']}")
            visual+=f",colorchannelmixer=aa={layer['opacity']}"
            if layer.get("fade_in_seconds",0)>0:
                visual+=(f",fade=t=in:st=0:"
                         f"d={layer['fade_in_seconds']}:alpha=1")
            if layer.get("fade_out_seconds",0)>0:
                outgoing_start=duration-float(layer["fade_out_seconds"])
                visual+=(f",fade=t=out:st={outgoing_start}:"
                         f"d={layer['fade_out_seconds']}:alpha=1")
            if matte_index is not None:
                # A rights-checked luma matte multiplies, rather than
                # replaces, the original RGBA/chroma-key/fade alpha. Thus a
                # transparent logo never becomes opaque through its mask.
                matte=layer["matte"]
                filters.append(visual+f"[original{index}]")
                mask=(f"[{matte_index}:v:0]trim=start={matte['source_in']}:"
                      f"duration={duration},setpts=PTS-STARTPTS,"
                      f"scale={layer['width']}:{layer['height']}:flags=bilinear,"
                      f"fps={fps},format=gray")
                if matte["invert"]:
                    mask+=",negate"
                filters.append(mask+f"[mask{index}]")
                filters.extend([
                    f"[original{index}]split[pixels{index}][withalpha{index}]",
                    f"[withalpha{index}]alphaextract[alpha{index}]",
                    f"[alpha{index}][mask{index}]blend=all_mode=multiply[maskedalpha{index}]",
                    f"[pixels{index}][maskedalpha{index}]alphamerge[masked{index}]"
                ])
                filters.append(f"[masked{index}]setpts=PTS+{start}/TB[v{index}]")
            else:
                filters.append(visual+f",setpts=PTS+{start}/TB[v{index}]")
            output=f"stack{index}"
            posx=_motion_expression(layer,"x")
            posy=_motion_expression(layer,"y")
            if layer.get("motion"):
                # FFmpeg comma/colon-bearing expressions are quoted only
                # when keyframe calculations need them.
                posx="'"+posx+"'"
                posy="'"+posy+"'"
            filters.append(
                f"[{base}][v{index}]overlay=x={posx}:y={posy}:"
                f"eof_action=pass:shortest=0:"
                f"enable='between(t,{start},{start+duration})':format=auto[{output}]")
            base=output
        else:
            # Quantize once to each source's real sample clock and to the
            # output bus clock. Millisecond delays silently shift audio.
            if row["file"] not in source_audio_rates:
                source_audio_rates[row["file"]]=_decoded_audio_stream_format(row["file"])[0]
            source_rate=source_audio_rates[row["file"]]
            source_first=_audio_sample_index(source_in,source_rate)
            source_length=_audio_sample_index(duration,source_rate)
            if source_length<=0:
                raise ValueError("Audio trim is shorter than one source sample")
            source_end=source_first+source_length
            lag_samples=_audio_sample_index(start,bus_rate)
            effects=(f"[{source_index}:a:0]atrim=start_sample={source_first}:"
                f"end_sample={source_end},"
                f"asetpts=PTS-STARTPTS,aresample={bus_rate},"
                f"aformat=channel_layouts={bus_layout},volume={layer['gain_db']}dB")
            balance=float(layer.get("stereo_balance",0))
            if balance:
                # Per-channel post-upmix balance, not invented 3D sound or
                # altered speech timing. Inverse endpoints mute only one bus.
                # Leaving balance at 0 retains the existing stereo field.
                left=1-max(0.0,balance)
                right=1+min(0.0,balance)
                effects+=(f",pan=stereo|c0={left:.9g}*c0"
                          f"|c1={right:.9g}*c1")
            speaker_gains = layer.get("speaker_gains_db")
            if speaker_gains:
                # FFmpeg pan executes per-sample and preserves six native
                # source speakers. Coefficients come only from typed finite dB,
                # not a model-supplied filter expression or implicit downmix.
                matrix = "|".join(
                    f"{speaker}={10 ** (float(speaker_gains.get(speaker, 0)) / 20):.12g}*c{index}"
                    for index, speaker in enumerate(_SURROUND_SPEAKERS))
                effects += ",pan=5.1|" + matrix
            envelope=_gain_automation_expression(layer)
            if envelope is not None:
                effects+=","+envelope
            effects+=(f",adelay={lag_samples}S:all=1,apad,"
                      f"atrim=end_sample={bus_end_samples}[audio{index}]")
            filters.append(effects)
            music.append(f"[audio{index}]")
    if "color_semantics" in c:
        filters.append(f"[{base}]format=yuv420p,"
                       "setparams=range=tv:color_primaries=bt709:"
                       "color_trc=bt709:colorspace=bt709[vout]")
    else:
        filters.append(f"[{base}]format=yuv420p[vout]")
    if music:
        if len(music)==1:
            filters.append(f"{music[0]}anull[aout]")
        else:
            filters.append("".join(music)+f"amix=inputs={len(music)}:"
                           "duration=longest:normalize=0[aout]")
    else:
        filters.append(f"anullsrc=r={bus_rate}:cl={bus_layout},"
                       f"atrim=end_sample={bus_end_samples}[aout]")
    args+=["-filter_complex",";".join(filters),"-map","[vout]","-map","[aout]",
           "-c:v","libx264","-pix_fmt","yuv420p","-crf","18",
           "-c:a","aac","-b:a",("512k" if bus_channels==6 else "192k"),
           "-r",str(fps),
           "-t",str(secs),"-movflags","+faststart"]
    if "color_semantics" in c:
        args+=["-color_primaries","bt709","-color_trc","bt709",
               "-colorspace","bt709"]
    if bus_channels != 2 or bus_rate != 48000:
        args += ["-ar", str(bus_rate), "-ac", str(bus_channels)]
    args.append(str(out))
    return args



_SUFFIX_BY_MIME={
    "video/mp4":".mp4","video/quicktime":".mov","video/webm":".webm",
    "audio/wav":".wav","audio/mpeg":".mp3","audio/flac":".flac",
    "image/png":".png","image/jpeg":".jpg","image/webp":".webp","image/x-exr":".exr"
}


def sealed_attested_original(vault,asset_id,attestation_id,private,cache):
    """Shared real native compositor/cut CAS seal, never a model-owned source.

    Always inspect the *exact* owner's immutable attestation first, copy the
    actual vault bytes to an exclusive 0700 render sandbox, fsync, SHA-check,
    chmod 0400, and pass only this frozen local file to the decoder.
    """
    receipt=vault.inspect(asset_id,attestation_id=attestation_id)
    suffix=_SUFFIX_BY_MIME.get(receipt["mime"])
    if suffix is None:
        raise ValueError("No supported original decoder media format")
    key=(asset_id,suffix)
    if key not in cache:
        frozen=private/(asset_id+suffix)
        with Path(receipt["path"]).open("rb") as incoming, frozen.open("xb") as stored:
            shutil.copyfileobj(incoming,stored,1024*1024)
            stored.flush()
            os.fsync(stored.fileno())
        if sha256_file(frozen)!=asset_id:
            raise ValueError("Original video/audio changed while sealing actual decoder input")
        os.chmod(frozen,0o400)
        cache[key]=frozen
    return cache[key]


def _freeze_composition_sources(plan,root,vault,private):
    """Copy every owner-attested original into readonly CAS-sealed render inputs.

    This isolates the actual native compositor from a mutable or temporarily
    swapped artist checkout path. The planned scene, layers and sound envelopes
    are *not* modified, only the private physical decoder input addresses.
    """
    clone=copy.deepcopy(plan)
    preserved={}
    sealed={}
    for kind in ("video_layers","audio_tracks"):
        for layer in clone[kind]:
            identity=layer["asset_id"]
            attestation=layer["attestation_id"]
            record=vault.inspect(identity,attestation_id=attestation)
            suffix=_SUFFIX_BY_MIME.get(record["mime"])
            if suffix is None:
                raise ValueError("No exact decoder format for original layer material")
            original_layer=next(x for x in plan[kind] if x["id"]==layer["id"])
            original=_exact_media(original_layer,vault,root,
                                  need=kind)
            preserved[str(original)]=identity
            frozen=sealed_attested_original(
                vault,identity,attestation,private,sealed)
            layer["source"]=str(frozen.relative_to(root))
            if kind=="video" and "matte" in layer:
                original_matte=original_layer["matte"]
                original_mask=_exact_media(original_matte,vault,root,
                                           need="original matte")
                preserved[str(original_mask)]=original_matte["asset_id"]
                pinned_mask=sealed_attested_original(
                    vault,original_matte["asset_id"],
                    original_matte["attestation_id"],private,sealed)
                layer["matte"]["source"]=str(pinned_mask.relative_to(root))
    validate_composition(clone,root,vault)
    return clone,preserved,sealed

def render_composition(plan_json,workspace,vault_root,out,*,runner=None,probe=None):
    root=Path(workspace).resolve()
    source=Path(plan_json)
    before=sha256_file(source)
    plan=json.loads(source.read_text(encoding="utf-8"))
    if sha256_file(source)!=before:
        raise ValueError("Director composition plan changed during initial read")
    vault=MediaVault(vault_root)
    output=Path(out).resolve()
    if output.suffix.lower()!=".mp4" or output.exists():
        raise ValueError("Cannot overwrite previously accepted original movie")
    output.parent.mkdir(parents=True,exist_ok=True)
    # Each licensed editor render owns a distinct exclusive stage. A shared
    # deterministic ".incomplete.mp4" can be raced: FFmpeg -y would overwrite
    # another editor's in-flight movie, or loser cleanup could unlink it.
    fd,private_name=tempfile.mkstemp(
        prefix=".zx7-composite-render-",suffix=".mp4",dir=output.parent)
    os.close(fd)
    temporary=Path(private_name)
    try:
        with tempfile.TemporaryDirectory(prefix=".zx7-owned-sources-",dir=root) as working:
            frozen,originals,snapshots=_freeze_composition_sources(
                plan,root,vault,Path(working))
            if sha256_file(source)!=before:
                raise ValueError("Original audiovisual plan changed before rendering")
            cmd=actual_composite_command(frozen,root,vault,temporary)
            (runner or subprocess.run)(cmd,check=True,timeout=3600)
            if not temporary.is_file() or temporary.stat().st_size<100:
                raise RuntimeError("FFmpeg did not generate real audiovisual media")
            detail=(probe or _probe_details)(temporary)
            expected=plan["canvas"]
            if detail["width"]!=expected["width"] or detail["height"]!=expected["height"] or (
                    abs(detail["duration_seconds"]-expected["duration"])>
                    max(.12,2/expected["fps"])) or not detail["audio_stream_present"]:
                raise RuntimeError("Rendered composite disagrees with authored geometry/timing/audio")
            real_codec_proof=runner is None and probe is None
            observed_sound = None
            if real_codec_proof:
                qa=full_decode_inspection(temporary,expected={
                    "width":expected["width"],
                    "height":expected["height"],
                    "require_audio":True})
                if not qa["technical_delivery_verified"] or not qa[
                        "full_picture_and_sound_decoder_completed"]:
                    raise RuntimeError("Actual composited film failed whole video/audio decode")
                rate, channels, layout = _decoded_audio_stream_format(temporary)
                bus_rate, bus_layout, bus_channels = _audio_bus_spec(expected)
                if (rate != bus_rate or channels != bus_channels
                        or layout != bus_layout):
                    raise RuntimeError("Actual exported audio channel/speaker clock disagrees with authored bus")
                observed_sound = {"sample_rate": rate, "channels": channels,
                                  "channel_layout": layout}
            if sha256_file(source)!=before or any(
                    sha256_file(path)!=digest for path,digest in originals.items()):
                raise ValueError("Owner media or director plan changed during real compositing")
            if any(sha256_file(path)!=digest for (digest,_),path in snapshots.items()):
                raise ValueError("Original frozen media bytes changed during compositing")
            for kind in ("video_layers","audio_tracks"):
                for layer in plan[kind]:
                    vault.inspect(layer["asset_id"],
                                  attestation_id=layer["attestation_id"])
                    if kind=="video" and "matte" in layer:
                        matte=layer["matte"]
                        vault.inspect(matte["asset_id"],
                                      attestation_id=matte["attestation_id"])
            # Hardlink rejects any concurrent creator's approved result; an
            # os.replace() could silently overwrite an already accepted movie.
            with temporary.open("rb") as movie:
                os.fsync(movie.fileno())
            os.link(temporary,output)
        return {"path":str(output),"sha256":sha256_file(output),
                "bytes":output.stat().st_size,"duration_seconds":detail["duration_seconds"],
                "video_layers":len(plan["video_layers"]),
                "audio_tracks":len(plan["audio_tracks"]),"audio_present":True,
                "audio_sample_rate": observed_sound["sample_rate"] if observed_sound else None,
                "audio_channels": observed_sound["channels"] if observed_sound else None,
                "audio_channel_layout": observed_sound["channel_layout"] if observed_sound else None,
                "verified_physically":real_codec_proof,
                "full_picture_and_sound_decoder_completed":real_codec_proof,
                "test_runner_or_probe_injected":not real_codec_proof,
                "sealed_original_cas_during_decode":True,
                "human_artistic_approval":False}
    finally:
        # Only this attempt's native private movie may be deleted. Never
        # delete an accepted film after losing the no-clobber hardlink race.
        temporary.unlink(missing_ok=True)
