"""Offline safety tests for real-X11 native editor pointer acceptance harness.

These tests do NOT claim a GUI event occurred. Real installed Electron/Xvfb,
native writer CAS, saved document and decoded A/V are tested in mcp-e2e.py.
"""
import asyncio
import os
import unittest
from unittest.mock import patch

from engines.velorn.native_pointer_proof import (
    _editor_window, _geometry, _validated_pointer_point,
    drag_native_clip_pointer,
)


def position():
    return {
        "visible": True,
        "clip": {"left": 350, "right": 390, "top": 260,
                 "bottom": 312, "width": 40, "height": 52},
        "viewport": {"left": 240, "right": 1200, "top": 190, "bottom": 560,
                     "width": 960, "height": 370},
        "content": {"left": 240, "right": 1200, "top": 212, "bottom": 550,
                    "width": 960, "height": 338},
        "window": {"width": 1280, "height": 720,
                   "pixelRatio": 1, "x": 0, "y": 0},
    }


class TestNativePointerBounds(unittest.TestCase):
    def test_valid_native_clip_center_inside_scrollable_track(self):
        self.assertEqual(_validated_pointer_point(position()), (370, 286))

    def test_insufficient_clip_width_refuses_trim_handle_guess(self):
        data = position()
        data["clip"].update(width=14, right=364)
        with self.assertRaisesRegex(AssertionError, "too small"):
            _validated_pointer_point(data)

    def test_invalid_display_density_cannot_guess_x11_coordinates(self):
        data = position()
        data["window"]["pixelRatio"] = 2
        with self.assertRaisesRegex(AssertionError, "too small"):
            _validated_pointer_point(data)

    def test_offscreen_and_nonvisible_clip_refused(self):
        data = position()
        data["clip"].update(top=720, bottom=772)
        with self.assertRaisesRegex(AssertionError, "miss"):
            _validated_pointer_point(data)

    def test_absent_viewport_refused(self):
        data = position()
        data["viewport"] = None
        with self.assertRaisesRegex(AssertionError, "not available"):
            _validated_pointer_point(data)

    def test_no_ci_refuses_gui_and_cdp_even_if_display_is_provided(self):
        with patch.dict(os.environ, {"CI": "false"}):
            with self.assertRaisesRegex(ValueError, "isolated CI"):
                _editor_window("127.0.0.1:97")
            with self.assertRaisesRegex(ValueError, "CI"):
                _geometry("native-clip")

    def test_invalid_clip_id_refused_without_subprocess(self):
        with patch.dict(os.environ, {"CI": "true"}):
            with self.assertRaises(ValueError):
                _geometry("")
            with self.assertRaises(ValueError):
                _geometry("x" * 241)


class TestNativePointerX11Event(unittest.IsolatedAsyncioTestCase):
    async def test_one_true_press_four_motion_events_and_release(self):
        with (
            patch("engines.velorn.native_pointer_proof._editor_window",
                  return_value=("1234", {"CI": "true"})),
            patch("engines.velorn.native_pointer_proof._geometry",
                  return_value=position()),
            patch("engines.velorn.native_pointer_proof._x11") as x11,
            patch("engines.velorn.native_pointer_proof.asyncio.sleep",
                  new_callable=unittest.mock.AsyncMock),
        ):
            receipt = await drag_native_clip_pointer("127.0.0.1:97", "id")
            actions = [call.args[1] for call in x11.call_args_list]
        self.assertEqual(
            actions,
            ["mousemove", "mousedown", "mousemove", "mousemove",
             "mousemove", "mousemove", "mouseup"])
        self.assertTrue(receipt["actual_X11_button_motion_release"])
        self.assertFalse(receipt["direct_JS_timeline_mutation"])

    async def test_mouse_button_is_released_after_motion_error(self):
        def fail_at_delta(env, *args):
            if args[0] == "mousemove" and args[-2] > 370:
                raise OSError("synthetic X11 transport loss")
            calls.append(args[0])
        calls = []
        with (
            patch("engines.velorn.native_pointer_proof._editor_window",
                  return_value=("1234", {"CI": "true"})),
            patch("engines.velorn.native_pointer_proof._geometry",
                  return_value=position()),
            patch("engines.velorn.native_pointer_proof._x11",
                  side_effect=fail_at_delta),
        ):
            with self.assertRaisesRegex(OSError, "transport loss"):
                await drag_native_clip_pointer("127.0.0.1:97", "id")
        self.assertEqual(calls[-1], "mouseup")


if __name__ == "__main__":
    unittest.main()
