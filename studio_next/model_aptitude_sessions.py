"""Operator-triggered, durable LOCAL model-to-BODY aptitude checks.

No background network API, no model execution on dashboard GET, no model
rights to call BODY tools. Each user-approved audition runs up to 3 bounded
read-only *selection* probes using actually installed host-granted schemas.
A process crash marks the audition interrupted; inference is NEVER replayed
automatically. Measured protocol compatibility is NOT creativity.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from .body_capabilities import installed_body_capability_fabric
from .diagnostic_trace import append_host_event
from .model_tool_audition import (
    ModelToolAuditionError, constrained_local_audition_adapter,
    run_model_tool_audition, summarize_model_tool_auditions,
)


class ModelAptitudeSessions:
    """One local-model calibration at a time with an observable durable ledger."""

    def __init__(self, coordinator, model, *, max_cases=3, cooldown_seconds=600):
        if type(max_cases) is not int or not 1 <= max_cases <= 8:
            raise ValueError("Finite operator-approved model diagnostic case budget required")
        if type(cooldown_seconds) not in (int, float) or not 30 <= cooldown_seconds <= 7200:
            raise ValueError("Finite diagnostic resource cooldown required")
        self.coordinator = coordinator
        self.model = model
        self.max_cases = max_cases
        self.cooldown_seconds = cooldown_seconds
        self._executor = ThreadPoolExecutor(max_workers=1,thread_name_prefix="zx7-brain-diagnostic")
        self._lock = threading.Lock()
        self._closed = False
        with coordinator._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS model_diagnostic_runs(
                id TEXT PRIMARY KEY, created REAL NOT NULL,
                status TEXT NOT NULL, evidence TEXT NOT NULL)""")
            # A crash leaves the test's tool-free inference unfinished.
            # Calling the model again would waste cost and blur its provenance.
            db.execute("UPDATE model_diagnostic_runs SET status='interrupted' "
                       "WHERE status IN ('queued','running')")

    @staticmethod
    def _baseline():
        path = Path(__file__).resolve().parent/"fixtures/model_tool_baseline_v1.json"
        raw = path.read_bytes()
        if len(raw) > 16384:
            raise ModelToolAuditionError("Packaged baseline is unbounded")
        data = json.loads(raw)
        if (not isinstance(data, dict) or data.get("schema") != 1
                or data.get("kind") != "operator-owned-model-to-body-audition-cases"
                or not isinstance(data.get("cases"), list)
                or not 1 <= len(data["cases"]) <= 8):
            raise ModelToolAuditionError("Installed host-owned aptitude baseline missing")
        return hashlib.sha256(raw).hexdigest(), data["cases"]

    def latest(self):
        with self.coordinator._connect() as db:
            row = db.execute(
                "SELECT id,created,status,evidence FROM model_diagnostic_runs "
                "ORDER BY created DESC,id DESC LIMIT 1").fetchone()
        if row is None:
            return {"status":"unmeasured", "case_count":0,
                    "creativity_not_assessed":True,
                    "body_execution_not_tested":True}
        return self._summary_row(row)

    @staticmethod
    def _summary_row(row):
        identity,created,status,raw=row
        evidence=json.loads(raw)
        if not isinstance(evidence,dict):
            raise ValueError("Stored model diagnostic record is malformed")
        return {
            "run_id":identity, "observed_at":created, "status":status,
            "cases_recorded":len(evidence.get("cases",[])),
            "results":evidence.get("cases",[]),
            "summary":evidence.get("summary"),
            "model_label":evidence.get("model_label"),
            "baseline_sha256":evidence.get("baseline_sha256"),
            "catalog_revision":evidence.get("catalog_revision"),
            "host_failure_type":evidence.get("host_failure_type"),
            "model_weights_physically_attested":False,
            "body_execution_not_tested":True,
            "creativity_not_assessed":True,
            "no_tool_mutations_executed":True,
        }

    def inspect(self, identity):
        if not isinstance(identity,str) or len(identity)!=32 or any(
                ch not in "0123456789abcdef" for ch in identity):
            raise ValueError("Exact model diagnostic receipt identity required")
        with self.coordinator._connect() as db:
            row=db.execute("SELECT id,created,status,evidence "
                           "FROM model_diagnostic_runs WHERE id=?",(identity,)).fetchone()
        if row is None:
            raise ValueError("Unknown calibrated model diagnostic")
        return self._summary_row(row)

    def request(self):
        """Explicit local operator action; never a scheduled measurement."""
        # For security and fairness the service only launches the already
        # trusted loopback local adapter, never a third-party hosted provider.
        from .providers import LocalCreativeModel
        if not isinstance(self.model,LocalCreativeModel):
            raise ValueError("A verified local replaceable model adapter is needed")
        with self._lock:
            if self._closed:
                raise RuntimeError("Model diagnostics service is closing")
            sha,cases=self._baseline()
            if len(cases)>self.max_cases:
                raise ModelToolAuditionError("Host-owned case budget exceeded")
            # Fail before inference if a required BODY tool was not actually
            # installed, granted or discoverable in the current runtime.
            fabric=installed_body_capability_fabric(self.coordinator.projects)
            for case in cases:
                for operation in case["offered_operation_ids"]:
                    fabric.resolve(operation,revision=fabric.revision)
            with self.coordinator._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                busy=db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running') "
                                "LIMIT 1").fetchone()
                if busy:
                    raise ValueError("A production job has reserved host compute")
                row=db.execute(
                    "SELECT id,created,status FROM model_diagnostic_runs "
                    "ORDER BY created DESC LIMIT 1").fetchone()
                if row is not None:
                    if row[2] in ("queued","running"):
                        return {"run_id":row[0],"status":row[2],
                                "reused_existing_active_run":True}
                    if time.time()-row[1]<self.cooldown_seconds:
                        raise ValueError("Real model calibration is under host cooldown")
                identity=uuid.uuid4().hex
                evidence={"cases":[],"model_label":self.model.settings.model_id,
                          "baseline_sha256":sha,"catalog_revision":fabric.revision}
                db.execute("INSERT INTO model_diagnostic_runs VALUES(?,?,?,?)",
                           (identity,time.time(),"queued",
                            json.dumps(evidence,sort_keys=True)))
                append_host_event(db,trace_id=identity,
                    capability_id="zx7.model_tool_aptitude",phase="contract",
                    outcome="started",code="operator_approved_model_test_started")
            try:
                self._executor.submit(self._run,identity,sha,cases,fabric)
            except BaseException:
                with self.coordinator._connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute("UPDATE model_diagnostic_runs SET status='interrupted' "
                               "WHERE id=?",(identity,))
                raise
            return {"run_id":identity,"status":"queued",
                    "no_background_tool_execution":True}

    def _persist(self, identity, status, evidence):
        with self.coordinator._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE model_diagnostic_runs SET status=?,evidence=? WHERE id=?",
                (status,json.dumps(evidence,sort_keys=True,allow_nan=False),identity))

    def _run(self,identity,baseline_sha,cases,fabric):
        evidence={"cases":[],"model_label":self.model.settings.model_id,
                  "baseline_sha256":baseline_sha,"catalog_revision":fabric.revision}
        status="failed_to_measure"
        started=time.monotonic()
        try:
            model=constrained_local_audition_adapter(self.model)
            self._persist(identity,"running",evidence)
            for case in cases:
                report=run_model_tool_audition(model,fabric,case)
                evidence["cases"].append({
                    "case_id":report["case_id"],
                    "result_code":report["result_code"],
                    "model_selected_expected_tool":report["model_selected_expected_tool"],
                    "selected_tool_schema_admissible":report["selected_tool_schema_admissible"],
                    "model_to_tool_contract_passed":report["model_to_tool_contract_passed"],
                    "elapsed_ms_measured":report["elapsed_ms_measured"],
                })
                self._persist(identity,"running",evidence)
            evidence["summary"]=summarize_model_tool_auditions([
                # The summary counts *actual* non-mutating inference results.
                # It does not turn this into a creative or production score.
                {**item,"kind":"model_to_body_contract_audition",
                 "model_label":evidence["model_label"],
                 "catalog_revision":fabric.revision}
                for item in evidence["cases"]])
            status="completed_measured_not_creative_certification"
        except Exception as exc:
            evidence["host_failure_type"]=type(exc).__name__
        finally:
            evidence["total_wall_ms"]=round((time.monotonic()-started)*1000,3)
            self._persist(identity,status,evidence)
            with self.coordinator._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                append_host_event(db,trace_id=identity,
                    capability_id="zx7.model_tool_aptitude",phase="contract",
                    outcome="observed" if status.startswith("completed") else "failed",
                    code=("model_tool_contract_cases_recorded" if status.startswith("completed")
                          else "model_diagnostic_runtime_blocked"),
                    elapsed_ms=evidence["total_wall_ms"])

    def close(self):
        with self._lock:
            self._closed=True
        # Never silently cancel an in-flight expensive model inference; it
        # completes its current bounded local request. Next startup marks
        # interrupted trials without replaying any model decision.
        self._executor.shutdown(wait=True,cancel_futures=True)
