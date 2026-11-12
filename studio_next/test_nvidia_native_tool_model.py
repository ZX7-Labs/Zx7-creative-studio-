"""Credential-free contracts for native typed NVIDIA model -> common BODY."""
import base64
import hashlib
import json
from io import BytesIO
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from studio_next.nvidia_native_tool_model import (
    NvidiaNativeToolCreativeModel, NvidiaOmniNativeToolCreativeModel,
    NVIDIA_OMNI_AUDIO_MODEL_ID, _provider_function,
)
from studio_next.nvidia_model import NvidiaConfigurationError, NvidiaModelSettings
from studio_next.providers import LocalModelOutputError


def _context(compact=False):
    return {
        "available_actions": ["search", "describe", "invoke"] if compact else
                             ["discover", "describe", "invoke"],
        "compact_tool_catalog": compact,
        "actual_granted_native_tools": ["get_project", "add_asset_to_timeline"],
        "selectable_native_tools": ["add_asset_to_timeline"] if compact else [],
        "inspectable_native_tools": [],
        "host_native_tool_contracts": [
            {"name": "add_asset_to_timeline",
             "description": "Add a real imported asset to the timeline",
             "input_schema": {"type": "object", "properties": {
                 "assetId": {"type": "string"},
                 "previewOnly": {"type": "boolean"}},
                 "required": ["assetId"], "additionalProperties": False}},
        ] if compact else [
            {"name": "get_project", "description": "Actual project state",
             "input_schema": {"type": "object", "properties": {},
                              "additionalProperties": False}},
            {"name": "add_asset_to_timeline",
             "description": "Place one imported asset",
             "input_schema": {"type": "object", "properties": {
                 "assetId": {"type": "string"},
                 "previewOnly": {"type": "boolean"}},
                 "required": ["assetId"], "additionalProperties": False}},
        ],
    }


def _reply(name, arguments, *, extra_calls=None):
    calls = [{"id": "call-1", "type": "function",
              "function": {"name": name, "arguments": arguments}}]
    calls.extend(extra_calls or [])
    return BytesIO(json.dumps({
        "choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": calls}}],
        "usage": {"prompt_tokens": 111, "completion_tokens": 12, "total_tokens": 123},
    }).encode())


class NativeTypedNvidiaTransportTests(unittest.TestCase):
    def test_real_host_schema_is_sent_as_provider_native_function_not_generic_envelope(self):
        captured = []
        class Opener:
            def open(self, request, timeout):
                captured.append(json.loads(request.data))
                return _reply(_provider_function("add_asset_to_timeline"),
                              '{"inputs":{"assetId":"native-source","previewOnly":false},'
                              '"reason":"Place original source"}')
        context = _context()
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-"+"A"*32}), patch(
                "studio_next.nvidia_model.build_opener", return_value=Opener()):
            model = NvidiaNativeToolCreativeModel(system_prompt="injected legacy instructions")
            decision = model.decide(context)
        self.assertEqual(decision, {
            "action": "invoke",
            "arguments": {"tool": "add_asset_to_timeline",
                          "inputs": {"assetId": "native-source", "previewOnly": False}},
            "reason": "Place original source"})
        self.assertEqual(model.last_call_usage["total_tokens"], 123)
        body = captured[0]
        self.assertEqual(body["tool_choice"], "required")
        self.assertFalse(body["parallel_tool_calls"])
        names = {t["function"]["name"] for t in body["tools"]}
        self.assertEqual(names, {_provider_function("get_project"),
                                 _provider_function("add_asset_to_timeline")})
        typed = next(t["function"]["parameters"] for t in body["tools"]
                     if t["function"]["name"] == _provider_function("add_asset_to_timeline"))
        self.assertEqual(typed["properties"]["inputs"], context[
            "host_native_tool_contracts"][1]["input_schema"])
        self.assertNotIn("host_native_tool_contracts",
                         body["messages"][1]["content"])
        self.assertNotIn("nvapi-", json.dumps(body))
        self.assertNotIn("response_format", body)
        self.assertEqual(len(context["host_native_tool_contracts"]), 2)

    def test_selected_indexed_tools_are_the_only_native_functions_and_search_is_available(self):
        context = _context(compact=True)
        functions, mapping = NvidiaNativeToolCreativeModel._tool_surface(context)
        self.assertEqual({x["function"]["name"] for x in functions},
                         {_provider_function("add_asset_to_timeline"),
                          "zx7_search_host_capabilities"})
        self.assertNotIn(_provider_function("get_project"), mapping)

    def test_host_grant_mismatch_duplicate_names_and_bad_schemas_rejected_before_network(self):
        model = NvidiaNativeToolCreativeModel(system_prompt="ignored")
        failing = [
            dict(_context(), host_native_tool_contracts=[
                {"name": "delete_all", "description": "", "input_schema": {"type": "object"}}]),
            dict(_context(), host_native_tool_contracts=
                 _context()["host_native_tool_contracts"] * 2),
            dict(_context(), host_native_tool_contracts=[
                {"name": "get_project", "description": "",
                 "input_schema": {"type": "array"}}]),
            dict(_context(), actual_granted_native_tools=["get_project"]),
            dict(_context(), compact_tool_catalog="false"),
        ]
        with patch("studio_next.nvidia_model.build_opener") as opener:
            for context in failing:
                with self.subTest(context=str(context)[:40]), self.assertRaises(
                        NvidiaConfigurationError):
                    model.decide(context)
            opener.assert_not_called()

    def test_unknown_or_double_tool_call_never_creates_native_decision(self):
        for bad_name, extra in (
            ("unknown_tool", None),
            (_provider_function("get_project"), [
                {"id": "call-2", "type": "function", "function": {
                    "name": _provider_function("get_project"), "arguments": "{}"}}]),
        ):
            class Opener:
                def open(self, request, timeout):
                    return _reply(bad_name,
                                  '{"inputs":{},"reason":"actual model choice"}',
                                  extra_calls=extra)
            with self.subTest(bad_name=bad_name), patch.dict(
                    os.environ, {"NVIDIA_API_KEY": "nvapi-"+"B"*32}), patch(
                    "studio_next.nvidia_model.build_opener", return_value=Opener()):
                with self.assertRaises(LocalModelOutputError):
                    NvidiaNativeToolCreativeModel(system_prompt="test").decide(_context())

    def test_json_duplicate_keys_untyped_inputs_and_fake_reason_never_execute(self):
        malformed = [
            '{"inputs":{},"reason":"A","reason":"B"}',
            '{"inputs":[],"reason":"A"}',
            '{"inputs":{},"reason":"   "}',
            '{"inputs":{},"reason":"A","unexpected":"arg"}',
        ]
        for value in malformed:
            class Opener:
                def open(self, request, timeout):
                    return _reply(_provider_function("get_project"), value)
            with self.subTest(value=value), patch.dict(
                    os.environ, {"NVIDIA_API_KEY": "nvapi-"+"C"*32}), patch(
                    "studio_next.nvidia_model.build_opener", return_value=Opener()):
                with self.assertRaises(LocalModelOutputError):
                    NvidiaNativeToolCreativeModel(system_prompt="test").decide(_context())

    def test_host_finish_requires_actual_evidence_not_a_model_claim(self):
        context = _context()
        functions, mapping = NvidiaNativeToolCreativeModel._tool_surface(context)
        self.assertNotIn("zx7_finish_verified_session", mapping)
        context["available_actions"].append("finish")
        functions, mapping = NvidiaNativeToolCreativeModel._tool_surface(context)
        self.assertIn("zx7_finish_verified_session", mapping)
        self.assertIn("zx7_finish_verified_session",
                      [x["function"]["name"] for x in functions])

    def test_real_native_jpeg_is_sent_with_correct_provenance_and_no_export_claim(self):
        """Source-pinned editable-timeline JPEG is visually reviewable by
        NVIDIA but must never impersonate a verified decoded export frame.
        A mocked HTTP boundary proves transport formatting, NOT live vision
        quality or model autonomy.
        """
        import base64
        import hashlib
        jpeg = b"\xff\xd8\xff\xe0" + b"synthetic-renderer-JPEG" + b"\xff\xd9"
        sha = hashlib.sha256(jpeg).hexdigest()
        ctx = {**_context(),
               "native_picture_origin":
                   "live_editable_timeline_preview_not_verified_export",
               "observed_picture_sha256": [sha],
               "missing_completion_evidence": [
                   "physical_export_verified", "verified_export_frame_observed"]}
        recorded = []
        class Opener:
            def open(self, request, timeout):
                recorded.append(json.loads(request.data))
                return _reply(_provider_function("get_project"),
                              '{"inputs":{},"reason":"Read current native project"}')
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-"+"E"*32}), patch(
                "studio_next.nvidia_model.build_opener", return_value=Opener()):
            model = NvidiaNativeToolCreativeModel(
                system_prompt="Trusted actual editor model",
                allow_image_upload=True)
            answer = model.decide_with_images(ctx, [("image/jpeg", jpeg)])
        self.assertEqual(answer["arguments"]["tool"], "get_project")
        self.assertEqual(len(recorded), 1)
        payload = recorded[0]
        self.assertEqual(payload["tool_choice"], "required")
        self.assertFalse(payload["parallel_tool_calls"])
        text, label, image = payload["messages"][1]["content"]
        self.assertEqual(text["type"], "text")
        facts = json.loads(text["text"])
        self.assertEqual(facts["native_picture_origin"],
                         "live_editable_timeline_preview_not_verified_export")
        self.assertIn("physical_export_verified",
                      facts["missing_completion_evidence"])
        self.assertEqual(json.loads(label["text"])["sha256"], sha)
        self.assertEqual(image["type"], "image_url")
        self.assertEqual(image["image_url"]["url"].split(",", 1)[0],
                         "data:image/jpeg;base64")
        self.assertEqual(base64.b64decode(
            image["image_url"]["url"].split(",", 1)[1]), jpeg)
        self.assertNotIn("nvapi-", json.dumps(payload))
        self.assertFalse(ctx.get("physical_export_verified", False))

    def test_synthetic_image_upload_only_with_explicit_host_permission(self):
        from hashlib import sha256
        img = b"\\x89PNG\\r\\n\\x1a\\n" + b"synthetic-test-frame"
        entry = {"job_id": "export-test", "path": "frame.png", "sha256": sha256(img).hexdigest()}
        ctx = dict(_context(), picture_evidence=[entry])
        model = NvidiaNativeToolCreativeModel(system_prompt="ignored")
        with self.assertRaises(NvidiaConfigurationError):
            model.decide_with_images(ctx, [("image/png", img)])
        model = NvidiaNativeToolCreativeModel(system_prompt="ignored", allow_image_upload=True)
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-"+"D"*32}):
            with self.assertRaises(NvidiaConfigurationError):
                model.decide_with_images(
                    dict(ctx, picture_evidence=[dict(entry, sha256="0"*64)]),
                    [("image/png", img)])


class OmniOriginalWavNativeToolTests(unittest.TestCase):
    @staticmethod
    def _wav():
        from io import BytesIO
        import wave
        output = BytesIO()
        with wave.open(output, "wb") as track:
            track.setnchannels(1)
            track.setsampwidth(2)
            track.setframerate(16000)
            track.writeframes(bytes([1, 0]) * 400)
        return output.getvalue()

    @staticmethod
    def _model(*, allowed=False):
        return NvidiaOmniNativeToolCreativeModel(
            NvidiaModelSettings(
                model_id=NVIDIA_OMNI_AUDIO_MODEL_ID,
                sampling={"chat_template_kwargs": {"enable_thinking": False}}),
            system_prompt="Inspect authorized native footage and sound",
            allow_original_audio_upload=allowed)

    def test_consent_false_wrong_model_and_ambiguous_custody_reject_before_network(self):
        sample = self._wav()
        digest = hashlib.sha256(sample).hexdigest()
        context = {**_context(), "audio_evidence": {
            "wav_sha256": digest, "export_sha256": "a" * 64}}
        with self.assertRaises(NvidiaConfigurationError):
            NvidiaOmniNativeToolCreativeModel(
                NvidiaModelSettings(), system_prompt="no",
                allow_original_audio_upload=True)
        with patch("studio_next.nvidia_model.build_opener") as network:
            model = self._model()
            with self.assertRaises(NvidiaConfigurationError):
                model.decide_with_audio(context, [("audio/wav", sample)])
            permitted = self._model(allowed=True)
            for evidence, raw in (
                ({"wav_sha256": "b" * 64, "export_sha256": "a" * 64}, sample),
                ({"wav_sha256": digest, "export_sha256": "malformed"}, sample),
                (context["audio_evidence"], b"Not a real wave"),
            ):
                with self.subTest(evidence=evidence, size=len(raw)):
                    with self.assertRaises(NvidiaConfigurationError):
                        permitted.decide_with_audio(
                            {**_context(), "audio_evidence": evidence},
                            [("audio/wav", raw)])
            with self.assertRaises(NvidiaConfigurationError):
                permitted.decide_with_audio(context, [("audio/wav", sample)] * 2)
            network.assert_not_called()

    def test_sha_bound_raw_wav_enters_only_separately_opted_in_omni_tool_request(self):
        sample = self._wav()
        digest = hashlib.sha256(sample).hexdigest()
        original = {**_context(), "audio_evidence": {
            "export_sha256": "a" * 64, "wav_sha256": digest}}
        captured = []
        class Opener:
            def open(self, request, timeout):
                captured.append(json.loads(request.data))
                return _reply(_provider_function("get_project"),
                              '{"inputs":{},"reason":"Inspect timed real audio evidence"}')
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-" + "Z" * 32}), patch(
                "studio_next.nvidia_model.build_opener", return_value=Opener()):
            result = self._model(allowed=True).decide_with_audio(
                original, [("audio/wav", sample)])
        self.assertEqual(result["action"], "invoke")
        self.assertEqual(result["arguments"], {"tool": "get_project", "inputs": {}})
        parts = captured[0]["messages"][1]["content"]
        self.assertEqual([part["type"] for part in parts], ["text", "text", "audio_url"])
        self.assertEqual(json.loads(parts[1]["text"])["original_wav_sha256"], digest)
        self.assertEqual(base64.b64decode(parts[2]["audio_url"]["url"].split(",", 1)[1]),
                         sample)
        self.assertNotIn("host_native_tool_contracts", parts[0]["text"])
        self.assertNotIn("nvapi-", json.dumps(captured))
        self.assertEqual(original["audio_evidence"]["wav_sha256"], digest)


    def test_native_session_selects_omni_only_with_separate_wav_consent(self):
        from studio_next.native_editor_session import native_decision_model
        args = SimpleNamespace(
            provider="nvidia", base_url="http://127.0.0.1:8080",
            structured_actions=True, model_id=NVIDIA_OMNI_AUDIO_MODEL_ID,
            model_timeout=180, allow_cloud_image_upload=False,
            allow_cloud_original_wav_upload=False, allow_public_research=False)
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-" + "Q" * 32}):
            disabled = native_decision_model(args)
            self.assertIsInstance(disabled, NvidiaOmniNativeToolCreativeModel)
            self.assertFalse(disabled.allow_original_audio_upload)
            args.allow_cloud_original_wav_upload = True
            enabled = native_decision_model(args)
            self.assertIsInstance(enabled, NvidiaOmniNativeToolCreativeModel)
            self.assertTrue(enabled.allow_original_audio_upload)
            self.assertEqual(enabled.settings.model_id, NVIDIA_OMNI_AUDIO_MODEL_ID)
            args.model_id = "nvidia/nemotron-3.5-super-vl-120b-a12b"
            with self.assertRaisesRegex(ValueError, "Original cloud WAV"):
                native_decision_model(args)

    def test_owner_and_native_parsers_keep_raw_wav_consent_disabled_by_default(self):
        from studio_next.native_editor_session import build_parser as native_parser
        from studio_next.studio_cli import main as owner_main
        # Native parser requires no remote request, files or model credentials.
        required = ["--source", "/tmp/test-source",
                    "--config", "/tmp/grants.json", "--state", "/tmp/native-state",
                    "--brief-file", "/tmp/brief.txt", "--receipt", "/tmp/receipt.jsonl",
                    "--model-id", NVIDIA_OMNI_AUDIO_MODEL_ID]
        args = native_parser().parse_args(required)
        self.assertFalse(args.allow_cloud_original_wav_upload)
        self.assertTrue(native_parser().parse_args(
            required + ["--allow-cloud-original-wav-upload"]).allow_cloud_original_wav_upload)
        # This is a parser-level safety assertion; no run/HTTP is requested.
        from unittest.mock import patch as mock_patch
        with mock_patch("studio_next.studio_cli.run_workspace") as run:
            owner_main(["run", "/tmp/nonexistent-owner", "--brief", "test"])
            kwargs = run.call_args.kwargs
        self.assertFalse(kwargs["allow_cloud_original_wav_upload"])



if __name__ == "__main__":
    unittest.main()
