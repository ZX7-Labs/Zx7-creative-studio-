"""Factual broadcast-style integrated loudness and TRUE-PEAK observation.

Read-only measurement of selected, rights-attested original audio programs.
Uses FFmpeg ebur128 true-peak option, never normalizes/re-encodes sound or
imposes an artistic streaming/broadcast target. It reports actual LUFS/LRA
and oversampled dBFS peak when the local installed analyzer supports them.

EBU R128 advises LRA isn't meaningful on very short (<60 s) content.
Full source pixel/audio decoder acceptance is independent of sound quality.
Separate encoded soundtracks are not isolated production stems.
"""
from __future__ import annotations
import json
import math
import re
import subprocess
import tempfile
import time
from pathlib import Path

from .composite_mix import _exact_media,sealed_attested_original
from .edit_timeline import SELF_CONTAINED_VIDEO_INPUT
from .media_vault import MediaVault,sha256_file

_VALUE=r"(-?(?:inf|\d+(?:\.\d+)?))"


def _level(summary,title,unit):
    match=re.search(title+r":\s*"+_VALUE+r"\s*"+unit,summary,re.I)
    if not match:
        raise ValueError("Native ebur128 analysis omitted "+title+" measurement")
    raw=match.group(1)
    if raw.lower()=="-inf":
        return "-inf" # JSON compliant; never encode Infinity/NaN
    value=float(raw)
    if not math.isfinite(value):
        raise ValueError("Native measured loudness is non-finite")
    return value


_AUDIO_FORMATS={"audio/wav":"wav","audio/mpeg":"mp3","audio/flac":"flac"}
_MAX_TRACKS=8
_METER="ebur128=peak=true:framelog=verbose,astats=metadata=0:reset=0:measure_perchannel=none:measure_overall=Number_of_samples"


def _inspect_programs(frozen,mime):
    if mime in _AUDIO_FORMATS:
        policy=("-protocol_whitelist","file,pipe","-format_whitelist",_AUDIO_FORMATS[mime])
    elif mime in ("video/mp4","video/quicktime","video/webm"):
        policy=SELF_CONTAINED_VIDEO_INPUT
    else:
        raise ValueError("Sound audit requires an attested audio or audiovisual container")
    try:
        info=json.loads(subprocess.check_output(["ffprobe","-v","error",*policy,
            "-show_streams","-show_format","-of","json",str(frozen)],timeout=60))
        duration=float(info["format"]["duration"])
        streams=info["streams"]
        if not isinstance(streams,list) or not math.isfinite(duration) or duration<=0:
            raise ValueError("Invalid actual stream inventory or duration")
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        raise ValueError("Original media stream inventory could not be physically measured") from exc
    audio=[s for s in streams if s.get("codec_type")=="audio"]
    if not audio:
        raise ValueError("Actual original media has no audio to measure")
    picture=None
    if mime not in _AUDIO_FORMATS:
        picture=next((s for s in streams if s.get("codec_type")=="video" and
                      not s.get("disposition",{}).get("attached_pic")),None)
        if picture is None or any(type(picture.get(k)) is not int or picture[k]<1
                                  for k in ("width","height")):
            raise ValueError("Actual original audiovisual media has no valid picture stream")
    return policy,duration,audio,picture


def _measure_program(frozen,policy,stream,ordinal,deadline):
    index=stream.get("index")
    try:
        rate=int(stream["sample_rate"])
        channels=stream["channels"]
        if type(index) is not int or index<0 or rate<1 or type(channels) is not int or channels<1:
            raise ValueError("Invalid physical stream identity or sample clock")
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError("Actual audio stream lacks a verified sample clock") from exc
    remaining=deadline-time.monotonic()
    if remaining<=0:
        raise ValueError("Bounded native sound measurement time exhausted")
    proc=subprocess.run(["ffmpeg","-hide_banner","-nostdin","-nostats","-loglevel","info",
         "-xerror",*policy,"-i",str(frozen),"-map",f"0:{index}","-vn",
         "-af",_METER,"-f","null","-"],capture_output=True,text=True,timeout=remaining,check=False)
    if proc.returncode:
        raise ValueError("Original waveform failed actual full-program true-peak analysis")
    report=proc.stderr or ""
    if "Summary:" not in report:
        raise ValueError("Actual EBU R128 media analysis was not completed")
    sections=re.split(r"\n\s*(Integrated loudness|Loudness range|True peak):",report.rsplit("Summary:",1)[1])
    if len(sections)<7:
        raise ValueError("Actual EBU R128 measurement summary was incomplete")
    facts={sections[i]:sections[i+1] for i in range(1,len(sections)-1,2)}
    try:
        integrated=_level(facts["Integrated loudness"],"I","LUFS")
        lra=_level(facts["Loudness range"],"LRA","LU")
        peak=_level(facts["True peak"],"Peak","dBFS")
    except KeyError as exc:
        raise ValueError("Incomplete originally decoded broadcast audio measurements") from exc
    counts=re.findall(r"\[Parsed_astats_[^\n]*?\] Number of samples: (\d+)(?:\.0+)?\s*$",report,re.M)
    if len(counts)!=1 or int(counts[0])<1:
        raise ValueError("Native audio decoder did not report a complete sample count")
    samples=int(counts[0]); duration=samples/rate
    language=stream.get("tags",{}).get("language")
    if not isinstance(language,str) or not re.fullmatch(r"[A-Za-z0-9-]{1,16}",language):
        language=None
    return {"audio_stream_index":ordinal,"container_stream_index":index,
            "sample_rate_hz":rate,"channels":channels,"language":language,
            "decoded_sample_count":samples,"decoded_duration_seconds":duration,
            "integrated_loudness_lufs":integrated,"loudness_range_lu":lra,
            "measured_true_peak_dbfs":peak,"lra_short_film_less_than_60_seconds_unreliable":duration<60}


def inspect_original_loudness(plan_file,workspace,vault_root):
    root=Path(workspace).resolve()
    source=Path(plan_file).resolve()
    if not source.is_file() or not source.is_relative_to(root):
        raise ValueError("No original protected artist loudness plan")
    plan_sha=sha256_file(source)
    plan=json.loads(source.read_text(encoding="utf-8"))
    if sha256_file(source)!=plan_sha:
        raise ValueError("Sound director's original plan changed during read")
    if not isinstance(plan,dict) or "media" not in plan or set(plan)-{"media","audio_stream_indices"}:
        raise ValueError("Sound audit needs verified original media and optional audio stream indices")
    indices=plan.get("audio_stream_indices",[0])
    if (not isinstance(indices,list) or not 1<=len(indices)<=_MAX_TRACKS or
            any(type(i) is not int or i<0 for i in indices) or len(set(indices))!=len(indices)):
        raise ValueError("Select one to eight unique nonnegative audio stream indices")
    media=plan["media"]
    if not isinstance(media,dict) or set(media)!={"source","asset_id","attestation_id"}:
        raise ValueError("Original soundtrack requires exactly one licensed source identity")
    vault=MediaVault(vault_root)
    movie=_exact_media(media,vault,root,need="audio")
    digest=sha256_file(movie)
    record=vault.inspect(digest,attestation_id=media["attestation_id"])
    if digest!=media["asset_id"]:
        raise ValueError("Source changed before native sound loudness measurement")
    with tempfile.TemporaryDirectory(prefix=".zx7-owned-sources-",dir=root) as working:
        frozen=sealed_attested_original(vault,digest,media["attestation_id"],Path(working),{})
        if sha256_file(source)!=plan_sha or sha256_file(movie)!=digest:
            raise ValueError("Original sound program changed before native analysis")
        policy,duration,audio,picture=_inspect_programs(frozen,record["mime"])
        if any(i>=len(audio) for i in indices):
            raise ValueError("Selected audio stream index is absent from the original container")
        deadline=time.monotonic()+7200
        tracks=[_measure_program(frozen,policy,audio[i],i,deadline) for i in indices]
        if (sha256_file(frozen)!=digest or sha256_file(movie)!=digest
                or sha256_file(source)!=plan_sha):
            raise ValueError("Original audio bytes or owner direction changed during true-peak measurement")
        vault.inspect(digest,attestation_id=media["attestation_id"])
    if sha256_file(movie)!=digest or sha256_file(source)!=plan_sha:
        raise ValueError("Artist original footage/sound or instructions changed during measurement")
    # Keep the existing scalar contract on the first requested program. The
    # ordered per-program results are not an invented combined mix or stems.
    primary=tracks[0]
    return {
        "path":record["path"],"original_workspace_path":str(movie),
        "sha256":digest,"bytes":record["size_bytes"],
        "asset_id":digest,"attestation_id":media["attestation_id"],
        "rights":record["rights_attestations"][0]["rights"],
        "duration_seconds":duration,"audio_present":True,"picture_present":picture is not None,
        "width":picture["width"] if picture else None,"height":picture["height"] if picture else None,
        "original_film_audio_measurement":"FFmpeg ebur128 with true-peak detector",
        "integrated_loudness_lufs":primary["integrated_loudness_lufs"],
        "loudness_range_lu":primary["loudness_range_lu"],
        "measured_true_peak_dbfs":primary["measured_true_peak_dbfs"],
        "lra_short_film_less_than_60_seconds_unreliable":primary["lra_short_film_less_than_60_seconds_unreliable"],
        "source_duration_seconds":duration,
        "source_original_audio_stream_verified":True,
        "meter_analyzed_exact_private_attested_cas":True,
        "audio_stream_selection":"first actual audio stream" if "audio_stream_indices" not in plan else "explicit ordered audio stream indices",
        "available_audio_stream_count":len(audio),"audio_stream_measurements":tracks,
        "loudness_normalization_applied_to_source":False,
        "any_target_lufs_or_peak_imposed":False,
        "multitrack_stem_analysis_covered":False,
        "dialogue_intelligibility_or_aesthetic_quality_approved":False
    }
