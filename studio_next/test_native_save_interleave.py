"""Synthetic refusal matrix for exact CI interrupted project-save process death."""
from pathlib import Path
import os
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from studio_next.native_editor_source_pin import (
    PINNED_VELORN_SAVE_INTERLEAVE_REVISION,
    _source_matches_pinned_native_save_interleave,
)


class SourceAdmissionTests(unittest.TestCase):
    def test_test_child_never_mints_production_native_save_claim(self):
        with patch.dict(os.environ, {"CI": "false"}):
            self.assertFalse(_source_matches_pinned_native_save_interleave(Path("/tmp/no-source")))

    def test_missing_child_or_nonexistent_source_fails_closed(self):
        self.assertFalse(_source_matches_pinned_native_save_interleave(None))
        with TemporaryDirectory() as folder:
            self.assertFalse(_source_matches_pinned_native_save_interleave(Path(folder)))
        if PINNED_VELORN_SAVE_INTERLEAVE_REVISION:
            self.assertEqual(len(PINNED_VELORN_SAVE_INTERLEAVE_REVISION), 40)


class KillRefusalTests(unittest.TestCase):
    def test_non_ci_cannot_check_or_kill_arbitrary_process(self):
        from engines.velorn.native_save_interleave_proof import (
            kill_exact_editor_during_native_write, validate_native_interruption_gate)
        root = Path("/tmp/not-a-verified-zx7-fixture")
        with patch.dict(os.environ, {"CI": "false"}):
            with self.assertRaises(PermissionError):
                validate_native_interruption_gate(
                    gate=root, project=root, state_root=root, source=root,
                    display="127.0.0.1:97", pid=200)
            with self.assertRaises(PermissionError):
                kill_exact_editor_during_native_write(
                    editor_source=root, state_root=root,
                    display="127.0.0.1:97", gate=root, project=root)

    def test_wrong_display_and_untrusted_fixture_refused_before_pid_lookup(self):
        from engines.velorn.native_save_interleave_proof import (
            kill_exact_editor_during_native_write, validate_native_interruption_gate)
        with TemporaryDirectory(prefix="zx7-untrusted-") as tmp:
            root = Path(tmp)
            with patch.dict(os.environ, {"CI": "true"}):
                with self.assertRaises(AssertionError):
                    validate_native_interruption_gate(
                        gate=root, project=root, state_root=root, source=root,
                        display="127.0.0.1:97", pid=200)
                with self.assertRaises(PermissionError):
                    kill_exact_editor_during_native_write(
                        editor_source=root, state_root=root, display=":0",
                        gate=root, project=root)


if __name__ == "__main__":
    unittest.main()
