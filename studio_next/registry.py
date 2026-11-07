"""Discoverable, least-privilege tool catalog. No arbitrary shell commands."""
from dataclasses import dataclass
from typing import Callable
from .contracts import ToolSpec, _json_like

def _check_technical_input_types(arguments,schema,tool_id):
    """Native minimal JSON-schema subset; code-owned constraints, no styles."""
    if not isinstance(schema,dict) or "properties" not in schema:
        return  # Existing/third-party tools still retain their trusted own checks.
    if schema.get("type")!="object" or not isinstance(schema["properties"],dict):
        raise ValueError("Malformed installed creative tool interface")
    if schema.get("additionalProperties") is False:
        extras=set(arguments)-set(schema["properties"])
        if extras:
            raise ValueError(f"{tool_id}: unapproved argument fields: "+", ".join(sorted(extras)))
    accepted={"string":str,"integer":int,"number":(int,float),
              "object":dict,"array":list,"boolean":bool}
    for key,value in arguments.items():
        entry=schema["properties"].get(key)
        if entry is None:
            continue
        if not isinstance(entry,dict) or entry.get("type") not in accepted:
            raise ValueError("Installed tool has an invalid machine-readable argument specification")
        kind=entry["type"]
        if kind in ("integer","number"):
            if isinstance(value,bool) or not isinstance(value,accepted[kind]):
                raise TypeError(f"{tool_id}: {key} must be a {kind}")
            import math
            if not math.isfinite(value):
                raise ValueError(f"{tool_id}: {key} must be finite")
            if "minimum" in entry and value<entry["minimum"]:
                raise ValueError(f"{tool_id}: {key} violates tool minimum")
        elif not isinstance(value,accepted[kind]):
            raise TypeError(f"{tool_id}: {key} must be a {kind}")


@dataclass
class _Entry:
    spec: ToolSpec
    runner: Callable | None
    idempotent: bool = False
    implementation_revision: str | None = None
    material_fingerprint: Callable | None = None

class ToolCatalog:
    def __init__(self):
        self._tools: dict[str,_Entry]={}
    def register(self,spec:ToolSpec,runner:Callable|None=None,*,
                 idempotent=False,implementation_revision=None,
                 material_fingerprint=None):
        if spec.tool_id in self._tools:
            raise ValueError(f"Duplicate tool {spec.tool_id}")
        if runner is not None and not callable(runner):
            raise TypeError("Runner must be a trusted registered callable")
        if not isinstance(idempotent,bool):
            raise ValueError("Trusted tool idempotency must be explicit")
        if implementation_revision is not None and (
                not isinstance(implementation_revision,str) or
                not implementation_revision.strip()):
            raise ValueError("Invalid actual executable revision")
        if material_fingerprint is not None and not callable(material_fingerprint):
            raise TypeError("Body source material verifier must be host-authorized callable")
        self._tools[spec.tool_id]=_Entry(spec,runner,idempotent,
                                         implementation_revision,material_fingerprint)
    def committed_tool_revisions(self):
        """Only registered runnable code can supply trusted cache versions."""
        return {name:item.implementation_revision
                for name,item in self._tools.items()
                if item.spec.status=="installed" and item.runner is not None
                and item.implementation_revision}
    def trusted_material_fingerprint(self,tool_id,inputs):
        entry=self._tools.get(tool_id)
        if entry is None or entry.runner is None or entry.material_fingerprint is None:
            raise ValueError("Installed tool has no physically verified source material adapter")
        return _json_like(entry.material_fingerprint(inputs))
    def trusted_idempotent_ids(self):
        """LLM tool arguments can never grant rerunnable side effects."""
        return {name for name,item in self._tools.items()
                if item.spec.status=="installed" and item.runner is not None
                and item.idempotent}

    def execution_admission(self, allowed_access=frozenset({"read","write"})):
        """Host fact: distinguish *discoverable* from *DAG-admissible* tools.

        A renderer/plug-in must have trusted source-material revalidation and
        a trusted implementation revision before the durable graph can safely
        accept it. A stateful native editor's presence in the catalog does not
        mean that it is a verifiable, retryable film DAG operation.

        This examines actual registered host-owned callables and versions. It
        does not invoke a tool, certify a rendered output or attribute model
        creativity. Generic future domains use the same contract.
        """
        permitted=frozenset(allowed_access)
        if not permitted or not permitted.issubset({"read","write"}):
            raise ValueError("Host execution admission needs read/write grants")
        result={}
        for identity,entry in self._tools.items():
            tool=entry.spec
            exposed=tool.status=="installed" and entry.runner is not None
            granted=tool.access in permitted
            revision=bool(entry.implementation_revision)
            materials=entry.material_fingerprint is not None
            dag=exposed and granted and revision and materials
            blockers=[]
            if not exposed:blockers.append("backend_not_installed")
            if not granted:blockers.append("access_not_granted")
            if exposed and not revision:blockers.append("no_committed_executor_revision")
            if exposed and not materials:blockers.append("no_trusted_material_fingerprint")
            result[identity]={
                "catalog_id":identity,
                "capability":tool.capability,
                "access":tool.access,
                "native_runner_registered":exposed,
                "trusted_material_adapter":materials,
                "committed_execution_revision":revision,
                "can_attempt_durable_graph":dag,
                "actually_executed_and_verified":False,
                "model_creative_quality_assessed":False,
                "blocked_by":blockers,
                "retry_requires_host_idempotence":not entry.idempotent,
            }
        return result
    def discover(self):
        return [entry.spec.public() for entry in self._tools.values()]
    def executable_ids(self, allowed_access=None):
        """Registered is not sufficient: proposals must respect granted permissions."""
        permitted=None if allowed_access is None else frozenset(allowed_access)
        return {k for k,v in self._tools.items()
                if v.spec.status=="installed" and v.runner is not None
                and (permitted is None or v.spec.access in permitted)}
    def invoke(self,tool_id,inputs,allowed_access=frozenset({"read"})):
        entry=self._tools.get(tool_id)
        if entry is None:raise ValueError(f"Unknown tool {tool_id!r}")
        spec=entry.spec
        if spec.status!="installed" or entry.runner is None:
            raise RuntimeError(f"Tool {tool_id} unavailable: {spec.status}")
        if spec.access not in allowed_access:
            raise PermissionError(f"Tool {tool_id} requires {spec.access} access")
        if not isinstance(inputs,dict):raise TypeError("Tool inputs must be an object")
        # The LLM only provides data: code entry points must be installed by a
        # trusted project maintainer. Do not eval/exec/subprocess LLM strings.
        arguments=_json_like(inputs)
        required=spec.operation_schema.get("required",[])
        for item in required:
            if item not in arguments:raise ValueError(f"Missing {tool_id} input: {item}")
        _check_technical_input_types(arguments,spec.operation_schema,tool_id)
        result=entry.runner(arguments)
        return _json_like(result)
