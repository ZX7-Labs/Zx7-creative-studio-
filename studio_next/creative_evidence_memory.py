"""Shared bounded creative-evidence memory; observations, not model retraining.

Only instrument-produced compact reference graphs are admitted in this first
adapter. No original video, audio or private frame bytes are persisted.
Deduplication, zlib, SHA-256 integrity and explicit payload quota are real.
Never silently evict an existing creative case to make room.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import zlib


class EvidenceMemoryError(ValueError):
    pass


def _pack(document):
    if (not isinstance(document, dict) or
            document.get("schema") != "ZX7_AUTHORIZED_REFERENCE_GRAPH_V1"):
        raise EvidenceMemoryError("Measured ZX7 reference graph required")
    digest = document.get("source_sha256")
    if (not isinstance(digest, str) or len(digest) != 64 or
            any(x not in "0123456789abcdef" for x in digest)):
        raise EvidenceMemoryError("Real source identity is required")
    try:
        raw = json.dumps(document, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, separators=(",", ":")).encode()
    except (ValueError, TypeError) as exc:
        raise EvidenceMemoryError("Noncanonical creative evidence") from exc
    if len(raw) > 2_000_000:
        raise EvidenceMemoryError("Evidence exceeds bounded record size")
    return raw, zlib.compress(raw, level=6)


class CreativeEvidenceMemory:
    def __init__(self, path, *, max_compressed_bytes=100*1024*1024):
        if type(max_compressed_bytes) is not int or max_compressed_bytes < 4096:
            raise EvidenceMemoryError("Host must provide a safe memory budget")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limit = max_compressed_bytes
        self._lock = threading.RLock()
        self.db = sqlite3.connect(str(self.path), timeout=15,
                                  check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("""CREATE TABLE IF NOT EXISTS evidence(
            id TEXT PRIMARY KEY,
            source_sha256 TEXT NOT NULL,
            compressed BLOB NOT NULL,
            content_sha256 TEXT NOT NULL,
            uncompressed_bytes INTEGER NOT NULL,
            compressed_bytes INTEGER NOT NULL,
            created_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )""")
        self.db.execute("CREATE INDEX IF NOT EXISTS source_evidence_idx ON evidence(source_sha256)")
        self.db.commit()

    def close(self):
        with self._lock:
            self.db.close()

    def store(self, document):
        raw, packed = _pack(document)
        checksum = hashlib.sha256(raw).hexdigest()
        identity = hashlib.sha256(
            (document["source_sha256"] + ":" + checksum).encode()).hexdigest()
        with self._lock, self.db:
            exists = self.db.execute("SELECT 1 FROM evidence WHERE id=?",
                                     (identity,)).fetchone()
            if exists:
                return {"id": identity, "deduplicated": True,
                        "compressed_bytes": len(packed)}
            used = self.db.execute(
                "SELECT COALESCE(SUM(compressed_bytes),0) FROM evidence").fetchone()[0]
            if used + len(packed) > self.limit:
                raise EvidenceMemoryError(
                    "Evidence storage budget exhausted; no previous knowledge deleted")
            self.db.execute(
                "INSERT INTO evidence(id,source_sha256,compressed,content_sha256,"
                "uncompressed_bytes,compressed_bytes) VALUES(?,?,?,?,?,?)",
                (identity, document["source_sha256"], packed, checksum,
                 len(raw), len(packed)))
            return {"id": identity, "deduplicated": False,
                    "compressed_bytes": len(packed)}

    def recall(self, identity):
        if (not isinstance(identity, str) or len(identity) != 64 or
                any(x not in "0123456789abcdef" for x in identity)):
            raise EvidenceMemoryError("Invalid evidence id")
        with self._lock:
            row = self.db.execute(
                "SELECT compressed,content_sha256,uncompressed_bytes "
                "FROM evidence WHERE id=?", (identity,)).fetchone()
        if row is None:
            return None
        try:
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(row[0], row[2]+1)
            if decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
                raise EvidenceMemoryError("Invalid compressed evidence envelope")
        except zlib.error as exc:
            raise EvidenceMemoryError("Compressed evidence corruption") from exc
        if (len(decoded) != row[2] or
                hashlib.sha256(decoded).hexdigest() != row[1]):
            raise EvidenceMemoryError("Evidence checksum failed")
        return json.loads(decoded)

    def recent(self, *, limit=10):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise EvidenceMemoryError("Bounded evidence lookup required")
        with self._lock:
            rows = self.db.execute(
                "SELECT id,source_sha256,uncompressed_bytes,compressed_bytes,"
                "created_utc FROM evidence ORDER BY created_utc DESC,id DESC LIMIT ?",
                (limit,)).fetchall()
        columns = ("id", "source_sha256", "uncompressed_bytes",
                   "compressed_bytes", "created_utc")
        return [dict(zip(columns, row)) for row in rows]

    def usage(self):
        with self._lock:
            used, count = self.db.execute(
                "SELECT COALESCE(SUM(compressed_bytes),0),COUNT(*) FROM evidence").fetchone()
        return {"records": count, "compressed_payload_bytes": used,
                "limit_bytes": self.limit, "free_payload_bytes": self.limit-used,
                "database_file_bytes": self.path.stat().st_size,
                "database_overhead_not_counted_in_payload_budget": True}
