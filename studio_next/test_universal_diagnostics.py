"""Adversarial universal dashboard facts and model/BODY isolation contracts.

All trial pairs here are explicit test fixtures, never real model evaluations.
"""
import unittest

from studio_next.universal_diagnostics import (
    DiagnosticEvidenceError, compare_controlled_trials, universal_diagnostics,
)


def paired():
    identity = {
        "capability_id": "camera.editor.native",
        "input_sha256": "a" * 64,
        "contract_sha256": "b" * 64,
        "body_revision": "pinned-source-1",
        "host_verified": True,
    }
    return (
        {**identity, "kind": "control", "phase": "execution",
         "outcome": "verified"},
        {**identity, "kind": "model_candidate", "phase": "contract",
         "outcome": "failed"},
    )


def measured(*, model=True, pairs=()):
    return universal_diagnostics(
        operation_records=[
            {"id": "body.draw", "capability": "design", "status": "installed"},
            {"id": "body.render", "capability": "film", "status": "installed"},
            {"id": "body.lens", "capability": "film", "status": "needs_setup"},
            {"id": "body.piano", "capability": "audio", "status": "needs_setup"},
        ],
        job_records=[
            {"status": "completed"}, {"status": "blocked"},
            {"status": "running"},
        ],
        session_records=[
            {"status": "blocked", "events": [
                {"result": {"error": "Some raw user secret in model response"}},
                {"result": {"confirmed": True}},
            ]}],
        host_capacity={"cpu_logical_processors": 8,
                       "workspace_disk": {"free_bytes": 15_000_000}},
        model_configured=model,
        model_id="local-brain-fixture-only" if model else None,
        paired_trials=pairs,
    )


class UniversalDiagnosticsTests(unittest.TestCase):
    def test_live_installed_is_not_falsely_reported_as_executed_or_creative(self):
        report = measured()
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["body"]["installed_operations"], 2)
        self.assertEqual(report["body"]["registered_operations_needing_setup"], 2)
        self.assertEqual(report["body"]["capability_families"], 3)
        self.assertEqual(report["body"]["independent_output_quality"], "unmeasured")
        self.assertEqual(report["model"]["independent_creativity"], "unmeasured")
        self.assertEqual(report["model"]["capability_assessment"], "unmeasured")
        self.assertEqual(report["model"]["observed_model_decisions"], 2)
        self.assertEqual(report["model"]["session_dispatch_error_results"], 1)
        self.assertEqual(report["jobs"]["by_state"]["blocked"], 1)
        self.assertEqual(report["host"]["cpu_logical_processors"], 8)
        text = str(report)
        self.assertNotIn("Some raw user secret", text)
        self.assertNotIn("confidence_score", text)
        self.assertTrue(report["truth_policy"][
            "unpaired_failures_do_not_assign_model_or_body_blame"])

    def test_missing_model_is_setup_not_low_ability(self):
        report = measured(model=False)
        self.assertFalse(report["model"]["configured"])
        self.assertIsNone(report["model"]["identity"])
        self.assertEqual(report["diagnostics"][0]["code"], "model_not_configured")
        self.assertNotIn("bad_model", str(report))

    def test_host_verified_control_separates_model_interface_from_body_failure(self):
        control, candidate = paired()
        finding = compare_controlled_trials(control, candidate)
        self.assertEqual(finding["attribution"], "model_to_body_interface_observed")
        self.assertEqual(finding["creative_quality"], "not_assessed")
        report = measured(pairs=[{"control": control, "candidate": candidate}])
        self.assertEqual(report["controlled_comparisons"]["observed_pairs"], 1)
        self.assertEqual(report["controlled_comparisons"]["results"][
            "model_to_body_interface_observed"], 1)
        broken = {**control, "outcome": "failed"}
        body = compare_controlled_trials(broken, candidate)
        self.assertEqual(body["attribution"], "body_or_environment_blockage_observed")

    def test_mismatched_or_unverified_pairs_never_blame_model(self):
        c, m = paired()
        for changed in [
            {**m, "input_sha256": "c" * 64},
            {**m, "contract_sha256": "d" * 64},
            {**m, "host_verified": False},
            {**m, "phase": "review", "outcome": "failed"},
        ]:
            with self.subTest(changed=changed):
                self.assertEqual(compare_controlled_trials(c, changed)["attribution"],
                                 "inconclusive")
        m = {**m, "phase": "execution", "outcome": "verified"}
        self.assertEqual(compare_controlled_trials(c, m)["attribution"],
                         "technical_path_verified_for_pair")
        self.assertEqual(compare_controlled_trials(c, m)["creative_quality"],
                         "not_assessed")

    def test_source_neutral_durable_job_stages_never_expose_graph_ids(self):
        graph_name = "secret_owner_film_scene_001"
        import hashlib
        job_name = "confidential_client_job"
        report = universal_diagnostics(
            operation_records=[],job_records=[{"status":"blocked"}],
            session_records=[],host_capacity={},
            model_configured=False,
            job_stage_evidence=[{
                "job_ref_sha256":hashlib.sha256(job_name.encode()).hexdigest(),
                "job_status":"blocked",
                "independently_observed_node_results":True,
                "nodes":[{"node_ref_sha256":hashlib.sha256(graph_name.encode()).hexdigest(),
                          "state":"failed","attempts":2,"observed_at":42.0}],
            }])
        observed=report["durable_job_stages"]
        self.assertEqual(observed["observed_job_count"],1)
        self.assertEqual(observed["jobs"][0]["recent_nodes"][0]["attempts"],2)
        self.assertEqual(observed["jobs"][0]["recent_nodes"][0]["state"],"failed")
        self.assertNotIn(graph_name,str(report))
        self.assertNotIn(job_name,str(report))
        self.assertTrue(observed["lineage_may_span_original_project_revisions"])
        with self.assertRaises(DiagnosticEvidenceError):
            universal_diagnostics(operation_records=[],job_records=[],
                session_records=[],host_capacity={},model_configured=False,
                job_stage_evidence=[{"job_ref_sha256":"wrong","job_status":"blocked",
                                     "independently_observed_node_results":True,
                                     "nodes":[]}])

    def test_adversarial_registry_and_status_fields_fail_closed(self):
        with self.assertRaises(DiagnosticEvidenceError):
            universal_diagnostics(operation_records=[{
                "id": "test", "capability": "future capability",
                "status": "random green power"}],
                job_records=[], session_records=[], host_capacity={},
                model_configured=False)
        for invalid in (-1, "8", True, float("nan")):
            with self.subTest(invalid=invalid), self.assertRaises(
                    DiagnosticEvidenceError):
                universal_diagnostics(operation_records=[],
                    job_records=[], session_records=[],
                    host_capacity={"cpu_logical_processors": invalid},
                    model_configured=False)
        with self.assertRaises(DiagnosticEvidenceError):
            universal_diagnostics(operation_records=[],job_records=[],
                session_records=[{"status": "running", "events": [{}] * 129}],
                host_capacity={},model_configured=True)
        with self.assertRaises(DiagnosticEvidenceError):
            universal_diagnostics(operation_records=[],job_records=[],
                session_records=[],host_capacity={},model_configured="True")


if __name__ == "__main__":
    unittest.main()
