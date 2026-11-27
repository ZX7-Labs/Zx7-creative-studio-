"""Physical editable timed-text delivery, without changing source picture/sound."""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio_next.body_integration import body_catalog, validate_witness
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.media_vault import MediaVault, sha256_file


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Actual native movie and timed-text codecs required")
class NativeTimedTextDelivery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root / "original.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n",
            "-f", "lavfi", "-i", "testsrc2=size=160x96:rate=24000/1001:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=730:sample_rate=44100:duration=3",
            "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-metadata:s:a:0", "language=eng",
            "-metadata:s:a:1", "language=hin", str(self.original)],
            check=True, capture_output=True, timeout=60)
        self.vault = MediaVault(self.root / "vault")
        self.source = self.vault.ingest(self.original, mime="video/mp4",
            rights="owner_supplied", source_type="owner_upload", source_id="original-caption-film",
            evidence="Original synthetic film and two independently generated audio tracks",
            owner_or_generator="owner")
        self.plan = {"media": {"source": "zx7:sha256:" + self.source["asset_id"],
            "asset_id": self.source["asset_id"], "attestation_id": self.source["attestation_id"]},
            "tracks": [{"language": "eng", "default": False, "cues": [
                {"start_ms": 125, "end_ms": 1040, "text": "First line\nSecond line"},
                {"start_ms": 1125, "end_ms": 2750, "text": "Unicode नमस्ते"}]},
                {"language": "hin", "default": True, "cues": [
                {"start_ms": 125, "end_ms": 1040, "text": "नमस्ते दुनिया"}]}]}
        self.plan_file = self.root / "authored-cues.json"
        self.catalog = body_catalog(self.root)

    def apply(self, plan, name="captioned.mp4"):
        self.plan_file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return self.catalog.invoke("body.subtitle_delivery", {"plan": self.plan_file.name,
            "out": name}, allowed_access={"read", "write"})

    def test_two_selectable_language_tracks_preserve_every_original_av_stream(self):
        before = sha256_file(self.original)
        result = self.apply(self.plan)
        self.assertTrue(validate_witness("body.subtitle_delivery", result))
        self.assertEqual(sha256_file(self.original), before)
        movie = self.root / "captioned.mp4"
        streams = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
            "-of", "json", str(movie)], timeout=60))["streams"]
        self.assertEqual([s["codec_type"] for s in streams], ["video", "audio", "audio", "subtitle", "subtitle"])
        for stream, track in zip(streams[3:], self.plan["tracks"]):
            self.assertEqual(stream["codec_name"], "mov_text")
            self.assertEqual(stream["tags"]["language"], track["language"])
            self.assertEqual(bool(stream["disposition"]["default"]), track["default"])
        for filename in (self.original, movie):
            decoded = subprocess.check_output(["ffmpeg", "-v", "error", "-xerror", "-i", str(filename),
                "-map", "0:v:0", "-map", "0:a", "-c:v", "rawvideo", "-pix_fmt", "yuv420p",
                "-fps_mode", "passthrough", "-threads:v", "1", "-c:a", "pcm_f64le",
                "-f", "streamhash", "-hash", "sha256", "-"], timeout=60)
            if filename == self.original:
                original_decoded = decoded
            else:
                self.assertEqual(decoded, original_decoded)
        english = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(movie),
            "-map", "0:s:0", "-f", "srt", "-"], timeout=60).decode().replace("\r\n", "\n")
        self.assertIn("00:00:00,125 --> 00:00:01,040\nFirst line\nSecond line", english)
        self.assertIn("00:00:01,125 --> 00:00:02,750\nUnicode नमस्ते", english)
        hindi = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(movie),
            "-map", "0:s:1", "-f", "srt", "-"], timeout=60).decode()
        self.assertIn("नमस्ते दुनिया", hindi)
        self.assertIn(before, [x["sha256"] for x in fingerprint_physical_inputs(
            "body.subtitle_delivery", {"plan": self.plan_file.name}, self.root)])
        with self.assertRaises(FileExistsError):
            self.apply(self.plan)
        self.assertEqual(sha256_file(movie), result["sha256"])

    def test_invalid_timing_text_default_and_rights_leave_no_delivery(self):
        for mutate in (
            lambda p: p["tracks"][0]["cues"][1].update(start_ms=1000),
            lambda p: p["tracks"][0]["cues"][1].update(end_ms=9000),
            lambda p: p["tracks"][0]["cues"][0].update(text="one\n\ninjected"),
            lambda p: p["tracks"][0]["cues"][0].update(text="<b>not plain text</b>"),
            lambda p: p["tracks"][0].update(default=True),
            lambda p: p["tracks"][1].update(default=False),
            lambda p: p["media"].update(attestation_id="forged"),
        ):
            plan = copy.deepcopy(self.plan)
            mutate(plan)
            with self.subTest(plan=plan), self.assertRaises((ValueError, RuntimeError)):
                self.apply(plan, "must-not-exist.mp4")
            self.assertFalse((self.root / "must-not-exist.mp4").exists())
            self.assertFalse(list(self.root.glob(".zx7-uncommitted-*")))

    def test_existing_subtitle_track_is_not_silently_removed(self):
        self.apply(self.plan)
        existing = self.root / "captioned.mp4"
        rights = self.vault.ingest(existing, mime="video/mp4", rights="owner_supplied",
            source_type="owner_upload", source_id="already-captioned", evidence="Original timed-text fixture",
            owner_or_generator="owner")
        plan = copy.deepcopy(self.plan)
        plan["media"] = {"source": "zx7:sha256:" + rights["asset_id"],
            "asset_id": rights["asset_id"], "attestation_id": rights["attestation_id"]}
        with self.assertRaisesRegex(ValueError, "existing non-A/V"):
            self.apply(plan, "must-not-replace.mp4")
        self.assertFalse((self.root / "must-not-replace.mp4").exists())

    def test_actual_changed_av_or_caption_payload_is_refused_before_publication(self):
        from unittest.mock import patch
        real_run = subprocess.run
        for fault in ("audio", "text"):
            with self.subTest(fault=fault):
                def alter(argv, **kwargs):
                    if argv[0] == "ffmpeg" and "mov_text" in argv:
                        if fault == "audio":
                            argv = [*argv[:-1], "-c:a", "aac", "-b:a", "64k", argv[-1]]
                        else:
                            cue = Path(next(x for x in argv if x.endswith("track-0.srt")))
                            cue.write_text(cue.read_text(encoding="utf-8").replace(
                                "First line", "Unexpected replacement"), encoding="utf-8")
                    return real_run(argv, **kwargs)
                with patch("studio_next.body_subtitles.subprocess.run", side_effect=alter):
                    with self.assertRaisesRegex(ValueError, "changed original A/V|Decoded subtitle"):
                        self.apply(self.plan, "corrupt.mp4")
                self.assertFalse((self.root / "corrupt.mp4").exists())
                self.assertFalse(list(self.root.glob(".zx7-uncommitted-*")))

    def test_native_hdr_quicktime_picture_preserves_bit_depth_and_color_with_timed_text(self):
        movie = self.root / "hdr.mov"
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n", "-f", "lavfi",
            "-i", "testsrc2=size=96x64:rate=12:duration=1", "-vf",
            "format=yuv422p10le,setparams=range=limited:color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc",
            "-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le",
            "-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc",
            "-movflags", "+write_colr", "-bsf:v",
            "prores_metadata=color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc",
            str(movie)], check=True, capture_output=True, timeout=60)
        source = self.vault.ingest(movie, mime="video/quicktime", rights="owner_supplied",
            source_type="owner_upload", source_id="original-hdr-signal-fixture",
            evidence="Original synthetic native 10-bit PQ signaling test", owner_or_generator="owner")
        plan = {"media": {"source": "zx7:sha256:" + source["asset_id"], "asset_id": source["asset_id"],
            "attestation_id": source["attestation_id"]}, "tracks": [{"language": "eng", "default": True,
            "cues": [{"start_ms": 50, "end_ms": 900, "text": "HDR cue"}]}]}
        result = self.apply(plan, "captioned-hdr.mov")
        self.assertTrue(validate_witness("body.subtitle_delivery", result))
        self.assertFalse(result["audio_present"])
        actual = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
            "-of", "json", result["path"]], timeout=60))["streams"]
        self.assertEqual([s["codec_type"] for s in actual], ["video", "subtitle"])
        for key, value in {"codec_name": "prores", "pix_fmt": "yuv422p10le", "color_space": "bt2020nc",
                           "color_transfer": "smpte2084", "color_primaries": "bt2020"}.items():
            self.assertEqual(actual[0][key], value)
        self.assertEqual(sha256_file(movie), source["asset_id"])
