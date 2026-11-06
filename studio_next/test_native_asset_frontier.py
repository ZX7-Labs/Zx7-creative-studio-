"""Model-neutral trusted fact frontier: exact native source tools, no edit scripts.

The test stub chooses actions, so this proves protocol/safety only. The real
Qwen3.5-2B trial #41186113669 showed 40 authored decisions but never searched
for import, despite source assets in its brief and get_assets count=0.
"""
import copy
import json
import unittest
from types import SimpleNamespace

from studio_next.native_creative_control import NativeCreativeControl
from studio_next.native_state_evidence import _PINNED_NO_IMAGE_SEQUENCE_ERROR
from studio_next.native_creative_audit import audit_native_journal, NativeJournalError
from studio_next.test_native_creative_control import ScriptedModel, decision
from studio_next.test_native_asset_identity import LiveCatalogSession
from studio_next.test_native_state_evidence import ActualNativeObservationSession


class HostObservedEmptyAssetSession(LiveCatalogSession):
    def __init__(self):
        super().__init__([])
        self.tools.extend([
            SimpleNamespace(name="get_project",
                            description="Read real native saved project",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="import_asset_from_path",
                            description=("Preview or import a local media path into the "
                                         "active saved project. Source assets are "
                                         "copied on confirmed apply."),
                            input_schema={"type": "object", "properties": {
                                "path": {"type": "string"},
                                "previewOnly": {"type": "boolean"}}}),
        ])

    async def call_tool(self, name, arguments):
        if name == "get_project":
            self.calls.append((name, arguments))
            response = {"mcp": {"hasProject": True},
                        "project": {"id": "source-owned-project"},
                        "assetCount": 0, "timelineCount": 1,
                        "currentTimeline": {"id": "real-timeline",
                                            "clipCount": 0, "trackCount": 2,
                                            "transitionCount": 0}}
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps(response))])
        return await super().call_tool(name, arguments)


class CreateNativeProjectThenObserveEmptyAssets(ActualNativeObservationSession):
    def __init__(self):
        super().__init__()
        self.tools.extend([
            SimpleNamespace(name="get_assets",
                            description="Read actual native project assets",
                            input_schema={"type": "object", "properties": {
                                "limit": {"type": "integer"}}}),
            SimpleNamespace(name="import_asset_from_path",
                            description="Import local source into project-owned media",
                            input_schema={"type": "object", "properties": {
                                "path": {"type": "string"},
                                "previewOnly": {"type": "boolean"}}}),
        ])

    async def call_tool(self, name, arguments):
        if name == "get_assets":
            self.calls.append((name, arguments))
            return SimpleNamespace(is_error=False, content=[SimpleNamespace(
                type="text", text=json.dumps({
                    "count": 0, "limitApplied": False, "assets": []}))])
        return await super().call_tool(name, arguments)


class ActualHostAssetProducerFrontierTests(unittest.IsolatedAsyncioTestCase):
    def grants(self, session):
        return {t.name: ("read" if t.name in {
            "get_project", "get_assets", "get_timeline",
            "zx7_verify_native_export", "zx7_observe_verified_export_frame"}
            else "write") for t in session.tools}

    async def test_import_possibilities_are_visible_before_any_failed_model_write(self):
        # This is a scripted protocol oracle, not a creative demonstration.
        editor = HostObservedEmptyAssetSession()
        model = ScriptedModel([
            decision("describe", tool="import_asset_from_path"),
            decision("finish", summary="Import was not made in this protocol test"),
        ])
        access = self.grants(editor)
        result = await NativeCreativeControl(
            editor, model, max_turns=2, catalog_mode="indexed",
            host_tool_access=access,
            host_possible_effects={
                "import_asset_from_path": ["project_asset_available"],
            }).run("Inspect original licensed sources")
        self.assertIn("import_asset_from_path",
                      model.observed[0]["selectable_native_tools"])
        self.assertEqual(model.observed[0][
            "host_attested_source_asset_producers"]["origin"],
            "host_attested_empty_native_project")
        self.assertEqual([name for name, _ in editor.calls], [
            "get_project", "get_assets"])
        frontier = [x for x in result["events"] if x["kind"] ==
                    "host_native_empty_asset_frontier"]
        self.assertEqual(len(frontier), 1)
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=access)[
                "journal_chain_structurally_valid"])
        forgery = copy.deepcopy(result["events"])
        for item in forgery:
            if item.get("kind") == "host_native_empty_asset_frontier":
                item["result_tool_names"] = ["host-not-granted"]
        with self.assertRaises(NativeJournalError):
            audit_native_journal(forgery, host_tool_access=access)

    async def test_creating_project_exposes_source_producers_without_placement_error(self):
        editor = CreateNativeProjectThenObserveEmptyAssets()
        model = ScriptedModel([
            decision("invoke", tool="create_project",
                     inputs={"name": "Source-owned project"}),
            decision("describe", tool="import_asset_from_path"),
            decision("finish", summary="No edit performed in protocol test"),
        ])
        access = self.grants(editor)
        result = await NativeCreativeControl(
            editor, model, max_turns=3, catalog_mode="indexed",
            host_tool_access=access,
            host_possible_effects={
                "create_project": ["project_open"],
                "import_asset_from_path": ["project_asset_available"],
            },
            host_preconditions={
                "import_asset_from_path": ["project_open"],
            }).run("Create a real project and discover actual source tools")
        self.assertEqual(model.observed[0][
            "native_project_presence_from_last_inspection"], "absent")
        self.assertEqual(model.observed[1][
            "native_project_presence_from_last_inspection"], "present")
        self.assertIn("import_asset_from_path",
                      model.observed[1]["selectable_native_tools"])
        self.assertIn("get_assets", [name for name, _ in editor.calls])
        self.assertFalse(any(x["kind"] == "model_action_rejected"
                             for x in result["events"]))
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=access)[
                "journal_chain_structurally_valid"])

    async def test_empty_native_assets_expose_actual_host_producer_not_a_script(self):
        editor = HostObservedEmptyAssetSession()
        model = ScriptedModel([
            decision("search", query="add_asset_to_timeline"),
            decision("invoke", tool="add_asset_to_timeline",
                     inputs={"assetId": "hallucinated-asset", "previewOnly": False}),
            decision("invoke", tool="import_asset_from_path",
                     inputs={"path": "/trusted/staging/original.mp4",
                             "previewOnly": False}),
        ])
        access = self.grants(editor)
        result = await NativeCreativeControl(
            editor, model, max_turns=3, catalog_mode="indexed",
            host_tool_access=access,
            host_possible_effects={
                "import_asset_from_path": ["project_asset_available"],
            }).run("Edit genuinely imported owner-licensed video")
        self.assertEqual(result["status"], "turn_budget_exhausted")
        self.assertIn("import_asset_from_path",
                      model.observed[2]["selectable_native_tools"])
        self.assertEqual(model.observed[2]["last_capability_search_result"]["origin"],
                         "host_attested_missing_native_asset")
        self.assertEqual(model.observed[2]["last_rejected_native_action_feedback"][
            "validation_keyword"], "native_asset_not_imported")
        self.assertEqual([name for name, _ in editor.calls if name in (
            "add_asset_to_timeline", "import_asset_from_path")],
            ["import_asset_from_path"])
        frontier = [x for x in result["events"]
                    if x.get("kind") == "host_native_asset_capability_frontier"]
        self.assertEqual(len(frontier), 1)
        self.assertEqual(frontier[0]["result_tool_names"],
                         ["import_asset_from_path"])
        self.assertTrue(audit_native_journal(result["events"],
                           host_tool_access=access)["journal_chain_structurally_valid"])
        forged = copy.deepcopy(result["events"])
        for x in forged:
            if x.get("kind") == "host_native_asset_capability_frontier":
                x["result_tool_names"] = ["ungranted_import"]
        with self.assertRaises(NativeJournalError):
            audit_native_journal(forged, host_tool_access=access)
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_forced_image_sequence_error_can_be_corrected_without_replay(self):
        # No pathname/extension is interpreted by the BODY. Only the exact
        # actual source-pinned editor error proves no import happened.
        class SourceAttestedSequenceSession(HostObservedEmptyAssetSession):
            async def call_tool(self, name, arguments):
                if (name == "import_asset_from_path" and
                        arguments.get("asSequence") is True):
                    self.calls.append((name, arguments))
                    return SimpleNamespace(is_error=True, content=[
                        SimpleNamespace(
                            type="text",
                            text=_PINNED_NO_IMAGE_SEQUENCE_ERROR)])
                return await super().call_tool(name, arguments)
        editor = SourceAttestedSequenceSession()
        source_path = "/trusted/owner/staging/original.mp4"
        model = ScriptedModel([
            decision("search", query="import_asset_from_path"),
            decision("invoke", tool="import_asset_from_path", inputs={
                "path": source_path, "asSequence": True}),
            decision("invoke", tool="import_asset_from_path", inputs={
                "path": source_path, "asSequence": False, "previewOnly": False}),
        ])
        entry = next(tool for tool in editor.tools
                     if tool.name == "import_asset_from_path")
        entry.input_schema["properties"]["asSequence"] = {"type": "boolean"}
        access = self.grants(editor)
        outcome = await NativeCreativeControl(
            editor, model, max_turns=3, catalog_mode="indexed",
            host_tool_access=access).run("Edit original target footage")
        self.assertEqual(outcome["status"], "turn_budget_exhausted")
        self.assertEqual(model.observed[2]["last_rejected_native_action_feedback"][
            "validation_keyword"], "native_sequence_requires_image_frames")
        imports = [args for name, args in editor.calls
                   if name == "import_asset_from_path"]
        self.assertEqual(imports, [
            {"path": source_path, "asSequence": True},
            {"path": source_path, "asSequence": False,
             "previewOnly": False},
        ])
        events = [x for x in outcome["events"] if x["kind"] ==
                  "native_source_preimport_reported_error"]
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["host_source_proved_no_import_attempt"])
        self.assertTrue(audit_native_journal(
            outcome["events"], host_tool_access=access)[
                "journal_chain_structurally_valid"])
        forged = copy.deepcopy(outcome["events"])
        next(x for x in forged if x["kind"] ==
             "native_source_preimport_reported_error")["error_sha256"] = "0" * 64
        with self.assertRaises(NativeJournalError):
            audit_native_journal(forged, host_tool_access=access)

    async def test_import_with_video_like_directory_name_is_not_preemptively_blocked(self):
        editor = HostObservedEmptyAssetSession()
        entry = next(t for t in editor.tools
                     if t.name == "import_asset_from_path")
        entry.input_schema["properties"]["asSequence"] = {"type": "boolean"}
        model = ScriptedModel([
            decision("search", query="import_asset_from_path"),
            decision("invoke", tool="import_asset_from_path", inputs={
                # Could be a directory of numbered image frames, not an MP4.
                "path": "/source/archive.mkv",
                "asSequence": True, "previewOnly": False}),
        ])
        access = self.grants(editor)
        outcome = await NativeCreativeControl(
            editor, model, max_turns=2, catalog_mode="indexed",
            host_tool_access=access).run("Import original numbered image sequence")
        self.assertEqual([args for name, args in editor.calls
                          if name == "import_asset_from_path"], [{
            "path": "/source/archive.mkv", "asSequence": True,
            "previewOnly": False}])
        self.assertFalse(any(x["kind"] ==
                             "native_source_preimport_reported_error"
                             for x in outcome["events"]))

    async def test_other_native_import_errors_remain_uncertain_writes(self):
        class OtherErrorSession(HostObservedEmptyAssetSession):
            async def call_tool(self, name, arguments):
                if name == "import_asset_from_path":
                    self.calls.append((name, arguments))
                    return SimpleNamespace(is_error=True, content=[
                        SimpleNamespace(
                            type="text",
                            text="import_asset_from_path failed: Disk full")])
                return await super().call_tool(name, arguments)
        editor = OtherErrorSession()
        entry = next(t for t in editor.tools
                     if t.name == "import_asset_from_path")
        entry.input_schema["properties"]["asSequence"] = {"type": "boolean"}
        model = ScriptedModel([
            decision("search", query="import_asset_from_path"),
            decision("invoke", tool="import_asset_from_path", inputs={
                "path": "/source/footage.mp4",
                "asSequence": True, "previewOnly": False}),
        ])
        access = self.grants(editor)
        outcome = await NativeCreativeControl(
            editor, model, max_turns=2, catalog_mode="indexed",
            host_tool_access=access).run("Import footage")
        self.assertEqual(outcome["status"],
                         "native_error_requires_state_reconciliation")
        self.assertTrue(any(x["kind"] == "native_tool_reported_error"
                            for x in outcome["events"]))
        self.assertTrue(audit_native_journal(
            outcome["events"], host_tool_access=access)[
                "journal_chain_structurally_valid"])

    async def test_empty_native_export_rejected_before_stateful_rpc(self):
        # Actual Qwen run #41204331429 terminated after attempting to export
        # a zero-clip project. The pinned Velorn source has an explicit
        # checkExportReadiness no-visual-clip blocker before performAction.
        editor = HostObservedEmptyAssetSession()
        editor.tools.extend([
            SimpleNamespace(name="save_project", description="Save project",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="export_timeline",
                            description="Render current visual timeline",
                            input_schema={"type": "object", "properties": {}}),
        ])
        model = ScriptedModel([
            decision("search", query="save_project"),
            decision("invoke", tool="save_project", inputs={}),
            decision("search", query="export_timeline"),
            decision("invoke", tool="export_timeline", inputs={}),
            decision("search", query="import_asset_from_path"),
        ])
        access = self.grants(editor)
        outcome = await NativeCreativeControl(
            editor, model, max_turns=5, catalog_mode="indexed",
            host_tool_access=access,
            host_possible_effects={"import_asset_from_path": [
                "project_asset_available"]},
        ).run("Original native footage must be edited before export")
        self.assertEqual(outcome["status"], "turn_budget_exhausted")
        self.assertEqual(model.observed[4]["last_rejected_native_action_feedback"][
            "validation_keyword"], "native_export_no_timeline_clips")
        self.assertNotIn("export_timeline",
                         [name for name, _ in editor.calls])
        self.assertTrue(any(event.get("validation_keyword") ==
                            "native_export_no_timeline_clips"
                            for event in outcome["events"]))
        self.assertTrue(audit_native_journal(
            outcome["events"], host_tool_access=access)[
                "journal_chain_structurally_valid"])

    async def test_nonempty_native_export_still_uses_existing_host_authority(self):
        class PhysicalClipSession(HostObservedEmptyAssetSession):
            async def call_tool(self, name, arguments):
                result = await super().call_tool(name, arguments)
                if name == "get_project":
                    snapshot = json.loads(result.content[0].text)
                    snapshot["assetCount"] = 1
                    snapshot["currentTimeline"]["clipCount"] = 1
                    result.content[0].text = json.dumps(snapshot)
                return result
        editor = PhysicalClipSession()
        editor.tools.extend([
            SimpleNamespace(name="save_project", description="Save project",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="export_timeline",
                            description="Render current visual timeline",
                            input_schema={"type": "object", "properties": {}}),
        ])
        model = ScriptedModel([
            decision("search", query="save_project"),
            decision("invoke", tool="save_project", inputs={}),
            decision("search", query="export_timeline"),
            decision("invoke", tool="export_timeline", inputs={}),
        ])
        access = self.grants(editor)
        outcome = await NativeCreativeControl(
            editor, model, max_turns=4, catalog_mode="indexed",
            host_tool_access=access,
        ).run("Native editor export after actual content")
        self.assertEqual([name for name, _ in editor.calls
                          if name == "export_timeline"], ["export_timeline"])
        self.assertFalse(any(e.get("validation_keyword") ==
                             "native_export_no_timeline_clips"
                             for e in outcome["events"]))
        self.assertTrue(audit_native_journal(
            outcome["events"], host_tool_access=access)[
                "journal_chain_structurally_valid"])

    async def test_post_visual_write_lagging_zero_clip_read_is_not_export_veto(self):
        # Native editor reads can lag an acknowledged write. A zero-clip
        # snapshot is grounds to reject *known* empty export only until a
        # genuine model-chosen, host-confirmed visual content revision. After
        # that, the editor must decide actual readiness, never stale BODY data.
        editor = HostObservedEmptyAssetSession()
        editor.tools.extend([
            SimpleNamespace(name="add_text_clip",
                            description="Commit model-authored native text clip",
                            input_schema={"type": "object", "properties": {
                                "text": {"type": "string"}}}),
            SimpleNamespace(name="export_timeline",
                            description="Render the actual native timeline",
                            input_schema={"type": "object", "properties": {}}),
        ])
        model = ScriptedModel([
            decision("invoke", tool="add_text_clip", inputs={"text": "Actual scene"}),
            decision("invoke", tool="export_timeline", inputs={}),
            decision("finish", summary="Only native tool ACKs, not a verified movie"),
        ])
        grants = self.grants(editor)
        outcome = await NativeCreativeControl(
            editor, model, host_tool_access=grants, max_turns=3,
            host_content_revision_tools=("add_text_clip",)
        ).run("Author original text footage and export in the native editor")
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertEqual(model.observed[1][
            "latest_host_attested_native_project_progress"][
                "current_timeline_clip_count"], 0)
        self.assertIn("export_timeline", [tool for tool, _ in editor.calls])
        self.assertFalse(any(e.get("validation_keyword") ==
                             "native_export_no_timeline_clips"
                             for e in outcome["events"]))
        self.assertEqual(sum(e.get("kind") == "native_tool_result" and
                             e.get("tool") == "export_timeline"
                             for e in outcome["events"]), 1)
        self.assertTrue(audit_native_journal(
            outcome["events"], host_tool_access=grants,
            host_content_revision_tools=("add_text_clip",))[
                "journal_chain_structurally_valid"])

    async def test_no_host_producer_effect_means_no_fake_remediation_tool(self):
        editor = HostObservedEmptyAssetSession()
        model = ScriptedModel([
            decision("search", query="add_asset_to_timeline"),
            decision("invoke", tool="add_asset_to_timeline",
                     inputs={"assetId": "not-imported", "previewOnly": False}),
        ])
        access = self.grants(editor)
        result = await NativeCreativeControl(
            editor, model, max_turns=2, catalog_mode="indexed",
            host_tool_access=access, host_possible_effects={}).run(
                "Only actually granted source actions")
        self.assertFalse(any(e.get("kind") == "host_native_asset_capability_frontier"
                             for e in result["events"]))
        self.assertTrue(audit_native_journal(result["events"],
                           host_tool_access=access)["journal_chain_structurally_valid"])
        self.assertEqual([name for name, _ in editor.calls if name ==
                          "add_asset_to_timeline"], [])


if __name__ == "__main__":
    unittest.main()
