"""Real 5.1 production-audio preservation and fail-closed channel policy.

The BODY already has a 108-case sample-clock oracle. These independent
audio-channel tests cover the previously stereo-only *composition* route:
a wrong matrix/pan passes sample timing while destroying original sound.
No artistic or semantic-hearing certification is implied.
"""
from __future__ import annotations

import array
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from studio_next.body_document_schemas import validate_document
from studio_next.composite_mix import actual_composite_command, render_composition
from studio_next.media_vault import MediaVault

_FREQUENCIES = (220, 330, 440, 60, 660, 770)  # LFE intentionally below its low-pass
_SAMPLE_RATE = 48000
_SURROUND_SPEAKERS_TEST = ("FL", "FR", "FC", "LFE", "BL", "BR")


def _probe_channels(file: Path) -> dict:
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate,channels,channel_layout",
        "-of", "json", str(file)], timeout=45))["streams"][0]


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real native codecs unavailable (CI must provide both)")
class PhysicalSurroundProductionTests(unittest.TestCase):
    def _source(self, root: Path):
        source = root / "six-original-channels.wav"
        expressions = "|".join(f"0.35*sin(2*PI*{freq}*t)" for freq in _FREQUENCIES)
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "lavfi", "-i",
            f"aevalsrc={expressions}:s={_SAMPLE_RATE}:d=0.75:c=5.1",
            "-c:a", "pcm_s16le", "-y", str(source)],
            check=True, timeout=45)
        self.assertEqual(_probe_channels(source)["channels"], 6)
        original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        vault = MediaVault(root / "vault")
        receipt = vault.ingest(source, mime="audio/wav",
                               rights="owner_supplied", source_type="owner_upload",
                               source_id="physical-six-channel-fixture",
                               evidence="Real six-channel licensed synthetic PCM",
                               owner_or_generator="source-owner")
        plan = {
            "canvas": {"width":128, "height":96, "fps":12,
                       "duration":0.75, "background":"#152433",
                       "audio_bus": {"sample_rate":_SAMPLE_RATE,
                                     "channel_layout":"5.1"}},
            "video_layers": [],
            "audio_tracks": [{
                "id": "original-six-channel-source",
                "source": source.name,
                "asset_id": receipt["asset_id"],
                "attestation_id": receipt["attestation_id"],
                "start":0, "source_in":0, "duration":0.7, "gain_db":0,
            }],
        }
        return source, original_sha, vault, plan

    def test_native_six_discrete_channels_survive_real_video_export(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            source, original_sha, vault, plan = self._source(root)
            self.assertTrue(validate_document("body.composite_mix", plan, "plan"))
            spec = actual_composite_command(plan, root, vault, root / "movie.mp4")
            graph = spec[spec.index("-filter_complex") + 1]
            self.assertIn("aformat=channel_layouts=5.1", graph)
            self.assertIn("adelay=0S:all=1", graph)
            self.assertNotIn("aformat=channel_layouts=stereo", graph)
            document = root / "editable-sound-plan.json"
            document.write_text(json.dumps(plan), encoding="utf8")
            encoded = root / "surround-original-movie.mp4"
            receipt = render_composition(document, root, root / "vault", encoded)
            self.assertTrue(receipt["full_picture_and_sound_decoder_completed"])
            self.assertEqual(receipt["audio_channels"], 6)
            self.assertEqual(receipt["audio_channel_layout"], "5.1")
            stream = _probe_channels(encoded)
            self.assertEqual(int(stream["channels"]), 6)
            self.assertEqual(stream["channel_layout"], "5.1")
            self.assertEqual(int(stream["sample_rate"]), _SAMPLE_RATE)
            decoded = subprocess.check_output([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-i", str(encoded), "-map", "0:a:0", "-f", "f32le",
                "-ac", "6", "-ar", str(_SAMPLE_RATE), "-"], timeout=60)
            samples = array.array("f")
            samples.frombytes(decoded)
            self.assertEqual(len(samples) % 6, 0)
            self.assertGreater(len(samples) // 6, 20000)
            # Distinct authored frequency per native speaker: catches silent
            # loss, wrong speaker order and implicit 5.1->stereo->5.1 remixes.
            indexes = range(4800, 12000, 2)
            projections = []
            for ch in range(6):
                per_tone = []
                for hz in _FREQUENCIES:
                    sine = sum(samples[i*6 + ch] * math.sin(
                        2 * math.pi * hz * i / _SAMPLE_RATE) for i in indexes)
                    cosine = sum(samples[i*6 + ch] * math.cos(
                        2 * math.pi * hz * i / _SAMPLE_RATE) for i in indexes)
                    per_tone.append(2 * math.hypot(sine, cosine) / len(indexes))
                projections.append(per_tone)
            for speaker, powers in enumerate(projections):
                self.assertGreater(powers[speaker], .06, (speaker, powers))
                self.assertGreater(powers[speaker], 4 * max(
                    power for index, power in enumerate(powers) if index != speaker),
                    (speaker, powers))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             original_sha)
            self.assertEqual(json.loads(document.read_text()), plan)

    def test_speaker_gain_revision_keeps_all_other_physical_channels(self):
        # The same original 5.1 WAV supports two independently editable
        # plans, separately encoded movies and a genuine user-selected
        # correction to FR—not a flattened/mislabeled audio replay.
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            source, original_sha, vault, plan = self._source(root)
            first_plan = root / "original-surround-plan.json"
            first_plan.write_text(json.dumps(plan), encoding="utf8")
            first_movie = root / "original-surround-film.mp4"
            first_proof = render_composition(first_plan, root, root / "vault",
                                             first_movie)
            self.assertEqual(first_proof["audio_channels"], 6)
            revised_plan = json.loads(json.dumps(plan))
            revised_plan["audio_tracks"][0]["speaker_gains_db"] = {"FR": -12}
            self.assertTrue(validate_document(
                "body.composite_mix", revised_plan, "plan"))
            graph = actual_composite_command(
                revised_plan, root, vault, root / "revision.mp4")
            filters = graph[graph.index("-filter_complex") + 1]
            self.assertIn("pan=5.1|FL=1*c0|FR=", filters)
            revised_document = root / "revised-surround-plan.json"
            revised_document.write_text(json.dumps(revised_plan), encoding="utf8")
            revised_movie = root / "revised-surround-film.mp4"
            revised_proof = render_composition(
                revised_document, root, root / "vault", revised_movie)
            self.assertEqual(revised_proof["audio_channels"], 6)
            self.assertNotEqual(revised_proof["sha256"], first_proof["sha256"])
            def speaker_rms(file):
                raw = subprocess.check_output(["ffmpeg", "-hide_banner",
                    "-loglevel", "error", "-nostdin", "-i", str(file),
                    "-map", "0:a:0", "-ar", str(_SAMPLE_RATE), "-ac", "6",
                    "-f", "f32le", "-"], timeout=60)
                pcm = array.array("f")
                pcm.frombytes(raw)
                frame_count = len(pcm) // 6
                self.assertGreater(frame_count, 12000)
                samples = range(4800, 12000)
                return [
                    math.sqrt(sum(pcm[index*6 + speaker] ** 2
                                  for index in samples) / len(samples))
                    for speaker in range(6)]
            before = speaker_rms(first_movie)
            after = speaker_rms(revised_movie)
            for speaker in range(6):
                ratio = after[speaker] / before[speaker]
                if speaker == 1:
                    self.assertGreater(ratio, 0.18)
                    self.assertLess(ratio, 0.34, (speaker, ratio))
                else:
                    self.assertGreater(ratio, 0.90, (speaker, ratio))
                    self.assertLess(ratio, 1.10, (speaker, ratio))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             original_sha)
            self.assertEqual(json.loads(first_plan.read_text()), plan)
            self.assertEqual(json.loads(revised_document.read_text()),
                             revised_plan)
            self.assertEqual(_probe_channels(revised_movie)["channel_layout"], "5.1")
            # Public CI uses synthetic authored material only; all bytes
            # exist for independent playback/review rather than a green log.
            if os.environ.get("ZX7_SURROUND_PROOF_DIR"):
                destination = Path(os.environ["ZX7_SURROUND_PROOF_DIR"])
                destination.mkdir(parents=True, exist_ok=True)
                files = [source, first_plan, first_movie,
                         revised_document, revised_movie]
                for item in files:
                    shutil.copy2(item, destination / item.name)
                (destination / "sound-proof.json").write_text(json.dumps({
                    "source_sha256": original_sha,
                    "original_movie_sha256": first_proof["sha256"],
                    "revised_movie_sha256": revised_proof["sha256"],
                    "physical_speakers": list(_SURROUND_SPEAKERS_TEST),
                    "before_rms": before, "after_rms": after,
                    "native_original_and_revision_editable": True,
                    "source_custody_unchanged": True,
                    "genuine_model_creativity_verified": False,
                    "professional_mastering_or_semantic_hearing_verified": False,
                }, indent=2) + "\n", encoding="utf8")

    def test_untrusted_surround_gains_never_execute_or_cross_into_stereo_bus(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            _, _, vault, plan = self._source(root)
            for speaker_gains in (
                {"FR": True}, {"FR": float("nan")}, {"FR": float("inf")},
                {"FR": 36}, {"FR": -120}, {"surround;rm -rf /": 10},
                ["FL", -12], "pan=5.1|FR=10*c0",
            ):
                malformed = json.loads(json.dumps(plan))
                malformed["audio_tracks"][0]["speaker_gains_db"] = speaker_gains
                with self.assertRaises(ValueError):
                    validate_document("body.composite_mix", malformed, "plan")
                with self.assertRaisesRegex(ValueError, "speaker gains|Surround"):
                    actual_composite_command(malformed, root, vault,
                                             root / "never.mp4")
            stereo = json.loads(json.dumps(plan))
            stereo["canvas"]["audio_bus"]["channel_layout"] = "stereo"
            stereo["audio_tracks"][0]["speaker_gains_db"] = {"FR": -6}
            with self.assertRaisesRegex(ValueError, "multichannel|speaker"):
                actual_composite_command(stereo, root, vault, root / "never.mp4")
            self.assertFalse((root / "never.mp4").exists())

    def test_96000_hz_six_channel_bus_has_real_decodable_speaker_clock(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            _, _, vault, plan = self._source(root)
            plan["canvas"]["audio_bus"]["sample_rate"] = 96000
            self.assertTrue(validate_document("body.composite_mix", plan, "plan"))
            project = root / "high-rate-plan.json"
            project.write_text(json.dumps(plan))
            movie = root / "high-rate-six-speaker.mp4"
            proven = render_composition(project, root, root / "vault", movie)
            self.assertTrue(proven["full_picture_and_sound_decoder_completed"])
            self.assertEqual(proven["audio_channels"], 6)
            self.assertEqual(proven["audio_sample_rate"], 96000)
            self.assertEqual(int(_probe_channels(movie)["sample_rate"]), 96000)

    def test_no_silent_multichannel_downmix_or_unapproved_upmix(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            _, _, vault, plan = self._source(root)
            missing_bus = json.loads(json.dumps(plan))
            missing_bus["canvas"].pop("audio_bus")
            with self.assertRaisesRegex(ValueError, "multichannel|channel"):
                actual_composite_command(missing_bus, root, vault, root / "never.mp4")
            # A six-channel source cannot be silently relabeled stereo.
            wrong_bus = json.loads(json.dumps(plan))
            wrong_bus["canvas"]["audio_bus"]["channel_layout"] = "stereo"
            with self.assertRaisesRegex(ValueError, "multichannel|channel"):
                actual_composite_command(wrong_bus, root, vault, root / "never.mp4")
            # Explicit surround requires *actual* matching native speaker
            # layout, not a model-requested upmix or missing source media.
            mono = root / "mono.wav"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i",
                "sine=frequency=220:sample_rate=48000:duration=0.75",
                "-c:a", "pcm_s16le", "-y", str(mono)], check=True, timeout=45)
            ref = vault.ingest(mono, mime="audio/wav", rights="owner_supplied",
                source_type="owner_upload", source_id="separate-mono-source",
                evidence="Actual distinct mono PCM", owner_or_generator="source-owner")
            wrong_source = json.loads(json.dumps(plan))
            wrong_source["audio_tracks"][0].update(
                source=mono.name, asset_id=ref["asset_id"],
                attestation_id=ref["attestation_id"])
            with self.assertRaisesRegex(ValueError, "5.1|channel"):
                actual_composite_command(wrong_source, root, vault, root / "never.mp4")
            self.assertFalse((root / "never.mp4").exists())

    def test_bus_and_surround_controls_are_typed_not_arbitrary_filter_expressions(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            _, _, vault, plan = self._source(root)
            for bus in (
                {"sample_rate": True, "channel_layout": "5.1"},
                {"sample_rate": 0, "channel_layout": "5.1"},
                {"sample_rate": 96001, "channel_layout": "5.1"},
                {"sample_rate": 48000, "channel_layout": "5.1;volume=999"},
                {"sample_rate": 48000, "channel_layout": "7.1"},
                {"channel_layout": "5.1"},
                {"sample_rate": 48000},
                {"sample_rate": 48000, "channel_layout": "5.1", "cmd": "exec"},
            ):
                bad = json.loads(json.dumps(plan))
                bad["canvas"]["audio_bus"] = bus
                with self.assertRaises(ValueError):
                    validate_document("body.composite_mix", bad, "plan")
                with self.assertRaises(ValueError):
                    actual_composite_command(bad, root, vault, root / "never.mp4")
            bad_balance = json.loads(json.dumps(plan))
            bad_balance["audio_tracks"][0]["stereo_balance"] = 0.5
            with self.assertRaisesRegex(ValueError, "stereo balance|surround|channel"):
                actual_composite_command(bad_balance, root, vault, root / "never.mp4")
