"""Owner entry point for the installed native creative studio.

This prepares private owner workspaces and calls the existing model/editor
session. It does not implement another creative planner or editing engine.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import hashlib
from http.client import HTTPException
from importlib import metadata
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
from urllib.request import Request

from .body_editor_client import _load_json
from .body_editor_policy import load_editor_config
from .native_editor_source_pin import PINNED_VELORN_MCP_REVISION, TRUSTED_VELORN_REVISIONS
from .providers import LocalModelSettings


def _write_new(path, value):
    with open(Path(path), "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as out:
        json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write("\n")


def _write_status(session, value):
    temporary = session / (".status-" + secrets.token_hex(8))
    try:
        _write_new(temporary, value)
        os.replace(temporary, session / "status.json")
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _bound_session_runner(workspace_lock, session, session_id):
    """Bind one session to live kernel locks; file contents alone prove no liveness."""
    import fcntl
    with open(session / ".runner.lock", "a", opener=lambda p, f:
              os.open(p, f | os.O_NOFOLLOW, 0o600)) as session_lock:
        fcntl.flock(session_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # A session-specific lock closes the transition window in which a new
        # workspace lock holder has not yet replaced an old session binding.
        workspace_lock.seek(0)
        workspace_lock.truncate()
        json.dump({"schema": 1, "session_id": session_id}, workspace_lock)
        workspace_lock.flush()
        os.fsync(workspace_lock.fileno())
        yield


def _probe_runner_lock(path, *, binding=False):
    """Read-only lock observation. Missing/unstable metadata is unknown, not a PID guess."""
    import fcntl
    try:
        lock = open(path, "r", encoding="utf-8", opener=lambda p, f:
                    os.open(p, f | os.O_NOFOLLOW))
    except FileNotFoundError:
        return None, None
    with lock:
        info = os.fstat(lock.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError("Runner lock must be a private owner-controlled file")
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            held = False
        except BlockingIOError:
            held = True
        session_id = None
        if binding:
            try:
                raw = lock.read(1025)
                value = _load_json(raw) if len(raw) <= 1024 else None
                candidate = value.get("session_id") if isinstance(value, dict) else None
                if (value.get("schema") == 1 and isinstance(candidate, str)
                        and len(candidate) == 24
                        and all(c in "0123456789abcdef" for c in candidate)):
                    session_id = candidate
            except (ValueError, UnicodeError, AttributeError):
                pass  # A live owner may be replacing the bounded binding.
        return held, session_id


def _private_root(path):
    raw = Path(path).expanduser().absolute()
    if raw.is_symlink():
        raise ValueError("Studio workspace must not be a symbolic link")
    root = raw.resolve(strict=True)
    if not root.is_dir() or root.stat().st_uid != os.getuid():
        raise ValueError("Studio workspace must be an owner-controlled directory")
    if stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise ValueError("Studio workspace must be private (chmod 700)")
    return root


def _read_private(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("Missing or unsafe bounded studio configuration")
    if path.stat().st_uid != os.getuid() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Studio configuration must be private (chmod 600)")
    return _load_json(path.read_text(encoding="utf-8"))


def load_workspace(path):
    root = _private_root(path)
    config = _read_private(root / "studio.json")
    required = {"schema", "editor_source", "provider", "model_id", "base_url"}
    if (type(config) is not dict or set(config) != required or
            type(config["schema"]) is not int or config["schema"] != 1 or
            config["provider"] not in ("local", "nvidia") or
            not isinstance(config["editor_source"], str) or
            not Path(config["editor_source"]).is_absolute() or
            not isinstance(config["model_id"], str) or not config["model_id"].strip()):
        raise ValueError("Invalid studio configuration")
    LocalModelSettings(base_url=config["base_url"], model_id=config["model_id"])
    if config["provider"] == "nvidia" and config["base_url"] != "http://127.0.0.1:8080":
        raise ValueError("NVIDIA endpoint is fixed; omit --base-url")
    _read_private(root / "editor-grants.json")
    grants = load_editor_config(root / "editor-grants.json")
    for name in ("projects", "staging", "outputs", "state", "sessions"):
        child = root / name
        if child.is_symlink() or not child.is_dir() or child.resolve().parent != root:
            raise ValueError("Studio workspace directory was redirected or removed")
    if any(getattr(grants, name + "_root") != root / name
           for name in ("projects", "staging", "outputs")):
        raise ValueError("Studio grants must belong to this workspace")
    return root, config, grants


def _default_editor_source():
    for source in (Path(sys.prefix) / "share/zx7-studio/velorn",
                   Path(__file__).resolve().parents[1] / "third_party/velorn"):
        if (source / "package.json").is_file() and (source / "dist/index.html").is_file():
            return source
    raise ValueError("Built Velorn editor was not found. Install it or supply --source.")


def _local_model_ids(base_url):
    from .local_model_http import urlopen

    try:
        request = Request(base_url.rstrip("/") + "/v1/models")
        with urlopen(request, timeout=5) as response:
            raw = response.read(1024 * 1024 + 1)
        result = _load_json(raw.decode("utf-8")) if len(raw) <= 1024 * 1024 else None
        models = result.get("data") if isinstance(result, dict) else None
        if isinstance(models, list):
            return {model["id"] for model in models if isinstance(model, dict)
                    and isinstance(model.get("id"), str) and model["id"].strip()}
    except (OSError, ValueError, HTTPException, RecursionError):
        pass
    raise ValueError("Could not read model inventory. Start the local model server or supply --model-id.")


def initialize_workspace(path, *, source=None, model_id=None, provider="local",
                         base_url="http://127.0.0.1:8080"):
    from .native_editor_session import editor_runtime_path

    if provider not in ("local", "nvidia"):
        raise ValueError("Unknown creative model provider")
    if provider == "nvidia" and base_url != "http://127.0.0.1:8080":
        raise ValueError("NVIDIA endpoint is fixed; omit --base-url")
    root = Path(path).expanduser().absolute()
    if root.exists() or root.is_symlink():
        raise FileExistsError(f"Studio workspace already exists: {root}")
    source = _default_editor_source() if source is None else Path(source)
    source = source.expanduser().resolve(strict=True)
    if not source.is_dir():
        raise ValueError("Editor source must be a directory")
    # Validate the local endpoint before attempting an inventory request.
    if model_id is None:
        if provider == "nvidia":
            from .nvidia_model import NvidiaModelSettings

            model_id = NvidiaModelSettings().model_id
        else:
            LocalModelSettings(base_url=base_url)
            models = _local_model_ids(base_url)
            if not models:
                raise ValueError("The local server lists no model. Load one and try again.")
            if len(models) > 1:
                raise ValueError("The local server lists multiple models. Select one with --model-id.")
            model_id, = models
    LocalModelSettings(base_url=base_url, model_id=model_id)
    # Refuse to replace a workspace created while discovery was in progress.
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    root = root.resolve()
    for name in ("projects", "staging", "outputs", "state", "sessions"):
        (root / name).mkdir(mode=0o700)
    template = _load_json(editor_runtime_path("editor.example.json").read_text(encoding="utf-8"))
    template.update({name + "_root": str(root / name) for name in ("projects", "staging", "outputs")})
    _write_new(root / "editor-grants.json", template)
    config = {"schema": 1, "editor_source": str(source), "provider": provider,
              "model_id": model_id, "base_url": base_url}
    _write_new(root / "studio.json", config)
    load_workspace(root)
    return {"workspace": str(root), "status": "initialized", "next": "doctor"}


def doctor(path, *, check_model=True):
    """Inspect setup; never install engines, download weights or call cloud AI."""
    from .native_editor_session import editor_runtime_path, native_editor_child_environment
    root, config, _ = load_workspace(path)
    checks = []
    def add(name, ok, detail):
        checks.append({"name": name, "ready": bool(ok), "detail": detail})
    for program in ("node", "git", "ffmpeg", "ffprobe"):
        location = shutil.which(program)
        add(program, location is not None, location or "Install " + program)
    for package, required in (("mcp", "2.3.0"), ("jsonschema", None)):
        try:
            version = metadata.version(package)
        except metadata.PackageNotFoundError:
            version = None
        add(package, version is not None and (required is None or version == required),
            version or "Install zx7-studio-body[editor,production]")
    add("packaged_editor_bridge", all(editor_runtime_path(n).is_file()
        for n in ("mcp.mjs", "launcher.mjs", "client.mjs")), "Installed native bridge assets")
    source = Path(config["editor_source"])
    pinned = clean = False
    if shutil.which("git") and source.is_dir():
        try:
            options = dict(capture_output=True, text=True, timeout=10,
                           env=native_editor_child_environment())
            resolved = str(source.resolve(strict=True))
            rev = subprocess.run(
                ["git", "-C", resolved, "rev-parse", "--show-toplevel", "HEAD"], **options)
            identity = rev.stdout.splitlines()
            pinned = (rev.returncode == 0 and len(identity) == 2 and
                      identity[0] == resolved and identity[1] in TRUSTED_VELORN_REVISIONS)
            diff = subprocess.run(["git", "-C", str(source), "diff", "--quiet", "HEAD", "--"], **options)
            clean = diff.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    add("editor_source_pin", pinned and clean,
        "Requires clean Velorn " + PINNED_VELORN_MCP_REVISION + " or its approved desktop revision")
    add("editor_build", (source / "dist/index.html").is_file(), "Build pinned editor with npm ci && npm run build")
    electron = source / "node_modules/electron/dist/electron"
    add("electron", electron.is_file() and os.access(electron, os.X_OK), "Install pinned editor dependencies")
    bundled_media = False
    if pinned and clean and shutil.which("node"):
        try:
            probe = subprocess.run(["node", "--input-type=module", "-e",
                "import {createRequire} from 'node:module'; "
                "const r=createRequire(process.argv[1]); "
                "console.log(JSON.stringify([r('ffmpeg-static'),r('@derhuerst/ffprobe-static')]));",
                str(source / "package.json")], capture_output=True, text=True,
                timeout=5, env=native_editor_child_environment())
            paths = _load_json(probe.stdout) if probe.returncode == 0 else None
            bundled_media = (isinstance(paths, list) and len(paths) == 2 and
                all(isinstance(p, str) and Path(p).is_file() and os.access(p, os.X_OK)
                    for p in paths))
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    add("editor_media_binaries", bundled_media,
        "The editor requires its own installed ffmpeg-static and ffprobe-static binaries")
    add("ordinary_user", os.geteuid() != 0, "Run editor as an ordinary user with Chromium sandbox enabled")
    if config["provider"] == "local" and check_model:
        try:
            ids = _local_model_ids(config["base_url"])
            add("local_model", config["model_id"] in ids, "Configured model must be listed by the actual local server")
        except ValueError:
            add("local_model", False, "Start the configured local OpenAI-compatible model server")
    elif config["provider"] == "nvidia":
        add("provider_credentials", bool(os.environ.get("NVIDIA_API_KEY")), "NVIDIA_API_KEY presence only; no cloud request made")
    return {"workspace": str(root), "ready": all(c["ready"] for c in checks),
            "model_connection_checked": check_model and config["provider"] == "local", "checks": checks}


def _stage_asset(path, destination, rights):
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or not source.stat().st_size:
        raise ValueError("Authorized source must be a nonempty regular file")
    temporary = destination / (".copy-" + secrets.token_hex(8))
    digest = hashlib.sha256()
    before = source.stat()
    try:
        with source.open("rb") as src, open(temporary, "xb", opener=lambda p, f: os.open(p, f, 0o600)) as out:
            while chunk := src.read(1024 * 1024):
                digest.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        after = source.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError("Source changed while staging; original remains untouched")
        target = destination / (digest.hexdigest()[:16] + "-" + source.name)
        # A run has its own staging directory. Refuse duplicate source names.
        os.link(temporary, target)
        return {"path": str(target), "sha256": digest.hexdigest(), "bytes": after.st_size,
                "rights": rights, "rights_independently_verified": False}
    finally:
        temporary.unlink(missing_ok=True)


def run_workspace(path, *, brief, assets=(), rights=None, project=None,
                  max_turns=32, model_timeout=480, allow_cloud_image_upload=False,
                  reviewed_revision=False, reviewed_av_revision=False,
                  allow_cloud_audio_diagnostics=False, allow_public_research=False, searxng_url=None,
                  xvfb_binary=None, display=None):
    from .native_editor_session import build_parser, run_native_session
    root, config, grants = load_workspace(path)
    if not isinstance(brief, str) or not 1 <= len(brief.strip()) <= 24000:
        raise ValueError("Provide a nonempty creative brief up to 24000 characters")
    if assets and (not isinstance(rights, str) or not rights.strip() or len(rights) > 4096):
        raise ValueError("State ownership or license evidence for supplied assets with --rights")
    LocalModelSettings(base_url=config["base_url"], model_id=config["model_id"],
                       timeout_seconds=model_timeout)
    if type(max_turns) is not int or not 1 <= max_turns <= 128:
        raise ValueError("Model turn budget must be between 1 and 128")
    if reviewed_revision and reviewed_av_revision:
        raise ValueError("Choose one reviewed revision evidence mode")
    if type(reviewed_av_revision) is not bool or type(allow_cloud_audio_diagnostics) is not bool:
        raise ValueError("Reviewed audiovisual and cloud consent switches must be booleans")
    if config["provider"] == "local" and (allow_cloud_image_upload or allow_cloud_audio_diagnostics):
        raise ValueError("Cloud media permission is only applicable to NVIDIA")
    if allow_cloud_audio_diagnostics and not reviewed_av_revision:
        raise ValueError("Cloud audio diagnostics consent requires reviewed audiovisual mode")
    if config["provider"] == "nvidia" and (reviewed_revision or reviewed_av_revision):
        if not allow_cloud_image_upload:
            raise ValueError("NVIDIA reviewed revisions require explicit --allow-cloud-image-upload")
        if reviewed_av_revision and not allow_cloud_audio_diagnostics:
            raise ValueError("NVIDIA audiovisual review requires explicit --allow-cloud-audio-diagnostics")
    if searxng_url is not None:
        if not allow_public_research:
            raise ValueError("A SearXNG endpoint requires explicit --allow-public-research")
        from .creative_research import validate_searxng_url
        searxng_url = validate_searxng_url(searxng_url)
    project_path = None
    if project is not None:
        project_path = Path(project).expanduser().resolve(strict=True)
        if not project_path.is_relative_to(root / "projects") or not (project_path / "project.comfystudio").is_file():
            raise ValueError("Choose a saved native project inside this workspace")
    # An entirely empty native projects root permits a genuinely fresh
    # reviewed A/V session with source-bound snapshots for both render cuts.
    # Existing projects are never silently treated as an empty fresh trial.
    fresh_av = (reviewed_av_revision and project_path is None and
                not any((root / "projects").iterdir()))
    # Check before creating a run or copying media. No inference on bad setup.
    setup = doctor(root)
    if not setup["ready"]:
        missing = ", ".join(c["name"] for c in setup["checks"] if not c["ready"])
        raise ValueError("Studio setup incomplete: " + missing + "; run zx7-studio doctor")
    # One actual editor uses fixed native ports and one active project. A
    # kernel lock, not a stale PID file, releases automatically on process exit.
    import fcntl
    with open(root / ".run.lock", "a", opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("An editing session is already running in this workspace") from None
        sid = secrets.token_hex(12)
        session = root / "sessions" / sid
        session.mkdir(mode=0o700)
        with _bound_session_runner(lock, session, sid):
            locations = {n: root / n / sid for n in ("staging", "outputs", "state")}
            for directory in locations.values():
                directory.mkdir(mode=0o700)
            status = {"session_id": sid, "state": "preparing", "provider": config["provider"],
                      "model_id": config["model_id"], "artistic_quality_approved": False,
                      "render_snapshots_required": bool(fresh_av),
                      "outputs_directory": str(locations["outputs"]),
                      "projects_directory": str(root / "projects"),
                      "native_journal": str(session / "native-journal.jsonl")}
            _write_status(session, status)
            try:
                sources = dict.fromkeys(Path(a).expanduser().resolve(strict=True) for a in assets)
                ledger = [_stage_asset(a, locations["staging"], rights) for a in sources]
                _write_new(session / "sources.json", ledger)
                host = _read_private(root / "editor-grants.json")
                host.update({n + "_root": str(p) for n, p in locations.items() if n != "state"})
                _write_new(session / "host-grants.json", host)
                owner_context = {"authorized_sources": ledger,
                    "existing_native_project": str(project_path) if project_path else None,
                    "projects_root": str(root / "projects"), "outputs_root": str(locations["outputs"])}
                text = brief.strip() + "\n\nHost-authorized workspace facts (not an editing plan):\n" + json.dumps(owner_context, ensure_ascii=False)
                if len(text) > 32000:
                    raise ValueError("Brief and asset context exceed the native session budget")
                with open(session / "brief.txt", "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as out:
                    out.write(text)
                argv = ["--source", config["editor_source"], "--config", str(session / "host-grants.json"),
                        "--state", str(locations["state"]), "--brief-file", str(session / "brief.txt"),
                        "--receipt", str(session / "native-journal.jsonl"), "--provider", config["provider"],
                        "--model-id", config["model_id"], "--base-url", config["base_url"],
                        "--max-turns", str(max_turns), "--model-timeout", str(model_timeout),
                        "--structured-actions", "--evaluation-evidence",
                        ("reviewed-av-revision" if reviewed_av_revision else
                         "reviewed-revision" if reviewed_revision else "export")]
                if fresh_av:
                    argv += ["--fresh-trial-project", "--record-av-project-snapshots"]
                if allow_cloud_audio_diagnostics:
                    argv.append("--allow-cloud-audio-diagnostics")
                for flag, value in (("--xvfb-binary", xvfb_binary), ("--display", display)):
                    if value:
                        argv.extend([flag, str(value)])
                # A full studio grants more native tools than a single direct
                # function request admits. Both providers discover the same
                # current schemas in bounded groups, without reducing grants.
                argv.append("--indexed-catalog")
                if project_path is not None:
                    argv.extend(["--project", str(project_path)])
                if allow_cloud_image_upload:
                    argv.append("--allow-cloud-image-upload")
                if allow_public_research:
                    argv.append("--allow-public-research")
                if searxng_url is not None:
                    argv.extend(["--searxng-url", searxng_url])
                args = build_parser().parse_args(argv)
                if project_path is not None:
                    from .native_editor_project import checkpoint_saved_project
                    status["prior_project_checkpoint"] = checkpoint_saved_project(
                        project_path, session / "prior-project.comfystudio")
                status["state"] = "running"
                _write_status(session, status)
                summary = asyncio.run(run_native_session(args))
                status.update(state=("completed" if summary.get("evaluation_evidence_satisfied") is True
                                     else "needs_attention"), result=summary)
                _write_status(session, status)
                return status
            except BaseException as exc:
                # The persisted receipt/native project are kept. Never replay a
                # possible write or claim recovery from the status file alone.
                status.update(state="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                              error_type=type(exc).__name__, automatic_write_replay=False)
                _write_status(session, status)
                raise


def workspace_status(path):
    root, _, _ = load_workspace(path)
    held_before, bound_before = _probe_runner_lock(root / ".run.lock", binding=True)
    sessions = []
    for directory in sorted((root / "sessions").iterdir()):
        if not directory.is_symlink() and directory.is_dir():
            try:
                record = _read_private(directory / "status.json")
            except ValueError:
                # A new session directory precedes its first atomic status
                # publication. Do not turn that narrow window into an error.
                if (not (directory / "status.json").exists()
                        and not (directory / "status.json").is_symlink()):
                    continue
                raise
            sessions.append((directory, record))
    held_after, bound_after = _probe_runner_lock(root / ".run.lock", binding=True)
    bound_session = bound_after if bound_before == bound_after else None
    for directory, record in sessions:
        if record.get("state") not in ("preparing", "running"):
            continue
        session_held, _ = _probe_runner_lock(directory / ".runner.lock")
        if (held_before is True and held_after is True and session_held is True
                and bound_session == directory.name == record.get("session_id")):
            observed = "active"
        elif session_held is False or (held_before is False and held_after is False):
            observed = "not_running"
        else:
            observed = "unknown"
        # This is a read-only observation, never a replacement for the saved
        # state, an outcome/recovery claim, or permission to replay native writes.
        record["runner_liveness"] = {"status": observed,
            "requires_attention": observed != "active", "automatic_write_replay": False}
        if record["state"] == "running" and record.get("session_id") == directory.name:
            journal = directory / "native-journal.jsonl"
            if journal.exists() or journal.is_symlink():
                from .native_creative_audit import native_journal_progress
                record["native_progress"] = native_journal_progress(journal)
    return {"workspace": str(root), "sessions": [record for _, record in sessions],
            "runner_observation": {"workspace_lock_held": held_after,
                "bound_session_id": bound_session, "scope": "host_runner_only"}}


def main(argv=None):
    p = argparse.ArgumentParser(description="ZX7 Studio: create and revise native projects from an owner brief")
    commands = p.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a private studio; never overwrite existing work")
    init.add_argument("workspace", type=Path)
    init.add_argument("--source", type=Path, help="Override the installed editor path")
    init.add_argument("--model-id", help="Select a local model or override the provider default")
    init.add_argument("--provider", choices=("local", "nvidia"), default="local")
    init.add_argument("--base-url", default="http://127.0.0.1:8080")
    for name in ("doctor", "status"):
        commands.add_parser(name).add_argument("workspace", type=Path)
    verify = commands.add_parser("verify", help="Independently re-decode both reviewed A/V exports and match editable native project")
    verify.add_argument("workspace", type=Path)
    verify.add_argument("session_id")
    verify.add_argument("--max-decode-seconds", type=int, default=900,
                        help="Host resource limit for independent physical decoding, not a creative duration")
    run = commands.add_parser("run", help="Run the existing native AI editor; preserve session and source evidence")
    run.add_argument("workspace", type=Path)
    prompt = run.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--brief")
    prompt.add_argument("--brief-file", type=Path)
    run.add_argument("--asset", action="append", default=[], type=Path)
    run.add_argument("--rights")
    run.add_argument("--project", type=Path)
    run.add_argument("--max-turns", type=int, default=32)
    run.add_argument("--model-timeout", type=int, default=480)
    run.add_argument("--allow-cloud-image-upload", action="store_true")
    run.add_argument("--allow-public-research", action="store_true",
                     help="Allow model-written public queries to external research services")
    run.add_argument("--searxng-url", help="Optional owner-configured loopback SearXNG base URL")
    reviews = run.add_mutually_exclusive_group()
    reviews.add_argument("--reviewed-revision", action="store_true",
                         help="Require verified visual renders before and after a revision")
    reviews.add_argument("--reviewed-av-revision", action="store_true",
                         help="Require timed picture AND sound review and editable revision")
    run.add_argument("--allow-cloud-audio-diagnostics", action="store_true",
                     help="Separately allow NVIDIA to see numerical sound diagnostics (never raw WAV)")
    run.add_argument("--xvfb-binary")
    run.add_argument("--display")
    args = p.parse_args(argv)
    try:
        if args.command == "init":
            result = initialize_workspace(args.workspace, source=args.source, model_id=args.model_id,
                provider=args.provider, base_url=args.base_url)
        elif args.command == "doctor":
            result = doctor(args.workspace)
        elif args.command == "status":
            result = workspace_status(args.workspace)
        elif args.command == "verify":
            from .studio_owner_delivery import verify_owner_audiovisual_delivery
            result = verify_owner_audiovisual_delivery(
                args.workspace, args.session_id,
                max_decode_seconds=args.max_decode_seconds)
        else:
            if args.brief is not None:
                brief = args.brief
            else:
                with args.brief_file.open(encoding="utf-8") as stream:
                    brief = stream.read(24001)
            result = run_workspace(args.workspace, brief=brief, assets=args.asset, rights=args.rights,
                project=args.project, max_turns=args.max_turns, model_timeout=args.model_timeout,
                allow_cloud_image_upload=args.allow_cloud_image_upload,
                allow_public_research=args.allow_public_research, searxng_url=args.searxng_url,
                reviewed_revision=args.reviewed_revision,
                reviewed_av_revision=args.reviewed_av_revision,
                allow_cloud_audio_diagnostics=args.allow_cloud_audio_diagnostics,
                xvfb_binary=args.xvfb_binary, display=args.display)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "doctor":
            return 0 if result["ready"] else 2
        return 0 if args.command != "run" or result["state"] == "completed" else 3
    except (ValueError, OSError, RuntimeError) as exc:
        print("Studio could not complete: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
