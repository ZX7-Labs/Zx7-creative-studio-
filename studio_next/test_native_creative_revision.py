"""Adversarial native Velorn source-derived review contracts; no model simulation."""
from __future__ import annotations

import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from studio_next.native_creative_revision import (
    NativeRevisionReviewError, compare_native_revisions,
    load_native_revision, review_native_collaboration,
)


def example():
    # Shape follows the real native project.comfystudio save, not Film IR.
    return {
        "name": "Private production", "version": "1.0",
        "created": "2026-11-12T17:54:07.491Z", "modified": "initial",
        "settings": {"width": 640, "height": 360, "fps": 24},
        "currentTimelineId": "timeline-1",
        "assets": [{"id": "asset-A", "name": "owner-private-voice.wav",
                    "url": "file:///secret/owner/private-voice.wav"}],
        "flowAi": {"documents": []},
        "timelines": [{
            "id": "timeline-1", "name": "Owner story", "modified": "initial",
            "tracks": [
                {"id": "video-1", "type": "video", "name": "Picture"},
                {"id": "audio-1", "type": "audio", "name": "Sound"},
            ],
            "clips": [{
                "id": "clip-1", "trackId": "video-1",
                "assetId": None, "type": "text", "startTime": 0.0,
                "duration": 2.0,
                "textProperties": {"text": "SECRET CREATIVE BRIEF", "fontSize": 48},
                "keyframes": {"opacity": [{"time": 0, "value": 20},
                                         {"time": 2, "value": 100}]},
            }, {
                "id": "clip-2", "trackId": "audio-1",
                "assetId": "asset-A", "type": "audio",
                "startTime": 0.0, "duration": 2.0, "sourceDuration": 3.0,
                "transform": {"gain": 1.0},
            }],
            "transitions": [], "markers": [],
        }],
        "thumbnail": "file:///secret/owner/thumbnail.webp",
    }


class NativeRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = 0

    def save(self, payload, *, directory=False, raw=None):
        self.counter += 1
        parent = self.root / ("project-" + str(self.counter))
        parent.mkdir()
        path = parent / "project.comfystudio"
        if raw is None:
            raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        path.write_text(raw, encoding="utf-8")
        return parent if directory else path

    def test_real_native_shape_hashes_and_source_values_are_private(self):
        left = self.save(example(), directory=True)
        update = example()
        update["timelines"][0]["clips"][0]["textProperties"]["text"] = "PRESERVE UNPUBLISHED OWNER SCRIPT"
        update["modified"] = "new"
        right = self.save(update)
        before_bytes = (left / "project.comfystudio").read_bytes()
        after_bytes = right.read_bytes()
        result = compare_native_revisions(left, right)
        self.assertTrue(result["native_lineage_hint_only"])
        self.assertEqual(result["status"], "differences_observed")
        self.assertEqual(result["before"]["counts"]["clips"], 2)
        text_change = next(c for c in result["changes"]
                           if c["kind"] == "clip" and c["id"] == "clip-1")
        self.assertEqual(text_change["changed_fields"], ["/textProperties/text"])
        self.assertNotEqual(text_change["before_sha256"], text_change["after_sha256"])
        encoded = json.dumps(result)
        for secret in ("SECRET CREATIVE BRIEF", "PRESERVE UNPUBLISHED OWNER SCRIPT",
                       "owner-private-voice.wav", "/secret/owner"):
            self.assertNotIn(secret, encoded)
        self.assertFalse(result["impact"]["actual_media_decoded"])
        self.assertFalse(result["impact"]["creative_quality_assessed"])
        self.assertTrue(result["host_live_native_revision_CAS_still_required"])
        self.assertEqual(before_bytes, (left / "project.comfystudio").read_bytes())
        self.assertEqual(after_bytes, right.read_bytes())

    def test_changes_in_native_track_order_and_native_keyframes_are_not_lost(self):
        left = self.save(example())
        updated = example()
        timeline = updated["timelines"][0]
        timeline["tracks"].reverse()
        timeline["clips"][0]["keyframes"]["opacity"][1]["value"] = 52
        right = self.save(updated)
        result = compare_native_revisions(left, right)
        self.assertTrue(result["impact"]["native_order_review_required"])
        self.assertTrue(any(c["kind"] == "native_order" and c["id"] == "tracks"
                            for c in result["changes"]))
        curve = next(c for c in result["changes"]
                     if c["kind"] == "clip" and c["id"] == "clip-1")
        self.assertEqual(curve["changed_fields"], ["/keyframes/opacity"])

    def test_unknown_native_properties_remain_hash_visible_with_no_flattening(self):
        left = example()
        left["timelines"][0]["clips"][0]["futureShaderStack"] = {
            "private proprietary parameter": [1, 2, 3]}
        right = deepcopy(left)
        right["timelines"][0]["clips"][0]["futureShaderStack"][
            "private proprietary parameter"][1] = 9
        before = self.save(left)
        after = self.save(right)
        output = compare_native_revisions(before, after)
        changed = next(x for x in output["changes"] if x["kind"] == "clip")
        self.assertIn("/futureShaderStack/opaque_", changed["changed_fields"][0])
        self.assertNotIn("private proprietary parameter", json.dumps(output))
        self.assertNotIn("[1, 9, 3]", json.dumps(output))

    def test_three_way_disjoint_native_objects_do_not_claim_merge_authority(self):
        base = example()
        human, ai = deepcopy(base), deepcopy(base)
        human["timelines"][0]["clips"][0]["textProperties"]["text"] = "Human prose"
        human["modified"] = "H"
        ai["timelines"][0]["clips"][1]["transform"]["gain"] = 0.6
        ai["modified"] = "A"
        result = review_native_collaboration(
            self.save(base), self.save(human), self.save(ai))
        self.assertEqual(result["status"], "no_known_overlap")
        self.assertEqual(result["intersections"], [])
        self.assertFalse(result["automatic_merge_permitted"])
        self.assertTrue(result["live_native_revision_CAS_required_for_every_write"])

    def test_same_field_concurrent_human_and_ai_are_conflict_not_last_write_wins(self):
        base = example()
        human, ai = deepcopy(base), deepcopy(base)
        human["timelines"][0]["clips"][0]["textProperties"]["text"] = "Human"
        ai["timelines"][0]["clips"][0]["textProperties"]["text"] = "AI"
        result = review_native_collaboration(
            self.save(base), self.save(human), self.save(ai))
        self.assertEqual(result["status"], "conflicting_changes")
        self.assertEqual(result["intersections"][0]["kind"], "same_field_conflict")
        self.assertNotIn("Human", json.dumps(result))

    def test_shared_object_disjoint_fields_conservatively_need_review(self):
        base = example()
        human, ai = deepcopy(base), deepcopy(base)
        human["timelines"][0]["clips"][0]["textProperties"]["text"] = "Human"
        ai["timelines"][0]["clips"][0]["duration"] = 1.5
        output = review_native_collaboration(
            self.save(base), self.save(human), self.save(ai))
        self.assertEqual(output["status"], "needs_native_review")
        self.assertEqual(output["intersections"][0]["kind"], "same_object_needs_review")

    def test_overwriting_native_track_or_source_asset_dependency_needs_review(self):
        base = example()
        human, ai = deepcopy(base), deepcopy(base)
        human["timelines"][0]["tracks"][1]["name"] = "Human mix track"
        ai["timelines"][0]["clips"][1]["transform"]["gain"] = 0.5
        output = review_native_collaboration(
            self.save(base), self.save(human), self.save(ai))
        self.assertIn("track_clip_dependency",
                      {c["kind"] for c in output["intersections"]})
        human2, ai2 = deepcopy(base), deepcopy(base)
        human2["assets"][0]["url"] = "file:///secret/new-voice.wav"
        ai2["timelines"][0]["clips"][1]["duration"] = 1.0
        output2 = review_native_collaboration(
            self.save(base), self.save(human2), self.save(ai2))
        self.assertIn("asset_clip_dependency",
                      {c["kind"] for c in output2["intersections"]})

    def test_clip_ids_are_scoped_by_real_timeline_not_global(self):
        base = example()
        second = deepcopy(base["timelines"][0])
        second["id"] = "timeline-2"
        second["name"] = "Other scene with repeated native clip IDs"
        base["timelines"].append(second)
        base["currentTimelineId"] = "timeline-2"
        human, ai = deepcopy(base), deepcopy(base)
        human["timelines"][0]["clips"][0]["textProperties"]["text"] = "Human first timeline"
        ai["timelines"][1]["clips"][0]["textProperties"]["text"] = "AI second timeline"
        result = review_native_collaboration(
            self.save(base), self.save(human), self.save(ai))
        self.assertEqual(result["status"], "no_known_overlap")
        self.assertFalse(result["automatic_merge_permitted"])
        first = compare_native_revisions(self.save(base), self.save(human))
        clips = [c for c in first["changes"] if c["kind"] == "clip"]
        self.assertEqual([(c["timeline_id"], c["id"]) for c in clips],
                         [("timeline-1", "clip-1")])

    def test_human_track_reordering_and_ai_clip_edit_need_native_review(self):
        base = example()
        human, ai = deepcopy(base), deepcopy(base)
        human["timelines"][0]["tracks"].reverse()
        ai["timelines"][0]["clips"][0]["textProperties"]["fontSize"] = 66
        human_path, ai_path = self.save(human), self.save(ai)
        result = review_native_collaboration(
            self.save(base), human_path, ai_path)
        self.assertEqual(result["status"], "needs_native_review")
        self.assertIn("timeline_order_dependency",
                      {c["kind"] for c in result["intersections"]})
        self.assertTrue(result["human_source_or_render_recheck"])
        self.assertTrue(result["ai_source_or_render_recheck"])
        self.assertFalse(result["automatic_merge_permitted"])

    def test_active_timeline_switch_requires_actual_render_check(self):
        base = example()
        clone = deepcopy(base["timelines"][0])
        clone["id"] = "timeline-2"
        clone["name"] = "Second active scene"
        base["timelines"].append(clone)
        switched = deepcopy(base)
        switched["currentTimelineId"] = "timeline-2"
        output = compare_native_revisions(self.save(base), self.save(switched))
        self.assertEqual(output["status"], "differences_observed")
        self.assertTrue(output["impact"]["editable_native_changes_detected"])
        self.assertTrue(output["impact"]["source_custody_or_render_review_required"])
        self.assertTrue(output["impact"]["unmodeled_document_metadata_changed"])
        self.assertFalse(output["impact"]["actual_media_decoded"])

    def test_timestamp_only_save_is_not_an_edit_or_render_improvement(self):
        base = example()
        retimestamped = deepcopy(base)
        retimestamped["modified"] = "new-metadata-only"
        output = compare_native_revisions(
            self.save(base), self.save(retimestamped))
        self.assertNotEqual(output["before"]["sha256"],
                            output["after"]["sha256"])
        self.assertFalse(output["impact"]["editable_native_changes_detected"])
        self.assertFalse(output["impact"]["source_custody_or_render_review_required"])
        self.assertTrue(output["impact"]["unmodeled_document_metadata_changed"])

    def test_identical_human_and_ai_changes_do_not_fabricate_conflict(self):
        base = example()
        human = deepcopy(base)
        human["timelines"][0]["clips"][0]["duration"] = 1.5
        ai = deepcopy(human)
        output = review_native_collaboration(
            self.save(base), self.save(human), self.save(ai))
        self.assertEqual(output["status"], "no_known_overlap")
        self.assertEqual(output["intersections"], [])

    def test_different_created_or_unrelated_native_projects_refuse_three_way(self):
        base = example()
        other = deepcopy(base)
        other["created"] = "unrelated"
        with self.assertRaisesRegex(NativeRevisionReviewError, "origin is unproven"):
            review_native_collaboration(
                self.save(base), self.save(other), self.save(base))

    def test_native_invariant_failures_are_not_silently_declared_valid(self):
        invalid = []
        a = example()
        a["timelines"][0]["clips"][0]["trackId"] = "nonexistent"
        invalid.append(a)
        b = example()
        b["timelines"][0]["clips"][1]["assetId"] = "wrong-asset"
        invalid.append(b)
        c = example()
        c["timelines"][0]["clips"].append(deepcopy(c["timelines"][0]["clips"][0]))
        invalid.append(c)
        d = example()
        d["currentTimelineId"] = "not-a-timeline"
        invalid.append(d)
        e = example()
        e["version"] = ""
        invalid.append(e)
        f = example()
        f["assets"][0]["id"] = "../../private/secret"
        invalid.append(f)
        for value in invalid:
            with self.subTest(index=len(str(value))):
                with self.assertRaises(NativeRevisionReviewError):
                    load_native_revision(self.save(value))

    def test_no_forged_json_duplicates_nonfinite_or_excessive_depth(self):
        for raw in ('{"version":"1","version":"2"}',
                    '{"version":NaN}',
                    '{"version":"1.0","assets":[],"timelines":[],"opacity":1e999}',
                    '{"foo":' + "[" * 45 + "0" + "]" * 45 + "}"):
            with self.subTest(raw=raw[:25]):
                with self.assertRaises(NativeRevisionReviewError):
                    load_native_revision(self.save({}, raw=raw))

    def test_symlink_file_and_ancestor_are_rejected(self):
        native = self.save(example())
        target = self.root / "redirect.comfystudio"
        target.symlink_to(native)
        with self.assertRaisesRegex(NativeRevisionReviewError, "symbolic link"):
            load_native_revision(target)
        alias = self.root / "alias"
        alias.symlink_to(native.parent, target_is_directory=True)
        with self.assertRaisesRegex(NativeRevisionReviewError, "symbolic link"):
            load_native_revision(alias / "project.comfystudio")

    def test_changed_fingerprint_distinguishes_different_native_bytes(self):
        a = example()
        b = deepcopy(a)
        b["modified"] = "new-version"
        one = load_native_revision(self.save(a))
        two = load_native_revision(self.save(b))
        self.assertNotEqual(one.sha256, two.sha256)
        self.assertEqual(one.counts, two.counts)

    def test_cli_runs_without_model_network_or_creative_edits(self):
        from studio_next.studio_cli import main
        base = example()
        human = deepcopy(base)
        human["timelines"][0]["clips"][0]["textProperties"]["text"] = "Change"
        ai = deepcopy(base)
        ai["timelines"][0]["clips"][1]["transform"]["gain"] = 0.75
        p0, p1, p2 = self.save(base), self.save(human), self.save(ai)
        for command, expected in (
            (["compare-native", str(p0), str(p1)], "differences_observed"),
            (["review-native", str(p0), str(p1), str(p2)], "no_known_overlap"),
        ):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(command), 0)
            self.assertEqual(json.loads(out.getvalue())["status"], expected)


if __name__ == "__main__":
    unittest.main()
