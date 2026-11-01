"""Real executable multi-engine boundary regressions (no neural model mock success)."""
import asyncio
import json
from types import SimpleNamespace
import unittest

from studio_next.capability_gateway import CapabilityGateway, CapabilityExecutionError
from studio_next.capability_fabric import CapabilityContractError


def tool(name, props=None, **schema):
    return SimpleNamespace(
        name=name, description="Native independent project control " + name,
        input_schema={"type": "object", "properties": props or {}, **schema},
        annotations={"readOnlyHint": True})  # annotations are untrusted, ignored


class Engine:
    def __init__(self, ops):
        self.tools = ops
        self.calls = []
        self.result = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text='{"real_native":true}')])
        self.fail = None
        self.active = 0
        self.maximum_parallel = 0

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name, args):
        self.active += 1
        self.maximum_parallel = max(self.maximum_parallel, self.active)
        self.calls.append((name, args))
        try:
            await asyncio.sleep(0)
            if self.fail is not None:
                raise self.fail
            return self.result
        finally:
            self.active -= 1


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_creative_engines_same_name_route_with_separate_grants(self):
        video = Engine([tool("render", {"frames": {"type": "integer"}},
                             required=["frames"])])
        motion = Engine([tool("render", {"curve": {"type": "array"}},
                              required=["curve"])])
        gateway = CapabilityGateway({
            "video": (video, {"render": "write"}),
            "motion": (motion, {"render": "write"}),
        })
        state = await gateway.refresh()
        self.assertEqual(state["operation_count"], 2)
        selected = gateway.search("render", limit=2)
        self.assertEqual(len(selected["matches"]), 2)
        self.assertEqual(
            (await gateway.invoke("video/render", revision=state["revision"],
                                  inputs={"frames": 24}))["state"],
            "host_reported_success_unverified")
        self.assertEqual(
            (await gateway.invoke("motion/render", revision=state["revision"],
                                  inputs={"curve": [0.1, 0.9]}))["state"],
            "host_reported_success_unverified")
        self.assertEqual(video.calls, [("render", {"frames": 24})])
        self.assertEqual(motion.calls, [("render", {"curve": [0.1, 0.9]})])
        self.assertEqual(len(gateway.evidence()), 2)

    async def test_unavailable_invented_and_wrong_parameter_never_dispatch(self):
        e = Engine([tool("add_text_clip", {"text": {"type": "string"}})])
        gateway = CapabilityGateway({"video": (e, {"add_text_clip": "write"})})
        old = (await gateway.refresh())["revision"]
        for op, revision, inputs in (
            ("video/search", old, {}),
            ("video/add_text_clip", "f" * 64, {"text": "hello"}),
            ("video/add_text_clip", old, {"text": 9}),
            ("video/add_text_clip", old, {"wrongField": "unlisted"}),
        ):
            with self.subTest(op=op, inputs=inputs), self.assertRaises(
                (CapabilityExecutionError, CapabilityContractError)):
                await gateway.invoke(op, revision=revision, inputs=inputs)
        self.assertEqual(e.calls, [])
        self.assertEqual(gateway.evidence(), [])

    async def test_fresh_selected_engine_contract_change_fails_closed(self):
        e = Engine([tool("make", {"value": {"type": "string"}})])
        gateway = CapabilityGateway({"video": (e, {"make": "write"})})
        old = (await gateway.refresh())["revision"]
        e.tools = [tool("make", {"value": {"type": "number"}})]
        with self.assertRaisesRegex(CapabilityExecutionError, "contract changed"):
            await gateway.invoke("video/make", revision=old, inputs={"value": "x"})
        self.assertEqual(e.calls, [])
        new = await gateway.refresh()
        self.assertNotEqual(new["revision"], old)
        await gateway.invoke("video/make", revision=new["revision"], inputs={"value": 1.25})
        self.assertEqual(len(e.calls), 1)

    async def test_grantless_new_tool_cannot_become_executable_by_model(self):
        e = Engine([tool("edit"), tool("wipe_all")])
        g = CapabilityGateway({"motion": (e, {"edit": "write"})})
        state = await g.refresh()
        self.assertEqual(state["operation_count"], 1)
        self.assertFalse(g.search("wipe")["matches"])
        with self.assertRaises(CapabilityContractError):
            await g.invoke("motion/wipe_all", revision=state["revision"], inputs={})
        self.assertEqual(e.calls, [])

    async def test_required_host_state_never_derived_from_model_arguments(self):
        e = Engine([tool("import_asset", {"path": {"type": "string"}})])
        facts = {"project_open": False}
        g = CapabilityGateway({"video": (e, {"import_asset": "write"},
                                         {"import_asset": ["project_open"]},
                                         lambda: dict(facts))})
        revision = (await g.refresh())["revision"]
        with self.assertRaisesRegex(CapabilityExecutionError, "prerequisite"):
            await g.invoke("video/import_asset", revision=revision,
                           inputs={"path": "legitimate-asset.mp4"})
        self.assertEqual(e.calls, [])
        facts["project_open"] = True
        result = await g.invoke("video/import_asset", revision=revision,
                                inputs={"path": "legitimate-asset.mp4"})
        self.assertEqual(result["state"], "host_reported_success_unverified")
        self.assertEqual(len(e.calls), 1)

    async def test_missing_host_fact_reader_rejects_without_invoking(self):
        e = Engine([tool("render")])
        g = CapabilityGateway({"graphics": (e, {"render": "write"},
                                           {"render": ["layers_open"]})})
        rev = (await g.refresh())["revision"]
        with self.assertRaisesRegex(CapabilityExecutionError, "independently"):
            await g.invoke("graphics/render", revision=rev, inputs={})
        self.assertEqual(e.calls, [])

    async def test_native_write_failure_does_not_get_retried_or_claim_success(self):
        e = Engine([tool("edit", {"text": {"type": "string"}})])
        e.result = SimpleNamespace(is_error=True, content=[
            SimpleNamespace(type="text", text="private raw secret")])
        g = CapabilityGateway({"video": (e, {"edit": "write"})})
        rev = (await g.refresh())["revision"]
        result = await g.invoke("video/edit", revision=rev, inputs={"text": "secret"})
        self.assertEqual(result["state"], "write_uncertain_reconciliation_required")
        self.assertEqual(len(e.calls), 1)
        event = g.evidence()[0]
        self.assertEqual(event["state"], "write_uncertain_reconciliation_required")
        self.assertNotIn("secret", json.dumps(event))
        self.assertNotIn("private", json.dumps(event))

    async def test_transport_failure_preserves_uncertain_write_state(self):
        e = Engine([tool("edit")])
        e.fail = ConnectionError("private path")
        g = CapabilityGateway({"video": (e, {"edit": "write"})})
        rev = (await g.refresh())["revision"]
        with self.assertRaises(ConnectionError):
            await g.invoke("video/edit", revision=rev, inputs={})
        self.assertEqual(g.evidence()[0]["state"], "write_uncertain_reconciliation_required")
        self.assertEqual(len(e.calls), 1)

    async def test_reported_read_error_does_not_fabricate_native_write(self):
        e = Engine([tool("inspect")])
        e.result = SimpleNamespace(is_error=True, content=[])
        g = CapabilityGateway({"video": (e, {"inspect": "read"})})
        rev = (await g.refresh())["revision"]
        result = await g.invoke("video/inspect", revision=rev, inputs={})
        self.assertEqual(result["state"], "read_failed")
        self.assertEqual(g.evidence()[0]["access"], "read")

    async def test_no_parallel_writes_within_one_native_engine(self):
        e = Engine([tool("modify", {"n": {"type": "integer"}})])
        g = CapabilityGateway({"native": (e, {"modify": "write"})})
        revision = (await g.refresh())["revision"]
        await asyncio.gather(*[
            g.invoke("native/modify", revision=revision, inputs={"n": i})
            for i in range(12)])
        self.assertEqual(len(e.calls), 12)
        self.assertEqual(e.maximum_parallel, 1)

    async def test_one_selected_engine_invocation_does_not_discover_unrelated_engine(self):
        video = Engine([tool("edit")])
        class Other(Engine):
            async def list_tools(self):
                self.calls.append(("discovered", {}))
                return await super().list_tools()
        motion = Other([tool("keyframe")])
        g = CapabilityGateway({"video": (video, {"edit": "write"}),
                               "motion": (motion, {"keyframe": "write"})})
        revision = (await g.refresh())["revision"]
        motion.calls.clear()
        await g.invoke("video/edit", revision=revision, inputs={})
        self.assertEqual(motion.calls, [])


    async def test_host_granted_future_operation_appears_automatically_on_refresh(self):
        engine = Engine([tool("original_project")])
        grants = {"original_project": "write"}
        gateway = CapabilityGateway({"creative": (engine, lambda: dict(grants))})
        initial = await gateway.refresh()
        self.assertEqual(initial["operation_count"], 1)
        engine.tools.append(tool("future_vfx"))
        grants["future_vfx"] = "write"
        current = await gateway.refresh()
        self.assertEqual(current["operation_count"], 2)
        self.assertNotEqual(current["revision"], initial["revision"])
        self.assertEqual(gateway.search("future vfx")["matches"][0]["id"],
                         "creative/future_vfx")
        with self.assertRaises(CapabilityContractError):
            gateway.describe("creative/future_vfx", revision=initial["revision"])
        applied = await gateway.invoke("creative/future_vfx",
                                       revision=current["revision"], inputs={})
        self.assertEqual(applied["state"], "host_reported_success_unverified")
        self.assertEqual(engine.calls, [("future_vfx", {})])

    async def test_host_revokes_grant_after_discovery_and_gateway_blocks_execution(self):
        e = Engine([tool("write_original")])
        grants = {"write_original": "write"}
        gateway = CapabilityGateway({"video": (e, lambda: dict(grants))})
        rev = (await gateway.refresh())["revision"]
        grants.clear()
        with self.assertRaises(CapabilityContractError):
            await gateway.invoke("video/write_original", revision=rev, inputs={})
        self.assertEqual(e.calls, [])
        self.assertEqual(gateway.evidence(), [])


    async def test_incomplete_native_receipt_is_not_a_write_success(self):
        engine = Engine([tool("write_file")])
        engine.result = {"content": [{"type": "text", "text": "maybe saved"}]}
        g = CapabilityGateway({"graphics": (engine, {"write_file": "write"})})
        rev = (await g.refresh())["revision"]
        with self.assertRaisesRegex(CapabilityExecutionError, "status envelope"):
            await g.invoke("graphics/write_file", revision=rev, inputs={})
        self.assertEqual(g.evidence()[0]["state"],
                         "write_uncertain_reconciliation_required")
        self.assertEqual(len(engine.calls), 1)

    async def test_conflicting_and_nonboolean_native_mcp_status_is_never_success(self):
        for malformed in (
            {"is_error": False, "isError": True, "content": []},
            {"is_error": True, "isError": False, "content": []},
            {"is_error": 0, "content": []},
            {"isError": "false", "content": []},
            SimpleNamespace(is_error=False, isError=True, content=[]),
        ):
            with self.subTest(status=repr(malformed)[:100]):
                engine = Engine([tool("commit_edit")])
                engine.result = malformed
                gateway = CapabilityGateway(
                    {"video": (engine, {"commit_edit": "write"})})
                revision = (await gateway.refresh())["revision"]
                with self.assertRaisesRegex(
                        CapabilityExecutionError, "boolean status envelope"):
                    await gateway.invoke("video/commit_edit",
                                         revision=revision, inputs={})
                self.assertEqual(len(engine.calls), 1)
                self.assertEqual(gateway.evidence()[0]["state"],
                                 "write_uncertain_reconciliation_required")

    async def test_nonfinite_and_oversized_model_payloads_do_not_dispatch(self):
        engine = Engine([tool("draw", {"meta": {"type": "object"}})])
        g = CapabilityGateway({"graphics": (engine, {"draw": "write"})})
        rev = (await g.refresh())["revision"]
        for raw in ({"meta": {"danger": float("nan")}},
                    {"meta": {"huge": "x" * 262_200}}):
            with self.subTest(size=len(str(raw))):
                with self.assertRaises(CapabilityExecutionError):
                    await g.invoke("graphics/draw", revision=rev, inputs=raw)
        self.assertEqual(engine.calls, [])
        self.assertEqual(g.evidence(), [])


    async def test_versioned_mcp_page_two_executes_only_after_live_revalidation(self):
        class Versioned(Engine):
            async def list_tools(self, *, cursor=None):
                if cursor is None:
                    return {"jsonrpc": "2.0", "id": 1, "result": {
                        "resultType": "complete", "tools": [tool("inspect")],
                        "nextCursor": "next-vfx-page"}}
                if cursor == "next-vfx-page":
                    return {"jsonrpc": "2.0", "id": 2, "result": {
                        "resultType": "complete", "tools": [tool("glow")]}}
                raise AssertionError("Untrusted cursor")
        engine = Versioned([])
        gateway = CapabilityGateway({"vfx": (engine, {
            "inspect": "read", "glow": "write"})})
        rev = (await gateway.refresh())["revision"]
        result = await gateway.invoke("vfx/glow", revision=rev, inputs={})
        self.assertEqual(result["state"], "host_reported_success_unverified")
        self.assertEqual(engine.calls, [("glow", {})])

    async def test_versioned_mcp_partial_revalidation_blocks_all_native_writes(self):
        class Changing(Engine):
            def __init__(self):
                super().__init__([tool("write")])
                self.incomplete = False
            async def list_tools(self):
                return {"result": {"resultType":
                    "input_required" if self.incomplete else "complete",
                    "tools": [tool("write")]}}
        engine = Changing()
        gateway = CapabilityGateway({"graphics": (engine, {"write": "write"})})
        rev = (await gateway.refresh())["revision"]
        engine.incomplete = True
        with self.assertRaises(CapabilityContractError):
            await gateway.invoke("graphics/write", revision=rev, inputs={})
        self.assertEqual(engine.calls, [])
        self.assertEqual(gateway.evidence(), [])

    async def test_gateway_revalidates_target_discovered_on_second_mcp_page(self):
        class Paged(Engine):
            async def list_tools(self, *, cursor=None):
                if cursor is None:
                    return SimpleNamespace(tools=[tool("first")], nextCursor="cursor42")
                self.calls.append(("paging_read", {}))
                return SimpleNamespace(tools=[tool("real_project_edit")],
                                       nextCursor=None)
        engine = Paged([])
        gateway = CapabilityGateway({"video": (engine, {
            "first": "read", "real_project_edit": "write"})})
        rev = (await gateway.refresh())["revision"]
        self.assertEqual(gateway.search("project edit")["matches"][0]["id"],
                         "video/real_project_edit")
        engine.calls.clear()
        result = await gateway.invoke("video/real_project_edit", revision=rev, inputs={})
        self.assertEqual(result["state"], "host_reported_success_unverified")
        self.assertEqual(engine.calls, [
            ("paging_read", {}), ("real_project_edit", {})])


if __name__ == "__main__":
    unittest.main()
