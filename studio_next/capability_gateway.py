"""Model-neutral, source-agnostic runtime for actual host-granted BODY operations.

Never infer execution rights from a model, retrieved tool annotation, readme,
or a tool name. Local engine and official MCP adapters expose list_tools /
call_tool. The host registers grants and optional fact readers. A compact
brain needs only capability IDs returned by search + an exact input contract.
No hardcoded video, VFX, animation, or design tool names.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
from collections.abc import Mapping

from .capability_fabric import (
    CapabilityContractError, CapabilityFabric, discover_all_live_tools)
from .body_editor_mcp import _local_schema_references
from .capability_attempts import CapabilityAttemptStore


class CapabilityExecutionError(ValueError):
    """Rejected BEFORE any native dispatch; no guessed operation is allowed."""


def _wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _native_mcp_status(result):
    """No native write evidence without a consistent strict boolean status."""
    missing = object()
    if isinstance(result, dict):
        values = [result.get(key, missing) for key in ("is_error", "isError")]
    else:
        values = [getattr(result, key, missing) for key in ("is_error", "isError")]
    present = [value for value in values if value is not missing]
    if (not present or any(type(value) is not bool for value in present)
            or len(set(present)) != 1):
        raise CapabilityExecutionError(
            "Native host returned no unambiguous boolean status envelope")
    return present[0]


class CapabilityGateway:
    """Trusted host-owned source connections, not a model/plugin write proxy.

    bindings: namespace -> (connected_session, trusted grants, [prerequisites],
                             [trusted async or sync fact reader]).
    The fact reader accepts no model-provided data and returns a mapping of
    host-attested boolean facts. Missing facts deny prerequisite admission.
    """

    def __init__(self, bindings: Mapping, *, attempt_store=None):
        if attempt_store is not None and not isinstance(attempt_store, CapabilityAttemptStore):
            raise CapabilityExecutionError("Only the trusted durable capability ledger is permitted")
        self._attempt_store = attempt_store
        if not isinstance(bindings, Mapping) or not 1 <= len(bindings) <= 256:
            raise CapabilityExecutionError("Connected host-bound source inventory is required")
        self._bindings = {}
        self._locks = {}
        for namespace, entry in bindings.items():
            if not isinstance(entry, tuple) or len(entry) not in (2, 3, 4, 5):
                raise CapabilityExecutionError("Source requires a real connection and grants")
            session, grants = entry[:2]
            requires = entry[2] if len(entry) >= 3 else {}
            facts = entry[3] if len(entry) >= 4 else None
            possible_effects = entry[4] if len(entry) == 5 else {}
            if (not callable(getattr(session, "list_tools", None)) or
                    not callable(getattr(session, "call_tool", None)) or
                    not (isinstance(grants, Mapping) or callable(grants)) or
                    (isinstance(grants, Mapping) and
                     any(not isinstance(k, str) or v not in ("read", "write")
                         for k, v in grants.items())) or
                    (facts is not None and not callable(facts))):
                raise CapabilityExecutionError("Host source bindings are invalid")
            # A trusted, host-owned callable can reflect newly installed
            # first-party tools after refresh; static grants for external
            # plugins remain fixed unless the host explicitly reconfigures.
            grant_source = grants if callable(grants) else dict(grants)
            self._bindings[namespace] = (session, grant_source,
                                         copy.deepcopy(requires), facts,
                                         copy.deepcopy(possible_effects))
            self._locks[namespace] = asyncio.Lock()
        self._fabric = None
        self._events = []

    def _live_grants(self, namespace):
        source = self._bindings[namespace][1]
        grants = source() if callable(source) else source
        if (not isinstance(grants, Mapping) or
                any(not isinstance(k, str) or not k or v not in ("read", "write")
                    for k, v in grants.items())):
            raise CapabilityExecutionError("Trusted host grants unavailable or malformed")
        return dict(grants)

    async def refresh(self):
        """Rebuild from real connected sources, e.g. after MCP list_changed.

        Refreshing changes the contract digest. Previously selected handles
        never gain authority under an updated ABI or grant set.
        """
        discovery = {name: (entry[0], self._live_grants(name),
                            entry[2], entry[4])
                     for name, entry in self._bindings.items()}
        fabric = await CapabilityFabric.from_connections(discovery)
        self._fabric = fabric
        return fabric.overview()

    def _current(self):
        if self._fabric is None:
            raise CapabilityExecutionError("Discover the real connected BODY before use")
        return self._fabric

    def search(self, query, *, limit=6):
        return self._current().search(query, limit=limit)

    def describe(self, operation_id, *, revision):
        return self._current().describe(operation_id, revision=revision)

    async def host_affordances(self, namespace: str, *, limit=4):
        """Only source-attested project facts; model cannot mint readiness."""
        self._current()
        if namespace not in self._bindings:
            raise CapabilityExecutionError("Unknown connected creative engine")
        _, _, _, reader, _ = self._bindings[namespace]
        if reader is None:
            raise CapabilityExecutionError("Missing trusted source state reader")
        facts = reader()
        if inspect.isawaitable(facts):
            facts = await facts
        choices = self._current().affordance_frontier(
            trusted_facts=facts, limit=limit, namespace=namespace)
        return {"revision": choices["revision"], "matches": choices["matches"],
                "has_more": choices["has_more"],
                "facts_are_host_attested": True,
                "no_creative_operation_executed": True}

    def evidence(self):
        """Only bounded identity/digest and outcome, never raw private media."""
        return copy.deepcopy(self._events)

    async def invoke(self, operation_id, *, revision, inputs, request_id=None):
        """One model-selected operation; never auto-retry uncertain writes.

        Always re-discover live tool ABI and grants under a per-source lock
        before the call. State gates are advisory in the catalog but enforced
        here when a trusted source explicitly declares prerequisites.
        Individual native engines still enforce their own path/rights policies.
        When configured with a durable attempt ledger, the host must provide
        a stable request_id for every WRITE. No client/model request text may
        create a second execution of the same admitted request.
        """
        prior = self._current()
        record = prior.resolve(operation_id, revision=revision)
        namespace, name = record["source"], record["native_name"]
        async with self._locks[namespace]:
            # Revalidate ONLY the selected engine, not every connected
            # creative app on each frame/operation. Cross-domain scaling
            # must not make single-engine edits O(all connected tools).
            session, _, conditions, fact_reader, effects = self._bindings[namespace]
            grants = self._live_grants(namespace)
            advertised = await discover_all_live_tools(session)
            fresh = CapabilityFabric({namespace: (
                advertised, grants, conditions, effects)})
            live_record = fresh.resolve(operation_id, revision=fresh.revision)
            for field in ("access", "input_schema", "description",
                          "requires", "may_enable"):
                if record[field] != live_record[field]:
                    raise CapabilityExecutionError(
                        "Native operation contract changed; rediscover capability")
            if name not in grants or grants[name] != record["access"]:
                raise CapabilityExecutionError("Native grant changed before operation")
            current = prior
            schema = copy.deepcopy(record["input_schema"])
            _local_schema_references(schema)
            import jsonschema
            if not isinstance(inputs, dict):
                raise CapabilityExecutionError("BODY inputs must be a structured object")
            try:
                encoded_inputs = _wire(inputs).encode("utf-8")
            except (ValueError, TypeError, OverflowError, RecursionError) as exc:
                raise CapabilityExecutionError("Native model inputs must be finite JSON") from exc
            if len(encoded_inputs) > 262_144:
                raise CapabilityExecutionError("Native model inputs exceed bounded ABI budget")
            # Host-named top-level fields are an ABI. Unspecified top-level
            # fields invite model hallucinations; intentionally open nested
            # artistic parameters remain unrestricted by this preflight.
            if (isinstance(schema.get("properties"), dict) and
                    "additionalProperties" not in schema and
                    "patternProperties" not in schema):
                schema["additionalProperties"] = False
            validator_type = jsonschema.validators.validator_for(schema)
            validator_type.check_schema(schema)
            invalid = next(validator_type(schema).iter_errors(inputs), None)
            if invalid is not None:
                raise CapabilityExecutionError(
                    "Invalid native parameters (" + str(invalid.validator)[:40] + ")")
            requirements = record["requires"]
            if requirements:
                if fact_reader is None:
                    raise CapabilityExecutionError(
                        "Required machine state cannot be independently established")
                facts = fact_reader()
                if inspect.isawaitable(facts):
                    facts = await facts
                readiness = current.check_prerequisites(
                    operation_id, revision=revision, trusted_facts=facts)
                if not readiness["admissible"]:
                    raise CapabilityExecutionError(
                        "Machine prerequisite absent or unknown; inspect host state")
            digest = hashlib.sha256(encoded_inputs).hexdigest()
            durable_write = (self._attempt_store is not None and
                             record["access"] == "write")
            if durable_write:
                # Commit to SQLite BEFORE the first non-idempotent RPC. A
                # process death after admission is conservatively unresolved,
                # even if the native worker never received the request.
                self._attempt_store.admit(
                    request_id=request_id, operation_id=operation_id,
                    catalog_revision=revision, input_sha256=digest)
            trace = {"operation_id": operation_id, "catalog_revision": revision,
                     "input_sha256": digest, "access": record["access"],
                     "state": "submitted_unconfirmed"}
            if durable_write:
                trace["durable_request_id_sha256"] = hashlib.sha256(
                    request_id.encode("utf-8")).hexdigest()
            self._events.append(trace)
            try:
                # One submission only; uncertain writes require reconciliation.
                result = await session.call_tool(name, copy.deepcopy(inputs))
            except BaseException:
                trace["state"] = ("read_failed" if record["access"] == "read"
                                  else "write_uncertain_reconciliation_required")
                if durable_write:
                    self._attempt_store.settle(
                        request_id=request_id, state=trace["state"])
                raise
            try:
                failure = _native_mcp_status(result)
            except CapabilityExecutionError:
                # The remote operation MAY already have mutated the document.
                # Contradictory and nonboolean statuses never become success.
                trace["state"] = ("read_failed" if record["access"] == "read"
                                  else "write_uncertain_reconciliation_required")
                if durable_write:
                    self._attempt_store.settle(
                        request_id=request_id, state=trace["state"])
                raise
            if failure:
                trace["state"] = ("read_failed" if record["access"] == "read"
                                  else "write_uncertain_reconciliation_required")
            else:
                # A successful MCP transport is NOT proof a native edit
                # committed. Preview-only, internal application failures and
                # delayed state visibility remain explicit downstream work.
                trace["state"] = "host_reported_success_unverified"
            if durable_write:
                self._attempt_store.settle(
                    request_id=request_id, state=trace["state"])
            return {"state": trace["state"], "operation_id": operation_id,
                    "native_result": result}
