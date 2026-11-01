"""Real encoded preview evidence and hostile sparse edit validation."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image

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
