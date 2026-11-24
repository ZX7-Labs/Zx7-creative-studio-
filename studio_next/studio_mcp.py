"""One standard local MCP connection for the model-independent creative BODY.

The host supplies the workspace, exact installed editor and grants. This
entry point starts the existing native editor transport, then exposes native
and installed creative operations through the same existing gateway. It does
not construct an inference provider, send a prompt or upload media.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

from .body_editor_policy import load_editor_config
from .capability_gateway import CapabilityGateway
from .capability_mcp_session import CombinedCapabilityMcpSession, create_combined_mcp_server
from .capability_session_budget import CapabilitySessionBudget


def resolve_attachment_paths(workspace, source, config_path, state):
    """Use the canonical private workspace when no manual paths are supplied."""
    if source is not None and config_path is not None and state is not None:
        return workspace, source, config_path, state
    from .studio_cli import load_workspace
    root, settings, _ = load_workspace(workspace)
    if settings["provider"] == "nvidia":
        raise ValueError("External MCP defaults require a local or external Brain workspace")
    return (root, source if source is not None else Path(settings["editor_source"]),
            config_path if config_path is not None else root / "editor-grants.json",
            state if state is not None else root / "state")


def prepare_attachment(workspace, config_path, state, *, max_calls, max_writes):
    """Check the owner boundary without model/provider or native execution."""
    from .native_editor_session import attest_owner_body_source

    config = load_editor_config(config_path)
    # Use the validated canonical configuration for grants; do not accept
    # model-supplied paths, permissions or arguments for the attachment.
    configuration = {"endpoint": config.endpoint,
                     "projects_root": str(config.projects_root),
                     "staging_root": str(config.staging_root),
                     "outputs_root": str(config.outputs_root),
                     "allowed_access": list(config.allowed_access),
                     "allowed_tools": dict(config.allowed_tools),
                     "verify_native_exports": config.verify_native_exports,
                     "timeout": config.timeout,
                     "required_export_delivery": (dict(config.required_export_delivery)
                         if config.required_export_delivery is not None else None)}
    body = attest_owner_body_source(workspace, configuration=configuration,
                                   provider="local")
    if body is None:
        raise ValueError("Choose an explicit owner BODY workspace")
    root = Path(workspace).resolve(strict=True)
    state = Path(state)
    if (not state.is_absolute() or state.is_symlink() or not state.is_dir() or
            state.resolve(strict=True) != state or not state.is_relative_to(root / "state") or
            (root / "state").is_symlink() or stat.S_IMODE(state.stat().st_mode) & 0o077):
        raise ValueError("MCP attachment needs a private existing state directory in this workspace")
    budget = CapabilitySessionBudget(max_calls=max_calls, max_writes=max_writes)
    return configuration, body, budget


async def run_attachment(args, prepared=None):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.server.stdio import stdio_server
    from .native_editor_session import (editor_runtime_path, native_session_grants,
                                        native_editor_child_environment)
    from .native_editor_identity import pinned_native_editor_identity_policy

    configuration, body, budget = (prepared if prepared is not None else prepare_attachment(
        args.workspace, args.config, args.state,
        max_calls=args.max_calls, max_writes=args.max_writes))
    source = args.source.resolve(strict=True)
    from .native_editor_source_pin import _source_matches_pinned_native_loss_aware_extract
    if (not source.is_dir() or not (source / "dist/index.html").is_file() or
            not _source_matches_pinned_native_loss_aware_extract(source)):
        raise ValueError("Choose the installed built cumulative source-pinned native editor")
    grants = native_session_grants(configuration, source)
    # Freeze exactly the host-attested roots and grants for the child. A
    # changed original configuration cannot attach a different workspace
    # between gateway admission and the launcher's second config read.
    attachment = Path(tempfile.mkdtemp(prefix="mcp-attachment-", dir=args.state))
    frozen_config = attachment / "editor-grants.json"
    with open(frozen_config, "x", encoding="utf-8",
              opener=lambda p, f: os.open(p, f, 0o600)) as out:
        json.dump(configuration, out, allow_nan=False)
    params = [str(editor_runtime_path("mcp.mjs")), "--source", str(source),
              "--config", str(frozen_config), "--state", str(attachment),
              "--python", sys.executable]
    for name in ("xvfb_binary", "xvfb_lib_dir", "display"):
        value = getattr(args, name)
        if value:
            params.extend(["--" + name.replace("_", "-"), str(value)])
    environment = native_editor_child_environment()
    # No provider is constructed by this process; known provider credentials
    # also do not belong in its native editor child.
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AZURE_OPENAI_API_KEY",
                "GOOGLE_API_KEY", "GEMINI_API_KEY", "HF_TOKEN"):
        environment.pop(key, None)
    paths = [str(Path(__file__).resolve().parent.parent)]
    if environment.get("PYTHONPATH"):
        paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    conn = StdioServerParameters(command="node", args=params, cwd=attachment,
                                 env=environment)
    async with stdio_client(conn) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=120) as editor:
            await editor.initialize()
            identity = pinned_native_editor_identity_policy(
                source, grants, editor,
                reserve_read=lambda: budget.reserve(source="editor", access="read"))
            if "write" in grants.values() and not (identity and identity.get("fence")):
                raise ValueError("Writable combined MCP requires the source-pinned native revision fence")
            bindings = {"editor": ((editor, grants, {}, None, {}, identity)
                                  if identity is not None else (editor, grants)),
                        "zx7": (body, body.trusted_grants)}
            gateway = CapabilityGateway(bindings, session_budget=budget)
            await gateway.refresh()
            view = CombinedCapabilityMcpSession(
                gateway, *bindings, require_model_native_observation_for=(
                    ("editor",) if identity and identity.get("fence") else ()))
            server = create_combined_mcp_server(view)
            async with stdio_server() as (outer_read, outer_write):
                await server.run(outer_read, outer_write, server.create_initialization_options())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--max-calls", type=int, default=4096)
    parser.add_argument("--max-writes", type=int, default=1024)
    parser.add_argument("--xvfb-binary")
    parser.add_argument("--xvfb-lib-dir")
    parser.add_argument("--display")
    args = parser.parse_args(argv)
    # One native editor at a time within the owner workspace; use the same
    # existing OS lock as zx7-studio run, not a second scheduler.
    import fcntl
    try:
        args.workspace, args.source, args.config, args.state = resolve_attachment_paths(
            args.workspace, args.source, args.config, args.state)
        prepared = prepare_attachment(args.workspace, args.config, args.state,
                                      max_calls=args.max_calls, max_writes=args.max_writes)
        lock_path = args.workspace / ".run.lock"
        with open(lock_path, "a", opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(run_attachment(args, prepared))
        return 0
    except (OSError, ValueError) as exc:
        print("ZX7 studio MCP attachment refused: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
