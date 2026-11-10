"""Credential-bound NVIDIA provider tests: no real key, money or network used."""
from __future__ import annotations

from io import BytesIO
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from studio_next.nvidia_model import (
    NvidiaConfigurationError, NvidiaCreativeModel, NvidiaModelSettings,
    NvidiaTransportError,
)


def _reply(body='{"action":"finish","reason":"tested"}'):
    return BytesIO(json.dumps({
        "choices": [{"finish_reason": "stop", "message": {"content": body}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 15, "total_tokens": 27}
    }).encode())


class NvidiaProviderContractTest(unittest.TestCase):
    def test_validated_host_owned_cloud_model(self):
        good = NvidiaModelSettings()
        self.assertEqual(good.model_id, "nvidia/nemotron-3.5-super-vl-120b-a12b")
        for changes in (
            {"base_url": "http://127.0.0.1:12345"},
            {"base_url": "https://attacker.example"},
            {"model_id": "../other"},
            {"timeout_seconds": 0},
            {"max_tokens": 999999},
            {"sampling": {"model": "other"}},
            {"sampling": {"response_format": {"type": "json_schema"}}},
            {"sampling": {"temperature": 2}},
            {"sampling": {"seed": True}},
            {"sampling": {"chat_template_kwargs": {"unexpected": True}}},
        ):
            with self.subTest(changes=changes), self.assertRaises(NvidiaConfigurationError):
                NvidiaModelSettings(**changes)

    def test_published_nvidia_reasoning_config_is_explicit_and_bounded(self):
        config = NvidiaModelSettings(
            max_tokens=8192, sampling={
                "temperature": 1.0, "top_p": 0.95,
                "chat_template_kwargs": {
                    "enable_thinking": True, "medium_effort": True}})
        self.assertEqual(config.max_tokens, 8192)
        for bad in (
            {"enable_thinking": "true"},
            {"enable_thinking": False, "medium_effort": True},
            {"enable_thinking": True, "medium_effort": False},
            {"enable_thinking": True, "medium_effort": "true"},
            {"enable_thinking": True, "unknown_effort": True},
            {"medium_effort": True},
        ):
            with self.subTest(kwargs=bad), self.assertRaises(NvidiaConfigurationError):
                NvidiaModelSettings(sampling={"chat_template_kwargs": bad})
        with self.assertRaises(NvidiaConfigurationError):
            NvidiaModelSettings(max_tokens=8193)
        # A frozen dataclass does not freeze a nested dictionary. Mutation
        # after validation must fail before ANY credentialed provider egress.
        from unittest.mock import patch
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-" + "A"*32}):
            config.sampling["chat_template_kwargs"]["invented"] = True
            with self.assertRaises(NvidiaConfigurationError):
                NvidiaCreativeModel(config)._open_request({
                    "model": config.model_id, "stream": False,
                    "response_format": {"type": "json_object"}})

    def test_hosted_reasoning_effort_wire_is_validated_before_egress(self):
        # The hosted endpoint documents none/low/high; not "medium".
        settings = NvidiaModelSettings(
            max_tokens=8192, sampling={
                "temperature": 1.0, "top_p": 0.95,
                "reasoning_effort": "low"})
        seen = []
        class Opener:
            def open(self, request, timeout):
                seen.append((json.loads(request.data), timeout))
                return _reply('{"action":"finish","reason":"wire test"}')
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-" + "Y"*32}), patch(
                "studio_next.nvidia_model.build_opener", return_value=Opener()):
            self.assertEqual(
                NvidiaCreativeModel(settings).decide({"brief": "Synthetic"}),
                {"action": "finish", "reason": "wire test"})
        self.assertEqual(len(seen), 1)
        request, timeout = seen[0]
        self.assertEqual(request["reasoning_effort"], "low")
        self.assertNotIn("chat_template_kwargs", request)
        self.assertEqual(request["max_tokens"], 8192)
        self.assertEqual(timeout, 180)
        for invalid in ("medium", "MEDIUM", "", True, 0, None):
            with self.subTest(invalid=invalid), self.assertRaises(
                    NvidiaConfigurationError):
                NvidiaModelSettings(sampling={"reasoning_effort": invalid})
        with self.assertRaisesRegex(NvidiaConfigurationError, "Conflicting"):
            NvidiaModelSettings(sampling={
                "reasoning_effort": "low",
                "chat_template_kwargs": {"enable_thinking": True}})
        # Mutation after settings creation must never reach credentials/network.
        settings.sampling["reasoning_effort"] = "medium"
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-" + "Y"*32}), patch(
                "studio_next.nvidia_model.build_opener") as network:
            with self.assertRaisesRegex(
                    NvidiaConfigurationError, "reasoning_effort"):
                NvidiaCreativeModel(settings)._open_request({
                    "model": settings.model_id, "stream": False,
                    "response_format": {"type": "json_object"}})
            network.assert_not_called()

    def test_no_key_no_network_and_no_key_in_settings(self):
        class Never:
            def open(self, *args, **kwargs):
                raise AssertionError("No network permitted")
        with patch.dict(os.environ, {"NVIDIA_API_KEY": ""}), patch(
                "studio_next.nvidia_model.build_opener", return_value=Never()) as opener:
            model = NvidiaCreativeModel()
            with self.assertRaisesRegex(NvidiaConfigurationError, "NVIDIA_API_KEY"):
                model.decide({"brief": "No credential available"})
            opener.assert_not_called()
        self.assertNotIn("nvapi-", repr(NvidiaModelSettings()))

    def test_opt_in_remote_request_reuses_strict_model_decoder(self):
        credential = "nvapi-" + "Z" * 32
        record = []
        class Opener:
            def open(self, req, timeout):
                record.append((req, timeout))
                return _reply('{"action":"finish","reason":"remote test"}')
        with patch.dict(os.environ, {"NVIDIA_API_KEY": credential}), patch(
                "studio_next.nvidia_model.build_opener", return_value=Opener()):
            model = NvidiaCreativeModel()
            self.assertEqual(model.decide({"brief": "Tell an original story"}),
                             {"action": "finish", "reason": "remote test"})
        self.assertEqual(model.last_call_usage["total_tokens"], 27)
        self.assertEqual(len(record), 1)
        req, timeout = record[0]
        self.assertEqual(req.full_url,
                         "https://integrate.api.nvidia.com/v1/chat/completions")
        self.assertEqual(req.get_header("Authorization"), "Bearer " + credential)
        self.assertEqual(timeout, 180)
        body = json.loads(req.data)
        self.assertEqual(body["model"], "nvidia/nemotron-3.5-super-vl-120b-a12b")
        self.assertFalse(body["stream"])
        self.assertEqual(body["max_tokens"], 2048)
        self.assertNotIn("response_format", body)
        self.assertEqual(body["chat_template_kwargs"], {"enable_thinking": False})
        self.assertNotIn(credential, req.data.decode())

    def test_private_images_need_separate_host_egress_permission(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-" + "Z" * 32}):
            model = NvidiaCreativeModel()
            with self.assertRaisesRegex(NvidiaConfigurationError, "Cloud image upload disabled"):
                model.decide_with_images({}, [("image/png", b"\x89PNG\r\n\x1a\n")])
            with self.assertRaisesRegex(NvidiaConfigurationError, "no verified original-WAV"):
                model.decide_with_audio({}, [])

    def test_remote_http_error_cannot_echo_sensitive_body(self):
        credential = "nvapi-" + "P" * 32
        class Opener:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 401, "private " + credential,
                                {}, BytesIO(b"private-media"))
        with patch.dict(os.environ, {"NVIDIA_API_KEY": credential}), patch(
                "studio_next.nvidia_model.build_opener", return_value=Opener()):
            with self.assertRaises(NvidiaTransportError) as observed:
                NvidiaCreativeModel().decide({"secret": "private-media"})
        self.assertNotIn(credential, str(observed.exception))
        self.assertNotIn("private-media", str(observed.exception))

    def test_hosted_transport_timeout_is_redacted_and_not_retried(self):
        secret = "nvapi-" + "Q" * 32
        for fault, expected in (
            (URLError(TimeoutError("private prompt " + secret)), "transport timed out"),
            (TimeoutError("private prompt " + secret), "transport timed out"),
            (URLError("private network " + secret), "connection failed"),
        ):
            with self.subTest(reason=expected):
                class Opener:
                    calls = 0
                    def open(self, req, timeout):
                        self.calls += 1
                        self.timeout = timeout
                        raise fault
                opener = Opener()
                with patch.dict(os.environ, {"NVIDIA_API_KEY": secret}), patch(
                        "studio_next.nvidia_model.build_opener", return_value=opener):
                    with self.assertRaisesRegex(NvidiaTransportError, expected) as caught:
                        NvidiaCreativeModel(
                            NvidiaModelSettings(timeout_seconds=180)
                        ).decide({"brief": "private prompt"})
                self.assertEqual(opener.calls, 1)
                self.assertEqual(opener.timeout, 180)
                self.assertNotIn(secret, str(caught.exception))
                self.assertNotIn("private prompt", str(caught.exception))

    def test_untrusted_response_envelope_never_echoes_private_fields(self):
        credential = "nvapi-" + "Z" * 32
        class Opener:
            def open(self, request, timeout):
                return BytesIO(b'{"private-media":1,"private-media":2}')
        with patch.dict(os.environ, {"NVIDIA_API_KEY": credential}), patch(
                "studio_next.nvidia_model.build_opener", return_value=Opener()):
            with self.assertRaises(NvidiaTransportError) as caught:
                NvidiaCreativeModel().decide({"brief": "private-media"})
        self.assertNotIn("private-media", str(caught.exception))

    def test_cloud_images_bounded_even_with_explicit_consent(self):
        model = NvidiaCreativeModel(allow_image_upload=True)
        with self.assertRaisesRegex(NvidiaConfigurationError, "egress budget"):
            model.decide_with_images({}, [("image/png", b"x" * 10)] * 5)

    def test_body_cli_selects_actual_nvidia_brain_without_network(self):
        from studio_next import body_service
        chosen = []
        def start(root, *, secret, port, workers, creative_model):
            chosen.append(creative_model)
        args = ["zx7-body", "--workspace-root", "/tmp/zx7-nvidia-contract",
                "--creative-provider", "nvidia", "--creative-model",
                "nvidia/nemotron-3.5-super-vl-120b-a12b"]
        with patch.dict(os.environ, {"ZX7_BODY_API_TOKEN": "P" * 48,
                                     "NVIDIA_API_KEY": "nvapi-" + "T" * 32}), patch(
                "studio_next.body_service.start_local_body_service", side_effect=start), patch(
                "sys.argv", args):
            body_service.main()
        self.assertEqual(len(chosen), 1)
        self.assertIsInstance(chosen[0], NvidiaCreativeModel)
        self.assertEqual(chosen[0].settings.provider_id, "nvidia")
        self.assertFalse(chosen[0].allow_image_upload)

    def test_host_startup_credential_preflight_is_no_network(self):
        from studio_next import body_service
        args = ["zx7-body", "--workspace-root", "/tmp/zx7-nvidia-contract",
                "--creative-provider", "nvidia", "--creative-model",
                "nvidia/nemotron-3.5-super-vl-120b-a12b"]
        with patch.dict(os.environ, {"ZX7_BODY_API_TOKEN": "P" * 48,
                                     "NVIDIA_API_KEY": ""}), patch("sys.argv", args), patch(
                "studio_next.body_service.start_local_body_service") as start, patch(
                "studio_next.nvidia_model.build_opener") as opener:
            with self.assertRaisesRegex(NvidiaConfigurationError, "NVIDIA_API_KEY"):
                body_service.main()
            start.assert_not_called()
            opener.assert_not_called()

    def test_post_validation_mutation_cannot_replace_model_context(self):
        model = NvidiaCreativeModel()
        model.settings.sampling["messages"] = [{"role": "user", "content": "override"}]
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-" + "Z" * 32}), patch(
                "studio_next.nvidia_model.build_opener") as opener:
            with self.assertRaisesRegex(NvidiaConfigurationError, "after host admission"):
                model.decide({"brief": "Keep original context"})
            opener.assert_not_called()

    def test_cloud_does_not_pretend_nvidia_enforces_json_schema(self):
        settings = NvidiaModelSettings()
        model = NvidiaCreativeModel(settings)
        model.settings.sampling["response_format"] = {
            "type": "json_schema", "json_schema": {"name": "tool", "strict": True,
                                                    "schema": {"type": "object"}}}
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-" + "Z" * 32}), patch(
                "studio_next.nvidia_model.build_opener") as opener:
            with self.assertRaisesRegex(NvidiaConfigurationError, "structured-output schemas"):
                model.decide({})
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
