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

from .providers import LocalCreativeModel, _CREATIVE_SYSTEM


_NVIDIA_ENDPOINT = "https://integrate.api.nvidia.com"
_KEY_FORMAT = re.compile(r"nvapi-[A-Za-z0-9_-]{20,512}\Z")
_MODEL_FORMAT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_NVIDIA_PARAMS = frozenset({"temperature", "top_p", "seed", "chat_template_kwargs"})


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
    model_id: str = "qwen/qwen3.5-122b-a10b"
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
            (self.max_tokens, 1, 4096),
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
        if "chat_template_kwargs" in self.sampling and (
                not isinstance(self.sampling["chat_template_kwargs"], dict) or
                set(self.sampling["chat_template_kwargs"]) != {"enable_thinking"} or
                type(self.sampling["chat_template_kwargs"]["enable_thinking"]) is not bool):
            raise NvidiaConfigurationError("Only explicit NVIDIA thinking-mode configuration is allowed")


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

    def _open_request(self, payload):
        key = os.environ.get("NVIDIA_API_KEY", "")
        if not isinstance(key, str) or not _KEY_FORMAT.fullmatch(key):
            raise NvidiaConfigurationError(
                "Set a valid NVIDIA_API_KEY in the trusted operator environment")
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
        remote = dict(payload)
        del remote["response_format"]
        remote["max_tokens"] = self.settings.max_tokens
        remote["chat_template_kwargs"] = self.settings.sampling.get(
            "chat_template_kwargs", {"enable_thinking": False})
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
            raise NvidiaTransportError("NVIDIA inference connection failed") from None

    def decide_with_images(self, context, images):
        if not self.allow_image_upload:
            raise NvidiaConfigurationError(
                "Cloud image upload disabled; host must explicitly authorize media egress")
        return super().decide_with_images(context, images)

    def decide_with_audio(self, context, audio):
        raise NvidiaConfigurationError(
            "NVIDIA Qwen endpoint has no verified original-WAV audio contract")
