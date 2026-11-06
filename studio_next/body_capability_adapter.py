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
from .native_editor_asset_reader import observed_editor_asset_ids


# Installed Velorn's original asset-ID parameters, not creative action plans.
# Future engines register their OWN source-specific paths using the same
# universal CapabilityGateway policy; the gateway itself is engine-neutral.
_EDITOR_ASSET_ID_PATHS = {
    "add_asset_to_timeline": {
        "/arguments/assetId": "assets",
    },
    "add_assets_to_timeline": {
        "/arguments/assetIds/*": "assets",
        "/arguments/assets/*/assetId": "assets",
        "/arguments/assets/*/id": "assets",
    },
    "replace_clip_with_asset": {
        "/arguments/assetId": "assets",
        "/arguments/replacementAssetId": "assets",
    },
}



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

    def native_asset_reference_policy(self):
        """Only host-granted native editor reads can attest model-selected IDs.

        A model does not get an additional native tool or source path by
        enabling this policy. The editor's existing get_assets grant must be
        'read', while each guarded mutation still needs its own WRITE grant.
        """
        client=self._editor_client
        if client is None or not callable(getattr(client,"call",None)):
            raise ValueError("Installed native editor reference guard needs a real editor client")
        granted=dict(client.allowed_tools)
        if ("read" not in self._allowed_access or
                granted.get("get_assets")!="read"):
            raise ValueError(
                "Live editor asset guard requires host-granted native get_assets READ")
        rules={
            "body.editor."+name: paths
            for name,paths in _EDITOR_ASSET_ID_PATHS.items()
            if granted.get(name)=="write" and "write" in self._allowed_access
        }
        if not rules:
            raise ValueError("No host-granted native asset writer to guard")

        async def observe_actual_native_assets():
            actual = await asyncio.to_thread(
                client.call,"get_assets",{"limit":1000},
                allowed_access=frozenset({"read"}))
            return observed_editor_asset_ids(actual)

        return {"reader":observe_actual_native_assets,"rules":rules}

    async def call_tool(self, name, inputs):
        catalog, permitted = self._installed()
        if name not in permitted:
            raise PermissionError("BODY operation no longer installed or granted")
        if permitted[name]["access"] not in self._allowed_access:
            raise PermissionError("BODY operation forbidden by host")
        # This is the SAME original trusted runner (including media rights,
        # output custody, durable publication and input validation).
        result = await asyncio.to_thread(
            catalog.invoke, name, inputs, allowed_access=self._allowed_access)
        return SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps(
                result, ensure_ascii=False, allow_nan=False))])


async def connect_installed_zx7_body(workspace, *, allowed_access=("read", "write"),
                                    editor_client=None,
                                    durable_write_requests=False,
                                    verify_native_editor_asset_ids=False):
    """Connect the real BODY with optional crash-durable write admission.

    A host enabling this mode must assign a stable request_id to each WRITE.
    Missing identity then fails before the native operation. READs retain
    their original input interface and never consume write attempt IDs.
    """
    from .capability_gateway import CapabilityGateway
    from .capability_attempts import CapabilityAttemptStore

    if type(durable_write_requests) is not bool:
        raise ValueError("Durable native admission requires an explicit boolean host policy")
    if type(verify_native_editor_asset_ids) is not bool:
        raise ValueError("Native asset reference guard needs an explicit boolean host policy")
    adapter = InstalledBodyAdapter(workspace, allowed_access=allowed_access,
                                   editor_client=editor_client)
    # Validate the optional identity policy's native grants before
    # constructing durable storage. Rejecting this policy must not create
    # a SQLite journal in the requested workspace.
    connection=(adapter,adapter.trusted_grants)
    if verify_native_editor_asset_ids:
        policy=adapter.native_asset_reference_policy()
        connection=(*connection,{},None,{},policy)
    ledger = (CapabilityAttemptStore(
        Path(workspace).resolve() / ".zx7-host-private" /
        "capability-attempts.sqlite3") if durable_write_requests else None)
    # This trusted host callback re-evaluates actual installed/allowed local
    # BODY operations on future refreshes. A creative model cannot mint
    # grants, and external plugin connections remain explicitly host-authorized.
    gateway = CapabilityGateway({"zx7": connection},
                                attempt_store=ledger)
    await gateway.refresh()
    return gateway
