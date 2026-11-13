# SPDX-License-Identifier: GPL-3.0-only
"""Isolated native project write-interruption proof; no production kill endpoint.

Only an exact CI Xvfb process, verified by its own source-bound launcher
identity and an active, source-pinned in-flight atomic-save barrier, is eligible.
Never target owner projects or use a bare PID after an identity check.
"""
from __future__ import annotations

import os
from pathlib import Path
import signal

try:
    from .native_crash_proof import _candidate_pid, _verify_process_identity
except ImportError:
    from native_crash_proof import _candidate_pid, _verify_process_identity


def validate_native_interruption_gate(
        *, gate: Path, project: Path, state_root: Path, source: Path,
        display: str, pid: int) -> tuple[Path, ...]:
    if os.environ.get("CI") != "true" or display != "127.0.0.1:97":
        raise PermissionError("Isolated exact synthetic Xvfb required")
    if not all(isinstance(p, Path) for p in (gate, project, state_root, source)):
        raise TypeError("Source and project identities must be Path objects")
    gate_root = gate.resolve(strict=True)
    project_root = project.resolve(strict=True)
    state = state_root.resolve(strict=True)
    editor = source.resolve(strict=True)
    if (gate.is_symlink() or project.is_symlink() or state_root.is_symlink() or
            source.is_symlink() or not gate_root.is_dir() or
            not project_root.is_dir() or not state.is_dir() or not editor.is_dir()):
        raise AssertionError("Unsafe native-save gate or project path")
    test_root = state.parent
    if (state.name != "state" or
            not test_root.name.startswith("zx7-editor-mcp-") or
            gate_root != test_root / "native-save-interleave-gate" or
            not project_root.is_relative_to(test_root / "projects")):
        raise AssertionError("Gate/project are not in the same synthetic CI fixture")

    for marker in ("armed", "entered"):
        member = gate_root / marker
        if member.is_symlink() or not member.is_file():
            raise AssertionError("Missing safe in-flight native-save marker")
    if (gate_root / "release").exists():
        raise AssertionError("Interruption refused after native-save release")
    entered = (gate_root / "entered").read_text(encoding="utf-8").strip()
    if entered != str(pid) or not 100 < pid <= 2**22:
        raise AssertionError("Gate marker does not identify the exact live Electron PID")
    old = project_root / "project.comfystudio"
    if old.is_symlink() or not old.is_file():
        raise AssertionError("No last committed native project to preserve")
    candidates = tuple(project_root.glob(".project.comfystudio.*.tmp"))
    if (len(candidates) != 1 or candidates[0].is_symlink() or
            not candidates[0].is_file() or candidates[0].stat().st_size < 10):
        raise AssertionError("No unique actual in-progress atomic temp write")
    return candidates


def kill_exact_editor_during_native_write(
        *, editor_source: Path, state_root: Path, display: str,
        gate: Path, project: Path) -> tuple[int, tuple[Path, ...]]:
    if os.environ.get("CI") != "true" or display != "127.0.0.1:97":
        raise PermissionError("Native write crash proof disabled outside isolated CI")
    pid = _candidate_pid(editor_source, state_root)
    candidates = validate_native_interruption_gate(
        gate=gate, project=project, state_root=state_root,
        source=editor_source, display=display, pid=pid)
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise RuntimeError("Linux pidfd required, refusing unsafe signal")
    fd = os.pidfd_open(pid, 0)
    try:
        proc = Path("/proc") / str(pid)
        _verify_process_identity(
            cmdline=(proc / "cmdline").read_bytes(),
            process_uid=proc.stat().st_uid,
            editor_source=editor_source, expected_uid=os.getuid())
        # Recheck the marker after the kernel has pinned the process identity.
        validate_native_interruption_gate(
            gate=gate, project=project, state_root=state_root,
            source=editor_source, display=display, pid=pid)
        signal.pidfd_send_signal(fd, signal.SIGKILL)
    finally:
        os.close(fd)
    return pid, candidates
