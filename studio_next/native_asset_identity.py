"""Verify native media identity using ACTUAL read-only editor asset inventory.

Never infer media identity from a file basename, tool name, model utterance,
or an acknowledged project creation. This gate does not import media or
select a shot. It only distinguishes grounded native asset references from
invented identifiers before a potentially stateful edit.
"""
from __future__ import annotations

import json
import math


class NativeAssetEvidenceError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise NativeAssetEvidenceError("Duplicate native media inventory field")
        result[key] = value
    return result


def inventory_from_native_text(texts):
    if not isinstance(texts, list) or len(texts) != 1 or not isinstance(texts[0], str):
        raise NativeAssetEvidenceError("One real native asset inventory response required")
    try:
        record = json.loads(texts[0], object_pairs_hook=_unique,
                            parse_constant=lambda x: (_ for _ in ()).throw(
                                NativeAssetEvidenceError("Nonfinite native inventory")))
    except (ValueError, TypeError, RecursionError) as exc:
        raise NativeAssetEvidenceError("Invalid native media inventory") from exc
    if not isinstance(record, dict):
        raise NativeAssetEvidenceError("Native media inventory must be an object")
    rows = record.get("assets")
    total = record.get("totalAssetCount")
    returned = record.get("returnedAssetCount")
    if (not isinstance(rows, list) or type(total) is not int or
            type(returned) is not int or total < 0 or returned < 0 or
            returned != len(rows) or returned > total or returned > 1000 or
            (total > 0 and returned == 0)):
        raise NativeAssetEvidenceError("Inconsistent native asset count")
    identities, names = [], []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise NativeAssetEvidenceError("Invalid native asset record")
        identifier = row.get("id")
        name = row.get("name")
        if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 240
                or identifier in seen or not isinstance(name, str)
                or len(name) > 1000):
            raise NativeAssetEvidenceError("Native asset identity missing or duplicated")
        seen.add(identifier)
        identities.append(identifier)
        names.append(name)
    return {"ids": identities, "names": names, "total": total,
            "complete": returned == total, "returned": returned}


def check_native_asset_reference(inputs, inventory):
    """Return structured source error or None; no native edit is executed.

    The Velorn placement API permits ID/name/latest selection. At least one
    known real asset must be imported; any explicitly supplied ID must match
    the actual inventory. A partial response cannot prove an ID is absent,
    so reject with incomplete-inventory rather than inventing certainty.
    """
    if not isinstance(inputs, dict) or not isinstance(inventory, dict):
        raise NativeAssetEvidenceError("Native source validation needs typed inputs")
    if inventory["total"] == 0:
        return "native_project_has_no_imported_assets"
    identity = inputs.get("assetId")
    if identity is not None:
        if not isinstance(identity, str) or not identity.strip():
            return "invalid_native_asset_id"
        if identity not in inventory["ids"]:
            return ("native_asset_inventory_incomplete" if not inventory["complete"]
                    else "asset_id_not_in_native_inventory")
    name = inputs.get("assetName")
    if name is not None and not isinstance(name, str):
        return "invalid_native_asset_name"
    if name is not None and name and not any(name.casefold() in x.casefold()
                                              for x in inventory["names"]):
        return ("native_asset_inventory_incomplete" if not inventory["complete"]
                else "asset_name_not_in_native_inventory")
    return None
