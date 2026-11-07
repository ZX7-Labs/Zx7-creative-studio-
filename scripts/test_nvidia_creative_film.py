"""Real renderer fixture tests, never a claimed model-generated artistic film."""
import json
import tempfile
from pathlib import Path
import unittest

from scripts.nvidia_creative_film import (
    FilmProofError, physical_proof, validate_artistic_control,
)
from scripts.nvidia_film_request import validate_request
from scripts.nvidia_smoke_request import SmokeRequestError


def _renderer_contract_only():
    # This deliberately boring PROTOCOL TEST is never the delivered film.
    # It proves arbitrary model-authored IR can be validated and encoded.
    return {
        "project": {
            "title": "REAL RENDERER PROTOCOL FIXTURE",
            "creative_intent": "Physical encoder test, not artistic work",
            "width": 640, "height": 360, "background": "#102030",
            "voice": "no_voice", "score": [],
            "background_noise": {"gain": 0, "seed": 17},
            "audio_mix": {"fade_in_seconds": 0,
                          "fade_out_seconds": .2, "peak_ceiling": .92},
        },
        "assets": [{
            "id": "probe_typography", "status": "verified",
            "rights": "generated_original",
            "location": "inline://probe_typography",
            "artwork": {
                "size": [360, 100],
                "items": [{"type": "text", "text": "PROTOCOL TEST",
                           "at": [15, 25], "size": 32,
                           "font": "sans", "fill": "#FFFFFF"}],
            },
        }],
        "shots": [
            {
                "id": "probe_scene_a", "purpose": "Test actual first shot",
                "duration_seconds": 2.5, "narration": "",
                "asset_refs": ["probe_typography"], "fact_refs": [],
                "layers": [{"asset": "probe_typography", "x": 320, "y": 180,
                            "animate": {"opacity": [[0, 0], [1, 1]]}}],
                "cues": [{
                    "type": "synth", "at": 0, "seconds": 1.0,
                    "gain": .12, "noise_gain": 0, "seed": 19,
                    "partials": [{
                        "start_hz": 220, "end_hz": 330,
                        "amplitude": .6, "phase_radians": 0,
                    }],
                    "envelope": [[0, 0], [.1, .5], [1, 0]],
                }],
            },
            {
                "id": "probe_scene_b", "purpose": "Test real second shot",
                "duration_seconds": 2.5, "narration": "",
                "asset_refs": ["probe_typography"], "fact_refs": [],
                "layers": [{"asset": "probe_typography", "x": 250, "y": 180,
                            "animate": {"opacity": [[0, .2], [2, 1]]}}],
                "cues": [],
            },
        ],
        "tool_graph": [{
            "id": "composite", "tool_id": "motion_studio.composite",
            "inputs": {}, "purpose": "Only physical renderer test",
            "depends_on": [],
        }],
    }


class OriginalModelFilmTests(unittest.TestCase):
    def test_reviewed_request_uses_no_stock_and_fixed_token_cap(self):
        request=(Path(__file__).resolve().parents[1] /
                 "research" / "nvidia-film-request.json")
        self.assertEqual(validate_request(request)["max_model_attempts"], 3)
        base=json.loads(request.read_text())
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"bad.json"
            for change in (
                    {"allow_external_stock_media": True},
                    {"synthetic_only": False},
                    {"max_model_attempts": 40},
                    {"model_id": "other/other"},
                    {"api_key": "not-permitted"},
                    {"kind": "upload-private-film"},
            ):
                path.write_text(json.dumps({**base,**change}))
                with self.subTest(change=change), self.assertRaises(SmokeRequestError):
                    validate_request(path)

    def test_actual_original_render_contract_and_no_preset_sound(self):
        original=_renderer_contract_only()
        compiled=validate_artistic_control(original)
        self.assertEqual(compiled["score"], [])
        self.assertEqual(compiled["scenes"][0]["cues"][0]["type"], "synth")
        self.assertEqual(compiled["assets"]["probe_typography"]["items"][0]["text"],
                         "PROTOCOL TEST")

    def test_missing_model_audio_motion_and_stock_music_rejected(self):
        original=_renderer_contract_only()
        for changed in ("stock", "sound", "static", "no_mix"):
            ir=json.loads(json.dumps(original))
            if changed == "stock":
                ir["assets"][0]["rights"] = "stock_free_unverified"
            elif changed == "sound":
                ir["shots"][0]["cues"][0]["type"] = "tap"
            elif changed == "static":
                ir["shots"][0]["layers"][0].pop("animate")
                ir["shots"][1]["layers"][0].pop("animate")
            else:
                ir["project"].pop("audio_mix")
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_artistic_control(ir)

    def test_existing_studio_physically_renders_and_decodes_test_only_ir(self):
        from motion_studio.render import render
        from studio_next.silent_audio import make_silent_timing
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            project=root/"original.json"
            project.write_text(json.dumps(validate_artistic_control(
                _renderer_contract_only())))
            output=root/"render"
            make_silent_timing(project,output)
            movie=render(project,output,width=640,fps=24)
            proof=physical_proof(movie,5.0)
            self.assertTrue(proof["full_decode_passed"])
            self.assertEqual(proof["width"],640)
            self.assertGreater(proof["decoded_soundtrack_rms"],.00001)


if __name__=="__main__":
    unittest.main()
