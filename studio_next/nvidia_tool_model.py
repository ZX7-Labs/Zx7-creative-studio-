"""Optional NVIDIA native *function-call* decision adapter.

Use a real provider tool-call envelope, not free-form JSON pretending to be
a native action. The trusted BODY still validates every decision and invokes
only installed, host-granted editor tools. This adapter has no dispatch power.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from .nvidia_model import (
    NvidiaCreativeModel, NvidiaModelSettings,
    NvidiaConfigurationError, NvidiaTransportError,
)
from .providers import LocalModelOutputError, _model_json

_TOOL_NAME = "zx7_select_next_creative_action"
_PARAMS = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["search", "describe", "invoke", "discover", "finish"],
            "description": "One of the host-exposed actions in current context",
        },
        "arguments": {
            "type": "object",
            "description": (
                "search: {query: natural language <=160 bytes, limit?:1..8}; "
                "describe: {tool: exactly visible granted native tool}; "
                "invoke: {tool: visible native tool, inputs: exact host schema}; "
                "discover: {}; finish: {summary: string}. "
                "Never guess an unlisted schema or a source, and do not claim "
                "any native write until the installed editor has acknowledged it."
            ),
        },
        "reason": {
            "type": "string",
            "description": "Non-empty causal reason for this one real action",
        },
    },
    "required": ["action", "arguments", "reason"],
    "additionalProperties": False,
}


class NvidiaToolCreativeModel(NvidiaCreativeModel):
    """NVIDIA provider tool-call surface with strict, bounded response custody."""

    def __init__(self, settings: NvidiaModelSettings | None = None, *,
                 system_prompt: str, allow_image_upload: bool = False):
        super().__init__(settings, system_prompt=system_prompt,
                         allow_image_upload=allow_image_upload)

    def _messages(self, context: dict, images):
        if not isinstance(context, dict):
            raise NvidiaConfigurationError("Native tool context must be a validated object")
        message = json.dumps(context, ensure_ascii=False, allow_nan=False)
        if not images:
            return [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": message},
            ]
        if not self.allow_image_upload:
            raise NvidiaConfigurationError("Cloud original frame evidence requires host consent")
        if not 1 <= len(images) <= 4:
            raise NvidiaConfigurationError("Cloud frame evidence batch must be bounded")
        evidence = context.get("picture_evidence")
        if evidence is not None and (not isinstance(evidence, list) or
                                    len(evidence) != len(images)):
            raise NvidiaConfigurationError("Original frame evidence mismatch")
        content = [{"type": "text", "text": message}]
        total = 0
        for index, item in enumerate(images):
            if not isinstance(item, tuple) or len(item) != 2:
                raise NvidiaConfigurationError("Original cloud frame is not (mime,bytes)")
            mime, raw = item
            if (mime not in ("image/png", "image/jpeg") or
                    not isinstance(raw, bytes) or not 8 <= len(raw) <= 3_000_000):
                raise NvidiaConfigurationError("NVIDIA image requires bounded original bytes")
            if (mime == "image/png" and not raw.startswith(b"\x89PNG\r\n\x1a\n")) or (
                    mime == "image/jpeg" and not raw.startswith(b"\xff\xd8\xff")):
                raise NvidiaConfigurationError("NVIDIA image mime and magic mismatch")
            total += len(raw)
            if total > 4 * 1024 * 1024:
                raise NvidiaConfigurationError("Cloud frame evidence exceeds host egress budget")
            if evidence is not None:
                metadata = evidence[index]
                if (not isinstance(metadata, dict) or any(
                        not isinstance(metadata.get(k), str) or not metadata[k]
                        for k in ("job_id", "path", "sha256")) or
                        metadata["sha256"] != hashlib.sha256(raw).hexdigest()):
                    raise NvidiaConfigurationError("Cloud frame hash custody is not verified")
            content.append({"type": "text", "text": json.dumps({
                "image_index": index, "sha256": hashlib.sha256(raw).hexdigest(),
                "image_mime": mime}, ensure_ascii=False)})
            content.append({"type": "image_url", "image_url": {
                "url": "data:" + mime + ";base64," + base64.b64encode(raw).decode("ascii")}})
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": content},
        ]

    def _call_as_tool(self, context, *, images=()):
        self.last_call_usage = None
        payload = {
            "model": self.settings.model_id,
            "stream": False,
            "response_format": {"type": "json_object"},
            "messages": self._messages(context, images),
            "tools": [{"type": "function", "function": {
                "name": _TOOL_NAME,
                "description": "Select EXACTLY ONE host-admitted creative editor action.",
                "parameters": _PARAMS,
            }}],
            "tool_choice": {"type": "function", "function": {"name": _TOOL_NAME}},
            "parallel_tool_calls": False,
        }
        payload.update(self.settings.sampling)
        try:
            with self._open_request(payload) as response:
                raw = response.read(self.settings.max_response_bytes + 1)
            if len(raw) > self.settings.max_response_bytes:
                raise LocalModelOutputError("oversize_tool_envelope")
            decoded = _model_json(raw.decode("utf-8"))
            usage = decoded.get("usage")
            if isinstance(usage, dict):
                reported = {
                    k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                    if type(usage.get(k)) is int and 0 <= usage[k] <= 1_000_000_000
                }
                self.last_call_usage = reported or None
            choices = decoded.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise LocalModelOutputError("tool_choice_count")
            selected = choices[0]
            if selected.get("finish_reason") == "length":
                raise LocalModelOutputError("truncated_tool_decision")
            calls = selected.get("message", {}).get("tool_calls")
            if not isinstance(calls, list) or len(calls) != 1:
                raise LocalModelOutputError("missing_or_multiple_function_calls")
            fn = calls[0].get("function")
            if (not isinstance(fn, dict) or fn.get("name") != _TOOL_NAME or
                    not isinstance(fn.get("arguments"), str)):
                raise LocalModelOutputError("unexpected_native_function")
            decision = _model_json(fn["arguments"])
            if not isinstance(decision, dict) or set(decision) != {
                    "action", "arguments", "reason"}:
                raise LocalModelOutputError("invalid_native_function_arguments")
            # Never execute here. The BODY controller owns the entire native
            # grammar, schema, rights and granted-source admission.
            return decision
        except (NvidiaConfigurationError, NvidiaTransportError, LocalModelOutputError):
            raise
        except (ValueError, TypeError, KeyError, AttributeError, IndexError, UnicodeError):
            raise LocalModelOutputError("invalid_tool_response_envelope") from None

    def decide(self, context):
        return self._call_as_tool(context)

    def decide_with_images(self, context, images):
        return self._call_as_tool(context, images=images)
