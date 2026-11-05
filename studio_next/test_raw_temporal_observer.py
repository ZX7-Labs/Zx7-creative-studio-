"""Actual decoded camera temporal-scan regressions, not a creative test."""
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

from studio_next.raw_temporal_observer import (
    RawTemporalObservationError, inspect_raw_temporal_source,
    select_temporal_samples, render_camera_contact_sheet,
)


class RawTemporalObserverTests(unittest.TestCase):
    def test_sample_grid_preserves_whole_source_and_local_changes(self):
        diffs = [0.0] * 160
        diffs[19] = 200.0
        diffs[96] = 180.0
        selected = select_temporal_samples(160, diffs)
        self.assertEqual(len(selected), 16)
        self.assertEqual(len(set(selected)), 16)
        self.assertEqual(selected[1], 19.0)
        self.assertEqual(selected[9], 96.0)
        for idx, second in enumerate(selected):
            self.assertGreaterEqual(second, idx * 10)
            self.assertLess(second, (idx + 1) * 10)

    @unittest.skipUnless(shutil.which("ffmpeg"), "real FFmpeg required")
    def test_physical_full_stream_changes_observed(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "camera.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-f", "lavfi", "-i", "color=black:size=64x36:rate=2:duration=32",
                "-vf", "drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='gte(t,16)'",
                "-c:v", "mpeg4", "-q:v", "2", str(source)
            ], capture_output=True, check=True, timeout=40)
            observed = inspect_raw_temporal_source(source, 32.0)
            self.assertEqual(observed["decoded_one_fps_frame_count"], 32)
            self.assertEqual(len(observed["contact_sheet_sample_times_seconds"]), 16)
            self.assertGreater(observed["maximum_adjacent_grayscale_delta_0_to_255"], 100)
            self.assertTrue(any(14 <= p["source_second"] <= 18
                                for p in observed["highest_change_seconds"]))
            self.assertIs(observed["not_motion_semantics_or_artistic_quality"], True)

    @unittest.skipUnless(shutil.which("ffmpeg"), "Real FFmpeg required")
    def test_portrait_source_preview_uses_letterboxing_not_image_distortion(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "portrait.mp4"
            sheet = Path(temp) / "contact.png"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-f", "lavfi", "-i", "color=white:size=64x128:rate=2:duration=4",
                "-c:v", "mpeg4", "-q:v", "2", str(source)
            ], capture_output=True, check=True, timeout=40)
            times = [round(.1 + .2 * i, 3) for i in range(16)]
            observed = render_camera_contact_sheet(source, 4.0, times, sheet)
            self.assertEqual(observed["sample_times_seconds"], times)
            with Image.open(sheet) as picture:
                self.assertEqual(picture.size, (1280, 840))
                self.assertLess(picture.getpixel((25, 90))[0], 30)
                self.assertGreater(picture.getpixel((160, 90))[0], 200)

    def test_fail_closed_on_invalid_evidence(self):
        for duration, changes in [
            (float("nan"), [0] * 30),
            (0, [0] * 30),
            (1201, [0] * 30),
            (40, [0, float("inf")]),
            (40, [0, -1]),
            (40, []),
        ]:
            with self.subTest(duration=duration, changes=changes[:2]):
                with self.assertRaises(RawTemporalObservationError):
                    select_temporal_samples(duration, changes)
        with self.assertRaises(RawTemporalObservationError):
            inspect_raw_temporal_source("/not-a-real-camera-input", 32)


if __name__ == "__main__":
    unittest.main()
