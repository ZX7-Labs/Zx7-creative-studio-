"""Real encoded preview evidence and hostile sparse edit validation."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave

import numpy as np
from PIL import Image, ImageDraw

from scripts.run_local_brain_creative_film import (_fit_film_caption, _title_overlay, _render_music, _validate_decision)

from .model_film_revision import (
    ModelFilmRevisionError, apply_model_selected_revision,
    encoded_film_contact_sheet,
)


class LocalFilmRevisionTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "title": "An Original Film",
            "story": "An evolving physical source-authored visual journey.",
            "beats": [
                {"artwork": 0, "caption": "Quiet beginnings",
                 "camera": "still", "weight": 1},
                {"artwork": 1, "caption": "Motion emerges",
                 "camera": "push", "weight": 2},
            ],
            "music": {"bpm": 80, "root_midi": 50,
                      "mode": "minor", "progression": [0, 2]},
        }

    def decision(self, **kw):
        base = {"action": "revise", "beat_index": 1,
                "field": "camera", "value": "pull",
                "expected_before":"push",
                "reason": "The actual second shot needs a deliberate wider resolution."}
        base.update(kw)
        return base

    def test_model_can_choose_only_one_real_sparse_typed_change(self):
        original = repr(self.plan)
        revised, receipt = apply_model_selected_revision(
            self.plan, self.decision(), asset_count=2)
        self.assertEqual(revised["beats"][1]["camera"], "pull")
        self.assertEqual(self.plan["beats"][1]["camera"], "push")
        self.assertEqual(repr(self.plan), original)
        self.assertEqual(receipt["changed_fields"], ["beats[1].camera"])
        self.assertTrue(receipt["revision_applied"])
        paced, _ = apply_model_selected_revision(
            self.plan, self.decision(field="weight", value="0.75", expected_before="2"), asset_count=2)
        self.assertEqual(paced["beats"][1]["weight"], 0.75)
        selected, _ = apply_model_selected_revision(
            self.plan, self.decision(field="artwork", value="0", expected_before="1"), asset_count=2)
        self.assertEqual(selected["beats"][1]["artwork"], 0)
        caption, _ = apply_model_selected_revision(
            self.plan, self.decision(field="caption", value="A fresh original sentence",
                                        expected_before="Motion emerges"),
            asset_count=2, source_titles=[
                "Sunrise painting", "Motion capture abstract sculpture"])
        self.assertEqual(caption["beats"][1]["caption"], "A fresh original sentence")
        kept, claim = apply_model_selected_revision(
            self.plan, self.decision(action="keep"), asset_count=2)
        self.assertEqual(kept, self.plan)
        self.assertFalse(claim["revision_applied"])

    def test_forged_native_decisions_rejected_without_changing_original(self):
        bad = [
            self.decision(beat_index=True), self.decision(beat_index=200),
            self.decision(field="shell"),
            self.decision(field=[]),
            self.decision(expected_before="A different shot's caption"),
            self.decision(expected_before="Motion emerges"),
            {key:value for key,value in self.decision().items()
             if key!="expected_before"}, self.decision(field="camera", value="zoom='system()'"),
            self.decision(field="camera", value="push"),
            self.decision(field="artwork", value="../../tmp"),
            self.decision(field="artwork", value="2"),
            self.decision(field="weight", value="NaN"),
            self.decision(field="weight", value="1e100000"),
            self.decision(field="weight", value="0"),
            self.decision(field="weight", value="-1"),
            self.decision(field="caption", value=""),
            self.decision(reason="short"),
            {**self.decision(), "grant_root": "/"},
        ]
        snapshot = repr(self.plan)
        for decision in bad:
            with self.subTest(decision=decision):
                with self.assertRaises(ModelFilmRevisionError):
                    apply_model_selected_revision(self.plan, decision, asset_count=2)
                self.assertEqual(repr(self.plan), snapshot)




    def test_original_model_score_has_no_bar_or_beat_clicks(self):
        """Observed prior production soundtrack had 0.16-FS sample jumps at
        2.727, 5.455, 10.909 seconds at its exact neural 88-BPM boundaries.
        The actual PCM executor now crossfades chords and zero-anchors beats,
        without changing the original model's pitch or chord decisions.
        """
        choices = {"bpm":88, "root_midi":57, "mode":"minor",
                   "progression":[0,3,4,2]}
        with tempfile.TemporaryDirectory() as root:
            wav_path=Path(root)/"model-composed-soundtrack.wav"
            _render_music(choices,wav_path,duration_seconds=8,sample_rate=48000)
            with wave.open(str(wav_path),"rb") as snd:
                self.assertEqual(snd.getnframes(),8*48000)
                self.assertEqual(snd.getframerate(),48000)
                self.assertEqual(snd.getnchannels(),2)
                self.assertEqual(snd.getsampwidth(),2)
                pcm=np.frombuffer(snd.readframes(snd.getnframes()),
                                  dtype="<i2").reshape(-1,2)
            left=pcm[:,0].astype(np.float64)/32768
            right=pcm[:,1].astype(np.float64)/32768
            differences=np.abs(np.diff(left))
            # Independent sample oracle, not authored by the synthesizer.
            self.assertLess(float(np.max(differences)),0.05)
            self.assertGreater(float(np.max(np.abs(left))),0.06)
            self.assertFalse(np.array_equal(left,right),
                             "Real source stereo must not be falsely duplicated")
            # At the instant of the historical 4/4 chord boundary there is
            # no discontinuity above the physical single-sample limit.
            for bar_time in (4*60/88,8*60/88):
                frame=int(bar_time*48000)
                self.assertLess(
                    float(np.max(differences[frame-2:frame+2])),0.05)

    def test_invalid_title_or_unbreakable_caption_rejected_before_render(self):
        plan=dict(self.plan)
        plan["beats"]=[dict(x) for x in self.plan["beats"]]
        with self.assertRaisesRegex(ValueError, "cannot fit"):
            plan["beats"][1]["caption"]="Z"*100
            _validate_decision(plan,[{},{}])
        with self.assertRaisesRegex(ValueError, "title exceeds"):
            plan["beats"][1]["caption"]="A fit caption"
            plan["title"]="M"*70
            _validate_decision(plan,[{},{}])

    def test_full_neural_caption_respects_actual_final_movie_safe_area(self):
        """Regress a visibly clipped source name in the prior 60-second film.

        The renderer must measure and lay out the entire model-authored string,
        not crop after 100 characters, break source metadata arbitrarily, or
        hide overflowing text behind the progress line.
        """
        source_caption = (
            "Pereslavl-Zalessky - Museum of Tricks and Ingenuity - "
            "hand woodblock for textile printing 1"
        )
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "art-director-caption.png"
            _title_overlay("Echoes in Vellum", source_caption, 2, 6, output)
            with Image.open(output) as frame:
                self.assertEqual(frame.size, (1280, 720))
                self.assertEqual(frame.mode, "RGBA")
                draw = ImageDraw.Draw(frame)
                layout = _fit_film_caption(
                    draw, source_caption, max_width=1128, max_height=112)
                self.assertEqual(
                    " ".join(layout["lines"]), source_caption)
                self.assertLessEqual(
                    layout["bbox"][2]-layout["bbox"][0],1128)
                self.assertLessEqual(
                    layout["bbox"][3]-layout["bbox"][1],112)
                self.assertGreaterEqual(layout["font_px"],17)
                self.assertLessEqual(len(layout["lines"]),2)
                # Original composited title area and progress region cannot
                # be in the same vertical band after physical rendering.
                self.assertLess(514+(layout["bbox"][3]-layout["bbox"][1]),644)
            with self.assertRaisesRegex(ValueError, "cannot fit"):
                _fit_film_caption(
                    ImageDraw.Draw(Image.new("RGBA", (1280,720))),
                    "Z"*250, max_width=300, max_height=40)

    def test_actual_neural_foreign_museum_attribution_rejected(self):
        """Reproduce a real local-Qwen bug: it copied source 0's museum/date
        into source 1's newly edited textile-block caption, despite correct
        beat index, previous caption and successful native MP4 export.
        """
        original = self.plan["beats"][1]
        original["caption"] = "Textile Printing Block MET 1971.87"
        titles = [
            "Frog on Lilypad, Chinese, 19th century, gouache on paper - Fitchburg Art Museum",
            "Textile Printing Block MET 1971.87img.jpg",
        ]
        hallucinated = self.decision(
            field="caption",
            expected_before=original["caption"],
            value="Textile Block MET 1971.87 - Carved in Stone, 19th century - Fitchburg Art Museum",
        )
        before = repr(self.plan)
        with self.assertRaisesRegex(ModelFilmRevisionError,
                                    "unsupported|borrows"):
            apply_model_selected_revision(
                self.plan, hallucinated, asset_count=2, source_titles=titles)
        self.assertEqual(before, repr(self.plan))
        # A model's original creative caption may be changed without borrowing
        # another source's named provenance, dates or invented identifiers.
        safe = self.decision(
            field="caption", expected_before=original["caption"],
            value="Textile Printing Block MET 1971.87 - Patterns of memory",
        )
        revised, evidence = apply_model_selected_revision(
            self.plan, safe, asset_count=2, source_titles=titles)
        self.assertEqual(revised["beats"][1]["caption"], safe["value"])
        self.assertTrue(evidence["cross_asset_attribution_checked"])
        self.assertFalse(evidence["semantic_fact_check_or_legal_rights_certified"])
        with self.assertRaisesRegex(ModelFilmRevisionError, "source metadata"):
            apply_model_selected_revision(
                self.plan, safe, asset_count=2)
        with self.assertRaisesRegex(ModelFilmRevisionError, "numeric"):
            apply_model_selected_revision(
                self.plan, self.decision(
                    field="caption", expected_before=original["caption"],
                    value="Textile Printing Block MET 1971.87 - invented provenance 1889",
                ), asset_count=2, source_titles=titles)

    def test_real_encoded_movie_frames_and_source_hash_are_bound_to_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            movie = root / "film.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=red:s=320x180:r=24:d=1",
                "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=24:d=1",
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[out]",
                "-map", "[out]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(movie)], check=True, timeout=35)
            sheet = root / "actually-decoded.png"
            receipt = encoded_film_contact_sheet(
                movie, [24, 24], sheet, fps=24)
            self.assertEqual(
                hashlib.sha256(movie.read_bytes()).hexdigest(),
                receipt["source_sha256"])
            self.assertEqual(
                hashlib.sha256(sheet.read_bytes()).hexdigest(),
                receipt["preview_sha256"])
            self.assertEqual(receipt["decoded_frame_count"], 2)
            self.assertEqual(receipt["source_frame_count"], 48)
            self.assertTrue(sheet.stat().st_size > 1000)
            with Image.open(sheet) as visual:
                red = visual.getpixel((160, 90))
                blue = visual.getpixel((480, 90))
                # Independent physical oracle: two film times must actually
                # depict different decoded sources, not repeated thumbnails.
                self.assertGreater(red[0], red[2] + 60)
                self.assertGreater(blue[2], blue[0] + 60)
            with self.assertRaises(ModelFilmRevisionError):
                encoded_film_contact_sheet(movie, [24, 24], sheet, fps=24)
            outside = root / "outside.png"
            dangling = root / "dangling-review.png"
            dangling.symlink_to(outside)
            with self.assertRaises(ModelFilmRevisionError):
                encoded_film_contact_sheet(movie, [24, 24], dangling, fps=24)
            self.assertFalse(outside.exists(),
                             "Symlink must never create outside preview output")
            with self.assertRaises(ModelFilmRevisionError):
                encoded_film_contact_sheet(movie, [24, 0], root / "bad.png", fps=24)


if __name__ == "__main__":
    unittest.main()
