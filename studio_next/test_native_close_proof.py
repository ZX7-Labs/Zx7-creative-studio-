"""CI-only native GUI close proof safety contracts, without X11 side effects."""
import json
import os
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from engines.velorn.native_close_proof import (
    _button_geometry, click_native_project_selection,
)


class GeometrySourceTests(TestCase):
    def test_external_calls_rejected_before_inspection(self):
        for target in ("menu", "project-selection"):
            with patch.dict(os.environ, {"CI": "false"}), patch(
                "subprocess.check_output") as run:
                with self.assertRaises(PermissionError):
                    _button_geometry(target)
                run.assert_not_called()

    def test_forged_or_outside_geometry_refused(self):
        for target in ("menu", "project-selection"):
            for entry in (
                {"visible": False, "unique": True},
                {"visible": True, "unique": False},
                {"visible": True, "unique": True,
                 "rect": {"left": -5, "right": 25, "top": 4, "bottom": 14},
                 "window": {"width": 300, "height": 100, "pixelRatio": 1}},
                {"visible": True, "unique": True,
                 "rect": {"left": 100, "right": 140, "top": 20, "bottom": 45},
                 "window": {"width": 300, "height": 100, "pixelRatio": 2}},
            ):
                with (self.subTest(target=target, entry=entry),
                      patch.dict(os.environ, {"CI": "true"}),
                      patch("subprocess.check_output",
                            return_value=json.dumps(entry).encode())):
                    with self.assertRaises(AssertionError):
                        _button_geometry(target)

    def test_only_bounded_visible_geometry_produces_one_point(self):
        data = {
            "visible": True, "unique": True,
            "rect": {"left": 100, "right": 140, "top": 20, "bottom": 44},
            "window": {"width": 300, "height": 100, "pixelRatio": 1},
        }
        with (patch.dict(os.environ, {"CI": "true"}),
              patch("subprocess.check_output",
                    return_value=json.dumps(data).encode())):
            self.assertEqual(_button_geometry("project-selection"), (120, 32))


class SyntheticOnlyClickTests(IsolatedAsyncioTestCase):
    async def test_wrong_display_is_rejected_without_any_process(self):
        for display in ("", ":97", "127.0.0.1:98", "127.0.0.1:0"):
            with (self.subTest(display=display),
                  patch.dict(os.environ, {"CI": "true"}),
                  patch("engines.velorn.native_close_proof._editor_window") as window):
                with self.assertRaises(PermissionError):
                    await click_native_project_selection(display)
                window.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
