"""BODY somatic control surface: discover -> inspect -> preflight -> graph execute.

The creative intelligence is NOT taught an enormous markdown catalogue. This
machine-owned interface exposes only real registered affordances and their
selected schema, technical rights/fingerprint, permission and source state.
It does not author aesthetics, grant paid/network access, execute a tool,
or claim semantic understanding or premium artist quality.
"""
from __future__ import annotations

import hashlib
import json
import re

from .contracts import ACCESS_MODES
from .registry import ToolCatalog, _check_technical_input_types
from .body_document_schemas import document_contracts

_ID = re.compile(r"^[a-z][a-z0-9_.-]{1,100}$")
_CURSOR = re.compile(r"^([0-9]{1,6})\.([0-9a-f]{64})$")


def _fingerprint(value):
    wire=json.dumps(value,allow_nan=False,ensure_ascii=False,sort_keys=True,
                    separators=(",",":")).encode("utf-8")
    return hashlib.sha256(wire).hexdigest()


class BodyAffordanceSurface:
    """Read-only sensory part of the trusted BODY control loop.

    All original motor activity still goes through owner authorization and the
    durable film DAG, with its physical post-render verifier/lease/recovery.
    """
    def __init__(self, catalog, *, excluded_tool_ids=frozenset()):
        if not isinstance(catalog,ToolCatalog):
            raise TypeError("Only a trusted installed BODY catalog is sensed")
        if (not isinstance(excluded_tool_ids,frozenset) or
                any(not isinstance(name,str) for name in excluded_tool_ids)):
            raise TypeError("Only a host-owned immutable tool exclusion policy is valid")
        self.catalog=catalog
        self._excluded=excluded_tool_ids

    @staticmethod
    def _permissions(permitted):
        if not isinstance(permitted,(set,frozenset)) or not permitted or (
                not permitted.issubset(ACCESS_MODES)):
            raise ValueError("Explicit trusted permission set is required")
        return permitted

    def _actual(self):
        rows=self.catalog.discover()
        if len({r["id"] for r in rows})!=len(rows):
            raise ValueError("Duplicate physical tool identity")
        revisions=self.catalog.committed_tool_revisions()
        # An installed native editor with no immutable source adapter or
        # committed graph revision is still a real engine, but NOT an
        # executable film DAG node. Never silently present it as ready.
        admission=self.catalog.execution_admission()
        runnable={identity for identity,detail in admission.items()
                  if detail["can_attempt_durable_graph"]}
        retry=self.catalog.trusted_idempotent_ids()
        return sorted(rows,key=lambda r:r["id"]),revisions,runnable,retry,admission

    def discover(self, *, capability=None, allowed_access=frozenset({"read"}),
                 include_unavailable=False, limit=12, cursor=None):
        permitted=self._permissions(allowed_access)
        if capability is not None and (
                not isinstance(capability,str) or not capability.strip()
                or len(capability)>160):
            raise ValueError("Use an exact named capability, not a freeform prompt")
        if type(include_unavailable) is not bool or (
                type(limit) is not int or not 1<=limit<=40):
            raise ValueError("Bounded discovery and status policy required")
        rows,revisions,runnable,retry,admission=self._actual()
        indexed=[]
        for row in rows:
            if row["id"] in self._excluded:continue
            installed=row["id"] in runnable and row["status"]=="installed"
            if row["access"] not in permitted:continue
            if capability is not None and row["capability"]!=capability:continue
            if not installed and not include_unavailable:continue
            status=("ready_to_preflight" if installed else
                    "needs_setup" if row["status"]!="installed" else
                    "requires_execution_adapter")
            indexed.append({
                "tool_id":row["id"],"capability":row["capability"],
                "access":row["access"],
                "status":status,
                "execution_blockers":admission[row["id"]]["blocked_by"],
                "required_inputs":list(row["schema"].get("required",[])),
                "source_review_required":True,
                "safe_to_retry":installed and row["id"] in retry,
                "code_revision":revisions.get(row["id"]),
            })
        version=_fingerprint(indexed)
        offset=0
        if cursor is not None:
            if not isinstance(cursor,str) or not (match:=_CURSOR.fullmatch(cursor)):
                raise ValueError("Untrusted affordance pagination cursor")
            offset=int(match[1])
            if match[2]!=version or offset>=len(indexed):
                raise ValueError("Tool list changed or pagination cursor is invalid")
        page=indexed[offset:offset+limit]
        after=offset+len(page)
        return {"schema":1,"catalog_sha256":version,
                "affordances":page,"matched":len(indexed),
                "next_cursor":f"{after}.{version}" if after<len(indexed) else None,
                "no_creative_presets":True,
                "complete_studio_certified":False}

    def describe(self,tool_id,*,allowed_access=frozenset({"read"})):
        permitted=self._permissions(allowed_access)
        if not isinstance(tool_id,str) or not _ID.fullmatch(tool_id):
            raise ValueError("Exact named tool identity required")
        if tool_id in self._excluded:
            raise PermissionError("Model-facing BODY tool has no current source-rights custody")
        rows,revisions,runnable,retry,admission=self._actual()
        for row in rows:
            if row["id"]!=tool_id:continue
            if row["access"] not in permitted:
                raise PermissionError("Tool access not granted by trusted owner policy")
            live=row["status"]=="installed" and tool_id in runnable
            status=("ready_to_preflight" if live else
                    "needs_setup" if row["status"]!="installed" else
                    "requires_execution_adapter")
            return {"schema":1,"tool_id":tool_id,
                    "status":status,
                    "execution_blockers":admission[tool_id]["blocked_by"],
                    "input_schema":row["schema"] if live else None,
                    "document_contracts":document_contracts(tool_id),
                    "capability":row["capability"],"access":row["access"],
                    "limitations":row["limitations"],
                    "declared_license":row["license"],
                    "implementation_revision":revisions.get(tool_id),
                    "safe_to_retry":live and tool_id in retry,
                    "real_output_verified_by_this_lookup":False}
        raise ValueError("No installed or registered BODY operation with that ID")

    def preflight(self,tool_id,inputs,*,allowed_access=frozenset({"read"})):
        """Technical preparation only; caller still has to submit original Film IR.

        The preview is advisory: the durable graph independently re-reads and
        checks source bytes after the actual render before publishing output.
        """
        detail=self.describe(tool_id,allowed_access=allowed_access)
        if detail["status"]!="ready_to_preflight":
            raise RuntimeError("No installed backend for physical operation")
        if not isinstance(inputs,dict) or len(inputs)>64:
            raise TypeError("Bounded typed operation arguments required")
        spec=detail["input_schema"]
        missing=[key for key in spec.get("required",[]) if key not in inputs]
        if missing:raise ValueError("Missing operation arguments: "+", ".join(missing))
        _check_technical_input_types(inputs,spec,tool_id)
        sources=self.catalog.trusted_material_fingerprint(tool_id,inputs)
        if not isinstance(sources,(dict,list)) or (
                isinstance(sources,list) and len(sources)>100000):
            raise ValueError("Real source material witness outside BODY contract")
        return {"schema":1,"tool_id":tool_id,
                "code_revision":detail["implementation_revision"],
                "requested_inputs_sha256":_fingerprint(inputs),
                "observed_material_sha256":_fingerprint(sources),
                "material_witness_count":len(sources),
                "readiness":"preflight_checked_not_executed",
                "source_identity_must_be_rechecked_at_execution":True,
                "owner_authorization_to_execute_granted":False,
                "real_movie_rendered":False,
                "creative_quality_certified":False}
