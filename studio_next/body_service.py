"""Independent local authenticated production-body service.

Run real locally installed creative tools WITHOUT ChatGPT supervision.
POST a model/artist-authored original Film IR, obtain an ID, poll status,
and restart interrupted jobs from the same SQLite + MediaVault stages.

This is a loopback-only trusted host API, never a public internet deployment.
No paid calls, software installs, shell commands, image/style templates or
infinite hidden background jobs. Real media is created only by registered tools.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import concurrent.futures
import fcntl
import hmac
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,unquote,parse_qs

from .body_capabilities import operational_tool_summary,explain_operational_tool
from .body_affordances import BodyAffordanceSurface
from .body_sensory import sense_body_job
from .body_integration import body_catalog
from .body_integration import run_body_project
from .media_vault import MediaVault,sha256_file,verify_media_container
from .body_archive import create_body_archive
from .durable_sqlite import connect_durable_database
from .body_mobile import ASSETS as MOBILE_ASSETS, CSP as MOBILE_CSP
from .body_download_tickets import DownloadTickets
from .body_verified_delivery import verified_artifact_snapshot
from .body_host_resources import inspect_host_resources
from .body_revision_impact import plan_film_revision_impact
from .durable_graph import durable_project_key

_ID=re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_MAX_JOB_BODY=4*1024*1024
_MAX_OWNER_FILE=1024*1024*1024
_MEDIA_NAME=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,179}$")
_MEDIA_MIME={".mp4":"video/mp4",".mov":"video/quicktime",
             ".webm":"video/webm",".png":"image/png",".jpeg":"image/jpeg",
             ".jpg":"image/jpeg",".webp":"image/webp",".svg":"image/svg+xml",
             ".wav":"audio/wav",".mp3":"audio/mpeg",".flac":"audio/flac",
             ".glb":"model/gltf-binary",".bin":"application/octet-stream"}


class LocalBodyCoordinator:
    def __init__(self,root,*,execute=None,workers=1,upload_timeout_seconds=30,
                 creative_model=None):
        if type(workers) is not int or not (1<=workers<=16):
            raise ValueError("Operator must choose finite host workload capacity")
        if (type(upload_timeout_seconds) not in (int,float) or
                not 1<=upload_timeout_seconds<=600):
            raise ValueError("Owner uploads require a bounded transfer deadline")
        if Path(root).is_symlink():
            raise ValueError("Studio host root cannot be a filesystem link")
        self.root=Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        for name in ("body-service.lock","body-jobs.sqlite3","projects"):
            if (self.root/name).is_symlink():
                raise ValueError("Studio host state cannot be a filesystem link")
        # An OS process lock is released on crash, unlike a stale Python flag.
        # Two independent services must NEVER drive the same renderer DB,
        # originals and partially produced frames concurrently.
        lock_fd=os.open(self.root/"body-service.lock",
                        os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
        self._instance_lock=os.fdopen(lock_fd,"a+")
        try:
            fcntl.flock(self._instance_lock.fileno(),
                        fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._instance_lock.close()
            raise RuntimeError("Original production workspace is already owned by another running body service") from exc
        self.projects=self.root/"projects"
        if self.projects.is_symlink():
            raise ValueError("Studio projects root cannot be linked to another owner")
        self.projects.mkdir(exist_ok=True)
        self.database=self.root/"body-jobs.sqlite3"
        self.executor=concurrent.futures.ThreadPoolExecutor(
            max_workers=workers,thread_name_prefix="zx7-original-body")
        self._queued=set()
        self._lock=threading.RLock()
        self._maintenance_lock=threading.RLock()
        self._active_uploads=set()
        self._reserved_upload_bytes=0
        self.upload_timeout_seconds=upload_timeout_seconds
        self._workspace_locks={}
        self.execute=execute or run_body_project
        self._uses_native_executor=execute is None
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,
                original_ir TEXT NOT NULL,status TEXT NOT NULL,
                attempts INTEGER NOT NULL, result TEXT,
                modified REAL NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS job_controls(
                job_id TEXT PRIMARY KEY, requested_action TEXT NOT NULL,
                requested_at REAL NOT NULL)""")
        # We already own the exclusive OS workspace lock, and no new worker
        # has been scheduled. A machine/process crash leaves a previously
        # running graph lease in the future; expire only those orphaned leases
        # so deterministic host-approved tools can actually resume NOW.
        # Non-idempotent operations still require manual reconciliation.
        self._reconcile_orphaned_work_on_exclusive_startup()
        self.creative_sessions=None
        if creative_model is not None:
            from .body_creative_session import CreativeSessions
            self.creative_sessions=CreativeSessions(self,creative_model)

    def _connect(self):
        if self.database.is_symlink():
            raise ValueError("Original host production database was replaced by a link")
        return connect_durable_database(self.database)

    def _reconcile_orphaned_work_on_exclusive_startup(self):
        """Release abandoned scene leases ONLY after exclusive service startup.

        SQLite's original node state and input fingerprint remain unchanged.
        The durable graph still refuses to rerun non-idempotent operations,
        even after the old lease is marked expired.
        """
        with self._connect() as db:
            unfinished=db.execute(
                "SELECT DISTINCT workspace_id FROM jobs WHERE status IN ('queued','running')"
            ).fetchall()
        for (workspace_id,) in unfinished:
            workspace=self._workspace(workspace_id)
            database=workspace/"production.sqlite3"
            if not database.is_file():
                continue
            with connect_durable_database(database) as stages:
                existing=stages.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='node_results'"
                ).fetchone()
                if not existing:
                    continue
                stages.execute(
                    "UPDATE node_results SET lease_until=0 "
                    "WHERE node_state='running' AND (lease_until IS NULL OR lease_until>0)"
                )

    def _workspace(self,identity):
        if not isinstance(identity,str) or not _ID.fullmatch(identity):
            raise ValueError("Unsafe original project/workspace identity")
        requested=self.projects/identity
        if requested.is_symlink():
            raise ValueError("One owner workspace cannot alias another")
        place=requested.resolve()
        if not place.is_relative_to(self.projects) or place.name!=identity:
            raise ValueError("Original project cannot escape studio folder")
        return place

    def upload_owner_media(self,workspace_id,filename,stream,bytes_expected,*,
                           mime,source_id,rights_evidence):
        """Owner-authenticated real bytes, never a model-created rights label.

        The file becomes visible only after full byte transfer and real
        decoder/provenance verification. No overwrite and no URL fetching.
        """
        if not isinstance(filename,str) or not _MEDIA_NAME.fullmatch(filename):
            raise ValueError("Invalid media asset file identity")
        if _MEDIA_MIME.get(Path(filename).suffix.lower())!=mime:
            raise ValueError("Media extension does not match declared source type")
        if type(bytes_expected) is not int or not (0<bytes_expected<=_MAX_OWNER_FILE):
            raise ValueError("Upload size exceeds operator-approved local resource budget")
        if not isinstance(source_id,str) or not source_id.strip() or (
                not isinstance(rights_evidence,str) or not rights_evidence.strip()):
            raise ValueError("Owner must explicitly attest the original media source")
        with self._maintenance_lock:
            folder=self._workspace(workspace_id)
            folder.mkdir(parents=True,exist_ok=True)
            final=folder/filename
            if final.exists():
                raise FileExistsError("Original imported media is immutable; never overwrite")
            stage=folder/(".zx7-import-"+uuid.uuid4().hex+".tmp")
            # Reserve enough space for the staging file and immutable CAS copy.
            reservation=2*bytes_expected
            if shutil.disk_usage(folder).free < self._reserved_upload_bytes+reservation:
                raise ValueError("Insufficient unreserved disk space for owner upload")
            self._reserved_upload_bytes+=reservation
            self._active_uploads.add(stage)
        # Stream and decode outside the global admission/snapshot lock. An
        # in-flight reservation explicitly prevents an inconsistent snapshot.
        deadline=time.monotonic()+self.upload_timeout_seconds
        try:
            with stage.open("xb") as dest:
                remaining=bytes_expected
                reader=getattr(stream,"read1",stream.read)
                while remaining:
                    if time.monotonic()>=deadline:
                        raise TimeoutError("Owner upload exceeded transfer deadline")
                    limit=min(1024*1024,remaining)
                    chunk=reader(limit)
                    if time.monotonic()>=deadline:
                        raise TimeoutError("Owner upload exceeded transfer deadline")
                    if not isinstance(chunk,(bytes,bytearray)) or not 0<len(chunk)<=limit:
                        raise ValueError("Owner upload ended before declared physical bytes")
                    dest.write(chunk)
                    remaining-=len(chunk)
                dest.flush()
                os.fsync(dest.fileno())
            vault=MediaVault(folder/"vault")
            attested=vault.ingest(stage,mime=mime,rights="owner_supplied",
                source_type="owner_upload",source_id=source_id,
                evidence=rights_evidence,owner_or_generator="authenticated_local_owner")
            os.link(stage,final)
            return {"source":filename,"asset_id":attested["asset_id"],
                    "attestation_id":attested["attestation_id"],
                    "mime":mime,"bytes":bytes_expected,
                    "verified_real_media_bytes":True,
                    "rights_claim":"Owner-attested; no independent legal ownership certification"}
        finally:
            try:stage.unlink(missing_ok=True)
            finally:
                with self._maintenance_lock:
                    self._active_uploads.discard(stage)
                    self._reserved_upload_bytes-=reservation

    def submit(self,film_ir,*,workspace_id,job_id=None):
        if not isinstance(film_ir,dict) or not isinstance(film_ir.get("tool_graph"),list):
            raise ValueError("Original creative Film IR and actual tool graph required")
        root=self._workspace(workspace_id)
        root.mkdir(parents=True,exist_ok=True)
        identifier=job_id or uuid.uuid4().hex
        if not _ID.fullmatch(identifier):
            raise ValueError("Invalid production job identity")
        encoded=json.dumps(film_ir,allow_nan=False,ensure_ascii=False)
        with self._maintenance_lock:
            with self._connect() as db:
                try:
                    db.execute("""INSERT INTO jobs VALUES(?,?,?,?,?,?,?)""",
                        (identifier,workspace_id,encoded,"queued",0,None,time.time()))
                except sqlite3.IntegrityError as exc:
                    raise ValueError("Original creative job ID already exists; never overwrite") from exc
            self.queue(identifier)
        return {"job_id":identifier,"workspace_id":workspace_id,"status":"queued",
                "original_artistic_plan_preserved":True}

    def queue(self,identity):
        if not isinstance(identity,str) or not _ID.fullmatch(identity):
            raise ValueError("Invalid job identity")
        with self._maintenance_lock:
            with self._lock:
                if identity in self._queued:
                    return False
                with self._connect() as db:
                    found=db.execute("SELECT status FROM jobs WHERE id=?",(identity,)).fetchone()
                if found is None:
                    raise ValueError("Unknown submitted project")
                if found[0] not in ("queued","running"):
                    return False
                self._queued.add(identity)
                try:
                    self.executor.submit(self._work,identity)
                except BaseException:
                    self._queued.discard(identity)
                    raise
                return True

    def create_recovery_snapshot(self, archive_path):
        """Quiescent, WAL-consistent snapshot of jobs + every film workspace.

        Backup is allowed ONLY with no executing jobs or owner uploads.
        A trusted external operator must retain the digest for restore.
        """
        with self._maintenance_lock:
            with self._lock:
                if self._active_uploads:
                    raise RuntimeError("Cannot snapshot partially uploaded owner artwork")
                if self._queued:
                    raise RuntimeError("Cannot snapshot studio with active render jobs")
                with self._connect() as db:
                    active=db.execute(
                        "SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')"
                    ).fetchone()[0]
                    if self.creative_sessions is not None:
                        sessions=db.execute("SELECT state FROM creative_sessions").fetchall()
                        if any(json.loads(raw)["status"] in ("queued","running") for (raw,) in sessions):
                            raise RuntimeError("Cannot snapshot an active creative session")
                if active:
                    raise RuntimeError("Cannot snapshot incomplete running original cinema")
                if next(self.projects.rglob(".zx7-import-*.tmp"),None) is not None:
                    raise RuntimeError("Cannot snapshot partially uploaded owner artwork")
                return create_body_archive(self.root,archive_path)

    def _work(self,identity):
        try:
            with self._connect() as db:
                # Jobs already have a bounded single executor owner locally.
                db.execute("""UPDATE jobs SET status='running',attempts=attempts+1,
                           modified=? WHERE id=?""",(time.time(),identity))
                row=db.execute("SELECT workspace_id,original_ir FROM jobs WHERE id=?",
                               (identity,)).fetchone()
            if row is None:raise ValueError("Submitted original film vanished")
            location=self._workspace(row[0])
            original=json.loads(row[1])
            # Distinct original projects may render concurrently. Multiple
            # jobs of ONE workspace may not mutate the same accepted files,
            # SQLite stage leases or original sound resources simultaneously.
            with self._lock:
                project_lock=self._workspace_locks.setdefault(row[0],threading.Lock())
            with project_lock:
                # Execution itself uses the crash-safe graph/physical witness vault.
                control=self._requested_control(identity)
                if control is not None:
                    result={"status":"paused" if control=="pause" else "cancelled",
                            "completed":[],"reused":[],"errors":[],
                            "stopped_at_verified_tool_boundary":True}
                elif self._uses_native_executor:
                    result=self.execute(original,location,
                        boundary_control=lambda:self._requested_control(identity))
                else:
                    result=self.execute(original,location)
            if not isinstance(result,dict):
                raise RuntimeError("Original film tool graph produced no audit result")
            ok=result.get("status")=="all_tool_results_verified"
            status=("completed" if ok else result["status"] if
                    result.get("status") in ("paused","cancelled") else "blocked")
            report=result
        except BaseException as exc:
            status="failed"
            report={"status":"failed","message":type(exc).__name__+": "+str(exc),
                    "movie_delivered":False}
        finally:
            with self._connect() as db:
                db.execute("""UPDATE jobs SET status=?,result=?,modified=? WHERE id=?""",
                    (status,json.dumps(report,allow_nan=False,ensure_ascii=False),
                     time.time(),identity))
                if status not in ("paused","cancelled"):
                    db.execute("DELETE FROM job_controls WHERE job_id=?",(identity,))
            with self._lock:
                self._queued.discard(identity)

    def inspect_media(self,identity,relative):
        """Authorized real output file from one job's original workspace."""
        summary=self.inspect(identity)
        if not isinstance(relative,str) or not relative or Path(relative).is_absolute():
            raise ValueError("Media path must be a project-relative artifact")
        asset=Path(relative)
        if any(p.startswith(".") for p in asset.parts) or "\\" in relative:
            raise ValueError("Unsafe film output media path")
        root=self._workspace(summary["workspace_id"])
        path=(root/asset).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("No physical film output at requested path")
        mime=_MEDIA_MIME.get(path.suffix.lower())
        if mime is None:
            raise ValueError("Unregistered media cannot be exposed via original film API")
        # This verifier decodes actual image/audio formats and inspects movie
        # streams; arbitrary JSON, private databases and credentials are never
        # streamed as a movie.
        verify_media_container(path,mime)
        return {"path":path,"mime":mime,"sha256":sha256_file(path),
                "bytes":path.stat().st_size}

    def list_media(self,identity):
        summary=self.inspect(identity)
        root=self._workspace(summary["workspace_id"])
        items=[]
        for path in sorted(root.rglob("*")):
            if any(part.startswith(".") for part in path.relative_to(root).parts):
                continue
            if path.is_symlink():
                raise ValueError("Untrusted linked project artifact")
            if not path.is_file() or path.suffix.lower() not in _MEDIA_MIME:
                continue
            items.append({"path":str(path.relative_to(root)),
                          "bytes":path.stat().st_size,
                          "sha256":sha256_file(path),
                          "physically_encoded_quality_certified":False})
        return {"job_id":identity,"assets":items}

    def _stage_progress(self,workspace_id,*,project_key=None,node_ids=()):
        """Read only this actual creative project lineage's persisted stages.

        Stage caches are shared across revisions of the SAME creative project:
        they are NOT individual job attempts or approved movie evidence.
        """
        empty={"observed_tool_states":[],
               "tool_progress_is_actual_sqlite":False,
               "stage_scope":"no_verified_project_lineage"}
        if not isinstance(project_key,str) or not re.fullmatch(r"[a-f0-9]{64}",project_key):
            return empty
        if not isinstance(node_ids,(set,list,tuple,frozenset)) or not all(
                isinstance(n,str) for n in node_ids):
            return empty
        approved=set(node_ids)
        if not approved:
            return {**empty,"stage_scope":"film_lineage_with_no_stage_nodes"}
        location=self._workspace(workspace_id)
        path=location/"production.sqlite3"
        if not path.is_file():
            return empty
        try:
            with sqlite3.connect(f"file:{path}?mode=ro",uri=True,timeout=4) as db:
                tables=db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if ("node_results",) not in tables:
                    return empty
                rows=db.execute("""SELECT node_id,node_state,attempts,updated_at
                    FROM node_results WHERE project_key=?
                    ORDER BY updated_at DESC LIMIT 500""",(project_key,)).fetchall()
            return {"observed_tool_states":[
                {"node_id":a,"state":b,"attempts":c,"updated_at":d}
                for a,b,c,d in rows if a in approved],
                "tool_progress_is_actual_sqlite":True,
                "stage_scope":"verified_shared_project_lineage_not_single_job_attempt"}
        except (sqlite3.Error,ValueError,OSError):
            return empty

    def host_resource_status(self):
        """Only live technical capacity, never unverified AI model execution."""
        return inspect_host_resources(self.root)

    def list_jobs(self,*,limit=100):
        """Bounded honest job statuses for a standalone creative desktop client."""
        if type(limit) is not int or not (1<=limit<=100):
            raise ValueError("Body job listing must be explicitly bounded")
        with self._connect() as db:
            rows=db.execute("""SELECT id,workspace_id,status,attempts,modified
                FROM jobs ORDER BY modified DESC,id DESC LIMIT ?""",(limit,)).fetchall()
        return {"jobs":[{"job_id":a,"workspace_id":b,"status":c,
                         "attempts":d,"updated_at":e} for a,b,c,d,e in rows],
                "status_is_physical_execution_evidence":True,
                "successful_jobs_do_not_automatically_prove_a_movie_exists":True}

    def _requested_control(self,identity):
        with self._connect() as db:
            row=db.execute("SELECT requested_action FROM job_controls WHERE job_id=?",
                           (identity,)).fetchone()
        return row[0] if row else None

    def request_control(self,identity,action):
        """Persist a safe boundary stop; never kill an encoder mid-file."""
        if (not isinstance(identity,str) or not _ID.fullmatch(identity) or
                action not in ("pause","cancel")):
            raise ValueError("A known job and explicit pause/cancel are required")
        with self._maintenance_lock:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row=db.execute("SELECT status FROM jobs WHERE id=?",(identity,)).fetchone()
                if row is None or row[0] not in ("queued","running"):
                    db.execute("ROLLBACK")
                    raise ValueError("Only active or queued production can be stopped")
                prior=db.execute("SELECT requested_action FROM job_controls WHERE job_id=?",
                                 (identity,)).fetchone()
                if prior and prior[0]=="cancel" and action=="pause":
                    db.execute("ROLLBACK")
                    raise ValueError("Cancellation cannot be silently downgraded")
                db.execute("INSERT INTO job_controls VALUES(?,?,?) "
                           "ON CONFLICT(job_id) DO UPDATE SET "
                           "requested_action=excluded.requested_action,requested_at=excluded.requested_at",
                           (identity,action,time.time()))
                db.execute("COMMIT")
        return {"job_id":identity,"requested_action":action,
                "current_tool_finishes_before_stop":True,
                "original_film_ir_unchanged":True}

    def retry_job(self,identity,*,resume=False):
        """Operator-authorized reuse of the same original immutable Film IR.

        Refuse active/completed jobs; re-rendering is never a hidden side effect
        of inspecting status. Durable graph verifies each unchanged asset.
        """
        if not isinstance(identity,str) or not _ID.fullmatch(identity):
            raise ValueError("Invalid original job identity")
        with self._maintenance_lock:
            with self._lock:
                if identity in self._queued:
                    raise ValueError("Original film is already scheduled")
                with self._connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    row=db.execute("SELECT status FROM jobs WHERE id=?",
                                   (identity,)).fetchone()
                    if row is None:
                        db.execute("ROLLBACK")
                        raise ValueError("Unknown original body job")
                    accepted=("paused",) if resume else ("blocked","failed","cancelled")
                    if row[0] not in accepted:
                        db.execute("ROLLBACK")
                        raise ValueError("Only stopped or blocked original work can be retried")
                    db.execute("""UPDATE jobs SET status='queued',result=NULL,
                               modified=? WHERE id=?""",(time.time(),identity))
                    db.execute("DELETE FROM job_controls WHERE job_id=?",(identity,))
                    db.execute("COMMIT")
                scheduled=self.queue(identity)
                if not scheduled:
                    raise RuntimeError("Original job could not be safely rescheduled")
        return {"job_id":identity,"status":"queued",
                "original_film_ir_unchanged":True,"operator_explicit_retry":True}

    def inspect(self,identity):
        if not isinstance(identity,str) or not _ID.fullmatch(identity):
            raise ValueError("Invalid original job identity")
        with self._connect() as db:
            row=db.execute("""SELECT workspace_id,status,attempts,result,modified,
                       original_ir FROM jobs WHERE id=?""",(identity,)).fetchone()
        if row is None:raise ValueError("Unknown job")
        result=json.loads(row[3]) if row[3] else None
        original=json.loads(row[5])
        nodes=original.get("tool_graph",[]) if isinstance(original,dict) else []
        node_ids={n["id"] for n in nodes if isinstance(n,dict)
                  and isinstance(n.get("id"),str)}
        # Persisted finished reports must match THIS job's original project.
        # A queued job can never claim previous or another worker's progress.
        project_key=None
        if row[1]!="queued" and isinstance(original,dict):
            try:
                expected=durable_project_key(original,
                    fact_ids=set(original.get("owner_facts",{})),
                    allowed_access=frozenset({"read","write"}))
            except (TypeError,ValueError):
                expected=None
            if expected is not None and (row[1]=="running" or (
                    isinstance(result,dict) and result.get("project_key")==expected)):
                project_key=expected
        return {"job_id":identity,"workspace_id":row[0],"status":row[1],
                "attempts":row[2],"result":result,
                "updated_at":row[4],
                "requested_action":self._requested_control(identity),
                "actual_tool_progress":self._stage_progress(row[0],
                     project_key=project_key,node_ids=node_ids)}

    def pending_restart(self):
        with self._connect() as db:
            ids=[x[0] for x in db.execute(
                "SELECT id FROM jobs WHERE status IN ('queued','running')")]
        for identity in ids:
            self.queue(identity)
        if self.creative_sessions is not None:
            self.creative_sessions.resume_pending()
        return len(ids)

    def close(self):
        if self.creative_sessions is not None:
            self.creative_sessions.close()
        self.executor.shutdown(wait=True)
        fcntl.flock(self._instance_lock.fileno(),fcntl.LOCK_UN)
        self._instance_lock.close()


def make_body_http_handler(coordinator,token):
    delivery_tickets=DownloadTickets()
    if not isinstance(token,str) or len(token)<32:
        raise ValueError("Local creative body API needs secret >=32 characters")
    def _utf8_media_header(headers,raw_name,encoded_name):
        encoded=headers.get(encoded_name)
        if encoded:
            if len(encoded)>12000:
                raise ValueError("Original rights/source evidence exceeds local header budget")
            try:
                return base64.b64decode(encoded,validate=True).decode("utf-8")
            except (binascii.Error,UnicodeError) as exc:
                raise ValueError("Original media source/rights header has invalid UTF-8") from exc
        return headers.get(raw_name,"")

    class Handler(BaseHTTPRequestHandler):
        server_version="ZX7Body/1"
        def log_message(self,format,*args):
            pass
        def _reply(self,code,payload):
            binary=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(binary)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(binary)
        def _authorized(self):
            actual=self.headers.get("Authorization","")
            if not hmac.compare_digest(actual,"Bearer "+token):
                self._reply(401,{"error":"Local production service requires host authorization"})
                return False
            return True
        def _stream_artifact(self,identity,relative,expected=None):
            media=coordinator.inspect_media(identity,relative)
            if expected is not None and (
                media["sha256"]!=expected["sha256"] or
                media["bytes"]!=expected["bytes"]):
                return self._reply(409,{"error":"Original media changed after ticket authorization"})
            # Snapshot the exact ORIGINAL bytes first. The old implementation
            # checked one open of the pathname then reopened it after HTTP
            # headers: a replaced file could be delivered under a false hash.
            try:
                with verified_artifact_snapshot(media) as source:
                    self.send_response(200)
                    self.send_header("Content-Type",media["mime"])
                    self.send_header("Content-Length",str(media["bytes"]))
                    self.send_header("X-ZX7-SHA256",media["sha256"])
                    self.send_header("Referrer-Policy","no-referrer")
                    self.send_header("Content-Disposition",
                                     'attachment; filename="'+Path(media["path"]).name+'"')
                    self.send_header("Cache-Control","no-store")
                    self.send_header("X-Content-Type-Options","nosniff")
                    self.end_headers()
                    shutil.copyfileobj(source,self.wfile,1024*1024)
            except (ValueError,RuntimeError) as exc:
                # A capacity failure (503) or a stale media SHA (409) cannot
                # masquerade as a successful original film transfer.
                code=503 if isinstance(exc,RuntimeError) else 409
                return self._reply(code,{"error":str(exc)})
        def do_GET(self):
            path=urlsplit(self.path).path
            if path in MOBILE_ASSETS:
                # Static shell contains NO user data or secret. Browser API calls
                # still need the existing Bearer token and remain loopback-bound.
                media,contents=MOBILE_ASSETS[path]
                self.send_response(200)
                self.send_header("Content-Type",media)
                self.send_header("Content-Length",str(len(contents)))
                self.send_header("Cache-Control","no-store")
                self.send_header("Content-Security-Policy",MOBILE_CSP)
                self.send_header("X-Content-Type-Options","nosniff")
                self.send_header("Referrer-Policy","no-referrer")
                self.end_headers()
                self.wfile.write(contents)
                return
            if path.startswith("/v1/download/"):
                ticket=delivery_tickets.consume(path.removeprefix("/v1/download/"))
                if ticket is None:
                    return self._reply(404,{"error":"Download authorization expired or already used"})
                try:
                    return self._stream_artifact(ticket["job_id"],ticket["relative"],expected=ticket)
                except (OSError,ValueError,TypeError):
                    return self._reply(404,{"error":"Authorized original media no longer available"})
            if not self._authorized():return
            try:
                if path=="/v1/health":
                    return self._reply(200,{"service":"zx7-local-body",
                        "host_only":"127.0.0.1","online":True,
                        "creative_model_configured":getattr(coordinator,"creative_sessions",None) is not None})
                if path.startswith("/v1/creative-sessions/"):
                    manager=getattr(coordinator,"creative_sessions",None)
                    if manager is None:
                        return self._reply(503,{"error":"No local creative model configured on this host"})
                    return self._reply(200,manager.inspect(path.removeprefix("/v1/creative-sessions/")))
                if path=="/v1/jobs":
                    return self._reply(200,coordinator.list_jobs())
                if path=="/v1/resources":
                    return self._reply(200,coordinator.host_resource_status())
                if path=="/v1/affordances":
                    opts=parse_qs(urlsplit(self.path).query,keep_blank_values=True)
                    if any(k not in ("capability","limit","cursor","include_unavailable") or
                           len(v)!=1 for k,v in opts.items()):
                        raise ValueError("Invalid bounded somatic capability query")
                    limit=int(opts.get("limit",["12"])[0])
                    flag=opts.get("include_unavailable",["false"])[0]
                    if flag not in ("true","false"):
                        raise ValueError("Invalid unavailable-tool query option")
                    catalog=body_catalog(coordinator.projects)
                    return self._reply(200,BodyAffordanceSurface(catalog).discover(
                        capability=opts.get("capability",[None])[0],limit=limit,
                        include_unavailable=flag=="true",
                        cursor=opts.get("cursor",[None])[0],
                        allowed_access=frozenset({"read","write"})))
                if path.startswith("/v1/affordances/"):
                    name=path.removeprefix("/v1/affordances/")
                    return self._reply(200,BodyAffordanceSurface(
                        body_catalog(coordinator.projects)).describe(name,
                            allowed_access=frozenset({"read","write"})))
                if path=="/v1/tools":
                    return self._reply(200,{"tools":operational_tool_summary(
                        coordinator.projects)})
                if path.startswith("/v1/tools/"):
                    name=path.removeprefix("/v1/tools/")
                    return self._reply(200,explain_operational_tool(
                        coordinator.projects,name))
                if path.startswith("/v1/jobs/"):
                    rest=path.removeprefix("/v1/jobs/")
                    if rest.endswith("/sense"):
                        identity=rest.removesuffix("/sense")
                        return self._reply(200,sense_body_job(coordinator,identity))
                    if "/artifacts/" in rest:
                        identity,relative=rest.split("/artifacts/",1)
                        self._stream_artifact(identity,unquote(relative))
                        return
                    if rest.endswith("/artifacts"):
                        identity=rest.removesuffix("/artifacts")
                        return self._reply(200,coordinator.list_media(identity))
                    return self._reply(200,coordinator.inspect(rest))
                return self._reply(404,{"error":"Unknown local body endpoint"})
            except (ValueError,TypeError) as exc:
                return self._reply(400,{"error":str(exc)})
        def do_POST(self):
            if not self._authorized():return
            path=urlsplit(self.path).path
            if path.startswith("/v1/creative-sessions/") and path.endswith("/stop"):
                manager=getattr(coordinator,"creative_sessions",None)
                if manager is None:
                    return self._reply(503,{"error":"No local creative model configured on this host"})
                try:
                    if self.headers.get("Content-Length","0") not in ("0",""):
                        raise ValueError("Stop takes no substituted creative input")
                    identity=path.removeprefix("/v1/creative-sessions/").removesuffix("/stop")
                    return self._reply(202,manager.stop(identity))
                except (ValueError,TypeError) as exc:
                    return self._reply(400,{"error":str(exc)})
            if path=="/v1/creative-sessions":
                manager=getattr(coordinator,"creative_sessions",None)
                if manager is None:
                    return self._reply(503,{"error":"No local creative model configured on this host"})
                try:
                    length=int(self.headers.get("Content-Length","0"))
                    if not 0<length<=131072:raise ValueError("Bounded creative brief required")
                    payload=json.loads(self.rfile.read(length))
                    if not isinstance(payload,dict) or set(payload)!={"workspace_id","brief","facts"}:
                        raise ValueError("Creative request needs workspace_id, brief and facts")
                    return self._reply(202,manager.create(payload["workspace_id"],payload["brief"],payload["facts"]))
                except (ValueError,TypeError) as exc:
                    return self._reply(400,{"error":str(exc)})
            if path=="/v1/affordances/preflight":
                # A sensory validation, NEVER a privileged execution or grant.
                # The owner must submit an independently protected Film IR job.
                try:
                    length=int(self.headers.get("Content-Length","0"))
                    if not 0<length<=_MAX_JOB_BODY:
                        raise ValueError("Bounded sensory preflight input required")
                    payload=json.loads(self.rfile.read(length))
                    if not isinstance(payload,dict) or set(payload)!={
                            "workspace_id","tool_id","inputs"}:
                        raise ValueError("Preflight takes exact existing workspace, tool and data")
                    workspace=coordinator._workspace(payload["workspace_id"])
                    if not workspace.is_dir():
                        raise ValueError("Original owner workspace not present")
                    return self._reply(200,BodyAffordanceSurface(
                        body_catalog(workspace)).preflight(
                            payload["tool_id"],payload["inputs"],
                            allowed_access=frozenset({"read","write"})))
                except (ValueError,TypeError,RuntimeError,PermissionError) as exc:
                    return self._reply(400,{"error":str(exc)})
            if path=="/v1/revisions/impact":
                # Read-only architectural diff. It does not execute a model,
                # reserve compute, alter the original Film IR or certify any
                # physical media as cached. Authentication is mandatory.
                try:
                    length=int(self.headers.get("Content-Length","0"))
                    if not (0<length<=_MAX_JOB_BODY):
                        raise ValueError("Bounded original film revision pair required")
                    payload=json.loads(self.rfile.read(length))
                    if not isinstance(payload,dict) or set(payload)!={"before","after"}:
                        raise ValueError("Exactly two original film IR revisions required")
                    return self._reply(200,plan_film_revision_impact(
                        payload["before"],payload["after"]))
                except (ValueError,TypeError,RecursionError) as exc:
                    return self._reply(400,{"error":str(exc)})

            if path.startswith("/v1/jobs/") and path.endswith("/download-ticket"):
                rest=path.removeprefix("/v1/jobs/").removesuffix("/download-ticket")
                if "/artifacts/" not in rest:
                    return self._reply(404,{"error":"Missing exact original artifact identity"})
                identity,relative=rest.split("/artifacts/",1)
                try:
                    if self.headers.get("Content-Length","0") not in ("0",""):
                        raise ValueError("Media download ticket accepts no model input")
                    decoded=unquote(relative)
                    media=coordinator.inspect_media(identity,decoded)
                    ticket=delivery_tickets.issue(identity,decoded,
                        sha256=media["sha256"],length=media["bytes"])
                    return self._reply(201,ticket)
                except (ValueError,TypeError,OSError,RuntimeError) as exc:
                    return self._reply(400,{"error":str(exc)})
            if path.startswith("/v1/workspaces/") and "/assets/" in path:
                pieces=path.split("/")
                if len(pieces)!=6 or pieces[1:3]!=["v1","workspaces"] or (
                        pieces[4]!="assets"):
                    return self._reply(404,{"error":"Invalid original media route"})
                try:
                    length=int(self.headers.get("Content-Length","0"))
                    self.connection.settimeout(coordinator.upload_timeout_seconds)
                    receipt=coordinator.upload_owner_media(
                        pieces[3],pieces[5],self.rfile,length,
                        mime=self.headers.get("Content-Type",""),
                        source_id=_utf8_media_header(self.headers,
                            "X-Source-Id","X-Source-Id-B64"),
                        rights_evidence=_utf8_media_header(self.headers,
                            "X-Rights-Evidence","X-Rights-Evidence-B64"))
                    return self._reply(201,receipt)
                except (ValueError,TypeError,FileExistsError,OSError) as exc:
                    return self._reply(400,{"error":str(exc)})
            if path.startswith("/v1/jobs/") and path.rsplit("/",1)[-1] in (
                    "retry","pause","resume","cancel"):
                pieces=path.split("/")
                if len(pieces)!=5 or pieces[1:3]!=["v1","jobs"]:
                    return self._reply(404,{"error":"Unknown original retry operation"})
                try:
                    if self.headers.get("Content-Length","0") not in ("0",""):
                        raise ValueError("Retry accepts no substituted creative plan")
                    if pieces[4] in ("pause","cancel"):
                        result=coordinator.request_control(pieces[3],pieces[4])
                    else:
                        result=coordinator.retry_job(pieces[3],resume=pieces[4]=="resume")
                    return self._reply(202,result)
                except (ValueError,RuntimeError) as exc:
                    return self._reply(400,{"error":str(exc)})
            if path!="/v1/jobs":
                return self._reply(404,{"error":"Only original film jobs and owned media can be submitted"})
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not (0<length<=_MAX_JOB_BODY):
                    raise ValueError("Bounded Film IR upload required; upload assets separately")
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict) or set(body)!={"workspace_id","film_ir"}:
                    raise ValueError("Job request requires original Film IR and workspace")
                return self._reply(202,coordinator.submit(
                    body["film_ir"],workspace_id=body["workspace_id"]))
            except (ValueError,TypeError,json.JSONDecodeError) as exc:
                return self._reply(400,{"error":str(exc)})
    return Handler


def start_local_body_service(root,*,secret,port=8765,workers=1,creative_model=None):
    if type(port) is not int or not (0<port<65536):
        raise ValueError("Local port must be explicit and valid")
    if not isinstance(secret,str) or len(secret)<32:
        raise ValueError("Local creative body API needs secret >=32 characters")
    coordinator=LocalBodyCoordinator(root,workers=workers,creative_model=creative_model)
    server=None
    try:
        # Bind first: a port collision must not strand an exclusive workspace
        # lock or start rendering jobs in a service that never came online.
        server=ThreadingHTTPServer(("127.0.0.1",port),
            make_body_http_handler(coordinator,secret))
        coordinator.pending_restart()
        server.serve_forever()
    finally:
        if server is not None:server.server_close()
        coordinator.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace-root",type=Path,required=True)
    p.add_argument("--port",type=int,default=8765)
    p.add_argument("--workers",type=int,default=1)
    p.add_argument("--creative-api",default="http://127.0.0.1:8085")
    p.add_argument("--creative-provider",choices=("local", "nvidia"),default="local",
                   help="Explicitly choose local inference or NVIDIA BYOK (never automatic)")
    p.add_argument("--creative-model",help="Explicit installed/local or NVIDIA catalog model ID")
    p.add_argument("--allow-cloud-image-upload",action="store_true",
                   help="Explicit host consent to upload original frames to selected NVIDIA model")
    a=p.parse_args()
    secret=os.getenv("ZX7_BODY_API_TOKEN")
    if not secret or len(secret)<32:
        raise SystemExit("Set a unique 32+ character ZX7_BODY_API_TOKEN in host environment")
    model=None
    if a.creative_provider == "nvidia" and (
            not a.creative_model or a.creative_api != "http://127.0.0.1:8085"):
        raise SystemExit("NVIDIA requires --creative-model and uses its fixed audited HTTPS endpoint")
    if a.allow_cloud_image_upload and a.creative_provider != "nvidia":
        raise SystemExit("Cloud image permission is valid only for an explicit NVIDIA provider")
    if a.creative_model:
        from .body_creative_session import SESSION_SYSTEM
        if a.creative_provider == "nvidia":
            from .nvidia_model import NvidiaCreativeModel, NvidiaModelSettings
            model = NvidiaCreativeModel(NvidiaModelSettings(model_id=a.creative_model),
                  system_prompt=SESSION_SYSTEM,allow_image_upload=a.allow_cloud_image_upload)
            model.verify_host_credentials()
        else:
            from .providers import LocalCreativeModel,LocalModelSettings
            model=LocalCreativeModel(LocalModelSettings(base_url=a.creative_api,
                model_id=a.creative_model,max_response_bytes=262144),system_prompt=SESSION_SYSTEM)
    start_local_body_service(a.workspace_root,secret=secret,
                             port=a.port,workers=a.workers,creative_model=model)


if __name__=="__main__":main()
