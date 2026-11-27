"""Physically decoded visual feedback for an authorized completed native edit."""
import hashlib
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from studio_next.body_editor_frame import observe_verified_export_frame, _verified_png_dimensions
from studio_next.body_editor_policy import EditorPathPolicy
from studio_next.body_editor_client import EditorAccessError
from studio_next.media_vault import sha256_file


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Requires a real physical A/V decoder")
class NativeEditorVisualFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.projects, self.staging, self.outputs = (root / name for name in
                                                     ("projects", "staging", "outputs"))
        for item in (self.projects, self.staging, self.outputs):
            item.mkdir()
        self.policy = EditorPathPolicy(self.projects, self.staging, self.outputs)
        self.source = self.outputs / "review.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12:duration=1",
                        "-c:v", "mpeg4", str(self.source)], check=True, timeout=30)
        self.digest = sha256_file(self.source)

    def sample(self, **options):
        return observe_verified_export_frame(str(self.source), policy=self.policy,
                                            verified_sha256=self.digest, **options)

    def test_real_verified_frame_matches_actual_video_and_has_bounded_png(self):
        png, receipt = self.sample(at_seconds=0.5)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual((receipt["observed_picture_width"],
                          receipt["observed_picture_height"]), (320, 180))
        self.assertEqual(receipt["png_sha256"], hashlib.sha256(png).hexdigest())
        self.assertEqual(receipt["export_sha256"], self.digest)
        self.assertFalse(receipt["sampled_video_seconds_exact_pts_proven"])
        self.assertFalse(receipt["human_or_artistic_quality_approved"])

    def test_heldout_short_event_controls_calibrate_targeted_picture_and_sound(self):
        """Physical oracle only: identical sample budget, not neural perception.

        Time targets are selected by this test from known synthetic intervals;
        a future blinded Brain must discover them independently. Include absent
        and offset modalities so a loud bin cannot certify a picture event.
        """
        from studio_next.body_editor_export import verify_native_editor_export
        from studio_next.body_editor_audio_timeline import observe_verified_export_audio_timeline
        passive = (0.25, 1.25, 2.25)
        targeted = (1.375, 1.5, 1.75)
        for name, box_start, tone_start in (
                ("aligned", 35, 1.5), ("offset", 43, 1.5),
                ("sound_only", None, 1.5), ("picture_only", 35, None)):
            with self.subTest(case=name):
                movie = self.outputs / (name + ".mp4")
                video = "color=c=gray:s=160x90:r=24:d=3"
                if box_start is not None:
                    video += (",drawbox=x=60:y=25:w=40:h=40:color=red:t=fill:"
                              f"enable='between(n,{box_start},{box_start+2})'")
                audio = ("anullsrc=r=48000:cl=mono:d=3" if tone_start is None else
                         "aevalsrc=0.25*sin(2*PI*880*t)*"
                         f"between(t\\,{tone_start}\\,{tone_start+.125}):s=48000:d=3")
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                                "-f", "lavfi", "-i", video, "-f", "lavfi", "-i", audio,
                                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
                                "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(movie)],
                               check=True, timeout=30)
                verification = verify_native_editor_export(str(movie), policy=self.policy)
                self.assertTrue(verification["physical_export_verified"])
                digest = sha256_file(movie)
                self.assertEqual(verification["native_export_sha256"], digest)

                def red_at(seconds):
                    png, receipt = observe_verified_export_frame(str(movie), policy=self.policy,
                        verified_sha256=digest, at_seconds=seconds)
                    self.assertEqual(receipt["export_sha256"], digest)
                    self.assertEqual(receipt["png_sha256"], hashlib.sha256(png).hexdigest())
                    self.assertFalse(receipt["sampled_video_seconds_exact_pts_proven"])
                    self.assertFalse(receipt["human_or_artistic_quality_approved"])
                    rgb = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                                          "-f", "image2pipe", "-i", "pipe:0",
                                          "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
                                         input=png, capture_output=True, check=True, timeout=10).stdout
                    self.assertEqual(len(rgb), 160 * 90 * 3)
                    offset = (45 * 160 + 80) * 3
                    r, g, b = rgb[offset:offset+3]
                    return r > 200 and g < 50 and b < 50

                self.assertFalse(any(red_at(t) for t in passive))
                expected = name in ("aligned", "picture_only")
                self.assertEqual([red_at(t) for t in targeted], [False, expected, False])
                if name == "offset":
                    self.assertTrue(red_at(1.875))
                sound = observe_verified_export_audio_timeline(str(movie), policy=self.policy,
                    verified_sha256=digest, start_seconds=1.375, duration_seconds=.5, bins=4)
                self.assertEqual(sound["export_sha256"], digest)
                self.assertEqual(sound["observed_pcm_samples"], 4000)
                peaks = [b["sample_peak_normalized"] for b in sound["intervals"]]
                if tone_start is None:
                    self.assertLess(max(peaks), .008)
                else:
                    self.assertGreater(peaks[1], .1)
                    self.assertLess(peaks[-1], .008)
                self.assertFalse(sound["human_or_artistic_quality_approved"])
                self.assertEqual(sha256_file(movie), digest)

    def test_decoder_spools_bounded_image_without_unbounded_ram_capture(self):
        original = subprocess.run
        calls = []
        def inspect_command(command, **kwargs):
            # subprocess.check_output internally delegates to subprocess.run;
            # constrain these assertions to the actual FFmpeg image command.
            if command[0] == "ffmpeg":
                calls.append((command, kwargs))
                self.assertEqual(kwargs.get("stderr"), subprocess.DEVNULL)
                self.assertNotEqual(kwargs.get("stdout"), subprocess.PIPE)
                self.assertIn("-fs", command)
                self.assertEqual(command[command.index("-fs") + 1], str(4 * 1024 * 1024))
            return original(command, **kwargs)
        from unittest.mock import patch
        with patch("studio_next.body_editor_frame.subprocess.run",
                   side_effect=inspect_command):
            png, receipt = self.sample(at_seconds=0.25)
        self.assertEqual(len(calls), 1)
        self.assertEqual(receipt["png_sha256"], hashlib.sha256(png).hexdigest())

    def test_complete_image_requires_real_chunk_integrity_and_iend(self):
        png, _ = self.sample(at_seconds=0.5)
        self.assertEqual(_verified_png_dimensions(png), (320, 180))
        for corrupted in (png[:24], png[:-12], png + b"trailing-bytes",
                          png[:30] + bytes([png[30] ^ 1]) + png[31:]):
            with self.subTest(size=len(corrupted)), self.assertRaises(ValueError):
                _verified_png_dimensions(corrupted)

    def test_bad_time_and_bad_hash_fail_closed(self):
        for time_value in (float("nan"), float("inf"), -1, True, 1.1):
            with self.subTest(time_value=time_value), self.assertRaises(ValueError):
                self.sample(at_seconds=time_value)
        with self.assertRaises(ValueError):
            observe_verified_export_frame(str(self.source), policy=self.policy,
                verified_sha256="0" * 64, at_seconds=0.5)

    def test_mutation_since_export_proof_is_rejected(self):
        self.source.write_bytes(self.source.read_bytes() + b"modified after verified export")
        with self.assertRaisesRegex(ValueError, "no longer match"):
            self.sample(at_seconds=0.5)

    def test_out_of_root_and_symbolic_link_observation_are_denied(self):
        other = self.staging / "not-authorized.mp4"
        other.write_bytes(self.source.read_bytes())
        link = self.outputs / "alias.mp4"
        link.symlink_to(self.source)
        project_original = self.projects / "not-an-export.mp4"
        project_original.write_bytes(self.source.read_bytes())
        for item in (other, link, project_original):
            with self.subTest(item=item), self.assertRaises(EditorAccessError):
                observe_verified_export_frame(str(item), policy=self.policy,
                    verified_sha256=self.digest, at_seconds=0.5)


if __name__ == "__main__":
    unittest.main()
