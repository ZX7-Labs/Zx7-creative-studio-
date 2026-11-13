# SPDX-License-Identifier: GPL-3.0-only
"""Saved native clip IDs are scoped to an explicitly observed timeline."""
import json
from pathlib import Path
import tempfile
import unittest

from native_save_interleave_flow import saved_clip


class NativeSavedTimelineIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zx7-native-save-id-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "project.comfystudio"
        self.doc = {
            "modified": "2026-11-13T18:00:00.000Z",
            "currentTimelineId": "selected-scene",
            "timelines": [
                {"id": "earlier-scene", "clips": [{"id": "clip-one", "startTime": 0.2}]},
                {"id": "selected-scene", "clips": [{"id": "clip-one", "startTime": 2.25}]},
            ],
        }

    def write(self):
        self.path.write_text(json.dumps(self.doc), encoding="utf-8")

    def test_duplicate_clip_ids_in_distinct_timelines_select_only_active_scene(self):
        self.write()
        clip, stamp = saved_clip(self.path, "clip-one", "selected-scene")
        self.assertEqual(clip["startTime"], 2.25)
        self.assertEqual(stamp, self.doc["modified"])

    def test_clip_id_missing_in_selected_timeline_rejected(self):
        self.write()
        with self.assertRaisesRegex(AssertionError, "missing or duplicated"):
            saved_clip(self.path, "not-in-scene", "selected-scene")

    def test_duplicate_clip_ids_inside_selected_timeline_rejected(self):
        self.doc["timelines"][1]["clips"].append(
            {"id": "clip-one", "startTime": 3})
        self.write()
        with self.assertRaisesRegex(AssertionError, "missing or duplicated"):
            saved_clip(self.path, "clip-one", "selected-scene")

    def test_native_project_switched_timeline_after_observation_rejected(self):
        self.write()
        with self.assertRaisesRegex(AssertionError, "active timeline changed"):
            saved_clip(self.path, "clip-one", "earlier-scene")


if __name__ == "__main__":
    unittest.main()
