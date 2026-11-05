"""Read-only cross-domain model-to-tool contract aptitude checks.

These scripted adapters are *test doubles*. None of the tests establish
LLM quality, model weights, native execution, or creative competence.
"""
from types import SimpleNamespace
import unittest

from studio_next.capability_fabric import CapabilityFabric
from studio_next.model_tool_audition import (
    ModelToolAuditionError, run_model_tool_audition,
    summarize_model_tool_auditions,
)


def real_shape_fabric():
    return CapabilityFabric({"future": ([
        {"name": "generate_procedural_audio",
         "description": "Create procedural audio with explicit frequency and sample rate",
         "inputSchema": {"type": "object",
                         "required": ["frequency"],
                         "properties": {"frequency": {"type": "number", "minimum": 1}}}},
        {"name": "read_existing_audio",
         "description": "Report original audio sample metadata",
         "inputSchema": {"type": "object", "properties": {"assetId": {"type": "string"}}}},
    ], {"generate_procedural_audio": "write",
        "read_existing_audio": "read"})})


class ScriptedProbeModel:
    settings=SimpleNamespace(model_id="scripted-fixture-not-real-brain")

    def __init__(self,response):
        self.response=response
        self.calls=[]

    def decide(self,context):
        self.calls.append(context)
        if isinstance(self.response,Exception):
            raise self.response
        return self.response


def case():
    return {
        "case_id":"operator_audio_contract",
        "task":"Generate an actual procedural tone with a numeric frequency.",
        "offered_operation_ids":[
            "future/read_existing_audio","future/generate_procedural_audio"],
        "expected_operation_id":"future/generate_procedural_audio",
    }


class ModelToBodyAptitudeProbeTests(unittest.TestCase):
    def test_expected_tool_and_schema_can_be_measured_without_body_dispatch(self):
        model=ScriptedProbeModel({
            "operation_id":"future/generate_procedural_audio",
            "inputs":{"frequency":440}})
        response=run_model_tool_audition(model,real_shape_fabric(),case())
        self.assertEqual(len(model.calls),1)
        self.assertTrue(response["model_to_tool_contract_passed"])
        self.assertTrue(response["selected_tool_schema_admissible"])
        self.assertFalse(response["body_tool_was_executed"])
        self.assertFalse(response["model_weights_physically_attested"])
        self.assertFalse(response["creative_quality_reviewed"])
        self.assertEqual(len(model.calls[0]["actual_granted_tool_contracts"]),2)
        self.assertNotIn("expected_operation_id",model.calls[0])
        summary=summarize_model_tool_auditions([response])
        self.assertEqual(summary["matching_tool_and_schema_count"],1)
        self.assertTrue(summary["no_global_power_score"])

    def test_separately_identifies_wrong_granted_tool_and_invalid_schema(self):
        cases=[
            ({"operation_id":"future/read_existing_audio","inputs":{}},
             "model_selected_other_granted_tool"),
            ({"operation_id":"future/generate_procedural_audio","inputs":{}},
             "model_tool_input_schema_rejected"),
            ({"operation_id":"imagined/paid_generator","inputs":{}},
             "model_selected_ungranted_operation"),
            ({"operation_id":"future/generate_procedural_audio","inputs":{"frequency":0}},
             "model_tool_input_schema_rejected"),
        ]
        for payload,code in cases:
            with self.subTest(code=code):
                report=run_model_tool_audition(
                    ScriptedProbeModel(payload),real_shape_fabric(),case())
                self.assertFalse(report["model_to_tool_contract_passed"])
                self.assertEqual(report["result_code"],code)

    def test_failed_model_inference_does_not_blame_body_or_fake_score(self):
        failing=ScriptedProbeModel(ConnectionError("private provider message"))
        report=run_model_tool_audition(failing,real_shape_fabric(),case())
        self.assertFalse(report["model_to_tool_contract_passed"])
        self.assertIn("ConnectionError",report["result_code"])
        self.assertNotIn("private provider",str(report))
        self.assertFalse(report["body_tool_was_executed"])

    def test_untrusted_or_unregistered_case_fails_before_model_inference(self):
        fabric=real_shape_fabric()
        cases=[
            {**case(),"offered_operation_ids":["future/missing","future/read_existing_audio"]},
            {**case(),"task":""},
            {**case(),"offered_operation_ids":["future/read_existing_audio"]},
            {**case(),"case_id":"/private/path"},
        ]
        for sample in cases:
            model=ScriptedProbeModel({})
            with self.subTest(sample=sample),self.assertRaises(ModelToolAuditionError):
                run_model_tool_audition(model,fabric,sample)
            self.assertFalse(model.calls)


if __name__=="__main__":
    unittest.main()
