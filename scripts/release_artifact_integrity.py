"""Fail-closed public CI artifact preflight for source-bound ZX7 release proofs.

The release evidence manifest inventories *all* source files, including private-
by-default .zx7-publications receipts. actions/upload-artifact omits hidden
files unless specifically enabled. A green CI run with 22 missing receipts is
not a complete retained proof. This verifier gates hidden-file inclusion to
only known, structurally valid synthetic publication receipts. It does not
grant publication rights or certify creativity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

_RECEIPT_NAME = re.compile(r"[0-9a-f]{64}\.json\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MANIFEST = "verified-release-evidence.json"


class ReleaseArtifactIntegrityError(ValueError):
    """Retained release proof cannot be reconciled to its physical files."""


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseArtifactIntegrityError("Duplicate evidence JSON field")
        result[key] = value
    return result


def _json(path: Path, *, limit: int):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ReleaseArtifactIntegrityError("Missing, linked or oversized evidence JSON")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ReleaseArtifactIntegrityError("Invalid release evidence JSON") from exc


def _safe_relative_path(value: object) -> PurePosixPath:
    if (not isinstance(value, str) or not value or len(value) > 1024 or
            "\\" in value or "\x00" in value):
        raise ReleaseArtifactIntegrityError("Invalid archive evidence path")
    path = PurePosixPath(value)
    if (path.is_absolute() or str(path) != value or
            any(part in (".", "..") for part in path.parts)):
        raise ReleaseArtifactIntegrityError("Unsafe or noncanonical evidence path")
    return path


def _is_approved_hidden_receipt(relative: PurePosixPath) -> bool:
    hidden = [(i, part) for i, part in enumerate(relative.parts)
              if part.startswith(".")]
    return (len(hidden) == 1 and
            hidden[0] == (len(relative.parts) - 2, ".zx7-publications") and
            bool(_RECEIPT_NAME.fullmatch(relative.name)))


def _check_hidden_file(path: Path, root: Path, relative: PurePosixPath, *,
                       relocated: bool) -> bool:
    if not any(part.startswith(".") for part in relative.parts):
        return False
    if not _is_approved_hidden_receipt(relative):
        raise ReleaseArtifactIntegrityError("Unexpected hidden file in public release proof")
    receipt = _json(path, limit=16 * 1024)
    fields = {"schema", "identity", "output", "stage", "sha256", "bytes"}
    if (type(receipt) is not dict or set(receipt) != fields or
            type(receipt["schema"]) is not int or receipt["schema"] != 1 or
            type(receipt["identity"]) is not dict or
            set(receipt["identity"]) !=
            {"project_key", "node_id", "input_key", "tool_id"} or
            type(receipt["output"]) is not str or
            type(receipt["sha256"]) is not str or
            not _SHA.fullmatch(receipt["sha256"]) or
            type(receipt["bytes"]) is not int or receipt["bytes"] < 100):
        raise ReleaseArtifactIntegrityError("Invalid synthetic publication receipt")
    output = Path(receipt["output"])
    if not output.is_absolute():
        raise ReleaseArtifactIntegrityError("Publication receipt output must be absolute")
    if relocated:
        # Original host-absolute output paths must not be rewritten in an
        # immutable receipt just because CI artifacts were downloaded elsewhere.
        # This checks retained bytes and sibling identity, NOT host authority.
        if not (path.parent.parent / output.name).is_file():
            raise ReleaseArtifactIntegrityError("Relocated publication output is missing")
    elif not output.is_relative_to(root) or output.parent != path.parent.parent:
        raise ReleaseArtifactIntegrityError("Publication receipt references external output")
    expected_stage = r"\.zx7-uncommitted-[0-9a-f]{32}" + re.escape(output.suffix)
    if (type(receipt["stage"]) is not str or
            not re.fullmatch(expected_stage, receipt["stage"])):
        raise ReleaseArtifactIntegrityError("Publication receipt references unsafe stage")
    return True


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_release_tree(root: Path, *, relocated: bool = False) -> dict:
    """Check every eligible upload byte, no untracked/secret hidden files.

    Call once immediately before the only hidden-inclusive artifact upload,
    then again on the actual downloaded artifact, not just on the source tree.
    """
    if type(relocated) is not bool:
        raise ReleaseArtifactIntegrityError("Invalid retained-evidence audit mode")
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ReleaseArtifactIntegrityError("Missing or linked release proof root")
    manifest = _json(root / _MANIFEST, limit=8 * 1024 * 1024)
    if (type(manifest) is not dict or
            type(manifest.get("artifacts")) is not list or
            not 0 < len(manifest["artifacts"]) <= 10000):
        raise ReleaseArtifactIntegrityError("Missing or unbounded release inventory")

    by_name = {}
    for entry in manifest["artifacts"]:
        if (type(entry) is not dict or set(entry) != {"path", "bytes", "sha256"} or
                type(entry["bytes"]) is not int or entry["bytes"] < 0 or
                type(entry["sha256"]) is not str or not _SHA.fullmatch(entry["sha256"])):
            raise ReleaseArtifactIntegrityError("Invalid release inventory entry")
        name = str(_safe_relative_path(entry["path"]))
        if name == _MANIFEST or name in by_name:
            raise ReleaseArtifactIntegrityError("Duplicated or self-referential release inventory")
        by_name[name] = entry

    actual = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ReleaseArtifactIntegrityError("Linked file or directory in release evidence")
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        _safe_relative_path(name)
        actual[name] = path
    if set(actual) != set(by_name) | {_MANIFEST}:
        raise ReleaseArtifactIntegrityError("Actual retained release files disagree with manifest")

    receipts = 0
    for name, entry in by_name.items():
        path = actual[name]
        receipts += int(_check_hidden_file(
            path, root, PurePosixPath(name), relocated=relocated))
        if path.stat().st_size != entry["bytes"] or _sha256(path) != entry["sha256"]:
            raise ReleaseArtifactIntegrityError("Release file changed after evidence inventory")
    return {"schema": 1, "verified": True, "files": len(by_name),
            "source_bound_publication_receipts": receipts,
            "artistic_quality_approved": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_directory", type=Path)
    parser.add_argument("--relocated", action="store_true",
                        help="Audit bytes after download, retaining original absolute receipt origins")
    args = parser.parse_args()
    print(json.dumps(verify_release_tree(
        args.release_directory, relocated=args.relocated),
                     sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
