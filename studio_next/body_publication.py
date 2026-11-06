"""Reconcile original physical output across renderer/SQLite crash windows.

An immutable receipt binds decoded bytes to the exact trusted graph attempt.
It is fsynced BEFORE publishing the final file. Recovery can finish that
publication without invoking the renderer or accepting an unrelated old file.
The private host workspace is the trust boundary; this is not a signature.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path


_ATTEMPT = contextvars.ContextVar("zx7_physical_publication", default=None)
_PUBLICATION_GUARD = contextvars.ContextVar(
    "zx7_physical_publication_guard", default=None)
_SHA = re.compile(r"^[0-9a-f]{64}$")


@contextmanager
def physical_tool_attempt(project_key, node_id, input_key, tool_id, *,
                          publication_guard=None):
    """Only the host executor supplies producer identity and lease authority.

    The receipt identity is deliberately stable across safe recovery attempts;
    the *live* worker owner is kept in a separate private context variable.
    """
    if publication_guard is not None and not callable(publication_guard):
        raise TypeError("Only the host supplies an active publication guard")
    identity = {"project_key": project_key, "node_id": node_id,
                "input_key": input_key, "tool_id": tool_id}
    token = _ATTEMPT.set(identity)
    guard_token = _PUBLICATION_GUARD.set(publication_guard)
    try:
        yield
    finally:
        _PUBLICATION_GUARD.reset(guard_token)
        _ATTEMPT.reset(token)


@contextmanager
def authorized_publication():
    """Fence physical publication to the exact active durable worker owner.

    The host guard holds the SQLite admission transaction while the final
    hardlink/receipt is published, so another worker cannot take over between
    checking an owner and publishing. No lease is inferred from model text.
    """
    if _ATTEMPT.get() is None:
        # Legacy explicit tool invocation has no graph custody receipt.
        yield
        return
    guard = _PUBLICATION_GUARD.get()
    if guard is None:
        raise PermissionError(
            "Graph-bound media publication needs an active host worker lease")
    with guard():
        yield


def current_trusted_attempt_tool():
    """Current verified host-graph operation, or None outside execution.

    A bare model/owner-supplied output witness is not authority to certify
    generated rights. A graph-bound producer proof must be established first.
    """
    identity=_ATTEMPT.get()
    return identity.get("tool_id") if isinstance(identity,dict) else None


def _sync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _receipt_location(final):
    identity = _ATTEMPT.get()
    if identity is None:
        return None
    final = Path(final).absolute()
    key = hashlib.sha256(json.dumps(
        {"identity": identity, "output": str(final)},
        sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    directory = final.parent / ".zx7-publications"
    if directory.is_symlink():
        raise ValueError("Linked production publication journal is untrusted")
    return directory / (key + ".json")


def publication_record_exists(final):
    path = _receipt_location(final)
    return path is not None and not path.is_symlink() and path.is_file()


def require_published_source(final, tool_id):
    """Verify host-journal provenance when a native project becomes a source.

    The private host journal, not a model-authored bundle manifest, establishes
    the producing tool. This does not grant rights to uploaded external files.
    """
    final=Path(final).absolute()
    directory=final.parent/".zx7-publications"
    if directory.is_symlink() or final.is_symlink() or not directory.is_dir():
        raise ValueError("Source needs an authentic host publication")
    for receipt in directory.glob("*.json"):
        if receipt.is_symlink() or receipt.stat().st_size>16384:continue
        try:
            record=json.loads(receipt.read_text())
            identity=record["identity"]
            if record["output"]!=str(final) or identity["tool_id"]!=tool_id:continue
            with physical_tool_attempt(**identity):
                if _receipt_location(final)!=receipt:continue
                verified=_load_receipt(final)
            with final.open("rb") as stream:actual=hashlib.file_digest(stream,"sha256").hexdigest()
            if verified["sha256"]==actual and verified["bytes"]==final.stat().st_size:return actual
        except (ValueError,KeyError,TypeError,OSError):continue
    raise ValueError("Source has no matching native producer publication")


def _load_receipt(final):
    path = _receipt_location(final)
    if path is None or not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size > 16384:
        raise ValueError("Untrusted physical publication receipt")
    record = json.loads(path.read_text(encoding="utf-8"))
    fields = {"schema", "identity", "output", "stage", "sha256", "bytes"}
    if (not isinstance(record, dict) or set(record) != fields or
            record["schema"] != 1 or record["identity"] != _ATTEMPT.get() or
            record["output"] != str(Path(final).absolute()) or
            not isinstance(record["sha256"], str) or
            not _SHA.fullmatch(record["sha256"]) or
            type(record["bytes"]) is not int or record["bytes"] < 100):
        raise ValueError("Publication receipt differs from original trusted tool attempt")
    name = record["stage"]
    if (not isinstance(name, str) or Path(name).name != name or
            not re.fullmatch(r"\.zx7-uncommitted-[0-9a-f]{32}" +
                             re.escape(Path(final).suffix), name)):
        raise ValueError("Publication receipt contains an unsafe source stage")
    return record


def prepare_publication(final, stage, witness):
    """Durably journal verified original bytes before their final hardlink."""
    receipt = _receipt_location(final)
    if receipt is None:
        return
    final, stage = Path(final).absolute(), Path(stage).absolute()
    if stage.parent != final.parent or stage.is_symlink():
        raise ValueError("Original publication stage must be a local regular file")
    record = {"schema": 1, "identity": _ATTEMPT.get(),
              "output": str(final), "stage": stage.name,
              "sha256": witness["sha256"], "bytes": witness["bytes"]}
    # Tools have already closed the encoded file; force its data to storage
    # before a durable receipt could advertise it after process/power loss.
    with stage.open("rb") as media:
        os.fsync(media.fileno())
    receipt.parent.mkdir(mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".receipt-", dir=receipt.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(record, out, sort_keys=True, ensure_ascii=False,
                      allow_nan=False)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, receipt)
        _sync_directory(receipt.parent)
        _sync_directory(final.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def recover_publication(final, *, witness, verify):
    """Return the same decoded output, or None if nothing was published yet."""
    final = Path(final).absolute()
    record = _load_receipt(final)
    if record is None:
        return None
    stage = final.parent / record["stage"]
    source = final if final.exists() else stage
    if not source.exists():
        return None  # Idempotent execution can recreate genuinely lost bytes.
    if source.is_symlink() or not source.is_file():
        raise ValueError("Untrusted linked or nonregular original media publication")
    actual = witness(source)
    if (actual.get("sha256") != record["sha256"] or
            actual.get("bytes") != record["bytes"] or not verify(actual)):
        raise ValueError("Original published media no longer matches physical receipt")
    if source == stage:
        os.link(stage, final)  # Never replace a different accepted file.
        _sync_directory(final.parent)
    # A redundant verified stage may remain when the host was killed after
    # linking the final file. Only remove the actual same inode.
    if stage.exists() and not stage.is_symlink() and os.path.samefile(stage, final):
        stage.unlink()
        _sync_directory(final.parent)
    return witness(final)


def sync_published_file(final):
    _sync_directory(Path(final).parent)
