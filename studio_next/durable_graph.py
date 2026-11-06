"""Crash-resilient, permissioned, provenance-bound execution of real film tool DAGs.

One film mind authors the DAG. Body tools are installed privileged adapters,
not JSON prompt templates or arbitrary model-supplied shell commands.

SQLite WAL stages survive process restart. A completed step may be reused only
after its digest, tool revision, original project/brief, upstream output and
actual media attestations all match. An incomplete NON-IDEMPOTENT operation is
never silently rerun; uncertain side effects require reconciliation.

This cannot guarantee permanent storage on ephemeral GitHub runners: the
SQLite database AND MediaVault must be mounted in persistent storage.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .contracts import _json_like
from .execution import _walk
from .film_ir import validate_film_ir
from .registry import ToolCatalog
from .stage_checkpoint import fingerprint
from .body_publication import physical_tool_attempt
from .durable_sqlite import connect_durable_database
from .body_dependency_scope import select_verified_node_assets


class RecoveryBlocked(RuntimeError):
    pass


def _wire(value):
    return json.dumps(value,allow_nan=False,ensure_ascii=False,
                      sort_keys=True,separators=(",",":"))


class DurableFilmGraph:
    def __init__(self,database,*,clock=None):
        self.path=Path(database)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.clock=clock or time.time
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS node_results(
                project_key TEXT NOT NULL,
                node_id TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                node_state TEXT NOT NULL,
                owner TEXT,
                lease_until REAL,
                output_json TEXT,
                output_sha256 TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL,
                PRIMARY KEY(project_key,node_id))""")

    def _connect(self):
        return connect_durable_database(self.path)

    def _transaction(self,callback):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                answer=callback(db)
                db.execute("COMMIT")
                return answer
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def start_or_reuse(self,project_key,node_id,input_sha,*,trusted_idempotent,
                       existing_result_verifier,lease_seconds):
        if not isinstance(existing_result_verifier,type(lambda:None)) and not callable(existing_result_verifier):
            raise ValueError("Body must check returned real outputs")
        owner=str(uuid.uuid4())
        now=self.clock()
        def operation(db):
            row=db.execute("""SELECT input_fingerprint,node_state,owner,lease_until,
                       output_json,output_sha256,attempts
                       FROM node_results WHERE project_key=? AND node_id=?""",
                       (project_key,node_id)).fetchone()
            prior_attempts=row[6] if row else 0
            if row and row[0]==input_sha and row[1]=="completed":
                answer=json.loads(row[4])
                if fingerprint(answer)!=row[5]:
                    raise RecoveryBlocked("Stored film tool output digest does not match")
                if existing_result_verifier(answer):
                    return "reused",answer,None
                # Completed physical artifact missing or changed: only an
                # idempotent tool may automatically try recreating it.
                if not trusted_idempotent:
                    raise RecoveryBlocked("Required original art disappeared; unsafe non-idempotent replay")
            if row and row[0]==input_sha and row[1]=="failed" and not trusted_idempotent:
                raise RecoveryBlocked("Non-idempotent failed operation may have created irreversible side effects")
            if row and row[0]==input_sha and row[1]=="running":
                if row[3] is None or row[3]>now:
                    raise RecoveryBlocked("Another worker holds the active scene lease")
                if not trusted_idempotent:
                    raise RecoveryBlocked("Uncertain prior side effect needs manual reconciliation")
            if row and row[0]!=input_sha and row[1]=="running" and (
                    row[3] is None or row[3]>now):
                raise RecoveryBlocked("Cannot change director source while tool worker is running")
            if row and row[0]!=input_sha and not trusted_idempotent:
                raise RecoveryBlocked("Changed original inputs would replay an irreversible operation")
            db.execute("""INSERT INTO node_results
                (project_key,node_id,input_fingerprint,node_state,
                 owner,lease_until,output_json,output_sha256,attempts,updated_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(project_key,node_id)
                 DO UPDATE SET input_fingerprint=excluded.input_fingerprint,
                    node_state='running',owner=excluded.owner,
                    lease_until=excluded.lease_until,output_json=NULL,
                    output_sha256=NULL,attempts=excluded.attempts,
                    updated_at=excluded.updated_at""",
                (project_key,node_id,input_sha,"running",
                 owner,now+lease_seconds,None,None,prior_attempts+1,now))
            return "execute",None,owner
        return self._transaction(operation)

    def renew_running_lease(self,project_key,node_id,input_sha,owner,lease_seconds):
        """Extend a lease ONLY for its exact live owner; never steal another stage.

        The trusted BODY worker supplies this heartbeat, not the artistic
        model. Returns false after completion, failure or ownership loss.
        """
        import math
        if not isinstance(lease_seconds,(int,float)) or isinstance(lease_seconds,bool) or (
                not math.isfinite(lease_seconds) or lease_seconds<=0):
            raise ValueError("Finite positive original renderer lease needed")
        now=self.clock()
        def operation(db):
            cursor=db.execute("""UPDATE node_results SET lease_until=?,updated_at=?
                WHERE project_key=? AND node_id=? AND input_fingerprint=?
                  AND owner=? AND node_state='running'""",
                (now+lease_seconds,now,project_key,node_id,input_sha,owner))
            return cursor.rowcount==1
        return self._transaction(operation)

    @contextmanager
    def publication_lease(self, project_key, node_id, input_sha, owner, *,
                          lease_seconds):
        """Fence original media publication against replaced/expired workers.

        Hold a short SQLite write transaction *only* across receipt creation,
        hardlink and directory fsync, never while rendering or decoding large
        media. An expired worker cannot publish after another worker acquires
        the same durable scene. The transaction also prevents ownership from
        changing between verification and the filesystem side effect.
        """
        import math
        if (not isinstance(lease_seconds, (int,float)) or
                isinstance(lease_seconds, bool) or
                not math.isfinite(lease_seconds) or lease_seconds<=0):
            raise ValueError("Finite positive publication lease renewal required")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row=db.execute("""SELECT node_state,owner,lease_until
                    FROM node_results WHERE project_key=? AND node_id=?
                      AND input_fingerprint=?""",
                    (project_key,node_id,input_sha)).fetchone()
                if (row is None or row[0]!="running" or row[1]!=owner
                        or row[2] is None or row[2]<=self.clock()):
                    raise RecoveryBlocked(
                        "Original publication blocked: worker no longer owns the live lease")
                yield
                # A large original can take longer than a normal heartbeat
                # while its final receipt/bytes are synced. The same SQLite
                # writer transaction prevents takeover during this period.
                # Freshly arm the lease before releasing the transaction.
                now=self.clock()
                changed=db.execute("""UPDATE node_results SET lease_until=?,updated_at=?
                    WHERE project_key=? AND node_id=? AND input_fingerprint=?
                      AND owner=? AND node_state='running'""",
                    (now+lease_seconds,now,project_key,node_id,input_sha,owner))
                if changed.rowcount!=1:
                    raise RecoveryBlocked(
                        "Original publication lost owner before final commit")
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def complete(self,project_key,node_id,input_sha,owner,result):
        serial=_wire(result)
        digest=fingerprint(result)
        def operation(db):
            cursor=db.execute("""UPDATE node_results SET node_state='completed',
                owner=NULL,lease_until=NULL,output_json=?,
                output_sha256=?,updated_at=?
                WHERE project_key=? AND node_id=? AND input_fingerprint=?
                AND node_state='running' AND owner=?""",
                (serial,digest,self.clock(),project_key,node_id,input_sha,owner))
            if cursor.rowcount!=1:
                raise RecoveryBlocked("Tool lease was lost; cannot declare this media committed")
        self._transaction(operation)
        return digest

    def failed(self,project_key,node_id,input_sha,owner):
        def operation(db):
            db.execute("""UPDATE node_results SET node_state='failed',
                lease_until=NULL,owner=NULL,updated_at=?
                WHERE project_key=? AND node_id=? AND input_fingerprint=?
                AND node_state='running' AND owner=?""",
                (self.clock(),project_key,node_id,input_sha,owner))
        self._transaction(operation)

    def inspect(self,project_key):
        with self._connect() as db:
            rows=db.execute("""SELECT node_id,node_state,attempts,output_sha256
                FROM node_results WHERE project_key=? ORDER BY node_id""",
                (project_key,)).fetchall()
        return [{"node_id":a,"status":b,"attempts":c,"output_sha256":d}
                for a,b,c,d in rows]


def durable_project_key(ir, *, fact_ids, allowed_access):
    """Derive the exact graph namespace from host-approved facts and access.

    Same film revisions may share a cache; unrelated films must never appear
    as a single job's execution progress merely because they share a folder.
    No media is executed or approved by calculating this identifier.
    """
    if not isinstance(ir,dict) or not isinstance(ir.get("project"),dict):
        raise ValueError("A real immutable creative project is required")
    rights=set(fact_ids)
    permitted=frozenset(allowed_access)
    if not permitted.issubset({"read","write","network","paid"}):
        raise ValueError("Invalid production access scope")
    return fingerprint({"creative_project":ir["project"],
        "fact_ids":sorted(rights),"owner_facts":ir.get("owner_facts",{}),
        "permission":sorted(permitted),"durable_schema":2})


def execute_durable_film_graph(ir,catalog,*,fact_ids,store,
                                trusted_idempotent_tools=frozenset(),
                                output_verifier=None,tool_revisions=None,
                                input_material_fingerprint=None,
                                boundary_control=None,
                                allowed_access=frozenset({"read","write"}),
                                lease_seconds=3600,step_budget=10000):
    """Resume any genre/media/scene-count by actual graph, with per-step custody.

    `output_verifier(tool_id,result)` MUST inspect real output files/vault
    references, not just result JSON schema. False means no usable artifact.
    """
    if not isinstance(catalog,ToolCatalog) or not isinstance(store,DurableFilmGraph):
        raise TypeError("Trusted installed ToolCatalog and durable SQLite runtime required")
    if not callable(output_verifier):
        raise ValueError("Production runtime needs physical output provenance verifier")
    if input_material_fingerprint is not None and not callable(input_material_fingerprint):
        raise ValueError("Source media fingerprint must come from trusted body code")
    if boundary_control is not None and not callable(boundary_control):
        raise ValueError("Only trusted operator control may stop production")
    import math
    if not isinstance(lease_seconds,(int,float)) or isinstance(lease_seconds,bool) or (
            not math.isfinite(lease_seconds) or lease_seconds<=0):
        raise ValueError("Finite positive safe worker lease required")
    if type(step_budget) is not int or step_budget<1:
        raise ValueError("Finite approved compute budget required")
    tool_revisions=tool_revisions or {}
    if not isinstance(tool_revisions,dict):
        raise ValueError("Trusted tool versions required")
    rights=set(fact_ids)
    permission=frozenset(allowed_access)
    if not permission.issubset({"read","write","network","paid"}):
        raise ValueError("Invalid production access scope")
    validation=validate_film_ir(ir,installed_tool_ids=catalog.executable_ids(permission),
                                fact_ids=rights)
    if not validation.render_ready:
        return {"status":"blocked","errors":validation.errors+validation.warnings,
                "completed":[],"reused":[],"video_proven":False}
    if len(validation.order)>step_budget:
        return {"status":"blocked","errors":["Trusted execution budget exceeded"],
                "completed":[],"reused":[],"video_proven":False}
    nodes={n["id"]:n for n in ir["tool_graph"]}
    # Check all references before any writes.
    for node in nodes.values():
        _walk(_json_like(node["inputs"]),set(node.get("depends_on",[])))
    # Stable project identity permits *unchanged* shots to be resumed after
    # the artist revises an unrelated shot. Every node still authenticates
    # its own art, inputs, media assets, installed tool and upstream lineage.
    project_key=durable_project_key(ir,fact_ids=rights,allowed_access=permission)
    outputs={}
    complete=[];reused=[];errors=[];trace=[]
    for node_id in validation.order:
        control=boundary_control() if boundary_control is not None else None
        if control not in (None,"pause","cancel"):
            raise ValueError("Invalid operator production control")
        if control is not None:
            return {"status":"paused" if control=="pause" else "cancelled",
                    "project_key":project_key,"completed":complete,"reused":reused,
                    "trace":trace,"errors":[],"video_proven":False,
                    "stopped_at_verified_tool_boundary":True,
                    "next_node":node_id}
        node=nodes[node_id]
        tid=node["tool_id"]
        can_retry=tid in trusted_idempotent_tools
        inputs=_walk(_json_like(node["inputs"]),set(node.get("depends_on",[])),
                     resolve=outputs)
        tool_version=tool_revisions.get(tid)
        if not isinstance(tool_version,str) or not tool_version.strip():
            errors.append("Missing installed tool revision for "+tid)
            break
        related=set(node.get("shot_refs",[]))
        # Unspecified shot dependencies default conservatively to the whole
        # movie; no invented assumed independence between shots.
        relevant_shots=[shot for shot in ir["shots"]
                        if not related or shot["id"] in related]
        try:
            relevant_assets=select_verified_node_assets(
                ir.get("assets",[]),node,relevant_shots)
            materials=(input_material_fingerprint(tid,inputs)
                       if input_material_fingerprint is not None else None)
            input_key=fingerprint({"tool_id":tid,"version":tool_version,
                "artistic_tool_node":node,"original_shots":relevant_shots,
                "verified_assets":relevant_assets,
                "actual_material_sha":materials,
                "args":inputs,"dependencies":{
                    dep:fingerprint(outputs[dep]) for dep in node.get("depends_on",[])}})
        except (ValueError,TypeError,OSError,OverflowError) as exc:
            errors.append("Cannot fingerprint actual film source: "+str(exc))
            break
        try:
            action,cached,owner=store.start_or_reuse(project_key,node_id,input_key,
                 trusted_idempotent=can_retry,
                 existing_result_verifier=lambda result:output_verifier(tid,result),
                 lease_seconds=lease_seconds)
            if action=="reused":
                out=cached
                reused.append(node_id)
            else:
                from .body_stage_lease import RunningStageHeartbeat
                heart=RunningStageHeartbeat(
                    store,project_key,node_id,input_key,owner,
                    lease_seconds=lease_seconds)
                try:
                    heart.start()
                    with physical_tool_attempt(
                            project_key,node_id,input_key,tid,
                            publication_guard=heart.publication_guard):
                        out=catalog.invoke(tid,inputs,allowed_access=permission)
                    if not output_verifier(tid,out):
                        raise ValueError("Tool provided no physically verified asset")
                    # The physical original media may have changed while a
                    # long-running encoder was working. Provenance is binding
                    # only if SAME BYTES still exist at commit time.
                    if input_material_fingerprint is not None:
                        after_materials=input_material_fingerprint(tid,inputs)
                        if after_materials!=materials:
                            raise RecoveryBlocked(
                                "Original source changed during physical render; cannot certify stale input")
                    # The heartbeat is stopped before committing, so it can
                    # never race a completed node and claim lease loss.
                    heart.stop()
                    store.complete(project_key,node_id,input_key,owner,out)
                except BaseException:
                    heart.abort()
                    store.failed(project_key,node_id,input_key,owner)
                    raise
            outputs[node_id]=out
            complete.append(node_id)
            trace.append({"node":node_id,"tool":tid,"state":action,
                "output_sha256":fingerprint(out)})
        except Exception as error:
            errors.append("Production step "+node_id+": "+
                          type(error).__name__+": "+str(error))
            break
    return {"status":"all_tool_results_verified" if not errors else
                    ("failed_partial" if complete else "blocked"),
            "project_key":project_key,"completed":complete,"reused":reused,
            "trace":trace,"errors":errors,
            "video_proven":False,
            "disclaimer":"This is tool graph custody. Actual final MP4 + audio + creative approval need independent checks."}
