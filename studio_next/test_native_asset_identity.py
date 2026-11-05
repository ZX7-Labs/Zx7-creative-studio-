"""Host asset identity against the exact pinned Velorn get_assets JSON.

Velorn source electron/mcpServer.js @ b3c02adbd5c0779feb8abf34978299e9502cc0e7
returns count, limitApplied, assets. All responses in this test are
synthetic protocol fixtures, never evidence of actual imported camera media.
"""
import json
import unittest

from .native_asset_identity import (
    NativeAssetEvidenceError, inventory_from_native_text,
    check_native_asset_reference,
)


class NativeAssetIdentityTests(unittest.TestCase):
    def test_empty_project_does_not_admit_staged_filename_as_imported_media(self):
        inventory=inventory_from_native_text([json.dumps({
            "count":0,"limitApplied":False,"assets":[]})])
        self.assertEqual(inventory["total"],0)
        self.assertTrue(inventory["complete"])
        self.assertEqual(check_native_asset_reference(
            {"assetId":"native/add_asset_to_timeline","assetName":"staged.mp4"},
            inventory),"native_project_has_no_imported_assets")

    def test_real_source_transport_shape_admits_exact_native_asset_identity(self):
        report={
            "count":2,"limitApplied":False,
            "assets":[
                {"id":"asset:real-123","name":"original-camera.webm",
                 "type":"video","path":"/owner/private/stage","isImported":True},
                {"id":"asset:real-456","name":"artist-overlay.png",
                 "type":"image","path":"/owner/private/graph","isImported":True},
            ],
        }
        inventory=inventory_from_native_text([json.dumps(report)])
        self.assertEqual(inventory["total"],2)
        self.assertEqual(inventory["returned"],2)
        self.assertTrue(inventory["complete"])
        self.assertEqual(inventory["ids"],["asset:real-123","asset:real-456"])
        self.assertIsNone(check_native_asset_reference({
            "assetId":"asset:real-123","assetName":"camera"},inventory))
        self.assertEqual(check_native_asset_reference({
            "assetId":"native/add_asset_to_timeline"},inventory),
            "asset_id_not_in_native_inventory")
        self.assertEqual(check_native_asset_reference({
            "assetName":"missing.mp4"},inventory),
            "asset_name_not_in_native_inventory")
        self.assertNotIn("/owner/private",str(inventory))

    def test_incomplete_actual_native_inventory_does_not_invent_missing_asset(self):
        inventory=inventory_from_native_text([json.dumps({
            "count":8,"limitApplied":True,
            "assets":[{"id":"asset-a","name":"Camera A"}]})])
        self.assertFalse(inventory["complete"])
        self.assertEqual(inventory["total"],8)
        self.assertEqual(inventory["returned"],1)
        self.assertEqual(check_native_asset_reference({
            "assetId":"not-in-current-bounded-page"},inventory),
            "native_asset_inventory_incomplete")

    def test_legacy_imaginary_counts_are_rejected_instead_of_silent_adaptation(self):
        with self.assertRaises(NativeAssetEvidenceError):
            inventory_from_native_text([json.dumps({
                "assets":[],"totalAssetCount":0,"returnedAssetCount":0})])

    def test_malformed_or_contradictory_source_envelopes_are_rejected(self):
        cases=[
            '{}',
            '{"count":1,"limitApplied":false,"assets":[]}',
            '{"count":0,"limitApplied":false,"assets":[{"id":"one","name":"a"}]}',
            '{"count":1,"limitApplied":true,"assets":[{"id":"one","name":"a"}]}',
            '{"count":0,"limitApplied":true,"assets":[]}',
            '{"count":8,"limitApplied":true,"assets":[]}',
            '{"count":1,"limitApplied":"false","assets":[{"id":"one","name":"a"}]}',
            '{"count":0,"limitApplied":0,"assets":[]}',
            '{"count":true,"limitApplied":false,"assets":[]}',
            '{"count":NaN,"limitApplied":false,"assets":[]}',
            '{"assets":[],"assets":[],"count":0,"limitApplied":false}',
            '{"count":2,"limitApplied":false,"assets":['
             '{"id":"same","name":"a"},{"id":"same","name":"b"}]}',
            '{"count":1,"limitApplied":false,"assets":[{"id":1,"name":"a"}]}',
            '{"count":1,"limitApplied":false,"assets":[{"id":"a","name":null}]}',
        ]
        for body in cases:
            with self.subTest(body=body),self.assertRaises(NativeAssetEvidenceError):
                inventory_from_native_text([body])


if __name__=="__main__":
    unittest.main()
