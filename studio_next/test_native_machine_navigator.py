"""Unscripted artistic choices with source-grounded native machine navigation.

Synthetic adapter/model responses below are explicit test fixtures, never
evidence of neural artistic ability or actual imported/edited real media.
"""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from studio_next.native_creative_control import NativeCreativeControl
from studio_next.native_creative_audit import audit_native_journal
from studio_next.test_native_creative_control import ScriptedModel, decision


class SyntheticNativeStateSession:
    def __init__(self, *, fail_assets=False):
        self.fail_assets=fail_assets
        self.imported=False
        self.calls=[]
        self.tools=[
            SimpleNamespace(name="get_project",description="Real active editor project",
                input_schema={"type":"object","properties":{}}),
            SimpleNamespace(name="get_assets",description="Read physical imported native assets",
                input_schema={"type":"object","properties":{}}),
            SimpleNamespace(name="get_timeline",description="Read native clip track state",
                input_schema={"type":"object","properties":{
                    "includeClips":{"type":"boolean"}, "limit":{"type":"integer"}}}),
            SimpleNamespace(name="import_asset_from_path",description="Import operator-owned video source",
                input_schema={"type":"object","required":["path"],
                              "properties":{"path":{"type":"string"},
                                  "previewOnly":{"type":"boolean"},
                                  "category":{"type":"string"}}}),
            SimpleNamespace(name="add_asset_to_timeline",description="Place existing native asset on timeline",
                input_schema={"type":"object","required":["assetId"],
                              "properties":{"assetId":{"type":"string"}}}),
        ]

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name, args):
        self.calls.append((name,args))
        if name=="get_project":
            return self._receipt({"mcp":{"hasProject":True},
                                  "project":{"id":"native-original"}})
        if name=="get_assets":
            if self.fail_assets:
                raise ConnectionError("Test-only unreachable read; not a model error")
            return self._receipt({"count":int(self.imported),
                                  "limitApplied":False,
                                  "assets":[{"id":"source-from-native","name":"owner-video"}]
                                  if self.imported else []})
        if name=="get_timeline":
            return self._receipt({"clips":[],"clipLimitApplied":False})
        if name=="import_asset_from_path":
            self.imported=True
            # Match the pinned Velorn application's real import receipt.
            return self._receipt({"success":True,"result":{"success":True,
                "asset":{"id":"source-from-native","name":"owner-video"}}})
        raise AssertionError("No native creative placement was model-authorized")

    @staticmethod
    def _receipt(body):
        return SimpleNamespace(is_error=False,content=[
            SimpleNamespace(type="text",text=json.dumps(body))])


class DelayedNativeAssetSession(SyntheticNativeStateSession):
    """A native ACK can be observed before the read-only source index settles."""

    def __init__(self, *, stale_post_import_reads=1, error_on_second_read=False,
                 stale_snapshot_contains_other_source=False):
        super().__init__()
        self.stale_post_import_reads=stale_post_import_reads
        self.error_on_second_read=error_on_second_read
        self.stale_snapshot_contains_other_source=stale_snapshot_contains_other_source
        self.post_import_reads=0

    async def call_tool(self, name, args):
        if name=="get_assets" and self.imported:
            self.post_import_reads += 1
            if self.error_on_second_read and self.post_import_reads==2:
                self.calls.append((name,args))
                raise ConnectionError("Test-only native inventory read outage")
            if self.post_import_reads <= self.stale_post_import_reads:
                self.calls.append((name,args))
                if self.stale_snapshot_contains_other_source:
                    return self._receipt({"count":1,"limitApplied":False,
                        "assets":[{"id":"older-asset","name":"unrelated older asset"}]})
                return self._receipt({"count":0,"limitApplied":False,"assets":[]})
        return await super().call_tool(name,args)


def host_grants():
    return {
        "get_project":"read","get_assets":"read","get_timeline":"read",
        "import_asset_from_path":"write","add_asset_to_timeline":"write",
    }


def controls(session,model,max_turns):
    return NativeCreativeControl(session,model,max_turns=max_turns,
        catalog_mode="indexed",host_tool_access=host_grants(),
        host_preconditions={
            "import_asset_from_path":["project_open"],
            "add_asset_to_timeline":["project_open","assets_present"],
        },
        host_possible_effects={
            "import_asset_from_path":["assets_present"],
            "add_asset_to_timeline":["timeline_picture_present"],
        })


class NativeMachineNavigatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_real_editor_facts_advertise_only_possible_import_without_writes(self):
        session=SyntheticNativeStateSession()
        model=ScriptedModel([
            decision("search",query="import asset"),
            decision("finish",summary="No physical film has been produced"),
        ])
        outcome=await controls(session,model,2).run("Free original visual artist")
        observed=model.observed[0]
        self.assertEqual(observed["host_observed_machine_facts"],
            {"project_open":True,"assets_present":False})
        offered={row["id"] for row in observed["host_machine_affordances"]["matches"]}
        self.assertIn("native/import_asset_from_path",offered)
        self.assertNotIn("native/add_asset_to_timeline",offered)
        self.assertEqual([name for name,_ in session.calls],["get_project","get_assets"])
        self.assertFalse(outcome["native_editing_capability_complete"])
        proof=audit_native_journal(outcome["events"],host_tool_access=host_grants())
        self.assertEqual(proof["recorded_native_write_result_count"],0)
        self.assertFalse(proof["human_or_artistic_quality_approved"])

    async def test_brain_can_choose_import_and_then_picture_tool_without_one_metadata_search(self):
        session=SyntheticNativeStateSession()
        model=ScriptedModel([
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/camera_source.webm"}),
            decision("finish",summary="Still no model-directed edit or export"),
        ])
        outcome=await controls(session,model,2).run("Model chooses creative film, no BODY storyboard")
        self.assertIn("invoke",model.observed[0]["available_actions"])
        self.assertIn("import_asset_from_path",
                      model.observed[0]["selectable_native_tools"])
        self.assertIn("add_asset_to_timeline",
                      model.observed[1]["selectable_native_tools"])
        self.assertNotIn("import_asset_from_path",
                         model.observed[1]["selectable_native_tools"])
        self.assertTrue(model.observed[1]["host_observed_machine_facts"][
            "assets_present"])
        self.assertEqual([name for name,_ in session.calls].count(
            "import_asset_from_path"),1)
        self.assertEqual([name for name,_ in session.calls].count(
            "add_asset_to_timeline"),0)
        self.assertTrue(any(x["kind"]=="host_machine_frontier"
                            for x in outcome["events"]))
        audit=audit_native_journal(outcome["events"],host_tool_access=host_grants())
        self.assertEqual(audit["recorded_native_write_result_count"],1)

    async def test_after_model_selected_import_host_shows_real_missing_picture_not_aesthetic_recipe(self):
        session=SyntheticNativeStateSession()
        model=ScriptedModel([
            decision("search",query="import asset"),
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/host-staging/camera.mp4"}),
            decision("search",query="add asset"),
            decision("finish",summary="Not a model-created film"),
        ])
        outcome=await controls(session,model,4).run("Artist chooses shots and camera motion")
        observed=model.observed[2]
        self.assertTrue(observed["host_observed_machine_facts"]["assets_present"])
        self.assertFalse(observed["host_observed_machine_facts"]["timeline_picture_present"])
        possibilities={row["id"] for row in observed["host_machine_affordances"]["matches"]}
        self.assertIn("native/add_asset_to_timeline",possibilities)
        self.assertNotIn("native/import_asset_from_path",possibilities)
        self.assertEqual([name for name,_ in session.calls].count(
            "import_asset_from_path"),1)
        self.assertEqual([name for name,_ in session.calls].count(
            "add_asset_to_timeline"),0)
        self.assertIn("get_timeline",[name for name,_ in session.calls])
        audit=audit_native_journal(outcome["events"],host_tool_access=host_grants())
        self.assertEqual(audit["recorded_native_write_result_count"],1)
        self.assertFalse(audit["video_editing_capability_complete"])

    async def test_machine_frontier_cannot_invent_grants_or_certify_art(self):
        import copy
        from studio_next.native_creative_audit import NativeJournalError
        session=SyntheticNativeStateSession()
        model=ScriptedModel([decision("finish",summary="No independent film")])
        result=await controls(session,model,1).run("Original film intent")
        events=result["events"]
        index=next(i for i,v in enumerate(events)
                   if v["kind"]=="host_machine_frontier")
        self.assertTrue(audit_native_journal(events,host_tool_access=host_grants())[
            "journal_chain_structurally_valid"])
        for field,forgery in (
            ("result_tool_names",["not_a_granted_tool"]),
            ("false_host_facts",["artistic_perfection_reached"]),
            ("false_host_facts",[]),
            ("host_known_facts_sha256","faked-state"),
            ("host_sensing_only_no_artistic_choice",False),
            ("no_native_dispatch",False),
        ):
            changed=copy.deepcopy(events)
            changed[index][field]=forgery
            with self.subTest(field=field,forgery=forgery),self.assertRaises(
                    NativeJournalError):
                audit_native_journal(changed,host_tool_access=host_grants())

    async def test_unobservable_native_source_is_unknown_not_unimported_and_no_auto_action(self):
        session=SyntheticNativeStateSession(fail_assets=True)
        model=ScriptedModel([
            decision("finish",summary="Original source state remains unknown"),
        ])
        outcome=await controls(session,model,1).run("No assumed pictures")
        sensed=model.observed[0]["host_observed_machine_facts"]
        self.assertEqual(sensed,{"project_open":True})
        self.assertIsNone(model.observed[0]["host_machine_affordances"])
        self.assertNotIn("import_asset_from_path",
                         [name for name,_ in session.calls])
        self.assertTrue(any(event["kind"]=="native_asset_inventory_unknown"
                            for event in outcome["events"]))
        audit_native_journal(outcome["events"],host_tool_access=host_grants())


    async def test_nested_batch_asset_hallucination_refused_before_native_write(self):
        """Same source-neutral native-ID gate must cover nested batch selectors.

        All reads and the first asset import below are test fixtures. This
        is an admission/recovery regression, not real model or media proof.
        """
        session=SyntheticNativeStateSession()
        session.tools.append(SimpleNamespace(
            name="add_assets_to_timeline",
            description="Place several native inventory assets onto tracks",
            input_schema={"type":"object","properties":{
                "assets":{"type":"array","items":{"type":"object",
                    "properties":{"assetId":{"type":"string"}}}},
                "previewOnly":{"type":"boolean"}}}))
        grants={**host_grants(),"add_assets_to_timeline":"write"}
        model=ScriptedModel([
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/real-camera.webm"}),
            decision("invoke",tool="add_assets_to_timeline",
                     inputs={"assets":[{"assetId":"model-invented-asset-id"}],
                             "previewOnly":False}),
            decision("finish",summary="No native timeline mutation accepted"),
        ])
        outcome=await NativeCreativeControl(
            session,model,max_turns=3,catalog_mode="indexed",
            host_tool_access=grants,host_preconditions={
                "import_asset_from_path":["project_open"],
                "add_assets_to_timeline":["project_open","assets_present"]},
            host_possible_effects={
                "import_asset_from_path":["assets_present"],
                "add_assets_to_timeline":["timeline_picture_present"]},
            ).run("Model independently selects real source")
        self.assertEqual([n for n,_ in session.calls].count(
            "import_asset_from_path"),1)
        self.assertNotIn("add_assets_to_timeline",
                         [n for n,_ in session.calls])
        rejected=[e for e in outcome["events"]
                  if e["kind"]=="model_action_rejected"]
        self.assertEqual(len(rejected),1)
        self.assertEqual(rejected[0]["tool"],"add_assets_to_timeline")
        self.assertEqual(rejected[0]["reason"],
                         "asset_id_not_in_native_inventory")
        self.assertTrue(rejected[0]["no_native_dispatch"])
        self.assertTrue(audit_native_journal(
            outcome["events"],host_tool_access=grants)
            ["journal_chain_structurally_valid"])
        self.assertFalse(outcome["native_editing_capability_complete"])

    async def test_native_import_ack_requires_fresh_asset_identity_after_visibility_lag(self):
        session=DelayedNativeAssetSession(stale_post_import_reads=1)
        model=ScriptedModel([
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/real-camera.webm"}),
            decision("finish",summary="Test-only no export or artistic evaluation"),
        ])
        # Stub only the physical waiting interval, not the native read results.
        with patch("studio_next.native_creative_control.asyncio.sleep",
                   new_callable=AsyncMock) as sleep:
            outcome=await controls(session,model,2).run("Use operator source")
        sleep.assert_awaited_once_with(1.5)
        self.assertTrue(model.observed[1]["host_observed_machine_facts"]["assets_present"])
        self.assertIn("source-from-native",model.observed[1][
            "last_physically_observed_native_asset_inventory"]["source_ids"])
        self.assertEqual([name for name,_ in session.calls].count("get_assets"),3)
        self.assertEqual([name for name,_ in session.calls].count(
            "import_asset_from_path"),1)
        reads=[event for event in outcome["events"]
               if event["kind"]=="host_native_asset_inventory" and event["turn"]==1]
        self.assertEqual([(r["read_attempt"],r["actual_imported_asset_total"])
                          for r in reads],[(1,0),(2,1)])
        self.assertEqual(audit_native_journal(outcome["events"],
            host_tool_access=host_grants())["recorded_native_write_result_count"],1)

    async def test_import_ack_does_not_invent_assets_when_bounded_reads_stay_empty(self):
        session=DelayedNativeAssetSession(stale_post_import_reads=2)
        model=ScriptedModel([
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/not-yet-visible.webm"}),
            decision("finish",summary="Source still not observed"),
        ])
        with patch("studio_next.native_creative_control.asyncio.sleep",
                   new_callable=AsyncMock) as sleep:
            outcome=await controls(session,model,2).run("Observe physical source identity")
        sleep.assert_awaited_once_with(1.5)
        self.assertNotIn("assets_present", model.observed[1][
            "host_observed_machine_facts"])
        self.assertEqual(model.observed[1]["last_native_source_import_reconciliation"], {
            "native_import_acknowledged":True,
            "specific_imported_asset_not_yet_observed":True,
            "same_source_reimport_requires_reconciliation":True,
            "read_only_get_assets_can_reconcile":True})
        self.assertEqual([name for name,_ in session.calls].count(
            "import_asset_from_path"),1)
        self.assertEqual([event["actual_imported_asset_total"]
            for event in outcome["events"]
            if event["kind"]=="host_native_asset_inventory" and event["turn"]==1],[0,0])
        audit_native_journal(outcome["events"],host_tool_access=host_grants())

    async def test_failed_second_asset_read_leaves_identity_unknown_not_assumed(self):
        session=DelayedNativeAssetSession(stale_post_import_reads=1,
                                          error_on_second_read=True)
        model=ScriptedModel([
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/source.webm"}),
            decision("finish",summary="Native identity unknown"),
        ])
        with patch("studio_next.native_creative_control.asyncio.sleep",
                   new_callable=AsyncMock) as sleep:
            outcome=await controls(session,model,2).run("Never infer imported files")
        sleep.assert_awaited_once_with(1.5)
        self.assertNotIn("assets_present",model.observed[1]["host_observed_machine_facts"])
        self.assertIsNone(model.observed[1][
            "last_physically_observed_native_asset_inventory"])
        self.assertEqual([name for name,_ in session.calls].count(
            "import_asset_from_path"),1)
        unknown=[event for event in outcome["events"]
                 if event["kind"]=="native_asset_inventory_unknown"]
        self.assertEqual(len(unknown),1)
        self.assertEqual(unknown[0]["read_attempt"],2)
        audit_native_journal(outcome["events"],host_tool_access=host_grants())


    async def test_other_existing_asset_does_not_confirm_new_import_identity(self):
        session=DelayedNativeAssetSession(stale_post_import_reads=1,
            stale_snapshot_contains_other_source=True)
        model=ScriptedModel([
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/fresh.webm"}),
            decision("finish",summary="Not a completed editorial operation"),
        ])
        with patch("studio_next.native_creative_control.asyncio.sleep",
                   new_callable=AsyncMock) as sleep:
            outcome=await controls(session,model,2).run("Preserve independent source IDs")
        sleep.assert_awaited_once_with(1.5)
        self.assertTrue(model.observed[1]["host_observed_machine_facts"]["assets_present"])
        self.assertIsNone(model.observed[1]["last_native_source_import_reconciliation"])
        reads=[e for e in outcome["events"] if e["kind"]=="host_native_asset_inventory"
               and e["turn"]==1]
        self.assertEqual([(e["read_attempt"],e["actual_imported_asset_total"])
                          for e in reads],[(1,1),(2,1)])
        # The count remained one on both reads, but ONLY the returned asset
        # identity in the second response reconciled the native import.
        self.assertIn("source-from-native",model.observed[1][
            "last_physically_observed_native_asset_inventory"]["source_ids"])
        audit_native_journal(outcome["events"],host_tool_access=host_grants())

    async def test_same_source_import_variants_blocked_until_real_asset_visible(self):
        session=DelayedNativeAssetSession(stale_post_import_reads=99)
        model=ScriptedModel([
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/source.webm",
                             "previewOnly":False}),
            decision("search",query="import asset"),
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/./source.webm",
                             "category":"video","previewOnly":False}),
            decision("finish",summary="Media identity still unresolved"),
        ])
        with patch("studio_next.native_creative_control.asyncio.sleep",
                   new_callable=AsyncMock):
            result=await controls(session,model,4).run("One source, never replay a write")
        self.assertEqual([n for n,_ in session.calls].count("import_asset_from_path"),1)
        refused=[e for e in result["events"]
                 if e["kind"]=="model_action_rejected"]
        self.assertEqual([e["validation_keyword"] for e in refused],
                         ["unreconciled_native_import"])
        self.assertEqual(refused[0]["no_native_dispatch"],True)
        audit_native_journal(result["events"],host_tool_access=host_grants())

    async def test_distinct_native_source_import_remains_possible(self):
        session=DelayedNativeAssetSession(stale_post_import_reads=99)
        model=ScriptedModel([
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/first.webm"}),
            decision("search",query="import asset"),
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/second.webm"}),
            decision("finish",summary="No creative timeline completed"),
        ])
        with patch("studio_next.native_creative_control.asyncio.sleep",
                   new_callable=AsyncMock):
            result=await controls(session,model,4).run("Different original sources permitted")
        self.assertEqual([a["path"] for n,a in session.calls
                          if n=="import_asset_from_path"],
                         ["/operator-owned/first.webm","/operator-owned/second.webm"])
        self.assertFalse(any(e["kind"]=="model_action_rejected"
                             for e in result["events"]))
        audit_native_journal(result["events"],host_tool_access=host_grants())

    async def test_model_selected_read_reconciles_visibility_without_reimport(self):
        session=DelayedNativeAssetSession(stale_post_import_reads=2)
        model=ScriptedModel([
            decision("invoke",tool="import_asset_from_path",
                     inputs={"path":"/operator-owned/camera.webm"}),
            decision("search",query="get assets"),
            decision("invoke",tool="get_assets",inputs={}),
            decision("finish",summary="Test-only source identity now observed"),
        ])
        with patch("studio_next.native_creative_control.asyncio.sleep",
                   new_callable=AsyncMock):
            result=await controls(session,model,4).run("Model invokes a fresh source read")
        self.assertEqual([n for n,_ in session.calls].count("import_asset_from_path"),1)
        self.assertEqual([n for n,_ in session.calls].count("get_assets"),4)
        self.assertIsNone(model.observed[3]["last_native_source_import_reconciliation"])
        self.assertTrue(model.observed[3]["host_observed_machine_facts"]["project_open"])
        self.assertTrue(model.observed[3]["host_observed_machine_facts"]["assets_present"])
        self.assertIn("source-from-native",model.observed[3][
            "last_physically_observed_native_asset_inventory"]["source_ids"])
        audit_native_journal(result["events"],host_tool_access=host_grants())

if __name__=="__main__":
    unittest.main()
