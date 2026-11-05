"""Unscripted artistic choices with source-grounded native machine navigation.

Synthetic adapter/model responses below are explicit test fixtures, never
evidence of neural artistic ability or actual imported/edited real media.
"""
import json
from types import SimpleNamespace
import unittest

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
                              "properties":{"path":{"type":"string"}}}),
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
            return self._receipt({"totalAssetCount":int(self.imported),
                                  "returnedAssetCount":int(self.imported),
                                  "assets":[{"id":"source-from-native","name":"owner-video"}]
                                  if self.imported else []})
        if name=="get_timeline":
            return self._receipt({"clips":[],"clipLimitApplied":False})
        if name=="import_asset_from_path":
            self.imported=True
            return self._receipt({"success":True,"result":{"imported":True}})
        raise AssertionError("No native creative placement was model-authorized")

    @staticmethod
    def _receipt(body):
        return SimpleNamespace(is_error=False,content=[
            SimpleNamespace(type="text",text=json.dumps(body))])


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


if __name__=="__main__":
    unittest.main()
