"""Physical native editor export observations are independent of MCP success."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio_next.body_editor_export import verify_native_editor_export
from studio_next.body_editor_policy import EditorPathPolicy
from studio_next.body_editor_client import EditorAccessError
from studio_next.media_vault import sha256_file


class NativeEditorExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.projects, self.staging, self.outputs = (
            self.root / part for part in ("projects", "staging", "outputs"))
        for part in (self.projects, self.staging, self.outputs):
            part.mkdir()
        self.policy = EditorPathPolicy(self.projects, self.staging, self.outputs)
        self.file = self.outputs / "actual-edit.mp4"
        self.file.write_bytes(b"not a video" * 128)

    def fake_inspect(self, source, **kwargs):
        return {"sha256": sha256_file(source), "technical_delivery_verified": True,
                "delivery_mismatches": [], "full_picture_and_sound_decoder_completed": True}

    def verify(self, path=None, **kwargs):
        return verify_native_editor_export(str(path or self.file), policy=self.policy,
                                           inspector=self.fake_inspect, **kwargs)

    def test_read_only_authorized_export_receipt_is_source_bound(self):
        proof = self.verify(expected={"require_audio": True})
        self.assertTrue(proof["physical_export_verified"])
        self.assertEqual(proof["native_export_sha256"], sha256_file(self.file))
        self.assertFalse(proof["artistic_quality_approved"])
        self.assertFalse(proof["autonomous_ai_creativity_proven"])

    def test_outside_output_and_staging_sources_cannot_be_observed(self):
        for path in (self.root / "private.mp4", self.staging / "import.mp4",
                     self.projects / "source-original.mp4", Path("/etc/passwd")):
            with self.subTest(path=path), self.assertRaises(EditorAccessError):
                self.verify(path)

    def test_symbolic_link_to_internal_file_is_denied(self):
        linked = self.outputs / "link.mp4"
        linked.symlink_to(self.file)
        with self.assertRaises(EditorAccessError):
            self.verify(linked)
        folder = self.outputs / "linked-dir"
        folder.symlink_to(self.projects, target_is_directory=True)
        (self.projects / "a.mp4").write_bytes(b"data" * 200)
        with self.assertRaises(EditorAccessError):
            self.verify(folder / "a.mp4")

    def test_wrong_format_and_empty_file_are_not_export_proofs(self):
        wrong = self.outputs / "document.txt"
        wrong.write_bytes(b"a" * 1000)
        with self.assertRaises(ValueError):
            self.verify(wrong)
        self.file.write_bytes(b"a")
        with self.assertRaises(ValueError):
            self.verify()

    def test_concurrent_mutation_never_yields_a_valid_receipt(self):
        def changed(source, **kwargs):
            old_hash = sha256_file(source)
            source.write_bytes(b"changed" * 200)
            return {"sha256": old_hash, "technical_delivery_verified": True}
        with self.assertRaisesRegex(ValueError, "changed during"):
            verify_native_editor_export(str(self.file), policy=self.policy, inspector=changed)

    def test_decoder_or_specification_failure_is_not_accepted(self):
        def failed(source, **kwargs):
            return {"sha256": sha256_file(source), "technical_delivery_verified": False,
                    "delivery_mismatches": ["missing required audio"]}
        with self.assertRaisesRegex(ValueError, "missing required audio"):
            verify_native_editor_export(str(self.file), policy=self.policy, inspector=failed)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "Needs actual FFmpeg/FFprobe")
    def test_required_audio_absence_is_bound_to_physical_file_and_cached(self):
        from studio_next.body_editor_export import NativeExportMissingAudio
        from studio_next.production_qc import full_decode_inspection

        def render(with_audio):
            command = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                       "testsrc2=size=160x90:rate=12:duration=1"]
            if with_audio:
                command += ["-f", "lavfi", "-i",
                            "sine=frequency=440:sample_rate=48000:duration=1"]
            subprocess.run(command + ["-c:v", "mpeg4", "-c:a", "aac", str(self.file)],
                           timeout=30, check=True)

        inspections = []
        cache = {}

        def inspect(source, **kwargs):
            inspections.append(source)
            return full_decode_inspection(source, **kwargs)

        def verify(expected):
            return verify_native_editor_export(
                str(self.file), policy=self.policy, expected=expected,
                inspector=inspect, missing_audio_cache=cache)

        render(False)
        for retry in (False, True):
            with self.assertRaises(NativeExportMissingAudio) as failure:
                verify({"require_audio": True})
            self.assertEqual(failure.exception.sha256, sha256_file(self.file))
            self.assertIs(failure.exception.cached, retry)
        self.assertEqual(len(inspections), 1)
        self.assertTrue(verify({"require_audio": False})["physical_export_verified"])
        render(True)
        self.assertTrue(verify({"require_audio": True})["observation"]["audio_present"])
        self.assertEqual(len(inspections), 3)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "Needs actual FFmpeg/FFprobe for full physical decode")
    def test_real_encoded_picture_and_sound_are_independently_decoded(self):
        self.file.unlink()
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=12:duration=1",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
                        "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(self.file)],
                       timeout=30, check=True)
        receipt = verify_native_editor_export(
            str(self.file), policy=self.policy,
            expected={"width": 160, "height": 90,
                      "duration_seconds": 1, "require_audio": True},
            max_seconds=30)
        self.assertTrue(receipt["observation"]["full_picture_and_sound_decoder_completed"])
        self.assertTrue(receipt["observation"]["audio_present"])
        self.assertFalse(receipt["artistic_quality_approved"])


if __name__ == "__main__":
    unittest.main()
