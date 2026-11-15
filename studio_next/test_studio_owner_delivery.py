"""Owner-level physical delivery acceptance tests; no model results are fabricated as art."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio_next import studio_cli
from studio_next.native_render_evidence import REVIEWED_AV_PAIR, destination_digest, timeline_scope_digest
from studio_next.studio_owner_delivery import verify_owner_audiovisual_delivery


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
        self.status = {
            "session_id": self.sid, "state": "completed",
            "render_snapshots_required": True,
            "result": {"status": "model_finished_unverified",
                       "evaluation_evidence_satisfied": True,
                       "required_evaluation_evidence": [REVIEWED_AV_PAIR],
                       "reviewed_native_audiovisual_pair": self.pair,
                       "reviewed_native_snapshot_sha256": self.snapshot_hashes},
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


if __name__ == "__main__":
    unittest.main()
