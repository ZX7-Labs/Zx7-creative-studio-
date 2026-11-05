"""Durable, privacy-bounded admission for any stateful creative BODY operation.

This is NOT a tool runner or a claim that an engine committed its changes.
A committed intent exists before a non-idempotent native RPC is dispatched.
If the process dies or the RPC result is ambiguous, an identical host request
cannot silently execute again after restart. Independent native project-state
reconciliation is still required before the host can author a new attempt.

Physical render publication remains owned by body_publication; this ledger
covers generic live editor/3D/audio/graphics tool side effects instead.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import stat
import time


_SHA = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_OPERATION = re.compile(r"[a-z][a-z0-9_-]{0,47}/[^\x00-\x1f\x7f]{1,160}\Z")
_TERMINAL_STATES = frozenset({
    "host_reported_success_unverified",
    "write_uncertain_reconciliation_required",
})


class CapabilityAttemptError(ValueError):
    """No new native side effect was admitted; inspect/reconcile the attempt."""


class CapabilityAttemptStore:
    """Host-owned SQLite WAL intent journal; no source paths, media or model text.

    The caller supplies a stable, host-assigned request_id, not a generated
    per-RPC ID and not an unchecked model assertion of idempotency. One request
    is admitted at most once, even after a previous process dies.
    """

    def __init__(self, path: Path):
        path = Path(path).absolute()
        parent = path.parent
        if parent.is_symlink():
            raise CapabilityAttemptError("Capability journal directory cannot be linked")
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if (not parent.is_dir() or parent.is_symlink() or
                stat.S_IMODE(parent.stat().st_mode) & 0o077):
            raise CapabilityAttemptError("Capability journal requires a private directory")
        if path.is_symlink():
            raise CapabilityAttemptError("Capability journal cannot be a symlink")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                         getattr(os, "O_CLOEXEC", 0) |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        st = path.stat(follow_symlinks=False)
        if (not stat.S_ISREG(st.st_mode) or
                stat.S_IMODE(st.st_mode) & 0o077):
            raise CapabilityAttemptError("Capability journal must be a private regular file")
        self.path = path
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS capability_attempts (
                request_id TEXT PRIMARY KEY,
                operation_id TEXT NOT NULL,
                catalog_revision TEXT NOT NULL,
                input_sha256 TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN (
                    'submitted_unconfirmed',
                    'host_reported_success_unverified',
                    'write_uncertain_reconciliation_required')),
                admitted_ns INTEGER NOT NULL,
                settled_ns INTEGER
            )""")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout = 10000")
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = FULL")
            yield db
        finally:
            db.close()

    @staticmethod
    def _validate(request_id, operation_id, catalog_revision, input_sha256):
        if not isinstance(request_id, str) or not _REQUEST.fullmatch(request_id):
            raise CapabilityAttemptError("Host request identity is missing or malformed")
        if not isinstance(operation_id, str) or not _OPERATION.fullmatch(operation_id):
            raise CapabilityAttemptError("Installed operation identity is malformed")
        if (not isinstance(catalog_revision, str) or
                not _SHA.fullmatch(catalog_revision) or
                not isinstance(input_sha256, str) or
                not _SHA.fullmatch(input_sha256)):
            raise CapabilityAttemptError("Exact capability and input digests required")

    def admit(self, *, request_id, operation_id, catalog_revision, input_sha256):
        """Atomically commit non-replayable intent before the first native call."""
        self._validate(request_id, operation_id, catalog_revision, input_sha256)
        with self._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("""INSERT INTO capability_attempts (
                    request_id,operation_id,catalog_revision,input_sha256,state,
                    admitted_ns,settled_ns) VALUES (?, ?, ?, ?, ?, ?, NULL)""",
                    (request_id, operation_id, catalog_revision, input_sha256,
                     "submitted_unconfirmed", time.time_ns()))
                db.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                db.execute("ROLLBACK")
                raise CapabilityAttemptError(
                    "Host request was already admitted; never replay a native write"
                ) from exc
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def settle(self, *, request_id, state):
        """Record host transport outcome, never pretend a write was applied."""
        if (not isinstance(request_id, str) or not _REQUEST.fullmatch(request_id)
                or state not in _TERMINAL_STATES):
            raise CapabilityAttemptError("Invalid native write settlement")
        with self._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                changed = db.execute("""UPDATE capability_attempts
                    SET state=?, settled_ns=?
                    WHERE request_id=? AND state='submitted_unconfirmed'""",
                    (state, time.time_ns(), request_id))
                if changed.rowcount != 1:
                    raise CapabilityAttemptError(
                        "Unknown or previously settled native attempt")
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def inspect(self, request_id):
        """Return host-safe provenance, including unresolved crash windows."""
        if not isinstance(request_id, str) or not _REQUEST.fullmatch(request_id):
            raise CapabilityAttemptError("Invalid host request identity")
        with self._connect() as db:
            record = db.execute("""SELECT request_id,operation_id,
                catalog_revision,input_sha256,state,admitted_ns,settled_ns
                FROM capability_attempts WHERE request_id=?""",
                (request_id,)).fetchone()
        return (dict(zip(("request_id", "operation_id", "catalog_revision",
                          "input_sha256", "state", "admitted_ns", "settled_ns"),
                         record)) if record else None)
