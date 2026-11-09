"""Fail-closed CI Electron 504 recovery; no network or native build in tests."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "engines/velorn/rebuild-ci-native-modules.sh"
FAKE_NPM = """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

log = Path(os.environ["ZX7_FAKE_NPM_LOG"])
calls = json.loads(log.read_text()) if log.exists() else []
calls.append({"args": sys.argv[1:], "mirror": os.environ.get("ELECTRON_MIRROR")})
log.write_text(json.dumps(calls))
scenario = os.environ["ZX7_FAKE_NPM_SCENARIO"]
if len(calls) == 1 and scenario != "already_ok":
    if scenario == "other_failure":
        print("npm error path /work/node_modules/electron", file=sys.stderr)
        print("npm error checksum mismatch", file=sys.stderr)
    elif scenario == "other_504":
        print("npm error path /work/node_modules/unrelated", file=sys.stderr)
        print("npm error HTTPError: Response code 504", file=sys.stderr)
    else:
        print("npm error path /work/node_modules/electron", file=sys.stderr)
        print("npm error HTTPError: Response code 504 (Gateway Time-out)", file=sys.stderr)
    sys.exit(29)
if len(calls) == 2 and scenario == "mirror_failure":
    print("npm error mirror offline", file=sys.stderr)
    sys.exit(19)
print("npm rebuild succeeded")
"""


class NativeElectronDownloadRecoveryTests(unittest.TestCase):
    def run_scenario(self, scenario):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            npm = bin_dir / "npm"
            npm.write_text(FAKE_NPM)
            npm.chmod(0o755)
            log = root / "calls.json"
            env = {
                **os.environ,
                "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                "ZX7_FAKE_NPM_LOG": str(log),
                "ZX7_FAKE_NPM_SCENARIO": scenario,
            }
            # A caller-supplied mirror must never accidentally mask the
            # original-source-first behavior tested here.
            env.pop("ELECTRON_MIRROR", None)
            result = subprocess.run(
                ["bash", str(SCRIPT)], env=env, cwd=root,
                capture_output=True, text=True, timeout=20)
            calls = json.loads(log.read_text())
            return result, calls

    def test_success_uses_original_install_hooks_exactly_once(self):
        result, calls = self.run_scenario("already_ok")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], {
            "args": ["rebuild", "--no-audit", "--no-fund"], "mirror": None})

    def test_electron_504_retries_one_mirror_then_all_postinstalls(self):
        result, calls = self.run_scenario("electron_504")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call["args"] for call in calls], [
            ["rebuild", "--no-audit", "--no-fund"],
            ["rebuild", "electron", "--no-audit", "--no-fund"],
            ["rebuild", "--no-audit", "--no-fund"]])
        self.assertEqual(calls[1]["mirror"], "https://npmmirror.com/mirrors/electron/")
        self.assertIsNone(calls[2]["mirror"])
        self.assertIn("HTTP 504", result.stdout)

    def test_integrity_or_other_build_failure_is_not_retried(self):
        for scenario in ("other_failure", "other_504"):
            with self.subTest(scenario=scenario):
                result, calls = self.run_scenario(scenario)
                self.assertEqual(result.returncode, 29)
                self.assertEqual(len(calls), 1)
                self.assertNotIn("alternate mirror", result.stdout)

    def test_second_network_failure_is_not_looped(self):
        result, calls = self.run_scenario("mirror_failure")
        self.assertEqual(result.returncode, 19)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["mirror"], "https://npmmirror.com/mirrors/electron/")


if __name__ == "__main__":
    unittest.main()
