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


def _relocate_input_schema(value, location):
    """Keep native local JSON pointers scoped to the embedded input schema."""
    if isinstance(value, list):
        return [_relocate_input_schema(item, location) for item in value]
    if not isinstance(value, dict):
        return value
    annotations = {"const", "enum", "default", "examples"}
    copied = {key: item if key in annotations else _relocate_input_schema(item, location)
              for key, item in value.items()}
    if "$ref" in copied and isinstance(copied["$ref"], str):
        ref = copied["$ref"]
        if ref != "#" and not ref.startswith("#/"):
            raise ValueError("Native input schema references must be local JSON pointers")
        copied["$ref"] = location + ref[1:]
    return copied


def _bind_selected_native_inputs(schema, selected, contracts):
    if not isinstance(contracts, list) or len(contracts) != len(selected):
        raise ValueError("Native input contracts must match the live tool frontier")
    inputs_by_name = {}
    for spec in contracts:
        if (not isinstance(spec, dict) or not isinstance(spec.get("name"), str)
                or spec["name"] not in selected or spec["name"] in inputs_by_name
                or not isinstance(spec.get("input_schema"), dict)
                or spec["input_schema"].get("type") != "object"):
            raise ValueError("Invalid current native input contract")
        inputs_by_name[spec["name"]] = spec["input_schema"]
    for index, action in enumerate(schema["oneOf"]):
        if action["properties"]["action"]["const"] == "invoke":
            action["properties"]["arguments"] = {"oneOf": [
                {"type": "object", "properties": {
                    "tool": {"const": name},
                    "inputs": _relocate_input_schema(inputs_by_name[name],
                        f"#/oneOf/{index}/properties/arguments/oneOf/{branch}/properties/inputs"),
                }, "required": ["tool", "inputs"], "additionalProperties": False}
                for branch, name in enumerate(selected)
            ]}


class LocalNativeStructuredCreativeModel(LocalCreativeModel):
    requires_indexed_native_function_contracts = True

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
                not actions or any(type(action) is not str for action in actions) or
                len(set(actions)) != len(actions)):
            raise ValueError("Trusted native action list is missing or ambiguous")
        if compact:
            selected = context.get("selectable_native_tools")
            inspectable = context.get("inspectable_native_tools")
            if not isinstance(selected, list) or not isinstance(inspectable, list):
                raise ValueError("Trusted native tool frontier is unavailable")
            schema = native_action_schema(
                [], compact_catalog=True, selected_tools=selected,
                inspectable_tools=inspectable, allow_finish="finish" in actions)
            if "host_native_tool_contracts" in context:
                _bind_selected_native_inputs(schema, selected, context["host_native_tool_contracts"])
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

    @staticmethod
    def _stable_native_context(context):
        """Reorder, never omit, real host facts for local llama.cpp KV reuse.

        Actual Qwen3.5-4B/native run #42432262621 reached an editable video
        clip but timed out when a ~5.7k-token turn reprocessed its changing
        prompt. The llama-server log measured low common-prefix reuse.
        Place stable SOURCE-OWNED facts (including full schema-derived input
        hints) before volatile event/search/readback records. Preserve every
        key, value, and complete original ordering among the remainder.
        This selects no creative tool and is independent of the model variant.
        """
        if type(context) is not dict:
            raise ValueError("Local native context must be an object")
        stable = (
            "creative_brief",
            "required_completion_evidence",
            "completion_does_not_certify_artistic_quality",
            "audio_semantically_reviewed",
            "compact_tool_catalog",
            "actual_granted_native_tools",
            "capability_overview",
            "host_selected_native_input_hints",
            "host_observed_machine_affordances",
            "selectable_native_tools",
        )
        return {
            **{key: context[key] for key in stable if key in context},
            **{key: value for key, value in context.items() if key not in stable},
        }

    def _choose(self, context, *, images=(), audio=()):
        schema = self._current_host_schema(context)
        # The decoder receives full selected schemas through response_format.
        # Keep the existing concise native hints in the model prompt.
        context = {key: value for key, value in context.items()
                   if key != "host_native_tool_contracts"}
        token = self._active_schema.set(schema)
        try:
            return self._invoke(
                self.system_prompt, self._stable_native_context(context),
                images=images, audio=audio)
        finally:
            self._active_schema.reset(token)

    def decide(self, context):
        return self._choose(context)

    def decide_with_images(self, context, images):
        return self._choose(context, images=images)

    def decide_with_audio(self, context, audio):
        return self._choose(context, audio=audio)
