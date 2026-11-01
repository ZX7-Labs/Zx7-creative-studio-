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

    def collect_selector(entry):
        # The pinned native resolver checks assetId before assetName for EACH
        # entry, not once across the entire batch. A valid first entry must
        # not conceal an invalid name/path on a second entry.
        if not isinstance(entry, dict):
            return
        exact_id = entry.get("assetId")
        if isinstance(exact_id, str) and exact_id.strip():
            selected_ids.append(exact_id.strip())
            return
        name = entry.get("assetName")
        if isinstance(name, str) and name.strip():
            selected_names.append(name.strip().casefold())

    if tool_name == "replace_clip_with_asset":
        collect_selector({"assetId": inputs.get("replacementAssetId"),
                          "assetName": inputs.get("replacementAssetName")})
    else:
        collect_selector(inputs)
    if tool_name == "add_assets_to_timeline":
        if any(field in inputs and not isinstance(inputs[field], list)
               for field in ("assets", "assetIds", "assetNames")):
            return {"validation_keyword": "native_asset_inventory_unverified",
                    "no_native_dispatch": True}
        # Exact pinned Velorn resolveAssetsForTimelineBatchPlacement
        # collects ALL THREE native input forms: assets, assetIds, assetNames.
        # Ignoring assetIds let real Qwen3.5-4B run #41258639051 pass two
        # filesystem .mp4 paths as native IDs and hit a terminal write error,
        # despite an actual imported asset being in the project.
        for item in inputs.get("assets", []):
            if isinstance(item, str) and item.strip():
                selected_ids.append(item.strip())
            else:
                collect_selector(item)
        for asset_id in inputs.get("assetIds", []):
            if isinstance(asset_id, str) and asset_id.strip():
                selected_ids.append(asset_id.strip())
        for asset_name in inputs.get("assetNames", []):
            if isinstance(asset_name, str) and asset_name.strip():
                selected_names.append(asset_name.strip().casefold())
    missing_ids = sorted(set(selected_ids) - ids)
    # IDs take precedence within an entry, but separate batch selectors
    # are additive. Every independently nominated name must also resolve.
    unresolved_names = [
        name for name in selected_names
        if not any(name in actual for actual in names)]
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
