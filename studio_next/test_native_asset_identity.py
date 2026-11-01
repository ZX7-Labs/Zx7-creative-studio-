"""Native asset identity evidence must come from real host inventory receipts."""
import json
import unittest

from .native_asset_identity import (NativeAssetEvidenceError,
                                    inventory_from_native_text,
                                    check_native_asset_reference)


class NativeAssetIdentityTests(unittest.TestCase):
    def test_empty_project_does_not_admit_staged_filename_as_imported_media(self):
        inventory = inventory_from_native_text([json.dumps({
            "assets": [], "totalAssetCount": 0, "returnedAssetCount": 0})])
        self.assertEqual(inventory["total"], 0)
        self.assertEqual(check_native_asset_reference(
            {"assetId": "native/add_asset_to_timeline", "assetName": "raw-gradient-0.mp4"},
            inventory), "native_project_has_no_imported_assets")

    def test_real_imported_media_identity_admits_correct_id(self):
        report = {"assets": [{"id":"asset:real-123","name":"raw-gradient-0.mp4"},
                             {"id":"asset:real-456","name":"shot.mp4"}],
                  "totalAssetCount":2,"returnedAssetCount":2}
        inventory = inventory_from_native_text([json.dumps(report)])
        self.assertIsNone(check_native_asset_reference(
            {"assetId":"asset:real-123","assetName":"gradient"}, inventory))
        self.assertEqual(check_native_asset_reference(
            {"assetId":"native/add_asset_to_timeline"}, inventory),
            "asset_id_not_in_native_inventory")
        self.assertEqual(check_native_asset_reference(
            {"assetName":"missing-asset.mp4"}, inventory),
            "asset_name_not_in_native_inventory")

    def test_truncated_native_inventory_is_not_claimed_complete(self):
        inventory = inventory_from_native_text([json.dumps({
            "assets":[{"id":"asset-a","name":"A"}],
            "totalAssetCount":8,"returnedAssetCount":1})])
        self.assertFalse(inventory["complete"])
        self.assertEqual(check_native_asset_reference(
            {"assetId":"asset-not-in-truncated-page"}, inventory),
            "native_asset_inventory_incomplete")

    def test_malformed_duplicate_conflicting_source_envelopes_are_rejected(self):
        cases = [
            '{}',
            '{"assets":[],"totalAssetCount":1,"returnedAssetCount":0}',
            '{"assets":[],"totalAssetCount":0,"returnedAssetCount":1}',
            '{"assets":[],"assets":[],"totalAssetCount":0,"returnedAssetCount":0}',
            '{"assets":[{"id":"same","name":"a"},{"id":"same","name":"b"}],'
            '"totalAssetCount":2,"returnedAssetCount":2}',
            '{"assets":[],"totalAssetCount":NaN,"returnedAssetCount":0}',
            '{"assets":[],"totalAssetCount":true,"returnedAssetCount":0}',
        ]
        for body in cases:
            with self.subTest(body=body):
                with self.assertRaises(NativeAssetEvidenceError):
                    inventory_from_native_text([body])


if __name__ == "__main__":
    unittest.main()
