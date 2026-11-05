"""Actual execution-admission projection: verified host registry vs installed app.

No synthetic score can certify a renderer, native edit or model creativity.
"""
import tempfile
import unittest
from pathlib import Path

from studio_next.body_integration import body_catalog
from studio_next.body_service import LocalBodyCoordinator
from studio_next.universal_diagnostics import DiagnosticEvidenceError, universal_diagnostics


class GraphReachabilitySnapshotTests(unittest.TestCase):
    def test_live_coordinator_counts_only_readiness_not_artistic_quality(self):
        with tempfile.TemporaryDirectory() as temporary:
            host=LocalBodyCoordinator(Path(temporary)/"runtime")
            try:
                catalog=body_catalog(host.projects)
                admission=catalog.execution_admission()
                expected=sum(1 for x in admission.values()
                             if x["can_attempt_durable_graph"])
                snapshot=host.diagnostic_snapshot()
                body=snapshot["body"]
                self.assertEqual(body["durable_graph_admission_candidates"],expected)
                self.assertLessEqual(expected,body["installed_operations"])
                self.assertTrue(body["candidate_is_not_verified_execution"])
                self.assertEqual(body["independent_output_quality"],"unmeasured")
                self.assertEqual(snapshot["model"]["independent_creativity"],"unmeasured")
                self.assertEqual(body["installed_requiring_another_execution_lane"],
                                 body["installed_operations"]-expected)
            finally:
                host.close()

    def test_neither_untrusted_abi_claim_nor_fake_verified_media_is_accepted(self):
        def run(admission):
            return universal_diagnostics(
                operation_records=[{
                    "id":"future.control","capability":"sound",
                    "status":"installed",
                }],
                job_records=[],session_records=[],host_capacity={},
                model_configured=False,execution_admission=admission)
        minimum={
            "catalog_id":"future.control","capability":"sound",
            "can_attempt_durable_graph":False,
            "native_runner_registered":True,
            "trusted_material_adapter":False,
            "committed_execution_revision":False,
            "actually_executed_and_verified":False,
            "model_creative_quality_assessed":False,
        }
        report=run({"future.control":minimum})
        self.assertEqual(report["body"]["installed_requiring_another_execution_lane"],1)
        self.assertEqual(report["diagnostics"][1]["code"],
                         "installed_not_admissible_to_durable_graph")
        for forged in (
            {"can_attempt_durable_graph":True},
            {"actually_executed_and_verified":True},
            {"model_creative_quality_assessed":True},
            {"catalog_id":"future.mismatch"},
            {"committed_execution_revision":"true"},
        ):
            with self.subTest(forged=forged),self.assertRaises(DiagnosticEvidenceError):
                run({"future.control":{**minimum,**forged}})


if __name__=="__main__":
    unittest.main()
