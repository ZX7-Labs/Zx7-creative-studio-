# SPDX-License-Identifier: GPL-3.0-only
"""Real installed native Electron vs independent Linux project writer.

Synthetic test media only. The external writer must commit through the *same*
exact, pinned native CAS module while an Electron session has an older loaded
project. This does not fake a second GUI/editor or authorize arbitrary files.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

_MARKER = "source-native-independent-os-writer"


def _expected_digest(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


async def exercise_external_native_writer_conflict(
    *, session, call, editor_source: Path, native_path: Path, original: Path,
    digest, display: str, active_project: Path,
):
    if os.environ.get("CI") != "true" or display != "127.0.0.1:97":
        raise PermissionError("External native writer proof is isolated CI-only")
    module = (editor_source / "electron" / "nativeProjectCAS.cjs")
    assert module.is_file() and not module.is_symlink()
    assert native_path.resolve() == active_project.resolve() / "project.comfystudio"
    assert not native_path.is_symlink() and native_path.is_file()
    before_sha = digest(native_path)
    source_sha = digest(original)
    document = json.loads(native_path.read_text(encoding="utf-8"))
    assert document["created"] and document["timelines"]
    assert document.get("zx7CrossProcessProof") is None
    document["zx7CrossProcessProof"] = _MARKER
    # Explicitly prove that a separate process committed NEW bytes, not a
    # duplicate same-content write or merely an in-memory revision counter.
    modified = json.dumps(document, ensure_ascii=False, indent=2)
    wanted_sha = _expected_digest(modified)
    assert wanted_sha != before_sha
    child_js = (
        "const m=require(process.argv[1]);"
        "m.saveNativeProjectCAS(process.argv[2],process.argv[3],process.argv[4])"
        ".then(r=>{process.stdout.write(r.sha256+'\\n')},"
        "e=>{process.stderr.write(e.code||e.message);process.exitCode=1})"
    )
    env = dict(os.environ)
    env.pop("NVIDIA_API_KEY", None)
    child = subprocess.run(
        ["node", "-e", child_js, str(module), str(native_path),
         modified, before_sha],
        capture_output=True, text=True, timeout=20, check=False, env=env,
    )
    assert child.returncode == 0, (
        "Independent native writer failed to commit: " + child.stderr[:240])
    assert child.stdout.strip() == wanted_sha
    assert digest(native_path) == wanted_sha
    assert digest(original) == source_sha

    # The original GUI process still has the pre-commit source head.
    # It must NOT turn its old loaded document into a successful new save.
    stale = await session.call_tool("save_project", {"previewOnly": False})
    assert stale.is_error, "Stale live Electron overwrote another process's save"
    assert digest(native_path) == wanted_sha
    active = await call(session, "get_project")
    assert active.get("mcp", {}).get("hasProject") is True
    assert active["project"]["path"] == str(active_project)
    timeline = await call(session, "get_timeline", {"includeClips": True})
    assert len(timeline["clips"]) == 3, "Rejected stale save lost live editorial state"
    assert digest(original) == source_sha

    # The ordinary GUI close path must also refuse to discard this project:
    # a failed save cannot be turned into silent data loss by navigation.
    from native_close_proof import click_native_project_selection
    pointer = await click_native_project_selection(display)
    still_live = await call(session, "get_project")
    assert still_live.get("mcp", {}).get("hasProject") is True
    assert still_live["project"]["path"] == str(active_project)
    assert digest(native_path) == wanted_sha
    assert digest(original) == source_sha
    print("ACTUAL_NATIVE_CROSS_PROCESS_STALE_GUI_REJECTION " + json.dumps({
        "physical_installed_Electron_editor_session_active": True,
        "independent_real_OS_process_committed_via_same_native_CAS": True,
        "external_commit_sha_verified": True,
        "stale_native_GUI_process_save_refused": True,
        "real_X11_close_pointer_issued": pointer[
            "real_X11_menu_and_project_selection_pointer_clicks"],
        "failed_stale_save_refused_close_and_kept_project_open": True,
        "committed_project_sha_unchanged_by_stale_GUI": True,
        "original_picture_sound_sha_unchanged": True,
        "no_automatic_merge_or_retry": True,
        "two_simultaneous_Editor_GUI_processes_tested": False,
    }, sort_keys=True), flush=True)
    return {"committed_sha": wanted_sha, "original_sha": source_sha,
            "marker": _MARKER}
