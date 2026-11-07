"""Domain-neutral MCP proxy admission tests; synthetic tools are NOT art."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from studio_next.body_capability_adapter import connect_installed_zx7_body
from studio_next.capability_attempts import CapabilityAttemptStore
from studio_next.capability_gateway import CapabilityExecutionError, CapabilityGateway
from studio_next.capability_mcp_session import CapabilityGatewayMcpSession
from studio_next.capability_session_budget import CapabilitySessionBudget


class LocalMcpSource:
    def __init__(self):
        self.names = ("read_native", "write_native", "forbidden_native")
        self.calls = []
        self.discoveries = 0

    async def list_tools(self):
        self.discoveries += 1
        return SimpleNamespace(nextCursor=None, tools=[
            SimpleNamespace(name=n, description="Installed native " + n,
                input_schema={"type": "object",
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"]})
            for n in self.names])

    async def call_tool(self, name, inputs):
        self.calls.append((name, inputs))
        return SimpleNamespace(
            is_error=False,
            content=[SimpleNamespace(type="text", text='{"success":true}')])


class GatewayMcpSessionTests(unittest.IsolatedAsyncioTestCase):
    async def _connect(self, source, budget=None, journal=None, grants=None):
        gateway = CapabilityGateway({
            "graphics": (source, grants or {
                "read_native": "read", "write_native": "write"}),
        }, session_budget=budget, attempt_store=journal)
        await gateway.refresh()
        return gateway

    async def test_one_brain_cannot_bypass_shared_write_or_call_ceiling(self):
        source=LocalMcpSource()
        budget=CapabilitySessionBudget(
            max_calls=2, max_writes=1, per_source={"graphics": 2})
        gateway=await self._connect(source,budget)
        session=CapabilityGatewayMcpSession(gateway,"graphics")
        visible=await session.list_tools()
        self.assertEqual({x.name for x in visible.tools},
            {"read_native","write_native"})
        self.assertIsNone(visible.nextCursor)
        self.assertTrue((await session.call_tool(
            "read_native", {"value":1})).content)
        self.assertTrue((await session.call_tool(
            "write_native", {"value":2})).content)
        with self.assertRaisesRegex(
                CapabilityExecutionError, "host_session_call_budget_exhausted"):
            await session.call_tool("write_native", {"value":3})
        self.assertEqual([name for name,_ in source.calls],
                         ["read_native","write_native"])
        self.assertEqual(gateway.host_budget_evidence()["reserved_calls"],2)
        self.assertEqual(gateway.host_budget_evidence()["reserved_writes"],1)

    async def test_ungranted_tool_never_reaches_real_source(self):
        source=LocalMcpSource()
        gateway=await self._connect(source)
        session=CapabilityGatewayMcpSession(gateway,"graphics")
        with self.assertRaisesRegex(
                CapabilityExecutionError,"not granted"):
            await session.call_tool("forbidden_native",{"value":1})
        self.assertEqual(source.calls,[])

    async def test_session_lease_rejects_refresh_and_live_grant_revocation(self):
        source=LocalMcpSource()
        grant_ref={"read_native":"read","write_native":"write"}
        gateway=await self._connect(source,grants=lambda:dict(grant_ref))
        session=CapabilityGatewayMcpSession(gateway,"graphics")
        grant_ref.pop("write_native")
        self.assertEqual([x.name for x in (await session.list_tools()).tools],
                         ["read_native"])
        with self.assertRaises(Exception):
            await session.call_tool("write_native",{"value":2})
        self.assertEqual(source.calls,[])
        await gateway.refresh()
        with self.assertRaisesRegex(
                CapabilityExecutionError,"catalog changed"):
            await session.call_tool("read_native",{"value":1})
        self.assertEqual(source.calls,[])

    async def test_durable_write_identity_only_from_host_callback(self):
        with tempfile.TemporaryDirectory() as root:
            source=LocalMcpSource()
            ledger=CapabilityAttemptStore(Path(root)/"native.sqlite3")
            gateway=await self._connect(source,journal=ledger)
            with self.assertRaisesRegex(
                    CapabilityExecutionError,"host request-ID allocator"):
                CapabilityGatewayMcpSession(gateway,"graphics")
            given=[]
            def allocate(operation):
                given.append(operation)
                return "owner-issued-native-request-001"
            session=CapabilityGatewayMcpSession(
                gateway,"graphics",host_request_id_allocator=allocate)
            await session.call_tool("write_native",{"value":4})
            self.assertEqual(given,["graphics/write_native"])
            self.assertEqual(ledger.inspect(
                "owner-issued-native-request-001")["state"],
                "host_reported_success_unverified")
            # A duplicate host ID cannot cause a second native write.
            with self.assertRaises(Exception):
                await session.call_tool("write_native",{"value":4})
            self.assertEqual(len(source.calls),1)

    async def test_genuine_installed_zx7_body_read_is_admitted_once(self):
        # Real installed native BODY operation, not a fake external renderer.
        with tempfile.TemporaryDirectory() as root:
            budget=CapabilitySessionBudget(max_calls=1,max_writes=0)
            gateway=await connect_installed_zx7_body(
                root,allowed_access=("read",),session_budget=budget)
            session=CapabilityGatewayMcpSession(gateway,"zx7")
            names={x.name for x in (await session.list_tools()).tools}
            self.assertIn("body.timecode_format",names)
            result=await session.call_tool("body.timecode_format",{
                "frame_index":48,"numerator":24,"denominator":1,
                "drop_frame":False})
            self.assertFalse(result.is_error)
            self.assertTrue(result.content[0].text)
            with self.assertRaisesRegex(
                    CapabilityExecutionError,"host_session_call_budget_exhausted"):
                await session.call_tool("body.timecode_format",{
                    "frame_index":48,"numerator":24,"denominator":1,
                    "drop_frame":False})
            self.assertEqual(gateway.host_budget_evidence()["reserved_calls"],1)


if __name__=="__main__":
    unittest.main()
