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

    def test_physical_4b_batch_asset_ids_must_reference_imported_project_objects(self):
        # Actual CPU 4B run #41258639051 imported one video yet selected
        # source filesystem paths for assetIds. Velorn's native batch ABI
        # requires opaque IDs from its asset catalog, not external filenames.
        original = "/owner/trial/staging/raw-gradient-0.mp4"
        other = "/owner/trial/staging/raw-gradient-1.mp4"
        stock = {"count": 1, "limitApplied": False, "assets": [
            {"id": "native-imported-5", "name": "raw-gradient-0.mp4"}]}
        invalid = assess_native_asset_selection("add_assets_to_timeline", {
            "assetIds": [original, other], "previewOnly": False}, stock)
        self.assertEqual(invalid["validation_keyword"],
                         "native_asset_not_imported")
        self.assertEqual(invalid["available_native_asset_ids_sample"],
                         ["native-imported-5"])
        self.assertEqual(invalid["requested_native_asset_id_count"], 2)
        self.assertTrue(invalid["no_native_dispatch"])
        self.assertIsNone(assess_native_asset_selection(
            "add_assets_to_timeline",
            {"assetIds": ["native-imported-5"]}, stock))
        self.assertIsNone(assess_native_asset_selection(
            "add_assets_to_timeline",
            {"assetNames": ["gradient-0"]}, stock))
        self.assertEqual(assess_native_asset_selection(
            "add_assets_to_timeline",
            {"assetNames": ["raw-gradient-1.mp4"]}, stock)[
                "validation_keyword"], "native_asset_not_imported")
        partial = {**stock, "count": 2, "limitApplied": True}
        self.assertEqual(assess_native_asset_selection(
            "add_assets_to_timeline",
            {"assetIds": [other]}, partial)[
                "validation_keyword"], "native_asset_inventory_incomplete")

    def test_all_native_batch_selector_shapes_and_per_entry_priority(self):
        stock = {"count": 2, "limitApplied": False,
                 "assets": [{"id": "a", "name": "One.mp4"},
                            {"id": "b", "name": "Two.mp4"}]}
        good = (
            {"assets": ["a", {"assetId": "b"}]},
            {"assets": [{"assetName": "one"}, {"assetName": "two"}]},
            {"assetIds": ["a"], "assetNames": ["two"]},
            {"assets": [{"assetId": "a", "assetName": "does-not-exist"},
                        {"assetId": "b"}]},
        )
        for selection in good:
            with self.subTest(selection=selection):
                self.assertIsNone(assess_native_asset_selection(
                    "add_assets_to_timeline", selection, stock))
        bad = (
            {"assets": ["a", "unknown"]},
            {"assetIds": ["a", "unknown"]},
            {"assetNames": ["one", "unknown"]},
            {"assetIds": ["a"], "assetNames": ["unknown"]},
            {"assets": [{"assetId": "a"}, {"assetName": "unknown"}]},
            {"assets": [{"assetId": "a"}, {"assetId": "unknown"}]},
            {"assetIds": None},
            {"assetNames": "a"},
            {"assets": None},
        )
        for selection in bad:
            with self.subTest(selection=selection):
                proof = assess_native_asset_selection(
                    "add_assets_to_timeline", selection, stock)
                self.assertIsNotNone(proof)
                self.assertTrue(proof["no_native_dispatch"])

    def test_replacement_primary_asset_id_has_native_precedence(self):
        # Pinned mcpActions.js replacement resolves assetId first, alias
        # replacementAssetId only if primary is omitted.
        stock = {"count": 2, "limitApplied": False, "assets": [
            {"id": "native-a", "name": "A.mp4"},
            {"id": "native-b", "name": "B.mp4"}]}
        ok = ({"assetId": "native-a"},
              {"assetId": "native-a", "replacementAssetId": "missing"},
              {"assetId": "native-a", "assetName": "missing"},
              {"replacementAssetId": "native-b"},
              {"replacementAssetName": "B"})
        for inputs in ok:
            with self.subTest(inputs=inputs):
                self.assertIsNone(assess_native_asset_selection(
                    "replace_clip_with_asset", inputs, stock))
        bad = ({"assetId": "unknown"},
               {"assetId": "unknown", "replacementAssetId": "native-b"},
               {"assetId": "/owner/staging/source.mp4"},
               {"replacementAssetId": "unknown"},
               {"assetName": "missing"},
               {"replacementAssetName": "missing"})
        for inputs in bad:
            with self.subTest(inputs=inputs):
                response = assess_native_asset_selection(
                    "replace_clip_with_asset", inputs, stock)
                self.assertEqual(response["validation_keyword"],
                                 "native_asset_not_imported")
                self.assertTrue(response["no_native_dispatch"])

    def test_duplicate_native_catalog_ids_cannot_decide_which_media_gets_edited(self):
        duplicate = {"count": 2, "limitApplied": False, "assets": [
            {"id": "same-id", "name": "Owner original video.mp4"},
            {"id": "same-id", "name": "Unrelated substitute.mp4"}]}
        for tool, selection in (
            ("add_asset_to_timeline", {"assetId": "same-id"}),
            ("replace_clip_with_asset", {"assetId": "same-id"}),
            ("add_assets_to_timeline", {"assetIds": ["same-id"]}),
        ):
            with self.subTest(tool=tool):
                response = assess_native_asset_selection(
                    tool, selection, duplicate)
                self.assertEqual(response["validation_keyword"],
                                 "native_asset_inventory_unverified")
                self.assertTrue(response["no_native_dispatch"])

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

    async def test_real_batch_path_ids_rejected_without_dispatch_then_real_ids_accepted(self):
        session = LiveCatalogSession([
            {"id": "project-imported-asset", "name": "raw-gradient-0.mp4"}])
        session.tools.append(SimpleNamespace(
            name="add_assets_to_timeline",
            description="Use imported project assets in a real timeline",
            input_schema={"type": "object", "properties": {
                "assetIds": {"type": "array", "items": {"type": "string"}},
                "previewOnly": {"type": "boolean"}}}))
        model = ScriptedModel([
            decision("invoke", tool="add_assets_to_timeline", inputs={
                "assetIds": ["/owner/staging/raw-gradient-0.mp4"],
                "previewOnly": False}),
            decision("invoke", tool="add_assets_to_timeline", inputs={
                "assetIds": ["project-imported-asset"], "previewOnly": False}),
            decision("finish", summary="Only native asset identity admission; not a film"),
        ])
        grants = {tool.name: ("write" if tool.name in {
            "add_assets_to_timeline", "add_asset_to_timeline",
            "update_text_clip"} else "read") for tool in session.tools}
        outcome = await NativeCreativeControl(
            session, model, host_tool_access=grants, max_turns=3).run(
            "Select source media by native project IDs, not filesystem path")
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertEqual(model.observed[1][
            "last_rejected_native_action_feedback"]["validation_keyword"],
            "native_asset_not_imported")
        self.assertEqual(model.observed[1][
            "last_rejected_native_action_feedback"][
                "available_native_asset_ids_sample"], ["project-imported-asset"])
        self.assertEqual([args for name, args in session.calls
                          if name == "add_assets_to_timeline"],
                         [{"assetIds": ["project-imported-asset"],
                           "previewOnly": False}])
        self.assertEqual(len([x for x in outcome["events"] if x.get("kind") ==
                              "native_tool_result" and x.get("tool") ==
                              "add_assets_to_timeline"]), 1)
        self.assertTrue(audit_native_journal(
            outcome["events"], host_tool_access=grants)[
                "journal_chain_structurally_valid"])

    async def test_import_receipt_preserves_opaque_native_id_for_model_only(self):
        # A real Qwen4B run received the correct imported asset ID at turn 2,
        # but a later checkpoint overwrote its last native response, so the
        # model eventually substituted filesystem paths for native assetIds.
        # Keep the positive application ACK's ID discoverable, never mutate
        # a request or accept it as final source verification.
        native_id = "asset-opaque-host-issued-9"
        class ActualImportSession(LiveCatalogSession):
            def __init__(self, *, receipt_id=native_id):
                super().__init__([
                    {"id": native_id, "name": "owner-footage.mp4"}])
                self.receipt_id = receipt_id
                self.tools.extend([
                    SimpleNamespace(
                        name="import_asset_from_path",
                        description="Host project media import",
                        input_schema={"type": "object", "properties": {
                            "path": {"type": "string"},
                            "previewOnly": {"type": "boolean"}}}),
                    SimpleNamespace(
                        name="add_assets_to_timeline",
                        description="Commit selected native catalog assets",
                        input_schema={"type": "object", "properties": {
                            "assetIds": {"type": "array", "items": {
                                "type": "string"}},
                            "previewOnly": {"type": "boolean"}}}),
                ])
            async def call_tool(self, name, arguments):
                if name != "import_asset_from_path":
                    return await super().call_tool(name, arguments)
                self.calls.append((name, arguments))
                return SimpleNamespace(is_error=False, content=[
                    SimpleNamespace(type="text", text=json.dumps({
                        "success": True, "previewOnly": False,
                        "action": "import_asset_from_path",
                        "result": {
                            "success": True, "action": "import_asset_from_path",
                            "asset": {"id": self.receipt_id,
                                      "name": "owner-footage.mp4"}},
                    }))])
        session = ActualImportSession()
        model = ScriptedModel([
            decision("invoke", tool="import_asset_from_path", inputs={
                "path": "/owner/staging/owner-footage.mp4",
                "previewOnly": False}),
            decision("invoke", tool="get_timeline", inputs={}),
            decision("invoke", tool="add_assets_to_timeline", inputs={
                "assetIds": [native_id], "previewOnly": False}),
            decision("finish", summary="Protocol passes, not a verified film"),
        ])
        grants = {t.name: ("write" if t.name in {
            "import_asset_from_path", "add_assets_to_timeline",
            "add_asset_to_timeline", "update_text_clip"} else "read")
                  for t in session.tools}
        result = await NativeCreativeControl(
            session, model, max_turns=4, host_tool_access=grants).run(
            "Model selects original footage and real native project object")
        self.assertEqual(result["status"], "model_finished_unverified")
        for index in (1, 2):
            hint = model.observed[index][
                "last_imported_native_asset_receipt_for_lookup_only"]
            self.assertEqual(hint["assetId"], native_id)
            self.assertEqual(hint["assetName"], "owner-footage.mp4")
            self.assertTrue(
                hint["provisional_until_get_assets_confirms_identity"])
        self.assertEqual([name for name, args in session.calls
                          if name == "add_assets_to_timeline"],
                         ["add_assets_to_timeline"])
        self.assertEqual(len([e for e in result["events"]
                              if e.get("kind") == "native_tool_result" and
                              e.get("tool") == "add_assets_to_timeline"]), 1)
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)[
                "journal_chain_structurally_valid"])
        # A malformed native ACK cannot invent a usable project object ID.
        malformed = ActualImportSession(receipt_id="")
        fake = ScriptedModel([
            decision("invoke", tool="import_asset_from_path", inputs={
                "path": "/owner/staging/owner-footage.mp4",
                "previewOnly": False}),
            decision("finish", summary="No native asset ID attested"),
        ])
        outcome = await NativeCreativeControl(
            malformed, fake, max_turns=2,
            host_tool_access={t.name: ("write" if t.name in {
                "import_asset_from_path", "add_assets_to_timeline",
                "add_asset_to_timeline", "update_text_clip"} else "read")
                for t in malformed.tools}).run("Do not invent native assets")
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertIsNone(fake.observed[1][
            "last_imported_native_asset_receipt_for_lookup_only"])

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
