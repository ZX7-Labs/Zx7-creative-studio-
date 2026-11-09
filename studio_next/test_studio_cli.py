"""Owner workflow integration. Fixture model responses do not prove creativity."""
import contextlib
import hashlib
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import stat
import select
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, patch

from studio_next import studio_cli as studio


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
            self.assertTrue(args.indexed_catalog)
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

    def test_failed_revision_retains_exact_prior_saved_project(self):
        from studio_next import native_editor_session
        self.init()
        selected = self.root / "projects" / "owned-project"
        selected.mkdir()
        native = selected / "project.comfystudio"
        original = b'{"timelines":[{"id":"before","clips":[]}]}\n'
        native.write_bytes(original)

        async def interrupted_save(args):
            snapshot = args.receipt.parent / "prior-project.comfystudio"
            self.assertEqual(snapshot.read_bytes(), original)
            self.assertEqual(stat.S_IMODE(snapshot.stat().st_mode), 0o600)
            self.assertEqual(native.read_bytes(), original)
            native.write_bytes(b'{"timelines":[{"id":"after"}]}\n')
            raise RuntimeError("interrupted after native save")

        with patch.object(studio, "doctor", return_value={"ready": True}), \
                patch.object(native_editor_session, "run_native_session", side_effect=interrupted_save):
            with self.assertRaisesRegex(RuntimeError, "interrupted after native save"):
                studio.run_workspace(self.root, brief="Revise my title", project=selected)
        status = studio.workspace_status(self.root)["sessions"][0]
        self.assertEqual(status["state"], "failed")
        self.assertFalse(status["automatic_write_replay"])
        checkpoint = status["prior_project_checkpoint"]
        self.assertEqual(checkpoint["project"], str(selected))
        self.assertEqual(checkpoint["sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(checkpoint["bytes"], len(original))
        self.assertEqual(Path(checkpoint["path"]).read_bytes(), original)
        self.assertIn(b'"after"', native.read_bytes())

    def test_revision_refuses_redirected_saved_project_before_editor_open(self):
        from studio_next import native_editor_session
        self.init()
        selected = self.root / "projects" / "owned-project"
        selected.mkdir()
        external = self.base / "external.comfystudio"
        external.write_text("{}")
        (selected / "project.comfystudio").symlink_to(external)
        model = AsyncMock(return_value={"evaluation_evidence_satisfied": False})
        with patch.object(studio, "doctor", return_value={"ready": True}), \
                patch.object(native_editor_session, "run_native_session", model):
            with self.assertRaisesRegex(ValueError, "Saved native project file must not be a symbolic link"):
                studio.run_workspace(self.root, brief="Revise my title", project=selected)
        model.assert_not_awaited()
        self.assertEqual(external.read_text(), "{}")

    def test_hosted_transport_uses_the_same_bounded_catalog_as_local(self):
        from studio_next import native_editor_session
        self.init(provider="nvidia", model_id="hosted-fixture")
        model = AsyncMock(return_value={"evaluation_evidence_satisfied": False})
        with patch.object(studio, "doctor", return_value={"ready": True}), \
                patch.object(native_editor_session, "run_native_session", model):
            studio.run_workspace(self.root, brief="An explicitly mocked transport fixture")
        args = model.await_args.args[0]
        self.assertEqual(args.provider, "nvidia")
        self.assertTrue(args.indexed_catalog)
        self.assertFalse(args.allow_cloud_image_upload)
        self.assertTrue(args.structured_actions)

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

    def start_blocked_fixture_runner(self, phase="running", asset=None):
        # Real process + real workspace/session kernel locks. The sole session
        # function is an explicitly blocked fixture, never a model/API call.
        code = """
import asyncio, json, sys, threading
from pathlib import Path
from unittest.mock import patch
from studio_next import studio_cli as studio, native_editor_session
async def blocked(args):
    print(json.dumps({'session_id': args.receipt.parent.name}), flush=True)
    await asyncio.Event().wait()
def blocked_staging(path, destination, rights):
    print(json.dumps({'session_id': destination.name}), flush=True)
    threading.Event().wait()
kwargs = ({'assets': [Path(sys.argv[3])], 'rights': 'I own this fixture'}
          if sys.argv[2] == 'preparing' else {})
with patch.object(studio, 'doctor', return_value={'ready': True}), \
        patch.object(native_editor_session, 'run_native_session', blocked), \
        patch.object(studio, '_stage_asset', blocked_staging):
    studio.run_workspace(Path(sys.argv[1]), brief='Blocked process fixture; no model calls', **kwargs)
"""
        process = subprocess.Popen([sys.executable, "-c", code, str(self.root), phase, str(asset or "")],
            cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
        self.addCleanup(cleanup)
        readable, _, _ = select.select([process.stdout], [], [], 15)
        self.assertTrue(readable, "Fixture did not enter its real locked run")
        line = process.stdout.readline()
        if not line:
            self.fail("Fixture exited before holding locks: " + process.stderr.read())
        return process, json.loads(line)["session_id"]

    def test_killed_runner_is_observed_without_rewriting_persisted_evidence(self):
        self.init()
        process, sid = self.start_blocked_fixture_runner()
        path = self.root / "sessions" / sid / "status.json"
        original = path.read_bytes()
        report = studio.workspace_status(self.root)
        live = report["sessions"][0]
        self.assertEqual(live["state"], "running")
        self.assertEqual(live["runner_liveness"]["status"], "active")
        self.assertEqual(report["runner_observation"]["bound_session_id"], sid)
        self.assertTrue(report["runner_observation"]["workspace_lock_held"])
        self.assertEqual(path.read_bytes(), original)
        process.kill()
        process.wait(timeout=10)
        stopped = studio.workspace_status(self.root)
        record = stopped["sessions"][0]
        self.assertEqual(record["state"], "running")  # Original persisted fact retained.
        self.assertEqual(record["runner_liveness"]["status"], "not_running")
        self.assertTrue(record["runner_liveness"]["requires_attention"])
        self.assertFalse(record["runner_liveness"]["automatic_write_replay"])
        self.assertFalse(stopped["runner_observation"]["workspace_lock_held"])
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue((path.parent / "sources.json").is_file())

    def test_killed_preparing_runner_is_not_reported_as_active(self):
        self.init()
        asset = self.base / "original.mov"
        asset.write_bytes(b"Owner source fixture; staging not yet started")
        process, sid = self.start_blocked_fixture_runner("preparing", asset)
        path = self.root / "sessions" / sid / "status.json"
        original_status = path.read_bytes()
        active = studio.workspace_status(self.root)["sessions"][0]
        self.assertEqual(active["state"], "preparing")
        self.assertEqual(active["runner_liveness"]["status"], "active")
        process.kill()
        process.wait(timeout=10)
        stopped = studio.workspace_status(self.root)["sessions"][0]
        self.assertEqual(stopped["state"], "preparing")
        self.assertEqual(stopped["runner_liveness"]["status"], "not_running")
        self.assertEqual(path.read_bytes(), original_status)
        self.assertEqual(asset.read_bytes(), b"Owner source fixture; staging not yet started")

    def test_new_locked_session_does_not_make_old_orphan_look_active(self):
        from studio_next import native_editor_session
        self.init()
        first, old_sid = self.start_blocked_fixture_runner()
        first.kill()
        first.wait(timeout=10)
        old_path = self.root / "sessions" / old_sid / "status.json"
        old_bytes = old_path.read_bytes()
        second, new_sid = self.start_blocked_fixture_runner()
        self.assertNotEqual(old_sid, new_sid)
        report = studio.workspace_status(self.root)
        records = {r["session_id"]: r for r in report["sessions"]}
        self.assertEqual(records[old_sid]["runner_liveness"]["status"], "not_running")
        self.assertEqual(records[new_sid]["runner_liveness"]["status"], "active")
        self.assertEqual(report["runner_observation"]["bound_session_id"], new_sid)
        self.assertEqual(old_path.read_bytes(), old_bytes)
        # The status probe cannot release or replace the actual editing lock.
        fixture = AsyncMock()
        with patch.object(studio, "doctor", return_value={"ready": True}), \
                patch.object(native_editor_session, "run_native_session", fixture), \
                self.assertRaisesRegex(ValueError, "already running"):
            studio.run_workspace(self.root, brief="Must not start a competing model")
        fixture.assert_not_awaited()
        self.assertIsNone(second.poll())

    def test_stale_binding_during_new_owner_transition_never_revives_old_session(self):
        import fcntl
        self.init()
        old, new = "a" * 24, "b" * 24
        for sid in (old, new):
            directory = self.root / "sessions" / sid
            directory.mkdir(mode=0o700)
            studio._write_status(directory, {"session_id": sid, "state": "preparing"})
            studio._write_new(directory / ".runner.lock", {})
        studio._write_new(self.root / ".run.lock", {"schema": 1, "session_id": old})
        # Reproduce the tiny real acquisition transition: a new process owns
        # the workspace + its session lock, before replacing the stale binding.
        with open(self.root / ".run.lock") as workspace_lock, \
                open(self.root / "sessions" / new / ".runner.lock") as session_lock:
            fcntl.flock(workspace_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(session_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            records = {r["session_id"]: r for r in studio.workspace_status(self.root)["sessions"]}
        self.assertEqual(records[old]["runner_liveness"]["status"], "not_running")
        self.assertEqual(records[new]["runner_liveness"]["status"], "unknown")

    def test_unbound_live_workspace_lock_is_unknown_not_a_false_active_session(self):
        import fcntl
        self.init()
        session = self.root / "sessions" / ("a" * 24)
        session.mkdir(mode=0o700)
        saved = {"session_id": session.name, "state": "running"}
        studio._write_status(session, saved)
        with open(self.root / ".run.lock", "x", opener=lambda p, f:
                  os.open(p, f, 0o600)) as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record = studio.workspace_status(self.root)["sessions"][0]
        self.assertEqual(record["runner_liveness"]["status"], "unknown")
        self.assertEqual(json.loads((session / "status.json").read_text()), saved)

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
