"""Attest the exact local upstream Electron MCP preview contract.

A pinned renderer handler does not establish how the externally callable
MCP layer handles previewOnly. This module admits no ungranted native tool
and never installs models, accesses the network or authorizes a mutation.
"""
from __future__ import annotations

import json
from pathlib import Path
import os
import subprocess

_SOURCE_LOCK = json.loads((Path(__file__).parent / "editor_runtime/source-lock.json").read_text(encoding="utf-8"))
PINNED_VELORN_MCP_REVISION = _SOURCE_LOCK["upstream_revision"]
PINNED_VELORN_DESKTOP_REVISION = _SOURCE_LOCK["desktop_revision"]
# A separately reviewed and reproducibly built collaboration source revision.
PINNED_VELORN_COLLAB_REVISION = _SOURCE_LOCK.get("collab_revision")
PINNED_VELORN_SCENE_REVISION = _SOURCE_LOCK.get("collab_scene_revision")
TRUSTED_VELORN_REVISIONS = frozenset(
    value for value in (
        PINNED_VELORN_MCP_REVISION, PINNED_VELORN_DESKTOP_REVISION,
        PINNED_VELORN_COLLAB_REVISION, PINNED_VELORN_SCENE_REVISION,
    ) if isinstance(value, str) and value)

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



def source_verified_preview_intent(tool, inputs, attested_tools) -> bool:
    """Recognize only the pinned MCP no-renderer-write request branches.

    The caller supplies independently source-attested, host-granted tools.
    Marker methods require an explicit true; placement and clip-edit methods
    default to preview. No tool name, text receipt or truthy nonboolean can
    establish this contract on its own.
    """
    if (not isinstance(tool, str) or not isinstance(inputs, dict) or
            not isinstance(attested_tools, (tuple, list, set, frozenset)) or
            any(not isinstance(name, str) or not name for name in attested_tools) or
            len(set(attested_tools)) != len(attested_tools) or tool not in attested_tools):
        return False
    if tool in _PINNED_MARKER_PREVIEWS:
        return inputs.get("previewOnly") is True
    if tool in (*_PINNED_ASSET_PLACEMENT_PREVIEWS, *_PINNED_CLIP_EDIT_PREVIEWS):
        return inputs.get("previewOnly", True) is True
    return False


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
            ["git", "-C", resolved, "rev-parse", "--show-toplevel", "HEAD"],
            capture_output=True, text=True, timeout=5, env=safe_env)
        identity = revision.stdout.splitlines()
        if (revision.returncode != 0 or len(identity) != 2 or
                identity[0] != resolved or identity[1] not in TRUSTED_VELORN_REVISIONS):
            return False
        clean = subprocess.run(
            ["git", "-C", resolved, "diff", "--quiet", "HEAD", "--",
             "electron/mcpServer.js"],
            capture_output=True, text=True, timeout=5, env=safe_env)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return False
    return clean.returncode == 0


def _source_matches_pinned_native_collaboration(source: Path) -> bool:
    """Exact reviewed overlay and unmodified renderer/API/bridge source.

    Never infer atomic GUI/AI protection from the original upstream commit,
    the presence of similarly named methods, or a user supplied revision.
    """
    if (not PINNED_VELORN_COLLAB_REVISION or not isinstance(source, Path) or
            not _source_matches_pinned_electron_mcp(source)):
        return False
    safe_env = dict(os.environ)
    safe_env.pop("NVIDIA_API_KEY", None)
    try:
        actual = subprocess.run(
            ["git", "-C", str(source.resolve(strict=True)), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, env=safe_env)
        if (actual.returncode != 0 or
                actual.stdout.strip() not in {
                    PINNED_VELORN_COLLAB_REVISION,
                    PINNED_VELORN_SCENE_REVISION,
                }):
            return False
        # A clean PINNED HEAD is the source contract, not just three
        # reviewed entry-point files. A dirty tracked timeline/store module
        # can suppress GUI revision emission while leaving those files intact.
        # Ignore untracked build outputs; reject any staged or unstaged
        # modification to tracked source. This is checkout attestation, not
        # a guarantee against post-check mutation by another local process.
        clean = subprocess.run(
            ["git", "-C", str(source.resolve(strict=True)), "diff", "--quiet",
             "HEAD", "--"],
            capture_output=True, text=True, timeout=5, env=safe_env)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return False
    return clean.returncode == 0


def _source_matches_pinned_native_scene(source: Path) -> bool:
    """Only the exact reviewed child overlay has shape+keyframe CAS semantics."""
    if (not PINNED_VELORN_SCENE_REVISION or
            not _source_matches_pinned_native_collaboration(source)):
        return False
    safe_env = dict(os.environ)
    safe_env.pop("NVIDIA_API_KEY", None)
    try:
        actual = subprocess.run(
            ["git", "-C", str(source.resolve(strict=True)), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, env=safe_env)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return False
    return (actual.returncode == 0 and
            actual.stdout.strip() == PINNED_VELORN_SCENE_REVISION)


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
