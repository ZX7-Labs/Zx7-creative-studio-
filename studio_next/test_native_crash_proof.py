"""Offline negative tests; physical crash/reopen is in installed X11 CI."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engines.velorn.native_crash_proof import (
    _trusted_pid_from_log, _verify_process_identity,
    kill_exact_editor_after_saved_revision,
)


class CrashProofSecurityTests(unittest.TestCase):
    def test_exact_pid_marker_not_arbitrary_ps_match(self):
        self.assertEqual(
            _trusted_pid_from_log("launcher started\nZX7_CI_NATIVE_ELECTRON_PID=321\n"),
            321,
        )
        for text in ("", "PID=321\n",
                     "ZX7_CI_NATIVE_ELECTRON_PID=1\n",
                     "ZX7_CI_NATIVE_ELECTRON_PID=321\n"
                     "ZX7_CI_NATIVE_ELECTRON_PID=322\n",
                     "ZX7_CI_NATIVE_ELECTRON_PID=abc\n"):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                _trusted_pid_from_log(text)

    def test_source_binary_and_uid_must_match_exactly(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp).resolve()
            expected = str(source / "node_modules/electron/dist/electron")
            _verify_process_identity(
                cmdline=(expected + "\x00--no-sandbox\x00" + str(source) + "\x00").encode(),
                process_uid=123, expected_uid=123, editor_source=source)
            with self.assertRaisesRegex(AssertionError, "different OS user"):
                _verify_process_identity(
                    cmdline=(expected + "\x00" + str(source) + "\x00").encode(),
                    process_uid=124, expected_uid=123, editor_source=source)
            with self.assertRaisesRegex(AssertionError, "not the exact"):
                _verify_process_identity(
                    cmdline=("/usr/bin/python3\x00" + str(source) + "\x00").encode(),
                    process_uid=123, expected_uid=123, editor_source=source)
            with self.assertRaisesRegex(AssertionError, "not the exact"):
                _verify_process_identity(
                    cmdline=(expected + "\x00/tmp/fake-editor\x00").encode(),
                    process_uid=123, expected_uid=123, editor_source=source)

    def test_non_ci_context_denied_before_any_pid_lookup_or_kill(self):
        with patch.dict(os.environ, {"CI": "false"}), patch("os.kill") as kill:
            with self.assertRaises(PermissionError):
                kill_exact_editor_after_saved_revision(
                    editor_source=Path("/not-owned"),
                    state_root=Path("/tmp"), display="127.0.0.1:97")
            kill.assert_not_called()

    def test_external_or_wrong_display_denied(self):
        with patch.dict(os.environ, {"CI": "true"}), patch("os.kill") as kill:
            for display in ("127.0.0.1:0", ":97", "127.0.0.1:98", ""):
                with self.subTest(display=display), self.assertRaises(PermissionError):
                    kill_exact_editor_after_saved_revision(
                        editor_source=Path("/not-owned"),
                        state_root=Path("/tmp"), display=display)
            kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
