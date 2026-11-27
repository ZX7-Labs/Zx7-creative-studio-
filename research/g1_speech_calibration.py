"""Isolate speech competence on the reviewed synthetic-only Omni WAV route.

The prior pitch calibration failed. Generated phrases and silence test a
separate documented model capability, without changing the transport or
claiming music understanding. No editor writes, user data or retry loop.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
from time import monotonic
import wave

from studio_next.body_editor_export import verify_native_editor_export
from studio_next.body_editor_audio import observe_verified_export_audio
from studio_next.body_editor_policy import EditorPathPolicy
from studio_next.nvidia_model import (NvidiaModelSettings, NvidiaConfigurationError,
                                      NvidiaTransportError)
from studio_next.nvidia_native_tool_model import (NVIDIA_OMNI_AUDIO_MODEL_ID,
                                                  NvidiaOmniNativeToolCreativeModel)
from studio_next.providers import LocalModelOutputError

CASES = ("silver moon", "", "paper boat", "winter rain")
DURATION = 2.5
SCHEMA = {"type": "object", "properties": {
    "transcript": {"type": "string", "maxLength": 120}},
    "required": ["transcript"], "additionalProperties": False}
SYSTEM = ("Transcribe the actual short WAV in English, without guessing words. "
          "If it contains no speech, return an empty transcript. Do not describe "
          "the sound or add any commentary to the transcript. Choose exactly one "
          "offered typed function with the transcript and a concise reason.")


def normalized(value):
    return " ".join(re.findall(r"[a-z]+", value.casefold()))


def answer(decision):
    if (type(decision) is not dict or set(decision) != {"action", "arguments", "reason"}
            or decision["action"] != "invoke" or type(decision["reason"]) is not str
            or not decision["reason"].strip()):
        raise ValueError("Invalid diagnostic decision")
    args = decision["arguments"]
    if (type(args) is not dict or set(args) != {"tool", "inputs"}
            or args["tool"] != "report_transcript"):
        raise ValueError("Invalid diagnostic function")
    result = args["inputs"]
    if (type(result) is not dict or set(result) != {"transcript"}
            or type(result["transcript"]) is not str or len(result["transcript"]) > 120):
        raise ValueError("Invalid diagnostic transcript")
    # Reject non-English tokens instead of normalizing them into false silence.
    if result["transcript"] and not re.fullmatch(r"[a-zA-Z\s.,!?'-]+", result["transcript"]):
        raise ValueError("Transcript contains unsupported characters")
    return result["transcript"]


def score(observed, expected):
    if not expected:
        return not observed.strip()
    return normalized(observed) == expected


def pcm_info(raw):
    with wave.open(io.BytesIO(raw), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) != (1, 2, 16000, 40000):
            raise ValueError("Unexpected calibration WAV framing")
        pcm = wav.readframes(40000)
    values = [x[0] for x in struct.iter_unpack("<h", pcm)]
    return {"pcm_sha256": hashlib.sha256(pcm).hexdigest(),
            "rms": (sum(x*x for x in values)/len(values))**.5/32768,
            "peak": max(abs(x) for x in values)/32768}


def generate(root, case, phrase, policy):
    if phrase not in CASES:
        raise ValueError("Only the fixed synthetic speech controls are allowed")
    movie = root / "outputs" / (case + ".mp4")
    speech = root / "staging" / (case + ".wav")
    # Generate local fixed stimuli, no model calls or external synthesis.
    source = f"flite=text='{phrase}':voice=slt" if phrase else "anullsrc=r=16000:cl=mono:d=2.5"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i", source,
                    "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(speech)],
                   check=True, timeout=30)
    with wave.open(str(speech), "rb") as w:
        duration = w.getnframes()/w.getframerate()
        if not 0 < duration <= DURATION:
            raise ValueError("Generated speech exceeds the untruncated stimulus window")
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i",
                    "color=c=gray:s=160x90:r=24:d=2.5", "-i", str(speech),
                    "-af", "apad=whole_dur=2.5", "-t", "2.5",
                    "-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "-1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(movie)],
                   check=True, timeout=30)
    verified = verify_native_editor_export(str(movie), policy=policy)
    raw, receipt = observe_verified_export_audio(str(movie), policy=policy,
        verified_sha256=verified["native_export_sha256"], start_seconds=0, duration_seconds=DURATION)
    info = pcm_info(raw)
    if info["pcm_sha256"] != receipt["pcm_sha256"]:
        raise ValueError("Decoded PCM receipt mismatch")
    if phrase and not (.005 < info["rms"] < .6 and .02 < info["peak"] < 1):
        raise ValueError("Speech control is silent or clipped")
    if not phrase and info["peak"] > .002:
        raise ValueError("Silent control contains unexpected signal")
    (root / "outputs" / (case + ".wav")).write_bytes(raw)
    keys = ("export_sha256", "wav_sha256", "requested_start_seconds",
            "requested_duration_seconds", "observed_audio_duration_seconds",
            "preview_downmixed_and_resampled", "exact_original_audio_pts_proven")
    context = {"case": case, "audio_evidence": {k: receipt[k] for k in keys},
        "available_actions": ["invoke"], "compact_tool_catalog": False,
        "actual_granted_native_tools": ["report_transcript"], "host_native_tool_contracts": [
            {"name": "report_transcript", "description": "One bounded transcription, no editor action.",
             "input_schema": SCHEMA}]}
    return context, raw, phrase, {"export": verified, "audio": receipt, "pcm": info,
                                  "generated_speech_duration_seconds": duration}


def run(root, execute=False):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for name in ("projects", "staging", "outputs"):
        (root / name).mkdir()
    policy = EditorPathPolicy(root / "projects", root / "staging", root / "outputs")
    controls = [generate(root, f"case-{i+1:02}", phrase, policy) for i, phrase in enumerate(CASES)]
    report = {"model": NVIDIA_OMNI_AUDIO_MODEL_ID, "synthetic_only": True,
              "max_calls": len(CASES), "music_or_professional_acceptance": False,
              "physical_controls": [{"case": ctx["case"], "oracle": phrase, "receipt": proof}
                                    for ctx, _, phrase, proof in controls], "results": []}
    def save():
        (root / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    if not execute:
        return report
    model = NvidiaOmniNativeToolCreativeModel(NvidiaModelSettings(model_id=NVIDIA_OMNI_AUDIO_MODEL_ID,
        timeout_seconds=90, max_tokens=8192, sampling={"temperature": .2,
            "chat_template_kwargs": {"enable_thinking": False}}), system_prompt=SYSTEM,
        allow_original_audio_upload=True)
    model.verify_host_credentials()
    for context, raw, expected, _ in controls:
        item = {"case": context["case"], "passed": False}
        started = monotonic()
        stop = False
        try:
            item["transcript"] = answer(model.decide_with_audio(context, [("audio/wav", raw)]))
            item["passed"] = score(item["transcript"], expected)
        except (NvidiaTransportError, NvidiaConfigurationError) as exc:
            item["failure_type"] = type(exc).__name__
            stop = True
        except (LocalModelOutputError, ValueError) as exc:
            item["failure_type"] = type(exc).__name__
        item.update(wall_ms=round((monotonic()-started)*1000, 3), usage=model.last_call_usage)
        report["results"].append(item)
        save()
        print(json.dumps(item), flush=True)
        if stop:
            break
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = run(args.out, execute=args.execute)
    if args.execute and (len(result["results"]) != len(CASES) or
                         not all(x["passed"] for x in result["results"])):
        raise SystemExit("Synthetic speech calibration failed; no broader audio acceptance")
