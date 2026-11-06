"""Strict pinned-native asset identity observation for the installed editor bridge.

This source-specific adapter converts a REAL host-authorized read-only
get_assets response into the universal capability reference inventory.
It never guesses asset IDs from names, source paths or model statements.
The general identity admission and durable write logic belong to
capability_reference_guard and capability_gateway, not to this editor.
"""
from __future__ import annotations

import json


class NativeEditorAssetInventoryError(ValueError):
    """Privacy-safe source reader failure; do not echo native payload text."""


def _unique_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise NativeEditorAssetInventoryError(
                "native_asset_inventory_duplicate_field")
        result[key]=value
    return result


def _nonfinite(_value):
    raise NativeEditorAssetInventoryError("native_asset_inventory_nonfinite")


def observed_editor_asset_ids(response):
    """Turn one actual native get_assets MCP response into a trusted snapshot.

    The pinned Velorn get_assets JSON is {count, limitApplied, assets}. A
    truncated asset read can prove presence only for IDs it returned; absence
    of other IDs is UNKNOWN, never a reason to invent or replay an edit.
    """
    if not isinstance(response,dict):
        raise NativeEditorAssetInventoryError(
            "native_asset_inventory_response_unavailable")
    # MCP isError is optional on successful reads, but every supplied status
    # must be an actual boolean. A string/int status must not silently grant
    # authority to a model-selected native object ID. The internal alias is
    # checked too so contradictory adapters fail closed.
    for status_field in ("isError", "is_error"):
        if status_field in response:
            status = response[status_field]
            if type(status) is not bool:
                raise NativeEditorAssetInventoryError(
                    "native_asset_inventory_invalid_transport_status")
            if status:
                raise NativeEditorAssetInventoryError(
                    "native_asset_inventory_response_unavailable")
    content=response.get("content")
    if (not isinstance(content,list) or len(content)!=1 or
            not isinstance(content[0],dict) or
            content[0].get("type")!="text"):
        raise NativeEditorAssetInventoryError(
            "native_asset_inventory_response_unavailable")
    text=content[0].get("text")
    if (not isinstance(text,str) or
            len(text.encode("utf-8")) > 2_097_152):
        raise NativeEditorAssetInventoryError(
            "native_asset_inventory_exceeds_budget")
    try:
        data=json.loads(text,object_pairs_hook=_unique_pairs,
                        parse_constant=_nonfinite)
    except (ValueError,TypeError,RecursionError) as exc:
        raise NativeEditorAssetInventoryError(
            "native_asset_inventory_invalid_json") from None
    if not isinstance(data,dict):
        raise NativeEditorAssetInventoryError(
            "native_asset_inventory_invalid_shape")
    total=data.get("count")
    limited=data.get("limitApplied")
    assets=data.get("assets")
    if (type(total) is not int or total<0 or
            type(limited) is not bool or not isinstance(assets,list) or
            len(assets)>1000 or len(assets)>total or
            (not limited and len(assets)!=total) or
            (limited and (len(assets)==0 or len(assets)>=total))):
        raise NativeEditorAssetInventoryError(
            "native_asset_inventory_inconsistent_counts")
    ids=[]
    seen=set()
    for asset in assets:
        if not isinstance(asset,dict):
            raise NativeEditorAssetInventoryError(
                "native_asset_inventory_invalid_record")
        source_id=asset.get("id")
        if (not isinstance(source_id,str) or
                not 1<=len(source_id)<=240 or
                source_id in seen):
            raise NativeEditorAssetInventoryError(
                "native_asset_inventory_duplicate_or_missing_id")
        seen.add(source_id)
        ids.append(source_id)
    # No names, source directories, media rights, prompt text or content are
    # returned to the host admission policy or saved in its private journal.
    return {"assets":{"ids":ids,"complete":not limited}}
