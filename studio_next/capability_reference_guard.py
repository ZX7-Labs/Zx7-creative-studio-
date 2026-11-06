"""Generic, host-attested live object-reference admission before creative writes.

This is a typed policy boundary, not a media picker and not proof of native
application commit. Each source-specific adapter must supply (1) explicit
argument paths for reference fields and (2) a fresh inventory from its real
read-only engine API. An untrusted model can choose references, but cannot
create a live identity by writing a plausible ID string.

No asset names, media, project paths or raw model input are included in any
validation error. This module is domain-neutral: tracks, nodes, shots, bones,
materials, images and 3D objects use the same host-owned contract.
"""
from __future__ import annotations

from collections.abc import Mapping
import re


class CapabilityReferenceError(ValueError):
    """Safe categorical pre-dispatch refusal, without exposing owner content."""


_KIND = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
_PART = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]{0,79}\Z")
_MAX_RULES = 64
_MAX_KINDS = 64
_MAX_IDS = 20_000
_MAX_ARRAY_ITEMS = 1_000
_MAX_REFERENCE_CHECKS = 4_096


def compile_reference_rules(rules):
    """Compile an installed adapter's fixed JSON-pointer-like ID paths.

    Supports literal object members and '*' for each element of an array,
    e.g. '/assets/*/assetId' or '/placements/*/nativeBoneId'.
    The paths come from trusted installed source, NOT from model-generated
    JSON or readme content. Rules matching absent optional fields do nothing;
    the live operation schema still enforces required fields.
    """
    if (not isinstance(rules, Mapping) or not 1 <= len(rules) <= _MAX_RULES):
        raise CapabilityReferenceError("invalid_host_reference_policy")
    compiled = []
    for path, kind in rules.items():
        if (not isinstance(path, str) or not path.startswith("/") or
                not isinstance(kind, str) or not _KIND.fullmatch(kind)):
            raise CapabilityReferenceError("invalid_host_reference_policy")
        parts = path.split("/")[1:]
        if (not 1 <= len(parts) <= 12 or
                any(part != "*" and not _PART.fullmatch(part)
                    for part in parts)):
            raise CapabilityReferenceError("invalid_host_reference_policy")
        compiled.append((tuple(parts),kind))
    return tuple(compiled)


def validate_live_references(inputs, compiled_rules, host_inventory):
    """Refuse unknown explicit native references before the first write RPC.

    Missing or truncated source inventory is UNKNOWN, never silently treated
    as a clean absence or evidence that an object exists. Re-read policies
    belong to the trusted host; this function accepts no model-sourced facts.
    """
    if not isinstance(inputs, dict):
        raise CapabilityReferenceError("invalid_native_object_arguments")
    if (not isinstance(compiled_rules, tuple) or
            not 1 <= len(compiled_rules) <= _MAX_RULES or
            not isinstance(host_inventory, Mapping) or
            len(host_inventory) > _MAX_KINDS):
        raise CapabilityReferenceError("invalid_host_reference_snapshot")
    used_kinds = {kind for _,kind in compiled_rules}
    inventories = {}
    for kind in used_kinds:
        source = host_inventory.get(kind)
        if not isinstance(source, Mapping) or set(source) != {"ids","complete"}:
            raise CapabilityReferenceError("native_identity_inventory_unavailable")
        ids = source["ids"]
        complete = source["complete"]
        if (not isinstance(ids, (list,tuple)) or
                not 0 <= len(ids) <= _MAX_IDS or
                type(complete) is not bool):
            raise CapabilityReferenceError("invalid_host_reference_snapshot")
        identities = set()
        for value in ids:
            if (not isinstance(value,str) or not 1 <= len(value) <= 240 or
                    value in identities):
                raise CapabilityReferenceError("invalid_host_reference_snapshot")
            identities.add(value)
        inventories[kind] = (identities,complete)
    checked = 0
    for path,kind in compiled_rules:
        nodes = [inputs]
        for part in path:
            following=[]
            for node in nodes:
                if part == "*":
                    if not isinstance(node, list):
                        raise CapabilityReferenceError("invalid_native_reference_shape")
                    if len(node) > _MAX_ARRAY_ITEMS:
                        raise CapabilityReferenceError("native_reference_batch_exceeds_limit")
                    following.extend(node)
                elif isinstance(node, dict):
                    if part in node:
                        following.append(node[part])
                    # Optional fields not present are validated separately by
                    # the native tool's exact input schema, never manufactured.
                else:
                    raise CapabilityReferenceError("invalid_native_reference_shape")
                if len(following) > _MAX_REFERENCE_CHECKS:
                    raise CapabilityReferenceError("native_reference_batch_exceeds_limit")
            nodes=following
        identities,complete=inventories[kind]
        for value in nodes:
            checked += 1
            if checked > _MAX_REFERENCE_CHECKS:
                raise CapabilityReferenceError("native_reference_batch_exceeds_limit")
            if not isinstance(value,str) or not value.strip():
                raise CapabilityReferenceError("invalid_native_reference_identity")
            if value not in identities:
                raise CapabilityReferenceError(
                    "native_identity_inventory_incomplete" if not complete
                    else "native_reference_not_in_live_inventory")
    return {"host_reference_checks_passed":checked,
            "native_application_state_applied_or_verified":False,
            "host_source_snapshot_used":True}
