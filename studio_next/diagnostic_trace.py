"""Durable, host-authored, source-neutral execution-stage evidence.

Append small categorical receipts only. Prompts, tool inputs, local media paths,
model completions, and raw exception strings are forbidden. No public event
injection endpoint exists. A SHA-256 chain detects accidental history edits;
it is *not* an independent signature against an adversary controlling SQLite.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time

_PHASES = frozenset((
    "source", "perception", "planning", "discovery", "contract",
    "execution", "observation", "verification", "review", "delivery",
))
_OUTCOMES = frozenset((
    "started", "observed", "verified", "failed", "paused",
    "cancelled", "unmeasured", "unknown",
))
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_CODE = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")
_ZERO = "0" * 64


class DiagnosticTraceError(ValueError):
    """Durable diagnostic source is malformed or contradictory."""


def initialize_trace_store(db):
    """Create a tiny append-only evidence table in the existing durable DB."""
    db.execute("""CREATE TABLE IF NOT EXISTS diagnostic_trace_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_json TEXT NOT NULL,
        prior_sha256 TEXT NOT NULL,
        record_sha256 TEXT NOT NULL)""")


def _identity(value, name):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise DiagnosticTraceError("Invalid source-neutral " + name)


def _encode(record):
    return json.dumps(record, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def append_host_event(db, *, trace_id, capability_id, phase,
                      outcome, code, elapsed_ms=None, observed_at=None):
    """Append after the host acquires an IMMEDIATE SQLite transaction.

    No model-provided data is accepted by this API. Only the trusted host
    passes fixed status classifications from its actual execution boundary.
    """
    if not db.in_transaction:
        raise DiagnosticTraceError("Host trace writes require an atomic SQLite transaction")
    _identity(trace_id, "trace")
    _identity(capability_id, "capability")
    if phase not in _PHASES or outcome not in _OUTCOMES:
        raise DiagnosticTraceError("Unknown actual execution stage or outcome")
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        raise DiagnosticTraceError("Diagnostic codes cannot contain raw user data")
    if elapsed_ms is not None and (
            type(elapsed_ms) not in (float, int)
            or not math.isfinite(elapsed_ms) or not 0 <= elapsed_ms < 1e10):
        raise DiagnosticTraceError("Measured execution duration is invalid")
    moment = time.time() if observed_at is None else observed_at
    if type(moment) not in (float, int) or not math.isfinite(moment) or moment < 0:
        raise DiagnosticTraceError("Host clock reading is invalid")
    row = db.execute(
        "SELECT record_sha256 FROM diagnostic_trace_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    previous = row[0] if row else _ZERO
    if not isinstance(previous, str) or not re.fullmatch("[0-9a-f]{64}", previous):
        raise DiagnosticTraceError("Host trace chain anchor is malformed")
    event = {
        "schema": 1, "trace_id": trace_id, "capability_id": capability_id,
        "phase": phase, "outcome": outcome, "code": code,
        "observed_at": round(moment, 6),
        "elapsed_ms": round(elapsed_ms, 3) if elapsed_ms is not None else None,
        "model_causality_not_assigned": True,
    }
    raw = _encode(event)
    if len(raw) > 2048:
        raise DiagnosticTraceError("Diagnostic receipt exceeded bounded evidence budget")
    digest = hashlib.sha256(bytes.fromhex(previous) + raw).hexdigest()
    db.execute(
        "INSERT INTO diagnostic_trace_events(record_json,prior_sha256,record_sha256)"
        " VALUES(?,?,?)",
        (raw.decode("utf-8"), previous, digest))
    return digest


def read_recent_host_events(db, *, limit=32):
    """Check linked hashes and return bounded recent categorical evidence.

    Verifies the whole returned window and its earliest available adjacent
    event, but does not pretend an externally notarized complete history.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise DiagnosticTraceError("Invalid bounded diagnostic history page")
    rows = db.execute(
        "SELECT id,record_json,prior_sha256,record_sha256 "
        "FROM diagnostic_trace_events ORDER BY id DESC LIMIT ?", (limit + 1,)
    ).fetchall()
    if not rows:
        return {"recent_events": [], "observed_event_count": 0,
                "recent_window_hashes_valid": True,
                "externally_signed_or_globally_certified": False}
    ascending = list(reversed(rows))
    previous_hash = None
    for identifier, raw, prior, digest in ascending:
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > 2048:
            raise DiagnosticTraceError("Host diagnostic event is corrupt")
        if not all(isinstance(x, str) and re.fullmatch("[0-9a-f]{64}", x)
                   for x in (prior, digest)):
            raise DiagnosticTraceError("Host diagnostic hash is corrupt")
        if previous_hash is not None and previous_hash != prior:
            raise DiagnosticTraceError("Host diagnostic events lost chain continuity")
        if hashlib.sha256(bytes.fromhex(prior) + raw.encode("utf-8")).hexdigest() != digest:
            raise DiagnosticTraceError("Host diagnostic receipt no longer matches hash")
        try:
            event = json.loads(raw)
        except ValueError as exc:
            raise DiagnosticTraceError("Host diagnostic receipt not parseable") from exc
        if (not isinstance(event, dict)
                or event.get("schema") != 1
                or event.get("phase") not in _PHASES
                or event.get("outcome") not in _OUTCOMES
                or event.get("model_causality_not_assigned") is not True):
            raise DiagnosticTraceError("Host diagnostic semantic invariant failed")
        previous_hash = digest
    events = [json.loads(raw) for _, raw, _, _ in reversed(ascending[-limit:])]
    return {"recent_events": events,
            "observed_event_count": db.execute(
                "SELECT COUNT(*) FROM diagnostic_trace_events").fetchone()[0],
            "recent_window_hashes_valid": True,
            "externally_signed_or_globally_certified": False,
            "only_host_classified_stage_codes": True}
