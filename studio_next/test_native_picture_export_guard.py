"""Model-independent native export safety test, not creative-quality evidence."""
import json
from types import SimpleNamespace
import unittest

from studio_next.native_creative_control import (
    NativeCreativeControl, _native_timeline_picture_presence_from_text,
)
from studio_next.test_native_creative_control import ScriptedModel, decision


class TimelineExportSession:
    def __init__(self, clips):
        self.clips = clips
        self.calls = []
        self.tools = [
            SimpleNamespace(name="get_project", description="Real project state",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="get_timeline", description="Actual clips",
                            input_schema={"type": "object", "properties": {
                                "includeClips": {"type": "boolean"},
                                "limit": {"type": "integer"}}}),
            SimpleNamespace(name="export_timeline", description="Export actual edit",
                            input_schema={"type": "object", "properties": {}}),
        ]

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, tool, args):
        self.calls.append((tool, args))
        if tool == "get_project":
            value = {"mcp": {"hasProject": True}, "project": {"id": "valid"}}
        elif tool == "get_timeline":
            value = {"clips": self.clips, "clipLimitApplied": False}
        elif tool == "export_timeline":
            raise AssertionError("Premature native export was not permitted")
        else:
            raise AssertionError("Unexpected tool")
        return SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps(value))])


class NativePictureExportGuardTests(unittest.IsolatedAsyncioTestCase):
    def test_native_timeline_source_fact_never_invents_picture(self):
        def texts(body):
            return [json.dumps(body)]
        self.assertEqual(_native_timeline_picture_presence_from_text(
            texts({"clips": [], "clipLimitApplied": False})), "absent")
        self.assertEqual(_native_timeline_picture_presence_from_text(
            texts({"clips": [{"type": "text", "assetId": None}],
                   "clipLimitApplied": False})), "absent")
        self.assertEqual(_native_timeline_picture_presence_from_text(
            texts({"clips": [{"type": "video", "assetId": "original-video"}],
                   "clipLimitApplied": False})), "present")
        self.assertEqual(_native_timeline_picture_presence_from_text(
            texts({"clips": [], "clipLimitApplied": True})), "unknown")
        self.assertEqual(_native_timeline_picture_presence_from_text(
            texts({"clips": [{"type": "video", "assetId": ""}],
                   "clipLimitApplied": False})), "absent")
        self.assertEqual(_native_timeline_picture_presence_from_text(
            texts({"clips": "untrusted", "clipLimitApplied": False})), "unknown")

    async def test_real_native_empty_timeline_rejects_export_without_dispatch(self):
        session = TimelineExportSession([])
        model = ScriptedModel([
            decision("search", query="export timeline"),
            decision("invoke", tool="export_timeline", inputs={}),
            decision("finish", summary="No unauthorized native export occurred"),
        ])
        outcome = await NativeCreativeControl(
            session, model, max_turns=3, catalog_mode="indexed",
            host_tool_access={"get_project": "read", "get_timeline": "read",
                              "export_timeline": "write"},
            host_preconditions={"export_timeline":
                                ["project_open", "timeline_picture_present"]},
        ).run("Edit a camera film")
        self.assertNotIn("export_timeline", [name for name, _ in session.calls])
        self.assertEqual(session.calls[-1], (
            "get_timeline", {"includeClips": True, "limit": 1000}))
        rejected = [e for e in outcome["events"]
                    if e["kind"] == "model_action_rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["validation_keyword"], "host_precondition")
        self.assertEqual(rejected[0]["schema_location"], "timeline_picture_present")
        self.assertFalse(outcome["native_editing_capability_complete"])


if __name__ == "__main__":
    unittest.main()
