"""Explicit opt-in NVIDIA BYOK creative brain for the existing ZX7 BODY.

No key is stored in model settings, project state, logs, or model prompts.
NVIDIA is a replaceable inference provider; never a source of tool authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .providers import LocalCreativeModel, LocalModelOutputError, _CREATIVE_SYSTEM


_NVIDIA_ENDPOINT = "https://integrate.api.nvidia.com"
_KEY_FORMAT = re.compile(r"nvapi-[A-Za-z0-9_-]{20,512}\Z")
_MODEL_FORMAT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_NVIDIA_PARAMS = frozenset({"temperature", "top_p", "seed", "chat_template_kwargs",
                            "reasoning_effort"})


class NvidiaConfigurationError(ValueError):
    """The operator's NVIDIA configuration was rejected before a network call."""


class NvidiaTransportError(RuntimeError):
    """A remote call failed. Never carry request headers or response bodies."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NvidiaTransportError("NVIDIA redirected a credentialed request; refused")


@dataclass(frozen=True)
class NvidiaModelSettings:
    provider_id: str = "nvidia"
    base_url: str = _NVIDIA_ENDPOINT
    model_id: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    timeout_seconds: int = 180
    max_response_bytes: int = 1_000_000
    max_tokens: int = 2048
    sampling: dict[str, Any] = field(default_factory=lambda: {
        "chat_template_kwargs": {"enable_thinking": False}
    })

    def __post_init__(self):
        if self.provider_id != "nvidia" or self.base_url != _NVIDIA_ENDPOINT:
            raise NvidiaConfigurationError("Unsupported NVIDIA inference endpoint/provider")
        if not isinstance(self.model_id, str) or not _MODEL_FORMAT.fullmatch(self.model_id):
            raise NvidiaConfigurationError("Invalid NVIDIA catalog model identifier")
        for value, low, high in (
            (self.timeout_seconds, 1, 600),
            (self.max_response_bytes, 1024, 2_000_000),
            (self.max_tokens, 1, 8192),
        ):
            if type(value) is not int or not low <= value <= high:
                raise NvidiaConfigurationError("NVIDIA inference requires bounded host limits")
        if not isinstance(self.sampling, dict) or set(self.sampling) - _NVIDIA_PARAMS:
            raise NvidiaConfigurationError("Unsupported NVIDIA inference parameter")
        if any(key in self.sampling for key in ("model", "messages", "tools", "response_format",
                                               "stream", "max_tokens")):
            raise NvidiaConfigurationError("Model settings cannot change host-controlled fields")
        for key in ("temperature", "top_p"):
            if key in self.sampling and (type(self.sampling[key]) not in (int, float) or
                                        not 0 <= self.sampling[key] <= 1):
                raise NvidiaConfigurationError("Invalid bounded NVIDIA sampling parameter")
        if "seed" in self.sampling and (type(self.sampling["seed"]) is not int or
                                      not -(2**63) <= self.sampling["seed"] < 2**63):
            raise NvidiaConfigurationError("Invalid NVIDIA sampling seed")
        if "chat_template_kwargs" in self.sampling:
            self._verify_thinking_kwargs(self.sampling["chat_template_kwargs"])
        if "reasoning_effort" in self.sampling:
            self._verify_reasoning_effort(self.sampling["reasoning_effort"])
            if "chat_template_kwargs" in self.sampling:
                raise NvidiaConfigurationError("Conflicting NVIDIA reasoning controls")

    @staticmethod
    def _verify_thinking_kwargs(kwargs):
        # NVIDIA Nemotron 3.5 Super VL's published model card explicitly
        # supports enable_thinking=True and medium_effort=True. Reasoning and
        # function output share the completion budget; no invented generic
        # provider settings are admitted here.
        if (type(kwargs) is not dict or
                not {"enable_thinking"} <= set(kwargs) <=
                {"enable_thinking", "medium_effort"} or
                type(kwargs["enable_thinking"]) is not bool or
                ("medium_effort" in kwargs and
                 (kwargs["enable_thinking"] is not True or
                  type(kwargs["medium_effort"]) is not bool or
                  kwargs["medium_effort"] is not True))):
            raise NvidiaConfigurationError(
                "Only explicitly supported NVIDIA reasoning configuration is allowed")


    @staticmethod
    def _verify_reasoning_effort(value):
        # Hosted /v1/chat/completions contract: none, low, high only.
        # Self-hosted NIM may offer other template knobs; do not send them
        # from the hosted transport without published API support.
        if type(value) is not str or value not in ("none", "low", "high"):
            raise NvidiaConfigurationError("Unsupported hosted NVIDIA reasoning_effort")


class NvidiaCreativeModel(LocalCreativeModel):
    """Same decisions/vision/JSON checks as LocalCreativeModel; different secure transport.

    Credential comes only from the operator's NVIDIA_API_KEY environment entry.
    Sending original image bytes requires explicit host opt-in. Never log inputs,
    response bodies, remote errors, or Authorization headers.
    """

    def __init__(self, settings: NvidiaModelSettings | None = None, *,
                 system_prompt: str = _CREATIVE_SYSTEM, allow_image_upload: bool = False):
        if type(allow_image_upload) is not bool:
            raise NvidiaConfigurationError("Cloud media permission must be explicit")
        super().__init__(settings or NvidiaModelSettings(), system_prompt=system_prompt)
        self.allow_image_upload = allow_image_upload

    @staticmethod
    def _credential():
        key = os.environ.get("NVIDIA_API_KEY", "")
        if not isinstance(key, str) or not _KEY_FORMAT.fullmatch(key):
            raise NvidiaConfigurationError(
                "Set a valid NVIDIA_API_KEY in the trusted operator environment")
        return key

    def verify_host_credentials(self):
        """Fail early at operator startup without making a remote request."""
        self._credential()

    def _open_request(self, payload):
        key = self._credential()
        if payload.get("model") != self.settings.model_id or payload.get("stream") is not False:
            raise NvidiaConfigurationError("Model identity and streaming are host-controlled")
        # NVIDIA's published Qwen endpoint documents chat fields but not a
        # response_format parameter. JSON is requested in the model's system
        # instructions and strictly parsed locally. Do not claim server schema
        # enforcement, and never silently discard caller-selected schemas.
        fmt = payload.get("response_format")
        if fmt != {"type": "json_object"}:
            raise NvidiaConfigurationError(
                "This NVIDIA endpoint does not guarantee structured-output schemas")
        # The dataclass is frozen, but its sampling dict can be mutated by
        # trusted Python callers. Never let that mutate request identity or
        # model-visible messages after the host's original validation.
        if set(self.settings.sampling) - _NVIDIA_PARAMS:
            raise NvidiaConfigurationError("NVIDIA sampling changed after host admission")
        # Revalidate mutable nested sampling at the actual egress boundary.
        self.settings.__post_init__()
        remote = dict(payload)
        del remote["response_format"]
        remote["max_tokens"] = self.settings.max_tokens
        if "reasoning_effort" in self.settings.sampling:
            if "chat_template_kwargs" in remote:
                raise NvidiaConfigurationError("Conflicting NVIDIA reasoning fields")
            remote["reasoning_effort"] = self.settings.sampling["reasoning_effort"]
        else:
            if "reasoning_effort" in remote:
                raise NvidiaConfigurationError("Conflicting NVIDIA reasoning fields")
            thinking_kwargs = self.settings.sampling.get(
                "chat_template_kwargs", {"enable_thinking": False})
            remote["chat_template_kwargs"] = dict(thinking_kwargs)
        data = json.dumps(remote, ensure_ascii=False, allow_nan=False).encode("utf-8")
        request = Request(_NVIDIA_ENDPOINT + "/v1/chat/completions", data=data,
                          headers={"Authorization": "Bearer " + key,
                                   "Content-Type": "application/json",
                                   "Accept": "application/json"}, method="POST")
        opener = build_opener(ProxyHandler({}), _NoRedirect(),
                              # Use the platform's validated CA certificate set.
                              # urllib's HTTPS handler verifies certificates by default.
                              )
        try:
            return opener.open(request, timeout=self.settings.timeout_seconds)
        except HTTPError as exc:
            # Never print API error bodies; they may echo prompt/private media.
            raise NvidiaTransportError("NVIDIA rejected inference request (HTTP %d)" %
                                       exc.code) from None
        except (URLError, OSError, ssl.SSLError) as exc:
            # A 120B vision/reasoning response may exceed a short HTTP read
            # timeout even when the API is reachable. Distinguish the bounded
            # transport timeout from other network failures without ever
            # exposing raw URL errors, request data, keys or response bodies.
            # Do NOT automatically retry: a POST may already have incurred
            # hosted inference cost. No native tool action is dispatched
            # without a received, validated model decision.
            reason = exc.reason if isinstance(exc, URLError) else exc
            if isinstance(reason, TimeoutError):
                raise NvidiaTransportError("NVIDIA inference transport timed out") from None
            raise NvidiaTransportError("NVIDIA inference connection failed") from None

    def _invoke(self, role, context, *, images=(), audio=()):
        try:
            return super()._invoke(role, context, images=images, audio=audio)
        except (NvidiaConfigurationError, NvidiaTransportError, LocalModelOutputError):
            raise
        except (ValueError, TypeError, KeyError, IndexError, UnicodeError):
            # Remote envelopes and parser exceptions may contain provider-
            # supplied strings. Never surface them into public build logs.
            raise NvidiaTransportError("NVIDIA response or request envelope is invalid") from None

    def decide_with_images(self, context, images):
        if not self.allow_image_upload:
            raise NvidiaConfigurationError(
                "Cloud image upload disabled; host must explicitly authorize media egress")
        if len(images) > 4 or sum(
                len(item[1]) for item in images
                if isinstance(item, tuple) and len(item) == 2 and
                isinstance(item[1], bytes)) > 4 * 1024 * 1024:
            raise NvidiaConfigurationError("Cloud image batch exceeds host egress budget")
        return super().decide_with_images(context, images)

    def decide_with_audio(self, context, audio):
        raise NvidiaConfigurationError(
            "NVIDIA selected endpoint has no verified original-WAV audio contract")
