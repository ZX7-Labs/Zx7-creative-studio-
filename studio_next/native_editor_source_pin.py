"""Attest the exact local upstream Electron MCP preview contract.

A pinned renderer handler does not establish how the externally callable
MCP layer handles previewOnly. This module admits no ungranted native tool
and never installs models, accesses the network or authorizes a mutation.
"""
from __future__ import annotations

from pathlib import Path
import os
import subprocess

PINNED_VELORN_MCP_REVISION = "b3c02adbd5c0779feb8abf34978299e9502cc0e7"
_PINNED_MARKER_PREVIEWS = (
    "add_timeline_markers", "remove_timeline_markers",
    "set_timeline_marker_properties",
)
_PINNED_ASSET_PLACEMENT_PREVIEWS = (
    "add_asset_to_timeline", "add_assets_to_timeline",
)
_PINNED_CLIP_EDIT_PREVIEWS = (
    "move_clips", "trim_clips", "delete_clips",
)


def _verified_editor_grants(grants: dict) -> bool:
    return (isinstance(grants, dict) and
            all(isinstance(name, str) and name and
                access in ("read", "write")
                for name, access in grants.items()))


def _source_matches_pinned_electron_mcp(source: Path) -> bool:
    """Verify real Git HEAD and clean externally callable Electron MCP source.

    Never confuse this with a complete application or supply-chain audit.
    """
    if not isinstance(source, Path):
        return False
    safe_env = dict(os.environ)
    safe_env.pop("NVIDIA_API_KEY", None)
    try:
        resolved = str(source.resolve(strict=True))
        revision = subprocess.run(
            ["git", "-C", resolved, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, env=safe_env)
        if (revision.returncode != 0 or
                revision.stdout.strip() != PINNED_VELORN_MCP_REVISION):
            return False
        clean = subprocess.run(
            ["git", "-C", resolved, "diff", "--quiet", "HEAD", "--",
             "electron/mcpServer.js"],
            capture_output=True, text=True, timeout=5, env=safe_env)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return False
    return clean.returncode == 0


def pinned_electron_marker_previews(source: Path, grants: dict) -> tuple[str, ...]:
    """Allow exactly source-verified *flat marker* no-write receipts."""
    if not _verified_editor_grants(grants):
        raise ValueError("Pinned preview attestation needs trusted native source/grants")
    if not isinstance(source, Path):
        raise ValueError("Pinned preview attestation requires a source Path")
    if not _source_matches_pinned_electron_mcp(source):
        return ()
    return tuple(name for name in _PINNED_MARKER_PREVIEWS
                 if grants.get(name) == "write")


def pinned_electron_asset_placement_previews(
        source: Path, grants: dict) -> tuple[str, ...]:
    """Allow exactly source-verified *flat asset-placement* preview receipts.

    These Electron methods return previewOnly:true by default, without
    calling a mutating renderer operation; the MODEL chooses whether to
    submit the explicitly suggested previewOnly:false apply call.
    """
    if not _verified_editor_grants(grants):
        raise ValueError("Pinned preview attestation needs trusted native source/grants")
    if not isinstance(source, Path):
        raise ValueError("Pinned preview attestation requires a source Path")
    if not _source_matches_pinned_electron_mcp(source):
        return ()
    return tuple(name for name in _PINNED_ASSET_PLACEMENT_PREVIEWS
                 if grants.get(name) == "write")


def pinned_electron_timeline_frame_previews(
        source: Path, grants: dict) -> tuple[str, ...]:
    """Attest source-native JPEG preview reads, NEVER decoded export proof.

    Pinned Electron MCP inspectTimelineFrame returns native timeline frame
    metadata plus image/jpeg data. Its non-export image has no verified
    export SHA256 and must not be mistaken for a physically decoded MP4.
    Current actual editor source and both read-only grants are prerequisites.
    """
    if not _verified_editor_grants(grants):
        raise ValueError("Pinned timeline preview needs trusted native source/grants")
    if not isinstance(source, Path):
        raise ValueError("Pinned timeline preview requires a source Path")
    if (grants.get("inspect_timeline_frame") != "read" or
            grants.get("get_project") != "read" or
            not _source_matches_pinned_electron_mcp(source)):
        return ()
    return ("inspect_timeline_frame",)


def pinned_electron_clip_edit_previews(
        source: Path, grants: dict) -> tuple[str, ...]:
    """Attest pinned native default read-only move/trim/delete plan receipts.

    The exact Electron MCP intercepts previewOnly missing/true before
    renderer performAction. A model must independently select
    previewOnly:false to commit; no host-generated move is authorized.
    """
    if not _verified_editor_grants(grants):
        raise ValueError("Pinned clip-preview source requires trusted grants")
    if not isinstance(source, Path):
        raise ValueError("Pinned clip-preview source requires a Path")
    if not _source_matches_pinned_electron_mcp(source):
        return ()
    return tuple(name for name in _PINNED_CLIP_EDIT_PREVIEWS
                 if grants.get(name) == "write")
