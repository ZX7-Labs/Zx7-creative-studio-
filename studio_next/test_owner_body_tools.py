"""Contract-first tests for the owner Brain's source-verified installed BODY tools.

No provider call, artist prompt, fake Blender render or media egress.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from studio_next.native_editor_session import attest_owner_body_source
from studio_next.body_capability_adapter import InstalledBodyAdapter
from studio_next.capability_gateway import CapabilityExecutionError, CapabilityGateway
from studio_next.capability_mcp_session import CombinedCapabilityMcpSession
from studio_next.capability_session_budget import CapabilitySessionBudget


class FakeEditor:
    """Only an independent pinned native-style read, never an editing success."""
    async def list_tools(self):
        return SimpleNamespace(nextCursor=None, tools=[
            SimpleNamespace(name="get_project", description="Read existing native project.",
                            input_schema={"type": "object", "properties": {},
                                          "additionalProperties": False})])

    async def call_tool(self, name, arguments):
        if name != "get_project" or arguments:
            raise AssertionError("Fake editor must not become a general write backend")
        return SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text='{"native":"source-read-only"}')])


def fixture(root):
    (root / "projects").mkdir()
    (root / "staging").mkdir()
    (root / "outputs").mkdir()
    (root / "staging" / "session-1").mkdir()
    (root / "outputs" / "session-1").mkdir()
    return {
        "projects_root": str(root / "projects"),
        "staging_root": str(root / "staging" / "session-1"),
        "outputs_root": str(root / "outputs" / "session-1"),
    }


class OwnerInstalledBodyTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_installed_catalog_is_optional_host_source_not_model_grants(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = fixture(root)
            self.assertIsNone(attest_owner_body_source(
                None, configuration=config, provider="local"))
            adapter = attest_owner_body_source(
                root, configuration=config, provider="local",
                allowed_access=("read",))
            self.assertIsInstance(adapter, InstalledBodyAdapter)
            actual = await adapter.list_tools()
            names = {t.name for t in actual.tools}
            self.assertIn("body.timecode_format", names)
            self.assertIn("body.timecode_parse", names)
            self.assertNotIn("body.asset_vault", names)
            self.assertEqual(set(adapter.trusted_grants()), names)
            self.assertTrue(all(v == "read" for v in adapter.trusted_grants().values()))

    async def test_untrusted_root_and_provider_cannot_attach_private_body(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root = Path(td)
            config = fixture(root)
            cases = [
                (Path(outside), config, "local"),
                (root, {**config, "projects_root": outside}, "local"),
                (root, {**config, "staging_root": outside}, "local"),
                (root, {**config, "outputs_root": outside}, "local"),
                (root, config, "nvidia"),
            ]
            for source, grants, provider in cases:
                with self.subTest(source=source, provider=provider), self.assertRaises(ValueError):
                    attest_owner_body_source(
                        source, configuration=grants, provider=provider)
            link = Path(outside) / "redirect"
            link.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                attest_owner_body_source(
                    link, configuration=config, provider="local")

    async def test_same_real_gateway_executes_editor_and_installed_body_under_one_budget(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = fixture(root)
            adapter = attest_owner_body_source(
                root, configuration=config, provider="local",
                allowed_access=("read",))
            budget = CapabilitySessionBudget(max_calls=2, max_writes=0)
            gateway = CapabilityGateway({
                "editor": (FakeEditor(), {"get_project": "read"}),
                "zx7": (adapter, adapter.trusted_grants),
            }, session_budget=budget)
            await gateway.refresh()
            model_view = CombinedCapabilityMcpSession(gateway, "editor", "zx7")
            names = {t.name for t in (await model_view.list_tools()).tools}
            self.assertIn("get_project", names)
            self.assertIn("body.timecode_format", names)
            editor = await model_view.call_tool("get_project", {})
            self.assertIn("source-read-only", editor.content[0].text)
            body = await model_view.call_tool("body.timecode_format", {
                "frame_index": 48, "numerator": 24, "denominator": 1,
                "drop_frame": False})
            self.assertFalse(body.is_error)
            self.assertIn("00:00:02:00", body.content[0].text)
            with self.assertRaisesRegex(CapabilityExecutionError,
                                        "host_session_call_budget_exhausted"):
                await model_view.call_tool("body.timecode_format", {
                    "frame_index": 24, "numerator": 24,
                    "denominator": 1, "drop_frame": False})
            self.assertEqual(gateway.host_budget_evidence()["reserved_calls"], 2)
            self.assertEqual(gateway.host_budget_evidence()["reserved_writes"], 0)

    async def test_same_gateway_creates_and_revises_real_editable_visual_graph_media(self):
        """Actual BODY pixel engine, native editor source and shared admission."""
        import hashlib
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = fixture(root)
            adapter = attest_owner_body_source(
                root, configuration=config, provider="local")
            budget = CapabilitySessionBudget(max_calls=4, max_writes=2)
            gateway = CapabilityGateway({
                "editor": (FakeEditor(), {"get_project": "read"}),
                "zx7": (adapter, adapter.trusted_grants),
            }, session_budget=budget)
            await gateway.refresh()
            view = CombinedCapabilityMcpSession(gateway, "editor", "zx7")
            names = {t.name for t in (await view.list_tools()).tools}
            self.assertIn("body.visual_graph", names,
                          "Installed actual FFmpeg/NumPy/Pillow visual engine must be present")
            native = await view.call_tool("get_project", {})
            self.assertIn("source-read-only", native.content[0].text)

            def authored_graph(red):
                return {
                    "version": "zx7-visual-graph/1",
                    "canvas": {"width": 32, "height": 24,
                               "frame_rate": {"numerator": 24, "denominator": 1},
                               "frames": 2, "working_space": "linear_srgb"},
                    "nodes": [{
                        "id": "paint", "op": "expression", "inputs": {},
                        "params": {
                            "channels": {"r": red, "g": "v", "b": "0", "a": "1"},
                            "uniforms": {},
                        },
                    }],
                    "output": "paint",
                    "render": {"first_frame": 0, "frame_count": 1,
                               "format": "png", "rgb_range": "clip_to_sdr",
                               "audio": "separate_tracks"},
                }

            originals = {}
            for name, red in (("original", "u"), ("revision", "1")):
                plan = root / (name + ".json")
                target = root / (name + ".png")
                plan.write_text(json.dumps(authored_graph(red)), encoding="utf-8")
                plan_sha = hashlib.sha256(plan.read_bytes()).hexdigest()
                result = await view.call_tool("body.visual_graph", {
                    "plan": plan.name, "out": target.name})
                self.assertFalse(result.is_error)
                self.assertTrue(target.is_file() and not target.is_symlink())
                with Image.open(target) as image:
                    self.assertEqual(image.size, (32, 24))
                    self.assertEqual(image.mode, "RGBA")
                    pixels = list(image.getdata())
                self.assertTrue(any(p[3] > 0 for p in pixels))
                self.assertEqual(hashlib.sha256(plan.read_bytes()).hexdigest(),
                                 plan_sha, "Real native editable source graph must survive")
                originals[name] = (hashlib.sha256(target.read_bytes()).hexdigest(),
                                   pixels[0][0])
            self.assertNotEqual(originals["original"][0],
                                originals["revision"][0],
                                "A real authored graph change must alter physical pixels")
            self.assertNotEqual(originals["original"][1],
                                originals["revision"][1])
            self.assertEqual(
                hashlib.sha256((root / "original.png").read_bytes()).hexdigest(),
                originals["original"][0], "Revision cannot overwrite original art")
            with self.assertRaisesRegex(CapabilityExecutionError,
                                        "host_session_write_budget_exhausted"):
                await view.call_tool("body.visual_graph", {
                    "plan": "original.json",
                    "out": "third.png"})
            self.assertFalse((root / "third.png").exists())
            self.assertEqual(gateway.host_budget_evidence()["reserved_writes"], 2)

    async def test_disabled_body_source_does_not_create_vault_or_expand_grants(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = fixture(root)
            self.assertIsNone(attest_owner_body_source(
                None, configuration=config, provider="local"))
            self.assertFalse((root / "vault").exists())
            self.assertFalse((root / ".zx7-host-private").exists())


if __name__ == "__main__":
    unittest.main()
