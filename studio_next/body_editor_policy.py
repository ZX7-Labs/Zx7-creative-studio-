"""Host-owned local editor grants and argument-path checks.

These checks cover the pinned editor's explicit filesystem arguments. They do
not sandbox Electron, police another process using its raw MCP port, remove
filesystem races or validate references embedded in native project documents.
Use trusted projects and one trusted local editor instance.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
import secrets
from pathlib import Path
from types import MappingProxyType

from .body_editor_client import EditorAccessError, EditorPreDispatchError, LocalEditorClient, _load_json
from .body_editor_delivery import admitted_owner_delivery


_CONFIG_LIMIT = 1024 * 1024
_BLOCKED = frozenset({
    "search_stock_media", "import_stock_media", "diagnose_comfyui_connection",
    "set_comfyui_connection", "repair_comfyui_connection", "guide_comfyui_setup",
    "control_comfyui_launcher", "get_comfyui_launcher_logs", "validate_comfyui_nodes",
    "list_velorn_workflows", "inspect_velorn_workflow", "list_comfyui_templates",
    "import_comfyui_workflow", "install_workflow_setup", "get_workflow_install_status",
    "generate_music", "generate_captions", "get_music_generation_status",
    "get_generation_queue_status", "get_generation_status",
    "prepare_generation_from_timeline_context", "list_recent_projects",
    "duplicate_project", "run_mcp_action_plan", "export_delivery_batch",
})
_FILE_KEYS = frozenset({"path", "filePath", "sourcePath", "projectPath",
                        "sourceProjectPath", "outputPath", "rendersDir"})
_LOGICAL_PATH_TOOLS = frozenset({"create_asset_folder", "move_assets_to_folder",
                                 "move_unused_assets_to_folder"})


def blocked_editor_tool(name: str) -> bool:
    """Editing grants cannot enable optional generation or host-management calls."""
    return (name in _BLOCKED or name.startswith(("queue_", "regenerate_", "transcribe_"))
            or "music_video" in name)


def _root(value) -> Path:
    if (not isinstance(value, (str, Path)) or str(value) != str(value).strip()
            or not Path(value).is_absolute()):
        raise ValueError("Editor roots must be explicit absolute paths")
    try:
        root = Path(value).resolve()
        ancestor = root
        while not ancestor.exists() and ancestor.parent != ancestor:
            ancestor = ancestor.parent
        if not ancestor.is_dir():
            raise ValueError("Editor root has a non-directory ancestor")
        return root
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("Editor root cannot be resolved") from exc


def _access(values) -> frozenset[str]:
    if not isinstance(values, (list, tuple, set, frozenset)) or any(
            value not in ("read", "write") for value in values):
        raise ValueError("Editor allowed_access must contain only read/write")
    return frozenset(values)


def _scoped_path(value, roots) -> bool:
    if (not isinstance(value, str) or not value or value != value.strip()
            or not Path(value).is_absolute()):
        return False
    candidate = Path(value)
    try:
        # resolve(strict=False) alone follows dangling links into nonexistent
        # locations. Detect those before authorizing a future output path.
        ancestor = candidate
        while True:
            if ancestor.is_symlink() and not ancestor.exists():
                return False
            if ancestor.exists():
                break
            if ancestor.parent == ancestor:
                return False
            ancestor = ancestor.parent
        canonical = candidate.resolve()
        return any(canonical.is_relative_to(root) for root in roots)
    except (OSError, RuntimeError, ValueError):
        return False


def _project_name(value) -> bool:
    return (isinstance(value, str) and bool(value.strip())
            and value.strip() not in (".", "..") and not any(
                character in "/\\" or ord(character) < 32 for character in value))


@dataclass(frozen=True)
class EditorPathPolicy:
    projects_root: Path
    staging_root: Path
    outputs_root: Path

    def __post_init__(self):
        for name in ("projects_root", "staging_root", "outputs_root"):
            object.__setattr__(self, name, _root(getattr(self, name)))

    def __call__(self, tool_name: str, arguments: dict, access: str) -> bool:
        if (not isinstance(tool_name, str) or not isinstance(arguments, dict)
                or access not in ("read", "write") or blocked_editor_tool(tool_name)):
            return False
        projects = (self.projects_root,)
        sources = (self.projects_root, self.staging_root)
        outputs = (self.projects_root, self.outputs_root)
        fields = {}
        if tool_name in ("import_asset_from_path", "relink_asset"):
            fields = {key: sources for key in ("path", "filePath", "sourcePath")}
            if not any(arguments.get(key) for key in fields):
                return False
        elif tool_name == "open_project":
            fields = {"projectPath": projects}
            if not arguments.get("projectPath"):
                return False
        elif tool_name in ("export_timeline", "export_fcpxml"):
            fields = {"outputPath": outputs}
        elif tool_name == "inspect_export_file":
            fields = {key: outputs for key in ("path", "filePath", "outputPath", "rendersDir")}
        for key in _FILE_KEYS.intersection(arguments):
            if key == "path" and tool_name in _LOGICAL_PATH_TOOLS:
                continue  # Native asset-panel hierarchy, not a host file path.
            if key not in fields or not _scoped_path(arguments[key], fields[key]):
                return False
        if tool_name == "import_asset_from_path":
            # Pinned Velorn prioritizes an explicit category over its extension
            # inference. Its conventional audio-only extensions must not be
            # mislabeled as visual assets. This is a format/ABI check, not
            # proof of media contents, and never rewrites the Brain's input.
            source = next(arguments[key] for key in ("path", "filePath", "sourcePath")
                          if arguments.get(key))
            requested = (arguments.get("category") or arguments.get("type") or
                         arguments.get("assetType"))
            if (isinstance(requested, str) and
                    requested.strip().lower() in ("video", "image", "images") and
                    Path(source).suffix.lower() in (".wav", ".mp3", ".flac", ".aac", ".aif", ".aiff")):
                try:
                    single_file = Path(source).is_file()
                except OSError:
                    return False
                if single_file:
                    raise EditorPreDispatchError("import_category_mismatch")
        if tool_name == "open_project":
            # The native loader appends one of these names, then follows it
            # through readFile. Checking only the folder misses document links.
            project = Path(arguments["projectPath"])
            if any(not _scoped_path(str(project / filename), projects)
                   for filename in ("project.comfystudio", "project.storyflow")):
                return False
        if tool_name in ("export_timeline", "export_fcpxml"):
            if "outputPath" not in arguments:
                raise EditorPreDispatchError("output_path_required")
            try:
                Path(arguments["outputPath"]).lstat()
            except FileNotFoundError:
                pass
            except OSError:
                return False
            else:
                raise EditorPreDispatchError("output_exists")
        if tool_name == "create_project":
            names = [arguments[key] for key in ("name", "projectName", "title") if key in arguments]
            if not names or not all(_project_name(name) for name in names):
                return False
        return True


@dataclass(frozen=True)
class EditorConfig:
    endpoint: str
    projects_root: Path
    staging_root: Path
    outputs_root: Path
    allowed_tools: Mapping[str, str]
    allowed_access: frozenset[str] = frozenset({"read"})
    timeout: float = 30.0
    verify_native_exports: bool = False
    required_export_delivery: Mapping[str, object] | None = None
    _policy: EditorPathPolicy = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        for name in ("projects_root", "staging_root", "outputs_root"):
            object.__setattr__(self, name, _root(getattr(self, name)))
        if not isinstance(self.allowed_tools, Mapping) or any(
                not isinstance(name, str) or not name or access not in ("read", "write")
                or blocked_editor_tool(name) for name, access in self.allowed_tools.items()):
            raise ValueError("Editor allowed_tools contains an invalid or blocked host grant")
        object.__setattr__(self, "allowed_tools", MappingProxyType(dict(self.allowed_tools)))
        object.__setattr__(self, "allowed_access", _access(self.allowed_access))
        if type(self.timeout) not in (int, float) or not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("Editor timeout must be positive and finite")
        if type(self.verify_native_exports) is not bool:
            raise ValueError("Native export verification must be explicitly enabled by the host")
        # Trusted host's deliverable, not model-authored mutable state.
        object.__setattr__(self, "required_export_delivery",
                           admitted_owner_delivery(self.required_export_delivery))
        # Reuse the transport's endpoint/grant validation without connecting.
        LocalEditorClient(self.endpoint, allowed_tools=self.allowed_tools, timeout=self.timeout)
        object.__setattr__(self, "_policy", EditorPathPolicy(
            self.projects_root, self.staging_root, self.outputs_root))

    def client(self, *, native_source=None) -> LocalEditorClient:
        return LocalEditorClient(self.endpoint, allowed_tools=self.allowed_tools,
            timeout=self.timeout, policy=self._policy, native_source=native_source)


class OwnerExportOffer:
    """An optional host-scoped argument candidate, never an export or reservation.

    Only the source-pinned H264 project-size route is known here. Native
    readiness and the no-overwrite policy are authoritative at dispatch;
    an offer neither changes timeline settings nor chooses a creative range.
    """
    def __init__(self, config: EditorConfig):
        if not isinstance(config, EditorConfig):
            raise TypeError("Owner delivery offer requires trusted EditorConfig")
        self._config = config
        self._path = None

    def _available(self, path):
        try:
            return self._config._policy("export_timeline", {"outputPath": str(path)}, "write")
        except (EditorPreDispatchError, OSError):
            return False

    def candidate(self, validator):
        config = self._config
        approved = config.required_export_delivery
        root = config.outputs_root
        if (approved is None or approved["video_codec"] != "h264" or
                config.allowed_tools.get("export_timeline") != "write" or
                config.allowed_tools.get("check_export_readiness") != "read" or
                not {"read", "write"}.issubset(config.allowed_access)):
            return None
        try:
            if not root.is_dir() or root.resolve(strict=True) != root:
                return None
        except (OSError, RuntimeError):
            return None
        properties = validator.schema.get("properties", {})
        # Do not invent fields or fill unknown required artistic inputs.
        if not {"target", "resolution", "outputPath", "previewOnly"}.issubset(properties):
            return None
        if self._path is None or not self._available(self._path):
            self._path = None
            for _ in range(4):
                proposed = root / ("export-" + secrets.token_hex(12) + ".mp4")
                if self._available(proposed):
                    self._path = proposed
                    break
        if self._path is None:
            return None
        arguments = {"outputPath": str(self._path), "target": "h264_project",
                     "resolution": "project", "previewOnly": False}
        if "fps" in properties:
            arguments["fps"] = approved["fps"]
        if not validator.is_valid(arguments):
            return None
        return {"tool": "export_timeline", "arguments": arguments,
                "owner_delivery_profile": dict(approved),
                "native_readiness_verified": False,
                "optional_model_selected_call": True,
                "note": "Project size must match; full timeline, no implied trim. Native readiness and destination are rechecked before dispatch."}

    def retire_submitted(self, arguments):
        # A native export may have started before any file is visible.
        # Never keep offering that same candidate after an apply submission.
        if arguments.get("previewOnly") is not True:
            self._path = None


def load_editor_config(path) -> EditorConfig:
    """Read bounded host JSON; never create directories or accept model grants."""
    try:
        with Path(path).open("rb") as source:
            data = source.read(_CONFIG_LIMIT + 1)
        if len(data) > _CONFIG_LIMIT:
            raise ValueError("Editor config exceeds one MiB byte limit")
        value = _load_json(data.decode("utf-8"))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Editor config must be finite UTF-8 JSON") from exc
    required = {"endpoint", "projects_root", "staging_root", "outputs_root", "allowed_tools"}
    if (not isinstance(value, dict) or set(value) - required - {"allowed_access", "timeout", "verify_native_exports", "required_export_delivery"}
            or required - set(value)):
        raise ValueError("Editor config has missing or unknown fields")
    return EditorConfig(**value)
