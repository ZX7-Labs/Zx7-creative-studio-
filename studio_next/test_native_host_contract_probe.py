"""Conformance probe before model spending: read real native tool outputs.

Fixtures only: the independently launched native app is verified in the
GH Actions physical trial, not by these scripted protocol responses.
"""
import json
from types import SimpleNamespace
import unittest

from scripts.run_native_model_trial import preflight_real_editor_inventory_contract
from studio_next.native_asset_identity import NativeAssetEvidenceError


class NativeAssetReadSession:
    def __init__(self, record, *, is_error=False, image=False):
        self.calls=[]
        self.record=record
        self.is_error=is_error
        self.image=image

    async def call_tool(self,tool,args):
        self.calls.append((tool,args))
        items=[SimpleNamespace(type="text",text=json.dumps(self.record))]
        if self.image:
            items.append(SimpleNamespace(type="image",data="test",
                                         mime_type="image/png"))
        return SimpleNamespace(is_error=self.is_error,content=items)


class FreshNativeProjectSession(NativeAssetReadSession):
    def __init__(self, status=None, *, is_error=False, image=False):
        super().__init__(status if status is not None else {
            "mcp":{"hasProject":False}, "project":None},
            is_error=is_error, image=image)

    async def call_tool(self,tool,args):
        if tool=="get_assets":
            raise AssertionError("Empty project must not be probed as an asset inventory")
        return await super().call_tool(tool,args)


class HostNativeSourceContractProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_empty_native_editor_defers_asset_probe_until_open(self):
        session=FreshNativeProjectSession()
        receipt=await preflight_real_editor_inventory_contract(session,{
            "get_project":"read", "get_assets":"read", "create_project":"write"},
            require_absent_project=True)
        self.assertEqual(session.calls,[("get_project",{})])
        self.assertTrue(receipt["native_project_observed_absent"])
        self.assertTrue(receipt["inventory_probe_deferred_until_native_project_exists"])
        self.assertFalse(receipt["native_asset_contract_proved"])
        self.assertIsNone(receipt["observed_asset_count"])
        self.assertTrue(receipt["no_native_write_attempted"])

    async def test_lifecycle_preflight_refuses_unknown_or_present_project(self):
        for project in (
            {"mcp":{"hasProject":True},"project":{"id":"already-open"}},
            {"mcp":{"hasProject":True},"project":None},
            {"mcp":{"hasProject":False},"project":{"id":"contradiction"}},
            {}):
            session=FreshNativeProjectSession(project)
            with self.subTest(project=project),self.assertRaises(ValueError):
                await preflight_real_editor_inventory_contract(session,{
                    "get_project":"read","get_assets":"read"},require_absent_project=True)
            self.assertEqual(session.calls,[("get_project",{})])

    async def test_lifecycle_preflight_requires_project_read_permission(self):
        session=FreshNativeProjectSession()
        with self.assertRaises(ValueError):
            await preflight_real_editor_inventory_contract(session,{
                "get_assets":"read"},require_absent_project=True)
        self.assertEqual(session.calls,[])

    async def test_lifecycle_probe_rejects_native_failure_or_image(self):
        for options in ({"is_error":True},{"image":True}):
            session=FreshNativeProjectSession(**options)
            with self.subTest(options=options),self.assertRaises(ValueError):
                await preflight_real_editor_inventory_contract(session,{
                    "get_project":"read","get_assets":"read"},require_absent_project=True)
            self.assertEqual(session.calls,[("get_project",{})])

    async def test_current_pinned_real_source_envelope_is_read_only_and_private(self):
        actual={"count":1,"limitApplied":False,"assets":[{
            "id":"native-asset-abc","name":"private owner's shot.webm",
            "type":"video","path":"/home/owner/private/source.webm"}]}
        session=NativeAssetReadSession(actual)
        proof=await preflight_real_editor_inventory_contract(
            session,{"get_assets":"read","create_project":"write"})
        self.assertEqual(session.calls,[("get_assets",{})])
        self.assertEqual(proof["observed_asset_count"],1)
        self.assertTrue(proof["bounded_inventory_complete"])
        self.assertTrue(proof["read_only"])
        self.assertTrue(proof["no_native_write_attempted"])
        self.assertFalse(proof["any_media_physically_imported_by_this_probe"])
        self.assertNotIn("private",str(proof))
        self.assertEqual(len(proof["source_response_sha256"]),64)

    async def test_imaginary_native_envelope_is_refused_before_any_model_inference(self):
        session=NativeAssetReadSession({
            "totalAssetCount":0,"returnedAssetCount":0,"assets":[]})
        with self.assertRaises(NativeAssetEvidenceError):
            await preflight_real_editor_inventory_contract(session,{
                "get_assets":"read"})
        self.assertEqual(session.calls,[("get_assets",{})])

    async def test_read_grant_is_mandatory_and_mutating_tools_never_called(self):
        session=NativeAssetReadSession({
            "count":0,"limitApplied":False,"assets":[]})
        for grants in ({"get_assets":"write"},{},None,
                       {"get_assets":"read","new_permission":"model_granted"}):
            if grants is not None and grants.get("get_assets")=="read":
                continue
            with self.subTest(grants=grants),self.assertRaises(ValueError):
                await preflight_real_editor_inventory_contract(session,grants)
        self.assertEqual(session.calls,[])

    async def test_native_rpc_errors_and_unexpected_media_are_not_source_proof(self):
        for params in ({"is_error":True},{"image":True}):
            session=NativeAssetReadSession({
                "count":0,"limitApplied":False,"assets":[]},**params)
            with self.subTest(params=params),self.assertRaises(ValueError):
                await preflight_real_editor_inventory_contract(session,{
                    "get_assets":"read"})
            self.assertEqual(session.calls,[("get_assets",{})])


if __name__=="__main__":
    unittest.main()
