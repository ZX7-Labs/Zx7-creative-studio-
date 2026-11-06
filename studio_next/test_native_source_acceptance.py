"""Prove real licensed source footage rather than a synthetic empty edit."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from studio_next.native_source_acceptance import (
    verify_original_footage_on_native_timeline)


class PhysicalNativeSourceAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sources = self.root / "staging"
        self.projects = self.root / "projects"
        self.sources.mkdir()
        self.projects.mkdir()
        self.src = self.sources / "original.mp4"
        self.src.write_bytes(b"original-owner-footage-content")
        self.owned = self.projects / "Movie"
        self.owned.mkdir()
        (self.owned / "media").mkdir()
        self.copy = self.owned / "media" / "original.mp4"
        self.copy.write_bytes(self.src.read_bytes())
        self.saved = self.owned / "project.comfystudio"
        self.manifest = [{"path": str(self.src),
                          "sha256": hashlib.sha256(
                              self.src.read_bytes()).hexdigest(),
                          "rights": "generated original owner media"}]
        self.project = {
            "assets": [{"id": "native-asset-12", "name": "Original",
                        "type": "video", "absolutePath": str(self.copy),
                        "settings": {"sourcePath": str(self.src),
                                     "importedViaMcp": True}}],
            "currentTimelineId": "native-timeline-1",
            "timelines": [{"id": "native-timeline-1", "duration": 60.0,
                           "tracks": [{"id": "video-1", "type": "video",
                                       "visible": True}], "clips": [{
                "id": "native-clip-88", "assetId": "native-asset-12",
                "type": "video", "trackId": "video-1",
                "startTime": 0, "duration": 4.0}]}],
        }
        self.save()
        self._original_project = copy.deepcopy(self.project)

    def save(self):
        self.saved.write_text(json.dumps(self.project), encoding="utf-8")

    def verify(self, export_windows=None):
        return verify_original_footage_on_native_timeline(
            self.projects, [self.saved], self.manifest,
            host_verified_export_windows=export_windows)

    def test_original_imported_video_must_have_physical_project_copy_and_clip(self):
        receipt = self.verify()
        self.assertTrue(receipt["actual_original_video_used_on_native_timeline"])
        self.assertEqual(receipt["physically_verified_native_source_clip_count"], 1)
        self.assertFalse(receipt["professional_artistic_quality_approved"])
        self.assertEqual(receipt["verified_native_source_clip_proof"][0][
            "source_sha256"], self.manifest[0]["sha256"])

    def test_original_source_clip_must_overlap_actual_export_window(self):
        # Pinned renderer may extend a full export beyond timeline.duration;
        # the *actual verified output interval* is the correct acceptance bound.
        # A caller-supplied render at [0,60) excludes later original media.
        clip = self.project["timelines"][0]["clips"][0]
        for start, visible in ((60, False), (3600, False), (-10, False),
                               (-2, True), (59, True), (0, True)):
            with self.subTest(start=start):
                clip["startTime"] = start
                self.save()
                self.assertEqual(self.verify([{
                    "start_seconds": 0, "end_seconds": 60
                }])["actual_original_video_used_on_native_timeline"], visible)

    def test_completely_transparent_native_source_does_not_count_as_visible(self):
        # Pinned exporter treats transform.opacity as percent, so zero
        # hides the imported footage even when its track is visible.
        clip = self.project["timelines"][0]["clips"][0]
        for value in (0, -1, float("nan"), "0", None):
            with self.subTest(opacity=repr(value)):
                clip["transform"] = {"opacity": value}
                self.save()
                self.assertFalse(self.verify([{
                    "start_seconds": 0, "end_seconds": 4
                }])["actual_original_video_used_on_native_timeline"])
        clip["transform"] = {"opacity": 55}
        self.save()
        self.assertTrue(self.verify([{
            "start_seconds": 0, "end_seconds": 4
        }])["actual_original_video_used_on_native_timeline"])

    def test_multiple_placed_clips_using_same_original_count_separately(self):
        timeline = self.project["timelines"][0]
        second = copy.deepcopy(timeline["clips"][0])
        second["id"] = "native-clip-89"
        second["startTime"] = 6
        timeline["clips"].append(second)
        self.save()
        proof = self.verify([{"start_seconds": 0, "end_seconds": 10}])
        self.assertTrue(proof["actual_original_video_used_on_native_timeline"])
        self.assertEqual(proof["physically_verified_native_source_clip_count"], 2)
        self.assertEqual(
            {item["native_clip_id"] for item in
             proof["verified_native_source_clip_proof"]},
            {"native-clip-88", "native-clip-89"})
        partial = self.verify([{"start_seconds": 6, "end_seconds": 8}])
        self.assertEqual(partial["physically_verified_native_source_clip_count"], 1)
        self.assertEqual(partial["verified_native_source_clip_proof"][0][
            "native_clip_id"], "native-clip-89")

    def test_pinned_editor_full_export_extends_past_timeline_duration(self):
        # electron/mcpServer.js uses max(timeline.duration, all clip ends)
        # when range=full. Do not reject genuine media at second 3600 just
        # because the saved project timeline's nominal duration is 60.
        self.project["timelines"][0]["clips"][0]["startTime"] = 3600
        self.save()
        self.assertTrue(self.verify()[
            "actual_original_video_used_on_native_timeline"])
        self.assertFalse(self.verify([{
            "start_seconds": 0, "end_seconds": 60
        }])["actual_original_video_used_on_native_timeline"])
        self.assertTrue(self.verify([{
            "start_seconds": 3600, "end_seconds": 3604
        }])["actual_original_video_used_on_native_timeline"])

    def test_verified_export_windows_fail_closed_on_invalid_or_unseen_output(self):
        self.assertFalse(self.verify([])[
            "actual_original_video_used_on_native_timeline"])
        for windows in (
            "all", [{"start_seconds": True, "end_seconds": 60}],
            [{"start_seconds": 0, "end_seconds": 0}],
            [{"start_seconds": 60, "end_seconds": 4}],
            [{"start_seconds": 0, "end_seconds": float("inf")}],
            [{"start_seconds": 0, "end_seconds": 60, "path": "/private"}],
        ):
            with self.subTest(windows=repr(windows)):
                with self.assertRaisesRegex(ValueError, "export"):
                    self.verify(windows)
        self.assertFalse(self.verify([{
            "start_seconds": 4, "end_seconds": 8
        }])["actual_original_video_used_on_native_timeline"])
        self.assertTrue(self.verify([{
            "start_seconds": 3, "end_seconds": 8
        }])["actual_original_video_used_on_native_timeline"])

    def test_malformed_source_time_and_active_duration_fail_closed(self):
        clip = self.project["timelines"][0]["clips"][0]
        for start in ("0", True, None, float("nan"), float("inf")):
            with self.subTest(start=repr(start)):
                clip["startTime"] = start
                self.save()
                self.assertFalse(self.verify()[
                    "actual_original_video_used_on_native_timeline"])
        clip["startTime"] = 0
        for duration in (None, 0, -1, float("nan"), float("inf")):
            with self.subTest(duration=repr(duration)):
                self.project["timelines"][0]["duration"] = duration
                self.save()
                with self.assertRaisesRegex(ValueError, "duration"):
                    self.verify()

    def test_original_media_in_project_but_not_on_timeline_is_not_editing(self):
        self.project["timelines"][0]["clips"] = []
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_markers_text_titles_and_synthetic_visuals_cannot_replace_source(self):
        self.project["timelines"][0]["clips"] = [{
            "id": "text-clip", "type": "text", "assetId": "native-asset-12",
            "startTime": 0, "duration": 4.0}]
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_dormant_timeline_is_not_the_current_delivered_movie(self):
        self.project["timelines"][0]["id"] = "unused-timeline"
        self.project["timelines"].append({
            "id": "native-timeline-1", "duration": 60.0,
            "tracks": [{"id": "video-1", "type": "video", "visible": True}],
            "clips": []})
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_disabled_clip_or_hidden_track_does_not_prove_visible_source(self):
        current = self.project["timelines"][0]
        current["clips"][0]["enabled"] = False
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])
        current["clips"][0]["enabled"] = True
        current["tracks"][0]["visible"] = False
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])
        current["tracks"][0]["visible"] = True
        current["clips"][0]["trackId"] = "invented-video-track"
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_spoofed_provenance_without_import_refused(self):
        self.project["assets"][0]["settings"]["importedViaMcp"] = False
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_wrong_or_missing_copy_refused_even_if_asset_path_looks_native(self):
        self.copy.write_bytes(b"other-content")
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])
        self.copy.unlink()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_external_symlink_or_direct_source_path_is_not_project_copy(self):
        self.project["assets"][0]["absolutePath"] = str(self.src)
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])
        link = self.owned / "media" / "link.mp4"
        link.symlink_to(self.src)
        self.project["assets"][0]["absolutePath"] = str(link)
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_untrusted_project_metadata_cannot_select_extra_host_paths(self):
        self.project["assets"][0]["settings"]["sourcePath"] = (
            "/not-owner-provided/unrelated-private-file.mp4")
        self.save()
        result = self.verify()
        self.assertFalse(result["actual_original_video_used_on_native_timeline"])

    def test_changed_original_hash_fails_closed(self):
        self.src.write_bytes(b"changed-after-attestation")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.verify()

    def test_empty_or_invented_manifest_never_approves_film(self):
        self.assertFalse(verify_original_footage_on_native_timeline(
            self.projects, [self.saved], [])[
                "actual_original_video_used_on_native_timeline"])
        with self.assertRaises(ValueError):
            verify_original_footage_on_native_timeline(
                self.projects, [self.saved],
                [{"path": str(self.src), "sha256": "x" * 64}])

    def test_ambiguous_native_asset_timeline_track_and_clip_ids_are_not_proof(self):
        # An editor may resolve duplicate IDs differently from the acceptance
        # verifier. Reject every ambiguity instead of selecting a favorable one.
        for category in ("asset", "timeline", "track", "clip"):
            with self.subTest(category=category):
                project = copy.deepcopy(self._original_project)
                timeline = project["timelines"][0]
                if category == "asset":
                    project["assets"].append({
                        "id": project["assets"][0]["id"],
                        "type": "video", "settings": {}})
                elif category == "timeline":
                    project["timelines"].append({
                        "id": timeline["id"], "tracks": [], "clips": []})
                elif category == "track":
                    timeline["tracks"].append({
                        "id": timeline["tracks"][0]["id"],
                        "type": "video", "visible": False})
                else:
                    timeline["clips"].append({
                        "id": timeline["clips"][0]["id"], "type": "text",
                        "startTime": 0, "duration": 4.0})
                self.project = project
                self.save()
                with self.assertRaisesRegex(ValueError, "ambiguous"):
                    self.verify()

    def test_nonboolean_visibility_and_enabled_values_are_not_visible_proof(self):
        # The upstream JS editor uses `!== false` for fallback display;
        # this verifier deliberately requires actual booleans to reject
        # malformed saved project state instead of relying on coercion.
        for field in ("track", "clip"):
            for falsey_value in (0, "", None, []):
                with self.subTest(field=field, value=falsey_value):
                    self.project = copy.deepcopy(self._original_project)
                    timeline = self.project["timelines"][0]
                    if field == "track":
                        timeline["tracks"][0]["visible"] = falsey_value
                    else:
                        timeline["clips"][0]["enabled"] = falsey_value
                    self.save()
                    self.assertFalse(
                        self.verify()["actual_original_video_used_on_native_timeline"])

    def test_nonfinite_or_missing_source_clip_start_cannot_prove_use(self):
        for bad_start in (float("nan"), float("inf"), float("-inf"), "0", None):
            with self.subTest(start=repr(bad_start)):
                self.project = copy.deepcopy(self._original_project)
                self.project["timelines"][0]["clips"][0]["startTime"] = bad_start
                # JSON NaN/Infinity are nonstandard but are sometimes written
                # by permissive serializers; saved acceptance must fail closed.
                self.save()
                self.assertFalse(
                    self.verify()["actual_original_video_used_on_native_timeline"])
        self.project = copy.deepcopy(self._original_project)
        self.project["timelines"][0]["clips"][0].pop("startTime")
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_negative_start_is_not_automatically_invalid(self):
        # A clip can cross timeline time zero: -1 start + 4 duration
        # yields 3 seconds of visible footage. Temporal-overlap validation
        # belongs to the independent active-duration gate.
        self.project["timelines"][0]["clips"][0]["startTime"] = -1
        self.save()
        self.assertTrue(
            self.verify()["actual_original_video_used_on_native_timeline"])

    def test_nonfinite_or_non_numeric_source_clip_duration_cannot_prove_use(self):
        for bad_duration in (float("nan"), float("inf"), float("-inf"), "4", None):
            with self.subTest(duration=repr(bad_duration)):
                self.project = copy.deepcopy(self._original_project)
                self.project["timelines"][0]["clips"][0]["duration"] = bad_duration
                self.save()
                self.assertFalse(
                    self.verify()["actual_original_video_used_on_native_timeline"])

    def test_hardlinked_original_is_not_an_independent_project_owned_copy(self):
        # Equal digest and an in-root path are insufficient when the native
        # project media inode is literally the owner's original video.
        self.copy.unlink()
        try:
            os.link(self.src, self.copy)
        except OSError as exc:
            self.skipTest(f"Filesystem cannot create a hardlink fixture: {exc}")
        self.assertTrue(os.path.samefile(self.src, self.copy))
        self.assertFalse(
            self.verify()["actual_original_video_used_on_native_timeline"])

    def test_duplicate_json_fields_cannot_choose_favorable_provenance(self):
        # Upstream JSON.stringify does not emit duplicates. A manually forged
        # native receipt with duplicate project fields is ambiguous.
        text = self.saved.read_text(encoding="utf-8")
        anchor = '"currentTimelineId": "native-timeline-1"'
        self.assertIn(anchor, text)
        self.saved.write_text(
            text.replace(anchor, anchor + ', ' + anchor, 1),
            encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            self.verify()

    def test_export_window_is_not_attributable_across_two_saved_projects(self):
        # A valid original clip in an unrelated project cannot prove the
        # actually rendered movie from another project contains that clip.
        sibling = self.projects / "second-project"
        sibling.mkdir()
        second = sibling / "project.comfystudio"
        second.write_text(json.dumps({
            "currentTimelineId": "other-active-timeline",
            "assets": [], "timelines": [{
                "id": "other-active-timeline", "duration": 4.0,
                "tracks": [], "clips": []
            }]
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            verify_original_footage_on_native_timeline(
                self.projects, [self.saved, second], self.manifest,
                host_verified_export_windows=[
                    {"start_seconds": 0, "end_seconds": 4}])
        # No delivered movie => still no positive proof, even with multiple
        # projects. This is not a restriction on normal native editing.
        for path in (self.saved, second):
            self.assertFalse(verify_original_footage_on_native_timeline(
                self.projects, [path], self.manifest,
                host_verified_export_windows=[])[
                    "actual_original_video_used_on_native_timeline"])

    def test_oversize_project_is_refused_before_json_decode(self):
        # Sparse on-disk fixture avoids allocating an enormous Python string.
        with self.saved.open("wb") as target:
            target.truncate(32 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(ValueError, "size limit"):
            self.verify()

    def test_project_path_escape_and_corrupt_native_project_refused(self):
        outside = self.root / "project.comfystudio"
        outside.write_text(json.dumps(self.project))
        with self.assertRaisesRegex(ValueError, "outside"):
            verify_original_footage_on_native_timeline(
                self.projects, [outside], self.manifest)
        self.saved.write_text('{"assets":[],"timelines":null}')
        with self.assertRaises(ValueError):
            self.verify()


if __name__ == "__main__":
    unittest.main()
