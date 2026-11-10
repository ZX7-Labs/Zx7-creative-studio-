"""Host editor grants and real filesystem scope, independent of model data."""
from dataclasses import FrozenInstanceError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from studio_next.body_editor_client import EditorAccessError, EditorClientError
from studio_next.body_editor_policy import EditorConfig, EditorPathPolicy, load_editor_config


class EditorPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.projects = self.root / "projects"
        self.staging = self.root / "staging"
        self.outputs = self.root / "outputs"
        self.outside = self.root / "outside"
        for directory in (self.projects, self.staging, self.outputs, self.outside):
            directory.mkdir()
        self.media = self.staging / "original.mp4"
        self.media.write_bytes(b"synthetic file, no media validity claim")
        self.config_path = self.root / "host.json"

    def tearDown(self):
        self.temp.cleanup()

    def config(self, **changes):
        value = {"endpoint": "http://127.0.0.1:19790/mcp",
                 "projects_root": str(self.projects), "staging_root": str(self.staging),
                 "outputs_root": str(self.outputs),
                 "allowed_tools": {"get_project": "read", "export_timeline": "write"},
                 "allowed_access": ["read", "write"]}
        value.update(changes)
        self.config_path.write_text(json.dumps(value), encoding="utf-8")
        return load_editor_config(self.config_path)

    def policy(self):
        return EditorPathPolicy(self.projects, self.staging, self.outputs)

    def test_load_preserves_canonical_roots_and_immutable_copied_grants(self):
        config = self.config()
        self.assertIsInstance(config, EditorConfig)
        self.assertEqual(config.projects_root, self.projects.resolve())
        self.assertEqual(config.timeout, 30.0)
        self.assertEqual(config.allowed_access, frozenset({"read", "write"}))
        with self.assertRaises(TypeError):
            config.allowed_tools["unknown"] = "write"
        with self.assertRaises(FrozenInstanceError):
            config.endpoint = "http://127.0.0.1:1/mcp"

    def test_native_export_proof_is_host_opt_in_and_strict_boolean(self):
        self.assertFalse(self.config().verify_native_exports)
        self.assertTrue(self.config(verify_native_exports=True).verify_native_exports)
        for invalid in ("true", 1, [], None):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                    ValueError, "explicitly enabled"):
                self.config(verify_native_exports=invalid)

    def test_optional_owner_delivery_is_bounded_and_immutable(self):
        self.assertIsNone(self.config().required_export_delivery)
        approved = {"width": 640, "height": 360, "fps": 24,
                    "max_duration": 6, "video_codec": "h264"}
        cfg = self.config(required_export_delivery=approved)
        self.assertEqual(dict(cfg.required_export_delivery), approved)
        approved["width"] = 1920
        self.assertEqual(cfg.required_export_delivery["width"], 640)
        with self.assertRaises(TypeError):
            cfg.required_export_delivery["width"] = 1920
        for invalid in (
            {}, [], {"width": 640},
            {**dict(cfg.required_export_delivery), "unknown": "permission"},
            {**dict(cfg.required_export_delivery), "width": True},
            {**dict(cfg.required_export_delivery), "width": 639},
            {**dict(cfg.required_export_delivery), "height": -360},
            {**dict(cfg.required_export_delivery), "fps": True},
            {**dict(cfg.required_export_delivery), "fps": float("nan")},
            {**dict(cfg.required_export_delivery), "fps": 0},
            {**dict(cfg.required_export_delivery), "max_duration": float("inf")},
            {**dict(cfg.required_export_delivery), "max_duration": -1},
            {**dict(cfg.required_export_delivery), "video_codec": "invented_codec"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.config(required_export_delivery=invalid)

    def test_constructor_also_copies_grants_and_access(self):
        grants = {"get_project": "read"}
        access = ["read"]
        config = EditorConfig("http://127.0.0.1:19790/mcp", self.projects,
                              self.staging, self.outputs, grants, access)
        grants["export_timeline"] = "write"
        access.append("write")
        self.assertEqual(dict(config.allowed_tools), {"get_project": "read"})
        self.assertEqual(config.allowed_access, frozenset({"read"}))

    def test_loader_has_no_filesystem_mutation_for_new_roots(self):
        missing = self.root / "not-created" / "projects"
        config = self.config(projects_root=str(missing))
        self.assertEqual(config.projects_root, missing)
        self.assertFalse(missing.parent.exists())

    def test_existing_file_cannot_be_a_root_or_ancestor_of_a_root(self):
        for root in (self.media, self.media / "new-root"):
            with self.subTest(root=root), self.assertRaises(ValueError):
                self.config(projects_root=str(root))

    def test_roots_cannot_have_padding_that_the_native_editor_would_trim(self):
        for name, root in (("projects_root", self.projects), ("staging_root", self.staging),
                           ("outputs_root", self.outputs)):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.config(**{name: str(root) + " "})
        for root in (str(self.projects) + " ", Path(str(self.projects) + " ")):
            with self.subTest(root=root), self.assertRaises(ValueError):
                EditorConfig("http://127.0.0.1:19790/mcp", root, self.staging,
                             self.outputs, {"get_project": "read"})

    def test_relative_roots_remote_endpoints_and_invalid_timeouts_are_refused(self):
        for changes in ({"projects_root": "relative"}, {"endpoint": "http://localhost:1/mcp"},
                        {"timeout": True}, {"timeout": 0}, {"timeout": float("inf")},
                        {"allowed_tools": {"get_project": "network"}},
                        {"allowed_access": ["read", "paid"]}, {"extra": "smuggled"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.config(**changes)

    def test_nonfinite_duplicate_utf8_and_oversized_config_are_refused(self):
        for raw in (b'{"endpoint":1,"endpoint":2}', b'{"timeout":NaN}', b'\xff', b' ' * (1024 * 1024 + 1)):
            self.config_path.write_bytes(raw)
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                load_editor_config(self.config_path)

    def test_network_generation_global_lookup_and_nested_grants_are_refused(self):
        for name in ("search_stock_media", "queue_prompt_generation_batch", "generate_music",
                     "control_comfyui_launcher", "install_workflow_setup", "run_mcp_action_plan",
                     "export_delivery_batch", "list_recent_projects", "duplicate_project"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.config(allowed_tools={name: "write"})

    def test_import_and_relink_source_aliases_are_scoped(self):
        policy = self.policy()
        for tool in ("import_asset_from_path", "relink_asset"):
            for field in ("path", "filePath", "sourcePath"):
                self.assertTrue(policy(tool, {field: str(self.media)}, "write"))
                self.assertFalse(policy(tool, {field: str(self.outside / "secret")}, "write"))
            self.assertFalse(policy(tool, {"path": str(self.media), "sourcePath": "/etc/passwd"}, "write"))
            self.assertFalse(policy(tool, {}, "write"))

    def test_new_outputs_are_allowed_under_project_or_output_roots_only(self):
        policy = self.policy()
        for root in (self.projects, self.outputs):
            self.assertTrue(policy("export_timeline", {"outputPath": str(root / "new" / "movie.mp4")}, "write"))
            self.assertTrue(policy("export_fcpxml", {"outputPath": str(root / "new" / "edit.xml")}, "write"))
        self.assertFalse(policy("export_timeline", {"outputPath": str(self.staging / "movie.mp4")}, "write"))
        self.assertFalse(policy("export_timeline", {"outputPath": str(self.outputs / ".." / "outside" / "movie.mp4")}, "write"))

    def test_exports_require_an_explicit_new_destination(self):
        for tool in ("export_timeline", "export_fcpxml"):
            with self.subTest(tool=tool), self.assertRaisesRegex(EditorAccessError, "explicit.*outputPath"):
                self.policy()(tool, {}, "write")

    def test_exports_cannot_overwrite_existing_files_directories_or_symlinks(self):
        project = self.projects / "native"
        project.mkdir()
        original = project / "project.comfystudio"
        original.write_bytes(b"saved original project")
        linked = self.outputs / "linked.mp4"
        linked.symlink_to(original)
        dangling = self.outputs / "dangling.mp4"
        dangling.symlink_to(self.outputs / "not-created.mp4")
        for tool in ("export_timeline", "export_fcpxml"):
            for destination in (original, project, linked, dangling, str(original) + " "):
                with self.subTest(tool=tool, destination=destination):
                    try:
                        accepted = self.policy()(tool, {"outputPath": str(destination)}, "write")
                    except EditorAccessError:
                        accepted = False
                    self.assertFalse(accepted)
        self.assertEqual(original.read_bytes(), b"saved original project")
        self.assertTrue(self.policy()("inspect_export_file", {"path": str(original)}, "read"))

    def test_existing_and_dangling_symlink_escapes_are_refused(self):
        policy = self.policy()
        (self.outputs / "escape").symlink_to(self.outside, target_is_directory=True)
        (self.outputs / "dead").symlink_to(self.outside / "missing", target_is_directory=True)
        for output in (self.outputs / "escape" / "new.mp4", self.outputs / "dead" / "new.mp4"):
            self.assertFalse(policy("export_timeline", {"outputPath": str(output)}, "write"))
        (self.staging / "escape.mp4").symlink_to(self.outside / "secret.mp4")
        self.assertFalse(policy("import_asset_from_path", {"path": str(self.staging / "escape.mp4")}, "write"))
        self.assertFalse(policy("import_asset_from_path", {"path": str(self.staging / "escape.mp4") + " "}, "write"))

    def test_client_does_not_rebind_a_configured_root_after_symlink_replacement(self):
        config = self.config(endpoint="http://127.0.0.1:1/mcp")
        self.outputs.rename(self.root / "original-outputs")
        self.outputs.symlink_to(self.outside, target_is_directory=True)
        try:
            config.client().call("export_timeline", {"outputPath": str(self.outputs / "escaped.mp4")},
                                 allowed_access=config.allowed_access)
        except EditorAccessError:
            pass
        except EditorClientError:
            self.fail("Replaced root was authorized and reached HTTP instead of being denied")
        else:
            self.fail("Replaced root was authorized")

    def test_inspection_aliases_and_render_directory_are_scoped(self):
        policy = self.policy()
        for field in ("path", "filePath", "outputPath", "rendersDir"):
            self.assertTrue(policy("inspect_export_file", {field: str(self.outputs / "result.mp4")}, "read"))
            self.assertFalse(policy("inspect_export_file", {field: str(self.outside)}, "read"))

    def test_project_open_requires_scoped_path_not_global_name(self):
        policy = self.policy()
        self.assertTrue(policy("open_project", {"projectPath": str(self.projects / "native")}, "write"))
        self.assertFalse(policy("open_project", {"projectName": "private"}, "write"))
        self.assertFalse(policy("open_project", {"projectPath": str(self.outside)}, "write"))

    def test_project_open_checks_primary_and_legacy_native_document_links(self):
        project = self.projects / "native"
        project.mkdir()
        outside_document = self.outside / "private.json"
        outside_document.write_text('{"private":true}')
        for filename in ("project.comfystudio", "project.storyflow"):
            document = project / filename
            document.write_text('{"saved":true}')
            self.assertTrue(self.policy()("open_project", {"projectPath": str(project)}, "write"))
            document.unlink()
            document.symlink_to(outside_document)
            self.assertFalse(self.policy()("open_project", {"projectPath": str(project)}, "write"))
            document.unlink()
            document.symlink_to(project / "missing.json")
            self.assertFalse(self.policy()("open_project", {"projectPath": str(project)}, "write"))
            document.unlink()
            internal = project / "saved.json"
            internal.write_text('{"saved":true}')
            document.symlink_to(internal)
            self.assertTrue(self.policy()("open_project", {"projectPath": str(project)}, "write"))
            document.unlink()

    def test_project_create_restricts_all_name_aliases_to_one_component(self):
        policy = self.policy()
        for field in ("name", "projectName", "title"):
            self.assertTrue(policy("create_project", {field: "मेरा original edit"}, "write"))
            for name in ("..", "../outside", "a/b", "a\\b", "", "nul\x00name"):
                self.assertFalse(policy("create_project", {field: name}, "write"))
        self.assertFalse(policy("create_project", {"name": "safe", "title": "../unsafe"}, "write"))

    def test_native_logical_asset_folder_paths_are_not_host_filesystem_paths(self):
        policy = self.policy()
        self.assertTrue(policy("create_asset_folder", {"path": ["Scenes", "Opening"], "previewOnly": False}, "write"))
        self.assertTrue(policy("move_assets_to_folder", {"path": "Scenes / Opening"}, "write"))
        self.assertTrue(policy("set_clip_keyframes", {"keyframes": [{"value": 0.5, "time": 1}]}, "write"))

    def test_unsupported_top_level_host_file_aliases_are_refused(self):
        self.assertFalse(self.policy()("get_project", {"filePath": "/etc/passwd"}, "read"))
        self.assertFalse(self.policy()("export_timeline", {"sourceProjectPath": "/etc"}, "write"))

    def test_client_denies_path_before_http_and_permits_scoped_native_call(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(request)
                data = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": {"content": []}}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            config = self.config(endpoint=f"http://127.0.0.1:{server.server_port}/mcp")
            client = config.client()
            with self.assertRaises(EditorAccessError):
                client.call("export_timeline", {"outputPath": "/etc/unowned.mp4"}, allowed_access=config.allowed_access)
            saved_project = self.projects / "project.comfystudio"
            original_asset = self.projects / "original.mp4"
            originals = {saved_project: b"saved editable native project", original_asset: b"original asset"}
            for path, data in originals.items():
                path.write_bytes(data)
            for tool in ("export_timeline", "export_fcpxml"):
                export_client = self.config(endpoint=f"http://127.0.0.1:{server.server_port}/mcp",
                    allowed_tools={tool: "write"}).client()
                for path in originals:
                    with self.subTest(tool=tool, path=path), self.assertRaises(EditorAccessError):
                        export_client.call(tool, {"outputPath": str(path)}, allowed_access={"write"})
                with self.subTest(tool=tool), self.assertRaises(EditorAccessError):
                    export_client.call(tool, {}, allowed_access={"write"})
            private_document = self.outside / "private.json"
            private_document.write_bytes(b"private native document")
            open_client = self.config(endpoint=f"http://127.0.0.1:{server.server_port}/mcp",
                allowed_tools={"open_project": "write"}).client()
            for filename in ("project.comfystudio", "project.storyflow"):
                linked_project = self.projects / filename.replace(".", "-")
                linked_project.mkdir()
                (linked_project / filename).symlink_to(private_document)
                with self.subTest(document=filename), self.assertRaises(EditorAccessError):
                    open_client.call("open_project", {"projectPath": str(linked_project)}, allowed_access={"write"})
            self.assertEqual(requests, [])
            self.assertEqual({path: path.read_bytes() for path in originals}, originals)
            self.assertEqual(private_document.read_bytes(), b"private native document")
            client.call("export_timeline", {"outputPath": str(self.outputs / "owned.mp4")}, allowed_access=config.allowed_access)
            self.assertEqual(len(requests), 1)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
