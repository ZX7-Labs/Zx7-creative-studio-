"""Source-attested native CAS: synthetic host/renderer interleavings.

NOT a live Electron GUI, model autonomy or artistic acceptance. The installed
source-writer F09 test belongs in engines/velorn and is a separate gate.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from studio_next.body_editor_client import (
    host_native_revision_rejection, host_pre_dispatch_rejection,
)
from studio_next.capability_attempts import (
    CapabilityAttemptError, CapabilityAttemptStore)
from studio_next.capability_gateway import CapabilityGateway
from studio_next.capability_mcp_session import CapabilityGatewayMcpSession
from studio_next.native_creative_control import NativeCreativeControl
from studio_next.test_native_creative_control import ScriptedModel, decision
from studio_next.native_editor_identity import (
    NativeEditorIdentityReader, pinned_native_editor_identity_policy,
)

UUID = "12345678-1234-1234-1234-123456789abc"
GRANTS = {
    "get_project": "read",
    "get_timeline": "read",
    "get_assets": "read",
    "update_text_clip": "write",
}


def result(value, *, error=False):
    return SimpleNamespace(
        is_error=error,
        content=[SimpleNamespace(type="text",
             text=value if isinstance(value, str) else json.dumps(value))],
    )


class RendererAndDebouncedSnapshot:
    """One actual editing state, with a deliberately older published inventory."""

    def __init__(self):
        self.calls = []
        self.live_counter = 1
        self.published_counter = 1
        self.human_text = "Original approved human title"
        self.clip_text = self.human_text
        self.writes = 0
        self.changed_at_commit = False
        self.force_unknown_error = False
        self.available = True
        self.tools = [
            SimpleNamespace(name=name, description=f"Native {name}",
                input_schema=({
                    "type":"object", "properties":{"clipId":{"type":"string"},
                       "text":{"type":"string"},"previewOnly":{"type":"boolean"}},
                    "required":["clipId","text"],
                } if name == "update_text_clip"
                   else {"type":"object", "properties":{
                       "includeClips":{"type":"boolean"},"limit":{"type":"integer"}}}))
            for name in GRANTS
        ]

    @property
    def live_revision(self):
        return f"{UUID}:{self.live_counter}"

    @property
    def published_revision(self):
        return f"{UUID}:{self.published_counter}"

    def human_gui_edit(self, text):
        self.live_counter += 1
        self.human_text = text
        self.clip_text = text
        # Deliberately DO NOT publish snapshot. Models can see stale data.

    def publish(self):
        self.published_counter = self.live_counter

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools, nextCursor=None)

    async def call_tool(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "get_project":
            return result({
                "mcp":{"hasProject":True,"lastSnapshotAt":"source-published"},
                "project":{"name":"private-video","path":"/private/not-exposed",
                           "currentTimelineId":"timeline-A"},
                "currentTimeline":{"id":"timeline-A","trackCount":1,"clipCount":1},
                "assetCount":0, "generatedAt":"source-published",
                "zx7NativeRevision":self.published_revision if self.available else None,
            })
        if name == "get_timeline":
            return result({
                "id":"timeline-A",
                "tracks":[{"id":"track-A"}],
                "clips":[{"id":"clip-A"}],
                "clipLimitApplied":False,
            })
        if name == "get_assets":
            return result({"assets":[],"count":0,"limitApplied":False})
        if name == "update_text_clip":
            if self.changed_at_commit:
                self.changed_at_commit = False
                self.human_gui_edit("Human edited at actual native commit boundary")
            if self.force_unknown_error:
                return result("UNKNOWN_REMOTE_ERROR", error=True)
            if args.get("__zx7ExpectedRevision") != self.live_revision:
                return result("ZX7_STALE_NATIVE_REVISION", error=True)
            self.writes += 1
            self.clip_text = args["text"]
            self.live_counter += 1
            return result({"success":True,"applied":True})
        raise AssertionError("Unexpected source call")


class NativeLiveRevisionAdmissionTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.renderer = RendererAndDebouncedSnapshot()
        self.reader = NativeEditorIdentityReader(
            self.renderer, GRANTS, require_live_revision=True)
        self.policy = {
            "reader":self.reader,
            "rules":{"update_text_clip":{"/clipId":"clips"}},
            "fence":{"update_text_clip":{
                "inventory_key":"__zx7_live_revision",
                "argument_key":"__zx7ExpectedRevision",
                "rejected_code":"ZX7_STALE_NATIVE_REVISION"}},
        }
        self.gateway = CapabilityGateway({"editor":(
            self.renderer, GRANTS, {}, None, {}, self.policy)})
        self.rev = (await self.gateway.refresh())["revision"]
        self.host_session = CapabilityGatewayMcpSession(self.gateway, "editor")

    async def submit(self, text):
        return await self.host_session.call_tool(
            "update_text_clip", {"clipId":"clip-A","text":text})

    async def test_human_gui_edit_during_debounce_is_not_lost_and_model_can_replan(self):
        self.renderer.human_gui_edit("Manual human edit")
        chosen={"clipId":"clip-A","text":"Stale planned AI title"}
        stale=await self.submit(chosen["text"])
        self.assertTrue(stale.is_error)
        self.assertEqual(host_native_revision_rejection(
            stale, "update_text_clip", chosen), "native_revision_changed_at_commit")
        self.assertIsNone(host_pre_dispatch_rejection(
            stale, "update_text_clip", chosen))
        self.assertEqual(self.renderer.writes, 0)
        self.assertEqual(self.renderer.clip_text, "Manual human edit")
        self.assertEqual(self.gateway.evidence()[0]["state"],
                         "native_conflict_rejected_no_write")
        # After the actual editor publishes its new source snapshot, a
        # NEW model-chosen revision can preserve the manual intent.
        self.renderer.publish()
        fresh=await self.submit("Manual human edit / AI-reviewed lower third")
        self.assertFalse(fresh.is_error)
        self.assertEqual(self.renderer.writes, 1)
        self.assertEqual(self.renderer.clip_text,
                         "Manual human edit / AI-reviewed lower third")
        self.assertEqual(self.gateway.evidence()[1]["state"],
                         "host_reported_success_unverified")

    async def test_commit_boundary_race_after_four_source_reads_is_rejected(self):
        self.renderer.changed_at_commit=True
        stale=await self.submit("stale")
        self.assertTrue(stale.is_error)
        self.assertEqual(self.renderer.writes, 0)
        self.assertEqual(self.renderer.clip_text,
                         "Human edited at actual native commit boundary")

    async def test_missing_live_source_revision_is_no_dispatch(self):
        self.renderer.available=False
        params={"clipId":"clip-A","text":"No live source"}
        denied=await self.host_session.call_tool("update_text_clip",params)
        self.assertTrue(denied.is_error)
        self.assertEqual(host_pre_dispatch_rejection(
            denied, "update_text_clip", params),
                         "native_identity_live_revision_unavailable")
        self.assertFalse(self.renderer.writes)
        self.assertFalse(any(n=="update_text_clip" for n,_ in self.renderer.calls))

    async def test_model_cannot_supply_or_overwrite_host_revision(self):
        payload={"clipId":"clip-A","text":"Attempted token spoof",
                 "__zx7ExpectedRevision":self.renderer.live_revision}
        with self.assertRaisesRegex(ValueError,"Invalid native parameters"):
            await self.host_session.call_tool("update_text_clip",payload)
        self.assertEqual(self.renderer.writes,0)

    async def test_unknown_native_error_does_not_become_safe_cas_refusal(self):
        self.renderer.force_unknown_error=True
        value=await self.submit("unknown")
        self.assertTrue(value.is_error)
        self.assertIsNone(host_native_revision_rejection(
            value, "update_text_clip", {"clipId":"clip-A","text":"unknown"}))
        self.assertEqual(self.gateway.evidence()[0]["state"],
                         "write_uncertain_reconciliation_required")

    async def test_tampered_trusted_receipt_is_not_accepted_as_writer_proof(self):
        old=await self.submit("valid")
        self.assertFalse(old.is_error)
        self.assertIsNone(host_native_revision_rejection(
            old, "update_text_clip", {"clipId":"clip-A","text":"valid"}))

    async def test_creative_controller_requires_fresh_model_decision_after_writer_refusal(self):
        self.renderer.human_gui_edit("Human changes title before AI write")
        model=ScriptedModel([
            decision("invoke",tool="update_text_clip",
                     inputs={"clipId":"clip-A","text":"old stale plan"}),
            decision("finish",summary="Refused and must inspect fresh editor state"),
        ])
        outcome=await NativeCreativeControl(
            self.host_session, model,max_turns=2,
            host_tool_access=GRANTS,host_pre_dispatch_rejections=True,
        ).run("Do not replace human-authored titles")
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertTrue(any(e["kind"] == "native_writer_rejected_stale_revision"
                            and e["native_write_applied"] is False
                            and e["no_native_dispatch"] is False
                            for e in outcome["events"]))
        self.assertEqual(self.renderer.writes,0)
        self.assertEqual(self.renderer.clip_text,"Human changes title before AI write")
        self.assertEqual(len(model.observed),2)
        self.assertEqual(model.observed[-1]["last_rejected_native_action_feedback"][
                             "validation_keyword"],"native_revision_conflict")

    async def test_durable_native_conflict_survives_restart_without_false_replay(self):
        self.renderer.human_gui_edit("Human original must survive failed AI edit")
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "private" / "native-attempts.sqlite3"
            store = CapabilityAttemptStore(journal)
            gateway = CapabilityGateway({"editor": (
                self.renderer, GRANTS, {}, None, {}, self.policy)},
                attempt_store=store)
            await gateway.refresh()
            allocator = lambda operation: "host-cas-first"
            admitted = CapabilityGatewayMcpSession(
                gateway, "editor", host_request_id_allocator=allocator)
            original = {"clipId": "clip-A", "text": "stale AI title"}
            reply = await admitted.call_tool("update_text_clip", original)
            self.assertTrue(reply.is_error)
            self.assertEqual(host_native_revision_rejection(
                reply, "update_text_clip", original),
                "native_revision_changed_at_commit")
            self.assertEqual(self.renderer.writes, 0)
            self.assertEqual(store.inspect("host-cas-first")["state"],
                             "native_conflict_rejected_no_write")
            reopened = CapabilityAttemptStore(journal)
            self.assertEqual(reopened.unverified_attempts()["attempts"], [])
            # The old request identity remains exhausted forever, even when
            # the known-safe native failure would otherwise permit replanning.
            self.renderer.publish()
            with self.assertRaisesRegex(
                    CapabilityAttemptError, "already admitted"):
                await admitted.call_tool("update_text_clip", original)
            self.assertEqual(self.renderer.writes, 0)
            fresh = CapabilityGatewayMcpSession(
                gateway, "editor",
                host_request_id_allocator=lambda _: "host-cas-second")
            corrected = await fresh.call_tool("update_text_clip", {
                "clipId": "clip-A",
                "text": "Human original must survive failed AI edit / revised"})
            self.assertFalse(corrected.is_error)
            self.assertEqual(self.renderer.writes, 1)
            self.assertEqual(reopened.inspect("host-cas-second")["state"],
                             "host_reported_success_unverified")
            self.assertEqual(
                reopened.unverified_attempts()["attempts"][0]["request_id"],
                "host-cas-second")

    async def test_original_upstream_without_verified_overlay_does_not_claim_fence(self):
        # Backward compatibility. A source filename alone cannot imply
        # source-native atomic collaboration admission.
        with patch("studio_next.native_editor_identity._source_matches_pinned_electron_mcp",
                   return_value=True), patch(
               "studio_next.native_editor_identity._source_matches_pinned_native_collaboration",
                   return_value=False):
            policy=pinned_native_editor_identity_policy(
                __import__("pathlib").Path("/fake"),GRANTS,self.renderer)
        self.assertEqual(set(policy), {"reader","rules"})
        self.assertFalse(getattr(policy["reader"],"_require_live_revision"))


if __name__ == "__main__":
    import unittest
    unittest.main()
