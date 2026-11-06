"""Source-evidence regression for native media identity; never a creative preset."""
import copy
import json
import unittest
from types import SimpleNamespace

from studio_next.native_asset_identity import (
    assess_native_asset_selection, requires_native_asset_inventory)
from studio_next.native_creative_control import NativeCreativeControl
from studio_next.native_creative_audit import audit_native_journal, NativeJournalError
from studio_next.test_native_creative_control import (
    FakeSession, ScriptedModel, decision)


class AssetIdentityPureTests(unittest.TestCase):
    def test_known_id_is_eligible_unknown_id_is_not(self):
        stock = {"count": 1, "limitApplied": False,
                 "assets": [{"id": "native-id-7", "name": "Raw Footage.mp4"}]}
        self.assertIsNone(assess_native_asset_selection(
            "add_asset_to_timeline", {"assetId": "native-id-7"}, stock))
        failure = assess_native_asset_selection(
            "add_asset_to_timeline", {"assetId": "raw-footage"}, stock)
        self.assertEqual(failure["validation_keyword"], "native_asset_not_imported")
        self.assertEqual(failure["available_native_asset_ids_sample"],
                         ["native-id-7"])
        self.assertTrue(failure["no_native_dispatch"])

    def test_model_names_are_checked_against_original_native_inventory(self):
        stock = {"count": 1, "limitApplied": False,
                 "assets": [{"id": "asset-1", "name": "Raw Footage.mp4"}]}
        self.assertIsNone(assess_native_asset_selection(
            "add_asset_to_timeline", {"assetName": "footage"}, stock))
        self.assertEqual(assess_native_asset_selection(
            "add_asset_to_timeline", {"assetName": "invented"}, stock)[
            "validation_keyword"], "native_asset_not_imported")
        # Pinned Velorn prioritizes explicit assetId over optional name.
        self.assertIsNone(assess_native_asset_selection(
            "add_asset_to_timeline",
            {"assetId": "asset-1", "assetName": "invented"}, stock))

    def test_project_with_no_imported_assets_cannot_place_external_filename(self):
        empty = {"count": 0, "limitApplied": False, "assets": []}
        for inputs in ({"assetId": "raw-gradient-0"},
                       {"assetName": "raw-gradient-0.mp4"},
                       {"latestGenerated": True},
                       {"assets": [{"assetId": "raw-gradient-0"}]}):
            with self.subTest(inputs=inputs):
                tool = ("add_assets_to_timeline" if "assets" in inputs
                        else "add_asset_to_timeline")
                result = assess_native_asset_selection(tool, inputs, empty)
                self.assertEqual(result["validation_keyword"],
                                 "native_asset_not_imported")
                self.assertEqual(result["available_native_asset_count"], 0)

    def test_batch_and_replace_preserve_exact_source_ids(self):
        stock = {"count": 2, "limitApplied": False,
                 "assets": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]}
        self.assertIsNone(assess_native_asset_selection(
            "add_assets_to_timeline",
            {"assets": [{"assetId": "a"}, {"assetId": "b"}]}, stock))
        self.assertEqual(assess_native_asset_selection(
            "add_assets_to_timeline",
            {"assets": [{"assetId": "a"}, {"assetId": "c"}]}, stock)[
            "validation_keyword"], "native_asset_not_imported")
        self.assertIsNone(assess_native_asset_selection(
            "replace_clip_with_asset", {"replacementAssetId": "a"}, stock))

    def test_untrusted_or_incomplete_inventory_never_proves_absence(self):
        for stock in (
            {"count": "one", "limitApplied": False, "assets": []},
            {"count": 1, "limitApplied": False, "assets": []},
            {"count": 1, "limitApplied": False,
             "assets": [{"id": "", "name": "fake"}]},
        ):
            self.assertEqual(assess_native_asset_selection(
                "add_asset_to_timeline", {"assetId": "x"}, stock)[
                "validation_keyword"], "native_asset_inventory_unverified")
        partial = {"count": 2000, "limitApplied": True,
                   "assets": [{"id": "one", "name": "One"}]}
        self.assertEqual(assess_native_asset_selection(
            "add_asset_to_timeline", {"assetId": "absent"}, partial)[
            "validation_keyword"], "native_asset_inventory_incomplete")
        self.assertIsNone(assess_native_asset_selection(
            "add_asset_to_timeline", {"assetId": "one"}, partial))
        self.assertEqual(assess_native_asset_selection(
            "add_asset_to_timeline", {"assetName": "One"}, partial)[
            "validation_keyword"], "native_asset_inventory_incomplete")

    def test_no_creative_operation_or_new_tool_is_inferred(self):
        self.assertFalse(requires_native_asset_inventory("add_text_clip"))
        self.assertIsNone(assess_native_asset_selection(
            "add_text_clip", {"assetId": "unknown"}, None))


class LiveCatalogSession(FakeSession):
    def __init__(self, assets, *, malformed=False):
        super().__init__()
        self.assets = assets
        self.malformed = malformed
        self.tools.extend([
            SimpleNamespace(name="get_assets", description="Read imported project assets",
                            input_schema={"type": "object", "properties": {
                                "limit": {"type": "integer"}}}),
            SimpleNamespace(name="add_asset_to_timeline",
                            description="Place real imported project media",
                            input_schema={"type": "object", "properties": {
                                "assetId": {"type": "string"},
                                "assetName": {"type": "string"},
                                "previewOnly": {"type": "boolean"}}}),
        ])

    async def call_tool(self, name, arguments):
        if name == "get_assets":
            self.calls.append((name, arguments))
            receipt = ({"count": "unverified", "limitApplied": False,
                        "assets": []} if self.malformed else
                       {"count": len(self.assets), "limitApplied": False,
                        "assets": self.assets})
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps(receipt))])
        return await super().call_tool(name, arguments)


class NativeAssetIdentityControlTests(unittest.IsolatedAsyncioTestCase):
    async def trial(self, assets, asset_id, *, malformed=False):
        session = LiveCatalogSession(assets, malformed=malformed)
        model = ScriptedModel([
            decision("invoke", tool="add_asset_to_timeline",
                     inputs={"assetId": asset_id, "previewOnly": False}),
            decision("finish", summary="No professional quality proof"),
        ])
        grants = {tool.name: ("write" if tool.name in
                  {"add_asset_to_timeline", "update_text_clip"}
                  else "read") for tool in session.tools}
        result = await NativeCreativeControl(
            session, model, host_tool_access=grants,
            max_turns=2).run("Edit actual owner-licensed video")
        return session, model, result

    async def test_actual_cpu_trial_unimported_filename_is_rejected_pre_dispatch(self):
        session, model, result = await self.trial([], "raw-gradient-0")
        self.assertEqual(session.calls, [("get_assets", {"limit": 1000})])
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertEqual(model.observed[1]["last_rejected_native_action_feedback"][
            "validation_keyword"], "native_asset_not_imported")
        self.assertFalse(any(e["kind"] == "native_tool_submitted"
                             for e in result["events"]))
        grants = {tool.name: ("write" if tool.name in {
                  "add_asset_to_timeline", "update_text_clip"} else "read")
                  for tool in session.tools}
        proven = audit_native_journal(
            result["events"], host_tool_access=grants)
        self.assertTrue(proven["journal_chain_structurally_valid"])
        forged = copy.deepcopy(result["events"])
        for event in forged:
            if event.get("kind") == "host_native_asset_inventory_observed":
                event["host_attested_read_only"] = False
                break
        with self.assertRaises(NativeJournalError):
            audit_native_journal(forged, host_tool_access=grants)

    async def test_true_native_project_id_preserves_model_creative_control(self):
        session, model, result = await self.trial(
            [{"id": "asset-real-001", "name": "Original video"}],
            "asset-real-001")
        self.assertEqual(session.calls, [
            ("get_assets", {"limit": 1000}),
            ("add_asset_to_timeline", {
                "assetId": "asset-real-001", "previewOnly": False})])
        self.assertTrue(any(e["kind"] == "native_tool_result" and
                            e.get("tool") == "add_asset_to_timeline"
                            for e in result["events"]))
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_uncertain_read_only_inventory_does_not_dispatch_write(self):
        session, model, result = await self.trial([], "invented",
                                                  malformed=True)
        self.assertEqual(session.calls, [("get_assets", {"limit": 1000})])
        self.assertEqual(model.observed[1]["last_rejected_native_action_feedback"][
            "validation_keyword"], "native_asset_inventory_unverified")
        self.assertFalse(any(e["kind"] == "native_tool_submitted"
                             for e in result["events"]))


if __name__ == "__main__":
    unittest.main()
