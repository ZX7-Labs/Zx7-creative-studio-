"""Source identity security checks for the opt-in native saved-timestamp overlay.

This is a small offline negative test. The independent acceptance of actual
source saves, repeated disk/renderer/MCP timestamp equality, physical A/V,
GUI/AI coediting and post-SIGKILL project reopen is in installed mcp-e2e.py.
"""
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from studio_next.native_editor_source_pin import (
    PINNED_VELORN_EDITORIAL_REVISION,
    PINNED_VELORN_SAVE_REVISION,
    TRUSTED_VELORN_REVISIONS,
    _source_matches_pinned_native_save,
    _source_matches_pinned_native_editorial,
)


class NativeSaveSourceIdentityTests(unittest.TestCase):
    def test_reviewed_save_revision_is_distinct_and_registered(self):
        self.assertEqual(len(PINNED_VELORN_SAVE_REVISION), 40)
        self.assertNotEqual(
            PINNED_VELORN_SAVE_REVISION, PINNED_VELORN_EDITORIAL_REVISION)
        self.assertIn(PINNED_VELORN_SAVE_REVISION, TRUSTED_VELORN_REVISIONS)
        self.assertIn(PINNED_VELORN_EDITORIAL_REVISION, TRUSTED_VELORN_REVISIONS)

    def test_unverified_checkout_never_advertises_save_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(_source_matches_pinned_native_save(Path(tmp)))
            self.assertFalse(_source_matches_pinned_native_editorial(Path(tmp)))

    def test_only_exact_reviewed_child_has_corrected_save_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            for revision, accepted in (
                (PINNED_VELORN_SAVE_REVISION, True),
                (PINNED_VELORN_EDITORIAL_REVISION, False),
                ("0" * 40, False),
            ):
                with (
                    self.subTest(revision=revision),
                    patch(
                        "studio_next.native_editor_source_pin."
                        "_source_matches_pinned_native_editorial",
                        return_value=True
                    ),
                    patch(
                        "studio_next.native_editor_source_pin.subprocess.run",
                        return_value=SimpleNamespace(
                            returncode=0, stdout=revision + "\n")
                    ),
                ):
                    self.assertIs(
                        _source_matches_pinned_native_save(path), accepted)

    def test_editorial_source_failure_cannot_promote_save_privileges(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "studio_next.native_editor_source_pin."
            "_source_matches_pinned_native_editorial", return_value=False
        ), patch(
            "studio_next.native_editor_source_pin.subprocess.run"
        ) as command:
            self.assertFalse(_source_matches_pinned_native_save(Path(tmp)))
            command.assert_not_called()

    def test_git_timeout_fails_closed_without_untrusted_fallback(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "studio_next.native_editor_source_pin."
            "_source_matches_pinned_native_editorial", return_value=True
        ), patch(
            "studio_next.native_editor_source_pin.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["git"], timeout=5)
        ):
            self.assertFalse(_source_matches_pinned_native_save(Path(tmp)))

    def test_missing_path_and_non_path_refuse_source_identity(self):
        self.assertFalse(_source_matches_pinned_native_save(None))
        self.assertFalse(_source_matches_pinned_native_save("not-a-real-source"))


if __name__ == "__main__":
    unittest.main()
