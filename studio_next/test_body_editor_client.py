import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from studio_next.body_editor_client import (
    LocalEditorClient, EditorAccessError, EditorClientError,
    EditorProtocolError, EditorToolError,
)


class LocalEditorClientTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.reply = lambda request: {"jsonrpc": "2.0", "id": request["id"],
                                      "result": {"content": [{"type": "text", "text": "native"}]}}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append(request)
                answer = owner.reply(request)
                status, payload = answer if isinstance(answer, tuple) else (200, answer)
                body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except BrokenPipeError:
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}/mcp"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def client(self, **kwargs):
        return LocalEditorClient(self.endpoint, allowed_tools={"read": "read", "edit": "write"}, **kwargs)

    def test_complete_native_schema_and_unknown_tools_are_discovered_without_grant(self):
        tools = [{"name": "future_native_tool", "inputSchema": {"type": "object", "properties": {
            "curve": {"anyOf": [{"type": "string"}, {"type": "null"}]}}, "additionalProperties": False}}]
        self.reply = lambda request: {"jsonrpc": "2.0", "id": request["id"], "result": {"tools": tools}}
        client = self.client()
        self.assertEqual(client.list_tools(), tools)
        with self.assertRaises(EditorAccessError):
            client.call("future_native_tool", {})
        self.assertEqual(len(self.requests), 1)

    def test_actual_native_call_arguments_and_fresh_correlated_ids(self):
        client = self.client()
        arguments = {"clipId": "native", "nested": {"points": [0, 0.5, None]}}
        self.assertEqual(client.call("read", arguments)["content"][0]["text"], "native")
        client.call("read", {})
        self.assertEqual(self.requests[0]["params"], {"name": "read", "arguments": arguments})
        self.assertNotEqual(self.requests[0]["id"], self.requests[1]["id"])

    def test_host_grants_and_caller_access_precede_http(self):
        client = self.client()
        for name, access in [("unknown", {"read", "write"}), ("edit", {"read"})]:
            with self.assertRaises(EditorAccessError):
                client.call(name, {}, allowed_access=access)
        self.assertEqual(self.requests, [])
        client.call("edit", {}, allowed_access={"write"})
        self.assertEqual(len(self.requests), 1)

    def test_only_exact_true_policy_accepts_before_http(self):
        for verdict in [False, None, 1, "yes"]:
            with self.subTest(verdict=verdict), self.assertRaises(EditorAccessError):
                self.client(policy=lambda *args: verdict).call("read", {})
        self.assertEqual(self.requests, [])
        self.client(policy=lambda *args: True).call("read", {})

    def test_grants_are_copied_and_read_only(self):
        grants = {"read": "read"}
        client = LocalEditorClient(self.endpoint, allowed_tools=grants)
        grants["edit"] = "write"
        self.assertNotIn("edit", client.allowed_tools)
        with self.assertRaises(TypeError):
            client.allowed_tools["edit"] = "write"
        with self.assertRaises(AttributeError):
            client.allowed_tools = {}
        self.assertEqual(client.endpoint, self.endpoint)

    def test_nonliteral_remote_credential_or_redirect_endpoints_refused(self):
        for endpoint in ["https://127.0.0.1:99/mcp", "http://localhost:99/mcp", "http://8.8.8.8:99/mcp",
                         "http://user@127.0.0.1:99/mcp", self.endpoint + "?x=1", self.endpoint + "/",
                         "http://127.0.0.1:0/mcp", "http://127.0.0.1:65536/mcp"]:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                LocalEditorClient(endpoint, allowed_tools={})

    def test_redirect_not_followed_or_retried(self):
        self.reply = lambda request: (302, b"redirect")
        with self.assertRaises(EditorProtocolError):
            self.client().call("read", {})
        self.assertEqual(len(self.requests), 1)

    def test_timeout_is_reported_without_retrying_a_possible_write(self):
        def reply(request):
            time.sleep(0.1)
            return {"jsonrpc": "2.0", "id": request["id"], "result": {"content": []}}
        self.reply = reply
        with self.assertRaises(EditorClientError):
            self.client(timeout=0.02).call("edit", {}, allowed_access={"write"})
        self.assertEqual(len(self.requests), 1)

    def test_cli_byte_limit_includes_multibyte_utf8_input(self):
        request = json.dumps({"operation": "call", "tool_name": "read", "arguments": {
            "x": "क" * 400000}}, ensure_ascii=False)
        self.assertLess(len(request), 1024 * 1024)
        result = self.cli(request)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.requests, [])

    def test_rpc_id_version_and_exclusive_result_are_checked(self):
        for update in [{"id": "wrong"}, {"jsonrpc": "1.0"}, {"error": {"code": 1}}]:
            self.reply = lambda request: {"jsonrpc": "2.0", "id": request["id"], "result": {}, **update}
            with self.subTest(update=update), self.assertRaises(EditorProtocolError):
                self.client().call("read", {})

    def test_rpc_and_native_errors_are_not_synthetic_success(self):
        self.reply = lambda request: {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -1, "message": "failed"}}
        with self.assertRaises(EditorProtocolError):
            self.client().call("read", {})
        self.reply = lambda request: {"jsonrpc": "2.0", "id": request["id"], "result": {"content": [], "isError": True}}
        with self.assertRaises(EditorToolError) as caught:
            self.client().call("read", {})
        self.assertTrue(caught.exception.result["isError"])

    def test_malformed_nonfinite_duplicate_json_and_result_rejected(self):
        for raw in [b"not json", b'{"jsonrpc":"2.0","id":1,"result":NaN}',
                    b'{"jsonrpc":"2.0","jsonrpc":"2.0"}', b'{"result":1e999}']:
            self.reply = lambda request: (200, raw)
            with self.subTest(raw=raw), self.assertRaises(EditorProtocolError):
                self.client().call("read", {})
        self.reply = lambda request: {"jsonrpc": "2.0", "id": request["id"], "result": {"content": {}, "isError": "false"}}
        with self.assertRaises(EditorProtocolError):
            self.client().call("read", {})

    def test_response_byte_limit_and_invalid_client_limits(self):
        with self.assertRaises(EditorProtocolError):
            self.client(max_response_bytes=16).call("read", {})
        for settings in [{"timeout": 0}, {"timeout": math.inf}, {"max_response_bytes": True}, {"max_response_bytes": 0}]:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.client(**settings)

    def test_bad_catalog_duplicate_names_and_pagination_fail_closed(self):
        good = {"name": "read", "inputSchema": {"type": "object"}}
        for result in [{"tools": [good, good]}, {"tools": [{}]}, {"tools": "wrong"},
                       {"tools": [good], "nextCursor": "more"}]:
            self.reply = lambda request: {"jsonrpc": "2.0", "id": request["id"], "result": result}
            with self.subTest(result=result), self.assertRaises(EditorProtocolError):
                self.client().list_tools()

    def test_arguments_must_be_finite_json_objects(self):
        for arguments in [[], {"x": math.nan}, {"x": math.inf}, {1: "bad"}, {"x": object()}]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.client().call("read", arguments)
        self.assertEqual(self.requests, [])

    def test_all_body_native_client_routes_reject_lossy_razor_before_any_write(self):
        # Actual loopback JSON-RPC client exercising the same grant checks used
        # by both the catalog and official stdio bridge, not just a pure mock.
        clip = {
            "id": "clip-artist", "trackId": "video-1",
            "type": "video", "startTime": 0, "duration": 12,
            "speed": 1, "reverse": False, "frameSampling": "frame",
            "sourceTimeScale": 1, "compositeLowerLayers": "auto",
            "transform": {"opacity": 100, "scaleX": 100},
            "keyframes": {"opacity": [{"time": 0, "value": 0},
                                      {"time": 2, "value": 100}]},
        }
        def reply(request):
            name = request["params"]["name"]
            if name == "get_timeline":
                data = {"timeline": {
                    "clips": [{
                        "id": clip["id"], "name": "original", "assetId": "src",
                        "trackId": clip["trackId"], "type": clip["type"],
                        "startTime": clip["startTime"], "duration": clip["duration"],
                        "speed": clip["speed"], "transform": clip["transform"],
                        "effects": [], "keyframes": clip.get("keyframes", {}),
                        "metadata": {}, "trackMatte": "none",
                    }],
                    "clipCount": 1, "clipLimitApplied": False,
                    "tracks": [{"id": "video-1", "locked": False}],
                    "transitions": []}}
            elif name == "inspect_clip":
                data = {"clip": clip}
            elif name == "split_clip":
                data = {"success": True}
            else:
                raise AssertionError("Unexpected native operation")
            return {"jsonrpc": "2.0", "id": request["id"],
                    "result": {"content": [{"type": "text", "text": json.dumps(data)}]}}
        self.reply = reply
        client = LocalEditorClient(self.endpoint, allowed_tools={
            "get_timeline": "read", "inspect_clip": "read", "split_clip": "write"})
        with self.assertRaisesRegex(EditorAccessError, "discard editable clip state"):
            client.call("split_clip", {
                "clipId": "clip-artist", "timeSeconds": 6,
                "previewOnly": False}, allowed_access={"read", "write"})
        self.assertEqual([r["params"]["name"] for r in self.requests],
                         ["inspect_clip"])
        self.assertIn("keyframes", clip)
        clip.pop("keyframes")
        successful = client.call("split_clip", {
            "clipId": "clip-artist", "timeSeconds": 6,
            "previewOnly": False}, allowed_access={"read", "write"})
        self.assertEqual(json.loads(successful["content"][0]["text"])["success"], True)
        self.assertEqual([r["params"]["name"] for r in self.requests[-3:]],
                         ["inspect_clip", "get_timeline", "split_clip"])

    def test_split_hidden_effect_in_native_summary_is_caught_by_complete_snapshot(self):
        # Pinned Velorn inspect_clip returns a compact summary WITHOUT
        # effects/keyframes. The full get_timeline clip has their real state.
        full_clip = {
            "id": "full-a", "name": "source", "type": "video",
            "assetId": "source", "trackId": "v1",
            "startTime": 0, "duration": 10, "trimStart": 0,
            "trimEnd": 10, "sourceDuration": 10, "speed": 1,
            "enabled": True, "labelColor": "", "trackMatte": "none",
            "lockMode": None, "syncLock": None,
            "transform": {"opacity": 100},
            "effects": [{"id": "protected-blur"}], "keyframes": {},
            "textProperties": None, "shapeProperties": None,
            "titleAnimation": None, "metadata": {"addedByMcp": True},
            "captionScope": None, "overlayKind": None, "text": "",
        }
        def reply(request):
            name = request["params"]["name"]
            if name == "inspect_clip":
                # Exact risk: native summary is not full editable state.
                value = {"clip": {key: full_clip[key] for key in (
                    "id", "trackId", "type", "assetId", "startTime",
                    "duration", "trimStart", "speed", "transform")}}
            elif name == "get_timeline":
                value = {"clips": [full_clip], "clipCount": 1,
                         "clipLimitApplied": False, "tracks": [{"id": "v1"}],
                         "transitions": []}
            elif name == "split_clip":
                raise AssertionError("Effects-bearing clip must never be razored")
            else:
                raise AssertionError("Unexpected native operation")
            return {"jsonrpc": "2.0", "id": request["id"],
                    "result": {"content": [{"type": "text",
                                            "text": json.dumps(value)}]}}
        self.reply = reply
        client = LocalEditorClient(self.endpoint, allowed_tools={
            "inspect_clip": "read", "get_timeline": "read", "split_clip": "write"})
        with self.assertRaisesRegex(EditorAccessError, "discard editable clip state"):
            client.call("split_clip", {"clipId": "full-a",
                        "timeSeconds": 3, "previewOnly": False},
                        allowed_access={"read", "write"})
        self.assertEqual([r["params"]["name"] for r in self.requests],
                         ["inspect_clip", "get_timeline"])

    def test_native_extract_full_state_protection_rejects_hidden_effects_and_then_allows_plain(self):
        # This exercises the actual shared RPC client interception, not only a
        # direct call of the guard. The summary is purposely never consulted:
        # native get_timeline is the sole source of editable effects/keyframes.
        full_clip = {
            "id": "native-a", "name": "source", "type": "video",
            "assetId": "source", "trackId": "video-1",
            "startTime": 0, "duration": 12, "trimStart": 0, "trimEnd": 12,
            "sourceDuration": 12, "speed": 1, "enabled": True,
            "labelColor": "", "trackMatte": "none", "lockMode": None,
            "syncLock": None, "transform": {"opacity": 100},
            "effects": [{"id": "preserve-this-effect"}],
            "textProperties": None, "shapeProperties": None,
            "titleAnimation": None, "keyframes": {},
            "metadata": {"addedByMcp": True}, "captionScope": None,
            "overlayKind": None, "text": "",
        }
        def reply(request):
            name = request["params"]["name"]
            arguments = request["params"]["arguments"]
            if name == "get_timeline":
                result = {"clips": [full_clip], "clipCount": 1,
                          "fps": 24, "trackCount": 1,
                          "clipLimitApplied": False,
                          "tracks": [{"id": "video-1", "locked": False}],
                          "transitions": []}
            elif name == "extract_range" and arguments.get("previewOnly") is True:
                # Exact upstream mcpServer.runRendererActionTool response.
                result = {"previewOnly": True, "action": "extract_range",
                          "result": {"previewOnly": True, "action": "extract_range",
                                     "warnings": [],
                                     "plan": {
                                         "splitAtStart": [{"id": "native-a"}],
                                         "splitAtEnd": [{"id": "native-a"}]}},
                          "suggestedApplyCall": {
                              "tool": "extract_range",
                              "arguments": {**arguments, "previewOnly": False}}}
            elif name == "extract_range" and arguments.get("previewOnly") is False:
                result = {"success": True, "message": "native edit confirmed"}
            else:
                raise AssertionError("Unexpected native editor operation")
            return {"jsonrpc": "2.0", "id": request["id"],
                    "result": {"content": [
                        {"type": "text", "text": json.dumps(result)}]}}
        self.reply = reply
        client = LocalEditorClient(self.endpoint, allowed_tools={
            "get_timeline": "read", "extract_range": "write"})
        arguments = {"startSeconds": 3, "endSeconds": 7, "previewOnly": False}
        with self.assertRaisesRegex(EditorAccessError, "discard editable clip state"):
            client.call("extract_range", arguments, allowed_access={"read", "write"})
        self.assertEqual([r["params"]["name"] for r in self.requests],
                         ["get_timeline", "extract_range"])
        self.assertTrue(self.requests[-1]["params"]["arguments"]["previewOnly"])
        full_clip["effects"] = []
        success = client.call("extract_range", arguments, allowed_access={"read", "write"})
        self.assertEqual(json.loads(success["content"][0]["text"])["success"], True)
        self.assertEqual([r["params"]["name"] for r in self.requests[-3:]],
                         ["get_timeline", "extract_range", "extract_range"])
        self.assertTrue(self.requests[-2]["params"]["arguments"]["previewOnly"])
        self.assertFalse(self.requests[-1]["params"]["arguments"]["previewOnly"])

    def test_split_without_granted_read_inspection_has_no_native_write(self):
        client = LocalEditorClient(self.endpoint, allowed_tools={"split_clip": "write"})
        with self.assertRaisesRegex(EditorAccessError, "host-granted read"):
            client.call("split_clip", {"clipId": "clip-1", "timeSeconds": 2,
                                       "previewOnly": False}, allowed_access={"read", "write"})
        self.assertEqual(self.requests, [])

    def cli(self, request, permissions=None):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root, "host.json")
            file.write_text(json.dumps(permissions or {"allowed_tools": {"read": "read", "edit": "write"}}))
            return subprocess.run([sys.executable, "-m", "studio_next.body_editor_client", "--endpoint", self.endpoint,
                                   "--permissions", str(file), "--request"], input=request, text=True,
                                  capture_output=True, timeout=10, cwd=Path(__file__).resolve().parents[1])

    def test_cli_uses_host_file_and_native_http(self):
        result = self.cli(json.dumps({"operation": "call", "tool_name": "read", "arguments": {"x": 1}}))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["content"][0]["text"], "native")
        denied = self.cli(json.dumps({"operation": "call", "tool_name": "edit", "arguments": {}}))
        self.assertNotEqual(denied.returncode, 0)
        self.assertEqual(len(self.requests), 1)

    def test_cli_request_cannot_supply_own_grants(self):
        result = self.cli(json.dumps({"operation": "call", "tool_name": "edit", "arguments": {}, "allowed_access": ["write"]}))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.requests, [])

    def test_cli_rejects_oversized_input_before_http(self):
        result = self.cli(json.dumps({"operation": "call", "tool_name": "read", "arguments": {"x": "x" * (1024 * 1024)}}))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
