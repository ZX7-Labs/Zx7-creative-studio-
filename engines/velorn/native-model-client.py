#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Connect ONE actual local model to the complete pinned native editor.

This is the first runnable, model-driven native editor gateway. It is not a
professional artistic quality certificate. The host config grants all tools
and source paths; model decisions cannot expand them. Run with a real local
OpenAI-compatible inference service, not a scripted test fixture.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio_next.native_creative_control import NativeCreativeControl, NATIVE_CREATIVE_SYSTEM
from studio_next.providers import LocalCreativeModel, LocalModelSettings
from studio_next.native_action_schema import native_action_schema
from studio_next.capability_gateway import CapabilityGateway
from studio_next.capability_mcp_session import CapabilityGatewayMcpSession
from studio_next.capability_session_budget import CapabilitySessionBudget


async def main(args):
    for path in (args.source, args.config, args.brief_file):
        if not path.exists():
            raise ValueError("Missing native source/config/creative brief file: " + str(path))
    if not args.state.is_dir():
        raise ValueError("Create a private state directory before launching the editor")
    # The host grants and input policies are loaded exclusively by mcp.mjs and
    # body_editor_mcp. None of those permissions come from model text.
    params = [str(ROOT / "engines/velorn/mcp.mjs"), "--source",
              str(args.source.resolve()), "--config", str(args.config.resolve()),
              "--state", str(args.state.resolve()), "--python", sys.executable]
    for name in ("xvfb_binary", "xvfb_lib_dir", "display"):
        value = getattr(args, name)
        if value:
            params.extend(["--" + name.replace("_", "-"), str(value)])
    if args.software_gpu:
        params.append("--software-gpu")
    if args.no_sandbox:
        raise ValueError("Do not disable Chromium sandbox in live-model creative sessions")
    if args.provider == "nvidia":
        if args.structured_actions:
            raise ValueError("NVIDIA Qwen API does not document strict response_format JSON schemas")
        if args.base_url != "http://127.0.0.1:8080":
            raise ValueError("NVIDIA endpoint is fixed, not overridden by --base-url")
        from studio_next.nvidia_model import NvidiaCreativeModel, NvidiaModelSettings
        model = NvidiaCreativeModel(
            NvidiaModelSettings(model_id=args.model_id,timeout_seconds=args.model_timeout),
            system_prompt=NATIVE_CREATIVE_SYSTEM,
            allow_image_upload=args.allow_cloud_image_upload)
        model.verify_host_credentials()
    else:
        if args.allow_cloud_image_upload:
            raise ValueError("Cloud-media consent requires --provider nvidia")
        model = LocalCreativeModel(
            LocalModelSettings(base_url=args.base_url, model_id=args.model_id,
                               timeout_seconds=args.model_timeout),
            system_prompt=NATIVE_CREATIVE_SYSTEM)
    configuration = json.loads(args.config.read_text(encoding="utf-8"))
    host_grants = configuration.get("allowed_tools")
    if not isinstance(host_grants, dict) or not host_grants:
        raise ValueError("Native editor requires explicit host-controlled tool grants")
    host_grants = dict(host_grants)
    host_grants.update({name: "read" for name in (
        "zx7_verify_native_export", "zx7_observe_verified_export_frame",
        "zx7_observe_verified_export_samples", "zx7_observe_verified_export_audio",
        "zx7_observe_verified_export_audio_timeline")})
    brief = args.brief_file.read_text(encoding="utf-8")
    conn = StdioServerParameters(command="node", args=params, cwd=ROOT)
    async with stdio_client(conn) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=120) as session:
            await session.initialize()
            # One host-owned gateway mediates both the neural tool proposals
            # and controller readbacks; the raw MCP connection is never passed
            # into NativeCreativeControl. Local and NVIDIA are interchangeable.
            budget = CapabilitySessionBudget(
                max_calls=args.max_turns * 12, max_writes=args.max_turns)
            gateway = CapabilityGateway(
                {"editor": (session, host_grants)}, session_budget=budget)
            await gateway.refresh()
            admitted = CapabilityGatewayMcpSession(gateway, "editor")
            if args.structured_actions:
                discovered = (await admitted.list_tools()).tools
                model.settings.sampling['response_format'] = {
                    'type': 'json_schema', 'json_schema': {'name': 'native_editor_action',
                        'strict': True, 'schema': native_action_schema([tool.name for tool in discovered])}}
            outcome = await NativeCreativeControl(
                admitted, model, max_turns=args.max_turns,
                host_tool_access=host_grants,
                receipt_path=args.receipt).run(brief)
    print(json.dumps({
        "status": outcome["status"],
        "model_id_reported": outcome["actual_model_id_reported"],
        "selected_provider": args.provider,
        "events": len(outcome["events"]),
        "measured_model_wall_ms_total": outcome["measured_model_wall_ms_total"],
        "measured_native_mcp_wall_ms_total": outcome["measured_native_mcp_wall_ms_total"],
        "token_usage_independently_verified": False,
        "cloud_media_upload_permitted_by_host": args.allow_cloud_image_upload,
        "receipt": str(args.receipt),
        "native_editing_capability_complete": False,
        "artistic_quality_independently_approved": False,
        "neural_autonomy_independently_verified": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True,
                   help="Owner-controlled native MCP grants/root paths")
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--brief-file", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True,
                   help="New local private 0600 receipt, never overwritten/replayed")
    p.add_argument("--provider", choices=("local", "nvidia"), default="local")
    p.add_argument("--model-id", type=str, required=True)
    p.add_argument("--allow-cloud-image-upload", action="store_true",
                   help="Explicitly consent to sending private observed frames to NVIDIA")
    p.add_argument("--base-url", default="http://127.0.0.1:8080")
    p.add_argument("--model-timeout", type=int, default=480)
    p.add_argument("--max-turns", type=int, default=32)
    p.add_argument("--structured-actions", action="store_true",
                   help="Use native action JSON Schema on a backend supporting structured decoding")
    p.add_argument("--xvfb-binary")
    p.add_argument("--xvfb-lib-dir")
    p.add_argument("--display")
    p.add_argument("--software-gpu", action="store_true")
    p.add_argument("--no-sandbox", action="store_true")
    asyncio.run(main(p.parse_args()))
