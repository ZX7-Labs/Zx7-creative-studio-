"""Cross-domain explicit reference admission; all engine responses are fixtures.

This suite proves the host validates selected IDs against fresh, read-only
inventories before a stateful RPC. It does not certify real native editor/model
revisions or physical output fidelity.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from studio_next.capability_attempts import CapabilityAttemptStore
from studio_next.capability_gateway import CapabilityGateway,CapabilityExecutionError
from studio_next.capability_reference_guard import (
    CapabilityReferenceError,compile_reference_rules,validate_live_references)


class NativeReferenceGuardContracts(unittest.TestCase):
    def setUp(self):
        self.rules=compile_reference_rules({
            "/placements/*/assetId":"assets",
            "/placements/*/trackId":"tracks",
            "/scene/nodes/*/sourceObjectId":"objects"})
        self.snapshot={
            "assets":{"ids":["original-source-1","source-2"],"complete":True},
            "tracks":{"ids":["picture-1","audio-1"],"complete":True},
            "objects":{"ids":["mesh-1","rig-1"],"complete":True}}

    def test_valid_references_from_multiple_future_engine_domains(self):
        payload={"placements":[{"assetId":"original-source-1",
                                "trackId":"picture-1"},
                               {"assetId":"source-2","trackId":"audio-1"}],
                 "scene":{"nodes":[{"sourceObjectId":"mesh-1"},
                                   {"sourceObjectId":"rig-1"}]}}
        proof=validate_live_references(payload,self.rules,self.snapshot)
        self.assertEqual(proof["host_reference_checks_passed"],6)
        self.assertTrue(proof["host_source_snapshot_used"])
        self.assertFalse(proof["native_application_state_applied_or_verified"])

    def test_known_nested_source_does_not_mint_unobserved_graphics_object(self):
        with self.assertRaisesRegex(
                CapabilityReferenceError,"native_reference_not_in_live_inventory"):
            validate_live_references(
                {"placements":[{"assetId":"original-source-1",
                                "trackId":"invented-track"}]},self.rules,self.snapshot)

    def test_absent_id_in_partial_real_inventory_means_unknown_not_not_found(self):
        snapshot={**self.snapshot,"tracks":{
            "ids":["picture-1"],"complete":False}}
        with self.assertRaisesRegex(
                CapabilityReferenceError,"native_identity_inventory_incomplete"):
            validate_live_references(
                {"placements":[{"trackId":"unseen-audio-track"}]},
                self.rules,snapshot)
        proof=validate_live_references(
            {"placements":[{"trackId":"picture-1"}]},self.rules,snapshot)
        self.assertEqual(proof["host_reference_checks_passed"],1)

    def test_invalid_nested_reference_type_or_structure_rejected(self):
        cases=(
            {"placements":[{"assetId":None}]},
            {"placements":[{"assetId":True}]},
            {"placements":[{"assetId":""}]},
            {"placements":{"assetId":"source-2"}},
            {"scene":{"nodes":[17]}},
        )
        for value in cases:
            with self.subTest(value=str(value)),self.assertRaises(CapabilityReferenceError):
                validate_live_references(value,self.rules,self.snapshot)

    def test_empty_optional_rule_does_not_invent_mandatory_parameters(self):
        result=validate_live_references({"editName":"owner original"},
            self.rules,self.snapshot)
        self.assertEqual(result["host_reference_checks_passed"],0)

    def test_duplicate_or_malformed_native_snapshot_is_rejected(self):
        for value in (
            {"ids":["mesh-1","mesh-1"],"complete":True},
            {"ids":["mesh-1"],"complete":"true"},
            {"ids":[42],"complete":True},
            {"ids":[],"complete":None},
            {"ids":["a"*241],"complete":True},
        ):
            with self.subTest(value=str(value)),self.assertRaisesRegex(
                    CapabilityReferenceError,"invalid_host_reference_snapshot"):
                validate_live_references(
                    {"scene":{"nodes":[{"sourceObjectId":"mesh-1"}]}},
                    self.rules,{**self.snapshot,"objects":value})
        with self.assertRaisesRegex(
                CapabilityReferenceError,"native_identity_inventory_unavailable"):
            validate_live_references({},self.rules,{"assets":self.snapshot["assets"]})

    def test_bounded_batch_and_policy_paths_fail_closed(self):
        for rules in (
            {}, {"/../../untrusted":"assets"},
            {"/placements/*/*/*/*/*/*/*/*/*/*/*/*/*":"assets"},
            {"not-a-pointer":"assets"},
            {"/assets/*/assetId":"invalid kind with spaces"},
        ):
            with self.subTest(rules=str(rules)),self.assertRaises(CapabilityReferenceError):
                compile_reference_rules(rules)
        too_many={"placements":[{"assetId":"source-2"} for _ in range(1001)]}
        with self.assertRaisesRegex(
                CapabilityReferenceError,"native_reference_batch_exceeds_limit"):
            validate_live_references(too_many,self.rules,self.snapshot)


class StubInstalledCreativeEngine:
    def __init__(self):
        self.calls=[]
        self.schemas=[
            SimpleNamespace(name="place_object",description="Place exact existing native model object",
                input_schema={"type":"object","required":["placements"],
                    "properties":{"placements":{
                        "type":"array","minItems":1,
                        "items":{"type":"object","required":["objectId"],
                            "properties":{"objectId":{"type":"string"}},
                            "additionalProperties":False}}}})
        ]

    async def list_tools(self):
        return SimpleNamespace(tools=self.schemas)

    async def call_tool(self,name,args):
        self.calls.append((name,args))
        return SimpleNamespace(is_error=False,content=[
            SimpleNamespace(type="text",text='{"success":true}')])


class UniversalNativeObjectAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.home=tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.path=Path(self.home.name)/"private"/"native-intents.sqlite3"
        self.store=CapabilityAttemptStore(self.path)
        self.engine=StubInstalledCreativeEngine()
        self.ids=["real-blender-object"]
        self.read_count=0
        self.read_failure=None

    def real_read(self):
        self.read_count+=1
        if self.read_failure:
            raise self.read_failure
        return {"objects":{"ids":self.ids[:],"complete":True}}

    async def _gateway(self, *, attach_policy=True):
        binding=(self.engine,{"place_object":"write"},{},None,{})
        if attach_policy:
            binding+=({"reader":self.real_read,
                       "rules":{"place_object":{"/placements/*/objectId":"objects"}}},)
        gateway=CapabilityGateway({"geometry":binding},
            attempt_store=CapabilityAttemptStore(self.path))
        rev=(await gateway.refresh())["revision"]
        return gateway,rev

    async def test_genuine_host_read_precedes_each_permitted_native_write(self):
        gateway,rev=await self._gateway()
        payload={"placements":[{"objectId":"real-blender-object"}]}
        outcome=await gateway.invoke("geometry/place_object",
            revision=rev,inputs=payload,request_id="host-geometry-1")
        self.assertEqual(outcome["state"],"host_reported_success_unverified")
        self.assertEqual(len(self.engine.calls),1)
        self.assertEqual(self.read_count,1)
        self.assertEqual(self.store.inspect("host-geometry-1")["state"],
                         "host_reported_success_unverified")
        self.assertNotIn("real-blender-object",str(gateway.evidence()))
        self.assertFalse(gateway.unverified_native_writes()["attempts"][0]
                         ["native_application_state_independently_verified"])

    async def test_hallucinated_id_denied_before_native_dispatch_and_journal(self):
        gateway,rev=await self._gateway()
        with self.assertRaisesRegex(
                CapabilityExecutionError,"native_reference_not_in_live_inventory"):
            await gateway.invoke("geometry/place_object",revision=rev,
                inputs={"placements":[{"objectId":"model-invented-object"}]},
                request_id="host-forbidden-1")
        self.assertEqual(self.engine.calls,[])
        self.assertEqual(gateway.evidence(),[])
        self.assertIsNone(self.store.inspect("host-forbidden-1"))

    async def test_refreshed_host_inventory_revocation_invalidates_old_model_handle(self):
        gateway,rev=await self._gateway()
        self.ids=["different-native-object"]
        with self.assertRaises(CapabilityExecutionError):
            await gateway.invoke("geometry/place_object",revision=rev,
                inputs={"placements":[{"objectId":"real-blender-object"}]},
                request_id="host-stale-1")
        self.assertEqual(self.read_count,1)
        self.assertEqual(self.engine.calls,[])
        self.assertIsNone(self.store.inspect("host-stale-1"))

    async def test_host_inventory_read_failure_does_not_dispatch_or_admit(self):
        gateway,rev=await self._gateway()
        self.read_failure=ConnectionError("private original state reader offline")
        with self.assertRaises(ConnectionError):
            await gateway.invoke("geometry/place_object",revision=rev,
                inputs={"placements":[{"objectId":"real-blender-object"}]},
                request_id="host-offline-1")
        self.assertEqual(self.engine.calls,[])
        self.assertIsNone(self.store.inspect("host-offline-1"))

    async def test_invalid_policy_is_not_registered_as_a_connected_engine(self):
        for broken in (
            {"reader":"not callable","rules":{
                "place_object":{"/placements/*/objectId":"objects"}}},
            {"reader":self.real_read,"rules":{
                "place_object":{"wrong": "objects"}}},
            {"reader":self.real_read,"rules":{}},
        ):
            with self.subTest(broken=str(broken)),self.assertRaises(CapabilityExecutionError):
                CapabilityGateway({"geometry":(
                    self.engine,{"place_object":"write"},{},None,{},broken)})

    async def test_policy_is_opt_in_so_existing_engine_abi_is_unchanged(self):
        gateway,rev=await self._gateway(attach_policy=False)
        response=await gateway.invoke("geometry/place_object",revision=rev,
            inputs={"placements":[{"objectId":"legacy-opaque-id"}]},
            request_id="legacy-1")
        self.assertEqual(response["state"],"host_reported_success_unverified")
        self.assertEqual(self.read_count,0)
        self.assertEqual(len(self.engine.calls),1)


if __name__=="__main__":
    unittest.main()
