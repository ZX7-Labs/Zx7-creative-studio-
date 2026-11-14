"""Use existing installed ZX7 creative operations through the same brain/body ABI.

No MD files, tool scripts from the model, grant escalation or new render
implementations. The legacy trusted ToolCatalog remains the execution owner.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from .body_integration import body_catalog


# Native .blend projects and movies are usable downstream only when the
# ORIGINAL BODY durable producer committed an authentic source receipt.
# Reuse the existing DurableFilmGraph/production.sqlite3 and film tool ledger;
# never generate a fake publication or weaken require_published_source.
_DURABLE_NATIVE_PRODUCERS = frozenset({
    "body.motion_project", "body.motion_export",
})


def _invoke_existing_durable_producer(workspace, operation, inputs):
    import hashlib
    from .body_integration import run_body_project, _witness
    from .body_publication import require_published_source
    from .body_motion_project import verify_motion_bundle
    from .edit_timeline import _path_within

    if (operation not in _DURABLE_NATIVE_PRODUCERS or
            not isinstance(inputs, dict) or
            set(inputs) != ({"plan", "out"} if operation == "body.motion_project"
                           else {"bundle", "out", "fps"})):
        raise ValueError("Invalid trusted original native media producer contract")
    # Per-input stable journal project key, not an AI-specified lease, fake
    # rights label or fresh random ID. Identical retries hit the same durable
    # graph node; changed inputs cannot overwrite its previous accepted file.
    try:
        canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("Native source publication requires safe finite arguments") from exc
    digest = hashlib.sha256((operation + "\\n" + canonical).encode("utf-8")).hexdigest()
    job = {
        "project": {"creative_intent": "Host-authenticated native source " + digest},
        "shots": [{"id": "native", "purpose": "Retain genuine native source"}],
        "tool_graph": [{
            "id": "native_producer", "tool_id": operation,
            "purpose": "Physically publish native source with existing BODY lease",
            "inputs": inputs, "depends_on": [],
        }],
    }
    outcome = run_body_project(job, workspace)
    if outcome["status"] != "all_tool_results_verified":
        raise ValueError("Native source requires the original durable BODY publication")
    target = _path_within(workspace, inputs["out"], exists=True)
    actual = require_published_source(target, operation)
    witness = _witness(target)
    if witness["sha256"] != actual:
        raise ValueError("Native source differs from committed original publication")
    if operation == "body.motion_project":
        witness["native_project_observations"] = verify_motion_bundle(target)["native"]
    return {**witness, "durable_native_source_published": True}


class InstalledBodyAdapter:
    """Live connected source for CapabilityGateway, backed by actual BODY code."""

    def __init__(self, workspace, *, allowed_access=("read", "write"),
                 editor_client=None):
        allowed = frozenset(allowed_access)
        if not allowed or not allowed.issubset({"read", "write"}):
            raise ValueError("BODY bridge can only receive explicit local read/write grants")
        self._workspace = Path(workspace).resolve()
        self._editor_client = editor_client
        self._allowed_access = allowed
        self._grants = None

    def _installed(self):
        catalog = body_catalog(self._workspace, editor_client=self._editor_client)
        enabled = catalog.executable_ids(self._allowed_access)
        descriptors = {item["id"]: item for item in catalog.discover()
                       if item["id"] in enabled}
        return catalog, descriptors

    async def list_tools(self):
        _, permitted = self._installed()
        # These data come only from the actual installed local ToolCatalog,
        # never AI text, old app documentation or guessed future APIs.
        return SimpleNamespace(tools=[
            SimpleNamespace(name=ident,
                            description=detail["capability"] + ". " +
                                        detail["description"],
                            input_schema=detail["schema"])
            for ident, detail in sorted(permitted.items())],
            nextCursor=None)

    def trusted_grants(self):
        _, permitted = self._installed()
        return {name: spec["access"] for name, spec in permitted.items()}

    async def call_tool(self, name, inputs):
        catalog, permitted = self._installed()
        if name not in permitted:
            raise PermissionError("BODY operation no longer installed or granted")
        if permitted[name]["access"] not in self._allowed_access:
            raise PermissionError("BODY operation forbidden by host")
        # This is the SAME original trusted runner (including media rights,
        # output custody, durable publication and input validation).
        if name in _DURABLE_NATIVE_PRODUCERS:
            # The Brain still calls the SAME tool; the original durable BODY
            # graph owns the provenance/lease needed for reusable native art.
            result = await asyncio.to_thread(
                _invoke_existing_durable_producer, self._workspace, name, inputs)
        else:
            result = await asyncio.to_thread(
                catalog.invoke, name, inputs, allowed_access=self._allowed_access)
        return SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps(
                result, ensure_ascii=False, allow_nan=False))])


async def connect_installed_zx7_body(workspace, *, allowed_access=("read", "write"),
                                    editor_client=None,
                                    durable_write_requests=False,
                                    session_budget=None):
    """Connect the real BODY with optional crash-durable write admission.

    A host enabling this mode must assign a stable request_id to each WRITE.
    Missing identity then fails before the native operation. READs retain
    their original input interface and never consume write attempt IDs.
    """
    from .capability_gateway import CapabilityGateway
    from .capability_attempts import CapabilityAttemptStore
    from .capability_session_budget import (
        CapabilitySessionBudget, CapabilitySessionBudgetError)

    # Reject malformed host budgets before any SQLite directory is created.
    # Existing callers without this optional policy remain unchanged.
    if session_budget is not None:
        if not isinstance(session_budget, CapabilitySessionBudget):
            raise ValueError("Installed BODY requires a host-owned execution budget")
        try:
            session_budget.validate_sources(("zx7",))
        except CapabilitySessionBudgetError as exc:
            raise ValueError(str(exc)) from exc
    if type(durable_write_requests) is not bool:
        raise ValueError("Durable native admission requires an explicit boolean host policy")
    adapter = InstalledBodyAdapter(workspace, allowed_access=allowed_access,
                                   editor_client=editor_client)
    ledger = (CapabilityAttemptStore(
        Path(workspace).resolve() / ".zx7-host-private" /
        "capability-attempts.sqlite3") if durable_write_requests else None)
    # This trusted host callback re-evaluates actual installed/allowed local
    # BODY operations on future refreshes. A creative model cannot mint
    # grants, and external plugin connections remain explicitly host-authorized.
    gateway = CapabilityGateway({"zx7": (adapter, adapter.trusted_grants)},
                                attempt_store=ledger,
                                session_budget=session_budget)
    await gateway.refresh()
    return gateway
