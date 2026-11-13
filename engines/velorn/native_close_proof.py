# SPDX-License-Identifier: GPL-3.0-only
"""Actual CI-only X11 click on source-native Project Selection close action.

The read-only geometry process never dispatches DOM/store events. The trusted
installed editor receives actual X11 pointer input; the caller independently
checks whether the project was preserved or closed by native source.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess

if __package__:
    from .native_pointer_proof import _editor_window, _x11
else:
    from native_pointer_proof import _editor_window, _x11


_SCRIPT = Path(__file__).with_name("native-close-geometry.mjs")


def _button_geometry(target: str) -> tuple[int, int]:
    if os.environ.get("CI") != "true" or target not in ("menu", "project-selection"):
        raise PermissionError("GUI project-close proof is limited to isolated CI")
    raw = subprocess.check_output(
        ["node", str(_SCRIPT), "19393", target],
        env={**os.environ, "ZX7_POINTER_E2E_CDP_PORT": "19393"},
        stderr=subprocess.PIPE, timeout=25)
    data = json.loads(raw)
    rect, window = data.get("rect"), data.get("window")
    if (data.get("visible") is not True or data.get("unique") is not True or
            not isinstance(rect, dict) or not isinstance(window, dict) or
            window.get("pixelRatio") != 1):
        raise AssertionError("Source-native project menu action is not visibly unique")
    x = round((rect["left"] + rect["right"]) / 2)
    y = round((rect["top"] + rect["bottom"]) / 2)
    if not (10 < x < window["width"] - 10 and
            10 < y < window["height"] - 10):
        raise AssertionError("Project menu click point is outside editor window")
    return x, y


async def click_native_project_selection(display: str) -> dict:
    if os.environ.get("CI") != "true" or display != "127.0.0.1:97":
        raise PermissionError("Project selection proof requires exact synthetic Xvfb")
    window, env = _editor_window(display)
    for target in ("menu", "project-selection"):
        x, y = _button_geometry(target)
        _x11(env, "mousemove", "--sync", "--window", window, x, y)
        _x11(env, "click", 1)
        await asyncio.sleep(.30)
    return {
        "real_X11_menu_and_project_selection_pointer_clicks": True,
        "native_source_project_close_action": True,
        "direct_JS_project_store_mutation": False,
        "only_read_only_CDP_coordinates": True,
    }
