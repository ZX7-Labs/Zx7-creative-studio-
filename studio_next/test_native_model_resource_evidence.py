"""Linux per-process memory evidence: honest scope and failure modes."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.run_native_model_trial import (
    parse_linux_proc_peak_rss, read_live_linux_model_peak_rss,
    preserve_native_trial_failure_audit,
)


class NativeModelMemoryProofTests(unittest.TestCase):
    def test_valid_linux_vm_hwm_reports_bytes_not_kibibytes(self):
        self.assertEqual(parse_linux_proc_peak_rss(
            "Name:\tllama-server\nVmRSS:\t  400 kB\nVmHWM:\t 123456 kB\n"),
            123456 * 1024)
        # Peak stays larger than current RSS after memory is released.
        self.assertEqual(parse_linux_proc_peak_rss(
            "VmHWM:\t  8192 kB\nVmRSS:\t 1024 kB\n"), 8192 * 1024)

    def test_absent_inconsistent_or_untrusted_procfs_is_not_measurement(self):
        bad = [
            "", "VmRSS:\t10 kB", "VmHWM:\t0 kB", "VmHWM: -1 kB",
            "VmHWM: 1 MB", "VmHWM: NaN kB", "VmHWM: 42",
            "VmHWM: 4 kB\nVmHWM: 5 kB",
            "VmHWM: 9999999999999 kB", "notVmHWM: 1234 kB",
        ]
        for raw in bad:
            with self.subTest(raw=raw):
                self.assertIsNone(parse_linux_proc_peak_rss(raw))
        self.assertIsNone(parse_linux_proc_peak_rss(None))

    def test_live_process_read_does_not_infer_memory_from_pid_errors(self):
        for pid in (-1, 0, True, "not-a-pid"):
            with self.subTest(pid=pid):
                self.assertIsNone(read_live_linux_model_peak_rss(pid))
        if sys.platform == "linux" and os.name == "posix":
            with patch("scripts.run_native_model_trial.Path.read_text",
                       side_effect=FileNotFoundError("model already exited")):
                self.assertIsNone(read_live_linux_model_peak_rss(os.getpid()))
            with patch("scripts.run_native_model_trial.Path.read_text",
                       return_value="VmHWM:\t128 kB\n"):
                self.assertEqual(read_live_linux_model_peak_rss(os.getpid()),
                                 128 * 1024)
            # Physical read of the active current process exercises procfs.
            self.assertGreater(read_live_linux_model_peak_rss(os.getpid()), 0)


class PartialNativeTrialFailureEvidenceTests(unittest.TestCase):
    def test_real_timeout_prefix_is_never_reported_as_complete_movie(self):
        with tempfile.TemporaryDirectory() as root:
            work = Path(root)
            (work / "native-journal.jsonl").write_text(
                '{"kind":"model_decision_failed"}' + chr(10))
            mock_audit = {
                "schema": 1, "journal_chain_structurally_valid": True,
                "event_count": 13, "recorded_native_write_result_count": 2,
                "model_reported_end_state": "model_decision_failed",
                "video_editing_capability_complete": False,
            }
            with patch("scripts.run_native_model_trial.read_native_journal",
                       return_value=[{"kind": "model_decision_failed"}]), patch(
                       "scripts.run_native_model_trial.audit_native_journal",
                       return_value=mock_audit) as validator:
                report = preserve_native_trial_failure_audit(
                    work, host_tool_access={"get_project": "read"},
                    expected_required_evidence=("native_write_acknowledged",),
                    host_content_revision_tools=("add_asset_to_timeline",))
            validator.assert_called_once()
            self.assertTrue(report["partial_journal_structurally_verified"])
            self.assertFalse(report["technical_trial_completed"])
            self.assertFalse(report["artistic_quality_approved"])
            self.assertTrue(report["incomplete_trial_no_native_write_replay"])
            persisted = json.loads(
                (work / "journal-audit-partial.json").read_text())
            self.assertEqual(persisted, report)
            self.assertEqual(persisted["recorded_native_write_result_count"], 2)

    def test_invalid_partial_ledger_is_still_recorded_as_unverified(self):
        with tempfile.TemporaryDirectory() as root:
            work = Path(root)
            (work / "native-journal.jsonl").write_text("invalid")
            with patch("scripts.run_native_model_trial.read_native_journal",
                       side_effect=ValueError("bad hash chain")):
                report = preserve_native_trial_failure_audit(
                    work, host_tool_access={}, expected_required_evidence=(),
                    host_content_revision_tools=())
            self.assertFalse(report["partial_journal_structurally_verified"])
            self.assertEqual(report["partial_journal_audit_error_type"],
                             "ValueError")
            self.assertFalse(report["technical_trial_completed"])
            self.assertEqual(json.loads(
                (work / "journal-audit-partial.json").read_text()), report)

    def test_auditor_false_verdict_cannot_be_relabelled_valid(self):
        with tempfile.TemporaryDirectory() as root:
            work = Path(root)
            (work / "native-journal.jsonl").write_text("present")
            with patch("scripts.run_native_model_trial.read_native_journal",
                       return_value=[{"kind": "model_decision_failed"}]), patch(
                       "scripts.run_native_model_trial.audit_native_journal",
                       return_value={"journal_chain_structurally_valid": False}):
                report = preserve_native_trial_failure_audit(
                    work, host_tool_access={}, expected_required_evidence=(),
                    host_content_revision_tools=())
            self.assertFalse(report["partial_journal_structurally_verified"])
            self.assertFalse(report["technical_trial_completed"])
            self.assertEqual(report["partial_journal_audit_error_type"],
                             "ValueError")

    def test_no_native_journal_is_not_represented_as_verified(self):
        with tempfile.TemporaryDirectory() as root:
            work = Path(root)
            self.assertEqual(preserve_native_trial_failure_audit(
                work, host_tool_access={}, expected_required_evidence=(),
                host_content_revision_tools=()), {
                    "partial_journal_present": False,
                    "partial_journal_structurally_verified": False})
            self.assertFalse((work / "journal-audit-partial.json").exists())


if __name__ == "__main__":
    unittest.main()
