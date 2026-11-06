"""Native clip/track source identity regression, not model creativity or edit templates."""
import copy
import json
import unittest
from types import SimpleNamespace

from studio_next.native_timeline_identity import (
    assess_native_timeline_references, needs_native_timeline_identity)
from studio_next.native_creative_audit import audit_native_journal, NativeJournalError
from studio_next.native_creative_control import NativeCreativeControl
from studio_next.test_native_creative_control import (
    FakeSession, ScriptedModel, decision)

DUPLICATE_SCHEMA = {"type": "object", "properties": {
    "clipId": {"type": "string"},
    "trackId": {"type": "string"},
    "previewOnly": {"type": "boolean"},
}, "required": ["clipId"]}


def current_timeline(*, clips=(), tracks=(), truncated=False):
    return {"id": "timeline-native", "clipLimitApplied": truncated,
            "clips": list(clips), "tracks": list(tracks)}


class NativeObjectReferenceContractTests(unittest.TestCase):
    def test_real_clip_track_ids_are_accepted_not_synthesized(self):
        native = current_timeline(
            clips=[{"id": "clip-native-7", "trackId": "track-native-2"}],
            tracks=[{"id": "track-native-2"}])
        args = {"clipId": "clip-native-7", "trackId": "track-native-2"}
        self.assertTrue(needs_native_timeline_identity(args, DUPLICATE_SCHEMA))
        self.assertIsNone(assess_native_timeline_references(
            args, DUPLICATE_SCHEMA, native))
        missing = assess_native_timeline_references(
            {"clipId": "clip-1793434585049", "trackId": "track-2"},
            DUPLICATE_SCHEMA, native)
        self.assertEqual(missing["validation_keyword"], "native_clip_id_absent")
        self.assertTrue(missing["native_ids_must_be_observed_not_invented"])
        self.assertEqual(missing["native_clip_ids_sample"], ["clip-native-7"])
        self.assertEqual(missing["native_track_ids_sample"], ["track-native-2"])

    def test_empty_project_disallows_duplicate_of_nonexistent_timeline_clip(self):
        observed = current_timeline()
        refused = assess_native_timeline_references(
            {"clipId": "clip-1793434585049", "trackId": "track-2"},
            DUPLICATE_SCHEMA, observed)
        self.assertEqual(refused["validation_keyword"], "native_clip_id_absent")
        self.assertEqual(refused["native_clip_count_observed"], 0)
        self.assertEqual(refused["native_track_count_observed"], 0)

    def test_native_schema_bound_ids_only_no_generalized_artistic_guessing(self):
        other = {"type": "object", "properties": {
            "clipId": {"type": "string"}, "trackId": {"type": "string"}}}
        self.assertFalse(needs_native_timeline_identity(
            {"text": "invented"}, other))
        self.assertIsNone(assess_native_timeline_references(
            {"text": "invented"}, other, None))
        # Unknown arbitrary semantic fields are not reinterpreted as IDs.
        self.assertFalse(needs_native_timeline_identity(
            {"target": "clip-999"}, other))
        # Strictly interpret only names declared by the specific native schema.
        self.assertFalse(needs_native_timeline_identity(
            {"clipId": "clip-999"}, {"type": "object", "properties": {}}))

    def test_typed_multi_id_lookup_and_truncation_are_not_absence_proof(self):
        schema = {"type": "object", "properties": {
            "clipIds": {"type": "array"}, "trackIds": {"type": "array"}}}
        known = current_timeline(clips=[{"id": "owned-clip"}],
                                 tracks=[{"id": "owned-track"}])
        self.assertIsNone(assess_native_timeline_references(
            {"clipIds": ["owned-clip"], "trackIds": ["owned-track"]},
            schema, known))
        self.assertEqual(assess_native_timeline_references(
            {"clipIds": ["owned-clip", "missing"]}, schema,
            current_timeline(clips=[{"id": "owned-clip"}], truncated=True))[
                "validation_keyword"], "native_timeline_inventory_incomplete")
        self.assertEqual(assess_native_timeline_references(
            {"trackIds": ["missing"]}, schema, known)[
            "validation_keyword"], "native_track_id_absent")

    def test_corrupt_source_receipt_refuses_as_unverified_not_as_empty(self):
        for malformed in (
            {"clips": [], "tracks": []},
            current_timeline(clips=[{"id": ""}]),
            current_timeline(tracks=[{"id": 42}]),
            {"clips": [1], "tracks": [], "clipLimitApplied": False},
        ):
            with self.subTest(malformed=malformed):
                response = assess_native_timeline_references(
                    {"clipId": "invented"}, DUPLICATE_SCHEMA, malformed)
                self.assertEqual(response["validation_keyword"],
                                 "native_timeline_identity_unverified")


class TimelineSession(FakeSession):
    def __init__(self, timeline, *, corrupt=False):
        super().__init__()
        self.timeline = timeline
        self.corrupt = corrupt
        self.tools.append(SimpleNamespace(
            name="duplicate_clip", description="Native duplicate clip",
            input_schema=copy.deepcopy(DUPLICATE_SCHEMA)))
        # Original standard get_timeline schema supports these exact fields.
        self.tools[0].input_schema = {"type": "object", "properties": {
            "includeClips": {"type": "boolean"},
            "includeTransitions": {"type": "boolean"},
            "limit": {"type": "integer"}}}

    async def call_tool(self, name, arguments):
        if name == "get_timeline":
            self.calls.append((name, arguments))
            receipt = "not-json" if self.corrupt else json.dumps(self.timeline)
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=receipt)])
        return await super().call_tool(name, arguments)


class NativeTimelineIdentityControlTests(unittest.IsolatedAsyncioTestCase):
    async def trial(self, native, *, clip, track, corrupt=False):
        session = TimelineSession(native, corrupt=corrupt)
        model = ScriptedModel([
            decision("invoke", tool="duplicate_clip", inputs={
                "clipId": clip, "trackId": track, "previewOnly": False}),
            decision("finish", summary="Protocol ends; no creative acceptance"),
        ])
        grants = {tool.name: ("write" if tool.name in
                  ("duplicate_clip", "update_text_clip") else "read")
                  for tool in session.tools}
        result = await NativeCreativeControl(
            session, model, max_turns=2, host_tool_access=grants).run(
                "Edit actual source-footage in a native project")
        audit = audit_native_journal(result["events"],
                                     host_tool_access=grants)
        return session, model, result, audit, grants

    async def test_real_2b_hallucinated_clip_id_never_reaches_editor_write(self):
        session, model, result, audit, grants = await self.trial(
            current_timeline(), clip="clip-1793434585049", track="track-2")
        self.assertEqual(session.calls, [("get_timeline", {
            "includeClips": True, "includeTransitions": False, "limit": 1000})])
        self.assertEqual(model.observed[1]["last_rejected_native_action_feedback"][
            "validation_keyword"], "native_clip_id_absent")
        self.assertTrue(audit["journal_chain_structurally_valid"])
        self.assertFalse(any(e["kind"] == "native_tool_submitted"
                             for e in result["events"]))
        forgery = copy.deepcopy(result["events"])
        for event in forgery:
            if event.get("kind") == "host_native_timeline_inventory_observed":
                event["host_attested_read_only"] = False
                break
        with self.assertRaises(NativeJournalError):
            audit_native_journal(forgery, host_tool_access=grants)

    async def test_existing_native_ids_do_not_block_model_selected_edit(self):
        native = current_timeline(
            clips=[{"id": "native-clip", "trackId": "native-track"}],
            tracks=[{"id": "native-track"}])
        session, model, result, audit, _ = await self.trial(
            native, clip="native-clip", track="native-track")
        self.assertEqual(session.calls, [
            ("get_timeline", {
                "includeClips": True, "includeTransitions": False, "limit": 1000}),
            ("duplicate_clip", {"clipId": "native-clip",
                                "trackId": "native-track", "previewOnly": False}),
        ])
        self.assertTrue(audit["journal_chain_structurally_valid"])
        self.assertTrue(any(e["kind"] == "native_tool_result" and
                            e.get("tool") == "duplicate_clip"
                            for e in result["events"]))
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_failed_read_never_grants_or_dispatches_write(self):
        session, model, result, audit, _ = await self.trial(
            current_timeline(), clip="fake", track="fake", corrupt=True)
        self.assertEqual([name for name, _ in session.calls], ["get_timeline"])
        self.assertEqual(model.observed[1]["last_rejected_native_action_feedback"][
            "validation_keyword"], "native_timeline_identity_unverified")
        self.assertTrue(audit["journal_chain_structurally_valid"])


if __name__ == "__main__":
    unittest.main()
