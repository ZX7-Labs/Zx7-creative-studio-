"""G1 editorial native-CAS threat cases, distinct from installed Electron proof.

A deterministic fake renderer tests host/native protocol interleavings. Real
Velorn X11+MCP, decoded video/audio and saved-project evidence are required
separately before the source candidate is trusted.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
from pathlib import Path

from studio_next.body_editor_client import (
    host_pre_dispatch_rejection, host_native_revision_rejection)
from studio_next.capability_gateway import CapabilityGateway
from studio_next.capability_mcp_session import CapabilityGatewayMcpSession
from studio_next.native_editor_identity import pinned_native_editor_identity_policy
from studio_next.test_native_scene_revision import SourceSceneRenderer, result

EDITORIAL = (
    "move_clips", "trim_clips", "delete_clips",
    "add_asset_to_timeline", "add_assets_to_timeline",
    "set_clip_audio", "set_clip_speed", "update_track",
    "add_transition", "set_clip_style",
)
GRANTS = {
    "get_project": "read", "get_timeline": "read", "get_assets": "read",
    "update_text_clip": "write", "update_shape_clip": "write",
    "set_clip_keyframes": "write",
    **{name: "write" for name in EDITORIAL},
}


class EditorialRenderer(SourceSceneRenderer):
    def __init__(self):
        super().__init__()
        self.editorial_commits = []
        self.tools.extend(SimpleNamespace(
            name=name, description="Pinned native editorial operation",
            input_schema={"type": "object", "properties": {
                "previewOnly": {"type": "boolean"},
                "clipId": {"type": "string"},
                "trackId": {"type": "string"},
                "clipIds": {"type": "array", "items": {"type": "string"}},
                "assetId": {"type": "string"},
            }}) for name in EDITORIAL)

    async def call_tool(self, name, args):
        if name not in EDITORIAL:
            return await super().call_tool(name, args)
        self.calls.append((name, dict(args)))
        if args.get("previewOnly") is not False:
            return result({"previewOnly": True, "action": name})
        if self.changed_at_commit:
            self.changed_at_commit = False
            self.human_gui_edit("Native GUI update raced at source commit")
        if args.get("__zx7ExpectedRevision") != self.live_revision:
            return result("ZX7_STALE_NATIVE_REVISION", error=True)
        self.editorial_commits.append((name, dict(args)))
        self.live_counter += 1
        return result({"success": True, "native_editor_committed": True})


def policy(renderer, *, editorial=True):
    prefix = "studio_next.native_editor_identity."
    with (
        patch(prefix + "_source_matches_pinned_electron_mcp",
              return_value=True),
        patch(prefix + "_source_matches_pinned_native_collaboration",
              return_value=True),
        patch(prefix + "_source_matches_pinned_native_scene",
              return_value=True),
        patch(prefix + "_source_matches_pinned_native_editorial",
              return_value=editorial),
    ):
        return pinned_native_editor_identity_policy(
            Path("/source-pinned"), GRANTS, renderer)


class NativeEditorialCASProtocolTests(IsolatedAsyncioTestCase):
    async def fresh(self, *, editorial=True):
        renderer = EditorialRenderer()
        gateway = CapabilityGateway({
            "editor": (renderer, GRANTS, {}, None, {},
                       policy(renderer, editorial=editorial))})
        await gateway.refresh()
        view = CapabilityGatewayMcpSession(
            gateway, "editor", require_model_native_observation=True)
        return renderer, gateway, view

    async def test_exact_ten_new_source_operations_and_older_source_compatibility(self):
        native, _, _ = await self.fresh()
        self.assertEqual(set(policy(native)["fence"]),
                         set(EDITORIAL) | {
                             "update_text_clip", "update_shape_clip",
                             "set_clip_keyframes"})
        self.assertEqual(set(policy(native, editorial=False)["fence"]),
                         {"update_text_clip", "update_shape_clip",
                          "set_clip_keyframes"})

    async def test_no_observation_rejects_every_mutating_editorial_action(self):
        for action in EDITORIAL:
            with self.subTest(tool=action):
                native, _, brain = await self.fresh()
                args = {"previewOnly": False}
                denied = await brain.call_tool(action, args)
                self.assertTrue(denied.is_error)
                self.assertEqual(host_pre_dispatch_rejection(
                    denied, action, args),
                    "native_identity_model_observation_required")
                self.assertFalse(native.editorial_commits)
                self.assertFalse(any(n == action for n, _ in native.calls))

    async def test_gui_edit_after_model_plan_requires_fresh_decision_for_all(self):
        for action in EDITORIAL:
            with self.subTest(tool=action):
                native, _, brain = await self.fresh()
                await brain.call_tool("get_project", {})
                native.human_gui_edit("Human intervened between model and BODY")
                native.publish()
                args = {"previewOnly": False}
                refused = await brain.call_tool(action, args)
                self.assertEqual(host_pre_dispatch_rejection(
                    refused, action, args),
                    "native_identity_model_observation_stale")
                self.assertFalse(native.editorial_commits)
                self.assertFalse(any(n == action for n, _ in native.calls))
                repeat = await brain.call_tool(action, args)
                self.assertEqual(host_pre_dispatch_rejection(
                    repeat, action, args),
                    "native_identity_model_observation_required")
                await brain.call_tool("get_project", {})
                applied = await brain.call_tool(action, args)
                self.assertFalse(applied.is_error)
                self.assertEqual(len(native.editorial_commits), 1)
                self.assertEqual(native.editorial_commits[0][0], action)
                self.assertNotIn("__zx7ExpectedRevision", args)

    async def test_unpublished_gui_event_cannot_cross_native_editor_commit(self):
        for action in EDITORIAL:
            with self.subTest(tool=action):
                native, gateway, brain = await self.fresh()
                await brain.call_tool("get_project", {})
                native.human_gui_edit("Unpublished editor mutation")
                proposed = {"previewOnly": False}
                refused = await brain.call_tool(action, proposed)
                self.assertEqual(host_native_revision_rejection(
                    refused, action, proposed),
                    "native_revision_changed_at_commit")
                self.assertFalse(native.editorial_commits)
                self.assertEqual(gateway.evidence()[-1]["state"],
                                 "native_conflict_rejected_no_write")

    async def test_native_previews_are_not_writes_or_commit_epoch_consumers(self):
        for action in EDITORIAL:
            with self.subTest(tool=action):
                native, _, brain = await self.fresh()
                await brain.call_tool("get_project", {})
                for preview in ({}, {"previewOnly": True}):
                    got = await brain.call_tool(action, preview)
                    self.assertFalse(got.is_error)
                self.assertFalse(native.editorial_commits)
                self.assertEqual([args for name, args in native.calls
                                  if name == action], [{}, {"previewOnly": True}])
                applied = await brain.call_tool(action, {"previewOnly": False})
                self.assertFalse(applied.is_error)
                self.assertEqual(len(native.editorial_commits), 1)

    async def test_unknown_native_failure_cannot_masquerade_as_atomic_conflict(self):
        native, gateway, brain = await self.fresh()
        await brain.call_tool("get_project", {})
        native.changed_at_commit = False
        original = native.call_tool

        async def broken(name, args):
            if name == "move_clips":
                return result("UNTRUSTED_REMOTE_ERROR", error=True)
            return await original(name, args)

        native.call_tool = broken
        params = {"previewOnly": False}
        failed = await brain.call_tool("move_clips", params)
        self.assertTrue(failed.is_error)
        self.assertIsNone(host_native_revision_rejection(
            failed, "move_clips", params))
        self.assertEqual(gateway.evidence()[-1]["state"],
                         "write_uncertain_reconciliation_required")
