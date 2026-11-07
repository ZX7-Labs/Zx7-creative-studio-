"""Interop tests use the official SDK and a real local HTTP editor fixture."""
import asyncio
import base64
import hashlib
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from studio_next.body_editor_client import LocalEditorClient

HAS_MCP = importlib.util.find_spec("mcp") is not None
if HAS_MCP:
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.shared.memory import create_client_server_memory_streams
    from studio_next.body_editor_mcp import create_editor_server


SCHEMA = {"type": "object", "properties": {
    "clipId": {"type": "string"},
    "text": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
    "required": ["clipId"], "additionalProperties": False}
TOOLS = [
    {"name": "get_project", "description": "Native project",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "update_text_clip", "description": "Native text", "inputSchema": SCHEMA},
    {"name": "install_workflow_setup", "inputSchema": {"type": "object"}},
]


@unittest.skipUnless(HAS_MCP, "Install the editor extra to test the official MCP protocol")
class EditorMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.requests = []
        self.tools = TOOLS
        self.native_fail = False
        self.delay = 0
        self.active = 0
        self.max_active = 0
        self.hold = None
        self.entered = threading.Event()
        self.state_lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append(request)
                if request["method"] == "tools/list":
                    result = {"tools": owner.tools}
                else:
                    with owner.state_lock:
                        owner.active += 1
                        owner.max_active = max(owner.max_active, owner.active)
                    try:
                        if owner.hold is not None and request["params"]["arguments"].get("clipId") == "a":
                            owner.entered.set()
                            owner.hold.wait(timeout=3)
                        time.sleep(owner.delay)
                        result = {"content": [{"type": "text", "text": "native"}],
                                  "_meta": {"native": "preserved"}, "isError": owner.native_fail}
                    finally:
                        with owner.state_lock:
                            owner.active -= 1
                body = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.http.daemon_threads = True
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.http.server_port}/mcp"
        self.client = LocalEditorClient(self.endpoint, allowed_tools={
            "get_project": "read", "update_text_clip": "write"})

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()

    async def with_session(self, check, *, access=frozenset({"read", "write"}),
                           export_verifier=None, frame_observer=None, audio_observer=None,
                           audio_timeline_observer=None):
        server = create_editor_server(self.client, allowed_access=access,
                                      export_verifier=export_verifier,
                                      frame_observer=frame_observer,
                                      audio_observer=audio_observer,
                                      audio_timeline_observer=audio_timeline_observer)
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            async with anyio.create_task_group() as group:
                group.start_soon(server.run, *server_streams, server.create_initialization_options())
                async with ClientSession(*client_streams) as session:
                    await session.initialize()
                    await check(session)
                group.cancel_scope.cancel()

    async def test_native_schema_grants_and_write_pass_through_official_protocol(self):
        async def check(session):
            tools = (await session.list_tools()).tools
            self.assertEqual([tool.name for tool in tools], ["get_project", "update_text_clip"])
            self.assertEqual(tools[1].input_schema, SCHEMA)
            result = await session.call_tool("update_text_clip", {"clipId": "native", "text": "Revised"})
            self.assertFalse(result.is_error)
            self.assertEqual(result.content[0].text, "native")
            self.assertEqual(result.meta, {"native": "preserved"})
            self.assertEqual(self.requests[-1]["params"], {
                "name": "update_text_clip", "arguments": {"clipId": "native", "text": "Revised"}})
        await self.with_session(check)

    async def test_read_only_host_cannot_advertise_or_call_writes(self):
        async def check(session):
            self.assertEqual([tool.name for tool in (await session.list_tools()).tools], ["get_project"])
            result = await session.call_tool("update_text_clip", {"clipId": "x"})
            self.assertTrue(result.is_error)
            self.assertFalse(any(row["method"] == "tools/call" for row in self.requests))
        await self.with_session(check, access=frozenset({"read"}))

    async def test_unknown_tools_and_invalid_arguments_never_reach_editor(self):
        async def check(session):
            for name, args in [("install_workflow_setup", {}), ("update_text_clip", {}),
                               ("update_text_clip", {"clipId": 2}),
                               ("update_text_clip", {"clipId": "x", "allowed_access": ["write"]})]:
                result = await session.call_tool(name, args)
                self.assertTrue(result.is_error)
            self.assertFalse(any(row["method"] == "tools/call" for row in self.requests))
            self.assertFalse((await session.call_tool("get_project", {})).is_error)
        await self.with_session(check)

    async def test_upstream_undeclared_native_parameters_never_reach_stateful_editor(self):
        import copy
        self.tools=copy.deepcopy(TOOLS)
        self.tools[1]["inputSchema"].pop("additionalProperties")
        async def check(session):
            advertised=[tool for tool in (await session.list_tools()).tools
                        if tool.name=="update_text_clip"][0].input_schema
            self.assertNotIn("additionalProperties",advertised)
            forbidden=await session.call_tool("update_text_clip",{
                "clipId":"real", "fakePermission":"write"})
            self.assertTrue(forbidden.is_error)
            self.assertFalse(any(row["method"]=="tools/call" for row in self.requests))
            permitted=await session.call_tool("update_text_clip",{
                "clipId":"real","text":None})
            self.assertFalse(permitted.is_error)
            self.assertEqual(sum(row["method"]=="tools/call" for row in self.requests),1)
        await self.with_session(check)

    async def test_nested_original_artistic_schema_not_accidentally_sealed(self):
        import copy
        self.tools=copy.deepcopy(TOOLS)
        self.tools[1]["inputSchema"]={
            "type":"object",
            "required":["clipId","visual"],
            "properties":{
                "clipId":{"type":"string"},
                "visual":{"type":"object","properties":{
                    "layer":{"type":"string"}}},
            },
        }
        async def check(session):
            allowed=await session.call_tool("update_text_clip",{
                "clipId":"real",
                "visual":{"layer":"title","original_artist_shader_parameters":{
                    "contrast":0.77,"custom":[1,2,3]}}})
            self.assertFalse(allowed.is_error)
            self.assertEqual(sum(row["method"]=="tools/call" for row in self.requests),1)
        await self.with_session(check)

    async def test_native_tool_error_is_preserved_and_session_remains_usable(self):
        async def check(session):
            self.native_fail = True
            result = await session.call_tool("get_project", {})
            self.assertTrue(result.is_error)
            self.assertEqual(result.meta, {"native": "preserved"})
            self.assertEqual(result.content[0].text, "native")
            self.native_fail = False
            self.assertFalse((await session.call_tool("get_project", {})).is_error)
        await self.with_session(check)

    async def test_native_calls_are_serialized(self):
        self.delay = .05
        async def check(session):
            await asyncio.gather(session.call_tool("update_text_clip", {"clipId": "a"}),
                                 session.call_tool("update_text_clip", {"clipId": "b"}))
            self.assertEqual(self.max_active, 1)
        await self.with_session(check)

    async def test_schema_id_and_local_defs_validate_without_schema_network_access(self):
        schema = {"$id": self.endpoint + "/schema", "type": "object",
                  "$defs": {"clip": {"type": "string"}},
                  "properties": {"clipId": {"$ref": "#/$defs/clip"}},
                  "required": ["clipId"]}
        self.tools = [TOOLS[0], {**TOOLS[1], "inputSchema": schema}]
        async def check(session):
            self.assertFalse((await session.call_tool("update_text_clip", {"clipId": "x"})).is_error)
            self.assertTrue((await session.call_tool("update_text_clip", {"clipId": 3})).is_error)
            self.assertEqual(len([row for row in self.requests if row["method"] == "tools/call"]), 1)
        await self.with_session(check)

    async def test_cancelled_queued_write_is_not_later_applied(self):
        self.hold = threading.Event()
        async def check(session):
            scopes, done = {}, {name: anyio.Event() for name in ("a", "b")}
            async def write(name):
                with anyio.CancelScope() as scope:
                    scopes[name] = scope
                    await session.call_tool("update_text_clip", {"clipId": name})
                done[name].set()
            try:
                async with anyio.create_task_group() as group:
                    group.start_soon(write, "a")
                    self.assertTrue(await anyio.to_thread.run_sync(lambda: self.entered.wait(timeout=2)))
                    group.start_soon(write, "b")
                    while "b" not in scopes:
                        await anyio.sleep(.001)
                    await anyio.sleep(.03)
                    scopes["b"].cancel()
                    await done["b"].wait()
                    await anyio.sleep(.03)
                    self.hold.set()
                    await done["a"].wait()
                    await anyio.sleep(.03)
                calls = [row for row in self.requests if row["method"] == "tools/call"]
                self.assertEqual([row["params"]["arguments"]["clipId"] for row in calls], ["a"])
            finally:
                self.hold.set()
        await self.with_session(check)

    async def test_cancelled_inflight_write_keeps_lock_until_native_response(self):
        self.hold = threading.Event()
        async def check(session):
            scopes, done = {}, {name: anyio.Event() for name in ("a", "b")}
            async def write(name):
                with anyio.CancelScope() as scope:
                    scopes[name] = scope
                    await session.call_tool("update_text_clip", {"clipId": name})
                done[name].set()
            try:
                async with anyio.create_task_group() as group:
                    group.start_soon(write, "a")
                    self.assertTrue(await anyio.to_thread.run_sync(lambda: self.entered.wait(timeout=2)))
                    scopes["a"].cancel()
                    await done["a"].wait()
                    group.start_soon(write, "b")
                    await anyio.sleep(.05)
                    calls = [row for row in self.requests if row["method"] == "tools/call"]
                    self.assertEqual(len(calls), 1)
                    self.hold.set()
                    await done["b"].wait()
                self.assertEqual(self.max_active, 1)
            finally:
                self.hold.set()
        await self.with_session(check)

    async def test_export_verifier_is_read_only_opt_in_and_no_native_rpc(self):
        observed = []
        def verifier(path, expected=None):
            observed.append((path, expected))
            if path != "/trusted/export.mp4":
                raise ValueError("outside selected export")
            return {"physical_export_verified": True, "artistic_quality_approved": False,
                    "native_export_sha256": "1" * 64}

        async def check(session):
            catalog = {tool.name: tool for tool in (await session.list_tools()).tools}
            self.assertIn("zx7_verify_native_export", catalog)
            good = await session.call_tool("zx7_verify_native_export", {
                "path": "/trusted/export.mp4", "expected": {"require_audio": True}})
            self.assertFalse(good.is_error)
            self.assertEqual(json.loads(good.content[0].text)["physical_export_verified"], True)
            self.assertEqual(observed, [("/trusted/export.mp4", {"require_audio": True})])
            for arguments in ({}, {"path": 12}, {"path": "/trusted/export.mp4", "expected": {"unknown": 1}},
                              {"path": "/etc/passwd"}):
                denied = await session.call_tool("zx7_verify_native_export", arguments)
                self.assertTrue(denied.is_error)
            self.assertFalse(any(x["method"] == "tools/call" for x in self.requests))
        await self.with_session(check, export_verifier=verifier)

        async def no_read(session):
            self.assertNotIn("zx7_verify_native_export", [
                tool.name for tool in (await session.list_tools()).tools])
            self.assertTrue((await session.call_tool("zx7_verify_native_export", {
                "path": "/trusted/export.mp4"})).is_error)
        await self.with_session(no_read, access=frozenset({"write"}), export_verifier=verifier)
        self.assertEqual(observed, [("/trusted/export.mp4", {"require_audio": True}),
                                    ("/etc/passwd", None)])

    async def test_a_frame_is_only_visible_after_its_exact_export_was_verified(self):
        observers = []
        def verifier(path, expected=None):
            if path != "/trusted/movie.mp4":
                raise ValueError("No authorized native export")
            return {"physical_export_verified": True, "native_export_sha256": "a" * 64}
        def observer(path, verified_sha256, at_seconds):
            observers.append((path, verified_sha256, at_seconds))
            png = b"verified-image"
            return png, {"export_sha256": verified_sha256,
                         "png_sha256": hashlib.sha256(png).hexdigest(),
                         "sampled_video_seconds_requested": at_seconds,
                         "human_or_artistic_quality_approved": False}

        async def check(session):
            names = [tool.name for tool in (await session.list_tools()).tools]
            self.assertIn("zx7_observe_verified_export_frame", names)
            self.assertTrue((await session.call_tool("zx7_observe_verified_export_frame", {
                "path": "/trusted/movie.mp4", "at_seconds": 0.5})).is_error)
            self.assertFalse((await session.call_tool("zx7_verify_native_export", {
                "path": "/trusted/movie.mp4"})).is_error)
            seen = await session.call_tool("zx7_observe_verified_export_frame", {
                "path": "/trusted/movie.mp4", "at_seconds": 0.5})
            self.assertFalse(seen.is_error)
            self.assertEqual(seen.content[1].type, "image")
            self.assertEqual(seen.content[1].mime_type, "image/png")
            self.assertEqual(observers, [("/trusted/movie.mp4", "a" * 64, 0.5)])
            self.assertTrue((await session.call_tool("zx7_observe_verified_export_frame", {
                "path": "/trusted/other.mp4", "at_seconds": 0.5})).is_error)
            self.assertTrue((await session.call_tool("zx7_observe_verified_export_frame", {
                "path": "/trusted/movie.mp4", "at_seconds": -1})).is_error)
            self.assertFalse(any(x["method"] == "tools/call" for x in self.requests))
        await self.with_session(check, export_verifier=verifier, frame_observer=observer)

    async def test_multiple_frame_observations_have_ordered_source_evidence(self):
        observed_times = []
        digest = "b" * 64
        def verifier(path, expected=None):
            self.assertEqual(path, "/trusted/source.mp4")
            return {"physical_export_verified": True, "native_export_sha256": digest}

        def observer(path, verified_sha256, at_seconds):
            self.assertEqual((path, verified_sha256), ("/trusted/source.mp4", digest))
            observed_times.append(at_seconds)
            png = b"physical-image-" + repr(at_seconds).encode()
            return png, {"export_sha256": digest,
                         "png_sha256": hashlib.sha256(png).hexdigest(),
                         "sampled_video_seconds_requested": at_seconds,
                         "human_or_artistic_quality_approved": False}

        async def check(session):
            name = "zx7_observe_verified_export_samples"
            listed = {tool.name: tool for tool in (await session.list_tools()).tools}
            self.assertIn(name, listed)
            query = {"path": "/trusted/source.mp4", "at_seconds": [0.25, 1.25, 2.25]}
            self.assertTrue((await session.call_tool(name, query)).is_error)
            self.assertFalse((await session.call_tool(
                "zx7_verify_native_export", {"path": query["path"]})).is_error)
            result = await session.call_tool(name, query)
            self.assertFalse(result.is_error, result)
            self.assertEqual(len(result.content), 4)
            receipt = json.loads(result.content[0].text)
            self.assertEqual(receipt["kind"], "verified_native_editor_selected_frames")
            self.assertEqual(receipt["export_sha256"], digest)
            self.assertFalse(receipt["continuous_motion_or_audio_proven"])
            self.assertFalse(receipt["human_or_artistic_quality_approved"])
            self.assertEqual([s["sampled_video_seconds_requested"] for s in receipt["samples"]],
                             query["at_seconds"])
            for block, sample in zip(result.content[1:], receipt["samples"]):
                self.assertEqual(block.type, "image")
                self.assertEqual(block.mime_type, "image/png")
                self.assertEqual(hashlib.sha256(base64.b64decode(block.data)).hexdigest(),
                                 sample["png_sha256"])
            self.assertEqual(observed_times, query["at_seconds"])
            for times in ([1, 1], [3, 2], [1], [0, 1, 2, 3, 4]):
                denied = await session.call_tool(name, {
                    "path": query["path"], "at_seconds": times})
                self.assertTrue(denied.is_error, times)
            self.assertEqual(observed_times, query["at_seconds"])
            self.assertFalse(any(row["method"] == "tools/call" for row in self.requests))
        await self.with_session(check, export_verifier=verifier, frame_observer=observer)

        async def no_read(session):
            self.assertNotIn("zx7_observe_verified_export_samples",
                             [t.name for t in (await session.list_tools()).tools])
        await self.with_session(no_read, access=frozenset({"write"}),
                                export_verifier=verifier, frame_observer=observer)

    async def test_multi_frame_failure_never_returns_partial_images_and_drops_proof(self):
        def verifier(path, expected=None):
            return {"physical_export_verified": True, "native_export_sha256": "c" * 64}
        def observer(path, verified_sha256, at_seconds):
            if at_seconds == 2:
                raise ValueError("Actual decoder rejected second frame")
            png = b"first-frame"
            return png, {"export_sha256": verified_sha256,
                         "png_sha256": hashlib.sha256(png).hexdigest(),
                         "sampled_video_seconds_requested": at_seconds}

        async def check(session):
            self.assertFalse((await session.call_tool(
                "zx7_verify_native_export", {"path": "/trusted/movie.mp4"})).is_error)
            args = {"path": "/trusted/movie.mp4", "at_seconds": [1, 2]}
            failed = await session.call_tool("zx7_observe_verified_export_samples", args)
            self.assertTrue(failed.is_error)
            self.assertEqual(len(failed.content), 1)
            again = await session.call_tool("zx7_observe_verified_export_samples", args)
            self.assertTrue(again.is_error)
            self.assertIn("verify", again.content[0].text.lower())
        await self.with_session(check, export_verifier=verifier, frame_observer=observer)

    async def test_multi_frame_total_payload_limit_fails_closed(self):
        def verifier(path, expected=None):
            return {"physical_export_verified": True, "native_export_sha256": "d" * 64}
        def observer(path, verified_sha256, at_seconds):
            png = b"x" * (3 * 1024 * 1024)
            return png, {"export_sha256": verified_sha256,
                         "png_sha256": hashlib.sha256(png).hexdigest(),
                         "sampled_video_seconds_requested": at_seconds}

        async def check(session):
            self.assertFalse((await session.call_tool("zx7_verify_native_export",
                              {"path": "/trusted/movie.mp4"})).is_error)
            invalid = await session.call_tool("zx7_observe_verified_export_samples", {
                "path": "/trusted/movie.mp4", "at_seconds": [1, 2, 3]})
            self.assertTrue(invalid.is_error)
            self.assertEqual(len(invalid.content), 1)
            self.assertIn("oversized", invalid.content[0].text.lower())
        await self.with_session(check, export_verifier=verifier, frame_observer=observer)

    async def test_verified_native_audio_is_real_mcp_audio_content_not_only_a_metric(self):
        digest = "d" * 64
        wav_bytes = b"RIFF" + b"native-audio-wav-test" * 5
        heard = []
        def verifier(path, expected=None):
            self.assertEqual(path, "/trusted/audio-movie.mp4")
            return {"physical_export_verified": True, "native_export_sha256": digest}
        def observer(path, verified_sha256, start_seconds, duration_seconds):
            heard.append((path, verified_sha256, start_seconds, duration_seconds))
            return wav_bytes, {
                "kind": "verified_native_editor_bounded_audio_excerpt",
                "export_sha256": verified_sha256,
                "wav_sha256": hashlib.sha256(wav_bytes).hexdigest(),
                "requested_start_seconds": start_seconds,
                "requested_duration_seconds": duration_seconds,
                "full_film_listening_or_spatial_mix_verified": False,
                "human_or_artistic_quality_approved": False,
            }
        async def check(session):
            tool = "zx7_observe_verified_export_audio"
            catalog = {x.name for x in (await session.list_tools()).tools}
            self.assertIn(tool, catalog)
            query = {"path": "/trusted/audio-movie.mp4",
                     "start_seconds": .25, "duration_seconds": 1.25}
            self.assertTrue((await session.call_tool(tool, query)).is_error)
            self.assertFalse((await session.call_tool("zx7_verify_native_export", {
                "path": query["path"]})).is_error)
            result = await session.call_tool(tool, query)
            self.assertFalse(result.is_error, result)
            self.assertEqual(len(result.content), 2)
            self.assertEqual(result.content[1].type, "audio")
            self.assertEqual(result.content[1].mime_type, "audio/wav")
            self.assertEqual(base64.b64decode(result.content[1].data), wav_bytes)
            receipt = json.loads(result.content[0].text)
            self.assertFalse(receipt["full_film_listening_or_spatial_mix_verified"])
            self.assertEqual(receipt["wav_sha256"], hashlib.sha256(wav_bytes).hexdigest())
            self.assertEqual(heard, [(query["path"], digest, .25, 1.25)])
            for invalid in (
                {"path": query["path"], "start_seconds": -1, "duration_seconds": 1},
                {"path": query["path"], "start_seconds": 0, "duration_seconds": 4},
                {"path": query["path"], "start_seconds": 0, "duration_seconds": 0},
                {"path": "/trusted/other.mp4", "start_seconds": 0, "duration_seconds": 1},
            ):
                self.assertTrue((await session.call_tool(tool, invalid)).is_error)
            self.assertEqual(len(heard), 1)
            self.assertFalse(any(row["method"] == "tools/call" for row in self.requests))
        await self.with_session(check, export_verifier=verifier, audio_observer=observer)

        async def deny_no_read(session):
            catalog = {x.name for x in (await session.list_tools()).tools}
            self.assertNotIn("zx7_observe_verified_export_audio", catalog)
        await self.with_session(deny_no_read, access=frozenset({"write"}),
                                export_verifier=verifier, audio_observer=observer)

    async def test_invalid_audio_witness_invalidates_its_verified_source(self):
        def verifier(path, expected=None):
            return {"physical_export_verified": True, "native_export_sha256": "e" * 64}
        def invalid_observer(path, verified_sha256, start_seconds, duration_seconds):
            wav = b"RIFF" + b"a" * 50
            return wav, {"export_sha256": verified_sha256,
                         "wav_sha256": "0" * 64,
                         "requested_start_seconds": start_seconds,
                         "requested_duration_seconds": duration_seconds}
        async def check(session):
            self.assertFalse((await session.call_tool("zx7_verify_native_export", {
                "path": "/trusted/audio.mp4"})).is_error)
            query = {"path": "/trusted/audio.mp4", "start_seconds": 0.5,
                     "duration_seconds": 1}
            invalid = await session.call_tool("zx7_observe_verified_export_audio", query)
            self.assertTrue(invalid.is_error)
            self.assertEqual(len(invalid.content), 1)
            again = await session.call_tool("zx7_observe_verified_export_audio", query)
            self.assertTrue(again.is_error)
            self.assertIn("verify", again.content[0].text.lower())
        await self.with_session(check, export_verifier=verifier,
                                audio_observer=invalid_observer)

    async def test_verified_temporal_audio_proof_is_source_bound_and_read_only(self):
        digest = "9" * 64
        requests = []
        def verifier(path, expected=None):
            self.assertEqual(path, "/trusted/long-video.mp4")
            return {"physical_export_verified": True, "native_export_sha256": digest}
        def observer(path, verified_sha256, start_seconds, duration_seconds, bins):
            requests.append((path, verified_sha256, start_seconds, duration_seconds, bins))
            return {"kind": "verified_native_editor_audio_temporal_envelope",
                    "export_sha256": verified_sha256,
                    "requested_start_seconds": start_seconds,
                    "requested_duration_seconds": duration_seconds,
                    "intervals": [{"sample_peak_normalized": 0.1,
                                   "rms_dbfs": -25.0} for _ in range(bins)],
                    "exact_original_audio_pts_proven": False,
                    "human_or_artistic_quality_approved": False}
        async def check(session):
            name = "zx7_observe_verified_export_audio_timeline"
            self.assertIn(name, [tool.name for tool in (await session.list_tools()).tools])
            args = {"path": "/trusted/long-video.mp4",
                    "start_seconds": 3.5, "duration_seconds": 10.0, "bins": 12}
            self.assertTrue((await session.call_tool(name, args)).is_error)
            self.assertFalse((await session.call_tool("zx7_verify_native_export", {
                "path": args["path"]})).is_error)
            result = await session.call_tool(name, args)
            self.assertFalse(result.is_error, result)
            self.assertEqual(len(result.content), 1)
            receipt = json.loads(result.content[0].text)
            self.assertEqual(receipt["export_sha256"], digest)
            self.assertEqual(len(receipt["intervals"]), 12)
            self.assertFalse(receipt["human_or_artistic_quality_approved"])
            self.assertEqual(requests, [(args["path"], digest, 3.5, 10.0, 12)])
            for invalid in (
                {**args, "duration_seconds": 301}, {**args, "bins": 257},
                {**args, "bins": True}, {**args, "start_seconds": float("nan")},
                {**args, "start_seconds": -1}, {**args, "path": "/trusted/other.mp4"}):
                self.assertTrue((await session.call_tool(name, invalid)).is_error)
            self.assertEqual(len(requests), 1)
            self.assertFalse(any(x["method"] == "tools/call" for x in self.requests))
        await self.with_session(check, export_verifier=verifier, audio_timeline_observer=observer)
        async def deny_no_read(session):
            self.assertNotIn("zx7_observe_verified_export_audio_timeline",
                             [tool.name for tool in (await session.list_tools()).tools])
        await self.with_session(deny_no_read, access=frozenset({"write"}),
                                export_verifier=verifier, audio_timeline_observer=observer)

    async def test_bad_audio_timeline_receipt_clears_trust_without_partial_data(self):
        def verifier(path, expected=None):
            return {"physical_export_verified": True, "native_export_sha256": "a" * 64}
        def wrong(path, verified_sha256, start_seconds, duration_seconds, bins):
            return {"kind": "verified_native_editor_audio_temporal_envelope",
                    "export_sha256": "f" * 64,
                    "requested_start_seconds": start_seconds,
                    "requested_duration_seconds": duration_seconds,
                    "intervals": [1] * bins}
        async def check(session):
            self.assertFalse((await session.call_tool("zx7_verify_native_export", {
                "path": "/trusted/video.mp4"})).is_error)
            args = {"path": "/trusted/video.mp4", "start_seconds": 0,
                    "duration_seconds": 2, "bins": 4}
            bad = await session.call_tool("zx7_observe_verified_export_audio_timeline", args)
            self.assertTrue(bad.is_error)
            self.assertEqual(len(bad.content), 1)
            again = await session.call_tool("zx7_observe_verified_export_audio_timeline", args)
            self.assertTrue(again.is_error)
            self.assertIn("verify", again.content[0].text.lower())
        await self.with_session(check, export_verifier=verifier,
                                audio_timeline_observer=wrong)

    async def test_readonly_decode_does_not_block_native_editing(self):
        """Long-running physical inspection cannot monopolize editor RPC locks."""
        entered = threading.Event()
        release = threading.Event()
        def verifier(path, expected=None):
            entered.set()
            if not release.wait(timeout=5):
                raise ValueError("Timed out waiting for synthetic decode release")
            return {"physical_export_verified": True, "native_export_sha256": "e" * 64}

        async def check(session):
            finished = anyio.Event()
            async def verify():
                try:
                    receipt = await session.call_tool("zx7_verify_native_export", {
                        "path": "/trusted/isolated-output.mp4"})
                    self.assertFalse(receipt.is_error)
                finally:
                    finished.set()
            async with anyio.create_task_group() as group:
                group.start_soon(verify)
                try:
                    self.assertTrue(await anyio.to_thread.run_sync(
                        lambda: entered.wait(timeout=2)))
                    with anyio.fail_after(2):
                        current = await session.call_tool("get_project", {})
                    self.assertFalse(current.is_error)
                    self.assertFalse(finished.is_set())
                finally:
                    release.set()
                await finished.wait()
        await self.with_session(check, export_verifier=verifier)

    def test_missing_host_grant_or_remote_schema_reference_fails_closed(self):
        self.tools = [TOOLS[0]]
        with self.assertRaisesRegex(ValueError, "absent"):
            create_editor_server(self.client)
        self.tools = [TOOLS[0], {**TOOLS[1], "inputSchema": {"type": "object",
            "properties": {"x": {"$ref": "https://example.invalid/schema"}}}}]
        with self.assertRaisesRegex(ValueError, "reference"):
            create_editor_server(self.client, allowed_access=frozenset({"read", "write"}))

    async def test_real_stdio_client_initialize_list_and_call(self):
        with tempfile.TemporaryDirectory() as root:
            roots = {name: str(Path(root) / name) for name in ("projects", "staging", "outputs")}
            config = {"endpoint": self.endpoint, "projects_root": roots["projects"],
                      "staging_root": roots["staging"], "outputs_root": roots["outputs"],
                      "allowed_tools": {"get_project": "read", "update_text_clip": "write"},
                      "allowed_access": ["read", "write"]}
            path = Path(root) / "host.json"
            path.write_text(json.dumps(config))
            params = StdioServerParameters(command=sys.executable, args=["-m", "studio_next.body_editor_mcp",
                                            "--config", str(path)])
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    self.assertEqual(initialized.server_info.name, "zx7-native-editor")
                    self.assertEqual((await session.list_tools()).tools[1].input_schema, SCHEMA)
                    self.assertFalse((await session.call_tool("get_project", {})).is_error)
                    self.assertFalse((await session.call_tool("update_text_clip", {"clipId": "x", "text": "stdio"})).is_error)
                    self.assertTrue((await session.call_tool("install_workflow_setup", {})).is_error)
            inspected = subprocess.run([sys.executable, "-m", "studio_next.body_editor_mcp", "--config", str(path),
                                        "--print-launch-config"], capture_output=True, text=True, timeout=10)
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            self.assertEqual(json.loads(inspected.stdout), {"endpoint": self.endpoint,
                "projects_root": roots["projects"], "staging_root": roots["staging"], "outputs_root": roots["outputs"]})


if __name__ == "__main__":
    unittest.main()
