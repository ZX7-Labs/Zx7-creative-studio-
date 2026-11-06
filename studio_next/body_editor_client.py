"""Bounded transport to an independently running local native editor.

Discovery preserves native schemas but grants no authority. Hosts explicitly
grant each callable tool as read or write. A host policy can additionally check
workspace paths and arguments; native file operations require such a policy at
the integrating boundary. This client is not a filesystem/process sandbox and
does not authenticate other local processes.

CLI grants come from a host-owned JSON file, never the request:
``{"allowed_tools":{"get_project":"read"},"allowed_access":["read"]}``.
Use the Python policy callback for workspace-restricted native operations.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
import http.client
import json
import math
from pathlib import Path
import re
import sys
from types import MappingProxyType
from typing import Any
import uuid


class EditorClientError(RuntimeError):
    """The editor transport or native operation failed."""


class EditorProtocolError(EditorClientError):
    """The editor returned an invalid or unsuccessful RPC response."""


class EditorToolError(EditorClientError):
    """A native tool explicitly reported failure."""

    def __init__(self, tool_name: str, result: dict):
        self.tool_name = tool_name
        self.result = result
        super().__init__(f"Native editor tool {tool_name!r} reported isError")


class EditorAccessError(PermissionError):
    """Host grants, caller access or policy prohibit the call."""


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(value):
    return json.loads(value, parse_constant=_reject_constant,
                      parse_float=_finite_float, object_pairs_hook=_unique_object)


def _json_arguments(arguments):
    if not isinstance(arguments, dict):
        raise ValueError("Native tool arguments must be a JSON object")

    def check(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object keys must be strings")
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
        elif value is not None and type(value) not in (str, int, float, bool):
            raise ValueError("Arguments must contain only JSON values")

    try:
        check(arguments)
        return _load_json(json.dumps(arguments, allow_nan=False))
    except (TypeError, RecursionError, OverflowError) as exc:
        raise ValueError("Arguments must be finite JSON values") from exc


def _access_modes(values):
    if not isinstance(values, (set, frozenset, list, tuple)) or any(
            value not in ("read", "write") for value in values):
        raise ValueError("Allowed access must contain only read/write modes")
    return frozenset(values)


class LocalEditorClient:
    """Local JSON-RPC with explicit host grants and per-call access.

    ``policy(tool_name, arguments, access)`` must return exactly True. It runs
    before HTTP, after host/caller permission checks. Without policy only explicit
    grants/access are enforced. Failed calls are never retried: a native write
    may have happened even when its response is lost.
    """

    def __init__(self, endpoint: str, *, allowed_tools: Mapping[str, str],
                 policy: Callable[[str, dict, str], bool] | None = None,
                 timeout: float = 30.0, max_response_bytes: int = 8 * 1024 * 1024):
        match = re.fullmatch(r"http://(127\.0\.0\.1|\[::1\]):([0-9]+)/mcp", endpoint) if isinstance(endpoint, str) else None
        if match is None or not 1 <= int(match[2]) <= 65535:
            raise ValueError("Editor endpoint must be http://127.0.0.1:PORT/mcp or http://[::1]:PORT/mcp")
        if not isinstance(allowed_tools, Mapping) or any(
                not isinstance(name, str) or not name or access not in ("read", "write")
                for name, access in allowed_tools.items()):
            raise ValueError("Host allowed_tools must map tool names to read/write")
        if policy is not None and not callable(policy):
            raise ValueError("Host policy must be callable")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be positive and finite")
        if type(max_response_bytes) is not int or max_response_bytes <= 0:
            raise ValueError("Response byte limit must be a positive integer")
        self._endpoint = endpoint
        self._host = match[1].strip("[]")
        self._port = int(match[2])
        self._allowed_tools = MappingProxyType(dict(allowed_tools))
        self._policy = policy
        self._timeout = timeout
        self._max_response_bytes = max_response_bytes

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def allowed_tools(self) -> Mapping[str, str]:
        return self._allowed_tools

    def _rpc(self, method: str, params: dict) -> Any:
        request_id = str(uuid.uuid4())
        body = json.dumps({"jsonrpc": "2.0", "id": request_id,
                           "method": method, "params": params}, allow_nan=False).encode("utf-8")
        # Direct literal-address connection: no DNS, ambient proxies or redirects.
        connection = http.client.HTTPConnection(self._host, self._port, timeout=self._timeout)
        try:
            connection.request("POST", "/mcp", body=body,
                               headers={"Content-Type": "application/json", "Accept": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                raise EditorProtocolError(f"Editor HTTP status {response.status}; redirects are not followed")
            data = response.read(self._max_response_bytes + 1)
            if len(data) > self._max_response_bytes:
                raise EditorProtocolError("Editor response exceeds byte limit")
        except (OSError, http.client.HTTPException) as exc:
            raise EditorClientError(f"Local editor transport failed: {exc}") from exc
        finally:
            connection.close()
        try:
            message = _load_json(data.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise EditorProtocolError("Editor response is not valid finite JSON") from exc
        if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
                or message.get("id") != request_id
                or ("error" in message) == ("result" in message)):
            raise EditorProtocolError("Invalid JSON-RPC response or mismatched request id")
        if "error" in message:
            raise EditorProtocolError(f"Native editor RPC error: {message['error']}")
        return message["result"]

    def list_tools(self) -> list[dict]:
        """Return complete native descriptors; discovery grants no calls."""
        result = self._rpc("tools/list", {})
        if (not isinstance(result, dict) or not isinstance(result.get("tools"), list)
                or result.get("nextCursor") not in (None, "")):
            raise EditorProtocolError("Malformed or paginated native tool catalog")
        names = set()
        for tool in result["tools"]:
            if (not isinstance(tool, dict) or not isinstance(tool.get("name"), str)
                    or not tool["name"] or tool["name"] in names
                    or not isinstance(tool.get("inputSchema"), dict)
                    or tool["inputSchema"].get("type") != "object"
                    or ("description" in tool and not isinstance(tool["description"], str))):
                raise EditorProtocolError("Malformed native tool descriptor")
            names.add(tool["name"])
        return result["tools"]

    def call(self, tool_name: str, arguments: dict, *,
             allowed_access=frozenset({"read"})) -> dict:
        """Call after host grants, caller access and argument policy checks."""
        if not isinstance(tool_name, str) or tool_name not in self._allowed_tools:
            raise EditorAccessError("Native tool has no host grant")
        access = self._allowed_tools[tool_name]
        if access not in _access_modes(allowed_access):
            raise EditorAccessError(f"Native tool requires {access} access")
        arguments = _json_arguments(arguments)
        if self._policy is not None and self._policy(tool_name, arguments, access) is not True:
            raise EditorAccessError("Native tool rejected by host policy")
        if tool_name == "split_clip":
            # The upstream inspect_clip summary omits effects/keyframes.
            # Require both the existing per-clip identity inspection and the
            # complete native get_timeline creative-state snapshot.
            from .body_editor_split_guard import preflight_non_destructive_native_split
            from .body_editor_extract_guard import (
                assert_plain_source_in_full_timeline, read_complete_timeline,
            )
            inspection = preflight_non_destructive_native_split(
                self, arguments, allowed_access=allowed_access)
            timeline = read_complete_timeline(self, allowed_access=allowed_access)
            for clip_id in inspection["preflighted_plain_source_clips"]:
                assert_plain_source_in_full_timeline(
                    self, clip_id, allowed_access=allowed_access, timeline=timeline)
        elif tool_name == "extract_range" and arguments.get("previewOnly") is False:
            # Extract internally splits at both range boundaries. A native
            # preview is used to discover actual split targets, not to mutate.
            from .body_editor_extract_guard import preflight_non_destructive_native_extract
            preflight_non_destructive_native_extract(
                self, arguments, allowed_access=allowed_access)
        result = self._rpc("tools/call", {"name": tool_name, "arguments": arguments})
        if (not isinstance(result, dict) or not isinstance(result.get("content"), list)
                or ("isError" in result and type(result["isError"]) is not bool)):
            raise EditorProtocolError("Malformed native tool result")
        if result.get("isError"):
            raise EditorToolError(tool_name, result)
        return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--permissions", required=True, type=Path)
    parser.add_argument("--request", required=True, action="store_true",
                        help="Read one discover/call JSON request from stdin")
    options = parser.parse_args(argv)
    try:
        permissions = _load_json(options.permissions.read_text(encoding="utf-8"))
        if not isinstance(permissions, dict) or set(permissions) - {"allowed_tools", "allowed_access"}:
            raise ValueError("Invalid host permissions file")
        client = LocalEditorClient(options.endpoint, allowed_tools=permissions["allowed_tools"])
        access = _access_modes(permissions.get("allowed_access", ["read"]))
        raw = sys.stdin.read(1024 * 1024 + 1)
        if len(raw.encode("utf-8")) > 1024 * 1024:
            raise ValueError("Request exceeds one MiB byte limit")
        request = _load_json(raw)
        if not isinstance(request, dict):
            raise ValueError("Request must be a JSON object")
        operation = request.get("operation")
        if operation == "discover" and set(request) == {"operation"}:
            result = {"tools": client.list_tools()}
        elif operation == "call" and set(request) == {"operation", "tool_name", "arguments"}:
            result = client.call(request["tool_name"], request["arguments"], allowed_access=access)
        else:
            raise ValueError("Request must contain discover, or call with tool_name and arguments")
        print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
        return 0
    except (EditorClientError, EditorAccessError, ValueError, KeyError, OSError, RecursionError) as exc:
        print(json.dumps({"error": {"type": type(exc).__name__, "message": str(exc)}}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
