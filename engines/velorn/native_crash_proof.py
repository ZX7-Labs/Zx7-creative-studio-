# SPDX-License-Identifier: GPL-3.0-only
"""Isolated synthetic CI proof of native Electron SIGKILL + saved project recovery.

This test intentionally never targets an arbitrary PID: the launcher reports
its own exact child PID into a private ephemeral test log, the identity is
checked against the source-pinned installed Electron binary, its launch path,
its owner UID and the isolated Xvfb test context before SIGKILL.
There is no production crash endpoint or model-visible kill capability.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import signal


_PID_MARKER = re.compile(r"^ZX7_CI_NATIVE_ELECTRON_PID=([0-9]+)$", re.MULTILINE)


def _trusted_pid_from_log(log_content: str) -> int:
    markers = _PID_MARKER.findall(log_content)
    if len(markers) != 1:
        raise AssertionError("Expected exactly one CI launcher-owned Electron PID")
    pid = int(markers[0])
    if not 100 < pid <= 2**22:
        raise AssertionError("Invalid CI Electron PID")
    return pid


def _verify_process_identity(
    *, cmdline: bytes, process_uid: int, editor_source: Path, expected_uid: int,
) -> None:
    if process_uid != expected_uid:
        raise AssertionError("Native editor process belongs to a different OS user")
    args = [entry.decode("utf-8", "strict") for entry in cmdline.split(b"\x00")
            if entry]
    expected_executable = (
        editor_source.resolve() / "node_modules/electron/dist/electron").resolve()
    if (not args or Path(args[0]).resolve() != expected_executable or
            str(editor_source.resolve()) not in args):
        raise AssertionError("PID is not the exact source-pinned CI Electron child")
    if any(arg.startswith("--remote-debugging-address=0.0.0.0")
           for arg in args):
        raise AssertionError("Unexpected non-loopback debug interface")


def _candidate_pid(editor_source: Path, state_root: Path) -> int:
    if os.environ.get("CI") != "true":
        raise PermissionError("Native crash proof is disabled outside synthetic CI")
    source = editor_source.resolve(strict=True)
    root = state_root.resolve(strict=True)
    if not source.is_dir() or not root.is_dir() or root.is_symlink():
        raise AssertionError("Native crash proof requires existing isolated folders")
    # The current and previous isolated test sessions may both have logs,
    # but only the currently live process is eligible.
    matches = []
    for file in root.glob("session-*/launcher.log"):
        if file.is_symlink() or not file.is_file():
            raise AssertionError("Unsafe CI launcher log")
        if not file.resolve().is_relative_to(root):
            raise AssertionError("Launcher log escaped isolated state root")
        content = file.read_text(encoding="utf-8")
        markers = _PID_MARKER.findall(content)
        if not markers:
            continue
        pid = _trusted_pid_from_log(content)
        proc = Path("/proc") / str(pid)
        try:
            stat = proc.stat()
            cmdline = (proc / "cmdline").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            continue
        _verify_process_identity(
            cmdline=cmdline, process_uid=stat.st_uid,
            editor_source=source, expected_uid=os.getuid(),
        )
        matches.append(pid)
    if len(matches) != 1:
        raise AssertionError(
            f"Expected exactly one active launcher-owned Electron process, found {len(matches)}")
    return matches[0]


def kill_exact_editor_after_saved_revision(
    *, editor_source: Path, state_root: Path, display: str,
) -> int:
    if os.environ.get("CI") != "true" or display != "127.0.0.1:97":
        raise PermissionError("Crash proof requires the known isolated CI Xvfb display")
    pid = _candidate_pid(editor_source, state_root)
    # Pin the kernel process identity BEFORE signalling. /proc PID alone
    # cannot prevent the process exiting and its numeric PID being reused
    # between an identity check and a kill(2) system call.
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise RuntimeError("Linux pidfd support required; refuse unsafe PID kill")
    fd = os.pidfd_open(pid, 0)
    try:
        proc = Path("/proc") / str(pid)
        _verify_process_identity(
            cmdline=(proc / "cmdline").read_bytes(),
            process_uid=proc.stat().st_uid,
            editor_source=editor_source, expected_uid=os.getuid(),
        )
        # No graceful shutdown: test unexpected native process death
        # strictly *after* a physically verified save. Never replay a write.
        signal.pidfd_send_signal(fd, signal.SIGKILL)
    finally:
        os.close(fd)
    return pid
