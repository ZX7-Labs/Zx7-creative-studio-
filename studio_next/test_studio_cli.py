"""Owner workflow integration. Fixture model responses do not prove creativity."""
import contextlib
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, patch

from . import studio_cli as studio


class StudioOwnerWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.root = self.base / "studio"

    def init(self, **changes):
        values = dict(source=self.source, model_id="local-fixture")
        values.update(changes)
        return studio.initialize_workspace(self.root, **values)

    def test_init_is_private_complete_and_never_overwrites(self):
        self.init()
        root, settings, grants = studio.load_workspace(self.root)
        self.assertEqual(settings["provider"], "local")
        self.assertTrue(grants.verify_native_exports)
        self.assertEqual(grants.outputs_root, root / "outputs")
        self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((root / "studio.json").stat().st_mode), 0o600)
        original = (root / "studio.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.init(model_id="changed")
        self.assertEqual((root / "studio.json").read_bytes(), original)

    def test_doctor_checks_actual_local_server_model_inventory_without_inference(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                raw = json.dumps({"data": [{"id": "local-fixture"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.init(base_url=f"http://127.0.0.1:{server.server_port}")
        report = studio.doctor(self.root)
        check = next(c for c in report["checks"] if c["name"] == "local_model")
        self.assertTrue(check["ready"])
        self.assertFalse(report["ready"])  # Real editor source/build still absent.
        self.assertEqual(requests, ["/v1/models"])

    def test_run_uses_canonical_native_session_preserves_asset_rights_and_result(self):
        from studio_next import native_editor_session
        self.init()
        original = self.base / "owned.bin"
        original.write_bytes(b"original fixture media, not a neural result")
        captured = []
        async def execute(args):
            captured.append(args)
            config = json.loads(args.config.read_text())
            self.assertEqual(config["projects_root"], str(self.root / "projects"))
            self.assertEqual(args.evaluation_evidence, "export")
            self.assertTrue(args.structured_actions)
            brief = args.brief_file.read_text()
            self.assertIn("मेरी फिल्म बनाओ", brief)
            self.assertNotIn("scene 1", brief)
            source = next(Path(config["staging_root"]).iterdir())
            self.assertEqual(source.read_bytes(), original.read_bytes())
            return {"status": "model_finished_unverified", "evaluation_evidence_satisfied": True}
        with patch.object(studio, "doctor", return_value={"ready": True}), \
                patch.object(native_editor_session, "run_native_session", side_effect=execute):
            result = studio.run_workspace(self.root, brief="मेरी फिल्म बनाओ",
                assets=[original], rights="I own this fixture")
        self.assertEqual(result["state"], "completed")
        self.assertEqual(len(captured), 1)
        self.assertEqual(original.read_bytes(), b"original fixture media, not a neural result")
        saved = studio.workspace_status(self.root)["sessions"]
        self.assertEqual(saved, [result])
        ledger = json.loads((self.root / "sessions" / result["session_id"] / "sources.json").read_text())
        self.assertEqual(ledger[0]["rights"], "I own this fixture")
        self.assertFalse(ledger[0]["rights_independently_verified"])

    def test_owner_revision_passes_selected_project_to_canonical_session(self):
        from studio_next import native_editor_session
        self.init()
        selected = self.root / "projects" / "owned-project"
        selected.mkdir()
        (selected / "project.comfystudio").write_text("{}")
        model = AsyncMock(return_value={"evaluation_evidence_satisfied": False})
        with patch.object(studio, "doctor", return_value={"ready": True}), \
                patch.object(native_editor_session, "run_native_session", model):
            report = studio.run_workspace(self.root, brief="Revise my title", project=selected)
        self.assertEqual(model.await_args.args[0].project, selected)
        self.assertEqual(report["state"], "needs_attention")
        self.assertTrue(Path(report["outputs_directory"]).is_dir())

    def test_uncertain_native_failure_is_retained_without_second_submission(self):
        from studio_next import native_editor_session
        self.init()
        failed = AsyncMock(side_effect=RuntimeError("uncertain outcome fixture"))
        with patch.object(studio, "doctor", return_value={"ready": True}), \
                patch.object(native_editor_session, "run_native_session", failed):
            with self.assertRaises(RuntimeError):
                studio.run_workspace(self.root, brief="Create and export")
        self.assertEqual(failed.await_count, 1)
        report = studio.workspace_status(self.root)["sessions"][0]
        self.assertEqual(report["state"], "failed")
        self.assertFalse(report["automatic_write_replay"])
        self.assertFalse(report["artistic_quality_approved"])

    def test_invalid_rights_setup_and_project_do_not_launch_model_or_copy_media(self):
        from studio_next import native_editor_session
        self.init()
        media = self.base / "source.mov"
        media.write_bytes(b"fixture")
        with patch.object(native_editor_session, "run_native_session", AsyncMock()) as model:
            for changes in ({"assets": [media]}, {"project": self.base},
                            {"allow_cloud_image_upload": True}, {"max_turns": 0}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    studio.run_workspace(self.root, brief="Owner brief", **changes)
            with patch.object(studio, "doctor", return_value={"ready": False,
                    "checks": [{"name": "electron", "ready": False}]}), self.assertRaisesRegex(ValueError, "electron"):
                studio.run_workspace(self.root, brief="Owner brief")
            model.assert_not_awaited()
        self.assertEqual(list((self.root / "sessions").iterdir()), [])

    def test_redirected_roots_and_unsafe_configuration_are_refused(self):
        self.init()
        (self.root / "outputs").rmdir()
        (self.root / "outputs").symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(ValueError):
            studio.load_workspace(self.root)
        (self.root / "outputs").unlink()
        (self.root / "outputs").mkdir(mode=0o700)
        (self.root / "studio.json").chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private"):
            studio.load_workspace(self.root)

    def test_owner_cli_reports_setup_failure_and_status(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(studio.main(["init", str(self.root), "--source", str(self.source),
                                         "--model-id", "local-fixture"]), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "initialized")
        with patch.object(studio, "doctor", return_value={"ready": False, "checks": []}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(studio.main(["doctor", str(self.root)]), 2)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(studio.main(["status", str(self.root)]), 0)
        self.assertEqual(json.loads(out.getvalue())["sessions"], [])


if __name__ == "__main__":
    unittest.main()
