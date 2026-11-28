"""Editable, measured original-picture finishing and audio loudness operations.

One creative intelligence chooses EVERY edit and numeric adjustment. There
are no default visual grades, branded looks or automatic stock transitions.
Trusted FFmpeg generates a real new MP4; the source is licensed MediaVault
bytes and will never be silently replaced or overwritten.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
import time
from fractions import Fraction
from pathlib import Path

from .media_vault import MediaVault,sha256_file,canonical_source_attestations
from .delivery_audit import _probe_details
from .composite_mix import _exact_media,sealed_attested_original
from .production_qc import full_decode_inspection
from .edit_timeline import SELF_CONTAINED_VIDEO_INPUT
from .body_stream_custody import _AV_FIELDS, _probe, _packet_digest, _decoded_av
from .body_loudness import _measure_program


def _float(value,kind,minimum,maximum):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or (
            not math.isfinite(value) or value<minimum or value>maximum):
        raise ValueError("Director's "+kind+" is not an executable numerical value")
    return float(value)


def build_finishing_filters(plan,*,has_audio):
    """Tool syntax only. No untrusted executable FFmpeg expressions."""
    if not isinstance(plan,dict) or set(plan)!={"video_ops","audio_ops"}:
        raise ValueError("Creative finisher requires explicitly chosen video/audio operations")
    video=plan["video_ops"];audio=plan["audio_ops"]
    if not isinstance(video,list) or not isinstance(audio,list):
        raise ValueError("Creative operations must be ordered arrays")
    if audio and not has_audio:
        raise ValueError("Cannot create spoken/sound-designed audio from silent film")
    v=[]
    a=[]
    for item in video:
        if not isinstance(item,dict):
            raise ValueError("Invalid visual finishing operation")
        kind=item.get("kind")
        if kind=="color_eq" and set(item)=={
                "kind","brightness","contrast","saturation","gamma"}:
            b=_float(item["brightness"],"brightness",-1,1)
            c=_float(item["contrast"],"contrast",0,3)
            s=_float(item["saturation"],"saturation",0,5)
            g=_float(item["gamma"],"gamma",.1,10)
            v.append(f"eq=brightness={b}:contrast={c}:saturation={s}:gamma={g}")
        elif kind=="denoise" and set(item)=={"kind","luma_spatial","luma_temporal"}:
            spatial=_float(item["luma_spatial"],"luma_spatial",0,20)
            temporal=_float(item["luma_temporal"],"luma_temporal",0,20)
            v.append(f"hqdn3d=luma_spatial={spatial}:luma_tmp={temporal}")
        elif kind=="sharpen" and set(item)=={"kind","strength"}:
            amount=_float(item["strength"],"sharpen_strength",-2,5)
            v.append(f"unsharp=5:5:{amount}:5:5:{amount}")
        else:
            raise ValueError("Unregistered original film finishing operation")
    for item in audio:
        if not isinstance(item,dict):
            raise ValueError("Invalid sound finishing operation")
        kind=item.get("kind")
        if kind=="gain" and set(item)=={"kind","db"}:
            amount=_float(item["db"],"audio_gain_db",-60,30)
            a.append(f"volume={amount}dB")
        elif kind=="loudnorm" and set(item)=={"kind","integrated_lufs","true_peak_dbfs","loudness_range"}:
            target=_float(item["integrated_lufs"],"lufs",-70,-5)
            peak=_float(item["true_peak_dbfs"],"true_peak",-9,0)
            loud_range=_float(item["loudness_range"],"dynamic_range",1,30)
            a.append(f"loudnorm=I={target}:TP={peak}:LRA={loud_range}")
        else:
            raise ValueError("Unregistered original sound finishing operation")
    return v,a


def _continuous_audio_samples(path, stream, scratch):
    """Prove decoded clock continuity before sample-index timestamp rebasing."""
    rate = int(stream["sample_rate"])
    tick = Fraction(stream["time_base"])
    count = 0
    last_frame = 0
    with scratch.open("wb") as report:
        subprocess.run(["ffprobe", "-v", "error", *SELF_CONTAINED_VIDEO_INPUT,
            "-select_streams", str(stream["index"]), "-show_frames",
            "-show_entries", "frame=best_effort_timestamp,nb_samples", "-of", "csv=p=0",
            str(path)], stdout=report, stderr=subprocess.PIPE, check=True, timeout=7200)
    with scratch.open("r", encoding="ascii") as report:
        for row in report:
            try:
                pts, samples = map(int, row.rstrip("\n").split(","))
            except ValueError as exc:
                raise ValueError("Selected audio has no exact decoded frame clock") from exc
            if samples <= 0 or pts * tick * rate != count:
                raise ValueError("Selected audio contains a gap, overlap or nonzero decoded origin")
            count += samples
            last_frame = samples
    logical = stream["duration_ts"] * tick * rate
    if count < logical or count - logical >= last_frame:
        raise ValueError("Selected audio has unsupported decoded end padding")
    return count


def _sound_only_finish(frozen, encoded, audio_filters, selection, private):
    """Apply one explicit sound edit without changing unselected native streams."""
    info = _probe(frozen)
    streams = info["streams"]
    videos = [s for s in streams if s["codec_type"] == "video"]
    audios = [s for s in streams if s["codec_type"] == "audio"]
    if (len(videos) != 1 or videos[0].get("disposition", {}).get("attached_pic") or
            not audios or info.get("chapters") or
            any(s["codec_type"] not in ("video", "audio", "subtitle") for s in streams)):
        raise ValueError("Sound-only MP4 finishing requires one picture, audio, and optional subtitle tracks without chapters")
    if selection is None:
        if len(audios) != 1:
            raise ValueError("An explicit audio stream selection is required for multiple sound programs")
        selection = 0
    if selection >= len(audios):
        raise ValueError("Selected audio stream is absent from the original")
    selected = audios[selection]
    try:
        rate = int(selected["sample_rate"])
        samples = Fraction(selected["time_base"]) * selected["duration_ts"] * rate
        if (selected.get("start_pts") != 0 or type(selected.get("duration_ts")) is not int or
                rate <= 0 or samples.denominator != 1 or samples <= 0):
            raise ValueError("Unsupported audio clock")
    except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError("Selected audio stream requires an exact zero-origin sample clock") from exc
    # The native AAC decoder may expose end padding beyond the logical
    # stream duration. Trim after restoring the original rate (loudnorm can
    # oversample internally); never silently extend the program clock.
    source_samples = _continuous_audio_samples(frozen, selected, private / "clock-before")
    chain = [*audio_filters, f"aresample={rate}", f"atrim=end_sample={int(samples)}", f"asettb=1/{rate}", "asetpts=N"]
    selector = f"a:{selection}"
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-n", "-copyts",
        *SELF_CONTAINED_VIDEO_INPUT, "-i", str(frozen), "-map", "0", "-c", "copy",
        f"-filter:{selector}", ",".join(chain), f"-c:{selector}", "aac",
        f"-b:{selector}", "192k", f"-ar:{selector}", str(rate),
        "-map_metadata", "0", "-map_chapters", "0", "-write_btrt", "0",
        "-movflags", "+faststart", str(encoded)], check=True, capture_output=True, timeout=3600)
    actual = _probe(encoded)["streams"]
    selected_after = None
    if len(actual) != len(streams):
        raise ValueError("Native sound finish changed the stream inventory")
    tags = ("language", "title", "handler_name")
    for before, after in zip(streams, actual):
        if (before["index"] != after["index"] or
                any(before.get("tags", {}).get(k) != after.get("tags", {}).get(k) for k in tags)):
            raise ValueError("Native sound finish changed stream identity or language metadata")
        if before["index"] == selected["index"]:
            selected_after = after
            clock = ("codec_type", "sample_rate", "channels", "channel_layout", "start_pts",
                     "duration_ts", "time_base", "disposition")
            if any(before.get(k) != after.get(k) for k in clock):
                raise ValueError("Native sound finish changed the selected sample clock or layout")
            continue
        if (any(before.get(k) != after.get(k) for k in _AV_FIELDS) or
                _packet_digest(frozen, before["index"], private / "packets-before") !=
                _packet_digest(encoded, after["index"], private / "packets-after")):
            raise ValueError("Native sound finish changed unselected codec parameters, timing or packets")
    decoded_before = _decoded_av(frozen, videos[0], len(audios))
    decoded_after = _decoded_av(encoded, videos[0], len(audios))
    if any(a != b for i, (a, b) in enumerate(zip(decoded_before, decoded_after)) if i != selection + 1):
        raise ValueError("Native sound finish changed decoded unselected picture or sound")
    if selected_after is None:
        raise ValueError("Selected audio stream missing from finished master")
    if _continuous_audio_samples(encoded, selected_after, private / "clock-after") != source_samples:
        raise ValueError("Native sound finish changed decoded sample count")
    deadline = time.monotonic() + 7200
    before = _measure_program(frozen, SELF_CONTAINED_VIDEO_INPUT, selected, selection, deadline)
    after = _measure_program(encoded, SELF_CONTAINED_VIDEO_INPUT,
                             selected_after, selection, deadline)
    if before["decoded_sample_count"] != after["decoded_sample_count"]:
        raise ValueError("Native sound finish changed decoded sample count")
    return {"selected_audio_stream_index": selection,
            "logical_audio_samples": int(samples), "unselected_streams_preserved": len(streams) - 1,
            "unselected_packets_and_decoded_av_preserved": True,
            "selected_program_before": before, "selected_program_after": after,
            "selected_audio_reencoded_as_aac": True,
            "target_loudness_independently_accepted": False}


def finish_authorized_movie(spec_file,workspace,vault_root,output,*,runner=None,probe=None):
    """Actual color and audio finisher using only sealed owner-source input.

    Model-chosen operations remain explicit typed data, never shell commands.
    Production-level technical validation requires real codecs, full picture
    and audio decoding, immutable original source and collision-safe master.
    """
    root=Path(workspace).resolve()
    spec_file=Path(spec_file).resolve()
    destination=Path(output).resolve()
    if (not spec_file.is_file() or not spec_file.is_relative_to(root)
            or destination.suffix.lower()!=".mp4"
            or not destination.is_relative_to(root) or destination.exists()):
        raise ValueError("Finishing needs an existing owner edit and new workspace MP4")
    plan_sha=sha256_file(spec_file)
    source=json.loads(spec_file.read_text(encoding="utf-8"))
    if sha256_file(spec_file)!=plan_sha:
        raise ValueError("Original finishing plan changed while being read")
    if (not isinstance(source,dict) or not {"media","ops"}.issubset(source) or
            set(source)-{"media","ops","audio_stream_index"}):
        raise ValueError("Director's chosen master footage and finishing ops required")
    selection = source.get("audio_stream_index")
    if "audio_stream_index" in source and (type(selection) is not int or selection < 0):
        raise ValueError("Select a nonnegative audio stream index")
    vault=MediaVault(vault_root)
    media=source["media"]
    if not isinstance(media,dict) or set(media)!={"source","asset_id","attestation_id"}:
        raise ValueError("No authenticated original movie asset")
    input_file=_exact_media(media,vault,root,need="video")
    real_codec_proof=runner is None and probe is None
    sound_proof = {}
    destination.parent.mkdir(parents=True,exist_ok=True)
    snapshots={}
    with tempfile.TemporaryDirectory(prefix=".zx7-owned-sources-",dir=root) as working:
        private=Path(working)
        frozen=sealed_attested_original(vault,media["asset_id"],
                                         media["attestation_id"],private,snapshots)
        if sha256_file(input_file)!=media["asset_id"] or sha256_file(spec_file)!=plan_sha:
            raise ValueError("Original edit or media changed before the finishing decoder")
        details=(probe or _probe_details)(frozen)
        filters,audio=build_finishing_filters(source["ops"],
                                             has_audio=details["audio_stream_present"])
        if not filters and not audio:
            raise ValueError("No finishing chosen; keep the original master without a duplicate")
        if selection is not None and (filters or not audio):
            raise ValueError("Explicit audio stream selection requires audio-only finishing")
        encoded=private/"finished-original-master.mp4"
        if real_codec_proof and not filters:
            if frozen.suffix.lower() != ".mp4":
                raise ValueError("Loss-preserving audio-only finishing currently requires original MP4")
            sound_proof = _sound_only_finish(frozen, encoded, audio, selection, private)
        else:
            if real_codec_proof:
                info = _probe(frozen)
                streams = info["streams"]
                videos = [s for s in streams if s["codec_type"] == "video"]
                audios = [s for s in streams if s["codec_type"] == "audio"]
                if (len(videos) != 1 or len(audios) > 1 or len(streams) != len(videos) + len(audios)
                        or info.get("chapters") or videos[0].get("disposition", {}).get("attached_pic")
                        or videos[0].get("pix_fmt") != "yuv420p"
                        or videos[0].get("color_transfer") in ("smpte2084", "arib-std-b67")
                        or videos[0].get("color_primaries") == "bt2020"):
                    raise ValueError("This picture finishing profile cannot preserve additional streams or high-precision/HDR color")
            cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                 "-n",*SELF_CONTAINED_VIDEO_INPUT,"-i",str(frozen)]
            if filters:
                cmd+=["-vf",",".join(filters)]
            if audio:
                cmd+=["-af",",".join(audio)]
            cmd+=["-map","0:v:0"]
            if details["audio_stream_present"]:
                cmd+=["-map","0:a:0","-c:a","aac","-b:a","192k"]
            else:
                cmd+=["-an"]
            cmd+=["-c:v","libx264","-crf","17","-pix_fmt","yuv420p",
                  "-movflags","+faststart",str(encoded)]
            (runner or subprocess.run)(cmd,check=True,timeout=3600)
        if not encoded.is_file() or encoded.stat().st_size<100:
            raise RuntimeError("Physical film master absent after finishing")
        rendered=(probe or _probe_details)(encoded)
        if (rendered["width"],rendered["height"])!=(
                 details["width"],details["height"]) or (
                 abs(rendered["duration_seconds"]-details["duration_seconds"])>.13
                or rendered["audio_stream_present"]!=details["audio_stream_present"]):
            raise RuntimeError("Film finishing silently changed picture timing or soundtrack")
        if real_codec_proof and not sound_proof:
            decoded=full_decode_inspection(encoded,expected={
                "width":details["width"],"height":details["height"],
                "duration_seconds":details["duration_seconds"],
                "require_audio":details["audio_stream_present"]})
            if not decoded["technical_delivery_verified"] or not decoded[
                    "full_picture_and_sound_decoder_completed"]:
                raise RuntimeError("Finished original master failed whole picture/audio decoder")
        if sha256_file(input_file)!=media["asset_id"] or (
                sha256_file(frozen)!=media["asset_id"]) or (
                sha256_file(spec_file)!=plan_sha):
            raise ValueError("Original owner camera, soundtrack or finishing plan changed during processing")
        vault.inspect(media["asset_id"],attestation_id=media["attestation_id"])
        with encoded.open("rb") as ready:
            os.fsync(ready.fileno())
        os.link(encoded,destination)
    return {"path":str(destination),"sha256":sha256_file(destination),
            "source_attestations":canonical_source_attestations([
                {k:media[k] for k in ("asset_id","attestation_id")}]),
            "bytes":destination.stat().st_size,
            "duration_seconds":rendered["duration_seconds"],
            "width":rendered["width"],"height":rendered["height"],
            "audio_present":rendered["audio_stream_present"],
            "video_operations":len(filters),"audio_operations":len(audio),
            "actual_encoded_movie_created":real_codec_proof,
            "sealed_original_cas_during_decode":True,
            "full_picture_and_sound_decoder_completed":real_codec_proof,
            "trusted_real_decoder_verified":real_codec_proof,
            "runner_or_probe_mocked":not real_codec_proof,
            **sound_proof,
            "human_visual_quality_certified":False,
            "human_listening_approved":False}
