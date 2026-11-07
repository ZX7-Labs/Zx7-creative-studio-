"""Adversarial model/BODY execution-lane reachability tests.

A tool being *installed and granted* never means the deterministic durable
film graph can safely execute it. Native stateful editing is its own lane.
Scripted connectors below are TEST FIXTURES, not physical video editor proofs.
"""
import tempfile
import unittest

from studio_next.body_affordances import BodyAffordanceSurface
from studio_next.body_integration import body_catalog
from studio_next.body_service import LocalBodyCoordinator
from studio_next.body_signal import BodyAuthority, BodyCommandRejected, LiveBodySignal
from studio_next.contracts import ToolSpec
from studio_next.registry import ToolCatalog
from studio_next.test_body_signal import authored_film


class SchemaOnlyNativeTestEditor:
    allowed_tools = {"get_project": "read", "update_text_clip": "write"}

    def __init__(self):
        self.calls=[]

    def list_tools(self):
        return [
            {"name":"get_project", "description":"Read current native project",
             "inputSchema":{"type":"object","properties":{}}},
            {"name":"update_text_clip","description":"Modify native text overlay",
             "inputSchema":{"type":"object",
                            "required":["clipId","text"],
                            "properties":{"clipId":{"type":"string"},
                                          "text":{"type":"string"}}}},
        ]

    def call(self,name,arguments,*,allowed_access):
        self.calls.append((name,arguments,allowed_access))
        return {"content":[{"type":"text","text":"fixture only"}],
                "isError":False}


class ActualExecutionLaneAdmissionTests(unittest.TestCase):
    def test_mature_native_editor_presence_not_falsely_claimed_as_durable_graph(self):
        with tempfile.TemporaryDirectory() as workspace:
            editor=SchemaOnlyNativeTestEditor()
            catalog=body_catalog(workspace,editor_client=editor)
            states=catalog.execution_admission()
            self.assertIn("body.editor.update_text_clip",states)
            native=states["body.editor.update_text_clip"]
            self.assertTrue(native["native_runner_registered"])
            self.assertFalse(native["can_attempt_durable_graph"])
            self.assertIn("no_trusted_material_fingerprint",native["blocked_by"])
            self.assertIn("no_committed_executor_revision",native["blocked_by"])
            self.assertFalse(native["actually_executed_and_verified"])
            sensor=BodyAffordanceSurface(catalog)
            available=sensor.discover(allowed_access={"read","write"},limit=40)
            self.assertNotIn("body.editor.update_text_clip",
                             {row["tool_id"] for row in available["affordances"]})
            described=sensor.describe("body.editor.update_text_clip",
                                      allowed_access={"read","write"})
            self.assertEqual(described["status"],"requires_execution_adapter")
            self.assertIsNone(described["input_schema"])
            with self.assertRaises(RuntimeError):
                sensor.preflight("body.editor.update_text_clip",{
                    "arguments":{"clipId":"native","text":"hello"}},
                    allowed_access={"read","write"})
            self.assertEqual(editor.calls,[])

    def test_real_host_catalog_trusted_durable_tools_remain_discoverable(self):
        with tempfile.TemporaryDirectory() as workspace:
            catalog=body_catalog(workspace)
            flags=catalog.execution_admission()
            for operation in ("body.timecode_format","body.resolve_asset"):
                self.assertTrue(flags[operation]["can_attempt_durable_graph"])
                self.assertTrue(flags[operation]["trusted_material_adapter"])
                self.assertTrue(flags[operation]["committed_execution_revision"])
            sensor=BodyAffordanceSurface(catalog)
            self.assertEqual(sensor.describe("body.timecode_format")["status"],
                             "ready_to_preflight")

    def test_model_graph_submit_rejects_native_session_only_before_dispatch(self):
        with tempfile.TemporaryDirectory() as workspace:
            coordinator=LocalBodyCoordinator(workspace,execute=lambda ir,root:{
                "status":"all_tool_results_verified"})
            editor=SchemaOnlyNativeTestEditor()
            try:
                signal=LiveBodySignal(coordinator,authority=BodyAuthority(
                    workspace_ids=frozenset({"scoped-film"}),
                    operations=frozenset({"submit"}),
                    tool_access=frozenset({"read","write"})),
                    catalog_factory=lambda root:body_catalog(root,editor_client=editor))
                original=authored_film()
                original["tool_graph"][0]["tool_id"]="body.editor.update_text_clip"
                original["tool_graph"][0]["inputs"]={
                    "arguments":{"clipId":"clip","text":"artist-authored"}}
                with self.assertRaises(BodyCommandRejected):
                    signal.command("submit",{
                        "workspace_id":"scoped-film","film_ir":original})
                self.assertEqual(coordinator.list_jobs()["jobs"],[])
                self.assertEqual(editor.calls,[])
            finally:
                coordinator.close()

    def test_future_specialist_registered_without_verifier_is_not_a_false_ready_signal(self):
        registry=ToolCatalog()
        registry.register(ToolSpec("future.simulate","simulations",
            "Internally implemented specialist domain","write",
            operation_schema={"type":"object","required":[],"properties":{}}),
            lambda x:{"claimed_success":True},idempotent=False)
        row=registry.execution_admission()["future.simulate"]
        self.assertFalse(row["can_attempt_durable_graph"])
        self.assertFalse(row["model_creative_quality_assessed"])
        self.assertNotIn("future.simulate",
            {x["tool_id"] for x in BodyAffordanceSurface(
                registry).discover(allowed_access={"read","write"})["affordances"]})


if __name__=="__main__":
    unittest.main()
