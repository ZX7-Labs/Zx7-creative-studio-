"""Lossless prompt-evidence regression tests from real Qwen 4B failure #42711402879.

These tests use only artificial native receipts and mocked model HTTP. Real
weights and public/private media never run in this suite.
"""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
import unittest
from unittest.mock import patch

from studio_next.local_native_structured_model import LocalNativeStructuredCreativeModel
from studio_next.providers import LocalModelSettings


class LocalNativePromptViewTests(unittest.TestCase):
    def setUp(self):
        self.model = LocalNativeStructuredCreativeModel(
            LocalModelSettings(model_id="local-test"),
            system_prompt="Select a host-admitted native action",
        )

    def test_duplicate_read_is_a_reference_to_complete_unchanged_snapshot(self):
        native_text = '{"clips":[' + ",".join(
            json.dumps(f"original-native-clip-{i}") for i in range(500)) + ']}'
        original = {
            "compact_tool_catalog": True,
            "available_actions": ["search"],
            "selectable_native_tools": [],
            "inspectable_native_tools": [],
            "native_read_snapshot_cache": [
                {"tool": "get_timeline", "source": "model_selected",
                 "result_texts": [native_text]}],
            "last_native_result_texts": [native_text],
        }
        untouched = deepcopy(original)
        compact = self.model._model_prompt_view(original)
        self.assertEqual(original, untouched)
        self.assertNotIn("last_native_result_texts", compact)
        reference = compact["last_native_result_snapshot_reference"]
        self.assertEqual(reference["cache_index"], 0)
        self.assertEqual(reference["tool"], "get_timeline")
        self.assertTrue(reference["complete_native_texts_preserved_in_snapshot"])
        self.assertEqual(compact["native_read_snapshot_cache"][0]["result_texts"],
                         original["last_native_result_texts"])
        self.assertEqual(json.dumps(compact).count("original-native-clip-499"), 1)
        self.assertLess(len(json.dumps(compact)), len(json.dumps(original)) - 5000)

    def test_live_source_schema_is_deduplicated_only_against_current_bound_grammar(self):
        source_schema = {"type": "object", "properties": {
            "previewOnly": {"type": "boolean"},
            "assetNames": {"type": "array", "items": {"type": "string"}},
        }}
        constrained = {**source_schema, "required": ["previewOnly"],
                       "additionalProperties": False}
        context = {
            "compact_tool_catalog": True,
            "available_actions": ["search", "describe", "invoke"],
            "selectable_native_tools": ["add_assets_to_timeline"],
            "inspectable_native_tools": ["add_assets_to_timeline"],
            "host_native_tool_contracts": [{
                "name": "add_assets_to_timeline",
                "input_schema": constrained}],
            "latest_events": [{
                "kind": "native_tool_schema",
                "tool": "add_assets_to_timeline",
                "input_schema": source_schema,
                "description": "Actual source schema"}],
        }
        untouched = deepcopy(context)
        requests = []
        def serve(request, timeout):
            requests.append(json.loads(request.data))
            result = {"choices": [{"message": {"content": json.dumps({
                "action": "search", "arguments": {"query": "native verified export"},
                "reason": "A model-authored read only discovery"})}}]}
            return BytesIO(json.dumps(result).encode("utf-8"))
        with patch("studio_next.providers.urlopen", side_effect=serve):
            answer = self.model.decide(context)
        self.assertEqual(answer["action"], "search")
        self.assertEqual(context, untouched)
        request = requests[0]
        prompt = json.loads(request["messages"][1]["content"])
        event = prompt["latest_events"][0]
        self.assertNotIn("input_schema", event)
        self.assertTrue(event["complete_schema_in_host_bound_response_grammar"])
        self.assertNotIn("host_native_tool_contracts", prompt)
        grammar = request["response_format"]["json_schema"]["schema"]
        invoke = next(action for action in grammar["oneOf"]
                      if action["properties"]["action"]["const"] == "invoke")
        actual = invoke["properties"]["arguments"]["oneOf"][0]
        self.assertEqual(actual["properties"]["tool"]["const"],
                         "add_assets_to_timeline")
        self.assertEqual(actual["properties"]["inputs"], constrained)

    def test_never_remove_nonmatching_original_read_or_schema(self):
        source = {
            "native_read_snapshot_cache": [{
                "tool": "get_project", "result_texts": ['{"original":1}']}],
            "last_native_result_texts": ['{"original":2}'],
            "latest_events": [{
                "kind": "native_tool_schema", "tool": "get_timeline",
                "input_schema": {"type": "object", "properties": {
                    "originalSourceField": {"type": "string"}}}}],
            "host_native_tool_contracts": [{
                "name": "get_timeline", "input_schema": {
                    "type": "object", "properties": {
                        "originalSourceField": {"type": "boolean"}}}}],
        }
        view = self.model._model_prompt_view(source)
        self.assertEqual(view["last_native_result_texts"],
                         source["last_native_result_texts"])
        self.assertEqual(view["latest_events"], source["latest_events"])
        self.assertNotIn("last_native_result_snapshot_reference", view)
        with self.assertRaises(ValueError):
            self.model._model_prompt_view([])


if __name__ == "__main__":
    unittest.main()
