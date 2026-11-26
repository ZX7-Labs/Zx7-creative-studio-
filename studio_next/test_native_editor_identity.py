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
        self.snapshot_heartbeat_between_reads = False
        self.provide_native_revision = False
        self.native_revision = "a" * 40
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
            if sum(c[0] == "get_project" for c in self.calls) == 2:
                if self.human_edit_during_read:
                    self.revision = "revision-human"
                    self.native_revision = "b" * 40
                elif self.snapshot_heartbeat_between_reads:
                    self.revision = "snapshot-heartbeat-without-native-edit"
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
        if name == "get_project" and self.provide_native_revision:
            data["zx7NativeRevision"] = self.native_revision
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

    async def test_source_fenced_native_identity_ignores_heartbeat_not_a_live_edit(self):
        """Pinned upstream snapshot generatedAt refreshes on a heartbeat.
        Source-attested zx7NativeRevision remains stable without a mutation.
        Never turn the volatile presentation stamp into a false edit.
        """
        self.native.provide_native_revision = True
        self.native.snapshot_heartbeat_between_reads = True
        trusted = NativeEditorIdentityReader(
            self.native, GRANTS, require_live_revision=True)
        observed = await trusted()
        self.assertEqual(observed["__zx7_live_revision"], "a" * 40)
        self.assertEqual([name for name, _ in self.native.calls],
                         ["get_project", "get_timeline", "get_assets", "get_project"])
        self.assertEqual(self.native.write_attempts, 0)

        # Legacy / unfenced sources have no same-commit CAS: reject drift.
        legacy = NativeReadSession()
        legacy.snapshot_heartbeat_between_reads = True
        with self.assertRaisesRegex(ValueError, "project_changed_during_read"):
            await NativeEditorIdentityReader(legacy, GRANTS)()
        self.assertEqual(legacy.write_attempts, 0)

    async def test_source_fenced_concurrent_native_mutation_and_missing_token_fail_closed(self):
        self.native.provide_native_revision = True
        self.native.human_edit_during_read = True
        fenced = NativeEditorIdentityReader(
            self.native, GRANTS, require_live_revision=True)
        with self.assertRaisesRegex(ValueError, "project_changed_during_read"):
            await fenced()
        self.assertEqual(self.native.write_attempts, 0)

        missing = NativeReadSession()
        missing.snapshot_heartbeat_between_reads = True
        with self.assertRaisesRegex(ValueError, "native_identity_live_revision_unavailable"):
            await NativeEditorIdentityReader(
                missing, GRANTS, require_live_revision=True)()
        self.assertEqual(missing.write_attempts, 0)

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

    async def test_partial_read_grants_never_claim_native_reference_proof(self):
        source = Path("/not-a-valid-source")
        for missing in ("get_project", "get_timeline", "get_assets"):
            with self.subTest(missing=missing), patch(
                "studio_next.native_editor_identity._source_matches_pinned_electron_mcp",
                return_value=True):
                grants = {k: v for k, v in GRANTS.items() if k != missing}
                self.assertIsNone(pinned_native_editor_identity_policy(
                    source, grants, self.native))
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

    async def test_source_attested_explicit_clip_track_reference_coverage(self):
        """Pinned Electron and renderer accept these explicit existing IDs.

        Never infer an artistic selector from an arbitrary field name. In
        particular a dip pair can use either array alias and either ID alias.
        """
        from studio_next.capability_reference_guard import (
            CapabilityReferenceError, compile_reference_rules,
            validate_live_references,
        )
        expected = {
            "update_caption_cues": {
                "/clipId": "clips"
            },
            "set_clip_label_color": {
                "/clipIds/*": "clips"
            },
            "select_clips": {
                "/clipId": "clips",
                "/clipIds/*": "clips",
                "/trackId": "tracks"
            },
            "add_solid_color": {
                "/trackId": "tracks"
            },
            "add_glsl_effect": {
                "/clipId": "clips"
            },
            "update_glsl_effect": {
                "/clipId": "clips"
            },
            "remove_glsl_effect": {
                "/clipId": "clips"
            },
            "add_dip_to_black": {
                "/clipIds/*": "clips",
                "/trackId": "tracks",
                "/clipPairs/*/outClipId": "clips",
                "/clipPairs/*/inClipId": "clips",
                "/clipPairs/*/clipAId": "clips",
                "/clipPairs/*/clipBId": "clips",
                "/clipPairs/*/fromClipId": "clips",
                "/clipPairs/*/toClipId": "clips",
                "/clipPairs/*/firstClipId": "clips",
                "/clipPairs/*/secondClipId": "clips",
                "/pairs/*/outClipId": "clips",
                "/pairs/*/inClipId": "clips",
                "/pairs/*/clipAId": "clips",
                "/pairs/*/clipBId": "clips",
                "/pairs/*/fromClipId": "clips",
                "/pairs/*/toClipId": "clips",
                "/pairs/*/firstClipId": "clips",
                "/pairs/*/secondClipId": "clips"
            },
            "set_clip_style": {
                "/clipId": "clips",
                "/clipIds/*": "clips",
                "/trackId": "tracks"
            }
        }
        grants = {**GRANTS, **{name: "write" for name in expected}}
        with patch("studio_next.native_editor_identity._source_matches_pinned_electron_mcp",
                   return_value=True):
            policy = pinned_native_editor_identity_policy(
                Path("/not-a-valid-source"), grants, self.native)
        inventory = await self.reader()
        for name, rules in expected.items():
            with self.subTest(tool=name):
                self.assertEqual(policy["rules"].get(name), rules)
                compiled = compile_reference_rules(rules)
                self.assertEqual(validate_live_references(
                    {}, compiled, inventory)["host_reference_checks_passed"], 0)
                for path, kind in rules.items():
                    def arguments(value):
                        for part in reversed(path.lstrip("/").split("/")):
                            value = [value] if part == "*" else {part: value}
                        return value
                    valid = inventory[kind]["ids"][0]
                    self.assertEqual(validate_live_references(
                        arguments(valid), compiled, inventory)[
                            "host_reference_checks_passed"], 1)
                    with self.assertRaisesRegex(
                            CapabilityReferenceError,
                            "native_reference_not_in_live_inventory"):
                        validate_live_references(
                            arguments("invented-id"), compiled, inventory)
        # These rules never add a grant or grant native commit/CAS semantics.
        with patch("studio_next.native_editor_identity._source_matches_pinned_electron_mcp",
                   return_value=True):
            limited = pinned_native_editor_identity_policy(
                Path("/not-a-valid-source"), GRANTS, self.native)
        self.assertNotIn("set_clip_label_color", limited["rules"])


class ArchivedLabelReferenceAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_label_batch_refused_before_native_write(self):
        """Native label resolution can otherwise silently omit a missing ID."""
        class LabelSession(NativeReadSession):
            def __init__(self):
                super().__init__()
                self.tools.append(SimpleNamespace(
                    name="set_clip_label_color", description="Native label edit",
                    input_schema={"type": "object", "properties": {
                        "clipIds": {"type": "array", "items": {"type": "string"}},
                        "color": {"type": "string"},
                        "filter": {"type": "string"},
                        "previewOnly": {"type": "boolean"}}}))

            async def call_tool(self, name, args):
                if name == "set_clip_label_color":
                    self.calls.append((name, args))
                    self.write_attempts += 1
                    return SimpleNamespace(is_error=False, content=[
                        SimpleNamespace(type="text", text='{"applied":true}')])
                return await super().call_tool(name, args)

        native = LabelSession()
        grants = {"get_project": "read", "get_timeline": "read",
                  "get_assets": "read", "set_clip_label_color": "write"}
        with patch("studio_next.native_editor_identity._source_matches_pinned_electron_mcp",
                   return_value=True):
            policy = pinned_native_editor_identity_policy(
                Path("/not-a-valid-source"), grants, native)
        binding = ((native, grants, {}, None, {}, policy) if policy is not None
                   else (native, grants))
        gateway = CapabilityGateway({"editor": binding})
        await gateway.refresh()
        session = CapabilityGatewayMcpSession(gateway, "editor")
        mixed = {"clipIds": ["clip-1", "invented-clip"],
                 "color": "#ff0000", "previewOnly": False}
        denied = await session.call_tool("set_clip_label_color", mixed)
        self.assertEqual(host_pre_dispatch_rejection(
            denied, "set_clip_label_color", mixed),
            "native_reference_not_in_live_inventory")
        self.assertEqual(native.write_attempts, 0)
        self.assertEqual(gateway.evidence(), [])
        good = {"clipIds": ["clip-1"], "color": "#ff0000",
                "previewOnly": False}
        accepted = await session.call_tool("set_clip_label_color", good)
        self.assertIs(accepted.is_error, False)
        self.assertEqual(native.write_attempts, 1)
        # A legitimate native filter does not require model-invented IDs.
        filtered = await session.call_tool("set_clip_label_color", {
            "filter": "enabled", "color": "#00ff00", "previewOnly": False})
        self.assertIs(filtered.is_error, False)
        self.assertEqual(native.write_attempts, 2)


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
        chosen = {"clipId": "clip-1", "text": "Do not edit"}
        reply = await CapabilityGatewayMcpSession(
            gateway, "editor").call_tool("update_text_clip", chosen)
        self.assertEqual(host_pre_dispatch_rejection(
            reply, "update_text_clip", chosen),
            "native_identity_read_budget_exhausted")
        self.assertEqual(self.native.write_attempts, 0)
        self.assertEqual(gateway.evidence(), [])
        self.assertEqual(budget.snapshot()["reserved_calls"], 3)
        self.assertEqual(budget.snapshot()["reserved_writes"], 0)

    async def test_human_changes_during_read_does_not_mark_write_uncertain(self):
        self.native.human_edit_during_read = True
        params = {"clipId": "clip-1", "text": "Do not overwrite"}
        result = await self.model_tools.call_tool("update_text_clip", params)
        # A human changed the live native snapshot between source reads.
        # This specific, host-verified no-write reason is now preserved instead
        # of collapsing it into an opaque inventory error.
        self.assertEqual(host_pre_dispatch_rejection(
            result, "update_text_clip", params),
            "native_identity_project_changed_during_read")
        self.assertEqual(self.native.write_attempts, 0)
        self.assertEqual(self.gateway.evidence(), [])
        self.assertEqual(self.gateway.host_budget_evidence()["reserved_writes"], 0)

    async def test_other_existing_engine_grants_and_model_choices_unmodified(self):
        catalog = await self.model_tools.list_tools()
        names = {x.name for x in catalog.tools}
        self.assertTrue(set(GRANTS) <= names)
        self.assertEqual(self.native.write_attempts, 0)


if __name__ == "__main__":
    unittest.main()
