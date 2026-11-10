"""Use physical audiovisual fixtures for the offline release evidence check."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

from scripts.audit_native_av_trial import audit_pair
from scripts.run_nvidia_native_trial import main as stage_trial
from studio_next.native_render_evidence import (
    AUDIO_ENVELOPE, AV_PCM_FIELD, AV_REVIEW_FIELD, DESTINATION_FIELD, SAVED_RENDER_FIELD,
    SAVED_RENDER_OPTIONS_FIELD, SCOPE_FIELD, TIMED_FRAMES,
)


class NativeAVTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scratch = tempfile.TemporaryDirectory()
        cls.addClassCleanup(scratch.cleanup)
        root = Path(scratch.name)
        cls.before = root / "before.mp4"
        cls.after_picture = root / "after-picture.mp4"
        cls.after_sound = root / "after-sound.mp4"
        cls.remux = root / "remux.mp4"
        cls.quicktime = root / "quicktime.mp4"
        cls.silent = root / "silent.mp4"
        for path, color, audio in (
                (cls.before, "red", "sine=f=440:r=48000:d=6"),
                (cls.after_picture, "blue", "sine=f=440:r=48000:d=6"),
                (cls.after_sound, "red", "sine=f=440:r=48000:d=6,volume=0.501187"),
                (cls.silent, "blue", "anullsrc=r=48000:cl=mono:d=6")):
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                 f"color={color}:s=640x360:r=24:d=6", "-f", "lavfi", "-i", audio,
                 "-c:v", "libx264", "-threads", "2", "-c:a", "aac", str(path)],
                check=True, timeout=30)
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-i", str(cls.before),
             "-c", "copy", "-metadata", "comment=container change", str(cls.remux)],
            check=True, timeout=30)
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-i", str(cls.after_picture),
             "-c", "copy", "-f", "mov", str(cls.quicktime)], check=True, timeout=30)
        cls.assert_container_changed = cls.before.read_bytes() != cls.remux.read_bytes()
        cls.first = root / "first.comfystudio"
        cls.edited = root / "edited.comfystudio"
        cls.edited_sound = root / "edited-sound.comfystudio"
        cls.metadata_only = root / "metadata-only.comfystudio"
        cls.malformed = root / "malformed.comfystudio"
        for path, text, gain, modified in (
                (cls.first, "Before", 0, 1), (cls.edited, "After", 0, 2),
                (cls.edited_sound, "Before", -6, 3), (cls.metadata_only, "Before", 0, 4)):
            path.write_text(json.dumps({
                "currentTimelineId": "timeline", "modified": modified,
                "timelines": [{"id": "timeline", "modified": modified,
                               "tracks": [{"id": "video", "type": "video"},
                                          {"id": "audio", "type": "audio"}],
                               "clips": [{"id": "clip", "trackId": "video",
                                          "textProperties": {"text": text}},
                                         {"id": "sound", "trackId": "audio",
                                          "gainDb": gain}]}],
            }), encoding="utf-8")
        cls.malformed.write_text('{"currentTimelineId":"a","currentTimelineId":"b"}')

    def test_accepts_physical_picture_or_sound_change_with_saved_editorial_delta(self):
        for output, project, picture, sound in (
                (self.after_picture, self.edited, True, False),
                (self.after_sound, self.edited_sound, False, True)):
            with self.subTest(output=output.name):
                report = audit_pair(self.before, output, self.first, project)
                self.assertIs(report["decoded_picture_changed"], picture)
                self.assertIs(report["decoded_sound_changed"], sound)

    def test_rejects_container_only_change(self):
        self.assertTrue(self.assert_container_changed)
        with self.assertRaisesRegex(ValueError, "No decoded"):
            audit_pair(self.before, self.remux, self.first, self.edited)

    def test_binds_relocated_exports_and_project_snapshots_to_host_receipts(self):
        def digest(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()

        events = []
        for index, (export, project, destination) in enumerate((
                (self.before, self.first, "a" * 64),
                (self.after_picture, self.edited, "b" * 64))):
            if index:
                events.append({"kind": "native_tool_result", "tool": "update_text_clip",
                               "host_application_write_acknowledged": True})
            export_sha = digest(export)
            common = {"kind": "native_tool_result", DESTINATION_FIELD: destination}
            events.extend((
                {**common, "tool": "export_timeline",
                 "host_application_write_acknowledged": True,
                 SCOPE_FIELD: "c" * 64, SAVED_RENDER_OPTIONS_FIELD: "d" * 64,
                 SAVED_RENDER_FIELD: digest(project)},
                {**common, "tool": "zx7_verify_native_export",
                 "independently_verified_export_sha256": export_sha, AV_REVIEW_FIELD: [6]},
                {**common, "tool": TIMED_FRAMES, "observed_export_sha256": export_sha,
                 "image_sha256": [destination, "e" * 64], AV_REVIEW_FIELD: [1, 4]},
                {**common, "tool": AUDIO_ENVELOPE, "observed_export_sha256": export_sha,
                 AV_REVIEW_FIELD: [0, 6], AV_PCM_FIELD: "f" * 64},
            ))
        with tempfile.TemporaryDirectory() as scratch:
            journal = Path(scratch) / "journal.jsonl"
            journal.write_text("\n".join(map(json.dumps, events)), encoding="utf-8")
            result = audit_pair(self.before, self.after_picture, self.first, self.edited,
                                journal=journal)
            self.assertTrue(result["host_journal_bound"])
            with self.assertRaisesRegex(ValueError, "accepted ordered"):
                audit_pair(self.after_picture, self.before, self.edited, self.first,
                           journal=journal)
            events[5][SAVED_RENDER_OPTIONS_FIELD] = "a" * 64
            journal.write_text("\n".join(map(json.dumps, events)), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "matching render settings"):
                audit_pair(self.before, self.after_picture, self.first, self.edited,
                           journal=journal)
            events[5][SAVED_RENDER_OPTIONS_FIELD] = "d" * 64
            events[5][SAVED_RENDER_FIELD] = digest(self.metadata_only)
            journal.write_text("\n".join(map(json.dumps, events)), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differs from the bound"):
                audit_pair(self.before, self.after_picture, self.first, self.edited,
                           journal=journal)

    def test_rejects_metadata_only_invalid_project_and_silent_audio(self):
        with self.assertRaisesRegex(ValueError, "lacks a comparable editorial change"):
            audit_pair(self.before, self.after_picture, self.first, self.metadata_only)
        with self.assertRaises(ValueError):
            audit_pair(self.before, self.after_picture, self.first, self.malformed)
        with self.assertRaisesRegex(ValueError, "silent"):
            audit_pair(self.before, self.silent, self.first, self.edited)
        with self.assertRaisesRegex(ValueError, "MP4 container brand"):
            audit_pair(self.before, self.quicktime, self.first, self.edited)

    def test_stage_only_creates_original_synthetic_inputs_and_never_launches(self):
        with tempfile.TemporaryDirectory() as scratch:
            workspace = Path(scratch) / "trial"
            with patch("scripts.run_nvidia_native_trial.run_trial") as launch:
                stage_trial(["--workspace", str(workspace), "--prepare-audiovisual-only"])
            launch.assert_not_called()
            self.assertFalse(any((workspace / "projects").iterdir()))
            self.assertFalse(any((workspace / "outputs").iterdir()))
            ledger = json.loads((workspace / "source-ledger.json").read_text())
            self.assertEqual({Path(item["path"]).suffix for item in ledger}, {".mp4", ".wav"})
            for item in ledger:
                self.assertFalse(item["preauthored_timeline"])
                self.assertEqual(hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest(),
                                 item["sha256"])
            sound_path, = (workspace / "staging").glob("*.wav")
            with wave.open(str(sound_path), "rb") as sound:
                self.assertEqual(sound.getnframes(), sound.getframerate() * 6)
                self.assertTrue(any(sound.readframes(sound.getnframes())))
