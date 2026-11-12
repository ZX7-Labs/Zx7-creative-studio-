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
from functools import partial
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from studio_next.native_creative_control import NativeCreativeControl, NATIVE_CREATIVE_SYSTEM
from studio_next.native_creative_audit import audit_native_journal
from studio_next.native_render_evidence import (
    AUDIO_ENVELOPE, REVIEWED_AV_PAIR, REVIEWED_NATIVE_EVIDENCE, REVIEWED_RENDER_PAIR,
)
from studio_next.native_editor_source_pin import (
    PINNED_VELORN_MCP_REVISION as _PINNED_MCP_PREVIEW_COMMIT,
    _PINNED_MARKER_PREVIEWS,
    pinned_electron_marker_previews, pinned_electron_asset_placement_previews,
    pinned_electron_clip_edit_previews, pinned_electron_timeline_frame_previews,
)
from studio_next.providers import LocalCreativeModel, LocalModelSettings
from studio_next.capability_gateway import CapabilityGateway
from studio_next.capability_mcp_session import CapabilityGatewayMcpSession, CombinedCapabilityMcpSession
from studio_next.capability_session_budget import CapabilitySessionBudget
from studio_next.native_editor_identity import pinned_native_editor_identity_policy


ROOT = Path(__file__).resolve().parent.parent


def editor_runtime_path(name: str) -> Path:
    """Locate the shipped GPL runtime independently of the source checkout."""
    if name not in {"mcp.mjs", "launcher.mjs", "client.mjs", "editor.example.json", "LICENSE", "NOTICE"}:
        raise ValueError("Unknown packaged editor runtime asset")
    return Path(__file__).resolve().parent / "editor_runtime" / name


def native_session_grants(configuration: dict, source: Path) -> dict:
    """Match the actual bridge catalog without inventing unavailable sensors."""
    configured = configuration.get("allowed_tools")
    if not isinstance(configured, dict) or not configured:
        raise ValueError("Native editor requires explicit host-controlled tool grants")
    access = configuration.get("allowed_access", ("read",))
    grants = {name: mode for name, mode in configured.items() if mode in access}
    if not grants:
        raise ValueError("Native editor has no tools enabled by host access")
    if configuration.get("verify_native_exports") is True and "read" in access:
        grants.update({name: "read" for name in (
            "zx7_verify_native_export", "zx7_observe_verified_export_frame",
            "zx7_observe_verified_export_samples", "zx7_observe_verified_export_audio",
            "zx7_observe_verified_export_audio_timeline")})
    if "read" in access and grants.get("get_timeline") == "read":
        from .native_editor_diagnostics import native_content_diagnostics_source_verified
        if native_content_diagnostics_source_verified(source):
            grants["zx7_inspect_native_content"] = "read"
    return grants


def native_editor_child_environment(environ=None):
    """Never disclose a cloud provider credential to native subprocesses."""
    child = dict(os.environ if environ is None else environ)
    child.pop("NVIDIA_API_KEY", None)
    return child


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
    prompt_suffix = (
        "\nUse the owner's brief language for the final summary unless the owner requests another."
    )
    if getattr(args, "allow_public_research", False):
        from studio_next.creative_research_mcp import PUBLIC_RESEARCH_SYSTEM
        prompt_suffix += "\n\n" + PUBLIC_RESEARCH_SYSTEM
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
                           else NATIVE_CREATIVE_SYSTEM) + prompt_suffix,
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
        system_prompt=NATIVE_CREATIVE_SYSTEM + prompt_suffix)


async def run_native_session(args):
    """Run the existing host-bound native loop and return its factual summary.

    No model or editor is installed implicitly. The caller owns the brief,
    grants, private state and whether a remote model may receive images.
    """
    for path in (args.source, args.config, args.brief_file):
        if not path.exists():
            raise ValueError("Missing native source/config/creative brief file: " + str(path))
    if not args.state.is_dir():
        raise ValueError("Create a private state directory before launching the editor")
    # The host grants and input policies are loaded exclusively by mcp.mjs and
    # body_editor_mcp. None of those permissions come from model text.
    params = [str(editor_runtime_path("mcp.mjs")), "--source",
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
    research = None
    searxng_url = getattr(args, "searxng_url", None)
    if getattr(args, "allow_public_research", False):
        from studio_next.creative_research_mcp import CreativeResearchMcpSession
        research = CreativeResearchMcpSession(allow_public_research=True,
            searxng_url=searxng_url, max_calls=8)
    elif searxng_url is not None:
        raise ValueError("A SearXNG endpoint requires explicit --allow-public-research")
    model = native_decision_model(args)
    configuration = json.loads(args.config.read_text(encoding="utf-8"))
    host_grants = native_session_grants(configuration, args.source)
    evidence_profiles = {
        "none": (),
        "export": ("native_write_acknowledged", "physical_export_verified"),
        "reviewed-revision": REVIEWED_NATIVE_EVIDENCE,
        "reviewed-av-revision": (*REVIEWED_NATIVE_EVIDENCE, REVIEWED_AV_PAIR),
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
        "move_clips", "trim_clips", "delete_clips", "add_track", "update_track", "remove_track",
    )
    if REVIEWED_AV_PAIR in required:
        revision_roles += ("set_clip_audio", "set_master_audio")
    host_revisions = tuple(
        name for name in revision_roles if host_grants.get(name) == "write")
    preview_tools = (pinned_electron_marker_previews(args.source, host_grants) +
                     pinned_electron_asset_placement_previews(args.source, host_grants) +
                     pinned_electron_clip_edit_previews(args.source, host_grants))
    cloud_diagnostics = getattr(args, "allow_cloud_audio_diagnostics", False)
    if cloud_diagnostics and (args.provider != "nvidia" or REVIEWED_AV_PAIR not in required):
        raise ValueError("Cloud audio diagnostics require NVIDIA audiovisual review mode")
    if (args.provider == "nvidia" and REVIEWED_RENDER_PAIR in required
            and not args.allow_cloud_image_upload):
        raise ValueError("Observed cloud trial requires explicit synthetic image upload permission")
    if args.provider == "nvidia":
        if REVIEWED_AV_PAIR in required and not cloud_diagnostics:
            raise ValueError("Cloud audiovisual review requires explicit audio diagnostics consent")
        # WAV has no validated NVIDIA input contract. Numerical diagnostics
        # are text and must also be excluded from unconsented hosted sessions.
        host_grants.pop("zx7_observe_verified_export_audio", None)
        if not cloud_diagnostics:
            host_grants.pop(AUDIO_ENVELOPE, None)
    capture_render_project = None
    if getattr(args, "record_av_project_snapshots", False):
        if not fresh or REVIEWED_AV_PAIR not in required or host_grants.get("save_project") != "write":
            raise ValueError("Render snapshots require a fresh audiovisual trial with a save grant")
        from .native_editor_project import capture_render_project as capture
        snapshots_root = args.state.resolve() / "av-project-snapshots"
        snapshots_root.mkdir(mode=0o700)
        capture_render_project = partial(capture, project_root.resolve(strict=True), snapshots_root)
    brief = args.brief_file.read_text(encoding="utf-8")
    if REVIEWED_AV_PAIR in required:
        brief += (
            "\n\nHost audiovisual review requirement. Independently verify the physical "
            "first export with sound (up to 300 seconds in this evidence mode), "
            "view two to four frames covering separated moments "
            "at least a third of its duration apart, and inspect the decoded audio "
            "timeline from zero through the measured export duration. Then choose and "
            "save an editable revision and check the same timestamps and audio window "
            "on a new export so the decoded picture or sound change can be verified. "
            "The audio timeline contains numerical observations only.")
    # NVIDIA_API_KEY must stay solely in the trusted Python Brain process.
    # The native editor, Electron children, FFmpeg, and arbitrary editor plugins
    # must never inherit a hosted-provider credential even for synthetic trials.
    child_environment = native_editor_child_environment()
    # Keep the bridge on this same implementation whether imported from an
    # installed wheel or a source checkout. Its private working directory is
    # unrelated to Python's module search path; no repo cwd is required.
    python_paths = [str(Path(__file__).resolve().parent.parent)]
    if child_environment.get("PYTHONPATH"):
        python_paths.append(child_environment["PYTHONPATH"])
    child_environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    conn = StdioServerParameters(command="node", args=params, cwd=args.state.resolve(),
                                 env=child_environment)
    async with stdio_client(conn) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=120) as session:
            await session.initialize()
            # One host-owned gateway mediates both the neural tool proposals
            # and controller readbacks; the raw MCP connection is never passed
            # into NativeCreativeControl. Local and NVIDIA are interchangeable.
            budget = CapabilitySessionBudget(
                max_calls=args.max_turns * 12, max_writes=args.max_turns)
            # Actual clean pinned Electron source supplies read-only ID
            # inventories; the Brain never chooses or fabricates this policy.
            # Each host-internal source observation charges the existing
            # cross-engine call budget; no new background agent or API.
            identity = pinned_native_editor_identity_policy(
                args.source, host_grants, session,
                reserve_read=lambda: budget.reserve(
                    source="editor", access="read"))
            bindings = {"editor": (
                (session, host_grants, {}, None, {}, identity)
                if identity is not None else (session, host_grants))}
            if research is not None:
                bindings["research"] = (research, research.grants)
            gateway = CapabilityGateway(bindings, session_budget=budget)
            await gateway.refresh()
            admitted = CapabilityGatewayMcpSession(gateway, "editor")
            model_session = (CombinedCapabilityMcpSession(gateway, "editor", "research")
                             if research is not None else admitted)
            model_grants = host_grants if research is None else {**host_grants, **research.grants}
            selected_project_setup = None
            if getattr(args, "project", None) is not None:
                from .native_editor_project import open_selected_native_project
                selected_project_setup = await open_selected_native_project(
                    admitted, project=args.project, source=args.source,
                    projects_root=configuration["projects_root"], grants=host_grants,
                    receipt_path=args.state / "owner-project-setup.jsonl")
            preconditions, machine_effects = trial_machine_contracts(
                host_grants, fresh=fresh)
            outcome = await NativeCreativeControl(
                model_session, model, max_turns=args.max_turns,
                host_tool_access=model_grants,
                host_pre_dispatch_rejections=True,
                catalog_mode=("indexed" if args.indexed_catalog else "full"),
                host_preconditions=preconditions,
                host_possible_effects=machine_effects,
                host_once_after_acknowledged_write=(
                    ("create_project",) if fresh else ()),
                host_verified_top_level_preview_tools=preview_tools,
                host_verified_timeline_preview_tools=(
                    pinned_electron_timeline_frame_previews(args.source, host_grants)),
                required_evidence=required,
                host_content_revision_tools=host_revisions,
            host_capture_render_project=capture_render_project,
                receipt_path=args.receipt).run(brief)
    pair_report = {}
    if REVIEWED_RENDER_PAIR in required:
        audit = audit_native_journal(outcome["events"], host_tool_access=model_grants,
            expected_required_evidence=required, host_content_revision_tools=host_revisions,
            host_pre_dispatch_rejections=True, host_verified_preview_error_tools=preview_tools)
        pair_report["reviewed_native_render_pair"] = audit["reviewed_native_render_pair"]
        if REVIEWED_AV_PAIR in required:
            pair_report["reviewed_native_audiovisual_pair"] = audit["reviewed_native_audiovisual_pair"]
    return {
        **pair_report,
        "status": outcome["status"],
        "model_id_reported": outcome["actual_model_id_reported"],
        "selected_provider": args.provider,
        "native_reference_preflight_enabled": identity is not None,
        "owner_project_setup": selected_project_setup,
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
        "cloud_audio_diagnostics_permitted_by_host": cloud_diagnostics,
        "public_research_permitted_by_host": research is not None,
        "receipt": str(args.receipt),
        "native_editing_capability_complete": False,
        "artistic_quality_independently_approved": False,
        "neural_autonomy_independently_verified": False,
    }


async def main(args):
    """Legacy asynchronous entry: preserve its JSON stdout summary."""
    summary = await run_native_session(args)
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True,
                   help="Owner-controlled native MCP grants/root paths")
    p.add_argument("--project", type=Path, help="Open and verify this owner-selected project before model editing")
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--brief-file", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True,
                   help="New local private 0600 receipt, never overwritten/replayed")
    p.add_argument("--provider", choices=("local", "nvidia"), default="local")
    p.add_argument("--model-id", type=str, required=True)
    p.add_argument("--allow-cloud-image-upload", action="store_true",
                   help="Explicitly consent to sending private observed frames to NVIDIA")
    p.add_argument("--allow-cloud-audio-diagnostics", action="store_true",
                   help="Explicitly consent to sending numerical audio timeline diagnostics to NVIDIA")
    p.add_argument("--allow-public-research", action="store_true",
                   help="Allow model-written public queries to external research services")
    p.add_argument("--searxng-url", help="Optional owner-configured loopback SearXNG base URL")
    p.add_argument("--base-url", default="http://127.0.0.1:8080")
    p.add_argument("--model-timeout", type=int, default=480)
    p.add_argument("--max-turns", type=int, default=32)
    p.add_argument("--indexed-catalog", action="store_true",
                   help="Use true host-granted compact capability search rather than the full prompt")
    p.add_argument("--fresh-trial-project", action="store_true",
                   help="Require an empty isolated root and prevent repeated project creation")
    p.add_argument("--record-av-project-snapshots", action="store_true",
                   help="Record the last explicitly saved project at each acknowledged trial render")
    p.add_argument("--evaluation-evidence",
                   choices=("none", "export", "reviewed-revision", "reviewed-av-revision"),
                   default="none",
                   help="Host-required physical proof before the model can finish")
    p.add_argument("--structured-actions", action="store_true",
                   help="Use local JSON Schema or opt-in NVIDIA forced function calling (host validates every native action)")
    p.add_argument("--xvfb-binary")
    p.add_argument("--xvfb-lib-dir")
    p.add_argument("--display")
    p.add_argument("--software-gpu", action="store_true")
    p.add_argument("--no-sandbox", action="store_true")
    return p


def cli(argv=None):
    asyncio.run(main(build_parser().parse_args(argv)))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
