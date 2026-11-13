# SPDX-License-Identifier: GPL-3.0-only
"""Installed, source-pinned native Electron live-save integration proof.

These are synthetic X11 actions, not a real human or a creative model.
All native writes are made through the installed MCP editor; the fault gate
only delays its actual atomic file writer (never changes React/Redux state).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time

from native_pointer_proof import drag_native_clip_pointer
from native_save_interleave_proof import kill_exact_editor_during_native_write


def saved_clip(document: Path, clip_id: str):
    data = json.loads(document.read_text(encoding="utf-8"))
    matches = [
        clip for timeline in data["timelines"]
        for clip in timeline["clips"] if clip["id"] == clip_id
    ]
    if len(matches) != 1:
        raise AssertionError("Original native source video clip missing or duplicated")
    return matches[0], data["modified"]


async def await_native_gate(gate: Path, pending: asyncio.Task) -> None:
    deadline = time.monotonic() + 14
    while not (gate / "entered").exists():
        if pending.done():
            raise AssertionError("Native save finished before entering real atomic writer")
        if time.monotonic() >= deadline:
            raise AssertionError("Real native atomic writer never reached in-flight gate")
        await asyncio.sleep(.05)
    if pending.done() or (gate / "release").exists():
        raise AssertionError("Save barrier was not held for a human edit or process death")


async def exercise_live_native_save(
        *, session, call, gate: Path, project: Path, native_path: Path,
        editor_source: Path, state_root: Path, display: str, pointer_clip_id: str,
        original: Path, digest):
    """Return source-bound recovery receipt after physical live GUI conflict and SIGKILL.

    A first save snapshot is intentionally stalled after its real native
    atomic temp write. The X11 clip move occurs before filesystem rename.
    A subsequent independently requested second save must persist the newer
    human-like authoring. A third actual save is interrupted BEFORE rename.
    """
    assert gate.is_dir() and not gate.is_symlink()
    assert native_path == project / "project.comfystudio"
    old_disk_sha, original_sha = digest(native_path), digest(original)
    before, previous_stamp = saved_clip(native_path, pointer_clip_id)
    original_start = float(before["startTime"])

    (gate / "armed").write_text("1", encoding="utf-8")
    pending = asyncio.create_task(call(session, "save_project", {"previewOnly": False}))
    try:
        await await_native_gate(gate, pending)
        assert digest(native_path) == old_disk_sha
        # IMPORTANT: This changes live native Velorn GUI with an actual mouse
        # while the renderer's earlier source snapshot is pending disk rename.
        pointer = await drag_native_clip_pointer(display, pointer_clip_id)
        # Do NOT issue a second MCP tool while the first save is waiting.
        # The native adapter may serialize RPCs; the mouse is independent OS
        # input. Verify the resulting clip through a real read after release.
        assert not pending.done() and digest(native_path) == old_disk_sha, (
            "Native save completed before testing concurrent live editing")
    finally:
        # This release is explicit only. No replay of an unconfirmed write.
        if (gate / "entered").exists():
            (gate / "release").write_text("1", encoding="utf-8")
    first = await asyncio.wait_for(pending, timeout=45)
    first_clip, first_stamp = saved_clip(native_path, pointer_clip_id)
    assert first_stamp == first["result"]["project"]["modified"]
    assert abs(float(first_clip["startTime"]) - original_start) < .001, (
        "In-flight first save retroactively captured newer GUI changes")
    assert digest(original) == original_sha

    # The live edit must remain in-memory. The first completed earlier snapshot
    # must not clear the dirty epoch or silently overwrite newer content.
    after_first = await call(session, "get_timeline", {"includeClips": True})
    retained = next(c for c in after_first["clips"] if c["id"] == pointer_clip_id)
    shifted_start = float(retained["startTime"])
    assert abs(shifted_start - original_start) > .02, (
        "Earlier save acknowledgment reverted the X11-authored edit")
    second = await call(session, "save_project", {"previewOnly": False})
    second_clip, second_stamp = saved_clip(native_path, pointer_clip_id)
    assert second_stamp == second["result"]["project"]["modified"]
    assert abs(float(second_clip["startTime"]) - shifted_start) < .001
    committed_sha = digest(native_path)
    assert committed_sha != old_disk_sha and digest(original) == original_sha
    print("ACTUAL_NATIVE_INFLIGHT_GUI_EDIT " + json.dumps({
        **pointer,
        "real_earlier_native_temp_write_held_during_X11_drag": True,
        "old_snapshot_cannot_undo_new_live_GUI_clip_movement": True,
        "first_save_document_retained_pre_edit_state": True,
        "second_explicit_save_persisted_newer_GUI_edit": True,
        "original_video_SHA_unchanged": True,
        "neural_model_or_professional_artist_tested": False,
    }, sort_keys=True), flush=True)

    # Re-arm the same CI-only fault boundary for another REAL native save.
    # The previous committed source is our recovery oracle.
    (gate / "armed").write_text("1", encoding="utf-8")
    third = asyncio.create_task(call(session, "save_project", {"previewOnly": False}))
    await await_native_gate(gate, third)
    assert digest(native_path) == committed_sha
    pid, temps = kill_exact_editor_during_native_write(
        editor_source=editor_source, state_root=state_root, display=display,
        gate=gate, project=project)
    assert pid > 100 and len(temps) == 1
    assert digest(native_path) == committed_sha
    assert digest(original) == original_sha
    third.cancel()
    try:
        await asyncio.wait_for(asyncio.gather(third, return_exceptions=True), timeout=10)
    except (asyncio.TimeoutError, Exception):
        # The editor process is dead. This uncertain native call is NEVER replayed.
        pass
    for name in ("armed", "entered", "release"):
        (gate / name).unlink(missing_ok=True)
    print("ACTUAL_NATIVE_INTERRUPTED_SAVE_BEFORE_RENAME " + json.dumps({
        "actual_native_atomic_temp_was_written": True,
        "kernel_pidfd_killed_exact_CI_Electron_during_write": True,
        "committed_native_document_SHA_unchanged": True,
        "original_video_SHA_unchanged": True,
        "uncertain_native_write_not_retried": True,
        "power_loss_or_fsync_durability_certified": False,
    }, sort_keys=True), flush=True)
    return {
        "committed_sha": committed_sha,
        "video_clip_start": shifted_start,
        "source_sha": original_sha,
    }
