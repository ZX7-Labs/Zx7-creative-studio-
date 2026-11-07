"""Adversarial protocol tests for host-current local native JSON Schema."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio_next.local_native_structured_model import LocalNativeStructuredCreativeModel
from studio_next.providers import LocalModelSettings


def decision(action, arguments):
    return json.dumps({
        "choices": [{"message": {
            "content": json.dumps({"action": action, "arguments": arguments,
                                   "reason": "Neural action"})}}],
        "usage": {"total_tokens": 11},
    }).encode()


class LocalNativeStructuredModelTests(unittest.TestCase):
    def setUp(self):
        self.model = LocalNativeStructuredCreativeModel(
            LocalModelSettings(model_id="local-brain"),
            system_prompt="Select exactly one admitted native action")

    def _sample(self, context, action, arguments):
        requests = []
        def serve(request, timeout):
            requests.append(json.loads(request.data))
            return BytesIO(decision(action, arguments))
        with patch("studio_next.providers.urlopen", side_effect=serve):
            result = self.model.decide(context)
        self.assertEqual(result["action"], action)
        self.assertEqual(self.model.last_call_usage["total_tokens"], 11)
        self.assertEqual(len(requests), 1)
        return requests[0]["response_format"]["json_schema"]["schema"]

    @staticmethod
    def _action_map(schema):
        return {x["properties"]["action"]["const"]: x for x in schema["oneOf"]}

    def test_initial_indexed_turn_forbids_guessing_unsearched_tool_or_finish(self):
        context = {"compact_tool_catalog": True,
                   "available_actions": ["search"],
                   "selectable_native_tools": [],
                   "inspectable_native_tools": [],
                   "actual_granted_native_tools": []}
        schema = self._sample(context, "search", {"query": "create project"})
        self.assertEqual(set(self._action_map(schema)), {"search"})
        self.assertNotIn("get_project", json.dumps(schema))
        self.assertNotIn("finish", json.dumps(schema))

    def test_current_host_frontier_only_grants_selected_invoke(self):
        context = {"compact_tool_catalog": True,
                   "available_actions": ["search", "describe", "invoke"],
                   "selectable_native_tools": ["create_project"],
                   "inspectable_native_tools": ["create_project_checkpoint"],
                   "actual_granted_native_tools": []}
        schema = self._sample(context, "invoke", {
            "tool": "create_project", "inputs": {"name": "An original work"}})
        actions = self._action_map(schema)
        self.assertEqual(
            actions["invoke"]["properties"]["arguments"]
            ["properties"]["tool"]["enum"], ["create_project"])
        self.assertEqual(set(
            actions["describe"]["properties"]["arguments"]
            ["properties"]["tool"]["enum"]),
            {"create_project", "create_project_checkpoint"})
        self.assertNotIn("finish", actions)

    def test_finish_is_impossible_until_trusted_evidence_is_complete(self):
        base = {"compact_tool_catalog": True, "selectable_native_tools": [],
                "inspectable_native_tools": [], "actual_granted_native_tools": []}
        before = self._sample({**base, "available_actions": ["search"]},
                              "search", {"query": "export"})
        after = self._sample({**base, "available_actions": ["search", "finish"]},
                             "finish", {"summary": "Native proof exists"})
        self.assertNotIn("finish", self._action_map(before))
        self.assertIn("finish", self._action_map(after))
        self.assertEqual(self.model.settings.sampling, {})

    def test_full_mode_has_real_tools_and_no_inert_search_action(self):
        context = {"compact_tool_catalog": False,
                   "available_actions": ["discover", "describe", "invoke", "finish"],
                   "actual_granted_native_tools": ["get_project", "add_text_clip"]}
        schema = self._sample(context, "discover", {})
        self.assertEqual(set(self._action_map(schema)),
                         {"discover", "describe", "invoke", "finish"})
        self.assertNotIn("search", self._action_map(schema))
        self.assertEqual(self._action_map(schema)["invoke"]["properties"]
                         ["arguments"]["properties"]["tool"]["enum"],
                         ["get_project", "add_text_clip"])

    def test_contradictory_host_actions_fail_before_model_transport(self):
        bad = [
            {"compact_tool_catalog": True, "available_actions": ["invoke"],
             "selectable_native_tools": [], "inspectable_native_tools": []},
            {"compact_tool_catalog": True, "available_actions": ["search", "search"],
             "selectable_native_tools": [], "inspectable_native_tools": []},
            {"compact_tool_catalog": True, "available_actions": ["search", "invoke"],
             "selectable_native_tools": ["ungranted", "ungranted"],
             "inspectable_native_tools": []},
            {"compact_tool_catalog": False,
             "available_actions": ["search", "invoke"],
             "actual_granted_native_tools": ["get_project"]},
        ]
        with patch("studio_next.providers.urlopen") as remote:
            for context in bad:
                with self.subTest(context=context), self.assertRaises(ValueError):
                    self.model.decide(context)
        remote.assert_not_called()

    def test_real_cpu_trial_recorder_uses_same_per_turn_model_adapter(self):
        # A fixture confirms wiring and provider envelope only. Neural model
        # success and artistic editing require a separate actual CPU run.
        from scripts.run_native_model_trial import RecordedModel
        with tempfile.TemporaryDirectory() as temp:
            recorder = RecordedModel(self.model, Path(temp))
            context = {"compact_tool_catalog": True,
                       "available_actions": ["search"],
                       "selectable_native_tools": [],
                       "inspectable_native_tools": [],
                       "actual_granted_native_tools": []}
            requests = []
            def serve(request, timeout):
                requests.append(json.loads(request.data))
                return BytesIO(decision("search", {"query": "import original footage"}))
            with patch("studio_next.providers.urlopen", side_effect=serve):
                answer = recorder.decide(context)
            self.assertEqual(answer["action"], "search")
            self.assertEqual(recorder.settings.sampling, {})
            self.assertEqual(recorder.last_call_usage["total_tokens"], 11)
            self.assertEqual(len(requests), 1)
            schema = requests[0]["response_format"]["json_schema"]["schema"]
            self.assertEqual(set(self._action_map(schema)), {"search"})
            transcript = (Path(temp) / "inference-transcript.jsonl").read_text()
            record = json.loads(transcript)
            self.assertEqual(record["context"], context)
            self.assertEqual(record["decision"], answer)
            self.assertEqual(record["server_reported_token_usage"]["total_tokens"], 11)

    def test_no_schema_leaks_to_configuration_or_separate_model_turn(self):
        first = {"compact_tool_catalog": True, "available_actions": ["search"],
                 "selectable_native_tools": [], "inspectable_native_tools": []}
        second = {"compact_tool_catalog": True,
                  "available_actions": ["search", "describe", "invoke"],
                  "selectable_native_tools": ["get_timeline"],
                  "inspectable_native_tools": []}
        s1 = self._sample(first, "search", {"query": "timeline"})
        s2 = self._sample(second, "invoke", {"tool": "get_timeline", "inputs": {}})
        self.assertEqual(set(self._action_map(s1)), {"search"})
        self.assertIn("invoke", self._action_map(s2))
        self.assertNotIn("response_format", self.model.settings.sampling)


if __name__ == "__main__":
    unittest.main()
