"""Real, pinned, LOCAL model diagnostic against the actually installed BODY ABI.

NOT a creative audition. Does not invoke any BODY edit/tool, reconfigure the
model, install software via pip, or fake skill as a percentage. It loads a
source-verified local Qwen GGUF in an isolated CPU trial and compares THREE
host-owned decisions to real granted schemas. All failures are evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_next.body_capabilities import installed_body_capability_fabric
from studio_next.model_tool_audition import (
    run_model_tool_audition, summarize_model_tool_auditions,
)
from studio_next.providers import LocalCreativeModel, LocalModelSettings
from scripts.run_local_brain_creative_film import _await_model


_AUDITION_SYSTEM = """You are being tested for exact tool-use compatibility, not
film direction. You are given an ordinary task and real, host-granted tool
schemas. Choose the one tool whose documented function satisfies the task
and provide a JSON object with exactly two keys: operation_id and inputs.
operation_id MUST match exactly one offered operation_id. inputs MUST be a
valid JSON object satisfying that operation's actual machine input schema.
No tools will be executed by this test. Never invent an operation or field.
Output JSON only. Do not explain. Do not imply that you performed the action.
"""


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evidence_bytes(path, data):
    path=Path(path)
    if path.exists():
        raise FileExistsError("Never replace an existing physical model trial")
    raw=(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode("utf-8")
    with path.open("xb") as file:
        file.write(raw)
    return {"sha256":hashlib.sha256(raw).hexdigest(), "bytes":len(raw)}


def execute(args):
    output=Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    runtime=Path(args.runtime).resolve()
    if runtime.exists():
        raise FileExistsError("Model runtime must be a fresh isolated directory")
    runtime.mkdir(parents=True, exist_ok=False)
    workspace=output/"workspace"
    workspace.mkdir()
    case_path=ROOT/"research/model-tool-audition-cases.json"
    manifest=json.loads(case_path.read_text(encoding="utf-8"))
    if (manifest.get("schema")!=1 or
            manifest.get("kind")!="operator-owned-model-to-body-audition-cases"
            or not isinstance(manifest.get("cases"),list)
            or not 1<=len(manifest["cases"])<=8):
        raise ValueError("Only bounded host-owned benchmark cases are admissible")
    pinned=ROOT/"engines/velorn/local-model-trial.lock.json"
    lock=json.loads(pinned.read_text(encoding="utf-8"))
    if (lock["model"]["id"]!="unsloth/Qwen3.5-2B-GGUF"
            or lock["model"]["license"]!="Apache-2.0"
            or lock["server"]["host"]!="127.0.0.1"):
        raise ValueError("Pinned host-approved local model identity is invalid")
    fabric=installed_body_capability_fabric(workspace)
    # Fail before downloading weights if this device cannot grant the benchmark
    # contracts; no invented or cached names are passed to the brain.
    for item in manifest["cases"]:
        for operation in item["offered_operation_ids"]:
            fabric.resolve(operation,revision=fabric.revision)
    result={
        "schema":1,
        "kind":"real_local_model_abi_compatibility_trial",
        "status":"attempted_not_certified",
        "body_catalog_revision":fabric.revision,
        "actual_case_manifest_sha256":sha(case_path),
        "actual_model_lock_sha256":sha(pinned),
        "model_id":lock["model"]["id"],
        "model_revision":lock["model"]["revision"],
        "local_inference_attestation":"model_weights_verified_by_source_pinned_download_helper",
        "no_body_tool_was_executed":True,
        "no_paid_api_was_used":True,
        "professional_creative_quality_unmeasured":True,
        "real_model_results":[],
    }
    weights_log=output/"local-model-server.log"
    model_proc=None
    try:
        with weights_log.open("xb") as logfile:
            model_proc,weights=_await_model(lock,runtime,logfile)
        # Source-pinned byte manifests are the physical proof. Do not expose
        # local runtime paths, private model contexts or raw completions.
        result["pinned_model_files"]={
            name:{"sha256":data.get("sha256"),"bytes":data.get("bytes")}
            for name,data in weights.items()}
        model=LocalCreativeModel(LocalModelSettings(
            model_id=lock["server"]["alias"],
            base_url="http://127.0.0.1:8080",
            timeout_seconds=300,
            sampling={"temperature":0.1,"max_tokens":550,
                      "response_format":{"type":"json_schema","json_schema":{
                          "name":"zx7_model_tool_contract_audition",
                          "strict":True,
                          "schema":{"type":"object",
                              "additionalProperties":False,
                              "required":["operation_id","inputs"],
                              "properties":{
                                  "operation_id":{"type":"string"},
                                  "inputs":{"type":"object"}}}}}}
        ),_AUDITION_SYSTEM)
        for case in manifest["cases"]:
            receipt=run_model_tool_audition(model,fabric,case)
            result["real_model_results"].append(receipt)
            # Persist each case before proceeding; a later inference crash is
            # not a license to manufacture successes for the missing cases.
            evidence_bytes(output/(case["case_id"]+".json"),receipt)
            print("PHYSICAL_MODEL_CASE",case["case_id"],
                  receipt["result_code"],"ms",receipt["elapsed_ms_measured"],
                  flush=True)
        result["summary"]=summarize_model_tool_auditions(result["real_model_results"])
        result["status"]="all_case_outputs_recorded_not_creative_certification"
    except BaseException as exc:
        result["status"]="blocked"
        result["failure_type"]=type(exc).__name__
        raise
    finally:
        if model_proc is not None:
            model_proc.terminate()
            try:
                model_proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                model_proc.kill()
                model_proc.wait(timeout=12)
        result["source_receipts_have_no_model_text_or_source_media"]=True
        evidence_bytes(output/"trial-summary.json",result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--runtime",type=Path,required=True)
    arguments=parser.parse_args()
    execute(arguments)


if __name__=="__main__":
    main()
