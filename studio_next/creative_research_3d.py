"""Free CC0 material, HDRI and 3D research from official public source APIs.

Only metadata search. Actual source bytes, rights and license proofs must be
attested independently before any scene/film can use an asset.
"""
from __future__ import annotations

import re
from .creative_research import (
    _check, _plain, _request_params, CreativeResearchError,
)


def poly_haven_assets(fetch_json, query, limit, *, type_name):
    """Poly Haven official free API: ranked semantic+keyword CC0 assets."""
    if type_name not in ("models", "textures", "hdris"):
        raise CreativeResearchError("Unsupported Poly Haven asset type")
    query = _check(query, limit)
    # Official public API /search accepts q, type and limit; the search
    # schema returns ranked slugs in a results array. Never request future
    # unpublished assets or issue paid-tier calls.
    url = _request_params("https://api.polyhaven.com/search", {
        "q": query.lower()[:100], "t": type_name,
        "limit": limit})
    response = fetch_json(url)
    items = response.get("results") if isinstance(response, dict) else None
    if not isinstance(items, list):
        raise CreativeResearchError("Poly Haven official search response malformed")
    results = []
    for entry in items[:limit]:
        slug = entry.get("slug") if isinstance(entry, dict) else None
        if not isinstance(slug, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,90}", slug):
            continue
        results.append({
            "title": _plain(slug.replace("_", " ").title()),
            "source_page": "https://polyhaven.com/a/" + slug,
            "declared_license": "CC0",
            "license_evidence_source": "polyhaven_official_sitewide_cc0_policy",
            "rights_status": "candidate_unverified",
            "media_type": "3d" if type_name == "models" else "image",
            "asset_kind": type_name,
            # Live API reuse condition, distinct from CC0 asset usage rights.
            "provider_credit": "Powered by Poly Haven",
        })
    return results


def ambientcg_assets(fetch_json, query, limit, *, type_name):
    """No-key ambientCG v3 public catalog; never Patreon early-access."""
    if type_name not in ("material", "hdri", "3d-model"):
        raise CreativeResearchError("Unsupported ambientCG asset type")
    query = _check(query, limit)
    url = _request_params("https://ambientcg.com/api/v3/assets", {
        "q": query, "type": type_name, "limit": limit,
        "include": "title"})
    response = fetch_json(url)
    items = response.get("assets") if isinstance(response, dict) else None
    if not isinstance(items, list):
        raise CreativeResearchError("ambientCG CC0 asset metadata malformed")
    out = []
    for entry in items[:limit]:
        if not isinstance(entry, dict):
            continue
        ident = entry.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", ident):
            continue
        out.append({
            "title": _plain(entry.get("title")) or ident,
            "source_page": "https://ambientcg.com/a/" + ident,
            "declared_license": "CC0",
            "license_evidence_source": "ambientcg_official_sitewide_cc0_policy",
            "rights_status": "candidate_unverified",
            "media_type": "3d" if type_name == "3d-model" else "image",
            "asset_kind": type_name,
        })
    return out
