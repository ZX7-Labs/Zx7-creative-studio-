"""Physical trusted BODY catalog through universal small/large brain interface."""
import tempfile
import shutil
from pathlib import Path
import unittest

from studio_next.body_capability_adapter import (
    InstalledBodyAdapter, connect_installed_zx7_body)
from studio_next.capability_gateway import CapabilityExecutionError
from studio_next.capability_attempts import CapabilityAttemptError, CapabilityAttemptStore
from studio_next.capability_fabric import CapabilityContractError
from studio_next.capability_session_budget import CapabilitySessionBudget


class InstalledBodyGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_installed_timecode_is_found_and_executed_without_manual(self):
        with tempfile.TemporaryDirectory() as root:
            gateway = await connect_installed_zx7_body(root, allowed_access=("read", "write"))
            state = gateway._current().overview()
            self.assertGreater(state["operation_count"], 0)
            options = gateway.search("timecode format", limit=8)["matches"]
            self.assertTrue(options)
            target = next(x for x in options if x["id"].endswith("body.timecode_format"))
            contract = gateway.describe(target["id"], revision=state["revision"])
            self.assertEqual(contract["input_schema"]["properties"]["frame_index"]["type"],
                             "integer")
            arguments = {"frame_index": 48, "numerator": 24, "denominator": 1,
                         "drop_frame": False}
            actual = await gateway.invoke(target["id"], revision=state["revision"],
                                          inputs=arguments)
            self.assertEqual(actual["state"], "host_reported_success_unverified")
            self.assertEqual(actual["operation_id"], target["id"])
            self.assertTrue(actual["native_result"].content[0].text)
            self.assertEqual(gateway.evidence()[0]["access"], "read")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "Physical BODY graph renderer requires FFmpeg and FFprobe")
    async def test_real_body_author_and_render_cross_the_internal_controller_ack_boundary(self):
        """Scripted choices exercise genuine BODY operations, not neural artistry."""
        import hashlib
        import json
        from studio_next.capability_mcp_session import CombinedCapabilityMcpSession
        from studio_next.native_creative_control import NativeCreativeControl
        from studio_next.test_native_creative_control import ScriptedModel, decision
        from studio_next.test_body_visual_document import graph
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gateway = await connect_installed_zx7_body(root)
            grants = gateway._live_grants("zx7")
            view = CombinedCapabilityMcpSession(gateway, "zx7")
            plan = "creative-graphs/first.json"
            model = ScriptedModel([
                decision("invoke", tool="body.visual_author", inputs={"document": graph(), "out": plan}),
                decision("invoke", tool="body.visual_graph", inputs={"plan": plan, "out": "first.png"}),
                decision("finish", summary="fixture only"),
            ])
            result = await NativeCreativeControl(view, model, host_tool_access=grants,
                max_turns=3, required_evidence=("native_write_acknowledged",)).run("Synthetic integration fixture")
            self.assertEqual(result["status"], "model_finished_unverified")
            writes = [e for e in result["events"] if e.get("host_application_write_acknowledged") is True]
            self.assertEqual([e["tool"] for e in writes], ["body.visual_author", "body.visual_graph"])
            self.assertEqual(json.loads((root / plan).read_text()), graph())
            with Image.open(root / "first.png") as image:
                image.load()
                self.assertEqual(image.size, (32, 24))
            self.assertEqual(hashlib.sha256((root / plan).read_bytes()).hexdigest(),
                json.loads(model.observed[1]["last_native_result_texts"][0])["sha256"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "Physical BODY graph renderer requires FFmpeg and FFprobe")
    async def test_actual_body_picture_reaches_model_without_native_video_import(self):
        """A decoded graphics render is a model-visible image, not an export proof."""
        import hashlib
        import io
        import json
        from studio_next.capability_mcp_session import CombinedCapabilityMcpSession
        from studio_next.native_creative_control import NativeCreativeControl
        from studio_next.native_creative_audit import audit_native_journal
        from studio_next.test_native_creative_control import ScriptedModel, decision
        from studio_next.test_body_visual_document import graph
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gateway = await connect_installed_zx7_body(root)
            grants = gateway._live_grants("zx7")
            self.assertEqual(grants.get("body.observe_picture"), "read")
            view = CombinedCapabilityMcpSession(gateway, "zx7")
            plan = "creative-graphs/first.json"
            await view.call_tool("body.visual_author", {"document": graph(), "out": plan})
            rendered = await view.call_tool("body.visual_graph", {"plan": plan, "out": "first.png"})
            sha = json.loads(rendered.content[0].text)["sha256"]
            model = ScriptedModel([
                decision("invoke", tool="body.observe_picture", inputs={"source": "first.png", "source_sha256": sha}),
                decision("finish", summary="fixture only"),
            ])
            result = await NativeCreativeControl(view, model, host_tool_access=grants,
                max_turns=2).run("Synthetic picture-sensor integration fixture")
            self.assertEqual(result["status"], "model_finished_unverified")
            context, pictures = model.images_observed[0]
            self.assertEqual(context["native_picture_origin"], "body_source_picture_not_verified_video_export")
            self.assertEqual(pictures[0][0], "image/png")
            with Image.open(io.BytesIO(pictures[0][1])) as preview, Image.open(root / "first.png") as original:
                self.assertEqual(preview.convert("RGBA").tobytes(), original.convert("RGBA").tobytes())
            observed = next(e for e in result["events"] if e.get("body_picture_source_sha256"))
            self.assertEqual(observed["body_picture_source_sha256"], sha)
            self.assertIsNone(observed["observed_export_sha256"])
            self.assertEqual(observed["image_sha256"], [hashlib.sha256(pictures[0][1]).hexdigest()])
            audit = audit_native_journal(result["events"], host_tool_access=grants, expected_required_evidence=())
            self.assertEqual(audit["observed_verified_export_digests"], [])

    async def test_body_picture_read_refuses_wrong_bytes_links_private_paths_and_write_only(self):
        import hashlib
        from PIL import Image
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root = Path(td)
            image = root / "picture.png"
            Image.new("RGB", (12, 10), "red").save(image)
            sha = hashlib.sha256(image.read_bytes()).hexdigest()
            external = Path(outside) / "picture.png"
            external.write_bytes(image.read_bytes())
            (root / "link.png").symlink_to(external)
            (root / "state").mkdir()
            (root / "state/private.png").write_bytes(image.read_bytes())
            adapter = InstalledBodyAdapter(root, allowed_access=("read",))
            self.assertIn("body.observe_picture", adapter.trusted_grants())
            for source, digest in (("picture.png", "a" * 64), ("link.png", sha),
                    (str(external), sha), ("state/private.png", sha)):
                with self.subTest(source=source), self.assertRaises((ValueError, PermissionError)):
                    await adapter.call_tool("body.observe_picture", {"source": source, "source_sha256": digest})
            result = await adapter.call_tool("body.observe_picture", {"source": "picture.png", "source_sha256": sha})
            self.assertEqual(len(result.content), 2)
            self.assertFalse((root / "vault").exists())
            denied = InstalledBodyAdapter(root, allowed_access=("write",))
            self.assertNotIn("body.observe_picture", denied.trusted_grants())
            with self.assertRaises(PermissionError):
                await denied.call_tool("body.observe_picture", {"source": "picture.png", "source_sha256": sha})

    async def test_model_attachment_cannot_bypass_original_source_custody_policy(self):
        from studio_next.body_integration import body_catalog
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = InstalledBodyAdapter(root)
            raw = body_catalog(root, initialize_vault=False)
            self.assertTrue({"body.render_edit", "body.otio"}.issubset(
                {item["id"] for item in raw.discover()}))
            grants = adapter.trusted_grants()
            for legacy in ("body.render_edit", "body.otio"):
                self.assertNotIn(legacy, grants)
                with self.assertRaises(PermissionError):
                    await adapter.call_tool(legacy, {"edit": "fake.json", "out": "fake.mp4"})
            self.assertEqual(list(root.iterdir()), [])
            if "body.render_edit_owned" in raw.executable_ids():
                self.assertIn("body.render_edit_owned", grants)
            if "body.otio_owned_export" in raw.executable_ids():
                self.assertIn("body.otio_owned_export", grants)

    async def test_denied_and_pure_read_calls_do_not_initialize_owner_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = InstalledBodyAdapter(root, allowed_access=("read",))
            with self.assertRaises(PermissionError):
                await adapter.call_tool("body.visual_author", {})
            self.assertEqual(list(root.iterdir()), [])
            result = await adapter.call_tool("body.timecode_format", {
                "numerator": 24, "denominator": 1, "frame_index": 48, "drop_frame": False})
            self.assertFalse(result.is_error)
            self.assertEqual(list(root.iterdir()), [])

    async def test_read_grant_cannot_execute_write_tools(self):
        with tempfile.TemporaryDirectory() as root:
            gateway = await connect_installed_zx7_body(root, allowed_access=("read",))
            state = gateway._current().overview()
            options = gateway.search("asset vault", limit=8)["matches"]
            self.assertFalse(any(x["access"] == "write" for x in options))
            with self.assertRaises(CapabilityContractError):
                await gateway.invoke("zx7/body.asset_vault", revision=state["revision"],
                                     inputs={"source_witness": {"fake": True}})
            self.assertFalse(gateway.evidence())

    async def test_actual_body_works_without_exposing_uninstalled_renderers(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = InstalledBodyAdapter(root, allowed_access=("read", "write"))
            grants = adapter.trusted_grants()
            real = await adapter.list_tools()
            self.assertEqual({t.name for t in real.tools}, set(grants))
            self.assertTrue(all(grant in ("read", "write") for grant in grants.values()))
            self.assertNotIn("body.invented_capability", grants)
            self.assertFalse(any("Markdown" in str(t) for t in real.tools))
            self.assertIsNone(real.nextCursor)


    async def test_catalog_discovery_and_grant_refresh_are_pure_read_only(self):
        """Observing possible creative tools must never create a media store."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = InstalledBodyAdapter(root, allowed_access=("read", "write"))
            expected = adapter.trusted_grants()
            names = {tool.name for tool in (await adapter.list_tools()).tools}
            self.assertIn("body.timecode_format", names)
            self.assertEqual(set(expected), names)
            self.assertFalse((root / "vault").exists(),
                "Read-only installed-tool inventory unexpectedly initialized media storage")
            self.assertFalse((root / ".zx7-host-private").exists())
            self.assertEqual(list(root.iterdir()), [])

    async def test_attaching_actual_body_gateway_does_not_write_before_tool_dispatch(self):
        """The live shared Brain/BODY discovery path must remain side-effect free."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gateway = await connect_installed_zx7_body(root, allowed_access=("read",))
            overview = gateway._current().overview()
            self.assertGreater(overview["operation_count"], 0)
            self.assertTrue(gateway.search("timecode", limit=4)["matches"])
            await gateway.refresh()
            self.assertEqual(gateway.evidence(), [])
            self.assertEqual(list(root.iterdir()), [],
                "Tool discovery, gateway attachment or refresh wrote owner workspace")

    async def test_real_installed_body_respects_host_supplied_call_budget(self):
        with tempfile.TemporaryDirectory() as root:
            budget = CapabilitySessionBudget(
                max_calls=1, max_writes=0, per_source={"zx7": 1})
            gateway = await connect_installed_zx7_body(
                root, allowed_access=("read",), session_budget=budget)
            revision = gateway._current().revision
            args = {"frame_index": 48, "numerator": 24,
                    "denominator": 1, "drop_frame": False}
            actual = await gateway.invoke(
                "zx7/body.timecode_format", revision=revision, inputs=args)
            self.assertEqual(actual["state"], "host_reported_success_unverified")
            with self.assertRaisesRegex(
                    CapabilityExecutionError, "host_session_call_budget_exhausted"):
                await gateway.invoke(
                    "zx7/body.timecode_format", revision=revision, inputs=args)
            self.assertEqual(len(gateway.evidence()), 1)
            self.assertEqual(gateway.host_budget_evidence()["reserved_calls"], 1)
            self.assertEqual(gateway.host_budget_evidence()["reserved_writes"], 0)

    async def test_blender_source_through_model_gateway_requires_original_durable_publication(self):
        """A source-producing native operation must use the existing verified
        DurableFilmGraph; it cannot silently publish a manifest-only .blend.
        """
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root:
            adapter = InstalledBodyAdapter(root, allowed_access=("read", "write"))
            with patch("studio_next.body_integration.motion_runtime_ready", return_value=True), \
                 patch("studio_next.body_integration._trusted_body_revision",
                       return_value="sha256:" + "a" * 64), \
                 patch("studio_next.body_integration.run_body_project",
                       return_value={"status": "blocked", "errors": ["fixture denial"]}) as graph, \
                 patch("studio_next.registry.ToolCatalog.invoke",
                       side_effect=AssertionError("direct unjournalled writer")):
                with self.assertRaisesRegex(ValueError, "durable"):
                    await adapter.call_tool("body.motion_project", {
                        "plan": "original-scene.json",
                        "out": "first.zxmotion"})
                graph.assert_called_once()
                self.assertFalse((Path(root) / "first.zxmotion").exists())

    async def test_blender_source_cannot_bypass_owner_read_only_grant(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root:
            adapter = InstalledBodyAdapter(root, allowed_access=("read",))
            with patch("studio_next.body_integration.motion_runtime_ready", return_value=True), \
                 patch("studio_next.body_integration._trusted_body_revision",
                       return_value="sha256:" + "a" * 64), \
                 patch("studio_next.body_integration.run_body_project") as graph:
                with self.assertRaises(PermissionError):
                    await adapter.call_tool("body.motion_project", {
                        "plan": "original-scene.json",
                        "out": "first.zxmotion"})
                graph.assert_not_called()

    async def test_invalid_body_budget_refuses_before_creating_durable_files(self):
        with tempfile.TemporaryDirectory() as root:
            for invalid in (
                {"max_calls": 1}, "host-created-string",
                CapabilitySessionBudget(
                    max_calls=1, max_writes=0,
                    per_source={"not-connected": 1}),
            ):
                with self.subTest(invalid=str(invalid)), self.assertRaises(ValueError):
                    await connect_installed_zx7_body(
                        root, allowed_access=("read",),
                        durable_write_requests=True, session_budget=invalid)
                self.assertFalse(
                    (Path(root) / ".zx7-host-private").exists())

    async def test_installed_body_opt_in_durable_writes_preserve_read_tools(self):
        with tempfile.TemporaryDirectory() as root:
            gateway = await connect_installed_zx7_body(
                root, allowed_access=("read", "write"),
                durable_write_requests=True)
            path = Path(root)/".zx7-host-private"/"capability-attempts.sqlite3"
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_mode & 0o077, 0)
            self.assertEqual(path.parent.stat().st_mode & 0o077, 0)
            revision=gateway._current().revision
            observed=await gateway.invoke("zx7/body.timecode_format",
                revision=revision,inputs={
                    "frame_index":48,"numerator":24,"denominator":1,
                    "drop_frame":False})
            self.assertEqual(observed["state"],"host_reported_success_unverified")
            # A generated-rights write would be rejected by its own BODY
            # graph policy, but stable host identity must be demanded even
            # earlier, before the legacy runner is ever called.
            with self.assertRaises(CapabilityAttemptError):
                await gateway.invoke("zx7/body.asset_vault",revision=revision,
                    inputs={"source_witness":{}})
            self.assertEqual(len(gateway.evidence()),1)
            self.assertIsNone(CapabilityAttemptStore(path).inspect("unissued"))

    async def test_installed_body_recovers_denied_native_write_identity_after_restart(self):
        with tempfile.TemporaryDirectory() as root:
            initial=await connect_installed_zx7_body(
                root,allowed_access=("read","write"),
                durable_write_requests=True)
            revision=initial._current().revision
            # The actual installed source-provenance writer refuses an
            # untrusted generated-media claim. That native failure is still
            # a possibly submitted write, so retain its host request ID.
            with self.assertRaises((PermissionError,ValueError)):
                await initial.invoke("zx7/body.asset_vault",
                    revision=revision,inputs={"source_witness":{}},
                    request_id="host-vault-denied-1")
            recovered=await connect_installed_zx7_body(
                root,allowed_access=("read","write"),
                durable_write_requests=True)
            page=recovered.unverified_native_writes(limit=4)
            self.assertEqual(len(page["attempts"]),1)
            self.assertEqual(page["attempts"][0]["request_id"],"host-vault-denied-1")
            self.assertEqual(page["attempts"][0]["operation_id"],
                             "zx7/body.asset_vault")
            self.assertEqual(page["attempts"][0]["state"],
                             "write_uncertain_reconciliation_required")
            self.assertFalse(page["attempts"][0]
                             ["native_application_state_independently_verified"])
            self.assertTrue(page["no_native_write_replayed"])
            self.assertFalse((Path(root)/"movie.mp4").exists())

    async def test_native_motion_refuses_success_without_actual_producer_receipt(self):
        """MCP direct native writes cannot launder an unattested Blender parent."""
        from types import SimpleNamespace
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter = InstalledBodyAdapter(root)
            class ForbiddenDirectRunner:
                def invoke(self, *_args, **_kwargs):
                    raise AssertionError("Direct native Blender runner skips host publication")
            with patch.object(adapter, "_installed", return_value=(
                ForbiddenDirectRunner(), {"body.motion_project": {"access": "write"}})):
                with patch("studio_next.body_integration.run_body_project",
                           return_value={"status": "all_tool_results_verified",
                                         "completed": ["native"], "errors": []}) as run:
                    with self.assertRaisesRegex((ValueError, FileNotFoundError),
                                                "published|source|No such|directory|Media missing"):
                        await adapter.call_tool("body.motion_project", {
                            "plan": "original.json", "out": "original.zxmotion"})
                    run.assert_called_once()
                    graph, destination = run.call_args.args
                    self.assertEqual(destination, root)
                    self.assertEqual(len(graph["tool_graph"]), 1)
                    node = graph["tool_graph"][0]
                    self.assertEqual(node["tool_id"], "body.motion_project")
                    self.assertEqual(node["inputs"], {
                        "plan": "original.json", "out": "original.zxmotion"})
                    self.assertEqual(node["depends_on"], [])
                    self.assertEqual(graph.get("owner_facts", {}), {})
                    self.assertFalse((root / "original.zxmotion").exists())

    async def test_native_motion_durable_failure_does_not_run_unfenced_writer(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter = InstalledBodyAdapter(root)
            class ForbiddenDirectRunner:
                def invoke(self, *_args, **_kwargs):
                    raise AssertionError("Unfenced write is not a fallback")
            with patch.object(adapter, "_installed", return_value=(
                ForbiddenDirectRunner(), {"body.motion_export": {"access": "write"}})):
                with patch("studio_next.body_integration.run_body_project",
                           return_value={"status": "blocked",
                                         "errors": ["Source needs an authentic host publication"]}):
                    with self.assertRaisesRegex(ValueError, "original durable BODY publication"):
                        await adapter.call_tool("body.motion_export", {
                            "bundle": "unverified.zxmotion", "out": "fake.mp4", "fps": 12})
                    self.assertFalse((root / "fake.mp4").exists())

    async def test_installed_body_refuses_non_boolean_durable_policy(self):
        with tempfile.TemporaryDirectory() as root:
            for invalid in ("true",1,None):
                with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                    await connect_installed_zx7_body(
                        root,durable_write_requests=invalid)
            self.assertFalse((Path(root)/".zx7-host-private").exists())


if __name__ == "__main__":
    unittest.main()
