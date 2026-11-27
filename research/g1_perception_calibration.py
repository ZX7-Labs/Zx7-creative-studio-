"""One-use synthetic G1 diagnostic, no native writes or artistic approval.

Generate only known test stimuli, decode with the existing BODY, then ask
one provider-native typed observation per case. No owner inputs, arbitrary
media paths, tool dispatch, or automatic retries. Not a production runner.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from time import monotonic

from studio_next.body_editor_export import verify_native_editor_export
from studio_next.body_editor_frame import observe_verified_export_frame
from studio_next.body_editor_audio_timeline import observe_verified_export_audio_timeline
from studio_next.body_editor_policy import EditorPathPolicy
from studio_next.nvidia_model import (NvidiaModelSettings, NvidiaConfigurationError,
                                      NvidiaTransportError)
from studio_next.nvidia_native_tool_model import NvidiaNativeToolCreativeModel
from studio_next.providers import LocalModelOutputError

MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
TIMES = (0.5, 1.5, 2.5)
# Opaque case IDs; truth is never placed in a model-visible context.
CASES = (("blue", 2, 0), ("none", -1, 1), ("red", 0, 0),
         ("none", -1, -1), ("blue", 1, -1))
SCHEMA = {"type": "object", "properties": {
    "picture_color": {"type": "string", "enum": ["none", "red", "blue"]},
    "picture_sample": {"type": "integer", "enum": [-1, 0, 1, 2]},
    "sound_bin": {"type": "integer", "enum": [-1, 0, 1, 2]},
    "relation": {"type": "string", "enum": ["aligned", "offset", "picture_only",
                                            "sound_only", "neither"]}},
    "required": ["picture_color", "picture_sample", "sound_bin", "relation"],
    "additionalProperties": False}
SYSTEM = ("Report only what is observable in these three actual decoded images and "
          "three numerical sound intervals. Image indexes and sound bins are zero-based. "
          "Report a red or blue center square if present, otherwise none and -1. "
          "Report the sound bin with the signal, or -1 if all are effectively silent. "
          "Compare their bins: aligned, offset, picture_only, sound_only, or neither. "
          "Numerical audio diagnostics are not listening. Choose exactly one offered "
          "typed function, including inputs and a concise reason. Do not invent evidence.")


def truth(color, picture, sound):
    relation = ("neither" if picture == sound == -1 else
                "sound_only" if picture == -1 else "picture_only" if sound == -1 else
                "aligned" if picture == sound else "offset")
    return dict(picture_color=color, picture_sample=picture, sound_bin=sound, relation=relation)


def answer(decision):
    if (type(decision) is not dict or set(decision) != {"action", "arguments", "reason"}
            or decision["action"] != "invoke" or type(decision["reason"]) is not str
            or not decision["reason"].strip()):
        raise ValueError("Invalid diagnostic decision")
    args = decision["arguments"]
    if (type(args) is not dict or set(args) != {"tool", "inputs"}
            or args["tool"] != "report_observation"):
        raise ValueError("Invalid diagnostic function")
    result = args["inputs"]
    if type(result) is not dict or set(result) != set(SCHEMA["required"]):
        raise ValueError("Invalid diagnostic fields")
    for key, field in SCHEMA["properties"].items():
        if type(result[key]) is not (int if field["type"] == "integer" else str) or result[key] not in field["enum"]:
            raise ValueError("Invalid diagnostic value")
    return result


def generate(root, case, spec, policy):
    color, picture, sound = spec
    movie = root / "outputs" / (case + ".mp4")
    video = "color=c=gray:s=160x90:r=24:d=3"
    if picture >= 0:
        start = picture * 24 + 6
        video += (f",drawbox=x=60:y=25:w=40:h=40:color={color}:t=fill:"
                  f"enable='between(n,{start},{start + 11})'")
    audio = "anullsrc=r=48000:cl=mono:d=3"
    if sound >= 0:
        audio = ("aevalsrc=0.25*sin(2*PI*880*t)*"
                 f"between(t\\,{sound + .25}\\,{sound + .75}):s=48000:d=3")
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i", video,
                    "-f", "lavfi", "-i", audio, "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    str(movie)], check=True, timeout=30)
    verification = verify_native_editor_export(str(movie), policy=policy)
    digest = verification["native_export_sha256"]
    colors, receipts, images, evidence = [], [], [], []
    for i, seconds in enumerate(TIMES):
        png, receipt = observe_verified_export_frame(str(movie), policy=policy,
            verified_sha256=digest, at_seconds=seconds)
        rgb = subprocess.run(["ffmpeg", "-v", "error", "-f", "image2pipe", "-i", "pipe:0",
                              "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
                             input=png, capture_output=True, check=True, timeout=10).stdout
        if len(rgb) != 160 * 90 * 3:
            raise ValueError("Unexpected physical calibration dimensions")
        r, g, b = rgb[(45 * 160 + 80) * 3:(45 * 160 + 80) * 3 + 3]
        colors.append("red" if r > 200 and max(g, b) < 50 else
                      "blue" if b > 200 and max(r, g) < 50 else "none")
        frame = root / "outputs" / f"{case}-{i}.png"
        frame.write_bytes(png)
        receipts.append(receipt)
        evidence.append({"job_id": case, "path": frame.name,
                         "sha256": hashlib.sha256(png).hexdigest()})
        images.append(("image/png", png))
    audio_receipt = observe_verified_export_audio_timeline(str(movie), policy=policy,
        verified_sha256=digest, start_seconds=0, duration_seconds=3, bins=3)
    picture_indexes = [i for i, value in enumerate(colors) if value != "none"]
    sound_indexes = [i for i, value in enumerate(audio_receipt["intervals"])
                     if value["sample_peak_normalized"] > .1]
    if len(picture_indexes) > 1 or len(sound_indexes) > 1:
        raise ValueError("Ambiguous physical calibration control")
    p = picture_indexes[0] if picture_indexes else -1
    s = sound_indexes[0] if sound_indexes else -1
    expected = truth(colors[p] if p >= 0 else "none", p, s)
    if expected != truth(*spec):
        raise ValueError("Generated media disagrees with independent decoded oracle")
    context = {"case": case, "frame_seconds": TIMES, "picture_evidence": evidence,
        "audio_diagnostics": audio_receipt["intervals"],
        "available_actions": ["invoke"], "compact_tool_catalog": False,
        "actual_granted_native_tools": ["report_observation"],
        "host_native_tool_contracts": [{"name": "report_observation",
            "description": "Return one observation for independent scoring; no editor action.",
            "input_schema": SCHEMA}]}
    return context, images, expected, {"export": verification, "frames": receipts,
                                       "audio": audio_receipt}


def run(root, execute=False):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for name in ("projects", "staging", "outputs"):
        (root / name).mkdir()
    policy = EditorPathPolicy(root / "projects", root / "staging", root / "outputs")
    generated = [generate(root, f"case-{i+1:02}", spec, policy) for i, spec in enumerate(CASES)]
    report = {"model": MODEL, "synthetic_only": True, "max_calls": len(CASES),
              "artistic_quality_approved": False, "semantic_hearing_proven": False,
              "physical_controls": [{"case": ctx["case"], "oracle": expected,
                 "receipt": receipt} for ctx, _, expected, receipt in generated], "results": []}
    def save():
        (root / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    if not execute:
        return report
    model = NvidiaNativeToolCreativeModel(NvidiaModelSettings(model_id=MODEL,
        timeout_seconds=90, max_tokens=8192, sampling={"reasoning_effort": "low"}),
        system_prompt=SYSTEM, allow_image_upload=True)
    model.verify_host_credentials()
    for context, images, expected, _ in generated:
        item = {"case": context["case"], "passed": False}
        started = monotonic()
        stop = False
        try:
            item["observation"] = answer(model.decide_with_images(context, images))
            item["passed"] = item["observation"] == expected
        except (NvidiaTransportError, NvidiaConfigurationError) as exc:
            item["failure_type"] = type(exc).__name__
            stop = True
        except (LocalModelOutputError, ValueError) as exc:
            item["failure_type"] = type(exc).__name__
        item.update(wall_ms=round((monotonic() - started) * 1000, 3),
                    usage=model.last_call_usage)
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
        raise SystemExit("Synthetic model observation control failed; no creative acceptance")
