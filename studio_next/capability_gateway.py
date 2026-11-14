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
from .capability_reference_guard import (
    CapabilityReferenceError, compile_reference_rules, validate_live_references)
from .capability_session_budget import (
    CapabilitySessionBudget, CapabilitySessionBudgetError)


_MODEL_NATIVE_OBSERVATION_UNCHECKED = object()
# Only pinned, synchronously committing editorial actions. An arbitrary
# WRITE does not acquire native revision semantics by its name.
_SOURCE_NATIVE_EDITORIAL_COMMIT_TOOLS = frozenset((
    "move_clips", "trim_clips", "delete_clips",
    "add_asset_to_timeline", "add_assets_to_timeline",
    "set_clip_audio", "set_clip_speed", "update_track",
    "add_transition", "set_clip_style", "split_clip",
))


class CapabilityExecutionError(ValueError):
    """Rejected BEFORE any native dispatch; no guessed operation is allowed."""


_SAFE_NATIVE_IDENTITY_READ_ERRORS = frozenset({
    "native_identity_read_failed",
    "native_identity_read_malformed",
    "native_identity_read_oversize",
    "native_identity_read_incomplete",
    "native_identity_project_unavailable",
    "native_identity_project_changed_during_read",
    "native_identity_source_counts_changed",
    "native_identity_live_revision_unavailable",
    "native_identity_model_observation_required",
    "native_identity_model_observation_stale",
})


class NativeReferencePreDispatchError(CapabilityExecutionError):
    """Host-only, provably no-dispatch denial with categorical safe feedback."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _source_native_commit_intent(tool, inputs):
    """Only source-attested *commits* need a native writer CAS token.

    Reader-like previews remain public-schema clean. In the pinned editor
    keyframe previews are the default; text and shape previews require an
    explicit true. Never infer that a preview is a write from the tool name.
    """
    if tool == "set_clip_keyframes" or tool in _SOURCE_NATIVE_EDITORIAL_COMMIT_TOOLS:
        return inputs.get("previewOnly") is False
    if tool in ("update_text_clip", "update_shape_clip"):
        return inputs.get("previewOnly") is not True
    return False


def _confirmed_native_revision_conflict(result, code):
    """Only a source-pinned edit can attest this exact no-write renderer code."""
    blocks = result.get("content") if isinstance(result, dict) else getattr(result, "content", None)
    if not isinstance(blocks, (list, tuple)) or len(blocks) != 1:
        return False
    block = blocks[0]
    kind = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
    value = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
    return kind == "text" and isinstance(value, str) and value == code


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
                             [trusted fact reader], [possible effects],
                             [host-owned reference reader/policies]).
    Reference checks inspect actual connected source state before model-selected
    writes. This does not substitute for native atomic document revisions.
    The fact reader accepts no model-provided data and returns a mapping of
    host-attested boolean facts. Missing facts deny prerequisite admission.
    """

    def __init__(self, bindings: Mapping, *, attempt_store=None,
                 session_budget=None):
        if session_budget is not None and not isinstance(
                session_budget, CapabilitySessionBudget):
            raise CapabilityExecutionError(
                "Only a host-owned capability session budget is permitted")
        self._session_budget = session_budget
        if attempt_store is not None and not isinstance(attempt_store, CapabilityAttemptStore):
            raise CapabilityExecutionError("Only the trusted durable capability ledger is permitted")
        self._attempt_store = attempt_store
        if not isinstance(bindings, Mapping) or not 1 <= len(bindings) <= 256:
            raise CapabilityExecutionError("Connected host-bound source inventory is required")
        self._bindings = {}
        self._locks = {}
        for namespace, entry in bindings.items():
            if not isinstance(entry, tuple) or len(entry) not in (2, 3, 4, 5, 6):
                raise CapabilityExecutionError("Source requires a real connection and grants")
            session, grants = entry[:2]
            requires = entry[2] if len(entry) >= 3 else {}
            facts = entry[3] if len(entry) >= 4 else None
            possible_effects = entry[4] if len(entry) >= 5 else {}
            identity = entry[5] if len(entry) == 6 else None
            if identity is not None:
                if (not isinstance(identity, Mapping) or
                        set(identity) not in (
                            {"reader", "rules"}, {"reader", "rules", "fence"}) or
                        not callable(identity["reader"]) or
                        not isinstance(identity["rules"], Mapping) or
                        not 1 <= len(identity["rules"]) <= 256):
                    raise CapabilityExecutionError("Invalid native identity policy")
                compiled = {}
                try:
                    for tool_name, rules in identity["rules"].items():
                        if (not isinstance(tool_name, str) or
                                len(tool_name) > 160 or
                                not isinstance(grants, Mapping) or
                                grants.get(tool_name) != "write"):
                            raise CapabilityReferenceError(
                                "invalid_host_reference_policy")
                        compiled[tool_name] = compile_reference_rules(rules)
                except CapabilityReferenceError as exc:
                    raise CapabilityExecutionError(str(exc)) from exc
                fences = identity.get("fence", {})
                if not isinstance(fences, Mapping) or len(fences) > 64:
                    raise CapabilityExecutionError("Invalid native commit fence policy")
                checked_fences = {}
                for tool_name, policy in fences.items():
                    if (tool_name not in compiled or
                            not isinstance(policy, Mapping) or
                            set(policy) != {"inventory_key", "argument_key", "rejected_code"} or
                            policy.get("inventory_key") != "__zx7_live_revision" or
                            policy.get("argument_key") != "__zx7ExpectedRevision" or
                            policy.get("rejected_code") != "ZX7_STALE_NATIVE_REVISION"):
                        raise CapabilityExecutionError("Unsupported host native revision fence")
                    checked_fences[tool_name] = dict(policy)
                identity = {"reader": identity["reader"], "rules": compiled,
                            "fence": checked_fences}
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
                                         copy.deepcopy(possible_effects), identity)
            self._locks[namespace] = asyncio.Lock()
        if self._session_budget is not None:
            try:
                self._session_budget.validate_sources(self._bindings)
            except CapabilitySessionBudgetError as exc:
                raise CapabilityExecutionError(str(exc)) from exc
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
        _, _, _, reader, _, _ = self._bindings[namespace]
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

    def host_budget_evidence(self):
        """Host-only call admission facts, not LLM token or price accounting."""
        if self._session_budget is None:
            return None
        return self._session_budget.snapshot()

    def unverified_native_writes(self, *, limit=32, cursor=None):
        """Trusted host recovery view, never a model-executable capability.

        This does not authorize replay, grant new native tools, or attest any
        application commit. It exposes only bounded host-generated identities
        already recorded in the durable attempt journal.
        """
        if self._attempt_store is None:
            raise CapabilityExecutionError(
                "Crash-recovery inspection requires the installed durable journal")
        return self._attempt_store.unverified_attempts(
            limit=limit, cursor=cursor)

    async def invoke(self, operation_id, *, revision, inputs, request_id=None,
                     model_observed_revision=_MODEL_NATIVE_OBSERVATION_UNCHECKED):
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
            session, _, conditions, fact_reader, effects, identity = self._bindings[namespace]
            # A plainly exhausted host budget must not spend more native
            # tools/list RPCs discovering an action it can never dispatch.
            # The later atomic reservation still handles cross-source races.
            if self._session_budget is not None:
                try:
                    self._session_budget.check_available(
                        source=namespace, access=record["access"])
                except CapabilitySessionBudgetError as exc:
                    raise CapabilityExecutionError(str(exc)) from exc
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
            # Model arguments are validated and fingerprinted independently of
            # the host-owned source revision appended only for native dispatch.
            dispatch_inputs = copy.deepcopy(inputs)
            native_fence = None
            # Explicit source IDs must still exist in the connected engine.
            # The Brain chooses the object/edit; host policy only checks a
            # source-native identity, never substitutes an artistic action.
            if record["access"] == "write" and identity is not None:
                rules = identity["rules"].get(name)
                if rules is not None:
                    try:
                        inventory = identity["reader"]()
                        if inspect.isawaitable(inventory):
                            inventory = await inventory
                        validate_live_references(inputs, rules, inventory)
                        native_fence = (
                            identity["fence"].get(name)
                            if _source_native_commit_intent(name, inputs)
                            else None)
                        if native_fence is not None:
                            source_revision = inventory.get(native_fence["inventory_key"])
                            hidden_argument = native_fence["argument_key"]
                            if (not isinstance(source_revision, str) or
                                    not 38 <= len(source_revision) <= 80 or
                                    hidden_argument in inputs):
                                raise NativeReferencePreDispatchError(
                                    "native_identity_live_revision_unavailable")
                            # A fresh host inventory alone must not silently
                            # bless a model decision conceived BEFORE a human
                            # changed the project. Compare the last native
                            # project revision the Brain actually observed,
                            # supplied only by the trusted session wrapper.
                            if model_observed_revision is not _MODEL_NATIVE_OBSERVATION_UNCHECKED:
                                if (type(model_observed_revision) is not str or
                                        not 38 <= len(model_observed_revision) <= 80):
                                    raise NativeReferencePreDispatchError(
                                        "native_identity_model_observation_required")
                                if model_observed_revision != source_revision:
                                    raise NativeReferencePreDispatchError(
                                        "native_identity_model_observation_stale")
                            dispatch_inputs[hidden_argument] = source_revision
                    except NativeReferencePreDispatchError:
                        raise
                    except CapabilityReferenceError as exc:
                        raise NativeReferencePreDispatchError(str(exc)) from exc
                    except CapabilitySessionBudgetError:
                        # Some source reads may have run, but NO native write
                        # was sent or durably admitted. Report this truth to
                        # the model, without misclassifying a prior write.
                        raise NativeReferencePreDispatchError(
                            "native_identity_read_budget_exhausted") from None
                    except ValueError as exc:
                        # Typed host-reader categories are public-safe only
                        # when they appear in this fixed allowlist. Unknown
                        # exception messages might contain private asset paths.
                        category = str(exc)
                        if category in _SAFE_NATIVE_IDENTITY_READ_ERRORS:
                            raise NativeReferencePreDispatchError(category) from None
                        raise NativeReferencePreDispatchError(
                            "native_identity_inventory_unavailable") from None
                    except Exception:
                        # Native reader errors may contain private owner paths.
                        # No native write was submitted or durably admitted.
                        raise NativeReferencePreDispatchError(
                            "native_identity_inventory_unavailable") from None
            # A single trusted budget spans all connected creative engines.
            # Reserve only after live grant/schema/machine preflight, but
            # before a durable intent or any native read/write RPC. A failed
            # remote attempt conservatively consumes the reserved slot.
            if self._session_budget is not None:
                try:
                    self._session_budget.reserve(
                        source=namespace, access=record["access"])
                except CapabilitySessionBudgetError as exc:
                    raise CapabilityExecutionError(str(exc)) from exc
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
                result = await session.call_tool(name, dispatch_inputs)
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
                # A *source-pinned* synchronous renderer rejection is known
                # to precede any native mutation. Without the strict exact
                # receipt, an ordinary failed write remains uncertain.
                if (native_fence is not None and
                        _confirmed_native_revision_conflict(
                            result, native_fence["rejected_code"])):
                    trace["state"] = "native_conflict_rejected_no_write"
                else:
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
