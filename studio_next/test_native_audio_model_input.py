"""Original decoded WAV is genuinely passed to compatible local model inputs.

These are transport/rights custody tests, not evidence that a neural model
heard music or judged professional mix quality. Actual model trial remains
separately required.
"""
import asyncio
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

from studio_next.providers import LocalCreativeModel,LocalModelSettings
from studio_next.native_creative_control import NativeCreativeControl,NativeCreativeControlError


def wav_bytes():
    buff=io.BytesIO()
    with wave.open(buff,"wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(16000)
        sound.writeframes((b"\x10\x03" * 16000))
    return buff.getvalue()


def receipt(audio):
    return {
        "kind":"verified_native_editor_bounded_audio_excerpt",
        "export_sha256":"a"*64,
        "wav_sha256":hashlib.sha256(audio).hexdigest(),
        "preview_downmixed_and_resampled":True,
        "requested_start_seconds":1,
        "requested_duration_seconds":1,
        "observed_audio_duration_seconds":1,
        "exact_original_audio_pts_proven":False,
        "original_multichannel_mix_proven":False,
    }


class FakeReply:
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,length):
        return json.dumps({"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}).encode()[:length]


class AuditoryModelTransport(unittest.TestCase):
    def setUp(self):
        self.model=LocalCreativeModel(LocalModelSettings(model_id="compatible-local-audio-model"))

    def test_binary_sound_and_source_proof_reach_model_as_audio_not_text(self):
        audio=wav_bytes()
        captured=[]
        def intercept(req,timeout):
            captured.append(json.loads(req.data))
            return FakeReply()
        evidence={"export_sha256":"a"*64,"wav_sha256":hashlib.sha256(audio).hexdigest()}
        with patch("studio_next.providers.urlopen",side_effect=intercept):
            self.assertEqual(self.model.decide_with_audio({"brief":"Listen","audio_evidence":evidence},
                           [("audio/wav",audio)]),{})
        self.assertEqual(len(captured),1)
        parts=captured[0]["messages"][1]["content"]
        self.assertEqual([item["type"] for item in parts],["text","text","input_audio"])
        self.assertEqual(base64.b64decode(parts[2]["input_audio"]["data"]),audio)
        self.assertEqual(parts[2]["input_audio"]["format"],"wav")
        self.assertEqual(json.loads(parts[1]["text"])["wav_sha256"],evidence["wav_sha256"])
        self.assertFalse(json.loads(parts[1]["text"])["original_multichannel_mastering_proven"])

    def test_local_server_usage_is_reported_not_invented_or_verified(self):
        class ReportedUsageReply(FakeReply):
            def read(self, length):
                return json.dumps({"usage": {"prompt_tokens": 71,
                                            "completion_tokens": 9,
                                            "total_tokens": 80,
                                            "untrusted_extra": "do not persist"},
                                   "choices": [{"finish_reason": "stop",
                                                "message": {"content": "{}"}}]}).encode()[:length]
        class UnreportedUsageReply(FakeReply):
            pass
        with patch("studio_next.providers.urlopen",
                   return_value=ReportedUsageReply()):
            self.model.decide({"test": "provider claims tokens"})
        self.assertEqual(self.model.last_call_usage,
                         {"prompt_tokens": 71, "completion_tokens": 9,
                          "total_tokens": 80})
        with patch("studio_next.providers.urlopen",
                   return_value=UnreportedUsageReply()):
            self.model.decide({"test": "no usage field"})
        self.assertIsNone(self.model.last_call_usage)

    def test_wrong_custody_format_size_and_mixed_images_fail_before_http(self):
        audio=wav_bytes()
        context={"audio_evidence":{"export_sha256":"a"*64,"wav_sha256":"b"*64}}
        with patch("studio_next.providers.urlopen") as net:
            cases=[
                (context,[("audio/wav",audio)]),
                ({},[("audio/wav",audio)]),
                ({"audio_evidence":{"export_sha256":"a"*64,
                   "wav_sha256":hashlib.sha256(audio).hexdigest()}},
                   [("audio/mp3",audio)]),
                ({"audio_evidence":{"export_sha256":"a"*64,
                   "wav_sha256":hashlib.sha256(audio).hexdigest()}},
                   [("audio/wav",b"not a wave file"*5)]),
            ]
            for ctx,sounds in cases:
                with self.subTest(ctx=ctx,sounds=sounds[0][0]), self.assertRaises(ValueError):
                    self.model.decide_with_audio(ctx,sounds)
            net.assert_not_called()


class ScriptedAudioModel:
    settings=SimpleNamespace(model_id="fixture-NOT-neural")
    def __init__(self):self.decisions=0;self.audio_input=None
    def decide(self,context):
        self.decisions+=1
        if self.decisions == 1:
            return {"action":"invoke","arguments":{"tool":"zx7_verify_native_export",
                           "inputs":{"path":"/host/verified.mp4"}},
                    "reason":"test fixture must verify export first"}
        return {"action":"invoke","arguments":{"tool":"zx7_observe_verified_export_audio",
                       "inputs":{"path":"/host/verified.mp4","start_seconds":1,
                                 "duration_seconds":1}},"reason":"test fixture requests actual WAV"}
    def decide_with_audio(self,context,audio):
        self.audio_input=(context,audio)
        return {"action":"finish","arguments":{"summary":"Transport tested, listening NOT independently proven"},
                "reason":"test fixture only"}


class Session:
    def __init__(self,audio):
        self.audio=audio
        self.corrupt=False
        self.corrupt_timing=False
        self.calls=0
    async def list_tools(self):
        return SimpleNamespace(tools=[SimpleNamespace(
            name="zx7_verify_native_export",description="Independently verified export",
            input_schema={"type":"object"}), SimpleNamespace(
            name="zx7_observe_verified_export_audio",description="Source-bound native audio",
            input_schema={"type":"object"})])
    async def call_tool(self,name,inputs):
        self.calls+=1
        if name == "zx7_verify_native_export":
            return SimpleNamespace(is_error=False, content=[SimpleNamespace(
                type="text", text=json.dumps({
                    "physical_export_verified": True,
                    "native_export_sha256": "a"*64,
                    "human_or_artistic_quality_approved": False}))])
        r=receipt(self.audio)
        if self.corrupt:r["wav_sha256"]="f"*64
        if self.corrupt_timing:r["requested_duration_seconds"]=-1
        return SimpleNamespace(is_error=False,content=[
            SimpleNamespace(type="text",text=json.dumps(r)),
            SimpleNamespace(type="audio",mime_type="audio/wav",
                            data=base64.b64encode(self.audio).decode())])


class ActualNativeAudioRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_audio_reaches_next_model_turn_with_sha_bound_custody(self):
        audio=wav_bytes()
        model=ScriptedAudioModel()
        session=Session(audio)
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"private.journal"
            result=await NativeCreativeControl(session,model,receipt_path=p,max_turns=4).run(
                "Review the scene's sound")
            self.assertEqual(result["status"],"model_finished_unverified")
            self.assertEqual(session.calls,2)
            ctx,received=model.audio_input
            self.assertEqual(received,[("audio/wav",audio)])
            self.assertEqual(ctx["audio_evidence"]["wav_sha256"],hashlib.sha256(audio).hexdigest())
            self.assertEqual(ctx["audio_evidence"]["requested_start_seconds"],1)
            self.assertEqual(ctx["audio_evidence"]["requested_duration_seconds"],1)
            self.assertFalse(ctx["audio_evidence"]["exact_original_audio_pts_proven"])
            serialized=p.read_text()
            self.assertNotIn(base64.b64encode(audio).decode()[:100],serialized)
            self.assertIn('"audio_sent_to_model_for_next_decision":true',serialized)
            self.assertIn('"independently_verified_export_sha256":"'+("a"*64)+'"',serialized)
            self.assertIn('"observed_export_sha256":"'+("a"*64)+'"',serialized)
            self.assertFalse(result["artistic_quality_independently_approved"])


    async def test_host_verified_audio_reaches_real_omni_adapter_without_extra_native_grants(self):
        """Native controller, actual source receipt and NVIDIA adapter use one grant path.

        A mocked credentialed HTTP opener proves the bytes and tool envelope
        without consuming credits or making any genuine semantic perception claim.
        """
        import os
        from studio_next.nvidia_model import NvidiaModelSettings
        from studio_next.nvidia_native_tool_model import (
            NvidiaOmniNativeToolCreativeModel, NVIDIA_OMNI_AUDIO_MODEL_ID,
            _provider_function, _META_FINISH,
        )
        audio = wav_bytes()
        commands = [
            (_provider_function("zx7_verify_native_export"), {
                "inputs": {"path": "/host/verified.mp4"},
                "reason": "Read the actual verified source first"}),
            (_provider_function("zx7_observe_verified_export_audio"), {
                "inputs": {"path": "/host/verified.mp4",
                           "start_seconds": 1, "duration_seconds": 1},
                "reason": "Hear only the verified export excerpt"}),
            (_META_FINISH, {
                "summary": "Mock transport proven, no subjective judgment",
                "reason": "This was a technical fixture only"}),
        ]
        captured = []
        class Opener:
            def open(self, request, timeout):
                body = json.loads(request.data)
                captured.append(body)
                function, args = commands[len(captured)-1]
                return io.BytesIO(json.dumps({"choices": [{
                    "finish_reason": "tool_calls",
                    "message": {"tool_calls": [{
                        "id": "fixture-call", "type": "function",
                        "function": {"name": function,
                                     "arguments": json.dumps(args)}}]}}],
                    "usage": {"prompt_tokens": 23, "completion_tokens": 7,
                              "total_tokens": 30}}).encode())
        model = NvidiaOmniNativeToolCreativeModel(
            NvidiaModelSettings(model_id=NVIDIA_OMNI_AUDIO_MODEL_ID,
                sampling={"chat_template_kwargs": {"enable_thinking": False}}),
            system_prompt="Use only existing native tools and independent sound evidence",
            allow_original_audio_upload=True)
        session = Session(audio)
        with tempfile.TemporaryDirectory() as root, patch.dict(
                os.environ, {"NVIDIA_API_KEY": "nvapi-" + "A" * 32}), patch(
                "studio_next.nvidia_model.build_opener", return_value=Opener()):
            journal = Path(root) / "private-native-journal.jsonl"
            result = await NativeCreativeControl(
                session, model, receipt_path=journal, max_turns=4,
                host_tool_access={
                    "zx7_verify_native_export": "read",
                    "zx7_observe_verified_export_audio": "read",
                }).run("Inspect the already verified sound source")
            self.assertEqual(result["status"], "model_finished_unverified")
            self.assertEqual(session.calls, 2)
            self.assertEqual(len(captured), 3)
            self.assertIsInstance(captured[0]["messages"][1]["content"], str)
            audio_parts = captured[2]["messages"][1]["content"]
            self.assertEqual([p["type"] for p in audio_parts],
                             ["text", "text", "audio_url"])
            sent = audio_parts[-1]["audio_url"]["url"]
            self.assertTrue(sent.startswith("data:audio/wav;base64,"))
            self.assertEqual(base64.b64decode(sent.split(",",1)[1]), audio)
            self.assertEqual(json.loads(audio_parts[1]["text"])[
                "original_wav_sha256"], hashlib.sha256(audio).hexdigest())
            self.assertNotIn(base64.b64encode(audio).decode()[:100],
                             journal.read_text())
            self.assertNotIn("nvapi-", journal.read_text())
            self.assertFalse(result["artistic_quality_independently_approved"])

    async def test_source_mismatch_rejected_before_model_listening(self):
        audio=wav_bytes()
        session=Session(audio)
        session.corrupt=True
        model=ScriptedAudioModel()
        with self.assertRaisesRegex(NativeCreativeControlError,"verified source"):
            await NativeCreativeControl(session,model,max_turns=3).run("Listen")
        self.assertIsNone(model.audio_input)

    async def test_invalid_timed_receipt_fails_before_model_audio_turn(self):
        audio=wav_bytes()
        session=Session(audio)
        session.corrupt_timing=True
        model=ScriptedAudioModel()
        with self.assertRaisesRegex(NativeCreativeControlError,"timed excerpt provenance"):
            await NativeCreativeControl(session,model,max_turns=3).run("Listen")
        self.assertIsNone(model.audio_input)

    async def test_missing_audio_capability_fails_closed(self):
        audio=wav_bytes()
        session=Session(audio)
        model=ScriptedAudioModel()
        model.decide_with_audio=None
        with self.assertRaisesRegex(NativeCreativeControlError,"audio-capable"):
            await NativeCreativeControl(session,model,max_turns=3).run("Listen")
        self.assertIsNone(model.audio_input)


if __name__=="__main__":
    unittest.main()
