"""Attest the exact local upstream Electron MCP preview contract.

A pinned renderer handler does not establish how the externally callable
MCP layer handles previewOnly. The verified Electron MCP entrypoint is the
authority. This helper never installs models, accesses network endpoints or
grants a tool not already authorized by the host.
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
# Pinned electron/mcpServer.js addAsset(s)ToTimeline returns a read-only
# preview by default, before performAction, with a model-selectable apply call.
_PINNED_ASSET_PLACEMENT_PREVIEWS = (
    "add_asset_to_timeline", "add_assets_to_timeline",
)


def pinned_electron_marker_previews(source: Path, grants: dict) -> tuple[str, ...]:
    """Admit the source-verified flat preview parser for the real pinned MCP.

    Fail closed when Git source identity or the entrypoint's worktree
    integrity cannot be independently verified. Private cloud credentials
    never enter these local Git subprocess environments.
    """
    if (not isinstance(source, Path) or not isinstance(grants, dict)
            or not all(isinstance(name, str) and access in ("read", "write")
                       for name, access in grants.items())):
        raise ValueError("Pinned preview attestation needs trusted native source/grants")
    safe_env = dict(os.environ)
    safe_env.pop("NVIDIA_API_KEY", None)
    try:
        resolved = str(source.resolve(strict=True))
        revision = subprocess.run(
            ["git", "-C", resolved, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, env=safe_env)
        if (revision.returncode != 0 or
                revision.stdout.strip() != PINNED_VELORN_MCP_REVISION):
            return ()
        clean = subprocess.run(
            ["git", "-C", resolved, "diff", "--quiet", "HEAD", "--",
             "electron/mcpServer.js"],
            capture_output=True, text=True, timeout=5, env=safe_env)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return ()
    if clean.returncode != 0:
        return ()
    return tuple(name for name in _PINNED_MARKER_PREVIEWS
                 if grants.get(name) == "write")


def pinned_electron_asset_placement_previews(
        source: Path, grants: dict) -> tuple[str, ...]:
    """Source-verified default-read-only preview of native asset placement.

    Reuse exactly the same attested clean Electron MCP source gate as marker
    previews, without giving the model an ungranted creative capability.
    """
    allowed = {**grants}
    # Reuse the authoritative source/clean-tree check; adding only grant keys
    # for installed marker operations is not a native tool authorization.
    attested = pinned_electron_marker_previews(
        source, {**allowed, "add_timeline_markers": "write"})
    if "add_timeline_markers" not in attested:
        return ()
    return tuple(name for name in _PINNED_ASSET_PLACEMENT_PREVIEWS
                 if allowed.get(name) == "write")
