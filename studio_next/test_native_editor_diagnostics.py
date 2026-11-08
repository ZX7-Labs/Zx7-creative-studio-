"""Read-only native-state facts; fixtures never imply creative acceptance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from studio_next.native_editor_diagnostics import (
    describe_native_text_semantics, inspect_native_content,
    native_content_diagnostics_source_verified,
)


def timeline():
    return {"id": "actual-timeline", "clipLimitApplied": False,
            "tracks": [{"id": "v1", "type": "video", "visible": True},
                       {"id": "a1", "type": "audio", "muted": False}],
            "clips": [{"id": "title", "type": "text", "trackId": "v1",
                       "textProperties": {"text": "PRIVATE TITLE"},
                       "transform": {"opacity": 0}, "enabled": True}]}


def receipt(value):
    return {"isError": False, "content": [{"type": "text", "text": json.dumps(value)}]}


class NativeContentDiagnosticsTests(unittest.TestCase):
    def test_zero_base_and_baked_zero_envelope_are_facts_not_forced_fixes(self):
        for transform, curve, expected in (
                ({"opacity": 0}, None, True),
                ({"opacity": 100}, [{"time": 0, "value": 0}, {"time": 2, "value": 0}], True),
                ({"opacity": 0}, [{"time": 0, "value": 0}, {"time": 1, "value": 100}], False),
                ({"opacity": 100}, [], False)):
            data = timeline()
            data["clips"][0]["transform"] = transform
            if curve is not None:
                data["clips"][0]["keyframes"] = {"opacity": curve}
            before = copy.deepcopy(data)
            report = inspect_native_content(receipt(data))
            with self.subTest(transform=transform, curve=curve):
                self.assertEqual(report["warning_counts"].get("opacity_envelope_zero", 0), int(expected))
                self.assertEqual(data, before)
                self.assertFalse(report["automatic_repairs"])
                self.assertFalse(report["physical_output_inspected"])
                self.assertFalse(report["artistic_quality_approved"])

    def test_hidden_disabled_muted_and_absent_lanes_are_reported_without_claiming_silence(self):
        data = timeline()
        data["clips"][0]["enabled"] = False
        data["tracks"][0]["visible"] = False
        data["tracks"][1]["muted"] = True
        report = inspect_native_content(receipt(data))
        self.assertEqual(report["warning_counts"], {
            "audio_track_muted": 1, "visual_clip_disabled": 1,
            "visual_track_hidden": 1, "opacity_envelope_zero": 1,
            "no_audio_type_clips_embedded_video_audio_unassessed": 1})
        data["tracks"].pop()
        self.assertEqual(inspect_native_content(receipt(data))["warning_counts"]["no_audio_tracks"], 1)
        self.assertFalse(report["audio_semantically_heard"])

    def test_truncated_inventory_cannot_prove_absent_audio_clips(self):
        data = timeline()
        data["clipLimitApplied"] = True
        report = inspect_native_content(receipt(data))
        self.assertFalse(report["clip_inventory_complete"])
        self.assertNotIn("no_audio_type_clips_embedded_video_audio_unassessed", report["warning_counts"])

    def test_results_are_bounded_and_do_not_echo_private_source_fields(self):
        data = timeline()
        original = data["clips"][0]
        data["clips"] = [{**original, "id": f"clip-{i}", "url": "/PRIVATE/path.mp4"}
                         for i in range(1000)]
        report = inspect_native_content(receipt(data), warning_limit=2)
        self.assertEqual(len(report["warnings"]), 2)
        self.assertEqual(report["warning_counts"]["opacity_envelope_zero"], 1000)
        self.assertTrue(report["warnings_truncated"])
        self.assertNotIn("PRIVATE", json.dumps(report))
        self.assertLess(len(json.dumps(report)), 2000)

    def test_malformed_or_failed_receipts_do_not_yield_content_facts(self):
        good = receipt(timeline())
        invalid = [None, {}, {**good, "isError": True}, {**good, "isError": "false"},
                   {**good, "is_error": True}, {**good, "content": []},
                   {"content": [{"type": "text", "text": '{"id":"one","id":"two"}'}]},
                   {"content": [{"type": "text", "text": "x" * (2 * 1024 * 1024 + 1)}]}]
        for value in invalid:
            with self.subTest(value=str(value)[:50]), self.assertRaises(ValueError):
                inspect_native_content(value)
        for limit in (True, 0, 33, 1.5, "2"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                inspect_native_content(good, warning_limit=limit)

    def test_ambiguous_inventory_and_animation_fail_closed(self):
        changes = [
            lambda d: d.pop("clipLimitApplied"),
            lambda d: d["tracks"].append(copy.deepcopy(d["tracks"][0])),
            lambda d: d["clips"].append(copy.deepcopy(d["clips"][0])),
            lambda d: d["clips"][0].update(trackId="missing"),
            lambda d: d["clips"][0].update(enabled="false"),
            lambda d: d["clips"][0].update(transform={"opacity": True}),
            lambda d: d["clips"][0].update(transform={"opacity": 10**1000}),
            lambda d: d["clips"][0].update(transform=[]),
            lambda d: d["clips"][0].update(keyframes=[]),
            lambda d: d["clips"][0].update(keyframes={"opacity": [{"time": 0, "value": None}]}),
            lambda d: d["clips"][0].update(keyframes={"opacity": "zero"}),
            lambda d: d["clips"][0].update(keyframes={"opacity": [{"time": -1, "value": 0}]}),
        ]
        for change in changes:
            data = timeline()
            change(data)
            with self.subTest(data=str(data)[:100]), self.assertRaises(ValueError):
                inspect_native_content(receipt(data))

    def test_semantic_description_changes_do_not_rewrite_schema_rules_or_original(self):
        schema = {"type": "object", "properties": {
            "transform": {"type": "object", "properties": {"opacity": {"type": "number"}}},
            "animationPreset": {"type": "string", "enum": ["fade", "none"]}}}
        original = copy.deepcopy(schema)
        enriched = describe_native_text_semantics("add_text_clip", schema)
        self.assertEqual(schema, original)
        self.assertIn("steady-state target", enriched["properties"]["transform"]["properties"]["opacity"]["description"])
        for node in (enriched["properties"]["transform"]["properties"]["opacity"],
                     enriched["properties"]["animationPreset"]):
            node.pop("description")
        self.assertEqual(enriched, original)
        with self.assertRaises(ValueError):
            describe_native_text_semantics("add_text_clip", {"type": "object"})

    def test_source_attestation_checks_real_pin_and_rejects_arbitrary_paths(self):
        source = Path(__file__).resolve().parents[1] / "third_party" / "velorn"
        self.assertTrue(native_content_diagnostics_source_verified(source))
        with tempfile.TemporaryDirectory() as scratch:
            self.assertFalse(native_content_diagnostics_source_verified(Path(scratch)))
        self.assertFalse(native_content_diagnostics_source_verified(str(source)))


if __name__ == "__main__":
    unittest.main()
