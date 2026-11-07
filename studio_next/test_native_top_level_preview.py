"""Source-backed Velorn top-level preview envelope admission, not creative proof.

The exact pinned electron/mcpServer.js createTimeline handler returns
{previewOnly:true, action:'create_timeline', plan:{...},
 suggestedApplyCall:{tool:'create_timeline',arguments:{previewOnly:false,...}}}
with NO success or result. These are protocol fixtures; they don't execute
the real native editor or prove physical project art.
"""
import json
from types import SimpleNamespace
import unittest

from studio_next.native_creative_audit import audit_native_journal
from studio_next.native_creative_control import NativeCreativeControl
from studio_next.test_native_creative_control import (
    FakeSession, ScriptedModel, decision,
)


def direct_native_preview():
    return {
        "previewOnly":True,
        "action":"create_timeline",
        "plan":{"name":"Independent scene design","width":640,"fps":24},
        "suggestedApplyCall":{
            "tool":"create_timeline",
            "arguments":{"name":"Independent scene design",
                         "previewOnly":False,"width":640,"fps":24},
        },
    }


class VelornDirectPlanPreviewFixture(FakeSession):
    def __init__(self, receipt):
        super().__init__()
        self.receipt=receipt
        self.tools.append(SimpleNamespace(
            name="create_timeline",
            description="Preview or create a native editable sequence",
            input_schema={"type":"object",
                          "properties":{
                              "name":{"type":"string"},
                              "previewOnly":{"type":"boolean"}}}))

    async def call_tool(self,name,arguments):
        if name=="create_timeline":
            self.calls.append((name,arguments))
            return SimpleNamespace(is_error=False,content=[SimpleNamespace(
                type="text",text=json.dumps(self.receipt))])
        return await super().call_tool(name,arguments)


def real_grants(session):
    return {tool.name:("write" if tool.name=="create_timeline" else "read")
            for tool in session.tools}


class ActualVelornPreviewContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_source_native_preview_is_not_an_applied_edit_or_uncertain_failure(self):
        session=VelornDirectPlanPreviewFixture(direct_native_preview())
        model=ScriptedModel([
            decision("invoke",tool="create_timeline",
                     inputs={"name":"Independent scene design"}),
            decision("finish",summary="Only a non-mutating native plan exists"),
        ])
        state=await NativeCreativeControl(
            session,model,max_turns=2,
            host_tool_access=real_grants(session)).run("Original film design")
        self.assertEqual(state["status"],"model_finished_unverified")
        self.assertEqual([x["kind"] for x in state["events"]].count(
            "native_tool_preview"),1)
        self.assertNotIn("native_tool_result",
                         [x["kind"] for x in state["events"]])
        self.assertEqual([x[0] for x in session.calls],["create_timeline"])
        self.assertTrue(model.observed[1]["last_native_preview_feedback"][
            "host_reported_preview_only"])
        self.assertFalse(state["native_editing_capability_complete"])
        audit=audit_native_journal(state["events"],
                                  host_tool_access=real_grants(session))
        self.assertEqual(audit["recorded_native_write_result_count"],0)
        self.assertFalse(audit["human_or_artistic_quality_approved"])

    async def test_forged_top_level_preview_never_becomes_an_acknowledged_mutation(self):
        base=direct_native_preview()
        variants=[
            {**base,"success":True},
            {**base,"action":"wrong_native_tool"},
            {**base,"suggestedApplyCall":{
                "tool":"wrong_native_tool",
                "arguments":{"previewOnly":False}}},
            {**base,"suggestedApplyCall":{
                "tool":"create_timeline",
                "arguments":{"previewOnly":True}}},
            {key:value for key,value in base.items() if key!="plan"},
        ]
        for receipt in variants:
            with self.subTest(receipt=receipt):
                session=VelornDirectPlanPreviewFixture(receipt)
                model=ScriptedModel([
                    decision("invoke",tool="create_timeline",
                             inputs={"name":"Independent scene design"}),
                ])
                state=await NativeCreativeControl(session,model,max_turns=1,
                    host_tool_access=real_grants(session)).run("Original film")
                self.assertEqual(state["status"],
                                 "native_error_requires_state_reconciliation")
                kinds=[x["kind"] for x in state["events"]]
                self.assertIn("native_tool_uncertain_outcome",kinds)
                self.assertNotIn("native_tool_result",kinds)
                self.assertNotIn("native_tool_preview",kinds)
                self.assertEqual(len(session.calls),1)
                independent=audit_native_journal(
                    state["events"],host_tool_access=real_grants(session))
                self.assertEqual(independent["recorded_native_write_result_count"],0)


if __name__=="__main__":
    unittest.main()
