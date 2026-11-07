"""Per-turn native control JSON Schema for a user-selected local model backend.

Reuse the existing LocalCreativeModel transport and official native_action_schema.
The trusted controller, never the model, supplies the current native options,
inspection candidates and evidence-based eligibility to finish. This adapter
cannot change grants, dispatch tools or certify creative quality.
"""
from __future__ import annotations

from contextvars import ContextVar

from .native_action_schema import native_action_schema
from .providers import LocalCreativeModel, LocalModelSettings


class LocalNativeStructuredCreativeModel(LocalCreativeModel):
    def __init__(self, settings: LocalModelSettings, *, system_prompt: str):
        if "response_format" in settings.sampling:
            raise ValueError("Native structured model owns its per-turn schema")
        super().__init__(settings, system_prompt=system_prompt)
        self._active_schema = ContextVar("zx7_native_local_action_schema", default=None)

    @staticmethod
    def _current_host_schema(context):
        if not isinstance(context, dict):
            raise ValueError("Trusted native model context must be an object")
        compact = context.get("compact_tool_catalog")
        actions = context.get("available_actions")
        if (type(compact) is not bool or not isinstance(actions, list) or
                not actions or len(set(actions)) != len(actions) or
                any(not isinstance(action, str) for action in actions)):
            raise ValueError("Trusted native action list is missing or ambiguous")
        if compact:
            selected = context.get("selectable_native_tools")
            inspectable = context.get("inspectable_native_tools")
            if not isinstance(selected, list) or not isinstance(inspectable, list):
                raise ValueError("Trusted native tool frontier is unavailable")
            schema = native_action_schema(
                [], compact_catalog=True, selected_tools=selected,
                inspectable_tools=inspectable, allow_finish="finish" in actions)
        else:
            tools = context.get("actual_granted_native_tools")
            if not isinstance(tools, list):
                raise ValueError("Trusted granted native tool list is unavailable")
            schema = native_action_schema(
                tools, compact_catalog=False, allow_finish="finish" in actions)
        available = {
            entry["properties"]["action"]["const"]
            for entry in schema["oneOf"]
        }
        if available != set(actions):
            raise ValueError("Host state and bounded native action grammar disagree")
        return schema

    def _open_request(self, payload):
        schema = self._active_schema.get()
        if schema is None:
            raise ValueError("Native structured output requires a live host action grammar")
        bounded = dict(payload)
        bounded["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "native_editor_action",
                "strict": True,
                "schema": schema,
            },
        }
        return super()._open_request(bounded)

    def _choose(self, context, *, images=(), audio=()):
        schema = self._current_host_schema(context)
        token = self._active_schema.set(schema)
        try:
            return self._invoke(self.system_prompt, context, images=images, audio=audio)
        finally:
            self._active_schema.reset(token)

    def decide(self, context):
        return self._choose(context)

    def decide_with_images(self, context, images):
        return self._choose(context, images=images)

    def decide_with_audio(self, context, audio):
        return self._choose(context, audio=audio)
