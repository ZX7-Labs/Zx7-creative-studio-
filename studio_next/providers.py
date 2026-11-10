"""Local-first swappable creative-model interfaces.

A provider supplies thinking power. It never obtains tool execution directly:
StudioDirector grants tool permissions and validates selected tool route.
No pretrained model is bundled and no 'best screenwriter' claim is made.
"""
from dataclasses import dataclass, field
import base64
import hashlib
import io
import wave
import json
import math
from urllib.parse import urlsplit
from urllib.request import Request
from .local_model_http import urlopen
from typing import Any


# Model-originated protocol failures only. They are untrusted output, not
# native operations; keep this finite allowlist shared by provider and auditor.
# Every accepted recovery MUST still be bounded, no-dispatch, and authenticated
# by the host journal. Transport/credential/native errors are not in this list.
MODEL_OUTPUT_REJECTION_CODES = frozenset({
    "duplicate_json_field",
    "invalid_json",
    "truncated_response",
    "empty_response",
    "non_object_json",
    "oversize_tool_envelope",
    "tool_choice_count",
    "truncated_tool_decision",
    "missing_or_multiple_function_calls",
    "unexpected_native_function",
    "invalid_native_function_arguments",
    "invalid_tool_response_envelope",
    "missing_native_tool_message",
    "missing_or_multiple_native_tool_calls",
    "unknown_or_ungranted_native_function",
    "invalid_native_function_json",
    "native_function_missing_reason",
    "native_function_inputs_shape",
    "native_metadata_search_shape",
    "native_metadata_describe_shape",
    "native_finish_shape",
    "unrecognized_native_host_action",
    "invalid_native_tool_envelope",
})

class LocalModelOutputError(ValueError):
    """Only model-authored content failed strict decoding; no native action.

    Server envelope/transport errors and controller/schema failures deliberately
    keep their original exception types and remain terminal.
    """

    def __init__(self, code: str):
        if code not in MODEL_OUTPUT_REJECTION_CODES:
            raise ValueError("Unknown model output failure classification")
        self.code = code
        message = ("Duplicate local model JSON field" if code == "duplicate_json_field"
                   else "Invalid model-authored response: " + code)
        super().__init__(message)


def _model_json(raw):
    """Reject ambiguous or non-finite model data before any tool admission."""
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate local model JSON field: " + key)
            value[key] = item
        return value
    def finite_float(raw_number):
        value = float(raw_number)
        if not math.isfinite(value):
            raise ValueError("Local model returned an overflowed JSON number")
        return value
    def reject_constant(value):
        raise ValueError("Local model returned non-finite JSON: " + value)
    return json.loads(raw, object_pairs_hook=unique, parse_float=finite_float,
                      parse_constant=reject_constant)

_CREATIVE_SYSTEM = """You are a studio CREATIVE DIRECTOR, story strategist and editor, not a coding assistant.
Think independently about audience, story, emotional arc, script, artwork, camera, composition,
music, voice, pace and production options. No fixed genre, runtime, scene count, font or render style.
Ground factual claims only in the caller-owned facts and licensed assets.
You have an advertised list of actually installed tools with honest limitations.
Choose when to ask ONE essential question, when to request a useful registered tool,
or when to propose a complete original treatment and justified tool route.
Reply as a JSON object with kind=question, kind=tool or kind=proposal.
A tool request has tool_id and inputs. Proposal has a plan with:
creative_intent, story, scenes, voice_choices, tool_route.
Scenes contain id, purpose, chosen duration_seconds when known, fact_refs and asset_refs.
Do not put fabricated media, invented claims or hidden tool commands in the result.
A producer and independent reviewer will test your decisions. Be specific and self-critical."""

_REVIEW_SYSTEM = """You are the skeptical independent editorial REVIEWER, not the creative author.
Critique the actual proposed work on original hook, emotional pacing, natural dialogue,
clarity, evidence accuracy, meaningful imagery, production tool feasibility,
continuity and sound design. Do not automatically approve. Identify concrete problems,
with exactly where they occur and how to repair them. Do not approve inaccessible
assets or imaginary tools. If no substantive blockers remain, approve.
Return JSON only: {"approved": true/false,
"issues":[{"location":"specific scene/field","reason":"specific flaw","repair":"actionable change"}]}.
You cannot execute tools or overrule caller evidence/security validation."""

@dataclass(frozen=True)
class LocalModelSettings:
    base_url: str = "http://127.0.0.1:8080"
    model_id: str = "local"
    timeout_seconds: int = 480
    max_response_bytes: int = 2000000
    sampling: dict[str, Any] = field(default_factory=dict)
    def __post_init__(self):
        parts=urlsplit(self.base_url)
        if parts.scheme!="http" or parts.hostname not in ("127.0.0.1","localhost","::1") or (
            parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in ("","/")):
            raise ValueError("Only local unauthenticated HTTP model servers are permitted")
        if not isinstance(self.model_id,str) or not self.model_id.strip():
            raise ValueError("Missing model id")
        if not 1 <= self.timeout_seconds <= 3600:
            raise ValueError("Specify a finite timeout for free compute")
        if not 1024 <= self.max_response_bytes <= 50000000:
            raise ValueError("Unsafe response size limit")
        if not isinstance(self.sampling,dict):
            raise ValueError("Sampling options must be a dict")
        if any(k in self.sampling for k in ("messages","model","stream","tools","tool_choice")):
            raise ValueError("Sampling config cannot override messages or model")

class LocalCreativeModel:
    """OpenAI-compatible local model adapter. No expensive cloud calls."""
    def __init__(self,settings:LocalModelSettings,system_prompt:str=_CREATIVE_SYSTEM):
        self.settings=settings
        self.system_prompt=system_prompt
        # Reported tokens come from the local server, not an independent
        # tokenizer. An absent count is unknown; never represent it as zero.
        self.last_call_usage = None

    def _open_request(self, payload):
        """Default strictly-local transport; cloud adapters override explicitly."""
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
        req=Request(self.settings.base_url.rstrip("/")+"/v1/chat/completions",
                    data=data,headers={"Content-Type":"application/json"},method="POST")
        return urlopen(req,timeout=self.settings.timeout_seconds)

    @staticmethod
    def _encode_context(context):
        return json.dumps(context,ensure_ascii=False,allow_nan=False)

    def _invoke(self,role,context,*,images=(),audio=()):
        self.last_call_usage = None
        user_content=self._encode_context(context)
        if images or audio:
            content=[{"type":"text","text":user_content}]
            evidence=context.get("picture_evidence") if isinstance(context,dict) else None
            if evidence is not None and (not isinstance(evidence,list) or len(evidence)!=len(images)):
                raise ValueError("Picture evidence count differs from actual vision inputs")
            for index,(mime,raw) in enumerate(images):
                if mime not in ("image/png","image/jpeg") or not isinstance(raw,bytes) or not 8<=len(raw)<=3000000:
                    raise ValueError("Bounded original PNG/JPEG image bytes required")
                if (mime=="image/png" and not raw.startswith(b"\x89PNG\r\n\x1a\n")) or (
                        mime=="image/jpeg" and not raw.startswith(b"\xff\xd8\xff")):
                    raise ValueError("Original model image bytes do not match their declared media type")
                label={"image_index":index,"image_mime":mime}
                if evidence is not None:
                    meta=evidence[index]
                    if not isinstance(meta,dict) or any(
                            not isinstance(meta.get(key),str) or not meta[key]
                            for key in ("job_id","path","sha256")):
                        raise ValueError("Image input lacks original job/path/SHA witness")
                    if hashlib.sha256(raw).hexdigest()!=meta["sha256"]:
                        raise ValueError("Picture and encoded model image identity mismatch")
                    label.update({"job_id":meta["job_id"],"path":meta["path"],
                                  "sha256":meta["sha256"],"image_payload_matches_evidence_sha256":True})
                # Each inline label is immediately followed by its own binary
                # image. Positional assumptions are insufficient for a model
                # comparing before/after frames from different film jobs.
                content.append({"type":"text","text":json.dumps(label,ensure_ascii=False)})
                content.append({"type":"image_url","image_url":{
                    "url":"data:"+mime+";base64,"+base64.b64encode(raw).decode("ascii")}})
            if audio:
                if images:
                    raise ValueError("Simultaneous video frames and audio need a separately validated backend")
                if len(audio) != 1 or not isinstance(audio[0],tuple) or len(audio[0]) != 2:
                    raise ValueError("Only one bounded original WAV is permitted per native model turn")
                mime,wav=audio[0]
                if mime != "audio/wav" or not isinstance(wav,bytes) or not 44 <= len(wav) <= 128*1024:
                    raise ValueError("One bounded PCM WAV is required for real model listening")
                try:
                    with wave.open(io.BytesIO(wav),"rb") as stream:
                        frames=stream.getnframes()
                        if (stream.getnchannels() != 1 or stream.getsampwidth() != 2 or
                                stream.getframerate() != 16000 or
                                stream.getcomptype() != "NONE" or
                                not 0 < frames <= 16000*3 or
                                len(stream.readframes(frames)) != frames*2):
                            raise ValueError("Actual 16 kHz mono PCM WAV format or length is invalid")
                except (wave.Error,EOFError,OSError) as exc:
                    raise ValueError("Malformed decoded source PCM WAV") from exc
                evidence=context.get("audio_evidence") if isinstance(context,dict) else None
                if (not isinstance(evidence,dict) or
                        not isinstance(evidence.get("export_sha256"),str) or
                        not isinstance(evidence.get("wav_sha256"),str) or
                        evidence["wav_sha256"] != hashlib.sha256(wav).hexdigest()):
                    raise ValueError("Original WAV source or binary custody evidence is missing")
                content.append({"type":"text","text":json.dumps(
                    {"original_audio":True,"export_sha256":evidence["export_sha256"],
                     "wav_sha256":evidence["wav_sha256"],
                     "preview_only_pcm_mono_16khz":True,
                     "original_multichannel_mastering_proven":False})})
                content.append({"type":"input_audio","input_audio":{
                    "data":base64.b64encode(wav).decode("ascii"),"format":"wav"}})
            user_content=content
        payload={"model":self.settings.model_id,"stream":False,
                 "messages":[{"role":"system","content":role},
                             {"role":"user","content":user_content}],
                 "response_format":{"type":"json_object"}}
        payload.update(self.settings.sampling)
        with self._open_request(payload) as resp:
            raw=resp.read(self.settings.max_response_bytes+1)
        if len(raw)>self.settings.max_response_bytes:
            raise ValueError("Local model response exceeds safe size limit")
        decoded=_model_json(raw.decode("utf-8"))
        # Only retain bounded counts actually supplied by the local server.
        # They remain reported usage, not independent tokenizer measurements.
        usage = decoded.get("usage") if isinstance(decoded, dict) else None
        if isinstance(usage, dict):
            reported = {key: usage[key]
                        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                        if type(usage.get(key)) is int and 0 <= usage[key] <= 1_000_000_000}
            self.last_call_usage = reported or None
        choice=decoded["choices"][0]
        if choice.get("finish_reason")=="length":
            raise LocalModelOutputError("truncated_response")
        body=choice["message"].get("content")
        if not isinstance(body,str) or not body.strip():
            raise LocalModelOutputError("empty_response")
        try:
            parsed=_model_json(body.strip())
        except ValueError as exc:
            code = ("duplicate_json_field" if
                    str(exc).startswith("Duplicate local model JSON field: ")
                    else "invalid_json")
            # Do not leak the model's possibly private key/value in logs.
            # The original parser error can include a model-authored key
            # that contains owner-private data. Suppress exception chaining.
            raise LocalModelOutputError(code) from None
        if not isinstance(parsed,dict):
            raise LocalModelOutputError("non_object_json")
        return parsed

    def decide(self,context):
        return self._invoke(self.system_prompt,context)

    def decide_with_images(self,context,images):
        return self._invoke(self.system_prompt,context,images=images)

    def decide_with_audio(self,context,audio):
        """Send one physically decoded, hash-bound WAV to a capable local model.

        This transport cannot independently prove that the model recognizes
        speech/music or correctly evaluates the underlying professional mix.
        """
        return self._invoke(self.system_prompt,context,audio=audio)

    def review(self,context):
        # Caller can create a separate instance with a different local model id,
        # but can also reuse one model while acknowledging role-only separation.
        return self._invoke(_REVIEW_SYSTEM,context)
