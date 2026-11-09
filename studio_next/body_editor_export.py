"""Independently decode and attest a native editor's physical export.

The source editor's "success" tool response cannot certify actual A/V output.
This is a read-only, host-scoped observation; it never certifies artistic quality
or claims a transactionally isolated media sandbox.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

from .body_editor_client import EditorAccessError
from .body_editor_policy import EditorPathPolicy
from .media_vault import sha256_file
from .production_qc import full_decode_inspection


VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".webm"})


def native_export_file_identity(path: Path):
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size < 512:
        raise ValueError("Native export must be an actual nonempty regular video file")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, sha256_file(path))


def _no_path_symlinks(path: Path, roots: tuple[Path, ...]) -> bool:
    """Reject link-based indirection from an authorized canonical root."""
    for root in roots:
        if not path.is_relative_to(root):
            continue
        ancestor = path
        while ancestor != root:
            if ancestor.is_symlink():
                return False
            ancestor = ancestor.parent
        return True
    return False


def verify_native_editor_export(path: str, *, policy: EditorPathPolicy,
                                expected: dict | None = None,
                                max_seconds: int = 7200,
                                inspector=full_decode_inspection) -> dict:
    """Inspect a *completed* physical export; reject mutated or escaped files.

    The host supplies roots and the decode budget, not the AI's tool arguments.
    A hash and filesystem identity are checked before and after full decode;
    this detects concurrent mutation but does not replace OS-level isolation.
    """
    if not isinstance(path, str) or not path or not Path(path).is_absolute():
        raise EditorAccessError("Native export path must be absolute")
    if not isinstance(policy, EditorPathPolicy):
        raise TypeError("A trusted editor host policy is required")
    if not policy("inspect_export_file", {"path": path}, "read") or not Path(
            path).resolve().is_relative_to(policy.outputs_root):
        raise EditorAccessError("Export observation requires the host's dedicated output root")
    source = Path(path)
    if source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("Expected a supported native video export")
    if not _no_path_symlinks(source, (policy.outputs_root,)):
        raise EditorAccessError("Export observation refuses symbolic-link indirection")
    before = native_export_file_identity(source)
    report = inspector(source, expected=expected, max_seconds=max_seconds)
    after = native_export_file_identity(source)
    if before != after or report.get("sha256") != before[-1]:
        raise ValueError("Native export changed during independent decoding")
    if not report.get("technical_delivery_verified"):
        raise ValueError("Native export failed independent picture/sound checks: "
                         + "; ".join(report.get("delivery_mismatches", [])))
    return {
        "schema": 1,
        "kind": "native_editor_independent_decoded_export",
        "native_export_sha256": before[-1],
        "bytes": before[2],
        "observation": report,
        "physical_export_verified": True,
        "artistic_quality_approved": False,
        "autonomous_ai_creativity_proven": False,
        "source_editor_response_is_not_evidence": True,
    }
