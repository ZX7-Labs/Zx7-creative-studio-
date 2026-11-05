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


class HostNativeSourceContractProbeTests(unittest.IsolatedAsyncioTestCase):
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
