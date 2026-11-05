"""Replaceable-model tool-use audition against *live* BODY contracts.

This test executes exactly one model inference per host-approved case and
ZERO creative tool operations. It measures tool choice and declared JSON input
compatibility only. No artwork or motion is generated. It cannot certify
model weights, artistic judgment, production readiness, or BODY execution.
"""
from __future__ import annotations

import hashlib
import json
import math
import time


TOOL_AUDITION_SYSTEM = """You are being tested for exact tool-use compatibility, not
film direction. You are given an ordinary task and real, host-granted tool
schemas. Choose the one tool whose documented function satisfies the task
and provide a JSON object with exactly two keys: operation_id and inputs.
operation_id MUST match exactly one offered operation_id. inputs MUST be a
valid JSON object satisfying that operation's actual machine input schema.
No tools will be executed by this test. Never invent an operation or field.
Output JSON only. Do not explain. Do not imply that you performed the action.
"""

TOOL_AUDITION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "zx7_model_tool_contract_audition",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["operation_id", "inputs"],
            "properties": {
                "operation_id": {"type": "string"},
                "inputs": {"type": "object"},
            },
        },
    },
}


def constrained_local_audition_adapter(actual_model):
    """Use the SAME trusted local model endpoint, with fair diagnostic prompt.

    No external provider is silently added. Any unrelated adapter stays
    unmeasured rather than being assigned an invalid quality or ability score.
    """
    from dataclasses import replace
    from .providers import LocalCreativeModel
    if not isinstance(actual_model, LocalCreativeModel):
        raise ModelToolAuditionError(
            "Only a configured host-local, prompt-isolatable model is supported")
    # Dataclass replacement retains model_id, loopback base URL, byte and
    # time budgets. It never changes or impersonates the production instance.
    return LocalCreativeModel(replace(
        actual_model.settings,
        sampling={
            "temperature": 0.1,
            "max_tokens": 550,
            "response_format": TOOL_AUDITION_RESPONSE_FORMAT,
        }),
        TOOL_AUDITION_SYSTEM)


class ModelToolAuditionError(ValueError):
    """Probe was malformed before a model could safely be tested."""


def _json(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False)


def run_model_tool_audition(model, fabric, case):
    """Run one bounded, non-mutating tool-selection experiment.

    case is authored by a trusted operator and tied to the actual current
    host registry, not generated from the model's reply. The expected tool
    choice is the test oracle; the model never receives its identity as an
    answer key. All offered tools have actually been granted by the host.
    """
    if not callable(getattr(model, "decide", None)):
        raise ModelToolAuditionError("Replaceable model adapter missing decide")
    if not isinstance(case, dict) or set(case) != {
            "case_id", "task", "offered_operation_ids", "expected_operation_id"}:
        raise ModelToolAuditionError("Exact host-owned audition case required")
    task = case["task"]
    if not isinstance(task,str) or not 1<=len(task.strip())<=1024:
        raise ModelToolAuditionError("Audition objective is absent or unbounded")
    case_id = case["case_id"]
    if not isinstance(case_id,str) or not 1<=len(case_id)<=80 or not all(
            c.isalnum() or c in "._-" for c in case_id):
        raise ModelToolAuditionError("Audition identity invalid")
    offers = case["offered_operation_ids"]
    expected = case["expected_operation_id"]
    if (not isinstance(offers,list) or not 2<=len(offers)<=8
            or any(not isinstance(x,str) or not x or len(x)>256 for x in offers)
            or len(set(offers))!=len(offers)
            or not isinstance(expected,str) or expected not in offers):
        raise ModelToolAuditionError("Need two to eight different genuinely granted tools")
    revision = getattr(fabric, "revision", None)
    if not isinstance(revision,str) or not revision:
        raise ModelToolAuditionError("Live tool-catalog revision required")
    tool_descriptors=[]
    for operation_id in offers:
        try:
            spec=fabric.resolve(operation_id,revision=revision)
        except (ValueError, KeyError) as exc:
            raise ModelToolAuditionError("Selected challenge tool not in the host catalog") from exc
        if spec.get("access") not in ("read","write"):
            raise ModelToolAuditionError("Tool lacks actual host permission")
        schema=spec.get("input_schema")
        if not isinstance(schema,dict):
            raise ModelToolAuditionError("Granted capability has no machine schema")
        from .body_editor_mcp import _local_schema_references
        import jsonschema
        _local_schema_references(schema)
        jsonschema.validators.validator_for(schema).check_schema(schema)
        description=spec.get("description","")
        if not isinstance(description,str):
            raise ModelToolAuditionError("Missing real installed capability description")
        tool_descriptors.append({
            "operation_id":operation_id,
            "description":description[:300],
            "schema":schema,
            "access":spec["access"],
        })
    if len(_json(tool_descriptors).encode("utf-8"))>16384:
        raise ModelToolAuditionError("Too many tool schema tokens for bounded audition")
    context = {
        "task": task, "current_host_catalog_revision": revision,
        "actual_granted_tool_contracts": tool_descriptors,
        "expected_response_shape": {"operation_id": "one actual offered tool id",
                                    "inputs": "JSON object matching that tool schema"},
        "body_execution_permitted": False,
        "do_not_guess_tool_names": True,
    }
    measured_at = time.monotonic()
    reason = None
    response = None
    try:
        response=model.decide(context)
    except Exception as exc:
        # A provider outage/JSON decoding failure is not automatically proof of
        # poor creative intelligence. Preserve only the exception type.
        reason="model_transport_or_decoding_"+type(exc).__name__
    elapsed_ms=round((time.monotonic()-measured_at)*1000,3)
    selected = None
    valid_schema = False
    target = False
    if reason is None:
        try:
            reply_bytes=_json(response).encode("utf-8")
            if len(reply_bytes)>65536:
                raise ValueError("Model reply exceeds bounded contract")
        except (ValueError,TypeError,RecursionError,OverflowError):
            reason="model_reply_not_finite_bounded_json"
    if reason is None:
        if not isinstance(response,dict) or set(response)!={"operation_id","inputs"}:
            reason="model_reply_shape_rejected"
        else:
            selected=response["operation_id"]
            inputs=response["inputs"]
            if not isinstance(selected,str) or selected not in offers:
                reason="model_selected_ungranted_operation"
            else:
                target=selected==expected
                if not isinstance(inputs,dict):
                    reason="model_inputs_not_an_object"
                else:
                    import jsonschema
                    spec=next(x["schema"] for x in tool_descriptors
                              if x["operation_id"]==selected)
                    # Preserve native nested schema semantics; do not accept
                    # invented top-level keys ignored by the native handler.
                    admission=json.loads(_json(spec))
                    if ("properties" in admission
                            and isinstance(admission["properties"],dict)
                            and "additionalProperties" not in admission
                            and "patternProperties" not in admission):
                        admission["additionalProperties"]=False
                    validator=jsonschema.validators.validator_for(admission)
                    validator.check_schema(admission)
                    invalid=next(validator(admission).iter_errors(inputs),None)
                    if invalid:
                        reason="model_tool_input_schema_rejected"
                    else:
                        valid_schema=True
                        if not target:
                            reason="model_selected_other_granted_tool"
    eligible = reason is None and target and valid_schema
    result = {
        "schema": 1, "kind": "model_to_body_contract_audition",
        "case_id": case_id,
        "catalog_revision": revision,
        "case_sha256": hashlib.sha256(_json(case).encode()).hexdigest(),
        "model_label": getattr(getattr(model,"settings",None),"model_id",None),
        "model_weights_physically_attested": False,
        "one_model_inference_attempted": True,
        "elapsed_ms_measured": elapsed_ms,
        "offered_granted_tool_count": len(offers),
        "model_selected_expected_tool": target,
        "selected_tool_schema_admissible": valid_schema,
        "model_to_tool_contract_passed": bool(eligible),
        "result_code": reason if reason is not None else "model_selected_schema_valid_tool",
        "body_tool_was_executed": False,
        "creative_quality_reviewed": False,
        "independent_real_model_execution_verified_by_this_function": False,
        "trial_is_not_a_general_model_rating": True,
    }
    return result


def summarize_model_tool_auditions(results):
    """Show narrowly measured, non-comparable case counts, not a power score."""
    if not isinstance(results,(list,tuple)) or len(results)>256:
        raise ModelToolAuditionError("Bounded model audition receipts required")
    if any(not isinstance(x,dict) or x.get("kind")!="model_to_body_contract_audition"
           for x in results):
        raise ModelToolAuditionError("Unknown independent tool-use observation")
    labels={x.get("model_label") for x in results}
    revisions={x.get("catalog_revision") for x in results}
    return {
        "evaluated_case_count":len(results),
        "model_label":next(iter(labels)) if len(labels)==1 else None,
        "one_catalog_revision":len(revisions)==1,
        "matching_tool_and_schema_count":sum(x.get("model_to_tool_contract_passed") is True
                                             for x in results),
        "wrong_tool_count":sum(x.get("result_code")=="model_selected_other_granted_tool"
                               for x in results),
        "invalid_output_count":sum(x.get("result_code") not in (
            "model_selected_schema_valid_tool","model_selected_other_granted_tool")
                                    for x in results),
        "creativity_not_assessed":True,
        "body_execution_not_tested":True,
        "model_weights_not_authenticated_by_tool_use_only":True,
        "no_global_power_score":True,
    }
