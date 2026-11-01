"""No-cost protocol/permission tests for user-selected creative Brain endpoints."""
import base64
import hashlib
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from studio_next.brain_model_endpoint import (
    CreativeBrainEndpoint, CreativeBrainModel, CreativeBrainConnectionError)


class BrainConnectionTests(unittest.TestCase):
    def test_local_is_fully_usable_without_keys_or_paid_permission(self):
        endpoint=CreativeBrainEndpoint(model_id="local-open-model")
        self.assertEqual(endpoint.mode,"local")
        self.assertFalse(endpoint.paid_inference_approved)
        self.assertIsNone(endpoint.credential_env)
        with self.assertRaises(CreativeBrainConnectionError):
            CreativeBrainEndpoint(model_id="remote",mode="local",
                base_url="https://api.example.org/v1")
        with self.assertRaises(CreativeBrainConnectionError):
            CreativeBrainEndpoint(model_id="local",mode="local",
                base_url="http://127.0.0.1:8080",credential_env="PAID_KEY")

    def test_remote_needs_explicit_approval_public_tls_and_host_only_secret(self):
        params=dict(model_id="creative-model",
                    base_url="https://api.example.org/v1",
                    mode="openai_compatible_remote",
                    credential_env="ZX7_CREATIVE_MODEL_API_KEY")
        with self.assertRaises(CreativeBrainConnectionError):
            CreativeBrainEndpoint(**params)
        approved=CreativeBrainEndpoint(**params,paid_inference_approved=True)
        self.assertTrue(approved.paid_inference_approved)
        self.assertFalse(approved.remote_owner_media_approved)
        for bad in ("http://api.example.org/v1",
                    "https://127.0.0.1/v1","https://user:pw@api.example.org/v1"):
            with self.subTest(bad=bad),self.assertRaises(CreativeBrainConnectionError):
                CreativeBrainEndpoint(**{**params,"base_url":bad},
                                      paid_inference_approved=True)

    def test_remote_media_never_sent_without_separate_explicit_consent(self):
        endpoint=CreativeBrainEndpoint(model_id="remote",
            base_url="https://api.example.org/v1",mode="openai_compatible_remote",
            credential_env="ZX7_CREATIVE_MODEL_API_KEY",paid_inference_approved=True)
        model=CreativeBrainModel(endpoint,system_prompt="Make artistic edits.")
        image=b"\x89PNG\r\n\x1a\n"+b"owned-image"
        context={"picture_evidence":[{"sha256":hashlib.sha256(image).hexdigest()}]}
        with self.assertRaisesRegex(CreativeBrainConnectionError,
                                    "explicit owner consent"):
            model.decide_with_images(context,[("image/png",image)])
        self.assertEqual(model.remaining_calls,endpoint.max_inference_calls)

    def test_actual_local_http_decision_and_bounded_call_count(self):
        messages=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                size=int(self.headers.get("Content-Length","0"))
                payload=json.loads(self.rfile.read(size))
                messages.append(payload)
                answer={"choices":[{"finish_reason":"stop","message":{
                    "content":'{"action":"discover","arguments":{},"reason":"inspect before editing"}'}}],
                    "usage":{"total_tokens":12}}
                raw=json.dumps(answer).encode()
                self.send_response(200)
                self.send_header("Content-Length",str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def log_message(self,*args):
                pass
        server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            endpoint=CreativeBrainEndpoint(model_id="local-gguf",
                base_url=f"http://127.0.0.1:{server.server_port}",
                max_inference_calls=1)
            model=CreativeBrainModel(endpoint,system_prompt="Independent creative director")
            result=model.decide({"creative_brief":"Edit actual owner footage"})
            self.assertEqual(result["action"],"discover")
            self.assertEqual(len(messages),1)
            self.assertEqual(messages[0]["model"],"local-gguf")
            self.assertEqual(messages[0]["messages"][1]["role"],"user")
            self.assertEqual(model.last_call_usage["total_tokens"],12)
            with self.assertRaisesRegex(CreativeBrainConnectionError,"budget exhausted"):
                model.decide({"creative_brief":"Again"})
            self.assertEqual(len(messages),1)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)

    def test_no_owner_private_image_source_substitution(self):
        endpoint=CreativeBrainEndpoint(model_id="local-gguf")
        model=CreativeBrainModel(endpoint,system_prompt="Visual judge")
        img=b"\x89PNG\r\n\x1a\n"+b"owned-image"
        with self.assertRaisesRegex(CreativeBrainConnectionError,"identity proof"):
            model.decide_with_images(
                {"picture_evidence":[{"sha256":"0"*64}]},[("image/png",img)])

    def test_billed_model_key_unavailable_fails_before_network(self):
        endpoint=CreativeBrainEndpoint(model_id="paid",
            base_url="https://api.example.org/v1",mode="openai_compatible_remote",
            credential_env="ZX7_CREATIVE_MODEL_API_KEY",paid_inference_approved=True)
        model=CreativeBrainModel(endpoint,system_prompt="Creative editor")
        with patch.dict(os.environ,{"ZX7_CREATIVE_MODEL_API_KEY":""}):
            with self.assertRaisesRegex(CreativeBrainConnectionError,"credential"):
                model.decide({"brief":"Creative only"})


if __name__=="__main__":
    unittest.main()
