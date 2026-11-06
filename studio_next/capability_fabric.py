"""ZX7 BODY machine-readable capability fabric, independent of creative domain.

The host owns authorization and actual tool schemas. A replaceable brain sees a
tiny discovery interface, searches relevant *installed/granted* operations and
asks for one exact schema. This is not a model prompt, a creative template or a
second permission layer. New source adapters contribute the same native shape.
No README/Markdown parsing, hosted search, embeddings or vendor dependency.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Mapping


class CapabilityContractError(ValueError):
    """An untrusted, absent, stale or invalid capability was selected."""


def _field(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _wire(item):
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def _tokens(value):
    # CamelCase and dot, slash, dash, underscore boundaries. This is small,
    # deterministic local retrieval, not a claim of semantic intelligence.
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    return set(re.findall(r"[^\W_]+", value.casefold(), re.UNICODE))



def _completed_tool_page(response):
    """Normalize one *complete* legacy or versioned MCP tools/list page.

    Pagination is permitted, but partial/interactive results and JSON-RPC
    errors never grant tool authority. Both discovery and gateway invocation
    use this function through discover_all_live_tools.
    """
    if _field(response, "error") is not None:
        raise CapabilityContractError("Native tool listing reported an RPC error")
    payload = _field(response, "result", response)
    if _field(payload, "resultType") not in (None, "complete"):
        raise CapabilityContractError("Native tool listing is not complete")
    received = _field(payload, "tools")
    if not isinstance(received, (list, tuple)):
        raise CapabilityContractError("Native tool page has no valid tool array")
    next_cursor = _field(payload, "nextCursor", _field(payload, "next_cursor"))
    return received, next_cursor


async def discover_all_live_tools(session):
    """Complete bounded MCP tools/list discovery, preserving opaque cursors.

    Supports modern Client(cursor=...) and official ClientSession(params=...).
    Repeated cursors or incomplete catalogs are failures, not hidden tools.
    """
    import inspect

    method = getattr(session, "list_tools", None)
    if not callable(method):
        raise CapabilityContractError("Connected source has no tools/list operation")
    try:
        parameters = inspect.signature(method).parameters
    except (TypeError, ValueError):
        parameters = {}
    cursor = None
    observed = set()
    tools = []
    for page_number in range(64):
        if cursor is None:
            page = await method()
        elif "cursor" in parameters:
            page = await method(cursor=cursor)
        elif "params" in parameters:
            from mcp.types import PaginatedRequestParams
            page = await method(params=PaginatedRequestParams(cursor=cursor))
        else:
            raise CapabilityContractError(
                "Paginated source requires an explicitly cursor-aware adapter")
        received, next_cursor = _completed_tool_page(page)
        if len(tools) + len(received) > 5000:
            raise CapabilityContractError("Complete tool catalog exceeds source budget")
        tools.extend(received)
        if next_cursor in (None, ""):
            return tools
        if (not isinstance(next_cursor, str) or
                len(next_cursor.encode("utf-8")) > 512 or
                next_cursor in observed):
            raise CapabilityContractError("Host repeated or malformed pagination cursor")
        observed.add(next_cursor)
        cursor = next_cursor
    raise CapabilityContractError("Native tool pagination exceeded maximum page count")


class CapabilityFabric:
    """Immutable, exact host-granted capability snapshot.

    Sources: mapping of namespace -> (MCP tools, trusted access grants), with
    optional third element: trusted machine preconditions keyed by tool name.
    A connected engine
    contributes only actual tools it advertised and the host explicitly
    authorized. Snapshots can be replaced when a source's catalog changes;
    stale references are rejected by the next snapshot's revision.
    """

    def __init__(self, sources: Mapping):
        if not isinstance(sources, Mapping) or not sources or len(sources) > 256:
            raise CapabilityContractError("At least one bounded real source is required")
        records = {}
        schema_bytes_total = 0
        for namespace, pair in sources.items():
            if (not isinstance(namespace, str) or
                    re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", namespace) is None or
                    not isinstance(pair, tuple) or len(pair) not in (2, 3, 4)):
                raise CapabilityContractError("Source identity and trusted grants required")
            tools, grants = pair[:2]
            requirements = pair[2] if len(pair) >= 3 else {}
            potential_enablers = pair[3] if len(pair) == 4 else {}
            if (not isinstance(requirements, Mapping) or
                    any(not isinstance(name, str) or
                        not isinstance(conditions, (list, tuple)) or
                        len(conditions) > 8 or
                        any(not isinstance(term, str) or
                            re.fullmatch(r"[a-z][a-z0-9_]{0,63}", term) is None
                            for term in conditions) or
                        len(set(conditions)) != len(conditions)
                        for name, conditions in requirements.items())):
                raise CapabilityContractError("Only trusted typed machine prerequisites are allowed")
            if any(name not in grants for name in requirements):
                raise CapabilityContractError("Prerequisite references an ungranted capability")
            if (not isinstance(potential_enablers, Mapping) or
                    any(not isinstance(name, str) or
                        not isinstance(facts, (list, tuple)) or
                        len(facts) > 8 or
                        any(not isinstance(v, str) or
                            re.fullmatch(r"[a-z][a-z0-9_]{0,63}", v) is None
                            for v in facts) or
                        len(set(facts)) != len(facts)
                        for name, facts in potential_enablers.items()) or
                    any(name not in grants for name in potential_enablers)):
                raise CapabilityContractError("Host potential effects require valid granted tools")
            if (not isinstance(tools, (list, tuple)) or len(tools) > 5000 or
                    not isinstance(grants, Mapping) or
                    any(not isinstance(k, str) or v not in ("read", "write")
                        for k, v in grants.items())):
                raise CapabilityContractError("Native source catalog/grants malformed")
            seen = set()
            for tool in tools:
                name = _field(tool, "name")
                schema = _field(tool, "input_schema", _field(tool, "inputSchema"))
                if (not isinstance(name, str) or not 0 < len(name) <= 160 or
                        any(ord(ch) < 32 for ch in name) or name in seen or
                        not isinstance(schema, dict)):
                    raise CapabilityContractError("Duplicate or malformed native tool")
                seen.add(name)
                if name not in grants:
                    continue
                identity = namespace + "/" + name
                desc = _field(tool, "description", "")
                if not isinstance(desc, str):
                    desc = ""
                # Avoid copying untrusted descriptions and giant schemas into
                # model context. Full trusted source schema remains local.
                summary = " ".join(desc[:1024].split())[:128]
                try:
                    schema_bytes = len(_wire(schema).encode("utf-8"))
                except (TypeError, ValueError, RecursionError) as exc:
                    raise CapabilityContractError("Unserializable native schema") from exc
                if schema_bytes > 512_000:
                    raise CapabilityContractError("Native schema exceeds host admission budget")
                schema_bytes_total += schema_bytes
                if schema_bytes_total > 32 * 1024 * 1024 or len(records) >= 10_000:
                    raise CapabilityContractError(
                        "All-source tool catalog exceeds memory safety budget")
                records[identity] = {
                    "operation_id": identity, "source": namespace,
                    "native_name": name, "description": summary,
                    "access": grants[name],
                    # Preserve the host's declared parameter order for
                    # compact model hints. Contract hashing remains canonical
                    # via _wire(sort_keys=True); the JSON roundtrip isolates
                    # our source snapshot from later host-side mutations.
                    "input_schema": json.loads(json.dumps(
                        schema, ensure_ascii=False, allow_nan=False)),
                    "schema_bytes": schema_bytes,
                    "name_tokens": _tokens(name + " " + namespace),
                    # Retrieval reads the COMPLETE bounded source-declared
                    # operation description, while the model still sees only
                    # the compact 128-char summary. Earlier source clipping
                    # removed "clip" from the native asset placement tool
                    # and biased "timeline clip add" toward marker operations.
                    # This is indexing, not new model authority or a script.
                    "description_tokens": _tokens(desc[:1024]),
                    "requires": list(requirements.get(name, ())),
                    # Potential effect is an affordance, NOT evidence that a
                    # later native call actually changed a project fact.
                    "may_enable": list(potential_enablers.get(name, ())),
                }
        if not records:
            raise CapabilityContractError("No executable host-granted capabilities")
        self._records = records
        self._namespaces = sorted(sources)
        # Exact local names remain an explicitly grounded retrieval route:
        # a brain that copied a real tool ID from BODY must not be trapped by
        # lexical ties with unrelated descriptions (as in the real 2B trial).
        # Keep namespace collisions visible rather than arbitrarily choosing
        # which engine owns a write.
        by_native_name = {}
        for identity, record in records.items():
            by_native_name.setdefault(record["native_name"], []).append(identity)
        self._exact_native_names = {
            name: tuple(sorted(ids)) for name, ids in by_native_name.items()}
        # Immutable inverted postings index over only host-discovered, granted
        # operations. Rare specialist terms examine only matching candidates;
        # neither entire tool schemas nor MD manuals enter neural context.
        postings = {}
        for ident, record in records.items():
            for term in record["name_tokens"] | record["description_tokens"]:
                postings.setdefault(term, set()).add(ident)
        self._postings = {term: frozenset(ids)
                          for term, ids in postings.items()}
        # A deterministic contract revision invalidates a stale model-side
        # selection even when the *name* is reused for a different ABI/grant.
        self.revision = hashlib.sha256(_wire([{
            "id": key, "access": value["access"],
            "summary": value["description"],
            # A changed host description can change search selection even
            # when its 128-character preview is unchanged. Version the
            # retrieval vocabulary with the executable native ABI.
            "search_tokens_sha256": hashlib.sha256(
                _wire(sorted(value["description_tokens"])).encode(
                    "utf-8")).hexdigest(),
            "schema": value["input_schema"],
            "requires": value["requires"], "may_enable": value["may_enable"]
        } for key, value in sorted(records.items())]).encode("utf-8")).hexdigest()

    @classmethod
    async def from_connections(cls, connections: Mapping):
        """Refresh live machine contracts from connected, authorized engines.

        No MD or guessed capability list. Every source supplies a real
        list_tools interface plus host-owned grants; omitted/ungranted tools
        never enter the model catalog. A changed snapshot receives a new
        revision so stale model decisions fail closed at the boundary.
        """
        if not isinstance(connections, Mapping) or not 1 <= len(connections) <= 256:
            raise CapabilityContractError("Real connected source inventory required")
        sources = {}
        for namespace, binding in connections.items():
            if not isinstance(binding, tuple) or len(binding) not in (2, 3, 4):
                raise CapabilityContractError("Source requires session and host grants")
            session, grants = binding[:2]
            if not callable(getattr(session, "list_tools", None)):
                raise CapabilityContractError("Native source lacks live tool discovery")
            advertised = await discover_all_live_tools(session)
            requirements = binding[2] if len(binding) >= 3 else {}
            enablers = binding[3] if len(binding) == 4 else {}
            sources[namespace] = (advertised, grants, requirements, enablers)
        return cls(sources)

    @property
    def count(self):
        return len(self._records)

    def overview(self, *, include_search_facets=False):
        """Tiny default, optional bounded host-grounded navigation vocabulary.

        Only actual authorized native operation *names* contribute terms. Tool
        descriptions are untrusted and excluded; no new tools, permissions,
        operation suggestions or creative sequence are invented. A specialist
        brain can independently search any term; facets are not executable.
        """
        if type(include_search_facets) is not bool:
            raise CapabilityContractError("Capability overview facets require a boolean")
        counts = {key: 0 for key in self._namespaces}
        for value in self._records.values():
            counts[value["source"]] += 1
        result = {"revision": self.revision, "operation_count": self.count,
                  "sources": counts, "discovery": "search_then_describe"}
        if include_search_facets:
            from collections import Counter
            terms = Counter()
            for record in self._records.values():
                terms.update(word for word in _tokens(record["native_name"])
                             if 3 <= len(word) <= 24)
            result["host_granted_search_terms"] = [
                word for word, _ in sorted(
                    terms.items(), key=lambda item: (-item[1], item[0]))[:16]]
            # Measured Qwen3.5-2B trial #41160412292 exposed a concrete
            # information-loss problem: the top-16 frequent tokens included
            # "asset"/"add" but omitted "import", although the connected
            # host actually granted import_asset_from_path. The model searched
            # "asset" and guessed an edit without importing source footage.
            # Preserve the distinct FIRST token of real native operation
            # names as a second, separately bounded navigation vocabulary.
            # These are NOT suggested actions, permissions, executable IDs,
            # scripted workflow steps, or tokens from untrusted descriptions.
            prefixes = set()
            for record in self._records.values():
                name = re.sub(r"(?<=[a-z])(?=[A-Z])", "_",
                              record["native_name"])
                prefix = name.split("_", 1)[0].casefold()
                if (3 <= len(prefix) <= 24 and
                        prefix.isalnum() and prefix in _tokens(name)):
                    prefixes.add(prefix)
            result["host_granted_action_prefixes"] = []
            for prefix in sorted(prefixes):
                if len(result["host_granted_action_prefixes"]) >= 32:
                    break
                candidate = dict(result)
                candidate["host_granted_action_prefixes"] = [
                    *result["host_granted_action_prefixes"], prefix]
                candidate["terms_are_search_hints_not_execution_grants"] = True
                candidate["action_prefixes_may_be_incomplete"] = True
                # Reserve headroom for ordinary JSON serializers that add
                # whitespace and the terminal truncation flag. The public
                # overview remains <=900 bytes even without compact encoding.
                if len(json.dumps(candidate).encode("utf-8")) <= 860:
                    result["host_granted_action_prefixes"].append(prefix)
            result["action_prefixes_may_be_incomplete"] = (
                len(result["host_granted_action_prefixes"]) < len(prefixes))
            result["terms_are_search_hints_not_execution_grants"] = True
        return result

    def search(self, query: str, *, limit: int = 6):
        if (not isinstance(query, str) or not query.strip() or
                len(query.encode("utf-8")) > 160 or
                type(limit) is not int or not 1 <= limit <= 8):
            raise CapabilityContractError("Use a bounded descriptive capability query")
        # Exact host-granted operation identity is stronger than any lexical
        # similarity. This never invents a tool, widens grants or authorizes
        # dispatch: it only returns the existing contract for model inspection.
        # An unqualified name shared by multiple engines remains an explicit
        # bounded tie, never an arbitrary winner.
        exact = query.strip()
        exact_ids = ((exact,) if exact in self._records
                     else self._exact_native_names.get(exact, ()))
        terms = _tokens(query)
        # Even a source-declared punctuation-only tool ID can be explicitly
        # retrieved; free-form punctuation with no exact match still fails.
        if not terms and not exact_ids:
            raise CapabilityContractError("Search query has no searchable terms")
        candidates = set(exact_ids)
        scored = []
        if exact_ids:
            scored = [(-1_000_000, ident, self._records[ident])
                      for ident in exact_ids]
        else:
            for term in terms:
                candidates.update(self._postings.get(term, ()))
            for ident in candidates:
                record = self._records[ident]
                name_hits = terms & record["name_tokens"]
                desc_hits = terms & record["description_tokens"]
                if not (name_hits or desc_hits):
                    continue
                # Deterministic all-term preference, then identity similarity.
                covered = len(name_hits | desc_hits)
                score = (100 * (covered == len(terms)) + 10 * covered +
                         5 * len(name_hits) + len(desc_hits))
                scored.append((-score, ident, record))
        scored.sort(key=lambda x: (x[0], x[1]))
        # A tiny specialist must not treat arbitrary alphabetical tie-breaks
        # as an informed choice between different creative write operations.
        # Return bounded *non-invokable* examples until the brain refines intent.
        if len(scored) > limit and scored[limit][0] == scored[limit - 1][0]:
            examples = [{"id": ident, "description": rec["description"][:96],
                         "access": rec["access"]}
                        for _, ident, rec in scored[:6]]
            return {"revision": self.revision, "matches": [],
                    "has_more": True, "requires_refinement": True,
                    "candidate_examples": examples,
                    "candidates_examined": len(candidates)}
        items = []
        for _, ident, record in scored[:limit]:
            schema = record["input_schema"]
            props = schema.get("properties")
            param_names = list(props)[:6] if isinstance(props, dict) else []
            items.append({"id": ident, "description": record["description"][:96],
                          "access": record["access"],
                          "parameters_sample": param_names,
                          "requires": record["requires"],
                          "may_enable": record["may_enable"]})
        return {"revision": self.revision, "matches": items,
                "has_more": len(scored) > limit,
                "requires_refinement": False,
                "candidates_examined": len(candidates)}

    def describe(self, operation_id: str, *, revision: str, max_schema_bytes=16_384):
        record = self.resolve(operation_id, revision=revision)
        if type(max_schema_bytes) is not int or not 512 <= max_schema_bytes <= 65_536:
            raise CapabilityContractError("Invalid bounded schema budget")
        if record["schema_bytes"] > max_schema_bytes:
            return {"operation_id": operation_id, "revision": self.revision,
                    "schema_too_large": True,
                    "required_schema_bytes": record["schema_bytes"]}
        return {"operation_id": operation_id, "revision": self.revision,
                "access": record["access"],
                "requires": record["requires"],
                "may_enable": record["may_enable"],
                "input_schema": record["input_schema"],
                "description": record["description"]}

    def resolve(self, operation_id: str, *, revision: str):
        if not isinstance(revision, str) or revision != self.revision:
            raise CapabilityContractError("Stale capability catalog revision")
        if not isinstance(operation_id, str) or operation_id not in self._records:
            raise CapabilityContractError("Unknown or ungranted BODY capability")
        return copy.deepcopy(self._records[operation_id])

    def affordance_frontier(self, *, trusted_facts: Mapping,
                            limit: int = 4, namespace: str | None = None):
        """Show bounded real operations able to enable currently missing facts.

        Only the trusted host supplies the facts and possible machine effects.
        This is not a recipe, recommended aesthetic choice, executable grant or
        success prediction. The creative model independently selects an action.
        """
        if (not isinstance(trusted_facts, Mapping) or
                any(not isinstance(key, str) or type(value) is not bool
                    for key, value in trusted_facts.items()) or
                type(limit) is not int or not 1 <= limit <= 8):
            raise CapabilityContractError("Host-attested boolean fact state required")
        if namespace is not None and namespace not in self._namespaces:
            raise CapabilityContractError("Unknown trusted creative source")
        needed = {key for key, value in trusted_facts.items() if not value}
        items = []
        for identifier, record in sorted(self._records.items()):
            if namespace is not None and record["source"] != namespace:
                continue
            enables = needed.intersection(record["may_enable"])
            if not enables:
                continue
            readiness = self.check_prerequisites(
                identifier, revision=self.revision, trusted_facts=trusted_facts)
            if not readiness["admissible"]:
                continue
            items.append({"id": identifier,
                          "description": record["description"][:96],
                          "access": record["access"],
                          "may_enable": sorted(enables),
                          "parameters_sample": list(
                              record["input_schema"].get("properties", {}))[:6]})
        return {"revision": self.revision,
                "matches": items[:limit],
                "has_more": len(items) > limit,
                "facts_are_host_attested": True,
                "effects_are_possibilities_not_verified_results": True}

    def check_prerequisites(self, operation_id: str, *, revision: str,
                           trusted_facts: Mapping):
        """Advisory machine-state check from the trusted host, never model text.

        An unknown fact is NOT false and is NOT an authorization to execute.
        Actual native host validation/approval remains mandatory on every
        write. No tool execution or model creativity is implied by this check.
        """
        record = self.resolve(operation_id, revision=revision)
        if (not isinstance(trusted_facts, Mapping) or
                any(not isinstance(k, str) or type(v) is not bool
                    for k, v in trusted_facts.items())):
            raise CapabilityContractError("Only host-attested boolean state is permitted")
        missing = [x for x in record["requires"] if x not in trusted_facts]
        blocked = [x for x in record["requires"] if trusted_facts.get(x) is False]
        return {"operation_id": operation_id, "revision": self.revision,
                "admissible": not (missing or blocked),
                "unknown_state": missing, "unsatisfied": blocked}
