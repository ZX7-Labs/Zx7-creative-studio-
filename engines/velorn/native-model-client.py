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
import os
import subprocess
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio_next.native_creative_control import NativeCreativeControl, NATIVE_CREATIVE_SYSTEM
from studio_next.native_editor_source_pin import (pinned_electron_asset_placement_previews, pinned_electron_clip_edit_previews, pinned_electron_timeline_frame_previews)
from studio_next.providers import LocalCreativeModel, LocalModelSettings
from studio_next.capability_gateway import CapabilityGateway
from studio_next.capability_mcp_session import CapabilityGatewayMcpSession
from studio_next.capability_session_budget import CapabilitySessionBudget


def native_editor_child_environment(environ=None):
    """Never disclose a cloud provider credential to native subprocesses."""
    child = dict(os.environ if environ is None else environ)
    child.pop("NVIDIA_API_KEY", None)
    return child


_PINNED_MCP_PREVIEW_COMMIT = "b3c02adbd5c0779feb8abf34978299e9502cc0e7"
_PINNED_MARKER_PREVIEWS = (
    "add_timeline_markers", "remove_timeline_markers",
    "set_timeline_marker_properties",
)


def pinned_electron_marker_previews(source: Path, grants: dict):
    """Attest the *actual Electron MCP entrypoint*, not renderer handlers.

    Some renderer handlers mutate without parsing previewOnly because the
    Electron MCP server validates/returns read-only previews first.
    Only claim that special reply contract for an exact clean source pin.
    An unknown build gets no optimistic preview attestation.
    """
    if (not isinstance(source, Path) or
            not isinstance(grants, dict) or
            not all(isinstance(name, str) and access in ("read", "write")
                    for name, access in grants.items())):
        raise ValueError("Pinned preview attestation needs trusted native source/grants")
    safe_env = native_editor_child_environment()
    try:
        revision = subprocess.run(
            ["git", "-C", str(source.resolve()), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, env=safe_env)
        if revision.returncode != 0 or revision.stdout.strip() != _PINNED_MCP_PREVIEW_COMMIT:
            return ()
        clean = subprocess.run(
            ["git", "-C", str(source.resolve()), "diff", "--quiet", "HEAD",
             "--", "electron/mcpServer.js"],
            capture_output=True, text=True, timeout=5, env=safe_env)
    except (OSError, subprocess.TimeoutExpired):
        return ()
    if clean.returncode != 0:
        return ()
    return tuple(name for name in _PINNED_MARKER_PREVIEWS
                 if grants.get(name) == "write")


def trial_machine_contracts(grants, *, fresh):
    """Construct machine facts from *only* the host-granted native catalog.

    A tool outside the configured grant set cannot acquire constraints,
    possible effects or affordance visibility by accident. This contract
    merely explains observed machine state, not what to edit or how.
    """
    if type(fresh) is not bool or not isinstance(grants, dict):
        raise ValueError("Machine facts require validated owner tool grants")
    if not fresh:
        return {}, {}
    prerequisites = {
        "import_asset_from_path": ("project_open",),
        "add_asset_to_timeline": ("project_open", "project_assets_available"),
        "add_assets_to_timeline": ("project_open", "project_assets_available"),
        "replace_clip_with_asset": ("project_open", "project_assets_available"),
        "add_text_clip": ("project_open",),
        "add_shape_clip": ("project_open",),
        "update_text_clip": ("project_open",),
        "save_project": ("project_open",),
        "export_timeline": ("project_open",),
    }
    if grants.get("create_project") != "write":
        raise ValueError("Fresh trial requires the real authorized project creator")
    return ({name: list(facts) for name, facts in prerequisites.items()
             if name in grants},
            {"create_project": ["project_open"]})


def native_decision_model(args):
    """Choose a configured model transport; the model cannot dispatch native calls.

    Hosted NVIDIA function calling is opt-in until a real provider protocol
    check succeeds. BODY continues to validate every actual editor operation.
    """
    if args.provider == "nvidia":
        if args.base_url != "http://127.0.0.1:8080":
            raise ValueError("NVIDIA endpoint is fixed, not overridden by --base-url")
        from studio_next.nvidia_model import NvidiaCreativeModel, NvidiaModelSettings
        model_type = NvidiaCreativeModel
        if args.structured_actions:
            from studio_next.nvidia_native_tool_model import (
                NvidiaNativeToolCreativeModel, NATIVE_DIRECT_TOOL_SYSTEM,
            )
            model_type = NvidiaNativeToolCreativeModel
        # Provider transport policy, NOT a second BODY/agent path.
        # NVIDIA's pinned Nemotron 3.5 VL is a REASONING tool model. The
        # initial live editor trials unintentionally DISABLED its reasoning,
        # capped output at 2048 and produced repeated imports and no clips.
        # The hosted API documents reasoning_effort none/low/high, not the
        # self-hosted medium_effort chat-template knob. Start with documented
        # low reasoning within the already reviewed 8192-token budget.
        # Keep legacy smoke/older transport settings and local model intact.
        nvidia_settings = (
            NvidiaModelSettings(
                model_id=args.model_id, timeout_seconds=args.model_timeout,
                max_tokens=8192,
                sampling={
                    "temperature": 1.0, "top_p": 0.95,
                    "reasoning_effort": "low",
                })
            if args.structured_actions else
            NvidiaModelSettings(model_id=args.model_id,
                                timeout_seconds=args.model_timeout))
        model = model_type(
            nvidia_settings,
            system_prompt=(NATIVE_DIRECT_TOOL_SYSTEM if args.structured_actions
                           else NATIVE_CREATIVE_SYSTEM),
            allow_image_upload=args.allow_cloud_image_upload)
        model.verify_host_credentials()
        return model
    if args.provider != "local":
        raise ValueError("Unrecognized creative model provider")
    if args.allow_cloud_image_upload:
        raise ValueError("Cloud-media consent requires --provider nvidia")
    local_type = LocalCreativeModel
    if args.structured_actions:
        from studio_next.local_native_structured_model import (
            LocalNativeStructuredCreativeModel,
        )
        local_type = LocalNativeStructuredCreativeModel
    return local_type(
        LocalModelSettings(base_url=args.base_url, model_id=args.model_id,
                           timeout_seconds=args.model_timeout),
        system_prompt=NATIVE_CREATIVE_SYSTEM)


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
    model = native_decision_model(args)
    configuration = json.loads(args.config.read_text(encoding="utf-8"))
    host_grants = configuration.get("allowed_tools")
    if not isinstance(host_grants, dict) or not host_grants:
        raise ValueError("Native editor requires explicit host-controlled tool grants")
    host_grants = dict(host_grants)
    host_grants.update({name: "read" for name in (
        "zx7_verify_native_export", "zx7_observe_verified_export_frame",
        "zx7_observe_verified_export_samples", "zx7_observe_verified_export_audio",
        "zx7_observe_verified_export_audio_timeline")})
    evidence_profiles = {
        "none": (),
        "export": ("native_write_acknowledged", "physical_export_verified"),
        "reviewed-revision": (
            "native_write_acknowledged", "physical_export_verified",
            "verified_export_frame_observed",
            "post_observation_native_write_acknowledged"),
    }
    required = evidence_profiles[args.evaluation_evidence]
    fresh = bool(args.fresh_trial_project)
    if fresh:
        project_root = Path(configuration["projects_root"])
        if not project_root.is_dir() or any(project_root.iterdir()):
            raise ValueError("Fresh neural trial requires an actual empty project root")
        if host_grants.get("create_project") != "write":
            raise ValueError("Fresh neural trial requires host-authorized create_project")
    revision_roles = (
        "add_asset_to_timeline", "add_assets_to_timeline",
        "add_text_clip", "update_text_clip", "add_shape_clip",
        "update_shape_clip", "set_clip_style", "set_clip_mask",
        "move_clips", "trim_clips", "delete_clips",
    )
    host_revisions = tuple(
        name for name in revision_roles if host_grants.get(name) == "write")
    if args.evaluation_evidence == "reviewed-revision" and not args.allow_cloud_image_upload:
        raise ValueError("Observed cloud trial requires explicit synthetic image upload permission")
    brief = args.brief_file.read_text(encoding="utf-8")
    # NVIDIA_API_KEY must stay solely in the trusted Python Brain process.
    # The native editor, Electron children, FFmpeg, and arbitrary editor plugins
    # must never inherit a hosted-provider credential even for synthetic trials.
    conn = StdioServerParameters(command="node", args=params, cwd=ROOT,
                                 env=native_editor_child_environment())
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
            preconditions, machine_effects = trial_machine_contracts(
                host_grants, fresh=fresh)
            outcome = await NativeCreativeControl(
                admitted, model, max_turns=args.max_turns,
                host_tool_access=host_grants,
                catalog_mode=("indexed" if args.indexed_catalog else "full"),
                host_preconditions=preconditions,
                host_possible_effects=machine_effects,
                host_once_after_acknowledged_write=(
                    ("create_project",) if fresh else ()),
                host_verified_top_level_preview_tools=(
                    pinned_electron_marker_previews(args.source, host_grants) +
                    pinned_electron_asset_placement_previews(args.source, host_grants) +
                    pinned_electron_clip_edit_previews(args.source, host_grants)),
                host_verified_timeline_preview_tools=(
                    pinned_electron_timeline_frame_previews(args.source, host_grants)),
                required_evidence=required,
                host_content_revision_tools=host_revisions,
                receipt_path=args.receipt).run(brief)
    print(json.dumps({
        "status": outcome["status"],
        "model_id_reported": outcome["actual_model_id_reported"],
        "selected_provider": args.provider,
        "model_action_transport": (
            "nvidia_host_native_typed_function_calls" if args.provider == "nvidia" and
            args.structured_actions else
            "local_current_host_json_schema" if args.provider == "local" and
            args.structured_actions else "free_form_json"),
        "required_evaluation_evidence": list(required),
        "evaluation_evidence_satisfied": bool(required) and outcome["status"] == "model_finished_unverified",
        "model_selected_write_receipts": sum(
            event.get("kind") == "native_tool_result" and
            event.get("host_application_write_acknowledged") is True
            for event in outcome["events"]),
        "independently_verified_export_receipts": sum(
            bool(event.get("independently_verified_export_sha256"))
            for event in outcome["events"]),
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
    p.add_argument("--indexed-catalog", action="store_true",
                   help="Use true host-granted compact capability search rather than the full prompt")
    p.add_argument("--fresh-trial-project", action="store_true",
                   help="Require an empty isolated root and prevent repeated project creation")
    p.add_argument("--evaluation-evidence",
                   choices=("none", "export", "reviewed-revision"), default="none",
                   help="Host-required physical proof before the model can finish")
    p.add_argument("--structured-actions", action="store_true",
                   help="Use local JSON Schema or opt-in NVIDIA forced function calling (host validates every native action)")
    p.add_argument("--xvfb-binary")
    p.add_argument("--xvfb-lib-dir")
    p.add_argument("--display")
    p.add_argument("--software-gpu", action="store_true")
    p.add_argument("--no-sandbox", action="store_true")
    asyncio.run(main(p.parse_args()))
