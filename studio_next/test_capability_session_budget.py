"""Cross-system host execution ceilings; fake engines test admission only.

No scripted film, fake neural quality claim, token estimate or actual billing.
The existing physical editor and independent native-CI workflows remain the
separate evidence for a real editor's output.
"""
import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from studio_next.capability_attempts import CapabilityAttemptStore
from studio_next.capability_gateway import (
    CapabilityExecutionError, CapabilityGateway)
from studio_next.capability_session_budget import (
    CapabilitySessionBudget, CapabilitySessionBudgetError)


class LocalToolSource:
    def __init__(self, name, *, access):
        self.name = name
        self.access = access
        self.calls = []
        self.fail = None

    async def list_tools(self):
        return SimpleNamespace(tools=[
            SimpleNamespace(
                name=self.name,
                description="Operate installed native tool " + self.name,
                input_schema={
                    "type": "object", "properties": {
                        "count": {"type": "integer", "minimum": 1}},
                    "required": ["count"]})])

    async def call_tool(self, name, inputs):
        self.calls.append((name, inputs))
        await asyncio.sleep(0)
        if self.fail is not None:
            raise self.fail
        # Transport-only fixture, not a claim of native state mutation.
        return SimpleNamespace(is_error=False, content=[])


class UniversalBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def _gateway(self, sources, budget, *, attempt_store=None):
        gateway = CapabilityGateway({
            namespace: (engine, {engine.name: engine.access})
            for namespace, engine in sources.items()
        }, attempt_store=attempt_store, session_budget=budget)
        revision = (await gateway.refresh())["revision"]
        return gateway, revision

    async def test_three_unrelated_engines_share_host_limits_not_tool_prompts(self):
        sources = {
            "video": LocalToolSource("trim", access="write"),
            "motion": LocalToolSource("keyframe", access="write"),
            "documents": LocalToolSource("inspect_page", access="read"),
        }
        budget = CapabilitySessionBudget(
            max_calls=5, max_writes=2,
            per_source={"video": 1, "motion": 1, "documents": 1})
        gateway, revision = await self._gateway(sources, budget)
        for source, name in (("video", "trim"),
                             ("motion", "keyframe"),
                             ("documents", "inspect_page")):
            response = await gateway.invoke(
                f"{source}/{name}", revision=revision, inputs={"count": 1})
            self.assertEqual(response["state"], "host_reported_success_unverified")
        self.assertEqual(sum(len(s.calls) for s in sources.values()), 3)
        self.assertEqual(gateway.host_budget_evidence()["reserved_calls"], 3)
        self.assertEqual(gateway.host_budget_evidence()["reserved_writes"], 2)
        with self.assertRaisesRegex(
                CapabilityExecutionError, "host_source_call_budget_exhausted"):
            await gateway.invoke("documents/inspect_page",
                                 revision=revision, inputs={"count": 1})
        self.assertEqual(len(sources["documents"].calls), 1)
        self.assertEqual(budget.snapshot()["reserved_calls_by_source"],
                         {"documents": 1, "motion": 1, "video": 1})

    async def test_global_write_limit_refuses_other_source_but_preserves_reads(self):
        sources = {
            "video": LocalToolSource("trim", access="write"),
            "animation": LocalToolSource("animate", access="write"),
            "research": LocalToolSource("inspect", access="read"),
        }
        budget = CapabilitySessionBudget(max_calls=4, max_writes=1)
        gateway, revision = await self._gateway(sources, budget)
        await gateway.invoke("video/trim", revision=revision, inputs={"count": 2})
        with self.assertRaisesRegex(
                CapabilityExecutionError, "host_session_write_budget_exhausted"):
            await gateway.invoke("animation/animate", revision=revision,
                                 inputs={"count": 1})
        self.assertEqual(sources["animation"].calls, [])
        await gateway.invoke("research/inspect", revision=revision,
                             inputs={"count": 1})
        self.assertEqual(budget.snapshot()["reserved_calls"], 2)

    async def test_invalid_model_inputs_do_not_consume_execution_slots(self):
        source = LocalToolSource("render", access="write")
        budget = CapabilitySessionBudget(max_calls=1, max_writes=1)
        gateway, revision = await self._gateway({"geometry": source}, budget)
        with self.assertRaises(CapabilityExecutionError):
            await gateway.invoke("geometry/render", revision=revision,
                                 inputs={"count": "wrong-type"})
        self.assertEqual(budget.snapshot()["reserved_calls"], 0)
        self.assertEqual(source.calls, [])
        await gateway.invoke("geometry/render", revision=revision,
                             inputs={"count": 1})
        self.assertEqual(budget.snapshot()["reserved_calls"], 1)

    async def test_concurrent_cross_source_invocation_reservation_is_atomic(self):
        sources = {
            "music": LocalToolSource("render", access="write"),
            "illustration": LocalToolSource("draw", access="write"),
        }
        budget = CapabilitySessionBudget(max_calls=1, max_writes=1)
        gateway, revision = await self._gateway(sources, budget)
        responses = await asyncio.gather(
            gateway.invoke("music/render", revision=revision, inputs={"count": 1}),
            gateway.invoke("illustration/draw", revision=revision, inputs={"count": 1}),
            return_exceptions=True)
        self.assertEqual(sum(not isinstance(r, BaseException)
                             for r in responses), 1)
        self.assertEqual(sum(isinstance(r, CapabilityExecutionError)
                             for r in responses), 1)
        self.assertEqual(sum(len(s.calls) for s in sources.values()), 1)
        self.assertEqual(budget.snapshot()["reserved_calls"], 1)

    async def test_uncertain_write_exhausts_slot_and_cannot_be_replayed(self):
        source = LocalToolSource("update", access="write")
        source.fail = TimeoutError("private project name /owner/secret")
        budget = CapabilitySessionBudget(max_calls=1, max_writes=1)
        gateway, revision = await self._gateway({"graphics": source}, budget)
        with self.assertRaises(TimeoutError):
            await gateway.invoke("graphics/update", revision=revision,
                                 inputs={"count": 1})
        self.assertEqual(budget.snapshot()["reserved_writes"], 1)
        with self.assertRaisesRegex(
                CapabilityExecutionError, "host_session_call_budget_exhausted"):
            await gateway.invoke("graphics/update", revision=revision,
                                 inputs={"count": 1})
        self.assertEqual(len(source.calls), 1)
        self.assertNotIn("owner/secret", str(gateway.host_budget_evidence()))

    async def test_exhausted_host_budget_cannot_create_durable_write_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = CapabilityAttemptStore(Path(folder) / "ledger.sqlite3")
            source = LocalToolSource("update", access="write")
            budget = CapabilitySessionBudget(max_calls=1, max_writes=1)
            gateway, revision = await self._gateway(
                {"scenes": source}, budget, attempt_store=journal)
            await gateway.invoke("scenes/update", revision=revision,
                                 inputs={"count": 1}, request_id="first")
            with self.assertRaisesRegex(
                    CapabilityExecutionError,
                    "host_session_call_budget_exhausted"):
                await gateway.invoke("scenes/update", revision=revision,
                                     inputs={"count": 1}, request_id="blocked")
            self.assertIsNone(journal.inspect("blocked"))
            self.assertEqual(len(source.calls), 1)
            self.assertFalse(journal.inspect("first")["state"].endswith("verified"))

    async def test_invalid_or_unknown_host_policies_fail_before_discovery(self):
        for limits in (
            {"max_calls": True, "max_writes": 1},
            {"max_calls": -1, "max_writes": 0},
            {"max_calls": 2, "max_writes": 3},
            {"max_calls": 1.0, "max_writes": 0},
            {"max_calls": 2, "max_writes": 1,
             "per_source": {"motion": "1"}},
            {"max_calls": 2, "max_writes": 1,
             "per_source": {"name with spaces": 1}},
        ):
            with self.subTest(limits=limits), self.assertRaises(
                    CapabilitySessionBudgetError):
                CapabilitySessionBudget(**limits)
        source = LocalToolSource("read", access="read")
        misnamed = CapabilitySessionBudget(
            max_calls=1, max_writes=0, per_source={"wrong": 1})
        with self.assertRaisesRegex(
                CapabilityExecutionError, "unknown_host_budget_source"):
            await self._gateway({"real": source}, misnamed)
        with self.assertRaisesRegex(
                CapabilityExecutionError, "host-owned"):
            CapabilityGateway({"real": (source, {"read": "read"})},
                              session_budget={"max_calls": 1})
        self.assertEqual(source.calls, [])


if __name__ == "__main__":
    unittest.main()
