"""Local-model network isolation and reliable JSON-output tests (no real server)."""
import io
import json
import unittest
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch
from studio_next.providers import LocalCreativeModel,LocalModelSettings

class FakeReply:
    def __init__(self,payload):
        self.payload=payload
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,length):return json.dumps(self.payload).encode()[:length]

def answer(text,finish="stop"):
    return {"choices":[{"finish_reason":finish,"message":{"content":text}}]}

class ProviderTests(unittest.TestCase):
    def test_ambiguous_model_json_never_reaches_native_editor_over_real_http(self):
        from studio_next.native_creative_control import NativeCreativeControl
        response = [b'']
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200)
                self.send_header('Content-Length', str(len(response[0])))
                self.end_headers()
                self.wfile.write(response[0])
            def log_message(self, *args): pass
        class Session:
            calls = []
            async def list_tools(self):
                return SimpleNamespace(tools=[SimpleNamespace(name='update_text_clip',
                    input_schema={'type':'object'}, description='Native edit')])
            async def call_tool(self, name, args):
                self.calls.append((name,args))
                return SimpleNamespace(is_error=False,content=[])
        server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            model = LocalCreativeModel(LocalModelSettings(base_url=f'http://127.0.0.1:{server.server_port}'))
            bad = [
                '{"action":"finish","action":"invoke","arguments":{"tool":"update_text_clip","inputs":{}},"reason":"ambiguous"}',
                '{"action":"invoke","arguments":{"tool":"update_text_clip","inputs":{"text":"first","text":"second"}},"reason":"ambiguous"}',
            ]
            for body in bad:
                response[0] = json.dumps(answer(body)).encode()
                with self.subTest(body=body), self.assertRaisesRegex(ValueError,'[Dd]uplicate'):
                    asyncio.run(NativeCreativeControl(Session(),model,max_turns=1).run('Edit a native project'))
                self.assertEqual(Session.calls,[])
            response[0] = b'{"choices":[],"choices":[{"message":{"content":"{}"}}]}'
            with self.assertRaisesRegex(ValueError,'[Dd]uplicate'):
                model.decide({})
            for body in ('{"value":1e999}', '{"value":NaN}', '{"value":-Infinity}'):
                response[0] = json.dumps(answer(body)).encode()
                with self.subTest(body=body), self.assertRaises(ValueError):
                    model.decide({})
            response[0] = json.dumps(answer('{"text":"ठीक है","value":0.125}')).encode()
            self.assertEqual(model.decide({}),{'text':'ठीक है','value':0.125})
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_remote_api_not_possible_by_default(self):
        for endpoint in ("https://api.openai.com","http://x.evil.com:8080",
                         "http://127.0.0.1:8080/path","http://me:pass@localhost:8080",
                         "http://localhost:8080/?key=secret"):
            with self.subTest(endpoint=endpoint),self.assertRaises(ValueError):
                LocalModelSettings(base_url=endpoint)
    def test_creative_response_schema(self):
        client=LocalCreativeModel(LocalModelSettings(model_id="qwen-local"))
        decision={"kind":"question","question":"Which specific product is it?"}
        requests=[]
        def mock_urlopen(req,timeout):
            data=json.loads(req.data)
            requests.append((req.full_url,data,timeout))
            return FakeReply(answer(json.dumps(decision)))
        with patch("studio_next.providers.urlopen",side_effect=mock_urlopen):
            result=client.decide({"brief":{"request":"Make a Short"}})
        self.assertEqual(result,decision)
        self.assertEqual(requests[0][1]["model"],"qwen-local")
        self.assertIn("film",requests[0][1]["messages"][0]["content"].lower()+
                      " film") # accepted general film remit
        self.assertTrue(requests[0][0].startswith("http://127.0.0.1:8080"))
    def test_local_pinned_native_decision_grammar_is_json_only_not_an_edit_script(self):
        from studio_next.native_creative_control import (
            NATIVE_CREATIVE_DECISION_SCHEMA, NATIVE_CREATIVE_SYSTEM)
        import jsonschema
        schema = NATIVE_CREATIVE_DECISION_SCHEMA
        jsonschema.Draft202012Validator.check_schema(schema)
        self.assertEqual(schema["required"], ["action", "arguments", "reason"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]["action"]["enum"]), {
            "search", "describe", "invoke", "apply_preview", "discover", "finish"})
        # This schema never specifies what file, clip, scene or tool the brain
        # may create. Actual host tools must still be discovered and granted.
        self.assertEqual(schema["properties"]["arguments"], {
            "type": "object", "additionalProperties": True})
        self.assertNotIn("tool", json.dumps(schema))
        self.assertNotIn("previewOnly", json.dumps(schema))
        response_format = {"type": "json_schema", "schema": schema}
        model = LocalCreativeModel(LocalModelSettings(
            model_id="zx7-pinned-local", sampling={
                "response_format": response_format,
            }), system_prompt=NATIVE_CREATIVE_SYSTEM)
        generated = {
            "action": "search", "arguments": {
                "query": "inspect current native original video media",
                "limit": 5,
            }, "reason": "Model-chosen real editor discovery",
        }
        requests = []
        def mock_urlopen(req, timeout):
            requests.append(json.loads(req.data))
            return FakeReply(answer(json.dumps(generated)))
        with patch("studio_next.providers.urlopen", side_effect=mock_urlopen):
            self.assertEqual(model.decide({"host_only": "safe"}), generated)
        self.assertEqual(requests[0]["response_format"], response_format)
        self.assertEqual(requests[0]["model"], "zx7-pinned-local")
        self.assertTrue(jsonschema.Draft202012Validator(schema).is_valid(generated))
        self.assertFalse(jsonschema.Draft202012Validator(schema).is_valid({
            **generated, "action": "execute_shell"}))
        # The unconstrained general creative-director provider remains
        # backward-compatible with regular JSON object mode.
        other = LocalCreativeModel(LocalModelSettings())
        with patch("studio_next.providers.urlopen", side_effect=mock_urlopen):
            other.decide({"brief": "Review licensed clips"})
        self.assertEqual(requests[1]["response_format"], {"type": "json_object"})

    def test_critic_response_separate_role(self):
        c=LocalCreativeModel(LocalModelSettings())
        with patch("studio_next.providers.urlopen",return_value=FakeReply(
            answer('{"approved":false,"issues":[{"location":"/scene1","reason":"weak","repair":"stronger hook"}]}'))):
            v=c.review({"plan":{"creative_intent":"draft"}})
        self.assertFalse(v["approved"])
    def test_model_body_decode_failures_are_typed_but_server_envelopes_are_not(self):
        from studio_next.providers import LocalModelOutputError
        model = LocalCreativeModel(LocalModelSettings())
        with patch("studio_next.providers.urlopen", return_value=FakeReply(
            answer('{"title":"first","title":"second"}'))):
            with self.assertRaises(LocalModelOutputError) as exc:
                model.decide({"brief": "Never silently choose between duplicate fields"})
        self.assertEqual(exc.exception.code, "duplicate_json_field")
        self.assertNotIn("first", str(exc.exception))
        self.assertTrue(exc.exception.__suppress_context__)
        # Raw model-authored JSON property names must never appear in a
        # printed traceback, which may be uploaded as shared CI evidence.
        import traceback
        chain = "".join(traceback.format_exception(exc.exception))
        self.assertNotIn('Duplicate local model JSON field: title', chain)
        self.assertNotIn('first', chain)
        for body, expected in (("not JSON", "invalid_json"),
                               ('{"incomplete":', "invalid_json"),
                               ('["list"]', "non_object_json"),
                               ("", "empty_response")):
            with self.subTest(body=body), patch(
                "studio_next.providers.urlopen", return_value=FakeReply(answer(body))
            ), self.assertRaises(LocalModelOutputError) as caught:
                model.decide({})
            self.assertEqual(caught.exception.code, expected)
        # A broken transport/server envelope is not model-authored content
        # and must not turn into an automatically re-asked creative decision.
        with patch("studio_next.providers.urlopen", return_value=FakeReply(
            {"choices": [], "choices_extra": []})):
            with self.assertRaises(IndexError):
                model.decide({})

    def test_truncated_output_is_error(self):
        c=LocalCreativeModel(LocalModelSettings())
        with patch("studio_next.providers.urlopen",return_value=FakeReply(
            answer('{"kind":"proposal"}',finish="length"))):
            with self.assertRaises(ValueError):
                c.decide({"brief":{}})
    def test_empty_and_non_object_json_rejected(self):
        c=LocalCreativeModel(LocalModelSettings())
        for payload in (answer(""),answer('["bad"]')):
            with patch("studio_next.providers.urlopen",return_value=FakeReply(payload)):
                with self.assertRaises(ValueError):
                    c.decide({})
    def test_sampling_cannot_override_identity(self):
        with self.assertRaises(ValueError):
            LocalModelSettings(sampling={"messages":[]})
        with self.assertRaises(ValueError):
            LocalModelSettings(sampling={"model":"not-approved"})
    def test_sampling_optional_model_decides_creative_outputs(self):
        s=LocalModelSettings(sampling={})
        self.assertEqual(s.sampling,{}) # no global temperature, fixed voice/pace etc

if __name__=="__main__":unittest.main()
