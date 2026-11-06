"""Source-attested native project asset identity admission.

This is a Velorn native *object-existence* check, not a sequence of creative
steps. It never imports assets, invents IDs, rewrites model arguments or
authorizes native execution. An actual host-granted get_assets read is required.
The original pinned editor and its schema remain the final execution authority.
"""
from __future__ import annotations


_ASSET_PLACEMENT_TOOLS = frozenset({
    "add_asset_to_timeline", "add_assets_to_timeline",
    "replace_clip_with_asset",
})


def requires_native_asset_inventory(tool_name: str) -> bool:
    return tool_name in _ASSET_PLACEMENT_TOOLS


def assess_native_asset_selection(tool_name: str, inputs: dict,
                                  inventory: dict) -> dict | None:
    """Return bounded truthful preflight feedback, or None if admissible.

    The pinned editor's get_assets returns {count, limitApplied, assets}.
    The caller must independently authenticate the READ grant and validate
    the native receipt. An incomplete page is not proof of nonexistence.
    """
    if tool_name not in _ASSET_PLACEMENT_TOOLS:
        return None
    if not isinstance(inputs, dict) or not isinstance(inventory, dict):
        return {"validation_keyword": "native_asset_inventory_unverified",
                "no_native_dispatch": True}
    count = inventory.get("count")
    incomplete = inventory.get("limitApplied")
    assets = inventory.get("assets")
    if (type(count) is not int or count < 0 or count > 10_000_000 or
            type(incomplete) is not bool or not isinstance(assets, list) or
            len(assets) > 1000 or count < len(assets) or
            any(not isinstance(item, dict) or
                not isinstance(item.get("id"), str) or
                not item["id"] or len(item["id"]) > 512
                for item in assets) or
            (not incomplete and count != len(assets))):
        return {"validation_keyword": "native_asset_inventory_unverified",
                "no_native_dispatch": True}
    ids = {item["id"] for item in assets}
    names = [item["name"].casefold() for item in assets
             if isinstance(item.get("name"), str)]
    selected_ids = []
    selected_names = []
    for field in ("assetId", "replacementAssetId"):
        if field in inputs and isinstance(inputs[field], str) and inputs[field].strip():
            selected_ids.append(inputs[field].strip())
    for field in ("assetName", "replacementAssetName"):
        if field in inputs and isinstance(inputs[field], str) and inputs[field].strip():
            selected_names.append(inputs[field].strip().casefold())
    if tool_name == "add_assets_to_timeline":
        batch = inputs.get("assets")
        if isinstance(batch, list):
            for item in batch:
                if isinstance(item, dict):
                    if isinstance(item.get("assetId"), str) and item["assetId"].strip():
                        selected_ids.append(item["assetId"].strip())
                    if isinstance(item.get("assetName"), str) and item["assetName"].strip():
                        selected_names.append(item["assetName"].strip().casefold())
    missing_ids = sorted(set(selected_ids) - ids)
    # Explicit IDs have precedence over secondary alias/name hints in Velorn.
    unresolved_names = ([] if selected_ids else [
        name for name in selected_names
        if not any(name in actual for actual in names)])
    if (missing_ids or unresolved_names or not assets):
        keyword = ("native_asset_inventory_incomplete" if incomplete else
                   "native_asset_not_imported")
        return {
            "validation_keyword": keyword,
            "available_native_asset_count": count,
            "available_native_asset_ids_sample": sorted(ids)[:8],
            "requested_native_asset_id_count": len(selected_ids),
            "actual_project_assets_are_distinct_from_source_paths": True,
            "no_native_dispatch": True,
        }
    # If the inventory is incomplete, a model's name/latest-based selector
    # could refer to a project asset on another page. Do not claim absence.
    # Exact IDs already confirmed from this page are safe to pass to Velorn.
    if incomplete and not selected_ids:
        return {"validation_keyword": "native_asset_inventory_incomplete",
                "available_native_asset_count": count,
                "available_native_asset_ids_sample": sorted(ids)[:8],
                "no_native_dispatch": True}
    return None
