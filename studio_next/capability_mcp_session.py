"""Expose an installed BODY connection to a Brain ONLY through its host gateway.

This bridges the existing model/native MCP session protocol, rather than
building another tool runner. The gateway still owns live grant/schema checks,
the source lock, the shared session budget and optional durable admission.
The wrapper cannot attest actual native state or artistic quality.
"""
from __future__ import annotations

from types import SimpleNamespace

from .capability_fabric import (
    discover_all_live_tools, CapabilityContractError, CapabilityFabric)
from .capability_gateway import CapabilityExecutionError, CapabilityGateway


class CapabilityGatewayMcpSession:
    """Source-neutral MCP-shaped view over a trusted existing gateway.

    Create this only after the host has connected sources and called
    gateway.refresh(). The selected catalog revision and grants are fixed for
    this adapter's lifetime. New tools/rights require explicit new admission.
    The creative model cannot choose durable request identities.
    """

    def __init__(self, gateway: CapabilityGateway, namespace: str, *,
                 host_request_id_allocator=None):
        if not isinstance(gateway, CapabilityGateway):
            raise CapabilityExecutionError("A real trusted BODY gateway is required")
        if namespace not in gateway._bindings:
            raise CapabilityExecutionError("Requested BODY source is not installed")
        if (host_request_id_allocator is not None and
                not callable(host_request_id_allocator)):
            raise CapabilityExecutionError("Only a host callback may assign write IDs")
        self._gateway = gateway
        self._namespace = namespace
        self._session = gateway._bindings[namespace][0]
        self._revision = gateway._current().revision
        self._original_grants = gateway._live_grants(namespace)
        self._allocate = host_request_id_allocator
        if gateway._attempt_store is not None and host_request_id_allocator is None:
            raise CapabilityExecutionError(
                "Durable BODY writes require a host request-ID allocator")

    def _operation(self, name):
        if not isinstance(name, str) or name not in self._original_grants:
            raise CapabilityExecutionError(
                "Native operation not granted to this Brain session")
        if self._gateway._current().revision != self._revision:
            raise CapabilityExecutionError(
                "Native BODY catalog changed; create a newly admitted session")
        return f"{self._namespace}/{name}"

    async def list_tools(self):
        """Expose only originally granted, live-advertised native tools."""
        if self._gateway._current().revision != self._revision:
            raise CapabilityExecutionError(
                "Native BODY catalog changed; create a newly admitted session")
        live = await discover_all_live_tools(self._session)
        current_grants = self._gateway._live_grants(self._namespace)
        # Reuse the same canonical host catalog compiler: it normalizes long
        # tool descriptions and JSON schemas. Comparing raw descriptions to
        # the admitted summary would reject perfectly stable real BODY tools.
        bound = self._gateway._bindings[self._namespace]
        try:
            fresh = CapabilityFabric({self._namespace: (
                live, current_grants, bound[2], bound[4])})
        except CapabilityContractError as exc:
            raise CapabilityExecutionError(
                "Native tool discovery no longer matches host admission") from exc
        allowed = []
        for tool in live:
            name = getattr(tool, "name", None)
            if (isinstance(name, str) and
                    current_grants.get(name) == self._original_grants.get(name) and
                    name in self._original_grants):
                try:
                    operation = self._operation(name)
                    current = self._gateway._current().resolve(
                        operation, revision=self._revision)
                    actual = fresh.resolve(operation, revision=fresh.revision)
                except CapabilityContractError as exc:
                    raise CapabilityExecutionError(
                        "Native tool discovery diverged from host admission") from exc
                if any(current[key] != actual[key] for key in (
                        "input_schema", "description", "access",
                        "requires", "may_enable")):
                    raise CapabilityExecutionError(
                        "Native tool metadata changed; host must refresh discovery")
                allowed.append(tool)
        return SimpleNamespace(tools=allowed, nextCursor=None)

    async def call_tool(self, name, arguments):
        """Route the exact native call through the existing source lock/policy.

        A failed or uncertain WRITE is not retried. Return the underlying MCP
        object unchanged so existing native inspectors can validate its status.
        """
        operation = self._operation(name)
        record = self._gateway._current().resolve(
            operation, revision=self._revision)
        request_id = None
        if record["access"] == "write" and self._gateway._attempt_store is not None:
            # Allocator belongs to the trusted host, not the model or raw tool.
            request_id = self._allocate(operation)
            if not isinstance(request_id, str) or not request_id.strip():
                raise CapabilityExecutionError(
                    "Host did not issue a durable native request identity")
        result = await self._gateway.invoke(
            operation, revision=self._revision,
            inputs=arguments, request_id=request_id)
        return result["native_result"]
