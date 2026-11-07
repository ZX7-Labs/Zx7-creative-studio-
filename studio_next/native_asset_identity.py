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
    # Pinned Velorn b3c02ad get_assets returns the EXACT transport keys
    # {count, limitApplied, assets}, not fabricated totalAssetCount /
    # returnedAssetCount. The original CPU camera trial proved that
    # expecting those imaginary keys hid actual imported sources.
    rows = record.get("assets")
    total = record.get("count")
    limited = record.get("limitApplied")
    returned = len(rows) if isinstance(rows, list) else -1
    if (not isinstance(rows, list) or type(total) is not int or
            type(limited) is not bool or total < 0 or returned < 0 or
            returned > total or returned > 1000 or
            (limited and (total <= returned or returned == 0)) or
            (not limited and returned != total)):
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
            "complete": not limited, "returned": returned}


def check_native_asset_reference(inputs, inventory):
    """Validate every EXPLICIT native asset reference against a fresh READ.

    Source references can live in a single tool input, batch assetIds /
    assetNames, or entries under a batch assets list. Checking only a top-level
    assetId allowed invented nested IDs through to stateful native operations.
    No media/source path or model-chosen name is ever placed into an error code.

    This does NOT infer an asset from a filename, pick a creative shot or
    claim that the native timeline changed. The host independently reads
    get_assets before invoking any native placement with the prerequisite.
    """
    if not isinstance(inputs, dict) or not isinstance(inventory, dict):
        raise NativeAssetEvidenceError("Native source validation needs typed inputs")
    if inventory["total"] == 0:
        return "native_project_has_no_imported_assets"

    def known_id(value):
        if not isinstance(value, str) or not value.strip():
            return "invalid_native_asset_id"
        if value not in inventory["ids"]:
            return ("native_asset_inventory_incomplete" if not inventory["complete"]
                    else "asset_id_not_in_native_inventory")
        return None

    def known_name(value):
        if not isinstance(value, str) or not value.strip():
            return "invalid_native_asset_name"
        if not any(value.casefold() in name.casefold()
                   for name in inventory["names"]):
            return ("native_asset_inventory_incomplete" if not inventory["complete"]
                    else "asset_name_not_in_native_inventory")
        return None

    # Preserve the upstream source-selection contract: a caller may request
    # the native editor's current "latest" choice without naming an asset.
    # The host does not manufacture an ID for that choice.
    if "assetId" in inputs and inputs["assetId"] is not None:
        issue = known_id(inputs["assetId"])
        if issue:
            return issue
    if "assetName" in inputs and inputs["assetName"] is not None:
        issue = known_name(inputs["assetName"])
        if issue:
            return issue
    for field, validator in (("assetIds", known_id),
                             ("assetNames", known_name)):
        if field not in inputs:
            continue
        values = inputs[field]
        if (not isinstance(values, list) or not values or
                len(values) > 1000):
            return ("invalid_native_asset_id" if field == "assetIds"
                    else "invalid_native_asset_name")
        for value in values:
            issue = validator(value)
            if issue:
                return issue

    if "assets" in inputs:
        entries = inputs["assets"]
        if (not isinstance(entries, list) or not entries or
                len(entries) > 1000):
            return "invalid_native_asset_batch"
        for entry in entries:
            if isinstance(entry, str):
                issue = known_id(entry)
            elif isinstance(entry, dict):
                if "assetId" in entry:
                    issue = known_id(entry["assetId"])
                elif "id" in entry:
                    issue = known_id(entry["id"])
                elif "assetName" in entry:
                    issue = known_name(entry["assetName"])
                elif "name" in entry:
                    issue = known_name(entry["name"])
                else:
                    # An opaque object is not an editor asset. An explicit
                    # batch entry needs a source selector, not guessed media.
                    return "native_asset_batch_entry_without_identity"
            else:
                return "invalid_native_asset_batch"
            if issue:
                return issue
    return None
