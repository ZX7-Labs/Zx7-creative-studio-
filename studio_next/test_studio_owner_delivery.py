"""Owner-level physical delivery acceptance tests; no model results are fabricated as art."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next import studio_cli
from studio_next.native_render_evidence import REVIEWED_AV_PAIR, destination_digest, timeline_scope_digest
from studio_next.studio_owner_delivery import (
    verify_owner_audiovisual_delivery, _verify_native_project_media_closure,
    _verify_staged_sources)


class OwnerAudiovisualDeliveryTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("Requires installed FFmpeg and FFprobe, not fake media")
        self.temp = tempfile.TemporaryDirectory(prefix="zx7-owner-av-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.source = base / "editor-source"
        self.source.mkdir()
        self.workspace = base / "owner"
        studio_cli.initialize_workspace(
            self.workspace, source=self.source, model_id="offline-test-model")
        self.sid = "a" * 24
        self.session = self.workspace / "sessions" / self.sid
        self.session.mkdir(mode=0o700)
        self.output_root = self.workspace / "outputs" / self.sid
        self.output_root.mkdir(mode=0o700)
        self.staging = self.workspace / "staging" / self.sid
        self.staging.mkdir(mode=0o700)
        self.project = self.workspace / "projects" / "editable-native"
        self.project.mkdir(mode=0o700)
        self.native = self.project / "project.comfystudio"
        self.initial_doc = {
            "currentTimelineId": "timeline-1",
            "timelines": [{"id": "timeline-1", "clips": [
                {"id": "original", "trackId": "video-track",
                 "name": "before revision"}]}],
        }
        self.final_doc = {
            "currentTimelineId": "timeline-1",
            "timelines": [{"id": "timeline-1", "clips": [
                {"id": "original", "trackId": "video-track",
                 "name": "after revision"}]}],
        }
        self.native.write_text(json.dumps(self.final_doc))
        self.media = [self.output_root / "first.mp4",
                      self.output_root / "revised.mp4"]
        for colour, output in (("navy", self.media[0]), ("red", self.media[1])):
            subprocess.run([
                "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi",
                "-i", f"color=c={colour}:s=64x36:r=24:d=0.5",
                "-f", "lavfi", "-i",
                "sine=frequency=440:sample_rate=48000:duration=0.5",
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                str(output),
            ], check=True, timeout=30)
        # The verifier must prove a usable source-backed native PROJECT,
        # not only an intact .comfystudio JSON and a previously rendered MP4.
        self.project_media = self.project / "assets" / "video" / "owner-source.mp4"
        self.project_media.parent.mkdir(parents=True)
        shutil.copyfile(self.media[0], self.project_media)
        self.media_id = "native-asset-original"
        for doc in (self.initial_doc, self.final_doc):
            doc["assets"] = [{
                "id": self.media_id, "type": "video",
                "name": "owner-source.mp4",
                "path": "assets/video/owner-source.mp4",
                "size": self.project_media.stat().st_size,
            }]
            doc["timelines"][0]["clips"][0].update({
                "type": "video", "assetId": self.media_id,
            })
        self.native.write_text(json.dumps(self.final_doc))
        self.original = self.staging / "owner-source.mp4"
        self.original.write_bytes(b"owner original bytes; not used as a pretend neural edit")
        studio_cli._write_new(self.session / "sources.json", [{
            "path": str(self.original),
            "sha256": hashlib.sha256(self.original.read_bytes()).hexdigest(),
            "bytes": self.original.stat().st_size,
            "rights": "synthetic fixture generated inside this test",
            "rights_independently_verified": False,
        }])
        scope = timeline_scope_digest(str(self.project), "timeline-1")
        self.pair = [
            {"destination_sha256": destination_digest(str(path)),
             "export_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
             "timeline_sha256": scope}
            for path in self.media]
        self.snapshots = self.workspace / "state" / self.sid / "av-project-snapshots"
        self.snapshots.mkdir(parents=True, mode=0o700)
        self.snapshot_hashes = []
        for binding, doc in zip(self.pair, (self.initial_doc, self.final_doc), strict=True):
            raw = json.dumps(doc)
            (self.snapshots / (binding["destination_sha256"] + ".comfystudio")).write_text(raw)
            self.snapshot_hashes.append(hashlib.sha256(raw.encode("utf-8")).hexdigest())
        media_sha = _verify_native_project_media_closure(
            self.project, self.final_doc)["native_media_observation_sha256"]
        self.status = {
            "session_id": self.sid, "state": "completed",
            "render_snapshots_required": True,
            "result": {"status": "model_finished_unverified",
                       "evaluation_evidence_satisfied": True,
                       "required_evaluation_evidence": [REVIEWED_AV_PAIR],
                       "reviewed_native_audiovisual_pair": self.pair,
                       "reviewed_native_snapshot_sha256": self.snapshot_hashes,
                       "reviewed_native_media_sha256": [media_sha, media_sha]},
        }
        studio_cli._write_status(self.session, self.status)

    def verify(self):
        return verify_owner_audiovisual_delivery(
            self.workspace, self.sid, max_decode_seconds=30)

    def test_owner_technical_delivery_uses_fresh_full_decode_and_editable_native_project(self):
        status_before = (self.session / "status.json").read_bytes()
        native_before = self.native.read_bytes()
        report = self.verify()
        self.assertTrue(report["physical_audiovisual_pair_verified"])
        self.assertEqual(report["owner_stated_original_count"], 1)
        self.assertTrue(report["source_staging_sha256_verified"])
        self.assertTrue(report["saved_native_matches_last_render_snapshot"])
        self.assertTrue(report["native_media_source_closure_verified"])
        self.assertTrue(report["native_media_matches_final_render_capture"])
        self.assertTrue(report["render_snapshot_media_closure_verified"])
        self.assertEqual(report["native_media_asset_inventory_count"], 1)
        self.assertEqual(report["native_media_used_asset_count"], 1)
        self.assertFalse(report["native_media_origin_or_export_contribution_proven"])
        self.assertFalse(report["native_render_snapshot_match_not_tested"])
        self.assertFalse(report["owner_rights_independently_verified"])
        self.assertFalse(report["original_media_visible_in_exports_proven"])
        self.assertFalse(report["artistic_quality_independently_approved"])
        self.assertFalse(report["model_autonomy_independently_evaluated"])
        self.assertEqual(len(report["rendered_exports"]), 2)
        self.assertEqual(report["editable_native_project_relative_to_workspace"],
                         "projects/editable-native/project.comfystudio")
        self.assertEqual(report["editable_native_project_sha256"],
                         hashlib.sha256(native_before).hexdigest())
        self.assertTrue(all(item["audio_decoded_and_non_silent"]
                            for item in report["rendered_exports"]))
        self.assertEqual((self.session / "status.json").read_bytes(), status_before)
        self.assertEqual(self.native.read_bytes(), native_before)
        self.assertEqual(self.original.read_bytes(),
                         b"owner original bytes; not used as a pretend neural edit")

    def _two_revisions_with_distinct_original_media(self):
        """Legitimate revision: new native asset, old asset still retained."""
        first_media = self.project / "assets" / "video" / "first-revision-source.mp4"
        shutil.copyfile(self.project_media, first_media)
        self.initial_doc["assets"][0]["path"] = "assets/video/first-revision-source.mp4"
        first_sha = _verify_native_project_media_closure(
            self.project, self.initial_doc)["native_media_observation_sha256"]
        first_snapshot = self.snapshots / (
            self.pair[0]["destination_sha256"] + ".comfystudio")
        raw = json.dumps(self.initial_doc).encode("utf-8")
        first_snapshot.write_bytes(raw)
        self.status["result"]["reviewed_native_snapshot_sha256"][0] = (
            hashlib.sha256(raw).hexdigest())
        self.status["result"]["reviewed_native_media_sha256"][0] = first_sha
        studio_cli._write_status(self.session, self.status)
        return first_media

    def test_first_and_final_revisions_with_distinct_retained_sources_remain_portable(self):
        first_media = self._two_revisions_with_distinct_original_media()
        report = self.verify()
        self.assertTrue(report["saved_native_matches_last_render_snapshot"])
        self.assertTrue(first_media.is_file())
        self.assertTrue(report["render_snapshot_media_closure_verified"])

    def test_first_revision_missing_source_cannot_be_reported_as_portable(self):
        first_media = self._two_revisions_with_distinct_original_media()
        first_media.unlink()
        with self.assertRaisesRegex(ValueError, "source media|snapshot source"):
            self.verify()

    def test_first_revision_same_size_media_replacement_cannot_pass(self):
        first_media = self._two_revisions_with_distinct_original_media()
        first_media.write_bytes(b"Z" * first_media.stat().st_size)
        with self.assertRaisesRegex(ValueError, "source media|snapshot source"):
            self.verify()

    def test_owner_explicit_delivery_profile_must_match_both_decoded_movies(self):
        requested = {"width": 64, "height": 36, "duration_seconds": 0.5}
        self.status["owner_delivery_target"] = requested
        studio_cli._write_status(self.session, self.status)
        accepted = self.verify()
        self.assertTrue(accepted["owner_delivery_profile_verified"])
        self.assertEqual(accepted["owner_delivery_target"], requested)
        for wrong in (
            {"width": 640, "height": 36, "duration_seconds": 0.5},
            {"width": 64, "height": 360, "duration_seconds": 0.5},
            {"width": 64, "height": 36, "duration_seconds": 6.0},
        ):
            with self.subTest(target=wrong):
                studio_cli._write_status(
                    self.session, {**self.status, "owner_delivery_target": wrong})
                with self.assertRaisesRegex(ValueError, "width|height|duration|profile"):
                    self.verify()

    def test_owner_rejects_malformed_or_disabled_sound_delivery_contract(self):
        for target in (
            {"width": True, "height": 36, "duration_seconds": 0.5},
            {"width": 64, "height": 36, "duration_seconds": "nan"},
            {"width": 64, "height": 36, "duration_seconds": 0},
            {"width": 64, "height": 36, "duration_seconds": 0.5, "require_audio": False},
        ):
            with self.subTest(target=target):
                studio_cli._write_status(
                    self.session, {**self.status, "owner_delivery_target": target})
                with self.assertRaisesRegex(ValueError, "owner delivery|delivery target|profile"):
                    self.verify()

    def test_owner_rejects_missing_native_asset_even_with_successful_previous_exports(self):
        self.assertTrue(self.verify()["physical_audiovisual_pair_verified"])
        self.project_media.unlink()
        with self.assertRaisesRegex(ValueError, "native|asset|source|media"):
            self.verify()

    def test_owner_rejects_same_size_media_substitution_after_render(self):
        # Existing pre-render project JSON and two physical exports remain
        # untouched. A different source with identical size must NOT pass
        # historical render-time media custody merely because it decodes.
        observed = self.verify()
        self.assertTrue(observed["native_media_source_closure_verified"])
        self.project_media.write_bytes(b"X" * self.project_media.stat().st_size)
        with self.assertRaisesRegex(ValueError, "render|source|changed|media|digest"):
            self.verify()

    def test_owner_rejects_native_asset_symlink_outside_project(self):
        self.project_media.unlink()
        self.project_media.symlink_to(self.media[0])
        with self.assertRaisesRegex(ValueError, "native|asset|source|media|linked"):
            self.verify()

    def test_owner_rejects_changed_media_and_forged_receipt(self):
        self.media[1].write_bytes(self.media[0].read_bytes())
        with self.assertRaisesRegex(ValueError, "differs"):
            self.verify()
        self.media[1].unlink()
        with self.assertRaisesRegex(ValueError, "removed"):
            self.verify()

    def test_owner_rejects_a_substituted_render_snapshot_or_stale_editable_project(self):
        report = self.verify()
        self.assertTrue(report["saved_native_matches_last_render_snapshot"])
        final_snapshot = self.snapshots / (self.pair[1]["destination_sha256"] + ".comfystudio")
        final_snapshot.write_text(json.dumps(self.initial_doc))
        with self.assertRaisesRegex(ValueError, "render snapshot digest"):
            self.verify()
        final_snapshot.write_text(json.dumps({
            **self.final_doc, "unverified_post_render_edit": True}))
        with self.assertRaisesRegex(ValueError, "render snapshot digest"):
            self.verify()
        final_snapshot.unlink()
        with self.assertRaisesRegex(ValueError, "render snapshot"):
            self.verify()

    def test_owner_rejects_substituted_first_snapshot_even_if_still_a_valid_editable_revision(self):
        self.assertTrue(self.verify()["saved_native_matches_last_render_snapshot"])
        first = self.snapshots / (self.pair[0]["destination_sha256"] + ".comfystudio")
        impostor = {
            "currentTimelineId": "timeline-1",
            "timelines": [{"id": "timeline-1", "clips": [
                {"id": "unrelated", "trackId": "video-track",
                 "name": "substituted-but-well-formed-previous-document"}]}],
        }
        first.write_text(json.dumps(impostor))
        # This still has a populated correct-timeline document and differs
        # from the final saved native project. Merely testing inequality is
        # not proof that the first render used these exact saved bytes.
        with self.assertRaisesRegex(ValueError, "render snapshot.*digest|digest.*render snapshot"):
            self.verify()

    def test_owner_rejects_missing_or_forged_render_time_snapshot_hashes(self):
        for hashes in (None, [], ["a" * 64], ["a" * 64, "b" * 64],
                       [self.snapshot_hashes[0], "broken"]):
            with self.subTest(hashes=hashes):
                changed = {**self.status["result"]}
                if hashes is None:
                    changed.pop("reviewed_native_snapshot_sha256", None)
                else:
                    changed["reviewed_native_snapshot_sha256"] = hashes
                studio_cli._write_status(self.session,
                                         {**self.status, "result": changed})
                with self.assertRaisesRegex(ValueError, "render snapshot digest"):
                    self.verify()

    def test_owner_rejects_missing_or_substituted_render_time_media_hashes(self):
        for hashes in (None, [], ["1" * 64], ["a" * 64, "bad"],
                       ["a" * 64, "b" * 64]):
            with self.subTest(hashes=hashes):
                changed = dict(self.status["result"])
                if hashes is None:
                    changed.pop("reviewed_native_media_sha256")
                else:
                    changed["reviewed_native_media_sha256"] = hashes
                studio_cli._write_status(self.session, {
                    **self.status, "result": changed})
                with self.assertRaisesRegex(ValueError, "media|source"):
                    self.verify()

    def test_owner_rejects_noncompleted_or_unreviewed_sessions(self):
        for update in (
            {"state": "running"}, {"state": "needs_attention"},
            {"result": {**self.status["result"], "evaluation_evidence_satisfied": False}},
            {"result": {**self.status["result"], "reviewed_native_audiovisual_pair": []}},
            {"result": {**self.status["result"], "required_evaluation_evidence": []}},
        ):
            with self.subTest(update=update):
                studio_cli._write_status(self.session, {**self.status, **update})
                with self.assertRaises(ValueError):
                    self.verify()

    def test_owner_rejects_moved_timeline_missing_project_or_changed_source(self):
        self.native.write_text(json.dumps({
            "currentTimelineId": "different", "timelines": [
                {"id": "different", "clips": [{"id": "x"}]}]}))
        with self.assertRaisesRegex(ValueError, "matches the reviewed timeline"):
            self.verify()
        self.native.unlink()
        with self.assertRaisesRegex(ValueError, "matches the reviewed timeline"):
            self.verify()

    def test_owner_rejects_modified_original_and_untrusted_paths(self):
        self.original.write_bytes(b"modified after run")
        with self.assertRaisesRegex(ValueError, "Original source bytes"):
            self.verify()
        self.original.write_bytes(b"owner original bytes; not used as a pretend neural edit")
        (self.output_root / "untrusted.mp4").symlink_to(self.media[0])
        with self.assertRaisesRegex(ValueError, "Symbolic-link output"):
            self.verify()

    def test_owner_rejects_silent_real_aac_even_if_native_receipt_claims_success(self):
        quiet = self.output_root / "silent.mp4"
        subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error",
            "-f", "lavfi", "-i", "color=c=black:s=64x36:r=24:d=0.5",
            "-f", "lavfi", "-i",
            "anullsrc=channel_layout=mono:sample_rate=48000:d=0.5",
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
            "-c:a", "aac", "-shortest", str(quiet),
        ], check=True, timeout=30)
        self.media[1].unlink()
        self.pair[1]["destination_sha256"] = destination_digest(str(quiet))
        self.pair[1]["export_sha256"] = hashlib.sha256(quiet.read_bytes()).hexdigest()
        studio_cli._write_status(self.session, self.status)
        with self.assertRaisesRegex(ValueError, "silent or unmeasurable"):
            self.verify()

    def test_owner_invalid_ids_budgets_and_unbound_receipts_fail_closed(self):
        for session in ("../escape", "not-hex", "b" * 25):
            with self.assertRaisesRegex(ValueError, "24-hex"):
                verify_owner_audiovisual_delivery(self.workspace, session)
        with self.assertRaisesRegex(ValueError, "finite"):
            verify_owner_audiovisual_delivery(
                self.workspace, self.sid, max_decode_seconds=float("nan"))
        self.pair[1]["timeline_sha256"] = "f" * 64
        studio_cli._write_status(self.session, self.status)
        with self.assertRaisesRegex(ValueError, "same timeline"):
            self.verify()


class NativeProjectMediaBoundaryRaceTests(unittest.TestCase):
    """Independent path-swap regression; never follow a raced parent symlink."""

    def test_parent_replaced_during_native_source_open_is_not_verified(self):
        with tempfile.TemporaryDirectory(prefix="zx7-native-race-") as temp:
            root = Path(temp)
            project = root / "project"
            videos = project / "assets" / "video"
            videos.mkdir(parents=True)
            (videos / "clip.mp4").write_bytes(b"original-native-media")
            outside = root / "outside"
            outside.mkdir()
            (outside / "clip.mp4").write_bytes(b"X" * len(b"original-native-media"))
            document = {
                "currentTimelineId": "film",
                "timelines": [{"id": "film", "clips": [
                    {"type": "video", "assetId": "original"}]}],
                "assets": [{"id": "original", "path": "assets/video/clip.mp4",
                            "size": len(b"original-native-media")}],
            }
            real_open = os.open
            swapped = [False]

            def replace_parent_before_file_open(path, flags, *args, **kwargs):
                if str(path).endswith("clip.mp4") and not swapped[0]:
                    videos.rename(project / "assets" / "retained-video")
                    videos.symlink_to(outside, target_is_directory=True)
                    swapped[0] = True
                return real_open(path, flags, *args, **kwargs)

            with patch("os.open", side_effect=replace_parent_before_file_open):
                with self.assertRaisesRegex(ValueError, "source media"):
                    _verify_native_project_media_closure(project, document)
            self.assertTrue(swapped[0], "test must simulate a real parent swap at open")

    def test_staged_owner_changed_size_preserves_existing_error_contract(self):
        with tempfile.TemporaryDirectory(prefix="zx7-staged-error-") as temp:
            root = Path(temp) / "owner"
            session = "b" * 24
            staging = root / "staging" / session
            staging.mkdir(parents=True)
            source = staging / "owner.wav"
            before = b"original-unchanged-asset"
            source.write_bytes(before)
            ledger = [{"path": str(source), "sha256": hashlib.sha256(before).hexdigest(),
                       "bytes": len(before), "rights": "synthetic",
                       "rights_independently_verified": False}]
            source.write_bytes(before + b"tampered")
            with self.assertRaisesRegex(ValueError, "Original source bytes differ"):
                _verify_staged_sources(root, session, ledger)

    def test_staged_original_parent_swap_cannot_follow_outside_workspace(self):
        with tempfile.TemporaryDirectory(prefix="zx7-staging-race-") as temp:
            workspace = Path(temp) / "workspace"
            session = "a" * 24
            staging = workspace / "staging" / session
            staging.mkdir(parents=True)
            source = staging / "owner.wav"
            original_bytes = b"real-owner-workspace-asset"
            source.write_bytes(original_bytes)
            outside = Path(temp) / "outside"
            outside.mkdir()
            # Same bytes deliberately defeat a plain digest-based check: the
            # security goal is no read THROUGH a linked parent outside root.
            (outside / source.name).write_bytes(original_bytes)
            ledger = [{"path": str(source), "sha256": hashlib.sha256(original_bytes).hexdigest(),
                       "bytes": len(original_bytes), "rights": "synthetic", 
                       "rights_independently_verified": False}]
            real_open = os.open
            swapped = [False]

            def replace_staging_before_file_open(path, flags, *args, **kwargs):
                if str(path).endswith("owner.wav") and not swapped[0]:
                    staging.rename(workspace / "staging" / "previous-session")
                    staging.symlink_to(outside, target_is_directory=True)
                    swapped[0] = True
                return real_open(path, flags, *args, **kwargs)

            with patch("os.open", side_effect=replace_staging_before_file_open):
                with self.assertRaisesRegex(ValueError, "source|media|changed|linked"):
                    _verify_staged_sources(workspace, session, ledger)
            self.assertTrue(swapped[0])

    @unittest.skipUnless(hasattr(os, "O_PATH"), "Linux O_PATH required")
    def test_native_media_directory_requires_search_not_read_permission(self):
        with tempfile.TemporaryDirectory(prefix="zx7-native-search-") as temp:
            project = Path(temp) / "project"
            video = project / "assets" / "video"
            video.mkdir(parents=True)
            (video / "original.mp4").write_bytes(b"file-beneath-execute-only-dir")
            doc = {"currentTimelineId": "t", "timelines": [{"id": "t", "clips": [
                       {"type": "video", "assetId": "v"}]}],
                   "assets": [{"id": "v", "path": "assets/video/original.mp4",
                               "size": len(b"file-beneath-execute-only-dir")}],
                   }
            video.chmod(0o111)
            try:
                result = _verify_native_project_media_closure(project, doc)
                self.assertTrue(result["native_media_source_closure_verified"])
            finally:
                video.chmod(0o700)

    def test_native_media_source_remains_readable_without_path_swaps(self):
        with tempfile.TemporaryDirectory(prefix="zx7-native-simple-") as temp:
            project = Path(temp) / "project"
            location = project / "assets" / "audio"
            location.mkdir(parents=True)
            (location / "source.wav").write_bytes(b"independent-owner-sound")
            doc = {"currentTimelineId": "t",
                   "timelines": [{"id": "t", "clips": [
                       {"type": "audio", "assetId": "a"}]}],
                   "assets": [{"id": "a", "path": "assets/audio/source.wav",
                               "size": len(b"independent-owner-sound")}],
                   }
            result = _verify_native_project_media_closure(project, doc)
            self.assertTrue(result["native_media_source_closure_verified"])
            self.assertEqual(result["native_media_used_asset_count"], 1)
            self.assertEqual(result["native_media_bytes_observed"],
                             len(b"independent-owner-sound"))


if __name__ == "__main__":
    unittest.main()
