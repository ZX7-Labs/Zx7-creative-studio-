"""Project-selection isolation and failure custody; no neural claims."""
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from studio_next.native_editor_project import capture_render_project, open_selected_native_project
from studio_next.native_render_evidence import DESTINATION_FIELD, SCOPE_FIELD, timeline_scope_digest


def result(value):
    return {'isError': False, 'content': [{'type': 'text', 'text': json.dumps(value)}]}


class RenderSnapshotTests(unittest.TestCase):
    def test_captures_exact_saved_bytes_inside_the_owner_root_without_replacing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            projects, snapshots = root / "projects", root / "snapshots"
            project = projects / "film"
            project.mkdir(parents=True)
            snapshots.mkdir()
            doc = {"currentTimelineId": "film-timeline", "modified": "version-1",
                   "assets": [{"id": "media-1", "name": "source.wav",
                               "path": "assets/audio/source.wav", "size": 32}],
                   "timelines": [{"id": "film-timeline", "clips": [
                       {"id": "clip-1", "type": "audio", "assetId": "media-1"}]}]}
            media_path = project / "assets" / "audio" / "source.wav"
            media_path.parent.mkdir(parents=True)
            media_path.write_bytes(b"A" * 32)
            original = json.dumps(doc, sort_keys=True).encode("utf-8")
            (project / "project.comfystudio").write_bytes(original)
            response = {"projectPath": str(project),
                        "settings": {"bitrateKbps": 8000, "audioBitrateKbps": 192, "preset": "medium"},
                        "result": {"options": {"rangeStart": 0, "rangeEnd": 6, "crf": 18}}}
            binding = {DESTINATION_FIELD: "a" * 64,
                       SCOPE_FIELD: timeline_scope_digest(str(project), "film-timeline")}
            identity = (str(project), "version-1")
            digest, options, source_media = capture_render_project(
                projects, snapshots, response, binding, identity)
            self.assertEqual(digest, hashlib.sha256(original).hexdigest())
            self.assertRegex(source_media, r"^[0-9a-f]{64}$")
            snapshot = snapshots / ("a" * 64 + ".comfystudio")
            self.assertEqual(snapshot.read_bytes(), original)
            with self.assertRaises(FileExistsError):
                capture_render_project(projects, snapshots, response, binding, identity)
            with self.assertRaisesRegex(ValueError, "outside"):
                capture_render_project(projects, snapshots, {"projectPath": str(root)}, binding, identity)
            with self.assertRaisesRegex(ValueError, "timeline differs"):
                capture_render_project(projects, snapshots, response, {
                    DESTINATION_FIELD: "b" * 64, SCOPE_FIELD: "c" * 64}, identity)
            with self.assertRaisesRegex(ValueError, "last acknowledged save"):
                capture_render_project(projects, snapshots, response, {
                    **binding, DESTINATION_FIELD: "d" * 64}, (str(project), "wrong-version"))
            changed = {**response, "settings": {**response["settings"], "bitrateKbps": 4000}}
            _, changed_options, same_media = capture_render_project(
                projects, snapshots, changed, {
                    **binding, DESTINATION_FIELD: "e" * 64}, identity)
            self.assertNotEqual(options, changed_options)
            self.assertEqual(source_media, same_media)
            media_path.write_bytes(b"Z" * 32)
            _, _, substituted = capture_render_project(projects, snapshots, response, {
                **binding, DESTINATION_FIELD: "f" * 64}, identity)
            self.assertNotEqual(source_media, substituted)

    def test_actual_native_autosave_timestamps_cannot_overwrite_model_approved_content(self):
        # In genuine model #45735804964 the editor updated two volatile
        # modified fields during lengthy read-only decisions after save.
        # The save and render must still agree on ALL creative content and
        # source bytes. A changed clip, swapped media or sibling document
        # must remain rejected; never authorize a second native action.
        from studio_next.native_editor_project import capture_acknowledged_save_identity
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            projects, snapshots = root / "projects", root / "snapshots"
            project = projects / "film"
            project.mkdir(parents=True)
            snapshots.mkdir()
            media = project / "assets/audio/source.wav"
            media.parent.mkdir(parents=True)
            media.write_bytes(b"Q" * 32)
            document = {
                "name": "film", "modified": "t1",
                "currentTimelineId": "timeline-one",
                "assets": [{"id": "asset-audio", "name": "source.wav",
                            "path": "assets/audio/source.wav", "size": 32}],
                "timelines": [{"id": "timeline-one", "modified": "t1",
                               "clips": [{"id": "clip-one", "type": "audio",
                                          "assetId": "asset-audio",
                                          "startTime": 0}]}],
            }
            file = project / "project.comfystudio"
            def persist():
                file.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
            persist()
            source_identity = capture_acknowledged_save_identity(
                projects, snapshots, {"path": str(project), "modified": "t1"})
            self.assertEqual(source_identity[:2], (str(project), "t1"))
            self.assertEqual(len(source_identity), 4)
            self.assertTrue(all(len(value) == 64 for value in source_identity[2:]))
            response = {"projectPath": str(project),
                        "settings": {"bitrateKbps": 8000,
                                     "audioBitrateKbps": 192, "preset": "medium"},
                        "result": {"options": {"rangeStart": 0,
                                                "rangeEnd": 6, "crf": 18}}}
            binding = {DESTINATION_FIELD: "a" * 64,
                       SCOPE_FIELD: timeline_scope_digest(str(project), "timeline-one")}
            document["modified"] = "t3"
            document["timelines"][0]["modified"] = "t2"
            persist()
            project_sha, options_sha, media_sha = capture_render_project(
                projects, snapshots, response, binding, source_identity)
            self.assertEqual(project_sha, hashlib.sha256(file.read_bytes()).hexdigest())
            self.assertEqual(media_sha, source_identity[3])
            self.assertRegex(options_sha, r"^[a-f0-9]{64}$")
            with self.assertRaisesRegex(ValueError, "last acknowledged save"):
                capture_render_project(projects, snapshots, response,
                                       {**binding, DESTINATION_FIELD: "b" * 64},
                                       (str(project), "t1"))
            # Even a silent same-size source substitution must be refused.
            media.write_bytes(b"Z" * 32)
            with self.assertRaisesRegex(ValueError, "media"):
                capture_render_project(projects, snapshots, response,
                                       {**binding, DESTINATION_FIELD: "c" * 64},
                                       source_identity)
            media.write_bytes(b"Q" * 32)
            document["timelines"][0]["clips"][0]["startTime"] = 1
            persist()
            with self.assertRaisesRegex(ValueError, "content"):
                capture_render_project(projects, snapshots, response,
                                       {**binding, DESTINATION_FIELD: "d" * 64},
                                       source_identity)
            with self.assertRaisesRegex(ValueError, "owner-selected"):
                capture_acknowledged_save_identity(
                    projects, snapshots,
                    {"path": str(project), "modified": "t3"},
                    expected_project=projects / "another")

    def test_owner_selected_existing_project_does_not_capture_another_native_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            projects, snapshots = root / "projects", root / "snapshots"
            selected, other = projects / "selected", projects / "other"
            selected.mkdir(parents=True)
            other.mkdir()
            snapshots.mkdir()
            (selected / "project.comfystudio").write_text(
                '{"currentTimelineId":"selected-timeline","modified":"v1",'
                '"assets":[],"timelines":[{"id":"selected-timeline","clips":[{"id":"title"}]}]}')
            (other / "project.comfystudio").write_text(
                '{"currentTimelineId":"other-timeline","modified":"v1",'
                '"assets":[],"timelines":[{"id":"other-timeline","clips":[{"id":"title"}]}]}')
            response = {
                "projectPath": str(other),
                "settings": {"bitrateKbps": 8000, "audioBitrateKbps": 192, "preset": "medium"},
                "result": {"options": {"rangeStart": 0, "rangeEnd": 6, "crf": 18}},
            }
            binding = {
                DESTINATION_FIELD: "b" * 64,
                SCOPE_FIELD: timeline_scope_digest(str(other), "other-timeline"),
            }
            with self.assertRaisesRegex(ValueError, "owner-selected"):
                capture_render_project(
                    projects, snapshots, response, binding, (str(other), "v1"),
                    expected_project=selected)
            self.assertEqual(list(snapshots.iterdir()), [])
            self.assertIn("selected-timeline",
                          (selected / "project.comfystudio").read_text())

            # Positive control: the exact selected native source is accepted,
            # and the render snapshot is an immutable copy, not a replacement.
            selected_saved = (selected / "project.comfystudio").read_bytes()
            same_project = {**response, "projectPath": str(selected)}
            correct_scope = {
                DESTINATION_FIELD: "c" * 64,
                SCOPE_FIELD: timeline_scope_digest(str(selected), "selected-timeline"),
            }
            snapshot_sha, _, media_sha = capture_render_project(
                projects, snapshots, same_project, correct_scope,
                (str(selected), "v1"), expected_project=selected)
            self.assertEqual(snapshot_sha, hashlib.sha256(selected_saved).hexdigest())
            self.assertRegex(media_sha, r"^[0-9a-f]{64}$")
            self.assertEqual(
                (snapshots / ("c" * 64 + ".comfystudio")).read_bytes(),
                selected_saved)
            self.assertEqual((selected / "project.comfystudio").read_bytes(),
                             selected_saved)


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

    def test_owner_selected_native_av_snapshot_attests_root_before_model(self):
        """The same source-owning renderer callback works when fresh=False.

        A real hosted trial formerly raised UnboundLocalError at
        physical_capture(project_root) before it could open the selected
        saved native document. Test the production entry and fail closed.
        """
        from contextlib import asynccontextmanager
        from unittest.mock import MagicMock
        from studio_next import native_editor_session as native

        config = self.root / "host-snapshot.json"
        config.write_text(json.dumps({
            "projects_root": str(self.root),
            "allowed_access": ["read", "write"],
            "allowed_tools": {
                "open_project": "write", "get_project": "read",
                "save_project": "write", "set_clip_audio": "write",
            },
            "verify_native_exports": True,
        }))
        brief = self.root / "brief-snapshot.txt"
        brief.write_text("Independently revise my existing native A/V project")
        args = native.build_parser().parse_args([
            "--source", str(self.root), "--config", str(config),
            "--state", str(self.root), "--brief-file", str(brief),
            "--receipt", str(self.root / "selected-av-journal.jsonl"),
            "--model-id", "safe-offline-fixture", "--project", str(self.selected),
            "--record-av-project-snapshots",
            "--evaluation-evidence", "reviewed-av-revision",
        ])
        @asynccontextmanager
        async def transport(*_):
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
                patch.object(native, "CombinedCapabilityMcpSession"), \
                patch.object(native, "NativeCreativeControl") as controller, \
                patch("studio_next.native_editor_project.open_selected_native_project",
                      new=AsyncMock(side_effect=RuntimeError("selected-root-reached"))) as setup:
            with self.assertRaisesRegex(RuntimeError, "selected-root-reached"):
                asyncio.run(native.run_native_session(args))
            setup.assert_awaited_once()
            self.assertEqual(setup.await_args.kwargs["project"], self.selected)
            self.assertEqual(setup.await_args.kwargs["projects_root"], str(self.root))
            controller.assert_not_called()
        self.assertTrue((self.root / "av-project-snapshots").is_dir())

    def test_native_model_can_choose_public_references_only_with_owner_consent(self):
        from contextlib import asynccontextmanager
        from types import SimpleNamespace
        from studio_next import native_editor_session as native
        from studio_next.test_native_creative_control import ScriptedModel, decision

        class Editor:
            async def initialize(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def list_tools(self):
                return SimpleNamespace(tools=[SimpleNamespace(name="update_text_clip",
                    description="Edit a native title", input_schema={"type": "object",
                        "properties": {"clipId": {"type": "string"}}})])

            async def call_tool(self, name, arguments):
                edits.append((name, arguments))
                return result({"success": True, "action": name})

        class Research:
            def web(self, **arguments):
                queries.append(arguments)
                return {"results": [{"source_page": "https://example.org/reference"}],
                        "import_authorized": False}

            assets = studies = web

        @asynccontextmanager
        async def transport(*_):
            yield (None, None)

        config = self.root / "host.json"
        config.write_text(json.dumps({"projects_root": str(self.root),
            "allowed_tools": {"update_text_clip": "write"}, "allowed_access": ["write"]}))
        brief = self.root / "brief.txt"
        brief.write_text("Develop an original visual direction, then revise the title")
        for provider in ("local", "nvidia"):
            for enabled in (False, True):
                with self.subTest(provider=provider, enabled=enabled):
                    queries, edits = [], []
                    flags = ["--allow-public-research"] if enabled else []
                    args = native.build_parser().parse_args([
                        "--source", str(self.root), "--config", str(config), "--state", str(self.root),
                        "--brief-file", str(brief), "--receipt", str(self.root / f"{provider}-{enabled}.jsonl"),
                        "--model-id", "fixture", "--provider", provider, "--indexed-catalog", *flags])
                    actions = []
                    if enabled:
                        actions.extend([decision("search", query="research_web", limit=1),
                            decision("invoke", tool="research_web", inputs={"query": "public motion references", "language": "ja"})])
                    actions.extend([decision("search", query="update_text_clip", limit=1),
                                    decision("invoke", tool="update_text_clip", inputs={"clipId": "title"}),
                                    decision("finish", summary="Fixture only")])
                    model = ScriptedModel(actions)
                    with patch.object(native, "stdio_client", transport), \
                            patch.object(native, "ClientSession", return_value=Editor()), \
                            patch.object(native, "native_decision_model", return_value=model), \
                            patch("studio_next.creative_research_mcp.CreativeResearch", return_value=Research()) as factory:
                        outcome = asyncio.run(native.run_native_session(args))
                    self.assertEqual(outcome["status"], "model_finished_unverified")
                    self.assertEqual(outcome["public_research_permitted_by_host"], enabled)
                    self.assertEqual(factory.call_count, int(enabled))
                    if enabled:
                        factory.assert_called_once_with(searxng_url=None)
                    self.assertEqual(queries, [{"query": "public motion references", "language": "ja"}] if enabled else [])
                    self.assertEqual(edits, [("update_text_clip", {"clipId": "title"})])
                    self.assertEqual(outcome["model_selected_write_receipts"], 1)
                    if enabled:
                        self.assertIn("research_web", model.observed[1]["selectable_native_tools"])
                        self.assertIn("https://example.org/reference", model.observed[2]["last_native_result_texts"][0])
                    self.assertNotIn("public motion references", args.receipt.read_text())

    def test_research_budget_and_provider_failure_leave_no_asset_or_write(self):
        from studio_next.creative_research import CreativeResearchError
        from studio_next.creative_research_mcp import CreativeResearchMcpSession

        class Research:
            calls = 0

            def studies(self, **_):
                self.calls += 1
                raise CreativeResearchError("private traceback")

            assets = studies

        async def check():
            research = Research()
            session = CreativeResearchMcpSession(allow_public_research=True, research_client=research, max_calls=1)
            for status in ("provider_unavailable_or_refused", "call_budget_exhausted"):
                response = await session.call_tool("research_studies", {"query": "public"})
                body = json.loads(response.content[0].text)
                self.assertEqual(body["status"], status)
                self.assertEqual(body["results"], [])
                self.assertFalse(body["import_authorized"])
                self.assertNotIn("private traceback", response.content[0].text)
            self.assertEqual(research.calls, 1)

        asyncio.run(check())

    def test_preview_or_error_receipt_does_not_authorize_model_editing(self):
        for value in ({'previewOnly': True, 'action': 'open_project'}, {'success': False}):
            self.receipt.unlink(missing_ok=True)
            self.session.call_tool.reset_mock()
            self.session.call_tool.side_effect = [result(value)]
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.run_setup()
            self.assertEqual(self.session.call_tool.await_count, 1)
