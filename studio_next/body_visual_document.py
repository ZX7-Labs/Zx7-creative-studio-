"""Secure, versioned authored source for the EXISTING native visual graph engine.

This is not a new renderer, universal creative format or model executable code.
Each authored document is validated with body_visual_graph, versioned under
one owner workspace, and writable with exclusive/atomic source publication.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat

from .body_visual_graph import validate_graph
from .media_vault import MediaVault

_DOC_BYTES_MAX = 1024 * 1024
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\.json\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_GRAPH_DIR = "creative-graphs"


def _target(root, relative, *, must_exist=False):
    if (not isinstance(relative, str) or
            not relative.startswith(_GRAPH_DIR + "/") or
            len(relative) > 256):
        raise ValueError("Visual project path must be a private creative-graphs/*.json path")
    pieces = relative.split("/")
    if len(pieces) != 2 or not _NAME.fullmatch(pieces[1]) or pieces[1].startswith("."):
        raise ValueError("Visual project path is not a safe flat native document name")
    base = Path(root)
    if not base.is_absolute() or base.is_symlink():
        raise ValueError("Original owner workspace must be a non-symlink absolute directory")
    workspace = base.resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("Owner workspace is not a directory")
    folder = workspace / _GRAPH_DIR
    if folder.is_symlink():
        raise ValueError("Editable authoring directory was redirected")
    if folder.exists():
        if not folder.is_dir() or folder.resolve(strict=True) != folder:
            raise ValueError("Untrusted native authoring directory")
        if folder.stat().st_mode & 0o077:
            raise ValueError("Editable native artwork directory must be private to the owner")
    elif must_exist:
        raise ValueError("Editable native source does not exist")
    target = folder / pieces[1]
    if target.is_symlink():
        raise ValueError("Editable project path was redirected")
    if must_exist and (not target.is_file() or target.resolve(strict=True) != target):
        raise ValueError("Editable native visual source is absent")
    return workspace, folder, target


def _canonical_validated(document, *, root):
    try:
        # Strict primitive-only, finite, UTF-8 source. No dynamic Python,
        # pickles, loaded plugins or model-supplied shell commands.
        binary = json.dumps(
            document, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8", errors="strict")
        if len(binary) > _DOC_BYTES_MAX:
            raise ValueError("Authored visual graph exceeds source document budget")
        copied = json.loads(binary)
        validate_graph(copied)
        source_nodes = [item for item in copied["nodes"]
                        if item["op"] == "source"]
        if source_nodes:
            vault = MediaVault(Path(root) / "vault")
            for node in source_nodes:
                media = node["params"]["media"]
                receipt = vault.inspect(
                    media["asset_id"], attestation_id=media["attestation_id"])
                if (receipt.get("asset_id", media["asset_id"]) != media["asset_id"] or
                        receipt.get("rights_attestations") is None):
                    raise ValueError("Original picture has no actual rights-bound source")
        return binary
    except (TypeError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValueError("Editable visual source must be finite safe JSON") from exc


def _read_checked(root, relative):
    workspace, _folder, target = _target(root, relative, must_exist=True)
    # Open the directory and file by kernel descriptors, not a path that a
    # simultaneous editor process could replace with a symlink after preflight.
    dirfd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        sourcefd = os.open(target.name, os.O_RDONLY | os.O_NOFOLLOW,
                           dir_fd=dirfd)
        with os.fdopen(sourcefd, "rb") as stream:
            observed = os.fstat(stream.fileno())
            if not stat.S_ISREG(observed.st_mode):
                raise ValueError("Native source is not a regular owner document")
            binary = stream.read(_DOC_BYTES_MAX + 1)
        unchanged = os.stat(target.name, dir_fd=dirfd, follow_symlinks=False)
        if (observed.st_dev, observed.st_ino, observed.st_size) != (
                unchanged.st_dev, unchanged.st_ino, unchanged.st_size):
            raise ValueError("Editable source file changed during native read")
    finally:
        os.close(dirfd)
    if len(binary) > _DOC_BYTES_MAX:
        raise ValueError("Editable source exceeded the owner read budget")
    try:
        document = json.loads(binary.decode("utf-8"),
                              parse_constant=lambda _: (_ for _ in ()).throw(
                                  ValueError("Non-finite editable source")))
        _canonical_validated(document, root=workspace)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Editable native graph is invalid UTF-8 JSON") from exc
    if target.is_symlink() or target.read_bytes() != binary:
        raise ValueError("Editable source changed during native read")
    return document, hashlib.sha256(binary).hexdigest(), target


def read_visual_document(workspace, *, plan):
    """Read only a specifically named authored graph; NEVER other owner JSON."""
    doc, sha, _ = _read_checked(workspace, plan)
    return {
        "kind": "authored_native_visual_graph",
        "relative_path": plan,
        "sha256": sha,
        "graph": doc,
        "physical_render_verified": False,
    }


def author_visual_document(workspace, *, document, out,
                           base=None, expected_sha256=None):
    """Publish exactly one validated, new native graph (or a separate revision).

    A revision references a byte-exact existing document and creates a NEW
    path. Never overwrite an existing drawing, arbitrary owner path or media.
    """
    root, folder, target = _target(workspace, out)
    old = None
    if (base is None) != (expected_sha256 is None):
        raise ValueError("Revision base and expected source SHA must both be explicit")
    if base is not None:
        if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256):
            raise ValueError("Exact source SHA required for revised native artwork")
        _doc, actual, _path = _read_checked(root, base)
        if actual != expected_sha256:
            raise ValueError("Native visual graph source revision has changed")
        if base == out:
            raise ValueError("A revision must preserve its original source file")
        old = {"path": base, "sha256": actual}
    binary = _canonical_validated(document, root=root)
    if target.exists() or target.is_symlink():
        raise FileExistsError("An existing native creative source cannot be overwritten")
    # Directory creation is a permitted owner write *after* input/rights checks.
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.is_symlink() or folder.stat().st_mode & 0o077:
        raise ValueError("Native artwork directory is not private")
    dirfd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    stage = ".zx7-authored-" + secrets.token_hex(16) + ".tmp"
    try:
        fd = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                     0o600, dir_fd=dirfd)
        try:
            with os.fdopen(fd, "wb") as outstream:
                outstream.write(binary)
                outstream.flush()
                os.fsync(outstream.fileno())
            # Atomic no-clobber, SAME opened owner directory descriptor.
            # Path-redirection races cannot relocate a write into another
            # project or change the destination inode after validation.
            os.link(stage, target.name, src_dir_fd=dirfd,
                    dst_dir_fd=dirfd, follow_symlinks=False)
            os.fsync(dirfd)
            observed = os.fstat(dirfd)
            current = folder.stat()
            if (folder.is_symlink() or
                    (observed.st_dev, observed.st_ino) !=
                    (current.st_dev, current.st_ino)):
                raise ValueError("Authored source directory changed during native commit")
        finally:
            os.unlink(stage, dir_fd=dirfd)
            os.fsync(dirfd)
    finally:
        os.close(dirfd)
    return {
        "kind": "authored_native_visual_graph",
        "relative_path": out,
        "sha256": hashlib.sha256(binary).hexdigest(),
        "previous": old,
        "editable_source_file_committed": True,
        "physical_render_verified": False,
    }
