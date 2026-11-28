"""Actual NativeCreativeControl decision-loop regression, no fake provider acceptance."""
import copy
import json
from types import SimpleNamespace
import unittest

from studio_next.native_creative_control import NativeCreativeControl
from studio_next.test_native_creative_control import ScriptedModel, decision


class SourceClipFeedbackTests(unittest.IsolatedAsyncioTestCase):
    async def run_scenario(self, *, second_clip_list=None, alternate_project=False):
        original = [
            {"id": "video-original", "type": "video", "assetId": "original-footage",
             "trackId": "video1", "startTime": 0, "duration": 6},
            {"id": "voice-original", "type": "audio", "assetId": "original-sound",
             "trackId": "audio1", "startTime": 0, "duration": 6},
        ]
        if second_clip_list is None:
            second_clip_list = [
                {"id": "title-now", "type": "text", "assetId": None,
                 "trackId": "video1", "startTime": 0, "duration": 6},
                copy.deepcopy(original[1]),
            ]
        writes = 0
        timeline_reads = 0
        class Session:
            def __init__(self):
                self.tools = [
                    SimpleNamespace(name="get_project", description="Real native project",
                                    input_schema={"type": "object", "properties": {}}),
                    SimpleNamespace(name="get_timeline", description="Real native timeline",
                                    input_schema={"type": "object", "properties": {
                                        "includeClips": {"type": "boolean"},
                                        "limit": {"type": "integer"}}}),
                    SimpleNamespace(name="add_text_clip", description="Create title on video track",
                                    input_schema={"type": "object", "properties": {
                                        "text": {"type": "string"},
                                        "previewOnly": {"type": "boolean"}},
                                        "required": ["text"]}),
                ]
                self.calls = []
            async def list_tools(self):
                return SimpleNamespace(tools=self.tools)
            async def call_tool(self, name, args):
                nonlocal writes, timeline_reads
                self.calls.append((name, dict(args)))
                if name == "get_project":
                    location = ("/private/another-project" if alternate_project and writes
                                else "/private/owner-project")
                    doc = {"mcp": {"hasProject": True},
                           # Real pinned get_project has name/path/created,
                           # NOT a fabricated stable project.id.
                           "project": {"name": "Editorial", "path": location,
                                       "created": "2026-11-25T02:10:00Z",
                                       "currentTimelineId": "timeline1"},
                           "currentTimeline": {"id": "timeline1", "clipCount": 2}}
                elif name == "get_timeline":
                    timeline_reads += 1
                    doc = {"id": "timeline1",
                           "clipLimitApplied": (second_clip_list == "TRUNCATED" and writes > 0),
                           "tracks": [{"id": "video1", "type": "video"},
                                      {"id": "audio1", "type": "audio"}],
                           "clips": (original if writes == 0 else
                                     original[:1] if second_clip_list == "TRUNCATED" else second_clip_list)}
                elif name == "add_text_clip":
                    writes += 1
                    doc = {"success": True, "result": {"previewOnly": False, "clipId": "title-now"}}
                else:
                    raise AssertionError(name)
                return SimpleNamespace(is_error=False, content=[
                    SimpleNamespace(type="text", text=json.dumps(doc))])

        session = Session()
        model = ScriptedModel([
            decision("invoke", tool="get_timeline", inputs={"includeClips": True, "limit": 1000}),
            decision("invoke", tool="add_text_clip", inputs={"text": "Title", "previewOnly": False}),
            decision("invoke", tool="get_timeline", inputs={"includeClips": True, "limit": 1000}),
            decision("finish", summary="Only procedural test, not independent quality"),
        ])
        grants = {"get_project": "read", "get_timeline": "read", "add_text_clip": "write"}
        outcome = await NativeCreativeControl(
            session, model, max_turns=4, catalog_mode="full",
            host_tool_access=grants, host_content_revision_tools=("add_text_clip",),
        ).run("An original source-backed video title editorial trial")
        return outcome, model, session, writes, timeline_reads

    async def test_disappearing_source_video_is_reported_after_model_selected_second_timeline_read(self):
        result, model, session, writes, reads = await self.run_scenario()
        self.assertEqual(writes, 1)
        self.assertEqual(reads, 2)
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertEqual(model.observed[2]["native_source_clip_change_after_observation"], None)
        change = model.observed[3]["native_source_clip_change_after_observation"]
        self.assertEqual(change["status"], "compared_model_selected_native_timelines")
        self.assertEqual(change["removed_source_video_clip_ids"], ["video-original"])
        self.assertEqual(change["source_video_asset_ids_no_longer_on_timeline"], ["original-footage"])
        self.assertEqual(change["removed_source_audio_clip_ids"], [])
        self.assertTrue(change["may_be_intentional_or_concurrent"])
        self.assertTrue(change["no_automatic_repair"])
        self.assertEqual(sum(name == "add_text_clip" for name, _ in session.calls), 1)
        from studio_next.native_creative_audit import audit_native_journal
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access={"get_project": "read",
            "get_timeline": "read", "add_text_clip": "write"},
            host_content_revision_tools=("add_text_clip",))
            ["journal_chain_structurally_valid"])

    async def test_source_split_retains_asset_even_if_old_clip_identity_disappears(self):
        after = [
            {"id": "video-split-half", "type": "video", "assetId": "original-footage",
             "trackId": "video1", "startTime": 0, "duration": 3},
            {"id": "title-now", "type": "text", "assetId": None,
             "trackId": "video1", "startTime": 3, "duration": 3},
            {"id": "voice-original", "type": "audio", "assetId": "original-sound",
             "trackId": "audio1", "startTime": 0, "duration": 6},
        ]
        _, model, _, writes, _ = await self.run_scenario(second_clip_list=after)
        self.assertEqual(writes, 1)
        change = model.observed[3]["native_source_clip_change_after_observation"]
        self.assertEqual(change["removed_source_video_clip_ids"], ["video-original"])
        self.assertEqual(change["source_video_asset_ids_no_longer_on_timeline"], [])
        self.assertEqual(change["source_video_clips_after"], 1)

    async def test_legitimate_separate_title_layer_preserves_source_with_no_disappearance(self):
        after = [
            {"id": "video-original", "type": "video", "assetId": "original-footage",
             "trackId": "video1", "startTime": 0, "duration": 6},
            {"id": "voice-original", "type": "audio", "assetId": "original-sound",
             "trackId": "audio1", "startTime": 0, "duration": 6},
            {"id": "title-now", "type": "text", "assetId": None,
             "trackId": "video1", "startTime": 0, "duration": 6},
        ]
        _, model, _, _, _ = await self.run_scenario(second_clip_list=after)
        change = model.observed[3]["native_source_clip_change_after_observation"]
        self.assertEqual(change["removed_source_video_clip_count"], 0)
        self.assertEqual(change["removed_source_audio_clip_count"], 0)
        self.assertEqual(change["source_video_asset_ids_no_longer_on_timeline"], [])

    async def test_deleted_audio_source_is_reported_separately_from_picture(self):
        after = [
            {"id": "video-original", "type": "video", "assetId": "original-footage",
             "trackId": "video1", "startTime": 0, "duration": 6},
            {"id": "title-now", "type": "text", "assetId": None,
             "trackId": "video1", "startTime": 0, "duration": 6},
        ]
        _, model, _, _, _ = await self.run_scenario(second_clip_list=after)
        change = model.observed[3]["native_source_clip_change_after_observation"]
        self.assertEqual(change["removed_source_video_clip_ids"], [])
        self.assertEqual(change["removed_source_audio_clip_ids"], ["voice-original"])
        self.assertEqual(change["source_audio_clips_after"], 0)

    async def test_truncated_timeline_never_mints_false_source_loss(self):
        _, model, _, writes, reads = await self.run_scenario(second_clip_list="TRUNCATED")
        self.assertEqual(writes, 1)
        self.assertEqual(reads, 2)
        change = model.observed[3]["native_source_clip_change_after_observation"]
        self.assertIsNone(change)

    async def test_project_switch_with_same_timeline_id_never_mints_false_source_loss(self):
        _, model, _, writes, reads = await self.run_scenario(alternate_project=True)
        self.assertEqual(writes, 1)
        self.assertEqual(reads, 2)
        self.assertIsNone(model.observed[3]["native_source_clip_change_after_observation"])


if __name__ == "__main__":
    unittest.main()
