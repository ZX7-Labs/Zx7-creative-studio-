"""Actual installed BODY bridge to source-neutral live native asset-ID guard.

The adapter exercises the real installed BODY catalog + gateway + durable SQLite.
Native editor RPC responses below are explicit bounded synthetic fixtures; they
are not physical Velorn or autonomous model creative acceptance evidence.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from studio_next.body_capability_adapter import connect_installed_zx7_body
from studio_next.capability_attempts import CapabilityAttemptStore
from studio_next.capability_gateway import CapabilityExecutionError
from studio_next.native_editor_asset_reader import (
    NativeEditorAssetInventoryError, observed_editor_asset_ids)


def native_assets(rows, *, total=None, limited=False):
    total = len(rows) if total is None else total
    return {"isError":False,"content":[{"type":"text",
        "text":json.dumps({"count":total,"limitApplied":limited,
                           "assets":rows})}]}


class NativeAssetReaderTests(unittest.TestCase):
    def test_real_pinned_native_transport_shape_without_paths(self):
        data=native_assets([
            {"id":"source-native-id","name":"original/owner/private.webm",
             "path":"/private/owner/movie.webm","type":"video"},
            {"id":"music-native-id","name":"original-audio.wav",
             "path":"/private/owner/audio.wav","type":"audio"}])
        parsed=observed_editor_asset_ids(data)
        self.assertEqual(parsed,{"assets":{
            "ids":["source-native-id","music-native-id"],"complete":True}})
        self.assertNotIn("/private/owner",str(parsed))
        self.assertNotIn("original-audio.wav",str(parsed))

    def test_empty_editor_is_an_actual_complete_empty_inventory(self):
        self.assertEqual(observed_editor_asset_ids(native_assets([])),
            {"assets":{"ids":[],"complete":True}})

    def test_partial_native_inventory_cannot_invent_absence(self):
        data=native_assets([
            {"id":"first-page","name":"first"}],total=5,limited=True)
        self.assertEqual(observed_editor_asset_ids(data),
            {"assets":{"ids":["first-page"],"complete":False}})

    def test_native_duplicate_or_corrupt_source_is_fail_closed(self):
        candidates=[
            {"isError":True,"content":[]},
            {"content":[]},
            {"content":[{"type":"image","data":"private"}]},
            {"content":[{"type":"text","text":"not JSON"}]},
            {"content":[{"type":"text","text":
                '{"assets":[],"assets":[],"count":0,"limitApplied":false}'}]},
            {"content":[{"type":"text","text":
                '{"assets":[],"count":NaN,"limitApplied":false}'}]},
            native_assets([{"id":"same"},{"id":"same"}]),
            native_assets([{"id":42}]),
            native_assets([{"id":"source"}],total=2,limited=False),
            native_assets([],total=5,limited=True),
            native_assets([{"id":"one"}],total=1,limited=True),
        ]
        for data in candidates:
            with self.subTest(data=str(data)[:50]),self.assertRaises(
                    NativeEditorAssetInventoryError):
                observed_editor_asset_ids(data)


    def test_malformed_native_transport_status_cannot_mint_asset_identity(self):
        # An unreadable/error-like native status must not create trusted IDs.
        valid = native_assets([{"id":"host-observed-source"}])
        for status in (
            {"isError":"false"}, {"isError":"true"}, {"isError":0},
            {"isError":None}, {"is_error":"false"}, {"is_error":1},
            {"isError":True}, {"is_error":True},
            {"isError":False,"is_error":True},
            {"isError":True,"is_error":False},
        ):
            with self.subTest(status=status), self.assertRaises(
                    NativeEditorAssetInventoryError):
                observed_editor_asset_ids({**valid, **status})

    def test_optional_boolean_native_success_status_is_compatible(self):
        valid = native_assets([{"id":"host-observed-source"}])
        for status in (
            {}, {"isError":False}, {"is_error":False},
            {"isError":False,"is_error":False},
        ):
            with self.subTest(status=status):
                observed = observed_editor_asset_ids({
                    **{k:v for k,v in valid.items() if k!="isError"},
                    **status,
                })
                self.assertEqual(
                    observed["assets"]["ids"], ["host-observed-source"])



class InstalledNativeAssetAdmissionTests(unittest.IsolatedAsyncioTestCase):
    class Editor:
        def __init__(self):
            self.allowed_tools={"get_assets":"read",
                                "add_assets_to_timeline":"write",
                                "replace_clip_with_asset":"write"}
            self.ids=["host-observed-original"]
            self.calls=[]
            self.inventory_error=None

        def list_tools(self):
            return [
                {"name":"get_assets","inputSchema":{"type":"object",
                    "properties":{}}},
                {"name":"add_assets_to_timeline",
                 "description":"Native batch edit of imported source IDs",
                 "inputSchema":{"type":"object","properties":{
                    "assetIds":{"type":"array","items":{"type":"string"}},
                    "assets":{"type":"array","items":{
                        "type":"object","properties":{
                            "assetId":{"type":"string"},"id":{"type":"string"}}}},
                    "previewOnly":{"type":"boolean"}}}},
                {"name":"replace_clip_with_asset",
                 "inputSchema":{"type":"object","properties":{
                    "assetId":{"type":"string"},
                    "replacementAssetId":{"type":"string"},
                    "clipId":{"type":"string"}}}},
            ]

        def call(self,name,arguments,*,allowed_access):
            self.calls.append((name,arguments,frozenset(allowed_access)))
            if name=="get_assets":
                if self.inventory_error:
                    raise self.inventory_error
                return native_assets([
                    {"id":value,"name":"owner private original"} for value in self.ids])
            if name in ("add_assets_to_timeline","replace_clip_with_asset"):
                return {"isError":False,"content":[{"type":"text",
                    "text":'{"success":true,"result":{"previewOnly":false}}'}]}
            raise AssertionError("Unexpected native operation")

    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.editor=self.Editor()
        self.path=Path(self.temp.name)/".zx7-host-private"/"capability-attempts.sqlite3"

    async def gateway(self, *, strict=True, durable=True):
        return await connect_installed_zx7_body(
            self.temp.name,editor_client=self.editor,
            allowed_access=("read","write"),
            durable_write_requests=durable,
            verify_native_editor_asset_ids=strict)

    async def test_real_registered_batch_write_uses_fresh_native_inventory_before_dispatch(self):
        gate=await self.gateway()
        rev=gate._current().revision
        event=await gate.invoke("zx7/body.editor.add_assets_to_timeline",
            revision=rev,inputs={"arguments":{
                "assetIds":["host-observed-original"],"previewOnly":False}},
            request_id="native-id-host-1")
        self.assertEqual(event["state"],"host_reported_success_unverified")
        self.assertEqual([x[0] for x in self.editor.calls],
            ["get_assets","add_assets_to_timeline"])
        self.assertEqual(self.editor.calls[0][2],frozenset({"read"}))
        self.assertEqual(self.editor.calls[1][2],frozenset({"write"}))
        self.assertEqual(CapabilityAttemptStore(self.path).inspect(
            "native-id-host-1")["state"],"host_reported_success_unverified")
        self.assertNotIn("host-observed-original",str(gate.evidence()))

    async def test_nested_model_hallucination_refused_before_any_edit_and_sqlite_intent(self):
        gate=await self.gateway()
        rev=gate._current().revision
        with self.assertRaisesRegex(
                CapabilityExecutionError,"native_reference_not_in_live_inventory"):
            await gate.invoke("zx7/body.editor.add_assets_to_timeline",
                revision=rev,inputs={"arguments":{"assets":[
                    {"assetId":"imaginary-source"}],"previewOnly":False}},
                request_id="native-fake-1")
        self.assertEqual([x[0] for x in self.editor.calls],["get_assets"])
        self.assertIsNone(CapabilityAttemptStore(self.path).inspect(
            "native-fake-1"))
        self.assertEqual(gate.evidence(),[])

    async def test_native_asset_removed_since_schema_discovery_is_refused(self):
        gate=await self.gateway()
        rev=gate._current().revision
        self.editor.ids=[]
        with self.assertRaises(CapabilityExecutionError):
            await gate.invoke("zx7/body.editor.replace_clip_with_asset",
                revision=rev,inputs={"arguments":{
                    "clipId":"owner-clip","replacementAssetId":"host-observed-original"}},
                request_id="stale-1")
        self.assertEqual([x[0] for x in self.editor.calls],["get_assets"])
        self.assertIsNone(CapabilityAttemptStore(self.path).inspect("stale-1"))

    async def test_private_native_inventory_failure_is_not_dispatched_or_echoed(self):
        gate=await self.gateway()
        self.editor.inventory_error=RuntimeError(
            "owner private source path /private/owner/secret-cinema.webm")
        with self.assertRaisesRegex(
                CapabilityExecutionError,"native_identity_inventory_unavailable") as caught:
            await gate.invoke("zx7/body.editor.add_assets_to_timeline",
                revision=gate._current().revision,
                inputs={"arguments":{"assetIds":["host-observed-original"]}},
                request_id="unobserved-1")
        self.assertNotIn("/private/owner",str(caught.exception))
        self.assertEqual([x[0] for x in self.editor.calls],["get_assets"])
        self.assertIsNone(CapabilityAttemptStore(self.path).inspect("unobserved-1"))

    async def test_missing_get_assets_host_read_grant_refuses_strict_policy_setup(self):
        self.editor.allowed_tools["get_assets"]="write"
        with self.assertRaisesRegex(ValueError,"get_assets READ"):
            await self.gateway()
        self.assertFalse(self.path.is_file())

    async def test_host_refuses_inert_or_malformed_native_policy_flag(self):
        for invalid in ("true",1,None):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                await connect_installed_zx7_body(
                    self.temp.name,editor_client=self.editor,
                    verify_native_editor_asset_ids=invalid)
        self.assertFalse(self.path.is_file())

    async def test_opt_in_does_not_break_existing_native_editor_adapter(self):
        gate=await self.gateway(strict=False, durable=False)
        rev=gate._current().revision
        # Legacy behavior remains explicit and is NOT described as ID-safe.
        outcome=await gate.invoke("zx7/body.editor.add_assets_to_timeline",
            revision=rev,inputs={"arguments":{
                "assetIds":["unverified-user-string"],"previewOnly":True}})
        self.assertEqual(outcome["state"],"host_reported_success_unverified")
        self.assertEqual([x[0] for x in self.editor.calls],
                         ["add_assets_to_timeline"])


if __name__=="__main__":
    unittest.main()
