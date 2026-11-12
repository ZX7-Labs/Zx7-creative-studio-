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
from pathlib import Path
import re
import sqlite3
import stat
import time

from .durable_sqlite import connect_durable_database


_SHA = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_OPERATION = re.compile(r"[a-z][a-z0-9_-]{0,47}/[^\x00-\x1f\x7f]{1,160}\Z")
_TERMINAL_STATES = frozenset({
    "host_reported_success_unverified",
    "write_uncertain_reconciliation_required",
    "native_conflict_rejected_no_write",
})

# Original on-disk schema is kept as an exact migration reference. A verified
# source-native CAS rejection is terminal, but NEVER replayable. Unlike an
# uncertain remote write it needs no project-state reconciliation.
_LEGACY_TABLE_SQL = """CREATE TABLE capability_attempts (
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
)"""
_CURRENT_TABLE_SQL = _LEGACY_TABLE_SQL.replace(
    "'write_uncertain_reconciliation_required'))",
    "'write_uncertain_reconciliation_required',\n"
    "        'native_conflict_rejected_no_write'))",
)
if _CURRENT_TABLE_SQL == _LEGACY_TABLE_SQL:
    raise RuntimeError("Native journal schema transition is missing")


def _normalized_schema_sql(statement):
    # SQLite may write IF NOT EXISTS in the schema and quote a renamed table.
    # Never migrate an unrelated or unexpected on-disk ledger schema.
    without_conditional = re.sub(
        r"\bIF\s+NOT\s+EXISTS\b", "", statement, flags=re.I)
    return re.sub(r"\s+", "", without_conditional.replace('"', "")).lower()


class CapabilityAttemptError(ValueError):
    """No new native side effect was admitted; inspect/reconcile the attempt."""


class CapabilityAttemptStore:
    """Host-owned durable SQLite intent journal; no paths, media or model text.

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
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' "
                    "AND name='capability_attempts'").fetchone()
                if row is None:
                    db.execute(_CURRENT_TABLE_SQL)
                elif (_normalized_schema_sql(row[0]) ==
                      _normalized_schema_sql(_LEGACY_TABLE_SQL)):
                    # Atomic forward-only migration: old intents survive
                    # exactly, including crash-window/uncertain writes.
                    # No queue, media, identity or payload is copied outside
                    # the private database. Failed migration rolls back.
                    other = db.execute(
                        "SELECT 1 FROM sqlite_master WHERE "
                        "name='capability_attempts_revision_next'").fetchone()
                    if other is not None:
                        raise CapabilityAttemptError(
                            "Unexpected native journal migration residue")
                    db.execute(_CURRENT_TABLE_SQL.replace(
                        "CREATE TABLE capability_attempts",
                        "CREATE TABLE capability_attempts_revision_next", 1))
                    fields = ("request_id,operation_id,catalog_revision,"
                              "input_sha256,state,admitted_ns,settled_ns")
                    db.execute(
                        "INSERT INTO capability_attempts_revision_next "
                        f"({fields}) SELECT {fields} FROM capability_attempts")
                    db.execute("DROP TABLE capability_attempts")
                    db.execute("ALTER TABLE capability_attempts_revision_next "
                               "RENAME TO capability_attempts")
                elif (_normalized_schema_sql(row[0]) !=
                      _normalized_schema_sql(_CURRENT_TABLE_SQL)):
                    raise CapabilityAttemptError(
                        "Unknown durable native attempt journal schema")
                db.execute("""CREATE INDEX IF NOT EXISTS
                    ix_capability_attempts_stable_scan
                    ON capability_attempts(admitted_ns, request_id)""")
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def _connect(self):
        # Reuse the production SQLite policy rather than forcing WAL on
        # runtimes affected by the upstream WAL-reset vulnerability.
        # This also closes each connection after its transaction.
        return connect_durable_database(self.path)

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
                # An explicitly stored logical timestamp is the scan key.
                # Clamp to the last committed admission so NTP/OS clock
                # rollback cannot move a NEW write behind a recovery cursor.
                last=db.execute(
                    "SELECT MAX(admitted_ns) FROM capability_attempts"
                ).fetchone()[0]
                if last is not None and (
                        type(last) is not int or not 0 <= last < 2**63-1):
                    raise CapabilityAttemptError(
                        "Durable native admission clock history is invalid")
                now=time.time_ns()
                admission=max(now, 0 if last is None else last+1)
                if type(now) is not int or not 0 <= admission < 2**63:
                    raise CapabilityAttemptError(
                        "Durable native admission clock exceeded SQLite bounds")
                db.execute("""INSERT INTO capability_attempts (
                    request_id,operation_id,catalog_revision,input_sha256,state,
                    admitted_ns,settled_ns) VALUES (?, ?, ?, ?, ?, ?, NULL)""",
                    (request_id, operation_id, catalog_revision, input_sha256,
                     "submitted_unconfirmed", admission))
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

    def unverified_attempts(self, *, limit=32, cursor=None):
        """Host-only bounded recovery inventory; no native write is replayed.

        Use the EXPLICITLY STORED (admitted_ns,request_id) B-tree key. SQLite
        can reassign implicit rowids during VACUUM, so they are not a durable
        cursor. Every new admission commits a logical timestamp greater than
        the previous maximum (including after system-clock rollback), meaning
        new rows cannot be inserted behind an already issued page cursor.

        Transport ACK remains unverified native application state. No model
        prompts, raw tool outputs, media, or local paths appear in the ledger.
        """
        if type(limit) is not int or not 1 <= limit <= 100:
            raise CapabilityAttemptError(
                "Host recovery inventory requires a bounded page of at most 100")
        if cursor is None:
            start_ns, start_request = 0, ""
        else:
            if (type(cursor) is not dict or
                    set(cursor)!={"admitted_ns","request_id"} or
                    type(cursor["admitted_ns"]) is not int or
                    not 0 <= cursor["admitted_ns"] < 2**63 or
                    not isinstance(cursor["request_id"],str) or
                    not _REQUEST.fullmatch(cursor["request_id"])):
                raise CapabilityAttemptError(
                    "Recovery cursor needs exact stable journal identity")
            start_ns, start_request = cursor["admitted_ns"], cursor["request_id"]
        with self._connect() as db:
            rows = db.execute("""SELECT request_id,operation_id,
                catalog_revision,input_sha256,state,admitted_ns,settled_ns
                FROM capability_attempts
                WHERE (admitted_ns,request_id) > (?,?)
                  AND state!='native_conflict_rejected_no_write'
                ORDER BY admitted_ns,request_id LIMIT ?""",
                (start_ns,start_request,limit+1)).fetchall()
        selected = rows[:limit]
        entries = []
        for row in selected:
            request, operation, revision, digest, state, admitted, settled = row
            self._validate(request, operation, revision, digest)
            if (state not in _TERMINAL_STATES|{"submitted_unconfirmed"} or
                    type(admitted) is not int or admitted < 0 or
                    (settled is not None and
                     (type(settled) is not int or settled < 0))):
                raise CapabilityAttemptError(
                    "Durable native attempt record is inconsistent")
            entries.append({
                "request_id":request,"operation_id":operation,
                "catalog_revision":revision,"input_sha256":digest,
                "state":state,"admitted_ns":admitted,
                "settled_ns":settled,
                "native_application_state_independently_verified":False,
            })
        more = len(rows)>limit
        return {
            "attempts":entries,"has_more":more,
            "next_cursor":({
                "admitted_ns":selected[-1][5],
                "request_id":selected[-1][0],
            } if more else None),
            "durable_host_recovery_inventory":True,
            "every_listed_attempt_requires_native_reconciliation":True,
            "no_native_write_replayed":True,
        }
