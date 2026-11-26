"""Prove official-release 403 fallback keeps exact ffmpeg-static SHA256 admission.

This is a network-isolated test of the actual checked-in Bash fetch function.
It never downloads a binary, installs an editor, or authorizes new endpoints.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

_SCRIPT = Path(__file__).resolve().parents[1] / "engines/velorn/install-ci-dependencies.sh"
_CONTENT = b"ZX7-exact-upstream-digest-test-only\\n"
_SHA = hashlib.sha256(_CONTENT).hexdigest()
_FAKE_CURL = """#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
target = args[args.index("--output") + 1]
url = args[-1]
with open(os.environ["ZX7_TEST_CURL_LOG"], "a") as out:
    out.write(url + "\\n")
mode = os.environ["ZX7_TEST_CURL_MODE"]
if mode == "primary" and "/releases/assets/" in url:
    Path(target).write_bytes(b"ZX7-exact-upstream-digest-test-only\\n")
elif url == "https://cdn.npmmirror.com/binaries/ffmpeg-static/b6.1.1/synthetic-linux-x64.gz":
    Path(target).write_bytes(
        b"tampered-for-test-only" if mode == "corrupt"
        else b"ZX7-exact-upstream-digest-test-only\\n")
else:
    sys.exit(22)
"""


class PinnedCiMediaDownloadFallbackTests(unittest.TestCase):
    def run_fetch(self, mode):
        # Invoke the exact source Bash function, not a reimplemented test
        # substitute. Keep all network I/O replaced by an isolated fake curl,
        # but use the REAL sha256sum binary to reject mismatches.
        source = _SCRIPT.read_text(encoding="utf-8")
        function = source.split("\nfetch() {\n", 1)[1].split("\n}\n\n# IDs", 1)[0]
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            curl = bin_dir / "curl"
            curl.write_text(_FAKE_CURL, encoding="utf-8")
            curl.chmod(0o755)
            log = root / "calls.txt"
            assets = root / "source-locked-assets"
            assets.mkdir()
            bash = (
                "set -euo pipefail\n"
                f"assets={str(assets)!r}\n"
                "fetch() {\n" + function + "\n}\n"
                f"fetch 999 synthetic-linux-x64.gz {_SHA}\n"
            )
            env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                       ZX7_TEST_CURL_MODE=mode, ZX7_TEST_CURL_LOG=str(log))
            result = subprocess.run(["bash", "-c", bash], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=20)
            urls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
            data = (assets / "synthetic-linux-x64.gz")
            return result, urls, data.read_bytes() if data.exists() else None

    def test_official_assets_403_use_only_fixed_mirror_and_exact_upstream_hash(self):
        result, urls, data = self.run_fetch("mirror")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(urls), 3)
        self.assertEqual(urls[0],
                         "https://api.github.com/repos/eugeneware/ffmpeg-static"
                         "/releases/assets/999?download=1")
        self.assertEqual(urls[1],
                         "https://github.com/eugeneware/ffmpeg-static"
                         "/releases/download/b6.1.1/synthetic-linux-x64.gz")
        self.assertEqual(urls[2],
                         "https://cdn.npmmirror.com/binaries/ffmpeg-static"
                         "/b6.1.1/synthetic-linux-x64.gz")
        self.assertEqual(hashlib.sha256(data).hexdigest(), _SHA)

    def test_mirror_byte_substitution_fails_closed_and_does_not_retry(self):
        result, urls, data = self.run_fetch("corrupt")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(urls), 3)
        self.assertNotEqual(hashlib.sha256(data).hexdigest(), _SHA)

    def test_original_verified_primary_never_calls_any_alternate(self):
        result, urls, data = self.run_fetch("primary")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(urls), 1)
        self.assertEqual(hashlib.sha256(data).hexdigest(), _SHA)
