"""ZX7 universal, evidence-first capability diagnostics.

Separates BODY availability, execution receipts, model-interface observations,
and independently assessed creative quality. No universal 'AI power' score;
no sample or synthetic fixture can establish artistic competence.

Callers provide ONLY host-observed facts. Do not expose model/user text, media
paths, raw error messages or external URLs in the public-facing projection.
The pure projection cannot issue a model inference, mutate a project or install
an engine. Every future BODY domain uses its live capability name, not a
hardcoded editor-specific list.
"""
from __future__ import annotations

from collections import Counter
import math
import re

_SCHEMA = 1
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_STATES = frozenset({
    "queued", "running", "completed", "blocked", "failed", "paused", "cancelled",
    "stopped", "budget_exhausted", "model_finished", "needs_owner_input",
})
_PHASES = (
    "source", "perception", "planning", "discovery", "contract",
    "execution", "observation", "verification", "review", "delivery",
)
_MAX_ROWS = 5000


class DiagnosticEvidenceError(ValueError):
    """A diagnostic report lacks sufficient bounded, trusted source facts."""


def _name(value, field):
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise DiagnosticEvidenceError(f"Invalid {field} identity")
    return value


def _whole(value, field):
    if type(value) is not int or value < 0:
        raise DiagnosticEvidenceError(f"Invalid observed {field} count")
    return value


def _rows(value, field):
    if not isinstance(value, (tuple, list)) or len(value) > _MAX_ROWS:
        raise DiagnosticEvidenceError(f"Unbounded {field}")
    if any(not isinstance(row, dict) for row in value):
        raise DiagnosticEvidenceError(f"Malformed {field}")
    return value


def compare_controlled_trials(control, candidate):
    """Conservative causal-isolation rule for a *paired* host-run capability trial.

    A comparison is useful only when the same physical input, exact granted
    contract and installed BODY capability were tested. Even a passing pair
    does NOT prove a model creatively good or a product production-ready.

    These dictionaries must come from an independent host verifier. This
    function cannot authenticate their provenance; the host must do that.
    """
    if not isinstance(control, dict) or not isinstance(candidate, dict):
        raise DiagnosticEvidenceError("Two host-attested trial records required")
    required = ("capability_id", "input_sha256", "contract_sha256", "body_revision")
    for field in required:
        a, b = control.get(field), candidate.get(field)
        if not isinstance(a, str) or not a or a != b:
            return {
                "attribution": "inconclusive",
                "evidence": "paired_input_or_contract_not_identical",
                "creative_quality": "not_assessed",
            }
    for record in (control, candidate):
        if (record.get("host_verified") is not True
                or record.get("kind") not in ("control", "model_candidate")
                or record.get("phase") not in _PHASES
                or record.get("outcome") not in ("verified", "failed", "unmeasured")):
            return {"attribution": "inconclusive",
                    "evidence": "trial_provenance_or_phase_unverified",
                    "creative_quality": "not_assessed"}
    if control["kind"] != "control" or candidate["kind"] != "model_candidate":
        return {"attribution": "inconclusive",
                "evidence": "independent_control_missing",
                "creative_quality": "not_assessed"}
    if control["phase"] == "execution" and control["outcome"] == "verified":
        if (candidate["phase"] in ("discovery", "contract", "planning")
                and candidate["outcome"] == "failed"):
            return {"attribution": "model_to_body_interface_observed",
                    "evidence": "same_body_contract_verified_control_model_action_rejected",
                    "creative_quality": "not_assessed"}
        if candidate["phase"] in ("execution", "verification") and candidate["outcome"] == "verified":
            return {"attribution": "technical_path_verified_for_pair",
                    "evidence": "model_selected_operation_and_control_physically_verified",
                    "creative_quality": "not_assessed"}
    if control["phase"] == "execution" and control["outcome"] == "failed":
        return {"attribution": "body_or_environment_blockage_observed",
                "evidence": "trusted_control_failed_before_model_comparison",
                "creative_quality": "not_assessed"}
    return {"attribution": "inconclusive",
            "evidence": "insufficient_isolation_of_model_and_body",
            "creative_quality": "not_assessed"}



def _safe_host_memory(host_capacity):
    memory = host_capacity.get("memory")
    if memory is None:
        return None
    if not isinstance(memory, dict):
        raise DiagnosticEvidenceError("Invalid physical memory observation")
    value = memory.get("available_bytes")
    if value is not None and (type(value) is not int or value < 0):
        raise DiagnosticEvidenceError("Invalid available host memory")
    return value


def universal_diagnostics(*, operation_records, job_records, session_records,
                          host_capacity, model_configured, model_id=None,
                          paired_trials=(), trace_evidence=None):
    """Bounded authenticated dashboard snapshot from actual host runtime state.

    Registry claims prove *discovery/installation*, not tool execution;
    finished job statuses are observed, not proof of creative quality.
    Sessions expose only counted decisions. Never show prompts or raw errors.
    """
    tools = _rows(operation_records, "capability registry")
    jobs = _rows(job_records, "durable job history")
    sessions = _rows(session_records, "creative sessions")
    pairs = _rows(paired_trials, "paired trial receipts")
    if trace_evidence is None:
        trace_evidence = {
            "recent_events": [], "observed_event_count": 0,
            "recent_window_hashes_valid": True,
            "externally_signed_or_globally_certified": False,
        }
    if not isinstance(trace_evidence, dict):
        raise DiagnosticEvidenceError("Host trace evidence is missing or untrusted")
    recent_events = _rows(trace_evidence.get("recent_events"), "actual stage receipts")
    _whole(trace_evidence.get("observed_event_count"), "durable trace")
    if (trace_evidence.get("recent_window_hashes_valid") is not True
            or trace_evidence.get("externally_signed_or_globally_certified") is not False):
        raise DiagnosticEvidenceError("Diagnostic trace custody cannot be verified")
    for event in recent_events:
        if (event.get("schema") != 1
                or event.get("model_causality_not_assigned") is not True
                or not isinstance(event.get("trace_id"), str)
                or not isinstance(event.get("capability_id"), str)
                or event.get("phase") not in _PHASES
                or event.get("outcome") not in (
                    "started", "observed", "verified", "failed",
                    "paused", "cancelled", "unmeasured", "unknown")
                or not isinstance(event.get("code"), str)):
            raise DiagnosticEvidenceError("Host trace contains ungrounded stage facts")
    if not isinstance(host_capacity, dict):
        raise DiagnosticEvidenceError("Live host capacity observation required")
    if type(model_configured) is not bool:
        raise DiagnosticEvidenceError("Model configuration state must be host observed")
    if model_id is not None and (
            not isinstance(model_id, str) or not 1 <= len(model_id) <= 128):
        raise DiagnosticEvidenceError("Invalid actual model identity")

    per_capability = {}
    for tool in tools:
        capability = tool.get("capability")
        if not isinstance(capability, str) or not capability or len(capability) > 128:
            raise DiagnosticEvidenceError("Registry contains unclassifiable capability")
        status = tool.get("status")
        if status not in ("installed", "needs_setup"):
            raise DiagnosticEvidenceError("Unexpected actual host tool status")
        key = tool.get("id")
        _name(key, "live operation")
        entry = per_capability.setdefault(capability, {
            "name": capability, "installed_operations": 0,
            "needs_setup_operations": 0,
            "physical_execution_verified": False,
            "creative_quality_verified": False,
            "operations_needing_setup": [],
        })
        entry["installed_operations" if status == "installed"
              else "needs_setup_operations"] += 1
        if status == "needs_setup":
            entry["operations_needing_setup"].append(key)
    catalog = sorted(per_capability.values(), key=lambda x: x["name"].casefold())
    for family in catalog:
        family["operations_needing_setup"].sort()

    job_states = Counter()
    for row in jobs:
        status = row.get("status")
        if status not in _STATES:
            raise DiagnosticEvidenceError("Unknown durable job state")
        count = row.get("count", 1)
        _whole(count, "durable job")
        job_states[status] += count
    session_states = Counter()
    decision_count = 0
    error_result_count = 0
    for row in sessions:
        status = row.get("status")
        if status not in _STATES:
            raise DiagnosticEvidenceError("Unknown actual creative session status")
        session_states[status] += 1
        decisions = row.get("events", [])
        if not isinstance(decisions, list) or len(decisions) > 128:
            raise DiagnosticEvidenceError("Unbounded creative decision history")
        for event in decisions:
            if not isinstance(event, dict):
                raise DiagnosticEvidenceError("Malformed creative decision receipt")
            decision_count += 1
            result = event.get("result")
            if isinstance(result, dict) and isinstance(result.get("error"), str):
                error_result_count += 1

    pair_evidence = []
    for pair in pairs:
        if set(pair) != {"control", "candidate"}:
            raise DiagnosticEvidenceError("Controlled pair must identify two independent runs")
        verdict = compare_controlled_trials(pair["control"], pair["candidate"])
        pair_evidence.append(verdict)
    paired_results = Counter(x["attribution"] for x in pair_evidence)

    all_installed = sum(x["installed_operations"] for x in catalog)
    setup_count = sum(x["needs_setup_operations"] for x in catalog)
    blocked = sum(job_states[x] for x in ("blocked", "failed"))
    unflagged_actions = decision_count - error_result_count
    diagnostics = []
    if not model_configured:
        diagnostics.append({
            "layer": "model", "code": "model_not_configured",
            "state": "setup_needed",
            "evidence": "host_creative_session_adapter_absent",
            "next_check": "Configure an authorized replaceable local model",
        })
    elif not pairs:
        diagnostics.append({
            "layer": "model", "code": "model_capability_unmeasured",
            "state": "unmeasured",
            "evidence": "no_paired_host_verified_model_body_trials",
            "next_check": "Run same-source verified BODY control and model candidate trials",
        })
    if setup_count:
        diagnostics.append({
            "layer": "body", "code": "registered_operations_need_setup",
            "state": "setup_needed",
            "evidence": "live_host_operation_catalog",
            "observed_count": setup_count,
            "next_check": "Inspect exact unavailable operations and their real dependencies",
        })
    if blocked:
        diagnostics.append({
            "layer": "execution", "code": "durable_jobs_blocked_or_failed",
            "state": "observed_blockage",
            "evidence": "real_durable_job_database",
            "observed_count": blocked,
            "next_check": "Inspect the affected job result and stage receipts",
        })
    if error_result_count:
        diagnostics.append({
            "layer": "interface", "code": "creative_session_actions_reported_errors",
            "state": "observed_blockage",
            "evidence": "stored_host_dispatched_session_results",
            "observed_count": error_result_count,
            "next_check": "Run independent control with identical source and contract before attributing fault",
        })
    for event in recent_events[:8]:
        if event["outcome"] == "failed":
            diagnostics.append({
                "layer": event["phase"],
                "code": event["code"],
                "state": "observed_blockage",
                "evidence": "host_durable_stage_receipt",
                "trace_id": event["trace_id"],
                "next_check": "Review the source-bound job stage and independent verifier",
            })
    for verdict in pair_evidence[:24]:
        if verdict["attribution"] not in ("technical_path_verified_for_pair", "inconclusive"):
            diagnostics.append({
                "layer": "comparison",
                "code": verdict["attribution"],
                "state": "observed_blockage",
                "evidence": verdict["evidence"],
                "next_check": "Inspect both independent host-run receipts",
            })
    # CPU/GPU statistics come directly from the existing host sensor; the
    # dashboard must never convert them to a guessed model creative rating.
    processor = host_capacity.get("cpu_logical_processors")
    if processor is not None and (type(processor) is not int or processor < 1):
        raise DiagnosticEvidenceError("Invalid actual CPU observation")
    disk = host_capacity.get("workspace_disk", {})
    if disk is not None and not isinstance(disk, dict):
        raise DiagnosticEvidenceError("Invalid real disk observation")
    free = disk.get("free_bytes") if isinstance(disk, dict) else None
    if free is not None and (type(free) is not int or free < 0):
        raise DiagnosticEvidenceError("Invalid actual free-disk reading")

    return {
        "schema": _SCHEMA,
        "kind": "zx7_universal_evidence_diagnostics",
        "truth_policy": {
            "no_model_creativity_score_without_independent_review": True,
            "installed_operations_are_not_verified_execution": True,
            "job_success_is_not_artistic_quality": True,
            "unpaired_failures_do_not_assign_model_or_body_blame": True,
        },
        "body": {
            "installed_operations": all_installed,
            "registered_operations_needing_setup": setup_count,
            "capability_families": len(catalog),
            "capabilities": catalog,
            "presence": "measured_live_registry",
            "independent_output_quality": "unmeasured",
        },
        "model": {
            "configured": model_configured,
            "identity": model_id if model_configured else None,
            "capability_assessment": ("host_paired_evidence_available" if pair_evidence
                                      else "unmeasured"),
            "independent_creativity": "unmeasured",
            "observed_creative_sessions": sum(session_states.values()),
            "observed_model_decisions": decision_count,
            "session_dispatch_error_results": error_result_count,
            "decisions_without_reported_error": unflagged_actions,
            "observed_session_window_limit": 64,
            "warning": "A successful decision is not proof of model intelligence or artistic merit",
        },
        "jobs": {
            "observed_count": sum(job_states.values()),
            "by_state": dict(sorted(job_states.items())),
            "physical_success_is_not_automatically_a_delivered_film": True,
        },
        "host": {
            "cpu_logical_processors": processor,
            "free_workspace_disk_bytes": free,
            "memory_available_bytes": _safe_host_memory(host_capacity),
            "capacity_is_not_model_capability": True,
            "source": "live_host_resource_sensor",
        },
        "controlled_comparisons": {
            "observed_pairs": len(pair_evidence),
            "results": dict(sorted(paired_results.items())),
            "causal_attribution_requires_same_input_and_contract": True,
            "each_pair_is_not_a_general_model_ranking": True,
        },
        "diagnostics": diagnostics[:40],
        "execution_traces": {
            "observed_event_count": trace_evidence["observed_event_count"],
            "recent_events": list(recent_events),
            "recent_window_hashes_valid": True,
            "independently_signed_or_globally_certified": False,
            "stage_evidence_never_assigns_model_causality": True,
        },
        "measurement_lanes": [
            {"name": "BODY discovery", "state": "observed",
             "proof": "live_registered_operations"},
            {"name": "BODY execution", "state": (
                "observed" if job_states else "unmeasured"),
             "proof": "actual_durable_jobs_and_categorical_stage_receipts"},
            {"name": "Model interface", "state": (
                "partially_observed" if decision_count else "unmeasured"),
             "proof": "host_stored_action_attempts_not_skill_certification"},
            {"name": "Paired causal isolation", "state": (
                "observed" if pairs else "unmeasured"),
             "proof": "same_contract_independent_host_controls_only"},
            {"name": "Independent creative quality", "state": "unmeasured",
             "proof": "professional_review_and_domain_acceptance_absent"},
        ],
        "unresolved": [
            "Per-operation execution health requires observed tool receipts",
            "Model vs BODY requires independent same-input controls",
            "Narrative and artistic quality require independent domain evaluation",
        ],
    }
