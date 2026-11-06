"""ZX7 unified model-neutral BODY signal: compact senses and authorized actions.

Consolidates the separate 21 October live-signal experiment onto the canonical
BodyAffordanceSurface + factual Body sensory contract. Not a creative model, MCP
implementation, media decoder, autonomous worker or artist quality certificate.
A host constructs BodyAuthority out-of-band; untrusted model data never grants
filesystem, workspace, network, spending or native operation rights.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .body_affordances import BodyAffordanceSurface
from .body_integration import body_catalog
from .body_sensory import sense_body_job
from .film_ir import validate_film_ir
from .body_document_schemas import validate_document
from .body_project_heads import DocumentHeadLedger

_ACTIONS=frozenset({"author_plan","revise_plan","select_plan","submit","pause","cancel","resume","retry"})
_ACCESS=frozenset({"read","write","network","paid"})
# Legacy edit/OTIO accept owner-supplied textual rights labels without real
# MediaVault custody. Retain them for explicit historical migration, never
# advertise or execute them from an autonomous model-facing BODY signal.
_LEGACY_UNATTESTED=frozenset({"body.render_edit","body.otio"})


class BodyCommandRejected(ValueError):
    """A command was rejected without starting new execution."""


@dataclass(frozen=True)
class BodyAuthority:
    """Real owner-provided immutable permission scope, not model arguments."""
    workspace_ids: frozenset[str]
    operations: frozenset[str]=field(default_factory=frozenset)
    fact_ids: frozenset[str]=field(default_factory=frozenset)
    tool_access: frozenset[str]=field(default_factory=lambda:frozenset({"read"}))

    def __post_init__(self):
        if (not isinstance(self.workspace_ids,frozenset)
            or not self.workspace_ids or
            any(not isinstance(x,str) or not x or len(x)>80 or
                not all(c.isalnum() or c in "-_" for c in x)
                for x in self.workspace_ids) or
            not isinstance(self.operations,frozenset) or
            not self.operations.issubset(_ACTIONS) or
            not isinstance(self.fact_ids,frozenset) or
            any(not isinstance(x,str) or not x for x in self.fact_ids) or
            not isinstance(self.tool_access,frozenset) or
            not self.tool_access or not self.tool_access.issubset(_ACCESS)):
            raise ValueError("Only narrow host-issued BODY authority is valid")
        if (bool(self.operations & {"submit","author_plan","revise_plan","select_plan"})
                and "write" not in self.tool_access):
            raise ValueError("Studio source creation requires host-issued write access")


class LiveBodySignal:
    """Read real registered tools, observe actual status, command owner jobs.

    This deliberately REUSES one trusted catalog, native persistence, native
    source validation and sense_body_job rather than forked implementations.
    """
    VERSION="zx7-body-signal/3"

    def __init__(self,coordinator,*,authority:BodyAuthority,
                 catalog_factory:Callable|None=None):
        if not isinstance(authority,BodyAuthority):
            raise TypeError("BODY requires out-of-band host-issued authority")
        self._coordinator=coordinator
        self._authority=authority
        self._factory=catalog_factory or body_catalog

    def _workspace(self,workspace_id):
        if (not isinstance(workspace_id,str)
                or workspace_id not in self._authority.workspace_ids):
            raise PermissionError("Workspace has not been authorized by owner host")
        return self._coordinator._workspace(workspace_id)

    def _surface(self,workspace_id):
        return BodyAffordanceSurface(
            self._factory(self._workspace(workspace_id)),
            excluded_tool_ids=_LEGACY_UNATTESTED)

    def discover(self,workspace_id,*,capability=None,cursor=None,limit=12,
                 include_unavailable=False):
        catalog=self._surface(workspace_id).discover(
            capability=capability,cursor=cursor,limit=limit,
            include_unavailable=include_unavailable,
            allowed_access=self._authority.tool_access)
        signatures={
            "author_plan":["workspace_id","tool_id","document"],
            "revise_plan":["workspace_id","tool_id","base_sha256","operations"],
            "select_plan":["workspace_id","project_id","tool_id",
                           "document_sha256","expected_revision_id",
                           "expected_document_sha256"],
            "submit":["workspace_id","film_ir"],
            "pause":["job_id"],"cancel":["job_id"],
            "resume":["job_id"],"retry":["job_id"]}
        return {"protocol":self.VERSION,**catalog,
                "host_authorized_commands":[
                    {"action":action,"required_arguments":signatures[action]}
                    for action in sorted(self._authority.operations)],
                "author_plan_creates_unlicensed_data_not_a_rendered_movie":True}

    def describe(self,workspace_id,tool_id):
        return {"protocol":self.VERSION,**self._surface(workspace_id).describe(
            tool_id,allowed_access=self._authority.tool_access)}

    def preflight(self,workspace_id,tool_id,inputs):
        return {"protocol":self.VERSION,**self._surface(workspace_id).preflight(
            tool_id,inputs,allowed_access=self._authority.tool_access)}

    def _author_original_plan(self,arguments):
        """Persist only a bounded JSON instrument plan in this owner workspace.

        The model may AUTHOR composition/story/tool intent but cannot attach
        rights, execute Python, choose an unregistered tool, overwrite artist
        media, or silently claim the film has rendered. Subsequent preflight
        and actual graph execution independently validate the typed document,
        immutable source custody and native installed renderer.
        """
        workspace_id=arguments["workspace_id"]
        workspace=self._workspace(workspace_id)
        tool_id=arguments["tool_id"]
        surface=self._surface(workspace_id)
        detail=surface.describe(
            tool_id,allowed_access=self._authority.tool_access)
        if not tool_id.startswith("body."):
            raise BodyCommandRejected(
                "Model can only author plans for recognized native BODY instruments")
        # Preparing immutable artistic intentions is safe while a renderer is
        # offline. Only the real registered code schema may be consulted.
        # NEVER describe or execute an unavailable tool as installed.
        schema=detail["input_schema"]
        if schema is None:
            matches=[row for row in surface.catalog.discover()
                     if row["id"]==tool_id and
                     row["access"] in self._authority.tool_access]
            if len(matches)!=1:
                raise BodyCommandRejected("Missing installed-body plan contract")
            schema=matches[0]["schema"]
        required=schema["required"]
        permitted=("plan","edit","scene_json","original_film_ir","video_job")
        document_fields=[name for name in required if name in permitted]
        if "input_name" in arguments:
            selected=arguments["input_name"]
            if selected not in required or selected not in permitted+("operation",):
                raise BodyCommandRejected("Unsupported creative document input_name")
            document_fields=[selected]
        if len(document_fields)!=1:
            raise BodyCommandRejected(
                "Installed BODY tool has no single supported JSON creative document")
        document=arguments["document"]
        if not isinstance(document,dict):
            raise BodyCommandRejected("Creative technical tool plan must be a JSON object")
        try:
            schema_validated=validate_document(tool_id,document,document_fields[0])
        except ValueError as exc:
            raise BodyCommandRejected(str(exc)) from exc
        try:
            raw=(json.dumps(document,allow_nan=False,ensure_ascii=False,
                sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")
        except (TypeError,ValueError,OverflowError,RecursionError) as exc:
            raise BodyCommandRejected("Original creative plan is not finite JSON") from exc
        if not 2<=len(raw)<=262144:
            raise BodyCommandRejected("Studio-authored original plan exceeds 256 KiB")
        digest=hashlib.sha256(raw).hexdigest()
        workspace.mkdir(parents=True,exist_ok=True)
        directory=workspace/"brain-authored"
        if directory.is_symlink():
            raise PermissionError("Creative plan workspace is a symbolic link")
        directory.mkdir(mode=0o700,exist_ok=True)
        target=directory/(digest+".json")
        if target.is_symlink():
            raise PermissionError("A competing editor substituted the creative plan")
        if target.is_file():
            from .media_vault import sha256_file
            if sha256_file(target)!=digest:
                raise PermissionError("Previously published creative plan bytes changed")
        else:
            fd,stage=tempfile.mkstemp(prefix=".zx7-plan-",dir=directory)
            try:
                with os.fdopen(fd,"wb") as created:
                    created.write(raw)
                    created.flush()
                    os.fsync(created.fileno())
                try:
                    os.link(stage,target)
                except FileExistsError:
                    from .media_vault import sha256_file
                    if target.is_symlink() or sha256_file(target)!=digest:
                        raise PermissionError(
                            "Another writer published a conflicting creative plan")
                folder_fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(folder_fd)
                finally:os.close(folder_fd)
            finally:
                Path(stage).unlink(missing_ok=True)
        return {
            "protocol":self.VERSION,
            "workspace_id":workspace_id,
            "tool_id":tool_id,
            "document_input_name":document_fields[0],
            "path":"brain-authored/"+target.name,
            "sha256":digest,"bytes":len(raw),
            "immutable_editor_document_published":True,
            "document_shape_validated":schema_validated,
            "tool_ready_to_execute_now":detail["status"]=="ready_to_preflight",
            "source_legal_rights_certified":False,
            "film_physically_rendered":False,
            "independent_artistic_quality_approved":False}

    def _read_original_plan(self,workspace_id,digest):
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
            raise BodyCommandRejected("Creative document identity must be a SHA256")
        directory=self._workspace(workspace_id)/"brain-authored"
        path=directory/(digest+".json")
        if directory.is_symlink() or path.is_symlink():raise PermissionError("Creative document cannot follow symbolic links")
        folder_fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=folder_fd)
            with os.fdopen(fd,"rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise PermissionError("Creative plan must be a regular file")
                raw=stream.read(262145)
        finally:os.close(folder_fd)
        if len(raw)>262144 or hashlib.sha256(raw).hexdigest()!=digest:
            raise BodyCommandRejected("Original creative document changed or exceeds its budget")
        return json.loads(raw)

    def inspect_plan(self,workspace_id,sha256,*,pointer=""):
        if "read" not in self._authority.tool_access:raise PermissionError("Host did not authorize creative document inspection")
        from .body_project_revision import selected_value
        try:value=selected_value(self._read_original_plan(workspace_id,sha256),pointer)
        except ValueError as exc:raise BodyCommandRejected(str(exc)) from exc
        raw=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
        if len(raw)>16384:
            return {"sha256":sha256,"pointer":pointer,"value_omitted":True,"encoded_bytes":len(raw),
                    "select_a_more_specific_pointer":True,"child_keys":list(value)[:200] if isinstance(value,dict) else None,
                    "item_count":len(value) if isinstance(value,(dict,list)) else None}
        return {"sha256":sha256,"pointer":pointer,"value":value,"value_omitted":False}

    def _revise_original_plan(self,arguments):
        from .body_project_revision import revise_document
        original=self._read_original_plan(arguments["workspace_id"],arguments["base_sha256"])
        try:revised=revise_document(original,arguments["operations"])
        except ValueError as exc:raise BodyCommandRejected(str(exc)) from exc
        request={"workspace_id":arguments["workspace_id"],"tool_id":arguments["tool_id"],"document":revised}
        if "input_name" in arguments:request["input_name"]=arguments["input_name"]
        result=self._author_original_plan(request)
        return {**result,"base_sha256":arguments["base_sha256"],"original_document_preserved":True,
                "changed_paths":[op["path"] for op in arguments["operations"] if op["op"]!="test"],
                "body_implementation_changed":False}

    def _select_original_plan(self, arguments):
        """Select a real immutable instrument document under an exact CAS head.

        Unlike a native editor WRITE, this only changes the host-designated
        *plan reference*. The original document must already exist as the
        exact physical bytes of its SHA and match a currently authorized,
        installed BODY tool schema. No source rights or native media is
        minted by selecting a plan.
        """
        workspace_id=arguments["workspace_id"]
        desired=arguments["document_sha256"]
        original=self._read_original_plan(workspace_id,desired)
        proof={"workspace_id":workspace_id,"tool_id":arguments["tool_id"],
               "document":original}
        if "input_name" in arguments:
            proof["input_name"]=arguments["input_name"]
        independently_validated=self._author_original_plan(proof)
        if independently_validated["sha256"]!=desired:
            raise BodyCommandRejected(
                "Original document no longer matches its validated SHA256")
        try:
            result=DocumentHeadLedger(self._workspace(workspace_id)).select(
                project_id=arguments["project_id"],tool_id=arguments["tool_id"],
                input_name=independently_validated["document_input_name"],
                document_sha256=desired,
                expected_revision_id=arguments["expected_revision_id"],
                expected_document_sha256=arguments["expected_document_sha256"])
        except ValueError as exc:
            raise BodyCommandRejected(str(exc)) from exc
        return {"protocol":self.VERSION,"workspace_id":workspace_id,**result,
                "original_document_bytes_preserved":True,
                "host_installed_document_schema_revalidated":True,
                "native_media_rendered_or_approved":False}

    def inspect_plan_heads(self,workspace_id,project_id,*,limit=50):
        """Inspect all native-tool plan heads in one authorized logical project."""
        if "read" not in self._authority.tool_access:
            raise PermissionError("Host did not grant creative project inspection")
        workspace=self._workspace(workspace_id)
        return {"protocol":self.VERSION,"workspace_id":workspace_id,
                **DocumentHeadLedger(workspace).heads(project_id,limit=limit)}

    def inspect_plan_history(self,workspace_id,project_id,tool_id,input_name,
                             *,limit=32):
        """Bounded immutable parent lineage, without raw creative documents."""
        if "read" not in self._authority.tool_access:
            raise PermissionError("Host did not grant creative revision inspection")
        workspace=self._workspace(workspace_id)
        return {"protocol":self.VERSION,"workspace_id":workspace_id,
                **DocumentHeadLedger(workspace).history(
                    project_id=project_id,tool_id=tool_id,
                    input_name=input_name,limit=limit)}

    def observe(self,job_id,*,include_artifacts=False,max_stages=16):
        if type(include_artifacts) is not bool:
            raise BodyCommandRejected("Artifact detail must be a boolean")
        job=self._coordinator.inspect(job_id)
        self._workspace(job["workspace_id"])
        signal=sense_body_job(self._coordinator,job_id,max_stages=max_stages)
        report={"protocol":self.VERSION,**signal}
        if include_artifacts:
            inventory=self._coordinator.list_media(job_id)
            actual=inventory.get("assets",[])
            if not isinstance(actual,list):
                raise RuntimeError("Malformed actual workspace media inventory")
            report["workspace_media"]=[
                {"path":item["path"],"sha256":item["sha256"],
                 "bytes":item["bytes"],"accepted_as_finished_film":False}
                for item in actual[:200] if isinstance(item,dict)
                and all(k in item for k in ("path","sha256","bytes"))]
            report["workspace_media_is_not_job_specific_receipt"]=True
            report["more_workspace_media"]=len(actual)>200
        return report

    def command(self,action,arguments,*,submission_key=None):
        if action not in _ACTIONS or not isinstance(action,str):
            raise BodyCommandRejected("Unknown model-facing BODY operation")
        if action not in self._authority.operations:
            raise PermissionError("Host did not authorize this BODY mutation")
        if not isinstance(arguments,dict):
            raise BodyCommandRejected("Typed BODY command object required")
        expected=({"film_ir","workspace_id"} if action=="submit" else
                  {"workspace_id","tool_id","document"} if action=="author_plan"
                  else {"workspace_id","tool_id","base_sha256","operations"} if action=="revise_plan"
                  else {"workspace_id","project_id","tool_id","document_sha256",
                        "expected_revision_id","expected_document_sha256"}
                       if action=="select_plan"
                  else {"job_id"})
        if (set(arguments)!=expected and not (
                action in ("author_plan","revise_plan","select_plan") and set(arguments)==expected|{"input_name"})):
            raise BodyCommandRejected("Unapproved BODY command argument fields")
        if action=="author_plan":
            return self._author_original_plan(arguments)
        if action=="revise_plan":
            return self._revise_original_plan(arguments)
        if action=="select_plan":
            return self._select_original_plan(arguments)
        if action=="submit":
            workspace_id=arguments["workspace_id"]
            self._workspace(workspace_id)
            ir=arguments["film_ir"]
            if not isinstance(ir,dict):
                raise BodyCommandRejected("Original creative Film IR object required")
            catalog=self._factory(self._workspace(workspace_id))
            validation=validate_film_ir(ir,
                installed_tool_ids=(
                    catalog.executable_ids(
                        allowed_access=self._authority.tool_access)
                    -_LEGACY_UNATTESTED),
                fact_ids=set(self._authority.fact_ids))
            if not validation.render_ready:
                raise BodyCommandRejected("Proposed film is not physically runnable: "+
                    "; ".join(validation.errors+validation.warnings)[:1200])
            # Coordinator's durable graph independently rechecks physical
            # assets, licenses, executable revisions and each source SHA.
            if submission_key is not None:
                if not isinstance(submission_key,str) or len(submission_key)!=64 or any(
                        c not in "0123456789abcdef" for c in submission_key):
                    raise BodyCommandRejected("Host submission key must be a SHA256")
                # Stable across a session crash after job insertion but before
                # recording its receipt. The validated original must match.
                identity=hashlib.sha256((workspace_id+submission_key).encode()).hexdigest()
                with self._coordinator._connect() as db:
                    existing=db.execute("SELECT workspace_id,original_ir,status FROM jobs WHERE id=?",
                                        (identity,)).fetchone()
                if existing is not None:
                    if existing[0]!=workspace_id or json.loads(existing[1])!=ir:
                        raise BodyCommandRejected("Submission key conflicts with original film")
                    return {"job_id":identity,"workspace_id":workspace_id,
                            "status":existing[2],"original_artistic_plan_preserved":True,
                            "existing_submission_reused":True}
                return self._coordinator.submit(ir,workspace_id=workspace_id,job_id=identity)
            return self._coordinator.submit(ir,workspace_id=workspace_id)
        job_id=arguments["job_id"]
        record=self._coordinator.inspect(job_id)
        self._workspace(record["workspace_id"])
        if action in ("pause","cancel"):
            return self._coordinator.request_control(job_id,action)
        return self._coordinator.retry_job(job_id,resume=action=="resume")
