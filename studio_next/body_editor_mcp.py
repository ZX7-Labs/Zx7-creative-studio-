"""Standard MCP stdio bridge to a host-granted local native editor.

The optional official SDK owns protocol negotiation and stdio framing. Native
schemas and results remain native; this module adds host grants, input-schema
validation and serial execution for the editor's single active project.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import hashlib
import math
import subprocess
from pathlib import Path
import sys

from .body_editor_client import (
    EditorAccessError, EditorClientError, EditorToolError, _access_modes,
)


def _local_schema_references(schema):
    """Validation must never fetch a schema or another hosted dependency."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in ("$ref", "$dynamicRef", "$recursiveRef") and (
                    not isinstance(value, str) or not value.startswith("#")):
                raise ValueError("Native schema has a nonlocal reference")
            _local_schema_references(value)
    elif isinstance(schema, list):
        for item in schema:
            _local_schema_references(item)


def native_admission_validator(schema):
    """One strict, source-native JSON Schema boundary for every BODY path.

    The advertised native schema remains byte-for-byte unchanged; only
    model-authored TOP-LEVEL fields outside the declared interface are
    refused where upstream omitted additionalProperties. Nested artistic
    data keeps the source's intended extensibility and JSON Schema dialect.
    This does not grant tools, execute an operation or fetch remote schemas.
    """
    import copy
    import jsonschema
    if not isinstance(schema, dict):
        raise ValueError("Native editor schema must be a JSON object")
    _local_schema_references(schema)
    admission=copy.deepcopy(schema)
    if (isinstance(admission.get("properties"),dict)
            and "additionalProperties" not in admission
            and "patternProperties" not in admission):
        admission["additionalProperties"]=False
    validator=jsonschema.validators.validator_for(admission)
    validator.check_schema(admission)
    return validator(admission)


def create_editor_server(client, *, allowed_access=frozenset({"read"}),
                         export_verifier=None, frame_observer=None,
                         audio_observer=None, audio_timeline_observer=None):
    """Return the official SDK server; discovery never expands host grants.

    Dependencies are imported here so the stdlib BODY remains usable without
    the optional ``editor`` extra. Schemas are checked once against actual
    discovery before the protocol server can advertise any operation.
    """
    import anyio
    import jsonschema
    from mcp.server import Server
    from mcp import types

    access = _access_modes(allowed_access)
    native = {tool["name"]: tool for tool in client.list_tools()}
    grants = dict(client.allowed_tools)
    if set(grants) - set(native):
        raise ValueError("Host-granted native editor tool is absent from discovery")
    tools = {}
    validators = {}
    for name, mode in grants.items():
        if mode not in access:
            continue
        schema = native[name]["inputSchema"]
        validators[name] = native_admission_validator(schema)
        tools[name] = types.Tool.model_validate(native[name])
    verified_export_name = "zx7_verify_native_export"
    observed_frame_name = "zx7_observe_verified_export_frame"
    observed_samples_name = "zx7_observe_verified_export_samples"
    observed_audio_name = "zx7_observe_verified_export_audio"
    observed_audio_timeline_name = "zx7_observe_verified_export_audio_timeline"
    verified_exports = {}
    if frame_observer is not None and (export_verifier is None or not callable(frame_observer)):
        raise ValueError("Frame observation requires a real host export verifier")
    if audio_observer is not None and (export_verifier is None or not callable(audio_observer)):
        raise ValueError("Audio observation requires a real host export verifier")
    if audio_timeline_observer is not None and (export_verifier is None or not callable(audio_timeline_observer)):
        raise ValueError("Audio timeline requires the full host export verifier")
    if any(tool in native for tool in (observed_frame_name, observed_samples_name,
                                       observed_audio_name, observed_audio_timeline_name)):
        raise ValueError("Native editor tool name collides with BODY observation")
    if export_verifier is not None:
        if not callable(export_verifier) or verified_export_name in native:
            raise ValueError("Invalid host export verifier or native tool name collision")
        if "read" in access:
            schema = {"type": "object",
                      "properties": {
                          "path": {"type": "string"},
                          "expected": {"type": "object",
                                       "properties": {
                                           "width": {"type": "integer", "minimum": 1},
                                           "height": {"type": "integer", "minimum": 1},
                                           "duration_seconds": {"type": "number", "exclusiveMinimum": 0},
                                           "require_audio": {"type": "boolean"}},
                                       "additionalProperties": False}},
                      "required": ["path"], "additionalProperties": False}
            tools[verified_export_name] = types.Tool(
                name=verified_export_name,
                description="Decode and independently verify an authorized finished native video export; not an artistic-quality score",
                inputSchema=schema)
            validators[verified_export_name] = jsonschema.Draft202012Validator(schema)
    if frame_observer is not None and "read" in access:
        frame_schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "at_seconds": {"type": "number", "minimum": 0}},
            "required": ["path", "at_seconds"], "additionalProperties": False}
        tools[observed_frame_name] = types.Tool(
            name=observed_frame_name,
            description="View one actual decoded bounded PNG from a previously verified native export; not full-motion review",
            inputSchema=frame_schema)
        validators[observed_frame_name] = jsonschema.Draft202012Validator(frame_schema)
        # A small, explicit sample set provides temporal context without
        # pretending to be a continuous video/audio playback interface.
        samples_schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "at_seconds": {
                    "type": "array", "minItems": 2, "maxItems": 4,
                    "uniqueItems": True,
                    "items": {"type": "number", "minimum": 0}}},
            "required": ["path", "at_seconds"], "additionalProperties": False}
        tools[observed_samples_name] = types.Tool(
            name=observed_samples_name,
            description=("Observe 2-4 independently decoded frames from a fully verified "
                         "native editor export, in requested timestamp order; not proof "
                         "of continuous motion, sound or artistic quality"),
            inputSchema=samples_schema)
        validators[observed_samples_name] = jsonschema.Draft202012Validator(samples_schema)
    if audio_observer is not None and "read" in access:
        audio_schema = {"type": "object", "properties": {
            "path": {"type": "string"},
            "start_seconds": {"type": "number", "minimum": 0},
            "duration_seconds": {"type": "number", "exclusiveMinimum": 0,
                                 "maximum": 3.0}},
            "required": ["path", "start_seconds", "duration_seconds"],
            "additionalProperties": False}
        tools[observed_audio_name] = types.Tool(
            name=observed_audio_name,
            description=("Hear a bounded actual PCM WAV excerpt of a previously "
                         "fully verified native export; downmixed 16 kHz mono, "
                         "not spatial mastering, transcript or full-film listening"),
            inputSchema=audio_schema)
        validators[observed_audio_name] = jsonschema.Draft202012Validator(audio_schema)
    if audio_timeline_observer is not None and "read" in access:
        temporal_schema = {"type": "object", "properties": {
            "path": {"type": "string"},
            "start_seconds": {"type": "number", "minimum": 0},
            "duration_seconds": {"type": "number", "exclusiveMinimum": 0,
                                 "maximum": 300},
            "bins": {"type": "integer", "minimum": 2, "maximum": 256}},
            "required": ["path", "start_seconds", "duration_seconds", "bins"],
            "additionalProperties": False}
        tools[observed_audio_timeline_name] = types.Tool(
            name=observed_audio_timeline_name,
            description=("Observe independently decoded, per-time-bin native video audio "
                         "peak/RMS for a bounded interval; diagnostic 8 kHz mono, not "
                         "original PTS, LUFS, multichannel master or artistic quality"),
            inputSchema=temporal_schema)
        validators[observed_audio_timeline_name] = jsonschema.Draft202012Validator(temporal_schema)
    lock = anyio.Lock()
    inspection_capacity = anyio.CapacityLimiter(1)

    def failed(message):
        return types.CallToolResult(is_error=True,
            content=[types.TextContent(type="text", text=message)])

    async def list_tools(_ctx, _params):
        return types.ListToolsResult(tools=list(tools.values()))

    async def call_tool(_ctx, params):
        name = params.name
        if name not in tools:
            return failed("Native tool is not granted for this MCP session")
        arguments = params.arguments if params.arguments is not None else {}
        try:
            validators[name].validate(arguments)
        except jsonschema.ValidationError as exc:
            return failed("Invalid native tool arguments: " + exc.message)
        if name == verified_export_name:
            try:
                async with inspection_capacity:
                    with anyio.CancelScope(shield=True):
                        proof = await anyio.to_thread.run_sync(
                            lambda: export_verifier(arguments["path"], expected=arguments.get("expected")),
                            abandon_on_cancel=False)
                if proof.get("physical_export_verified") is not True or not isinstance(
                        proof.get("native_export_sha256"), str):
                    return failed("Independent export verifier produced no trusted source-bound receipt")
                verified_exports[str(Path(arguments["path"]).resolve())] = proof["native_export_sha256"]
                while len(verified_exports) > 16:
                    verified_exports.pop(next(iter(verified_exports)))
                return types.CallToolResult(is_error=False, content=[
                    types.TextContent(type="text", text=json.dumps(proof, allow_nan=False))])
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                return failed("Independent native export verification failed: " + str(exc))
        if name in (observed_frame_name, observed_samples_name):
            samples_mode = name == observed_samples_name
            times = arguments["at_seconds"] if samples_mode else [arguments["at_seconds"]]
            if (any(type(at) not in (int, float) or not math.isfinite(at)
                    for at in times) or
                    (samples_mode and any(a >= b for a, b in zip(times, times[1:])))):
                return failed("Frame sample times must be finite and strictly increasing")
            identity = str(Path(arguments["path"]).resolve())
            digest = verified_exports.get(identity)
            if digest is None:
                return failed("Independently verify these physical export bytes before observing a frame")
            try:
                async with inspection_capacity:
                    with anyio.CancelScope(shield=True):
                        # All frames are sampled under one bounded inspection
                        # lease. Never return partial images after any failure.
                        observations = await anyio.to_thread.run_sync(
                            lambda: [frame_observer(
                                arguments["path"], verified_sha256=digest,
                                at_seconds=at) for at in times],
                            abandon_on_cancel=False)
                total_bytes = 0
                for (png, receipt), at in zip(observations, times):
                    if not isinstance(png, bytes) or not isinstance(receipt, dict):
                        raise ValueError("Invalid independent decoder observation")
                    total_bytes += len(png)
                    if (
                            receipt.get("export_sha256") != digest or
                            receipt.get("png_sha256") != hashlib.sha256(png).hexdigest() or
                            receipt.get("sampled_video_seconds_requested") != at or
                            len(png) > 4 * 1024 * 1024 or
                            total_bytes > 8 * 1024 * 1024):
                        raise ValueError("Incomplete, stale or oversized visual evidence")
                if samples_mode:
                    receipt = {
                        "schema": 1,
                        "kind": "verified_native_editor_selected_frames",
                        "export_sha256": digest,
                        "samples": [sample_receipt for _, sample_receipt in observations],
                        "exact_presentation_timestamps_proven": False,
                        "continuous_motion_or_audio_proven": False,
                        "human_or_artistic_quality_approved": False,
                    }
                else:
                    receipt = observations[0][1]
                return types.CallToolResult(is_error=False, content=[
                    types.TextContent(type="text", text=json.dumps(receipt, allow_nan=False)),
                    *[types.ImageContent(
                        type="image", data=base64.b64encode(png).decode("ascii"),
                        mimeType="image/png") for png, _ in observations]])
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                verified_exports.pop(identity, None)
                return failed("Verified native frame observation failed: " + str(exc))
        if name == observed_audio_name:
            identity = str(Path(arguments["path"]).resolve())
            digest = verified_exports.get(identity)
            if digest is None:
                return failed("Independently verify these physical export bytes before listening")
            try:
                async with inspection_capacity:
                    with anyio.CancelScope(shield=True):
                        wav_bytes, receipt = await anyio.to_thread.run_sync(
                            lambda: audio_observer(
                                arguments["path"], verified_sha256=digest,
                                start_seconds=arguments["start_seconds"],
                                duration_seconds=arguments["duration_seconds"]),
                            abandon_on_cancel=False)
                if (not isinstance(wav_bytes, bytes) or
                        not 44 <= len(wav_bytes) <= 128 * 1024 or
                        not isinstance(receipt, dict) or
                        receipt.get("export_sha256") != digest or
                        receipt.get("wav_sha256") != hashlib.sha256(wav_bytes).hexdigest() or
                        receipt.get("requested_start_seconds") != arguments["start_seconds"] or
                        receipt.get("requested_duration_seconds") != arguments["duration_seconds"]):
                    raise ValueError("Audio excerpt lacks valid source-bound evidence")
                return types.CallToolResult(is_error=False, content=[
                    types.TextContent(type="text", text=json.dumps(receipt, allow_nan=False)),
                    types.AudioContent(type="audio",
                                       data=base64.b64encode(wav_bytes).decode("ascii"),
                                       mimeType="audio/wav")])
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                verified_exports.pop(identity, None)
                return failed("Verified native audio observation failed: " + str(exc))
        if name == observed_audio_timeline_name:
            identity = str(Path(arguments["path"]).resolve())
            digest = verified_exports.get(identity)
            if digest is None:
                return failed("Independently verify these physical export bytes before audio analysis")
            try:
                values = (arguments["start_seconds"], arguments["duration_seconds"])
                if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
                    raise ValueError("Audio timeline timestamps must be finite")
                async with inspection_capacity:
                    with anyio.CancelScope(shield=True):
                        receipt = await anyio.to_thread.run_sync(
                            lambda: audio_timeline_observer(
                                arguments["path"], verified_sha256=digest,
                                start_seconds=arguments["start_seconds"],
                                duration_seconds=arguments["duration_seconds"],
                                bins=arguments["bins"]),
                            abandon_on_cancel=False)
                if (not isinstance(receipt, dict) or
                        receipt.get("kind") != "verified_native_editor_audio_temporal_envelope" or
                        receipt.get("export_sha256") != digest or
                        receipt.get("requested_start_seconds") != arguments["start_seconds"] or
                        receipt.get("requested_duration_seconds") != arguments["duration_seconds"] or
                        not isinstance(receipt.get("intervals"), list) or
                        len(receipt["intervals"]) != arguments["bins"]):
                    raise ValueError("Audio timeline lacked source-bound temporal evidence")
                return types.CallToolResult(is_error=False, content=[
                    types.TextContent(type="text", text=json.dumps(receipt, allow_nan=False))])
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                verified_exports.pop(identity, None)
                return failed("Verified audio timeline failed: " + str(exc))
        try:
            # Do not abandon a possibly applied write on protocol cancellation.
            # The lock stays held until the bounded native HTTP call finishes.
            async with lock:
                with anyio.CancelScope(shield=True):
                    result = await anyio.to_thread.run_sync(
                        lambda: client.call(name, arguments, allowed_access=access),
                        abandon_on_cancel=False)
            return types.CallToolResult.model_validate(result)
        except EditorToolError as exc:
            return types.CallToolResult.model_validate(exc.result)
        except (EditorAccessError, PermissionError, ValueError) as exc:
            return failed(str(exc))
        except EditorClientError as exc:
            uncertain = (" A write may already have occurred; inspect native state before retrying."
                         if grants[name] == "write" else "")
            return failed(str(exc) + uncertain)

    return Server("zx7-native-editor", version="0.1.0",
                  on_list_tools=list_tools, on_call_tool=call_tool)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path,
                        help="Host-owned editor grants and workspace roots")
    parser.add_argument("--print-launch-config", action="store_true",
                        help="Validate and print canonical roots without contacting the editor")
    options = parser.parse_args(argv)
    try:
        from .body_editor_policy import load_editor_config
        config = load_editor_config(options.config)
        if options.print_launch_config:
            print(json.dumps({"endpoint": config.endpoint,
                              "projects_root": str(config.projects_root),
                              "staging_root": str(config.staging_root),
                              "outputs_root": str(config.outputs_root)}, allow_nan=False))
            return 0
        export_verifier = None
        frame_observer = None
        audio_observer = None
        audio_timeline_observer = None
        if config.verify_native_exports:
            from .body_editor_export import verify_native_editor_export
            from .body_editor_frame import observe_verified_export_frame
            from .body_editor_audio import observe_verified_export_audio
            from .body_editor_audio_timeline import observe_verified_export_audio_timeline
            export_verifier = lambda path, expected=None: verify_native_editor_export(
                path, policy=config._policy, expected=expected)
            frame_observer = lambda path, verified_sha256, at_seconds: observe_verified_export_frame(
                path, policy=config._policy, verified_sha256=verified_sha256,
                at_seconds=at_seconds)
            audio_observer = lambda path, verified_sha256, start_seconds, duration_seconds: observe_verified_export_audio(
                path, policy=config._policy, verified_sha256=verified_sha256,
                start_seconds=start_seconds, duration_seconds=duration_seconds)
            audio_timeline_observer = lambda path, verified_sha256, start_seconds, duration_seconds, bins: observe_verified_export_audio_timeline(
                path, policy=config._policy, verified_sha256=verified_sha256,
                start_seconds=start_seconds, duration_seconds=duration_seconds,
                bins=bins)
        server = create_editor_server(config.client(), allowed_access=config.allowed_access,
                                      export_verifier=export_verifier, frame_observer=frame_observer,
                                      audio_observer=audio_observer,
                                      audio_timeline_observer=audio_timeline_observer)

        async def serve():
            from mcp.server.stdio import stdio_server
            async with stdio_server() as (read, write):
                await server.run(read, write, server.create_initialization_options())

        asyncio.run(serve())
        return 0
    except (ValueError, OSError, EditorClientError, ImportError) as exc:
        print(f"Native editor MCP startup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
