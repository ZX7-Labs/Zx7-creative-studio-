"""Real camera source staging tests; no mock decoder or neural authorship."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from studio_next.native_camera_seed import (
    NativeCameraSeedError, stage_attested_camera, verify_native_original_timeline,
)


class NativeCameraSeedTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "Physical camera decoder tools required")
    def test_actual_original_is_staged_without_prebaked_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "original.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-f", "lavfi", "-i", "testsrc2=size=64x36:rate=2:duration=32",
                "-c:v", "mpeg4", "-q:v", "2", str(source)
            ], check=True, timeout=40, capture_output=True)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            rights = root / "rights.json"
            rights.write_text(json.dumps({
                "sha256": digest, "duration_seconds": 32.0,
                "license_declared_by_source": "CC0",
                "full_picture_decode_completed": True,
            }))
            staging, evidence = root / "staging", root / "evidence"
            staging.mkdir()
            evidence.mkdir()
            report = stage_attested_camera(source, rights, staging, evidence)
            self.assertEqual(report["sha256"], digest)
            self.assertEqual(hashlib.sha256(
                Path(report["path"]).read_bytes()).hexdigest(), digest)
            self.assertEqual(report["temporal_observation"]["decoded_one_fps_frame_count"], 32)
            self.assertEqual(len(
                report["temporal_observation"]["contact_sheet_sample_times_seconds"]), 16)
            self.assertFalse(report["source_has_audio"])
            self.assertTrue(report["native_import_uses_original_bytes_not_prebaked_edit_segments"])
            self.assertTrue(Path(report["camera_preview_path"]).is_file())
            self.assertFalse(report.get("rights_legally_cleared", False))
            with self.assertRaises(FileExistsError):
                stage_attested_camera(source, rights, staging, evidence)

    def test_saved_native_project_must_use_actual_original_in_timeline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "camera.webm"
            original.write_bytes(b"exact original media identity test bytes")
            sha = hashlib.sha256(original.read_bytes()).hexdigest()
            project = root / "project"
            project.mkdir()
            target = project / "camera.webm"
            target.write_bytes(original.read_bytes())
            document = project / "project.comfystudio"
            structure = {
                "assets": [{"id": "real-camera", "path": "camera.webm"}],
                "timelines": [{"clips": [{"id": "native-1",
                                          "assetId": "real-camera"}]}],
            }
            document.write_text(json.dumps(structure))
            actual = verify_native_original_timeline(document, sha)
            self.assertTrue(actual["original_camera_bytes_preserved"])
            self.assertTrue(actual["original_on_saved_native_timeline"])
            self.assertEqual(actual["native_timeline_original_camera_clip_count"], 1)
            structure["timelines"][0]["clips"][0]["assetId"] = "other-media"
            document.write_text(json.dumps(structure))
            ignored = verify_native_original_timeline(document, sha)
            self.assertTrue(ignored["original_camera_bytes_preserved"])
            self.assertFalse(ignored["original_on_saved_native_timeline"])
            target.write_bytes(b"not the same original")
            modified = verify_native_original_timeline(document, sha)
            self.assertFalse(modified["original_camera_bytes_preserved"])

    def test_reject_rights_or_hash_without_importing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            camera = root / "original.mp4"
            camera.write_bytes(b"not the attested camera")
            rights = root / "manifest.json"
            staging, evidence = root / "staging", root / "evidence"
            staging.mkdir()
            evidence.mkdir()
            for license_name in ["copyrighted", "CC0"]:
                rights.write_text(json.dumps({
                    "sha256": "0"*64,
                    "license_declared_by_source": license_name,
                    "full_picture_decode_completed": True,
                }))
                with self.assertRaises(NativeCameraSeedError):
                    stage_attested_camera(camera, rights, staging, evidence)
                self.assertFalse(list(staging.iterdir()))
            rights.write_text(json.dumps({
                "sha256": hashlib.sha256(camera.read_bytes()).hexdigest(),
                "bytes": camera.stat().st_size + 1,
                "license_declared_by_source": "CC0",
                "full_picture_decode_completed": True,
            }))
            with self.assertRaises(NativeCameraSeedError):
                stage_attested_camera(camera, rights, staging, evidence)
            self.assertFalse(list(staging.iterdir()))
            linked = root / "alias.mp4"
            linked.symlink_to(camera)
            with self.assertRaises(NativeCameraSeedError):
                stage_attested_camera(linked, rights, staging, evidence)


if __name__ == "__main__":
    unittest.main()
