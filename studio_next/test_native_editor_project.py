"""Project-selection isolation and failure custody; no neural claims."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from studio_next.native_editor_project import open_selected_native_project


def result(value):
    return {'isError': False, 'content': [{'type': 'text', 'text': json.dumps(value)}]}


class SelectedProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.selected = self.root / 'chosen'
        self.selected.mkdir()
        (self.selected / 'project.comfystudio').write_text('{}')
        self.receipt = self.root / 'setup.jsonl'
        self.session = type('Session', (), {})()
        self.session.call_tool = AsyncMock()
        self.grants = {'open_project': 'write', 'get_project': 'read'}

    def run_setup(self):
        with patch('studio_next.native_editor_project.native_content_diagnostics_source_verified', return_value=True):
            return asyncio.run(open_selected_native_project(self.session,
                project=self.selected, source=self.root, projects_root=self.root,
                grants=self.grants, receipt_path=self.receipt))

    def test_selected_project_is_opened_once_then_independently_read_back(self):
        self.session.call_tool.side_effect = [result({'success': True, 'action': 'open_project'}),
            result({'project': {'path': str(self.selected)}})]
        summary = self.run_setup()
        self.assertTrue(summary['active_project_identity_verified'])
        self.assertFalse(summary['model_selected_action'])
        self.assertEqual(self.session.call_tool.await_args_list[0].args,
            ('open_project', {'projectPath': str(self.selected), 'previewOnly': False}))
        self.assertEqual(self.session.call_tool.await_args_list[1].args, ('get_project', {}))
        events = [json.loads(x) for x in self.receipt.read_text().splitlines()]
        self.assertEqual([e['phase'] for e in events],
            ['open_submitted', 'open_acknowledged', 'active_project_verified'])
        with self.assertRaises(FileExistsError):
            self.run_setup()
        self.assertEqual(self.session.call_tool.await_count, 2)

    def test_wrong_project_readback_never_starts_editing_or_reopens(self):
        self.session.call_tool.side_effect = [result({'success': True, 'action': 'open_project'})] + [
            result({'project': {'path': str(self.root / 'wrong')}})] * 10
        with patch('studio_next.native_editor_project.asyncio.sleep', new=AsyncMock()), \
                self.assertRaisesRegex(RuntimeError, 'differs'):
            self.run_setup()
        names = [c.args[0] for c in self.session.call_tool.await_args_list]
        self.assertEqual(names, ['open_project'] + ['get_project'] * 10)
        self.assertNotIn('active_project_verified', self.receipt.read_text())

    def test_uncertain_open_is_not_replayed_and_submission_survives(self):
        self.session.call_tool.side_effect = TimeoutError('fixture uncertain open')
        with self.assertRaises(TimeoutError):
            self.run_setup()
        self.assertEqual(self.session.call_tool.await_count, 1)
        self.assertEqual(json.loads(self.receipt.read_text())['phase'], 'open_submitted')

    def test_missing_grant_or_unattested_source_never_dispatches(self):
        del self.grants['open_project']
        with self.assertRaises(ValueError):
            self.run_setup()
        self.session.call_tool.assert_not_awaited()
        self.assertFalse(self.receipt.exists())
        self.grants['open_project'] = 'write'
        with patch('studio_next.native_editor_project.native_content_diagnostics_source_verified', return_value=False), \
                self.assertRaises(ValueError):
            asyncio.run(open_selected_native_project(self.session,
                project=self.selected, source=self.root, projects_root=self.root,
                grants=self.grants, receipt_path=self.receipt))
        self.session.call_tool.assert_not_awaited()

    def test_native_session_never_starts_controller_when_selected_identity_fails(self):
        from contextlib import asynccontextmanager
        from unittest.mock import MagicMock
        from studio_next import native_editor_session as native
        config = self.root / "host.json"
        config.write_text(json.dumps({"projects_root": str(self.root),
            "allowed_tools": self.grants, "allowed_access": ["read", "write"]}))
        brief = self.root / "brief.txt"
        brief.write_text("Revise my selected project")
        args = native.build_parser().parse_args([
            "--source", str(self.root), "--config", str(config),
            "--state", str(self.root), "--brief-file", str(brief),
            "--receipt", str(self.root / "journal.jsonl"), "--model-id", "fixture",
            "--project", str(self.selected)])
        @asynccontextmanager
        async def transport(*args):
            yield (None, None)
        session = MagicMock()
        session.initialize = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        gateway = MagicMock()
        gateway.refresh = AsyncMock()
        with patch.object(native, "stdio_client", transport), \
                patch.object(native, "ClientSession", return_value=session), \
                patch.object(native, "native_decision_model"), \
                patch.object(native, "CapabilityGateway", return_value=gateway), \
                patch.object(native, "CapabilityGatewayMcpSession"), \
                patch.object(native, "NativeCreativeControl") as controller, \
                patch("studio_next.native_editor_project.open_selected_native_project",
                      new=AsyncMock(side_effect=RuntimeError("wrong selected project"))) as setup:
            with self.assertRaisesRegex(RuntimeError, "wrong selected"):
                asyncio.run(native.run_native_session(args))
            controller.assert_not_called()
            setup.assert_awaited_once()
            self.assertEqual(setup.await_args.kwargs["project"], self.selected)

    def test_preview_or_error_receipt_does_not_authorize_model_editing(self):
        for value in ({'previewOnly': True, 'action': 'open_project'}, {'success': False}):
            self.receipt.unlink(missing_ok=True)
            self.session.call_tool.reset_mock()
            self.session.call_tool.side_effect = [result(value)]
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.run_setup()
            self.assertEqual(self.session.call_tool.await_count, 1)
