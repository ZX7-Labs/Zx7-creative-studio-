"""Pinned native identity contract: synthetic gateway traces + real upstream Node ABI separately.

These tests DO NOT certify a live human session, real GPU model or professional
creative judgment. They verify the host cannot turn a plausible string into a
native object and that read-only source observations precede writes.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from studio_next.body_editor_client import host_pre_dispatch_rejection
from studio_next.capability_gateway import CapabilityGateway, CapabilityExecutionError
from studio_next.capability_mcp_session import CapabilityGatewayMcpSession
from studio_next.capability_session_budget import CapabilitySessionBudget
from studio_next.native_editor_identity import (
    NativeEditorIdentityReader, pinned_native_editor_identity_policy,
)


class NativeReadSession:
    def __init__(self):
        self.calls = []
        self.project_id = "native-owned-project"
        self.revision = "revision-1"
        self.current_timeline = "native-active-timeline"
        self.tracks = [{"id": "video-1", "type": "video", "name": "Visual"}]
        self.clips = [{"id": "clip-1", "trackId": "video-1", "assetId": "asset-1"}]
        self.assets = [{"id": "asset-1", "type": "video", "name": "Original"}]
        self.error_tool = None
        self.malformed_tool = None
        self.human_edit_during_read = False
        self.fail_before_source = False
        self.limit_assets = False
        self.limit_clips = False
        self.write_attempts = 0
        self.tools = [
            SimpleNamespace(name=name, description="Pinned read " + name,
                input_schema={"type": "object", "properties": {
                    "includeClips": {"type": "boolean"}, "limit": {"type": "integer"}}})
            for name in ("get_project", "get_timeline", "get_assets")
        ]
        self.tools.append(SimpleNamespace(
            name="update_text_clip", description="Native author-chosen edit",
            input_schema={"type": "object", "properties": {
                "clipId": {"type": "string"},
                "text": {"type": "string"},
                "previewOnly": {"type": "boolean"}},
                "required": ["clipId", "text"]}))
        self.tools.append(SimpleNamespace(
            name="add_asset_to_timeline", description="Native clip placement",
            input_schema={"type": "object", "properties": {
                "assetId": {"type": "string"},
                "trackId": {"type": "string"},
                "previewOnly": {"type": "boolean"}}}))

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools, nextCursor=None)

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        await asyncio.sleep(0)
        if name == self.error_tool:
            return SimpleNamespace(is_error=True, content=[
                SimpleNamespace(type="text", text="private original path")])
        if name == self.malformed_tool:
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text="unparseable" )])
        if name in ("update_text_clip", "add_asset_to_timeline"):
            self.write_attempts += 1
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text='{"applied":true}')])
        if name == "get_project":
            if self.fail_before_source:
                raise RuntimeError("private /home/sensitive/owned-media.mov")
            if self.human_edit_during_read and sum(
                    c[0] == "get_project" for c in self.calls) == 2:
                self.revision = "revision-human"
            data = {
                "project": {
                    # Exact pinned Velorn source contract intentionally has
                    # NO project.id. Source identity uses the active timeline,
                    # name and project path, which are never echoed.
                    "name": self.project_id,
                    "path": "/private/owner/native-project",
                    "currentTimelineId": self.current_timeline},
                "mcp": {"hasProject": True,
                        "lastSnapshotAt": self.revision},
                "currentTimeline": {
                    "id": self.current_timeline,
                    "trackCount": len(self.tracks),
                    "clipCount": len(self.clips)},
                "assetCount": len(self.assets),
                "generatedAt": self.revision,
            }
        elif name == "get_timeline":
            data = {
                "id": self.current_timeline, "tracks": self.tracks,
                "clips": self.clips,
                "clipLimitApplied": self.limit_clips}
        elif name == "get_assets":
            data = {
                "count": len(self.assets), "assets": self.assets,
                "limitApplied": self.limit_assets}
        else:
            raise AssertionError("unsupported tool: " + name)
        return SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps(data))])


GRANTS = {
    "get_project": "read", "get_timeline": "read",
    "get_assets": "read", "update_text_clip": "write",
    "add_asset_to_timeline": "write",
}


class PinnedReaderUnitTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.native = NativeReadSession()
        self.reader = NativeEditorIdentityReader(self.native, GRANTS)

    async def test_exact_source_counts_and_four_real_read_only_calls(self):
        proof = await self.reader()
        self.assertEqual(proof["clips"]["ids"], ["clip-1"])
        self.assertEqual(proof["assets"]["ids"], ["asset-1"])
        self.assertEqual(proof["tracks"]["ids"], ["video-1"])
        self.assertTrue(proof["clips"]["complete"])
        self.assertEqual([name for name, _ in self.native.calls],
                         ["get_project", "get_timeline", "get_assets", "get_project"])
        self.assertEqual(self.native.write_attempts, 0)
        self.assertEqual(self.native.calls[1][1]["limit"], 1000)
        self.assertEqual(self.native.calls[2][1]["limit"], 1000)

    async def test_human_change_between_reads_fails_without_write(self):
        self.native.human_edit_during_read = True
        with self.assertRaisesRegex(ValueError, "project_changed_during_read"):
            await self.reader()
        self.assertEqual(self.native.write_attempts, 0)

    async def test_limited_snapshots_are_unknown_not_missing_ids(self):
        for field in ("limit_assets", "limit_clips"):
            setattr(self.native, field, True)
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "identity_read_incomplete"):
                await self.reader()
            setattr(self.native, field, False)

    async def test_mismatched_counts_are_refused(self):
        self.native.assets.append({"id": "asset-2"})
        async def changed_get():
            return await self.reader()
        original = self.native.call_tool
        async def broken(name, args):
            result = await original(name, args)
            if name == "get_assets":
                doc = json.loads(result.content[0].text)
                doc["count"] += 1
                result.content[0].text = json.dumps(doc)
            return result
        self.native.call_tool = broken
        with self.assertRaisesRegex(ValueError, "source_counts_changed"):
            await changed_get()

    async def test_malformed_and_error_native_read_cannot_authorize(self):
        for field in ("error_tool", "malformed_tool"):
            setattr(self.native, field, "get_assets")
            with self.subTest(field=field), self.assertRaises(ValueError):
                await self.reader()
            setattr(self.native, field, None)

    async def test_duplicate_or_nonstring_native_id_cannot_authorize(self):
        self.native.clips.append(dict(self.native.clips[0]))
        with self.assertRaisesRegex(ValueError, "identity_read_malformed"):
            await self.reader()
        self.native.clips = [{"id": 123}]
        with self.assertRaisesRegex(ValueError, "identity_read_malformed"):
            await self.reader()

    async def test_host_requires_read_grants_no_implicit_expansion(self):
        for missing in ("get_project", "get_timeline", "get_assets"):
            with self.subTest(missing=missing), self.assertRaisesRegex(
                    ValueError, "requires_three_granted_read_tools"):
                NativeEditorIdentityReader(self.native, {
                    k:v for k,v in GRANTS.items() if k != missing})
        self.assertEqual(self.native.calls, [])

    async def test_exact_pinned_attestation_only_and_never_model_route(self):
        source = Path("/not-a-valid-source")
        with patch("studio_next.native_editor_identity._source_matches_pinned_electron_mcp",
                   return_value=False):
            self.assertIsNone(pinned_native_editor_identity_policy(
                source, GRANTS, self.native))
        with patch("studio_next.native_editor_identity._source_matches_pinned_electron_mcp",
                   return_value=True):
            policy = pinned_native_editor_identity_policy(
                source, GRANTS, self.native)
            self.assertEqual(set(policy), {"reader", "rules"})
            self.assertIn("update_text_clip", policy["rules"])
            self.assertEqual(policy["rules"]["update_text_clip"]["/clipId"], "clips")
            self.assertNotIn("create_project", policy["rules"])
            self.assertNotIn("get_assets", policy["rules"])


class RealGatewayIdentityAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.native = NativeReadSession()
        self.budget = CapabilitySessionBudget(max_calls=24, max_writes=4)
        self.reader = NativeEditorIdentityReader(
            self.native, GRANTS,
            reserve_read=lambda: self.budget.reserve(source="editor", access="read"))
        self.rules = {
            "update_text_clip": {"/clipId": "clips"},
            "add_asset_to_timeline": {
                "/assetId": "assets", "/trackId": "tracks"},
        }
        self.gateway = CapabilityGateway(
            {"editor": (self.native, GRANTS, {}, None, {},
                        {"reader": self.reader, "rules": self.rules})},
            session_budget=self.budget)
        self.rev = (await self.gateway.refresh())["revision"]
        self.model_tools = CapabilityGatewayMcpSession(self.gateway, "editor")

    async def test_model_selected_native_edit_and_budgeted_source_read(self):
        inputs = {"clipId": "clip-1", "text": "Human-directed new title"}
        answer = await self.model_tools.call_tool("update_text_clip", inputs)
        self.assertIs(answer.is_error, False)
        self.assertEqual(self.native.write_attempts, 1)
        self.assertEqual([name for name, _ in self.native.calls], [
            "get_project", "get_timeline", "get_assets", "get_project",
            "update_text_clip"])
        b = self.gateway.host_budget_evidence()
        self.assertEqual(b["reserved_calls"], 5)
        self.assertEqual(b["reserved_writes"], 1)
        self.assertEqual(len(self.gateway.evidence()), 1)
        self.assertEqual(self.gateway.evidence()[0]["state"],
                         "host_reported_success_unverified")

    async def test_unobserved_object_is_clear_recoverable_no_dispatch(self):
        params = {"clipId": "invented-ID", "text": "Bad guess"}
        reply = await self.model_tools.call_tool("update_text_clip", params)
        self.assertTrue(reply.is_error)
        self.assertEqual(host_pre_dispatch_rejection(
            reply, "update_text_clip", params),
            "native_reference_not_in_live_inventory")
        self.assertEqual(self.native.write_attempts, 0)
        self.assertEqual(self.gateway.evidence(), [])
        self.assertEqual(self.gateway.host_budget_evidence()["reserved_writes"], 0)

    async def test_human_edit_between_model_looks_and_native_write(self):
        self.native.clips = [{"id": "clip-now-owned-by-human"}]
        result = await self.model_tools.call_tool("update_text_clip", {
            "clipId": "clip-1", "text": "Old agent editing stale clip"})
        self.assertEqual(host_pre_dispatch_rejection(result,
            "update_text_clip", {"clipId": "clip-1", "text": "Old agent editing stale clip"}),
            "native_reference_not_in_live_inventory")
        self.assertEqual(self.native.write_attempts, 0)

    async def test_valid_asset_wrong_track_fails_without_emitting_write(self):
        inputs = {"assetId": "asset-1", "trackId": "fabricated-track",
                  "previewOnly": False}
        rejected = await self.model_tools.call_tool("add_asset_to_timeline", inputs)
        self.assertEqual(host_pre_dispatch_rejection(
            rejected, "add_asset_to_timeline", inputs),
            "native_reference_not_in_live_inventory")
        self.assertEqual(self.native.write_attempts, 0)

    async def test_reader_failure_redacts_private_owner_path(self):
        self.native.fail_before_source = True
        params = {"clipId": "clip-1", "text": "New title"}
        result = await self.model_tools.call_tool("update_text_clip", params)
        self.assertEqual(host_pre_dispatch_rejection(
            result, "update_text_clip", params), "native_identity_inventory_unavailable")
        self.assertNotIn("/home/sensitive", str(result))
        self.assertEqual(self.native.write_attempts, 0)

    async def test_budget_exhaustion_does_not_authorize_native_write(self):
        budget = CapabilitySessionBudget(max_calls=3, max_writes=1)
        reader = NativeEditorIdentityReader(
            self.native, GRANTS,
            reserve_read=lambda: budget.reserve(source="editor", access="read"))
        gateway = CapabilityGateway(
            {"editor": (self.native, GRANTS, {}, None, {},
                        {"reader": reader, "rules": self.rules})},
            session_budget=budget)
        rev = (await gateway.refresh())["revision"]
        with self.assertRaisesRegex(CapabilityExecutionError, "call_budget_exhausted"):
            await gateway.invoke("editor/update_text_clip", revision=rev,
                inputs={"clipId": "clip-1", "text": "Do not edit"})
        self.assertEqual(self.native.write_attempts, 0)
        self.assertEqual(budget.snapshot()["reserved_writes"], 0)

    async def test_human_changes_during_read_does_not_mark_write_uncertain(self):
        self.native.human_edit_during_read = True
        params = {"clipId": "clip-1", "text": "Do not overwrite"}
        result = await self.model_tools.call_tool("update_text_clip", params)
        self.assertEqual(host_pre_dispatch_rejection(
            result, "update_text_clip", params), "native_identity_inventory_unavailable")
        self.assertEqual(self.native.write_attempts, 0)
        self.assertEqual(self.gateway.evidence(), [])

    async def test_other_existing_engine_grants_and_model_choices_unmodified(self):
        catalog = await self.model_tools.list_tools()
        names = {x.name for x in catalog.tools}
        self.assertTrue(set(GRANTS) <= names)
        self.assertEqual(self.native.write_attempts, 0)


if __name__ == "__main__":
    unittest.main()
