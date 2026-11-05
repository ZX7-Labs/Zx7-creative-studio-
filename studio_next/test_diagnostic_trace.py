"""Host evidence trace proof and tamper/error path tests.

No synthetic model decisions or simulated films are presented as capability.
"""
import json
import sqlite3
import tempfile
import time
from pathlib import Path
import unittest

from studio_next.diagnostic_trace import (
    DiagnosticTraceError, append_host_event, initialize_trace_store,
    read_recent_host_events,
)
from studio_next.body_service import LocalBodyCoordinator


class DiagnosticTraceTests(unittest.TestCase):
    def test_atomic_chain_catches_tampering_and_exposes_no_private_values(self):
        db = sqlite3.connect(":memory:", isolation_level=None)
        try:
            initialize_trace_store(db)
            db.execute("BEGIN IMMEDIATE")
            one = append_host_event(db,trace_id="run_1",
                                    capability_id="future.voice.synthesis",
                                    phase="execution",outcome="started",
                                    code="real_engine_started")
            two = append_host_event(db,trace_id="run_1",
                                    capability_id="future.voice.synthesis",
                                    phase="verification",outcome="failed",
                                    code="decoded_output_failed",elapsed_ms=125.12)
            db.execute("COMMIT")
            self.assertEqual(len(one),64)
            self.assertNotEqual(one,two)
            data=read_recent_host_events(db)
            self.assertTrue(data["recent_window_hashes_valid"])
            self.assertFalse(data["externally_signed_or_globally_certified"])
            self.assertEqual(data["recent_events"][0]["phase"],"verification")
            self.assertEqual(data["recent_events"][1]["phase"],"execution")
            self.assertTrue(data["recent_events"][0]["model_causality_not_assigned"])
            db.execute("UPDATE diagnostic_trace_events SET record_json=? WHERE id=2",
                       (json.dumps({"phase": "verification", "fake_score": 100}),))
            with self.assertRaises(DiagnosticTraceError):
                read_recent_host_events(db)
        finally:
            db.close()

    def test_fail_closed_on_invalid_codes_and_nontransactional_fabricated_events(self):
        db=sqlite3.connect(":memory:",isolation_level=None)
        try:
            initialize_trace_store(db)
            with self.assertRaises(DiagnosticTraceError):
                append_host_event(db,trace_id="t",capability_id="film",
                    phase="execution",outcome="verified",code="not_committed")
            db.execute("BEGIN IMMEDIATE")
            for values in (
                {"trace_id":"/tmp/secret"},
                {"code":"Error private original footage"},
                {"code":"error_/tmp/private"},
                {"phase":"invented_critical_stage"},
                {"outcome":"artistically_brilliant"},
                {"elapsed_ms":float("nan")},
            ):
                original={
                    "trace_id":"run_2", "capability_id":"future.domains",
                    "phase":"execution", "outcome":"failed", "code":"unverified_result",
                }
                original.update(values)
                with self.subTest(values=values),self.assertRaises(DiagnosticTraceError):
                    append_host_event(db,**original)
            db.execute("ROLLBACK")
        finally:
            db.close()

    def test_recent_bounded_page_verifies_adjacent_chain_linkage(self):
        db=sqlite3.connect(":memory:",isolation_level=None)
        try:
            initialize_trace_store(db)
            db.execute("BEGIN IMMEDIATE")
            for i in range(25):
                append_host_event(db,trace_id=f"session_{i}",
                    capability_id="future.3d",phase="discovery",
                    outcome="observed",code="tool_list_observed",
                    observed_at=i+1)
            db.execute("COMMIT")
            data=read_recent_host_events(db,limit=3)
            self.assertEqual(data["observed_event_count"],25)
            self.assertEqual(len(data["recent_events"]),3)
            self.assertEqual(data["recent_events"][0]["trace_id"],"session_24")
            db.execute("UPDATE diagnostic_trace_events SET prior_sha256=? WHERE id=24",
                       ("0"*64,))
            with self.assertRaises(DiagnosticTraceError):
                read_recent_host_events(db,limit=3)
        finally:
            db.close()

    def test_real_coordinator_records_stub_as_observed_not_physical_quality(self):
        # This is explicitly a bounded transport fixture, never a live model,
        # full-body rendering or an independently verified movie.
        with tempfile.TemporaryDirectory() as temporary:
            host=LocalBodyCoordinator(
                Path(temporary)/"host",
                execute=lambda plan,root:{"status":"all_tool_results_verified"})
            try:
                identity=host.submit({"tool_graph":[]},workspace_id="fixture")["job_id"]
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    if host.inspect(identity)["status"] not in ("queued","running"):
                        break
                    time.sleep(.02)
                report=host.diagnostic_snapshot()
                history=report["execution_traces"]
                self.assertEqual(history["observed_event_count"],2)
                self.assertTrue(history["recent_window_hashes_valid"])
                self.assertEqual(history["recent_events"][0]["code"],
                                 "custom_executor_completion_unverified")
                self.assertEqual(history["recent_events"][0]["outcome"],"observed")
                self.assertEqual(report["model"]["independent_creativity"],"unmeasured")
                self.assertEqual(report["controlled_comparisons"]["observed_pairs"],0)
            finally:
                host.close()


if __name__ == "__main__":
    unittest.main()
