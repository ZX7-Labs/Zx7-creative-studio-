# SPDX-License-Identifier: GPL-3.0-only
"""Real Electron X11 pointer gesture for synthetic native-editor CI only.

Uses the source-native clip DOM solely to locate *screen geometry*. All editing
goes through actual X11 mouse-down/motion/up, then independently read native
MCP state. Never use CDP to change the editor, invoke its action methods or
fake React events. Never run against a private owner project.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess


INSPECTION_PORT = 19393
_SCRIPT = Path(__file__).with_name("native-pointer-geometry.mjs")


def _x11(env, *args):
    subprocess.run(["xdotool", *map(str, args)], env=env,
                   check=True, timeout=8, capture_output=True)


def _editor_window(display: str):
    if (os.environ.get("CI") != "true" or
            not isinstance(display, str) or
            not display.startswith("127.0.0.1:") or
            not shutil.which("xdotool")):
        raise ValueError("Pointer integration requires isolated CI Xvfb and xdotool")
    env = {**os.environ, "DISPLAY": display}
    windows = subprocess.check_output(
        ["xdotool", "search", "--onlyvisible", "--name", "."],
        env=env, stderr=subprocess.PIPE, timeout=8).decode().split()
    matches = []
    for window in set(windows):
        name = subprocess.check_output(
            ["xdotool", "getwindowname", window], env=env,
            stderr=subprocess.PIPE, timeout=8).decode().strip()
        if "Velorn" in name:
            matches.append(window)
    if len(matches) != 1:
        raise AssertionError("Expected exactly one visible native Velorn window")
    _x11(env, "windowfocus", "--sync", matches[0])
    return matches[0], env


def _geometry(clip_id: str):
    if (os.environ.get("CI") != "true" or
            not isinstance(clip_id, str) or not 0 < len(clip_id) <= 240):
        raise ValueError("Read-only renderer probe needs CI and a native clip ID")
    output = subprocess.check_output(
        ["node", str(_SCRIPT), str(INSPECTION_PORT), clip_id],
        env=os.environ, stderr=subprocess.PIPE, timeout=23)
    geometry = json.loads(output)
    if (not isinstance(geometry, dict) or
            type(geometry.get("visible")) is not bool):
        raise ValueError("Native renderer geometry missing or malformed")
    return geometry


def _validated_pointer_point(position: dict):
    clip, viewport, content = (
        position.get("clip"), position.get("viewport"), position.get("content"))
    window = position.get("window")
    if not all(isinstance(rect, dict)
               for rect in (clip, viewport, content, window)):
        raise AssertionError("Native timeline geometry not available")
    if (window.get("pixelRatio") != 1 or
            not clip.get("width", 0) >= 24 or
            not clip.get("height", 0) >= 12):
        raise AssertionError("Native clip body is too small for safe X11 pointer drag")
    x = round(clip["left"] + clip["width"] / 2)
    y = round(clip["top"] + clip["height"] / 2)
    if not (12 < x < window["width"] - 55 and
            content["top"] + 9 < y < content["bottom"] - 9 and
            viewport["left"] + 10 < x < viewport["right"] - 50):
        raise AssertionError("Real pointer would miss the native editable clip body")
    return x, y


async def drag_native_clip_pointer(display: str, clip_id: str):
    """Return input evidence only; native timeline write MUST be checked outside.

    No auto-retry of an ambiguous mouse gesture, no arbitrary CDP expressions,
    no model-selected DOM selectors and no direct editor action RPC.
    """
    window, env = _editor_window(display)
    position = _geometry(clip_id)
    for _ in range(12):
        if position["visible"]:
            break
        clip, viewport, track = (
            position.get("clip"), position.get("viewport"), position.get("content"))
        if not all(isinstance(v, dict) for v in (clip, viewport, track)):
            raise AssertionError("Native clip not mounted in the visible timeline")
        if clip["width"] < 24 or clip["height"] < 12:
            raise AssertionError("Native clip too narrow for pointer drag")
        if clip["top"] < track["top"] + 9:
            wheel = 4
        elif clip["bottom"] > track["bottom"] - 9:
            wheel = 5
        else:
            raise AssertionError("Native clip not reachable by vertical X11 scrolling")
        _x11(env, "mousemove", "--sync", "--window", window,
             round(viewport["left"] + 70), round(track["top"] + 18))
        _x11(env, "click", wheel)
        await asyncio.sleep(.15)
        position = _geometry(clip_id)
    if not position["visible"]:
        raise AssertionError("Failed to scroll actual native clip into view")
    x, y = _validated_pointer_point(position)
    _x11(env, "mousemove", "--sync", "--window", window, x, y)
    _x11(env, "mousedown", 1)
    try:
        for dx in (5, 11, 17, 25):
            _x11(env, "mousemove", "--sync", "--window", window,
                 x + dx, y)
            await asyncio.sleep(.11)
    finally:
        _x11(env, "mouseup", 1)
    await asyncio.sleep(.3)
    return {
        "actual_X11_button_motion_release": True,
        "read_only_renderer_geometry": True,
        "actual_native_clip_DOM_target": True,
        "test_pointer_delta_x_px": 25,
        "direct_JS_timeline_mutation": False,
    }
