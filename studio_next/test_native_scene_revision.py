"""G1 native scene CAS interleavings, separately from installed Electron proof.

Source-bound host/Brain contracts and denial semantics only. A mocked
renderer is not an independent artistic/physical-editing acceptance.
"""
from __future__ import annotations

from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
from types import SimpleNamespace

from studio_next.body_editor_client import host_native_revision_rejection
from studio_next.capability_gateway import CapabilityGateway
from studio_next.capability_mcp_session import CapabilityGatewayMcpSession
from studio_next.native_editor_identity import pinned_native_editor_identity_policy
from studio_next.test_native_revision_fence import RendererAndDebouncedSnapshot, result

SCENE_GRANTS = {
    "get_project": "read", "get_timeline": "read", "get_assets": "read",
    "update_text_clip": "write", "update_shape_clip": "write",
    "set_clip_keyframes": "write",
}


class SourceSceneRenderer(RendererAndDebouncedSnapshot):
    def __init__(self):
        super().__init__()
        self.scene_writes = []
        self.tools.extend([
            SimpleNamespace(name=name, description="Original editable scene operation",
                input_schema={"type": "object", "properties": {
                    "clipId": {"type": "string"}, "previewOnly": {"type": "boolean"},
                    "fillColor": {"type": "string"}, "keyframes": {"type": "array"},
                }, "required": ["clipId"]})
            for name in ("update_shape_clip", "set_clip_keyframes")
        ])

    async def call_tool(self, name, args):
        if name not in ("update_shape_clip", "set_clip_keyframes"):
            return await super().call_tool(name, args)
        self.calls.append((name, dict(args)))
        preview = (args.get("previewOnly") is True if name == "update_shape_clip"
                   else args.get("previewOnly") is not False)
        if preview:
            return result({"previewOnly": True, "action": name, "plan": {},
                           "success": None})
        if self.changed_at_commit:
            self.changed_at_commit = False
            self.human_gui_edit("Human motion edit wins")
        if args.get("__zx7ExpectedRevision") != self.live_revision:
            return result("ZX7_STALE_NATIVE_REVISION", error=True)
        self.scene_writes.append((name, dict(args)))
        self.live_counter += 1
        return result({"success": True})


def source_policy(source, grants, session, *, scene):
    with patch("studio_next.native_editor_identity._source_matches_pinned_electron_mcp",
               return_value=True), patch(
          "studio_next.native_editor_identity._source_matches_pinned_native_collaboration",
               return_value=True), patch(
          "studio_next.native_editor_identity._source_matches_pinned_native_scene",
               return_value=scene):
        return pinned_native_editor_identity_policy(Path("/source-reviewed"), grants, session)


class SceneCasTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.native = SourceSceneRenderer()
        self.policy = source_policy(None, SCENE_GRANTS, self.native, scene=True)
        self.gateway = CapabilityGateway({"editor": (
            self.native, SCENE_GRANTS, {}, None, {}, self.policy)})
        await self.gateway.refresh()
        self.client = CapabilityGatewayMcpSession(self.gateway, "editor")

    async def test_expected_fences_are_only_source_proven_scope(self):
        self.assertEqual(set(self.policy["fence"]), {
            "update_text_clip", "update_shape_clip", "set_clip_keyframes"})
        previous = source_policy(None, SCENE_GRANTS, self.native, scene=False)
        self.assertEqual(set(previous["fence"]), {"update_text_clip"})

    async def test_human_changes_shape_after_host_observation_before_commit(self):
        self.native.changed_at_commit = True
        arguments = {"clipId": "clip-A", "fillColor": "#ee5511",
                     "previewOnly": False}
        denied = await self.client.call_tool("update_shape_clip", arguments)
        self.assertTrue(denied.is_error)
        self.assertEqual(host_native_revision_rejection(
            denied, "update_shape_clip", arguments),
            "native_revision_changed_at_commit")
        self.assertEqual(self.native.scene_writes, [])
        self.assertEqual(self.native.clip_text, "Human motion edit wins")
        self.assertEqual(self.gateway.evidence()[-1]["state"],
                         "native_conflict_rejected_no_write")
        self.native.publish()
        fresh = await self.client.call_tool("update_shape_clip", arguments)
        self.assertFalse(fresh.is_error)
        self.assertEqual(len(self.native.scene_writes), 1)

    async def test_keyframe_commit_after_stale_GUI_change_is_rejected(self):
        self.native.human_gui_edit("Human annotated the motion")
        args = {"clipId": "clip-A", "previewOnly": False,
                "keyframes": [{"time": 0, "value": 1}]}
        denied = await self.client.call_tool("set_clip_keyframes", args)
        self.assertTrue(denied.is_error)
        self.assertEqual(host_native_revision_rejection(
            denied, "set_clip_keyframes", args),
            "native_revision_changed_at_commit")
        self.assertEqual(self.native.scene_writes, [])
        self.native.publish()
        fresh = await self.client.call_tool("set_clip_keyframes", args)
        self.assertFalse(fresh.is_error)
        self.assertEqual(len(self.native.scene_writes), 1)

    async def test_source_native_default_keyframe_preview_does_not_mutate(self):
        preview = await self.client.call_tool("set_clip_keyframes", {
            "clipId": "clip-A", "keyframes": []})
        self.assertFalse(preview.is_error)
        self.assertEqual(self.native.scene_writes, [])
        raw_args = [a for name, a in self.native.calls
                    if name == "set_clip_keyframes"][-1]
        self.assertNotIn("__zx7ExpectedRevision", raw_args)
        preview_shape = await self.client.call_tool("update_shape_clip", {
            "clipId": "clip-A", "previewOnly": True})
        self.assertFalse(preview_shape.is_error)
        shape_previews = [arguments for name, arguments in self.native.calls
                          if name == "update_shape_clip"]
        self.assertTrue(shape_previews)
        self.assertNotIn("__zx7ExpectedRevision", shape_previews[-1])
        self.assertFalse(self.native.scene_writes)

    async def test_model_supplied_hidden_revision_never_overrides_host(self):
        args = {"clipId": "clip-A", "previewOnly": False,
                "__zx7ExpectedRevision": self.native.live_revision}
        for name in ("update_shape_clip", "set_clip_keyframes"):
            with self.subTest(name=name):
                invalid = await self.client.call_tool(name, args)
                self.assertTrue(invalid.is_error)
        self.assertFalse(self.native.scene_writes)


if __name__ == "__main__":
    import unittest
    unittest.main()
