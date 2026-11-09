"""Build and import the real installed runtime outside the source checkout.

These are package/transport checks, not neural or artistic acceptance.
"""
from __future__ import annotations

import json
import asyncio
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parents[1]


class InstalledNativeRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="zx7-installed-runtime-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.scratch = Path(cls.temporary.name)
        wheels = cls.scratch / "wheels"
        wheels.mkdir()
        built = subprocess.run([
            sys.executable, "-c",
            "from setuptools.build_meta import build_wheel; "
            f"build_wheel({str(wheels)!r})",
        ], cwd=ROOT, capture_output=True, text=True, timeout=60)
        if built.returncode:
            raise AssertionError("Real wheel build failed:\n" + built.stderr[-4000:])
        cls.wheel = next(wheels.glob("*.whl"))
        cls.installed = cls.scratch / "installed"
        checked = subprocess.run([
            sys.executable, "-m", "pip", "install", "--no-deps", "--no-compile",
            "--target", str(cls.installed), str(cls.wheel),
        ], cwd=cls.scratch, capture_output=True, text=True, timeout=30)
        if checked.returncode:
            raise AssertionError("Real wheel install failed:\n" + checked.stderr[-4000:])

    def test_wheel_contains_the_native_session_runtime_and_licenses(self):
        required = {
            "studio_next/native_editor_session.py",
            *{"studio_next/editor_runtime/" + name for name in (
                "mcp.mjs", "launcher.mjs", "client.mjs", "editor.example.json", "source-lock.json",
                "LICENSE", "NOTICE")},
        }
        with zipfile.ZipFile(self.wheel) as source:
            self.assertTrue(required.issubset(source.namelist()),
                "Installed native route is missing runtime files: " +
                str(sorted(required - set(source.namelist()))))
            entrypoints = next(p for p in source.namelist() if p.endswith("/entry_points.txt"))
            self.assertIn("zx7-studio = studio_next.studio_cli:main",
                          source.read(entrypoints).decode())
            from email.parser import Parser
            metadata_path = next(p for p in source.namelist() if p.endswith("/METADATA"))
            metadata = Parser().parsestr(source.read(metadata_path).decode())
            self.assertEqual(metadata["License-Expression"], "MIT AND GPL-3.0-only")
            license_files = metadata.get_all("License-File")
            self.assertEqual(set(license_files), {"LICENSE", "studio_next/editor_runtime/LICENSE",
                                                  "studio_next/editor_runtime/NOTICE"})
            base = metadata_path.removesuffix("METADATA") + "licenses/"
            for license_file in license_files:
                self.assertEqual(source.read(base + license_file), (ROOT / license_file).read_bytes())
            self.assertEqual(source.read("studio_next/editor_runtime/editor.example.json"),
                             (ROOT / "engines/velorn/editor.example.json").read_bytes())

    def test_installed_owner_console_runs_outside_checkout(self):
        env = {**os.environ, "PYTHONPATH": str(self.installed)}
        executable = self.installed / "bin/zx7-studio"
        workspace = self.scratch / "owner-workspace"
        commands = [
            (["--help"], 0),
            (["init", str(workspace), "--source", str(self.scratch),
              "--model-id", "not-a-running-model"], 0),
            (["status", str(workspace)], 0),
            (["doctor", str(workspace)], 2),
        ]
        for args, expected in commands:
            with self.subTest(args=args):
                checked = subprocess.run([str(executable), *args], cwd=self.scratch,
                    env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(checked.returncode, expected, checked.stderr)
                if args[0] == "doctor":
                    report = json.loads(checked.stdout)
                    self.assertFalse(report["ready"])
                    self.assertFalse(next(c["ready"] for c in report["checks"]
                                          if c["name"] == "editor_source_pin"))

    def test_installed_native_runtime_loads_without_the_checkout(self):
        installed = self.installed
        code = """
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
from studio_next import native_editor_session as native
base = pathlib.Path(sys.argv[1]).resolve()
assert pathlib.Path(native.__file__).resolve().is_relative_to(base)
assert native.editor_runtime_path('mcp.mjs').is_file()
args = native.build_parser().parse_args([
    '--source', '/authorized/source', '--config', '/private/host.json',
    '--state', '/private/state', '--brief-file', '/private/brief.txt',
    '--receipt', '/private/receipt.jsonl', '--model-id', 'replaceable-local-model'])
assert args.provider == 'local'
assert args.allow_cloud_image_upload is False
print(json.dumps({'runtime': str(native.editor_runtime_path('mcp.mjs'))}))
"""
        checked = subprocess.run([sys.executable, "-I", "-c", code, str(installed)],
                                 cwd=self.scratch, capture_output=True, text=True, timeout=15)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        mcp_path = Path(json.loads(checked.stdout)["runtime"])
        self.assertTrue(mcp_path.is_relative_to(installed))
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is required to verify the installed native runtime")
        inspect = """
const base = new URL(process.argv[1]);
const launcher = await import(new URL('./launcher.mjs', base));
const client = await import(new URL('./client.mjs', base));
if (typeof launcher.launchVelorn !== 'function' || typeof client.VelornClient !== 'function')
  throw Error('Installed native JavaScript modules are not executable');
console.log(launcher.UPSTREAM_COMMIT);
"""
        checked = subprocess.run([node, "--input-type=module", "-e", inspect,
                                  mcp_path.as_uri()], cwd=self.scratch,
                                 capture_output=True, text=True, timeout=15)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(checked.stdout.strip(), "b3c02adbd5c0779feb8abf34978299e9502cc0e7")

    def test_installed_wheel_bridge_runs_official_mcp_outside_checkout(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        calls = []

        class NativeFixture(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append(request)
                result = ({"tools": [{"name": "get_project", "inputSchema": {
                    "type": "object", "properties": {}, "additionalProperties": False}}]}
                    if request["method"] == "tools/list" else
                    {"content": [{"type": "text", "text": "installed-native-read"}]})
                body = json.dumps({"jsonrpc": "2.0", "id": request["id"],
                                   "result": result}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), NativeFixture)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        config = self.scratch / "installed-host.json"
        config.write_text(json.dumps({
            "endpoint": f"http://127.0.0.1:{server.server_port}/mcp",
            **{n + "_root": str(self.scratch / n)
               for n in ("projects", "staging", "outputs")},
            "allowed_tools": {"get_project": "read"}}))

        async def inspect():
            env = {**os.environ, "PYTHONPATH": str(self.installed)}
            env.pop("NVIDIA_API_KEY", None)
            params = StdioServerParameters(command=sys.executable,
                args=["-m", "studio_next.body_editor_mcp", "--config", str(config)],
                cwd=self.scratch, env=env)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=10) as session:
                    await session.initialize()
                    self.assertEqual([t.name for t in (await session.list_tools()).tools],
                                     ["get_project"])
                    result = await session.call_tool("get_project", {})
                    self.assertFalse(result.is_error)
                    self.assertEqual(result.content[0].text, "installed-native-read")
        try:
            asyncio.run(inspect())
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
        self.assertEqual(sum(r["method"] == "tools/call" for r in calls), 1)

    def test_legacy_runpy_exports_are_the_canonical_session_callables(self):
        from studio_next import native_editor_session as canonical
        legacy = runpy.run_path(str(ROOT / "engines/velorn/native-model-client.py"),
                                run_name="native_legacy_compatibility_test")
        for name in ("main", "run_native_session", "build_parser", "native_decision_model",
                     "native_editor_child_environment", "pinned_electron_marker_previews",
                     "trial_machine_contracts"):
            with self.subTest(name=name):
                self.assertIs(legacy[name], getattr(canonical, name))

    def test_native_session_grants_match_enabled_access_and_optional_sensors(self):
        from studio_next.native_editor_session import native_session_grants
        configured = {"get_project": "read", "update_text_clip": "write"}
        for access in (["read"], ["write"], ["read", "write"]):
            for verify in (False, True):
                with self.subTest(access=access, verify=verify):
                    grants = native_session_grants({"allowed_tools": configured,
                        "allowed_access": access, "verify_native_exports": verify}, self.scratch)
                    expected = {k: v for k, v in configured.items() if v in access}
                    self.assertEqual({k: v for k, v in grants.items() if not k.startswith("zx7_")},
                                     expected)
                    self.assertEqual("zx7_verify_native_export" in grants,
                                     verify and "read" in access)
                    self.assertNotIn("zx7_inspect_native_content", grants)
        self.assertEqual(native_session_grants({"allowed_tools": configured}, self.scratch),
                         {"get_project": "read"})
        self.assertEqual(configured, {"get_project": "read", "update_text_clip": "write"})

    def test_private_cwd_bridge_resolves_the_same_package_without_provider_secrets(self):
        from studio_next import native_editor_session as native
        from unittest.mock import patch
        config = self.scratch / "source-host.json"
        config.write_text(json.dumps({"allowed_tools": {"get_project": "read"}}))
        brief = self.scratch / "owner-brief.txt"
        brief.write_text("Create an original editable work.")
        args = native.build_parser().parse_args([
            "--source", str(self.scratch), "--config", str(config),
            "--state", str(self.scratch), "--brief-file", str(brief),
            "--receipt", str(self.scratch / "fresh.jsonl"), "--model-id", "local-model"])

        class ReachedNativeLaunch(RuntimeError):
            pass

        with patch.object(native, "stdio_client", side_effect=ReachedNativeLaunch) as launch, \
                patch.dict(os.environ, {"NVIDIA_API_KEY": "synthetic-test-secret"}):
            with self.assertRaises(ReachedNativeLaunch):
                asyncio.run(native.run_native_session(args))
        params = launch.call_args.args[0]
        self.assertEqual(Path(params.cwd), self.scratch.resolve())
        self.assertNotIn("NVIDIA_API_KEY", params.env)
        self.assertEqual(params.env["PYTHONPATH"].split(os.pathsep)[0], str(ROOT))
        self.assertEqual(params.args[0], str(native.editor_runtime_path("mcp.mjs")))


if __name__ == "__main__":
    unittest.main()
