"""Expose an installed BODY connection to a Brain ONLY through its host gateway.

This bridges the existing model/native MCP session protocol, rather than
building another tool runner. The gateway still owns live grant/schema checks,
the source lock, the shared session budget and optional durable admission.
The wrapper cannot attest actual native state or artistic quality.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

from .capability_fabric import (
    discover_all_live_tools, CapabilityContractError, CapabilityFabric)
from .capability_gateway import (CapabilityExecutionError, CapabilityGateway,
                                 NativeReferencePreDispatchError,
                                 _source_native_commit_intent)
from .native_editor_identity import _project_state, _read_json_result
from .body_editor_client import (
    HOST_PRE_DISPATCH_META, HOST_REJECTION_FEEDBACK,
    HOST_NATIVE_REVISION_META, HOST_NATIVE_REVISION_FEEDBACK,
    native_input_digest,
)


class CapabilityGatewayMcpSession:
    """Source-neutral MCP-shaped view over a trusted existing gateway.

    Create this only after the host has connected sources and called
    gateway.refresh(). The selected catalog revision and grants are fixed for
    this adapter's lifetime. New tools/rights require explicit new admission.
    The creative model cannot choose durable request identities.
    """

    def __init__(self, gateway: CapabilityGateway, namespace: str, *,
                 host_request_id_allocator=None,
                 require_model_native_observation=False):
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
        if type(require_model_native_observation) is not bool:
            raise CapabilityExecutionError("Native model-observation admission needs a host boolean")
        identity = gateway._bindings[namespace][5]
        if (require_model_native_observation and
                (not identity or not identity["fence"] or
                 self._original_grants.get("get_project") != "read")):
            raise CapabilityExecutionError(
                "Model-observed native revisions need a source-pinned writer and project read")
        self._require_model_native_observation = require_model_native_observation
        self._model_observed_native_revision = None
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
                # Expose the admitted, bounded host summary and a fresh
                # schema copy, never a plugin object's arbitrary attributes
                # or changed long description masquerading as host authority.
                allowed.append(SimpleNamespace(
                    name=name, description=current["description"],
                    input_schema=copy.deepcopy(current["input_schema"])))
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
        # Only a successful, source-shaped native get_project read made via
        # this exact model-visible session can establish model observation.
        # A host-only preflight read must never silently promote stale intent.
        if self._require_model_native_observation and name == "get_project":
            self._model_observed_native_revision = None
        observed = {}
        if self._require_model_native_observation and record["access"] == "write":
            observed["model_observed_revision"] = self._model_observed_native_revision
            # Source-attested preview-only calls are observations, not
            # mutations. Do not force another expensive model turn merely
            # because the editor returned a safe native edit plan. Every
            # real or uncertain commit still invalidates the older view.
            fences = self._gateway._bindings[self._namespace][5]["fence"]
            native_preview = (name in fences and
                              not _source_native_commit_intent(name, arguments))
            if not native_preview:
                self._model_observed_native_revision = None
        try:
            result = await self._gateway.invoke(
                operation, revision=self._revision,
                inputs=arguments, request_id=request_id, **observed)
        except NativeReferencePreDispatchError as exc:
            # This trusted gateway exception is raised before the first
            # stateful RPC / durable admission, NEVER for uncertain writes.
            # The existing controller verifies tool+input digests and then
            # lets the model independently choose a corrected operation.
            if exc.code not in HOST_REJECTION_FEEDBACK:
                raise CapabilityExecutionError(
                    "Unrecognized host native reference rejection") from None
            return SimpleNamespace(
                is_error=True,
                content=[SimpleNamespace(
                    type="text", text=HOST_REJECTION_FEEDBACK[exc.code])],
                meta={HOST_PRE_DISPATCH_META: {
                    "version": 1, "tool": name,
                    "inputs_sha256": native_input_digest(arguments),
                    "code": exc.code}})
        if result["state"] == "native_conflict_rejected_no_write":
            code = "native_revision_changed_at_commit"
            return SimpleNamespace(
                is_error=True,
                content=[SimpleNamespace(
                    type="text", text=HOST_NATIVE_REVISION_FEEDBACK[code])],
                meta={HOST_NATIVE_REVISION_META: {
                    "version": 1, "tool": name,
                    "inputs_sha256": native_input_digest(arguments),
                    "code": code}})
        if self._require_model_native_observation and name == "get_project":
            # Native response and MCP status are checked, never model text.
            # An unavailable/partial project read deliberately leaves this
            # session without write authority until a complete new read.
            try:
                native = _read_json_result(result["native_result"])
                _project_state(native)
                live = native.get("zx7NativeRevision")
                if (type(live) is str and 38 <= len(live) <= 80 and
                        all(33 <= ord(char) <= 126 for char in live)):
                    self._model_observed_native_revision = live
            except (TypeError, ValueError):
                pass
        return result["native_result"]


class CombinedCapabilityMcpSession:
    """Expose distinct host-granted sources through one model tool view."""

    def __init__(self, gateway, *namespaces,
                 require_model_native_observation_for=()):
        if (not isinstance(require_model_native_observation_for,
                           (tuple, list, set, frozenset)) or
                not set(require_model_native_observation_for).issubset(namespaces)):
            raise CapabilityExecutionError("Model-observation domains must be host-connected")
        self._sessions = [CapabilityGatewayMcpSession(
            gateway, name,
            require_model_native_observation=(
                name in require_model_native_observation_for))
            for name in namespaces]
        self._routes = {}
        for session in self._sessions:
            for tool in session._original_grants:
                if tool in self._routes:
                    raise CapabilityExecutionError("Creative sources advertise a duplicate tool name")
                self._routes[tool] = session

    async def list_tools(self):
        tools = []
        for session in self._sessions:
            tools.extend((await session.list_tools()).tools)
        return SimpleNamespace(tools=tools, nextCursor=None)

    async def call_tool(self, name, arguments):
        if not isinstance(name, str) or name not in self._routes:
            raise CapabilityExecutionError("Creative operation is not granted to this session")
        return await self._routes[name].call_tool(name, arguments)
