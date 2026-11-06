"""Git-like, native-tool-agnostic heads for original editable plan documents.

The BODY already stores canonical immutable plans by SHA256. This ledger
selects which of those plans is current for a logical project/instrument input
without rewriting originals, discarding alternatives or turning a draft into
a claim that any native editor actually applied an edit.

Each authorized workspace keeps revision heads in its EXISTING production
SQLite database so a regular physically verified project archive carries
history alongside its immutable source documents. Real application edits,
native-save observation, rights and final outputs remain separate contracts.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import quote

from .durable_sqlite import connect_durable_database


_PROJECT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
_TOOL = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]{0,159}\Z")
_INPUT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,79}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class DocumentHeadConflict(ValueError):
    """A stale actor made no edit to the selected, immutable document head."""


class DocumentHeadCorrupt(ValueError):
    """Stored project-head metadata is inconsistent; reject rather than guess."""


def _name(value, pattern, kind):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError("Invalid " + kind)
    return value


def _digest(value, kind, *, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(kind + " needs exact SHA256 identity")
    return value


def _limit(value):
    if type(value) is not int or not (1 <= value <= 100):
        raise ValueError("Project revision inspection needs a bounded limit")
    return value


def _offset(value):
    if type(value) is not int or not (0 <= value <= 100_000):
        raise ValueError("Invalid or unbounded revision history page offset")
    return value


def _event_digest(project, tool, input_name, parent, previous_document, document):
    original = {
        "schema": "zx7-creative-document-head-v1",
        "project": project, "tool": tool, "input": input_name,
        "parent_revision": parent, "parent_document": previous_document,
        "document": document,
    }
    return hashlib.sha256(json.dumps(original, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


class DocumentHeadLedger:
    """Durable compare-and-swap of *plans*, never unobserved native app state.

    Caller is the trusted BodySignal host, which must first independently
    reread SHA-bound source bytes and validate that the installed BODY tool
    accepts that document. Raw owner media, paths and model prompts never
    enter this database table.
    """

    def __init__(self, workspace):
        workspace = Path(workspace)
        if workspace.is_symlink() or (workspace.exists() and not workspace.is_dir()):
            raise ValueError("Project revision workspace cannot be linked or non-directory")
        self.path = workspace / "production.sqlite3"
        if self.path.is_symlink():
            raise ValueError("Project revision database must not be a symlink")

    def _connect(self):
        if self.path.parent.is_symlink() or not self.path.parent.is_dir():
            raise ValueError("Cannot write project head into an absent or linked workspace")
        if self.path.is_symlink():
            raise ValueError("Project revision database cannot become a symlink")
        return connect_durable_database(self.path)

    def _read_connection(self):
        if self.path.is_symlink():
            raise ValueError("Project revision database cannot become a symlink")
        if not self.path.is_file():
            return None
        # Reads never create an empty production database or change the live
        # rendering journal mode. The writer uses the shared safe SQLite policy.
        database = sqlite3.connect(
            "file:" + quote(str(self.path.resolve())) + "?mode=ro",
            uri=True, timeout=10)
        database.execute("PRAGMA busy_timeout=10000")
        return database

    @staticmethod
    def _create_tables(db):
        db.execute("""CREATE TABLE IF NOT EXISTS creative_document_heads (
            project_id TEXT NOT NULL,
            tool_id TEXT NOT NULL,
            input_name TEXT NOT NULL,
            revision_id TEXT NOT NULL,
            document_sha256 TEXT NOT NULL,
            modified_ns INTEGER NOT NULL,
            PRIMARY KEY (project_id, tool_id, input_name)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS creative_document_revisions (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            tool_id TEXT NOT NULL,
            input_name TEXT NOT NULL,
            revision_id TEXT NOT NULL UNIQUE,
            parent_revision_id TEXT,
            parent_document_sha256 TEXT,
            document_sha256 TEXT NOT NULL,
            recorded_ns INTEGER NOT NULL
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS ix_creative_document_lineage
            ON creative_document_revisions(project_id,tool_id,input_name,sequence)""")

    @staticmethod
    def _verify_head(db, row, project, tool, input_name):
        if row is None:
            return None
        revision, document = row[0], row[1]
        recorded = db.execute("""SELECT parent_revision_id,
            parent_document_sha256,document_sha256
            FROM creative_document_revisions
            WHERE revision_id=? AND project_id=? AND tool_id=? AND input_name=?""",
            (revision,project,tool,input_name)).fetchone()
        if (recorded is None or recorded[2] != document
                or _event_digest(project,tool,input_name,recorded[0],
                                 recorded[1],recorded[2]) != revision):
            raise DocumentHeadCorrupt("Project head does not match immutable revision history")
        return {"revision_id":revision, "document_sha256":document}

    def select(self, *, project_id, tool_id, input_name, document_sha256,
               expected_revision_id, expected_document_sha256):
        """Atomically select a physically present, host-validated plan revision.

        A stale parent is a conflict even if the proposed plan bytes are valid.
        Selecting a historical document under today's expected parent is a
        NEW revision (undo); neither historical rows nor files are overwritten.
        """
        project = _name(project_id, _PROJECT, "project identity")
        tool = _name(tool_id, _TOOL, "installed tool identity")
        slot = _name(input_name, _INPUT, "document input identity")
        document = _digest(document_sha256, "Document")
        expected = _digest(expected_revision_id, "Expected revision", nullable=True)
        previous = _digest(expected_document_sha256, "Expected document", nullable=True)
        if (expected is None) != (previous is None):
            raise ValueError("Project head and base document must both be specified or both be null")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._create_tables(db)
                row = db.execute("""SELECT revision_id,document_sha256
                    FROM creative_document_heads
                    WHERE project_id=? AND tool_id=? AND input_name=?""",
                    (project,tool,slot)).fetchone()
                head = self._verify_head(db,row,project,tool,slot)
                if ((head["revision_id"] if head else None) != expected or
                    (head["document_sha256"] if head else None) != previous):
                    raise DocumentHeadConflict(
                        "Stale creative plan head; inspect and explicitly rebase or undo")
                if head and head["document_sha256"] == document:
                    raise DocumentHeadConflict("No changed creative document to select")
                revision = _event_digest(project,tool,slot,expected,previous,document)
                instant = time.time_ns()
                db.execute("""INSERT INTO creative_document_revisions
                    (project_id,tool_id,input_name,revision_id,parent_revision_id,
                    parent_document_sha256,document_sha256,recorded_ns)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (project,tool,slot,revision,expected,previous,document,instant))
                db.execute("""INSERT INTO creative_document_heads
                    (project_id,tool_id,input_name,revision_id,
                     document_sha256,modified_ns)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(project_id,tool_id,input_name)
                    DO UPDATE SET revision_id=excluded.revision_id,
                                  document_sha256=excluded.document_sha256,
                                  modified_ns=excluded.modified_ns""",
                    (project,tool,slot,revision,document,instant))
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return {
            "project_id":project,"tool_id":tool,"input_name":slot,
            "revision_id":revision,"parent_revision_id":expected,
            "document_sha256":document,
            "host_plan_head_selected":True,
            "native_project_state_applied_or_verified":False,
            "media_source_rights_independently_verified":False,
        }

    def heads(self, project_id, *, limit=50, offset=0):
        """One bounded page of all engine/input heads in this logical project."""
        project = _name(project_id, _PROJECT, "project identity")
        bounded = _limit(limit)
        start = _offset(offset)
        connection = self._read_connection()
        if connection is None:
            return {"project_id":project,"heads":[],"has_more":False,
                    "next_offset":None}
        with closing(connection) as db:
            if not db.execute("""SELECT 1 FROM sqlite_master WHERE type='table'
                                 AND name='creative_document_heads'""").fetchone():
                return {"project_id":project,"heads":[],"has_more":False,
                        "next_offset":None}
            rows = db.execute("""SELECT tool_id,input_name,revision_id,
                document_sha256 FROM creative_document_heads
                WHERE project_id=? ORDER BY tool_id,input_name LIMIT ? OFFSET ?""",
                (project,bounded+1,start)).fetchall()
            selected = rows[:bounded]
            result=[]
            for tool,slot,revision,document in selected:
                head=self._verify_head(db,(revision,document),project,tool,slot)
                result.append({"tool_id":tool,"input_name":slot,**head})
            more=len(rows)>bounded
            return {"project_id":project,"heads":result,
                    "has_more":more,
                    "next_offset":start+bounded if more else None,
                    "native_project_state_applied_or_verified":False}

    def history(self, *, project_id, tool_id, input_name,
                limit=32, offset=0):
        """Bounded newest-first immutable lineage for an instrument input."""
        project = _name(project_id, _PROJECT, "project identity")
        tool = _name(tool_id, _TOOL, "installed tool identity")
        slot = _name(input_name, _INPUT, "document input identity")
        bounded = _limit(limit)
        start = _offset(offset)
        connection = self._read_connection()
        if connection is None:
            return {"project_id":project,"tool_id":tool,"input_name":slot,
                    "revisions":[],"has_more":False,"next_offset":None}
        with closing(connection) as db:
            if not db.execute("""SELECT 1 FROM sqlite_master WHERE type='table'
                                 AND name='creative_document_revisions'""").fetchone():
                return {"project_id":project,"tool_id":tool,"input_name":slot,
                        "revisions":[],"has_more":False,"next_offset":None}
            rows = db.execute("""SELECT revision_id,parent_revision_id,
                parent_document_sha256,document_sha256
                FROM creative_document_revisions
                WHERE project_id=? AND tool_id=? AND input_name=?
                ORDER BY sequence DESC LIMIT ? OFFSET ?""",
                (project,tool,slot,bounded+1,start)).fetchall()
            result=[]
            for revision,parent,previous,document in rows[:bounded]:
                if _event_digest(project,tool,slot,parent,previous,document)!=revision:
                    raise DocumentHeadCorrupt("Historical creative revision lineage changed")
                result.append({"revision_id":revision,"parent_revision_id":parent,
                               "document_sha256":document})
            more=len(rows)>bounded
            return {"project_id":project,"tool_id":tool,"input_name":slot,
                    "revisions":result,"has_more":more,
                    "next_offset":start+bounded if more else None,
                    "native_project_state_applied_or_verified":False}
