"""Expose an installed BODY connection to a Brain ONLY through its host gateway.

This bridges the existing model/native MCP session protocol, rather than
building another tool runner. The gateway still owns live grant/schema checks,
the source lock, the shared session budget and optional durable admission.
The wrapper cannot attest actual native state or artistic quality.
"""
from __future__ import annotations

import copy
import base64
import inspect
import json
from types import SimpleNamespace

from .body_picture_observation import TOOL as BODY_PICTURE_TOOL, validate_picture_receipt
from .capability_fabric import (
    discover_all_live_tools, CapabilityContractError, CapabilityFabric)
from .capability_gateway import (CapabilityExecutionError, CapabilityGateway,
                                 NativeReferencePreDispatchError, CapabilityPreDispatchError,
                                 _source_native_commit_intent)
from .native_editor_identity import _project_state, _read_json_result, _ids
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
        self._model_has_observed_project = False
        self._model_observed_timeline_id = None
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
                    input_schema=copy.deepcopy(current["input_schema"]),
                    access=current["access"],
                    requires=list(current["requires"]),
                    may_enable=list(current["may_enable"])))
        return SimpleNamespace(tools=allowed, nextCursor=None)


    async def _observed_source_inventory(self):
        """Optional read-only source witness; failure never mints model authority."""
        identity = self._gateway._bindings[self._namespace][5]
        if not identity or not identity.get("fence"):
            return None
        try:
            observation = identity["reader"]()
            if inspect.isawaitable(observation):
                observation = await observation
            return observation if type(observation) is dict else None
        except Exception:
            # A source not currently readable must never substitute a guessed
            # version or break an otherwise valid model-selected native READ.
            return None

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
            self._model_has_observed_project = False
            self._model_observed_timeline_id = None
        # A Brain may inspect the *complete* active timeline immediately after
        # an acknowledged native edit. The older session required another
        # get_project turn solely to renew the source revision, even though the
        # model just chose a real timeline read. Bracket that model-visible
        # read with host-only complete source observations. Neither host READ
        # is a creative decision, permission, preview apply or hidden write.
        full_timeline_read = (self._require_model_native_observation and
            self._model_has_observed_project and name == "get_timeline" and
            type(arguments) is dict and arguments.get("includeClips") is True)
        before_timeline = None
        if full_timeline_read:
            before_timeline = await self._observed_source_inventory()
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
                source = _project_state(native)
                live = native.get("zx7NativeRevision")
                if (type(live) is str and 38 <= len(live) <= 80 and
                        all(33 <= ord(char) <= 126 for char in live)):
                    self._model_observed_native_revision = live
                    self._model_has_observed_project = True
                    self._model_observed_timeline_id = source[1]
            except (TypeError, ValueError):
                pass
        if (full_timeline_read and before_timeline is not None and
                result["state"] == "host_reported_success_unverified"):
            after_timeline = await self._observed_source_inventory()
            try:
                actual = _read_json_result(result["native_result"])
                source_version = before_timeline["__zx7_live_revision"]
                if (before_timeline == after_timeline and
                        type(source_version) is str and
                        38 <= len(source_version) <= 80 and
                        actual.get("id") == self._model_observed_timeline_id and
                        actual.get("clipLimitApplied") is False and
                        _ids(actual.get("tracks")) == before_timeline["tracks"]["ids"] and
                        _ids(actual.get("clips")) == before_timeline["clips"]["ids"]):
                    # This fresh project/timeline view reached the Brain; a
                    # later human edit still changes the source CAS at dispatch.
                    self._model_observed_native_revision = source_version
            except (TypeError, KeyError, ValueError):
                # Malformed, incomplete, conflicting or stale read: retain
                # the original no-dispatch gate until a new get_project.
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


def _model_tool_description(tool):
    """Expose host-owned affordances, not invented artistic instructions."""
    notes = ["Host access: " + tool.access + "."]
    if tool.requires:
        notes.append("Requires: " + ", ".join(tool.requires) + ".")
    if tool.may_enable:
        notes.append("May enable: " + ", ".join(tool.may_enable) + ".")
    return " ".join([tool.description, *notes]).strip()


_PRE_DISPATCH_FEEDBACK = {
    "host_session_call_budget_exhausted":
        "Host session call budget exhausted. Stop; a new owner-authorized session is required.",
    "host_session_write_budget_exhausted":
        "Host session write budget exhausted. Stop writes; read-only inspection may remain available.",
    "host_source_call_budget_exhausted":
        "Host source call budget exhausted. Stop calls to this source.",
    "invalid_native_parameters":
        "Arguments do not match the admitted input schema. Inspect that schema and correct the arguments.",
    "invalid_input_object":
        "Arguments must be a JSON object. Inspect the admitted input schema.",
    "invalid_input_json":
        "Arguments must be finite JSON values. Correct the arguments.",
    "input_budget_exceeded":
        "Arguments exceed the host input size budget. Reduce the request without changing its meaning.",
}


def _pre_dispatch_feedback(error):
    message = _PRE_DISPATCH_FEEDBACK.get(error.code)
    if message is None:
        return None
    return "No native operation was dispatched. " + message


def create_combined_mcp_server(view: CombinedCapabilityMcpSession):
    """Export one admitted, model-independent creative BODY via official MCP.

    No provider, prompt, duplicate runner or new permissions. The existing
    combined session and gateway remain the only execution boundary. Serialize
    calls from this client so its last observed native revision cannot race
    another call in the same client session.
    """
    import anyio
    from mcp import types
    from mcp.server import Server

    if not isinstance(view, CombinedCapabilityMcpSession):
        raise CapabilityExecutionError("A host-admitted combined BODY session is required")
    lock = anyio.Lock()

    def failure(message):
        return types.CallToolResult(is_error=True, content=[
            types.TextContent(type="text", text=message)])

    async def list_tools(_context, _params=None):
        async with lock:
            actual = await view.list_tools()
        return types.ListToolsResult(tools=[types.Tool(
            name=tool.name, description=_model_tool_description(tool),
            inputSchema=tool.input_schema,
            annotations=types.ToolAnnotations(readOnlyHint=(tool.access == "read"))
            ) for tool in actual.tools])

    async def call_tool(_context, params):
        # Shield an admitted native call from cancellation: do not abandon a
        # possibly applied write or let the next request race its readback.
        async with lock:
            with anyio.CancelScope(shield=True):
                try:
                    result = await view.call_tool(
                        params.name, {} if params.arguments is None else params.arguments)
                except CapabilityPreDispatchError as exc:
                    return failure(_pre_dispatch_feedback(exc) or
                        "BODY could not establish a safe operation outcome; inspect current state. Do not blindly retry writes.")
                except (CapabilityExecutionError, CapabilityContractError):
                    return failure("BODY admission or receipt failed; inspect actual state. Do not blindly retry a write.")
                except Exception:
                    return failure("BODY operation failed; a write may have occurred. Inspect native state before retrying.")
        # Preserve official editor SDK results, including image/audio content
        # and trusted no-dispatch/conflict metadata, without reconstruction.
        if isinstance(result, types.CallToolResult):
            return result
        # Installed local BODY and trusted gateway rejections return the
        # existing MCP-shaped text result. Reject unknown shapes, do not infer
        # success or silently drop a sensor/metadata block.
        blocks = getattr(result, "content", None)
        status = getattr(result, "is_error", None)
        if params.name == BODY_PICTURE_TOOL and status is False:
            try:
                if (not isinstance(blocks, (list, tuple)) or len(blocks) != 2 or
                        blocks[0].type != "text" or blocks[1].type != "image" or
                        blocks[1].mime_type != "image/png" or len(blocks[1].data) > 6_000_000):
                    raise ValueError("Invalid BODY picture blocks")
                validate_picture_receipt(json.loads(blocks[0].text),
                    base64.b64decode(blocks[1].data, validate=True),
                    (params.arguments or {}).get("source_sha256"))
                return types.CallToolResult(is_error=False, content=[
                    types.TextContent(type="text", text=blocks[0].text),
                    types.ImageContent(type="image", data=blocks[1].data, mimeType="image/png")])
            except (ValueError, AttributeError, TypeError):
                return failure("BODY picture did not match its source-bound receipt.")
        if (type(status) is not bool or not isinstance(blocks, (list, tuple)) or
                not all(getattr(block, "type", None) == "text" and
                        isinstance(getattr(block, "text", None), str) for block in blocks)):
            return failure("BODY returned an unsupported receipt; inspect native state before retrying.")
        meta = getattr(result, "meta", None)
        return types.CallToolResult(is_error=status, content=[
            types.TextContent(type="text", text=block.text) for block in blocks],
            **({"_meta": meta} if meta is not None else {}))

    return Server("zx7-creative-studio", version="0.2.0",
                  on_list_tools=list_tools, on_call_tool=call_tool)
