"""No-network source contract tests for NVIDIA function-call native decisions."""
from __future__ import annotations
from io import BytesIO
import json
import os
import unittest
from unittest.mock import patch

from studio_next.nvidia_tool_model import NvidiaToolCreativeModel, _TOOL_NAME
from studio_next.nvidia_model import NvidiaConfigurationError
from studio_next.providers import LocalModelOutputError


def _mock_response(arguments, *, tool_name=_TOOL_NAME):
    return BytesIO(json.dumps({
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {
                "tool_calls": [{
                    "id": "call_single",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                }],
            },
        }],
        "usage": {"prompt_tokens": 52, "completion_tokens": 22, "total_tokens": 74},
    }).encode())


class NvidiaHostFunctionToolTests(unittest.TestCase):
    def test_real_request_has_one_forced_function_and_no_host_tool_dispatch(self):
        captured = []
        class Opener:
            def open(self, request, timeout):
                captured.append(request)
                return _mock_response(json.dumps({
                    "action": "search",
                    "arguments": {"query": "project creator", "limit": 3},
                    "reason": "Find the one real project creator",
                }))
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-" + "A" * 32}), patch(
                "studio_next.nvidia_model.build_opener", return_value=Opener()):
            model = NvidiaToolCreativeModel(system_prompt="Choose one safe native action")
            result = model.decide({"available_actions": ["search"], "turn": 0})
        self.assertEqual(result["action"], "search")
        self.assertEqual(result["arguments"]["query"], "project creator")
        self.assertEqual(model.last_call_usage["total_tokens"], 74)
        self.assertEqual(len(captured), 1)
        request = captured[0]
        self.assertEqual(request.full_url,
                         "https://integrate.api.nvidia.com/v1/chat/completions")
        body = json.loads(request.data)
        self.assertEqual(body["tool_choice"]["function"]["name"], _TOOL_NAME)
        self.assertEqual(body["tools"][0]["function"]["name"], _TOOL_NAME)
        self.assertFalse(body["parallel_tool_calls"])
        self.assertFalse(body["stream"])
        self.assertNotIn("response_format", body)
        self.assertNotIn("nvapi-", request.data.decode())

    def test_no_cloud_key_refuses_before_transport(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": ""}), patch(
                "studio_next.nvidia_model.build_opener") as opener:
            with self.assertRaises(NvidiaConfigurationError):
                NvidiaToolCreativeModel(system_prompt="test").decide({})
            opener.assert_not_called()

    def test_any_ambiguous_function_call_is_non_executable(self):
        malformed = [
            '{"action":"search","arguments":{"query":"a"},"reason":"b","reason":"duplicate"}',
            '{"action":"search","arguments":{"query":"a"}}',
            '{"action":"search","arguments":{},"reason":"ok","extra":true}',
        ]
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-" + "B" * 32}):
            for value in malformed:
                class Opener:
                    def open(self, req, timeout):
                        return _mock_response(value)
                with self.subTest(value=value), patch(
                        "studio_next.nvidia_model.build_opener",
                        return_value=Opener()):
                    with self.assertRaises(LocalModelOutputError):
                        NvidiaToolCreativeModel(system_prompt="test").decide({})
            class Other:
                def open(self, request, timeout):
                    return _mock_response('{"action":"finish","arguments":{},"reason":"ok"}',
                                          tool_name="untrusted_sender")
            with patch("studio_next.nvidia_model.build_opener", return_value=Other()):
                with self.assertRaisesRegex(LocalModelOutputError, "unexpected_native_function"):
                    NvidiaToolCreativeModel(system_prompt="test").decide({})

    def test_cloud_frame_upload_permission_and_actual_byte_identity(self):
        from hashlib import sha256
        raw = b"\x89PNG\r\n\x1a\n" + b"checked-real-image-bytes"
        item = {"job_id": "native-1", "path": "native-shot.png",
                "sha256": sha256(raw).hexdigest()}
        model = NvidiaToolCreativeModel(system_prompt="test")
        with self.assertRaises(NvidiaConfigurationError):
            model.decide_with_images({"picture_evidence": [item]}, [("image/png", raw)])
        model = NvidiaToolCreativeModel(system_prompt="test", allow_image_upload=True)
        with self.assertRaisesRegex(NvidiaConfigurationError, "hash custody"):
            model.decide_with_images({"picture_evidence": [
                {**item, "sha256": "0" * 64}]}, [("image/png", raw)])
        with self.assertRaisesRegex(NvidiaConfigurationError, "mime and magic"):
            model.decide_with_images({"picture_evidence": [item]}, [("image/png", b"not-png-data")])


if __name__ == "__main__":
    unittest.main()
