"""No-loss native save source contract and refusal matrix (offline only).

Physical Chromium/X11 error and original media tests run separately in CI.
"""
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from studio_next.native_editor_source_pin import (
    PINNED_VELORN_SAVE_REVISION, PINNED_VELORN_SAVE_ORDER_REVISION,
    TRUSTED_VELORN_REVISIONS,
    _source_matches_pinned_native_save_order,
)


class SaveOrderingSourceTests(unittest.TestCase):
    def test_exact_child_distinct_and_trusted(self):
        self.assertNotEqual(PINNED_VELORN_SAVE_ORDER_REVISION, PINNED_VELORN_SAVE_REVISION)
        self.assertEqual(len(PINNED_VELORN_SAVE_ORDER_REVISION), 40)
        self.assertIn(PINNED_VELORN_SAVE_REVISION, TRUSTED_VELORN_REVISIONS)
        self.assertIn(PINNED_VELORN_SAVE_ORDER_REVISION, TRUSTED_VELORN_REVISIONS)

    def test_old_save_child_does_not_gain_no_loss_claim(self):
        with TemporaryDirectory() as temp:
            source = Path(temp)
            for ref, ok in (
                (PINNED_VELORN_SAVE_ORDER_REVISION, True),
                (PINNED_VELORN_SAVE_REVISION, False),
                ("f" * 40, False),
            ):
                with (self.subTest(ref=ref),
                      patch("studio_next.native_editor_source_pin."
                            "_source_matches_pinned_native_save", return_value=True),
                      patch("studio_next.native_editor_source_pin.subprocess.run",
                            return_value=SimpleNamespace(returncode=0, stdout=ref + "\n"))):
                    self.assertIs(_source_matches_pinned_native_save_order(source), ok)

    def test_fail_closed_on_unknown_or_untrusted_source(self):
        with TemporaryDirectory() as temp:
            source = Path(temp)
            self.assertFalse(_source_matches_pinned_native_save_order(source))
            self.assertFalse(_source_matches_pinned_native_save_order(None))
            self.assertFalse(_source_matches_pinned_native_save_order(str(source)))
            with (patch("studio_next.native_editor_source_pin."
                        "_source_matches_pinned_native_save", return_value=False),
                  patch("studio_next.native_editor_source_pin.subprocess.run") as git):
                self.assertFalse(_source_matches_pinned_native_save_order(source))
                git.assert_not_called()

    def test_timeout_fail_closed(self):
        with TemporaryDirectory() as temp:
            with (patch("studio_next.native_editor_source_pin."
                        "_source_matches_pinned_native_save", return_value=True),
                  patch("studio_next.native_editor_source_pin.subprocess.run",
                        side_effect=subprocess.TimeoutExpired(["git"], timeout=5))):
                self.assertFalse(_source_matches_pinned_native_save_order(Path(temp)))


if __name__ == "__main__":
    unittest.main()
