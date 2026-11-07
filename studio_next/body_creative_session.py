"""Bounded model-to-BODY sessions from ordinary briefs, with durable receipts.

One installed local model authors decisions, documents and revisions. No film,
shot, soundtrack or creative direction is authored by this orchestrator.
Tests may inject a scripted client; those runs are explicitly not live-model
creative acceptance. Audio semantics and professional quality remain unproven.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import threading
import time
import uuid

from .body_integration import body_catalog
from .body_signal import BodyAuthority, LiveBodySignal
from .body_verified_delivery import verified_artifact_snapshot
from .media_vault import MediaVault

SESSION_SYSTEM = """You are the single creative intelligence operating an actual studio BODY.
The owner gives a creative brief, not a technical plan. Decide the story, medium,
voice, sound, pacing, artwork, production and revisions yourself. Never invent
tools, assets, rights, observations or a completed movie. Choose your own art.
Discover actual operations; describe selected tools for exact input/document
contracts, author those documents, preflight and submit Film IR production graphs.
All write tools execute through submit, not through read. A Film IR has project
{creative_intent}, shots[{id,purpose,duration_seconds,fact_refs,asset_refs}],
assets[{id,status,rights,location}], owner_facts and tool_graph nodes
{id,tool_id,purpose,inputs,depends_on}. Reuse original source assets and prior
graph stages, author a new plan/output path for revisions, never overwrite.
Observe job results, decode output and use real review instruments. You can
request actual PNG/JPEG pixels with read_picture for a job artifact; the next
turn receives up to four selected, SHA-verified images if vision is supported.
Selecting further images evicts the oldest selection, not the underlying media. Audio measurements
are not semantic listening, and frames do not establish continuous motion.
Do not falsely claim either. Preserve ambitious ideas when a resource is absent.
Return JSON only: {action, arguments, reason}. Actions and exact arguments:
discover:{capability?,cursor?,limit?,include_unavailable?}; describe:{tool_id};
preflight:{tool_id,inputs}; assets:{}; author_plan:{tool_id,document,input_name?};
inspect_plan:{sha256,pointer?}; revise_plan:{tool_id,base_sha256,operations,input_name?};
Revision operations edit creative JSON only: {op:add|replace|test,path,value} or
{op:remove,path}, with JSON Pointer paths. The original remains unchanged.
submit:{film_ir}; observe:{job_id}; wait:{job_id,seconds};
read:{tool_id,inputs} for registered READ tools only;
read_picture:{job_id,path}; unselect_picture:{job_id,path}; finish:{summary}; question:{question}.
recall:{offset,limit} retrieves earlier saved decisions and receipts when needed.
There is a finite turn/time budget. Finish only after checking your actual jobs,
state remaining blockers honestly and do not equate technical success with
cinematic quality. An essential unanswered fact may require question.
"""


_MAX_PICTURE_EVIDENCE=4
_MAX_PICTURE_EVIDENCE_BYTES=12_000_000


def _wire(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True)


class CreativeSessions:
    def __init__(self, coordinator, model, *, max_turns=64, seconds=3600):
        if type(max_turns) is not int or not 1<=max_turns<=128 or not 1<=seconds<=7200:
            raise ValueError("Creative session requires explicit finite host budgets")
        self.coordinator=coordinator
        self.model=model
        self.max_turns=max_turns
        self.seconds=seconds
        self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="zx7-creative")
        self._lock=threading.Lock()
        self._queued=set()
        with coordinator._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS creative_sessions(
                id TEXT PRIMARY KEY, workspace TEXT NOT NULL, state TEXT NOT NULL)""")
            db.execute("CREATE TABLE IF NOT EXISTS creative_session_controls(id TEXT PRIMARY KEY, action TEXT NOT NULL)")

    def _model_identity(self):
        settings=getattr(self.model,"settings",None)
        provider=getattr(settings,"provider_id","local")
        endpoint=getattr(settings,"base_url",None)
        return {"model_id":getattr(settings,"model_id",None),
                "provider_id":provider,
                "local_endpoint":endpoint if provider=="local" else None,
                "remote_endpoint":endpoint if provider=="nvidia" else None,
                "adapter":type(self.model).__module__+"."+type(self.model).__qualname__,
                "system_prompt_sha256":hashlib.sha256(
                    getattr(self.model,"system_prompt",SESSION_SYSTEM).encode()).hexdigest(),
                "neural_weights_or_independent_creativity_verified":False}

    def create(self,workspace,brief,facts):
        self.coordinator._workspace(workspace)
        if (not isinstance(brief,str) or not 1<=len(brief.strip())<=32000 or
                not isinstance(facts,dict) or len(_wire(facts))>64000 or
                any(not isinstance(k,str) or not k for k in facts)):
            raise ValueError("An ordinary brief and owner fact ledger are required")
        identity=uuid.uuid4().hex
        state={"id":identity,"workspace_id":workspace,"brief":brief,"facts":facts,
               "model_identity":self._model_identity(),
               "status":"queued","events":[],"pending":None,"jobs":[],
               "pictures":[],"elapsed_seconds":0,"turn_limit":self.max_turns,
               "expires_at":time.time()+self.seconds,
               "time_limit_seconds":self.seconds,"artistic_quality_approved":False,
               "audio_semantically_reviewed":False}
        with self.coordinator._maintenance_lock, self._lock, self.coordinator._connect() as db:
            # One artist controls one film workspace at a time.
            for (raw,) in db.execute("SELECT state FROM creative_sessions WHERE workspace=?",(workspace,)):
                if json.loads(raw)["status"] in ("queued","running"):
                    raise ValueError("A creative session is already active in this workspace")
            db.execute("INSERT INTO creative_sessions VALUES(?,?,?)",(identity,workspace,_wire(state)))
        self._queue(identity)
        return {"session_id":identity,"workspace_id":workspace,"status":"queued"}

    def inspect(self,identity):
        if not isinstance(identity,str) or len(identity)!=32 or any(c not in "0123456789abcdef" for c in identity):
            raise ValueError("Invalid creative session identity")
        with self.coordinator._connect() as db:
            row=db.execute("SELECT state FROM creative_sessions WHERE id=?",(identity,)).fetchone()
        if row is None: raise ValueError("Unknown creative session")
        return json.loads(row[0])

    def _save(self,state):
        with self.coordinator._maintenance_lock, self.coordinator._connect() as db:
            db.execute("UPDATE creative_sessions SET state=? WHERE id=?",(_wire(state),state["id"]))

    def stop(self,identity):
        state=self.inspect(identity)
        with self.coordinator._connect() as db:
            db.execute("INSERT OR REPLACE INTO creative_session_controls VALUES(?,?)",(identity,"stop"))
        # Existing production jobs remain individually pauseable/cancellable;
        # no new model action starts after the outstanding inference returns.
        return {"session_id":identity,"status":"stop_requested","jobs":state["jobs"]}

    def _stopped(self,identity):
        with self.coordinator._connect() as db:
            return db.execute("SELECT 1 FROM creative_session_controls WHERE id=? AND action='stop'",(identity,)).fetchone() is not None

    def resume_pending(self):
        with self.coordinator._connect() as db:
            records=db.execute("SELECT id,state FROM creative_sessions").fetchall()
        for identity,raw in records:
            if json.loads(raw)["status"] in ("queued","running"):
                self._queue(identity)

    def _queue(self,identity):
        with self._lock:
            if identity in self._queued:return
            self._queued.add(identity)
            self._executor.submit(self._run,identity)

    def close(self):
        self._executor.shutdown(wait=True)

    def _assets(self,workspace):
        vault=MediaVault(self.coordinator._workspace(workspace)/"vault")
        with vault._connect() as db:
            rows=db.execute("SELECT digest,attestation_id FROM attestations ORDER BY created_at LIMIT 201").fetchall()
        assets=[]
        for digest,attestation in rows[:200]:
            record=vault.inspect(digest,attestation_id=attestation)
            assets.append({"source":"zx7:sha256:"+digest,"asset_id":digest,
                "attestation_id":attestation,"mime":record["mime"],"bytes":record["size_bytes"],
                "rights_attestations":record["rights_attestations"]})
        return {"assets":assets,"more_assets":len(rows)>200}

    def _pictures(self,state):
        """Revalidate every selected immutable picture at the moment of model use.

        Review can compare different revisions simultaneously. The selection
        budget constrains each inference request, not film duration, shots or
        the number of frames a creative model may inspect over a session.
        """
        selected=state["pictures"]
        if not isinstance(selected,list) or len(selected)>_MAX_PICTURE_EVIDENCE:
            raise ValueError("Vision selection exceeds the host's frame comparison budget")
        images=[];total_bytes=0
        for picture in selected:
            record=self.coordinator.inspect(picture["job_id"])
            if record["workspace_id"]!=state["workspace_id"]:
                raise PermissionError("Picture belongs to another session workspace")
            media=self.coordinator.inspect_media(picture["job_id"],picture["path"])
            if media["mime"] not in ("image/png","image/jpeg") or media["bytes"]>3000000:
                raise ValueError("Vision requires an actual bounded PNG or JPEG artifact")
            if media["sha256"]!=picture["sha256"]:
                raise ValueError("Observed picture bytes changed")
            total_bytes+=media["bytes"]
            if total_bytes>_MAX_PICTURE_EVIDENCE_BYTES:
                raise ValueError("Vision selection exceeds the host's byte budget")
            with verified_artifact_snapshot(media) as stream:
                images.append((media["mime"],stream.read(3000001)))
        return images

    def _dispatch(self,state,signal,decision):
        if (not isinstance(decision,dict) or set(decision)!={"action","arguments","reason"} or
                not isinstance(decision["arguments"],dict) or
                not isinstance(decision["reason"],str) or len(_wire(decision))>262144):
            raise ValueError("Model must return a bounded typed action, arguments and reason")
        action=decision["action"]; args=decision["arguments"]; workspace=state["workspace_id"]
        if action=="discover":return signal.discover(workspace,**args)
        if action=="describe":return signal.describe(workspace,**args)
        if action=="preflight":return signal.preflight(workspace,**args)
        if action=="inspect_plan":return signal.inspect_plan(workspace,**args)
        if action=="assets" and not args:return self._assets(workspace)
        if action=="recall" and set(args)=={"offset","limit"}:
            offset=args["offset"];limit=args["limit"]
            if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=4:
                raise ValueError("Recall requires a nonnegative offset and limit 1..4")
            return {"events":state["events"][offset:offset+limit],"offset":offset}
        if action in ("author_plan","revise_plan","submit"):
            if "workspace_id" in args:
                raise ValueError("Session workspace is assigned by the host")
            if action=="submit":
                if set(args)!={"film_ir"} or not isinstance(args["film_ir"],dict):
                    raise ValueError("Submit requires one original Film IR")
                ir=args["film_ir"]
                if ir.get("owner_facts",state["facts"])!=state["facts"]:
                    raise ValueError("Model cannot replace owner facts")
                args={"film_ir":{**ir,"owner_facts":state["facts"]}}
            key=hashlib.sha256((state["id"]+str(len(state["events"]))).encode()).hexdigest()
            result=signal.command(action,{"workspace_id":workspace,**args},
                                  submission_key=key if action=="submit" else None)
            if action=="submit" and result["job_id"] not in state["jobs"]:
                state["jobs"].append(result["job_id"])
            return result
        if action=="read" and set(args)=={"tool_id","inputs"}:
            signal.describe(workspace,args["tool_id"])
            return body_catalog(self.coordinator._workspace(workspace)).invoke(
                args["tool_id"],args["inputs"],allowed_access={"read"})
        if action in ("observe","wait"):
            expected={"job_id"} if action=="observe" else {"job_id","seconds"}
            if set(args)!=expected:raise ValueError("Invalid job observation arguments")
            signal.observe(args["job_id"])
            if action=="wait":
                duration=args["seconds"]
                if type(duration) not in (int,float) or not 0<=duration<=10:
                    raise ValueError("Job wait must be at most ten seconds")
                end=time.monotonic()+duration
                while self.coordinator.inspect(args["job_id"])["status"] in ("queued","running") and time.monotonic()<end:
                    time.sleep(min(.1,max(0,end-time.monotonic())))
            return self.coordinator.inspect(args["job_id"])
        if action=="unselect_picture" and set(args)=={"job_id","path"}:
            if any(not isinstance(args[k],str) or not args[k] for k in ("job_id","path")):
                raise ValueError("Picture selection identity must be nonempty text")
            selected=[p for p in state["pictures"]
                      if (p["job_id"],p["path"])!=(args["job_id"],args["path"])]
            if len(selected)==len(state["pictures"]):
                raise ValueError("Selected picture not found")
            state["pictures"]=selected
            return {"unselected_picture":{"job_id":args["job_id"],"path":args["path"]},
                    "selected_picture_count":len(selected),
                    "original_artifacts_untouched":True}
        if action=="read_picture" and set(args)=={"job_id","path"}:
            signal.observe(args["job_id"])
            media=self.coordinator.inspect_media(args["job_id"],args["path"])
            # A physical artifact is immutable: do not quietly replace an
            # earlier visual witness with different bytes under the same path.
            for previous in state["pictures"]:
                if (previous["job_id"]==args["job_id"] and
                        previous["path"]==args["path"] and
                        previous["sha256"]!=media["sha256"]):
                    raise ValueError("Previously observed picture identity changed")
            pictures=[previous for previous in state["pictures"]
                      if (previous["job_id"],previous["path"])!=
                         (args["job_id"],args["path"])]
            pictures.append({**args,"sha256":media["sha256"]})
            evicted=pictures[:-_MAX_PICTURE_EVIDENCE]
            pictures=pictures[-_MAX_PICTURE_EVIDENCE:]
            # Validate *all* retained real pictures before committing selection.
            self._pictures({**state,"pictures":pictures})
            state["pictures"]=pictures
            return {**args,"sha256":media["sha256"],"pixels_in_next_model_request":True,
                    "selected_picture_count":len(pictures),
                    "evicted_previous_selections":[
                        {"job_id":p["job_id"],"path":p["path"]} for p in evicted],
                    "audio_reviewed":False,"continuous_motion_reviewed":False}
        if action in ("finish","question"):
            key="summary" if action=="finish" else "question"
            if set(args)!={key} or not isinstance(args[key],str) or not args[key].strip():
                raise ValueError("A final explanation or essential question is required")
            jobs=[self.coordinator.inspect(job) for job in state["jobs"]]
            if action=="finish" and any(j["status"] in ("queued","running") for j in jobs):
                raise ValueError("Observe submitted production jobs before finishing")
            state["status"]="model_finished" if action=="finish" else "needs_owner_input"
            state[key]=args[key]
            return {"jobs":[{"id":j["job_id"],"status":j["status"]} for j in jobs],
                    "model_statement_is_not_independent_quality_acceptance":True}
        raise ValueError("Unknown or unauthorized creative action")

    def _run(self,identity):
        state=self.inspect(identity); started=time.monotonic(); previous=state["elapsed_seconds"]
        try:
            if state["model_identity"]!=self._model_identity():
                raise RuntimeError("Resume requires the original configured model and protocol")
            state["status"]="running"; self._save(state)
            signal=LiveBodySignal(self.coordinator,authority=BodyAuthority(
                workspace_ids=frozenset({state["workspace_id"]}),
                fact_ids=frozenset(state["facts"]),operations=frozenset({"author_plan","revise_plan","submit"}),
                tool_access=frozenset({"read","write"})))
            while len(state["events"])<state["turn_limit"]:
                if self._stopped(identity):
                    state["status"]="stopped";return
                state["elapsed_seconds"]=previous+time.monotonic()-started
                if time.time()>=state["expires_at"]:break
                if state["pending"] is None:
                    context={"owner_brief":state["brief"],"owner_facts":state["facts"],
                             "workspace_id":state["workspace_id"],"submitted_jobs":state["jobs"],
                             "recent_events":state["events"][-8:],"picture_evidence":state["pictures"],
                             "remaining_turns":state["turn_limit"]-len(state["events"])}
                    images=self._pictures(state)
                    if images:decision=self.model.decide_with_images(context,images)
                    else:decision=self.model.decide(context)
                    if len(_wire(decision))>262144:
                        raise ValueError("Model action exceeds the session response budget")
                    state["pending"]=decision
                    self._save(state) # Commit intent before any BODY mutation.
                if self._stopped(identity):
                    state["status"]="stopped";return
                if time.time()>=state["expires_at"]:break
                decision=state["pending"]
                try:result=self._dispatch(state,signal,decision)
                except (ValueError,TypeError,RuntimeError,OSError,KeyError) as exc:
                    result={"error":type(exc).__name__+": "+str(exc)[:1600]}
                state["events"].append({"decision":decision,"result":result})
                state["pending"]=None
                state["elapsed_seconds"]=previous+time.monotonic()-started
                self._save(state)
                if state["status"]!="running":return
            state["status"]="budget_exhausted"
        except Exception as exc:
            state["status"]="blocked"
            state["error"]=type(exc).__name__+": "+str(exc)[:1600]
        finally:
            state["elapsed_seconds"]=previous+time.monotonic()-started
            try:self._save(state)
            finally:
                with self._lock:self._queued.discard(identity)
