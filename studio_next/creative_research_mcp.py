"""Opt-in MCP research and host-granted local video-reference inspection.

Starting this local MCP process authorizes its fixed free public HTTPS
endpoints by default; the host can disable all network calls. The model cannot grant itself
network access, arbitrary URLs, downloads or paid generation.
"""
from __future__ import annotations

import argparse
import asyncio
import json

from .creative_research import CreativeResearch, CreativeResearchError
from .creative_research_hub import CreativeResearchHub


_TOOL_DEFINITIONS = (
    ("research_creative",
     "Independent creative-domain research across every installed free public "
     "source. Discover visuals, sound, video references, animation, storytelling, "
     "design technique, audience papers and other creative knowledge. Returned "
     "leads cannot themselves authorize copyright reuse, even when CC0 declared.",
     {"type": "object", "properties": {
         "query": {"type": "string", "minLength": 1, "maxLength": 240},
         "domain": {"type": "string", "enum": ["all", "assets", "knowledge", "scholarship"]},
         "media": {"type": "string", "enum": ["all", "image", "audio", "video", "3d"]},
         "limit": {"type": "integer", "minimum": 1, "maximum": 12}},
      "required": ["query"], "additionalProperties": False}),
    ("research_assets",
     "Research CC0/public-domain footage, visual and audio *candidate* metadata. "
     "Rights are NOT independently verified, assets are NOT downloaded.",
     {"type": "object", "properties": {
         "query": {"type": "string", "minLength": 1, "maxLength": 240},
         "media": {"type": "string", "enum": ["image", "audio", "video"]},
         "limit": {"type": "integer", "minimum": 1, "maximum": 12}},
      "required": ["query", "media"], "additionalProperties": False}),
    ("research_studies",
     "Research scholarly metadata about storytelling, pacing, visual perception "
     "or audience behavior. Records are leads, NOT accepted scientific claims.",
     {"type": "object", "properties": {
         "query": {"type": "string", "minLength": 1, "maxLength": 240},
         "limit": {"type": "integer", "minimum": 1, "maximum": 12}},
      "required": ["query"], "additionalProperties": False}),
)


def create_research_server(*, allow_public_research=True, research_client=None,
                           research_hub=None, reference_root=None, memory_path=None):
    """Use official MCP SDK; requires an explicit host-side network grant."""
    if memory_path is not None and reference_root is None:
        raise PermissionError("Reference study memory requires host-granted local source folder")
    if type(allow_public_research) is not bool or (not allow_public_research and reference_root is None):
        raise PermissionError("Host must permit public research or grant local reference media")
    import anyio
    import jsonschema
    from mcp.server import Server
    from mcp import types

    client = research_client if research_client is not None else CreativeResearch()
    hub = research_hub if research_hub is not None else CreativeResearchHub.installed()
    operations = ({
        "research_creative": (_TOOL_DEFINITIONS[0][2], hub.research),
        "research_assets": (_TOOL_DEFINITIONS[1][2], client.assets),
        "research_studies": (_TOOL_DEFINITIONS[2][2], client.studies),
    } if allow_public_research else {})
    tools = ([types.Tool(name=name, description=description, inputSchema=schema)
              for name, description, schema in _TOOL_DEFINITIONS]
             if allow_public_research else [])
    if reference_root is not None:
        from pathlib import Path
        from .reference_evidence_tools import inspect_authorized_reference
        approved_root = Path(reference_root).resolve(strict=True)
        if not approved_root.is_dir():
            raise ValueError("Local reference root must be an existing directory")
        observation_schema = {"type":"object",
            "properties":{
                "reference":{"type":"string","minLength":1,"maxLength":1024},
                "bins":{"type":"integer","minimum":8,"maximum":256}},
            "required":["reference"],"additionalProperties":False}
        def inspect(*, reference, bins=64):
            return inspect_authorized_reference(approved_root, reference, bins=bins)
        operations["observe_authorized_reference"] = (observation_schema, inspect)
        tools.append(types.Tool(
            name="observe_authorized_reference",
            description=("Decode host-granted local reference footage into measured "
                         "editing change and actual sound-energy graphs. Not a cinematic "
                         "quality score, video-semantic judgment or a YouTube download."),
            inputSchema=observation_schema))
        if memory_path is not None:
            from .creative_evidence_memory import CreativeEvidenceMemory
            memory = CreativeEvidenceMemory(memory_path)
            def study(*, reference, bins=64):
                report = inspect_authorized_reference(
                    approved_root, reference, bins=bins)
                receipt = memory.store(report)
                return {**receipt, "source_sha256": report["source_sha256"],
                        "schema": "ZX7_STORED_REFERENCE_STUDY_V1",
                        "raw_video_or_audio_persisted": False,
                        "trained_model_weights": False}
            def recall(*, id):
                record = memory.recall(id)
                return {"found": record is not None, "evidence": record}
            def recent(*, limit=10):
                return {"records": memory.recent(limit=limit),
                        "capacity": memory.usage()}
            id_schema = {"type":"object",
                "properties":{"id":{"type":"string","pattern":"^[0-9a-f]{64}$"}},
                "required":["id"],"additionalProperties":False}
            recent_schema = {"type":"object",
                "properties":{"limit":{"type":"integer","minimum":1,"maximum":100}},
                "additionalProperties":False}
            additions = (
                ("study_authorized_reference", observation_schema, study,
                 "Observe host-authorized local video and persist only bounded "
                 "compressed source-bound graphs. No video/audio bytes are retained."),
                ("recall_reference_case", id_schema, recall,
                 "Retrieve a previously physically measured reference case by exact case ID."),
                ("recent_reference_cases", recent_schema, recent,
                 "List bounded metadata of measured editing references in shared memory; "
                 "not performance rankings or learned creative tastes."),
            )
            for name, schema, handler, description in additions:
                operations[name] = (schema, handler)
                tools.append(types.Tool(name=name, description=description,
                                        inputSchema=schema))
    capacity = anyio.CapacityLimiter(2)

    async def list_tools(_context, _params=None):
        return types.ListToolsResult(tools=tools)

    async def call_tool(_context, params):
        target = operations.get(params.name)
        if target is None:
            return types.CallToolResult(is_error=True, content=[
                types.TextContent(type="text", text="Unregistered research operation")])
        schema, handler = target
        arguments = params.arguments or {}
        error = next(jsonschema.Draft202012Validator(schema).iter_errors(arguments), None)
        if error is not None:
            return types.CallToolResult(is_error=True, content=[
                types.TextContent(type="text", text="Research parameters violate trusted schema")])
        try:
            async with capacity:
                result = await anyio.to_thread.run_sync(lambda: handler(**arguments))
            encoded = json.dumps(result, allow_nan=False, ensure_ascii=False)
            if len(encoded.encode("utf-8")) > 64_000:
                raise CreativeResearchError("Bounded research result exceeded")
        except (CreativeResearchError, ValueError, TypeError):
            # No remote response body, owner prompt or traceback is exposed.
            return types.CallToolResult(is_error=True, content=[
                types.TextContent(type="text", text="Public research unavailable or refused")])
        return types.CallToolResult(is_error=False, content=[
            types.TextContent(type="text", text=encoded)])

    return Server("zx7-creative-research", version="0.1.0",
                  on_list_tools=list_tools, on_call_tool=call_tool)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disable-public-research", action="store_true",
                        help="Host-owned kill switch for fixed public research endpoints")
    parser.add_argument("--reference-root",
                        help="Optional host-granted local media directory for actual reference-video observation")
    parser.add_argument("--memory-path",
                        help="Optional host-approved persistent SQLite measured-reference memory; requires --reference-root")
    args = parser.parse_args(argv)
    try:
        server = create_research_server(
            allow_public_research=not args.disable_public_research,
            reference_root=args.reference_root,
            memory_path=args.memory_path)
    except PermissionError as exc:
        parser.error(str(exc))
    from mcp.server.stdio import stdio_server

    async def serve():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(serve())


if __name__ == "__main__":
    main()
