"""One-use isolated synthetic audio perception diagnostic; no creative edits.

Only locally generated two-second tones are eligible. A host-decoded WAV,
not frequency statistics, reaches the reviewed Omni transport. The scorer
never invokes native operations. This is not music or professional acceptance.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
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

CASES = ((880, 440), (0, 0), (440, 880), (440, 440))
SCHEMA = {"type": "object", "properties": {
    "first_pitch": {"type": "string", "enum": ["low", "high", "silent"]},
    "second_pitch": {"type": "string", "enum": ["low", "high", "silent"]},
    "pattern": {"type": "string", "enum": ["rising", "falling", "steady", "silent"]}},
    "required": ["first_pitch", "second_pitch", "pattern"], "additionalProperties": False}
SYSTEM = ("Listen to the actual two-second WAV, with two one-second halves. "
          "Classify each half as low (near 440 Hz), high (near 880 Hz), or silent. "
          "Report whether pitch rises, falls, stays steady, or is silent. "
          "No numeric audio analysis is provided. Return exactly one offered typed "
          "function with the answer and a concise reason; do not invent perception.")


def classify(frequency):
    if frequency == 0:
        return "silent"
    if 430 <= frequency <= 450:
        return "low"
    if 870 <= frequency <= 890:
        return "high"
    raise ValueError("Unexpected independently decoded tone")


def truth(first, second):
    return {"first_pitch": classify(first), "second_pitch": classify(second),
            "pattern": "silent" if first == second == 0 else "steady" if first == second
                       else "rising" if first < second else "falling"}


def answer(decision):
    if (type(decision) is not dict or set(decision) != {"action", "arguments", "reason"}
            or decision["action"] != "invoke" or type(decision["reason"]) is not str
            or not decision["reason"].strip()):
        raise ValueError("Invalid diagnostic decision")
    args = decision["arguments"]
    if (type(args) is not dict or set(args) != {"tool", "inputs"}
            or args["tool"] != "report_sound"):
        raise ValueError("Invalid diagnostic function")
    result = args["inputs"]
    if type(result) is not dict or set(result) != set(SCHEMA["required"]):
        raise ValueError("Invalid diagnostic fields")
    if any(type(result[k]) is not str or result[k] not in field["enum"]
           for k, field in SCHEMA["properties"].items()):
        raise ValueError("Invalid diagnostic value")
    return result


def measured_tones(raw):
    with wave.open(io.BytesIO(raw), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) != (1, 2, 16000, 32000):
            raise ValueError("Unexpected decoded calibration WAV")
        samples = [x[0] for x in struct.iter_unpack("<h", w.readframes(32000))]
    frequencies, rms = [], []
    # Independent zero-crossing measurement in each stable interior window.
    for start in (3200, 19200):
        window = samples[start:start+9600]
        energy = (sum(x*x for x in window)/len(window))**.5/32768
        crossings = sum(a <= 0 < b for a, b in zip(window, window[1:]))
        frequencies.append(0 if energy < .002 else round(crossings/.6))
        rms.append(energy)
    return frequencies, rms


def generate(root, case, pair, policy):
    first, second = pair
    movie = root / "outputs" / (case + ".mp4")
    audio = ("aevalsrc=if(lt(t\\,1)\\,0.25*sin(2*PI*" + str(first) +
             "*t)\\,0.25*sin(2*PI*" + str(second) + "*t)):s=48000:d=2")
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i",
                    "color=c=gray:s=160x90:r=24:d=2", "-f", "lavfi", "-i", audio,
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(movie)],
                   check=True, timeout=30)
    verified = verify_native_editor_export(str(movie), policy=policy)
    raw, receipt = observe_verified_export_audio(str(movie), policy=policy,
        verified_sha256=verified["native_export_sha256"], start_seconds=0, duration_seconds=2)
    frequencies, rms = measured_tones(raw)
    expected = truth(*frequencies)
    if expected != truth(*pair):
        raise ValueError("Decoded pitch differs from independently specified stimulus")
    if first and (not all(.15 < x < .20 for x in rms) or abs(rms[0]-rms[1]) > .01):
        raise ValueError("Non-silent control has unequal pitch energy")
    if not first and max(rms) >= .002:
        raise ValueError("Silent control unexpectedly contains signal")
    (root / "outputs" / (case + ".wav")).write_bytes(raw)
    # Only the exact transport-required identity/timing fields, never the oracle.
    keys = ("export_sha256", "wav_sha256", "requested_start_seconds",
            "requested_duration_seconds", "observed_audio_duration_seconds",
            "preview_downmixed_and_resampled", "exact_original_audio_pts_proven")
    context = {"case": case, "audio_evidence": {k: receipt[k] for k in keys},
        "available_actions": ["invoke"], "compact_tool_catalog": False,
        "actual_granted_native_tools": ["report_sound"], "host_native_tool_contracts": [
            {"name": "report_sound", "description": "One bounded sound observation, no editor action.",
             "input_schema": SCHEMA}]}
    return context, raw, expected, {"export": verified, "audio": receipt,
                                   "measured_frequency_hz": frequencies, "measured_rms": rms}


def run(root, execute=False):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for name in ("projects", "staging", "outputs"):
        (root / name).mkdir()
    policy = EditorPathPolicy(root / "projects", root / "staging", root / "outputs")
    cases = [generate(root, f"case-{i+1:02}", pair, policy) for i, pair in enumerate(CASES)]
    report = {"model": NVIDIA_OMNI_AUDIO_MODEL_ID, "synthetic_only": True,
              "max_calls": len(CASES), "professional_audio_quality_approved": False,
              "physical_controls": [{"case": ctx["case"], "oracle": expected, "receipt": proof}
                                    for ctx, _, expected, proof in cases], "results": []}
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
    for context, raw, expected, _ in cases:
        item = {"case": context["case"], "passed": False}
        started = monotonic()
        stop = False
        try:
            item["observation"] = answer(model.decide_with_audio(context, [("audio/wav", raw)]))
            item["passed"] = item["observation"] == expected
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
        raise SystemExit("Synthetic sound observation control failed; no professional acceptance")
