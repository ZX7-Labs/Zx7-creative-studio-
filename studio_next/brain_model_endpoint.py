"""Model-agnostic creative Brain connector with strict owner-side cost control.

Owner setup: choose one OpenAI-compatible endpoint + model and, for a hosted
provider, one API credential. Research sources and creative BODY registration
need no separate provider credentials. The model is never given native
execution, network-grant, or budget-setting authority.

No hosted provider is called unless the owner explicitly enables paid model
inference. Bounded call counts are a safety ceiling, NOT a verified USD cap.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
from threading import Lock
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError
import ipaddress
import json
import os
import re

from .providers import _model_json, LocalModelOutputError


class CreativeBrainConnectionError(ValueError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class CreativeBrainEndpoint:
    model_id: str
    base_url: str = "http://127.0.0.1:8080"
    mode: str = "local"
    credential_env: str | None = None
    paid_inference_approved: bool = False
    remote_owner_media_approved: bool = False
    max_inference_calls: int = 48
    response_limit_bytes: int = 1_000_000

    def __post_init__(self):
        if not isinstance(self.model_id,str) or not self.model_id.strip() or len(self.model_id)>160:
            raise CreativeBrainConnectionError("Owner must choose one real model identifier")
        if self.mode not in ("local", "openai_compatible_remote"):
            raise CreativeBrainConnectionError("Unknown model connection kind")
        if (type(self.max_inference_calls) is not int or
                not 1 <= self.max_inference_calls <= 1000 or
                type(self.response_limit_bytes) is not int or
                not 1024 <= self.response_limit_bytes <= 5_000_000):
            raise CreativeBrainConnectionError("Finite non-runaway model request limits required")
        uri=urlsplit(self.base_url)
        if (not uri.hostname or uri.username or uri.password or
                uri.query or uri.fragment or uri.path not in ("", "/v1")
                or uri.port is not None and not 1 <= uri.port <= 65535):
            raise CreativeBrainConnectionError("Trusted model connection URL malformed")
        if self.mode == "local":
            if (uri.scheme != "http" or
                    uri.hostname not in ("localhost","127.0.0.1","::1")
                    or self.credential_env is not None
                    or self.paid_inference_approved is not False or
                    self.remote_owner_media_approved is not False):
                raise CreativeBrainConnectionError("Local model must stay on loopback without paid authorization")
        else:
            if uri.scheme != "https" or uri.hostname.lower() in (
                    "localhost", "localhost.localdomain"):
                raise CreativeBrainConnectionError("Remote model provider must use public HTTPS")
            try:
                if not ipaddress.ip_address(uri.hostname).is_global:
                    raise CreativeBrainConnectionError("Remote model cannot target a private IP")
            except ValueError as exc:
                if isinstance(exc, CreativeBrainConnectionError):
                    raise
            if (not self.paid_inference_approved or
                    not isinstance(self.credential_env, str) or not
                    re.fullmatch(r"[A-Z][A-Z0-9_]{2,100}", self.credential_env)):
                raise CreativeBrainConnectionError(
                    "Owner must explicitly approve paid model and choose a credential variable")


class CreativeBrainModel:
    """Pure decision inference; host validates every creative tool invocation."""

    def __init__(self, endpoint: CreativeBrainEndpoint, *, system_prompt: str):
        if not isinstance(endpoint,CreativeBrainEndpoint):
            raise CreativeBrainConnectionError("Validated model endpoint required")
        if not isinstance(system_prompt,str) or not system_prompt.strip():
            raise CreativeBrainConnectionError("Creative role instruction required")
        self.settings=endpoint
        self.system_prompt=system_prompt
        self._attempts=0
        self._lock=Lock()
        self.last_call_usage=None

    @property
    def remaining_calls(self):
        return self.settings.max_inference_calls-self._attempts

    def decide(self, context):
        return self._invoke(context)

    def decide_with_images(self, context, images):
        """Reject unconsented external media BEFORE any credential or budget use."""
        if (self.settings.mode == "openai_compatible_remote" and
                not self.settings.remote_owner_media_approved):
            raise CreativeBrainConnectionError(
                "Remote upload of owner visual evidence requires explicit owner consent")
        return self._invoke(context, images=images)

    def _invoke(self, context, *, images=()):
        """Exactly one bounded provider request; unknown outcomes never retried."""
        if not isinstance(context,dict):
            raise CreativeBrainConnectionError("Typed model context required")
        with self._lock:
            if self._attempts >= self.settings.max_inference_calls:
                raise CreativeBrainConnectionError(
                    "Model budget exhausted; human/operator must approve a new session")
            self._attempts += 1  # Reserve BEFORE potentially chargeable request.
        auth=None
        if self.settings.mode == "openai_compatible_remote":
            auth=os.getenv(self.settings.credential_env)
            if not auth or "\n" in auth or "\r" in auth:
                raise CreativeBrainConnectionError("Approved provider credential is unavailable")
        user_content=json.dumps(context,ensure_ascii=False,allow_nan=False)
        if images:
            if (self.settings.mode == "openai_compatible_remote" and
                    not self.settings.remote_owner_media_approved):
                raise CreativeBrainConnectionError(
                    "Remote upload of owner visual evidence requires explicit owner consent")
            if not isinstance(images,(tuple,list)) or len(images)>4:
                raise CreativeBrainConnectionError("Bounded actual visual evidence required")
            evidence=context.get("picture_evidence")
            if not isinstance(evidence,list) or len(evidence)!=len(images):
                raise CreativeBrainConnectionError(
                    "Original image source evidence is not bound to media")
            parts=[{"type":"text","text":user_content}]
            for index, picture in enumerate(images):
                if not isinstance(picture,tuple) or len(picture)!=2:
                    raise CreativeBrainConnectionError("Actual image tuple required")
                mime, raw = picture
                if (mime not in ("image/png","image/jpeg") or
                        not isinstance(raw,bytes) or
                        not 16 <= len(raw) <= 3_000_000 or
                        (mime=="image/png" and not raw.startswith(b"\x89PNG\r\n\x1a\n")) or
                        (mime=="image/jpeg" and not raw.startswith(b"\xff\xd8\xff"))):
                    raise CreativeBrainConnectionError("Untrusted visual media input")
                provenance=evidence[index]
                if (not isinstance(provenance,dict) or
                        not isinstance(provenance.get("sha256"),str) or
                        hashlib.sha256(raw).hexdigest()!=provenance["sha256"]):
                    raise CreativeBrainConnectionError(
                        "Owner media failed actual pixel byte identity proof")
                parts.append({"type":"text","text":json.dumps(
                    {"image_index":index,"sha256":provenance["sha256"]})})
                parts.append({"type":"image_url","image_url":{"url":
                    "data:"+mime+";base64,"+base64.b64encode(raw).decode("ascii")}})
            user_content=parts
        payload={
            "model": self.settings.model_id, "stream": False,
            "messages": [
                {"role":"system","content":self.system_prompt},
                {"role":"user","content":user_content}],
            "response_format":{"type":"json_object"}}
        body=json.dumps(payload,allow_nan=False).encode("utf-8")
        if len(body)>512_000:
            raise CreativeBrainConnectionError("Bounded creative thinking context exceeded")
        headers={"Content-Type":"application/json",
                 "Accept":"application/json",
                 "User-Agent":"ZX7-Creative-Brain/0.1"}
        if auth is not None:
            headers["Authorization"]="Bearer "+auth
        base=self.settings.base_url.rstrip("/")
        path="/chat/completions" if base.endswith("/v1") else "/v1/chat/completions"
        request=Request(base+path,data=body,method="POST",headers=headers)
        # No ambient proxy/redirect may receive the owner's model API key.
        opener=build_opener(ProxyHandler({}),_NoRedirect)
        try:
            with opener.open(request,timeout=120) as response:
                if response.status!=200:
                    raise CreativeBrainConnectionError("Selected model provider rejected the request")
                raw=response.read(self.settings.response_limit_bytes+1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise CreativeBrainConnectionError(
                "Model request failed or outcome uncertain; no automatic retry") from None
        if len(raw)>self.settings.response_limit_bytes:
            raise CreativeBrainConnectionError("Unbounded provider response")
        try:
            envelope=_model_json(raw.decode("utf-8"))
            if not isinstance(envelope,dict):
                raise CreativeBrainConnectionError("Provider returned non-object envelope")
            choices=envelope.get("choices")
            if not isinstance(choices,list) or len(choices)!=1:
                raise CreativeBrainConnectionError("Provider returned ambiguous model decisions")
            choice=choices[0]
            if not isinstance(choice,dict):
                raise CreativeBrainConnectionError("Invalid model response")
            if choice.get("finish_reason")=="length":
                raise LocalModelOutputError("truncated_response")
            message=choice.get("message")
            content=message.get("content") if isinstance(message,dict) else None
            if not isinstance(content,str) or not content.strip():
                raise LocalModelOutputError("empty_response")
            decision=_model_json(content)
            if not isinstance(decision,dict):
                raise CreativeBrainConnectionError("Model decision must be an object")
            usage=envelope.get("usage")
            self.last_call_usage={k:usage[k] for k in (
                "prompt_tokens","completion_tokens","total_tokens")
                if isinstance(usage,dict) and type(usage.get(k)) is int
                and 0 <= usage[k] <= 1_000_000_000} or None
            return decision
        except (UnicodeError, ValueError, TypeError, IndexError, KeyError):
            raise CreativeBrainConnectionError("Model returned invalid bounded JSON decision") from None
