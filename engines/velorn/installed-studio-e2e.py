"""Exercise the installed console and real editor with a scripted HTTP fixture."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Thread
import time

from jsonschema import Draft202012Validator


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(path):
    return subprocess.check_output([
        "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(path),
        "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ], stderr=subprocess.PIPE, timeout=20)


def exercise(source, xvfb):
    executable = shutil.which("zx7-studio")
    assert executable, "Install the BODY package before this proof"
    with tempfile.TemporaryDirectory(prefix="zx7-installed-editor-") as temporary:
        root = Path(temporary)
        studio = root / "studio"
        original = root / "original.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            "testsrc2=s=320x180:r=24:d=2", "-c:v", "libx264", "-pix_fmt",
            "yuv420p", str(original)], check=True, timeout=20)
        original_sha = digest(original)
        selected_steps = []
        errors = []
        readiness = []
        observed_frame_requests = []

        class Fixture(BaseHTTPRequestHandler):
            def send_json(self, value, status=200):
                raw = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                assert self.path == "/v1/models", self.path
                self.send_json({"data": [{"id": "scripted-installation-fixture"}]})

            def do_POST(self):
                try:
                    assert self.path == "/v1/chat/completions", self.path
                    request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    assert request["model"] == "scripted-installation-fixture"
                    content = request["messages"][1]["content"]
                    if isinstance(content, list):
                        assert any(item["type"] == "image_url" for item in content)
                        observed_frame_requests.append(True)
                        content = content[0]["text"]
                    context = json.loads(content)
                    owner = json.loads(context["creative_brief"].split("\n\n", 1)[1].split("\n", 1)[1])
                    output = Path(owner["outputs_root"]) / "fixture.mp4"
                    tool, args = selected_steps[0]
                    if tool == "check_export_readiness" and context["last_native_result_texts"]:
                        latest = json.loads(context["last_native_result_texts"][0])
                        if "blockers" in latest and "deliveryTarget" in latest:
                            readiness.append({"ready": latest["ready"], "blockers": latest["blockers"]})
                            if latest["ready"] is True:
                                selected_steps.pop(0)
                                tool, args = selected_steps[0]
                            else:
                                time.sleep(0.2)
                    if tool is None:
                        action = {"action": "finish", "arguments": {"summary": "Scripted transport fixture completed"}}
                    elif tool in context["selectable_native_tools"]:
                        inputs = args(owner, output) if callable(args) else args
                        if tool == "add_asset_to_timeline":
                            tracks = context["native_placement_tracks"]["tracks"]
                            picture = next(track for track in tracks
                                           if track["type"] == "video" and not track.get("locked"))
                            inputs = {**inputs, "trackId": picture["id"]}
                        action = {"action": "invoke", "arguments": {"tool": tool,
                            "inputs": inputs}}
                    else:
                        action = {"action": "search", "arguments": {"query": tool, "limit": 1}}
                    action["reason"] = "Explicit scripted installation test"
                    Draft202012Validator(request["response_format"]["json_schema"]["schema"]).validate(action)
                    if action["action"] != "search" and tool != "check_export_readiness":
                        selected_steps.pop(0)
                    self.send_json({"model": request["model"],
                        "choices": [{"message": {"content": json.dumps(action)}}]})
                except Exception as exc:
                    errors.append(exc)
                    self.send_json({"error": "Scripted installation fixture failed"}, 400)

            def log_message(self, *_):
                pass

        def verify(output):
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                try:
                    if output.is_file() and len(decode(output)) == 48 * 320 * 180 * 3:
                        return {"path": str(output), "expected": {"width": 320,
                            "height": 180, "duration_seconds": 2, "require_audio": False}}
                except subprocess.CalledProcessError:
                    pass  # The real native worker may still be writing.
                time.sleep(0.2)
            raise AssertionError("The actual editor did not produce the expected decodable export")

        def studio_command(*args):
            env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
            result = subprocess.run([executable, *map(str, args)], cwd=root, env=env,
                capture_output=True, text=True, timeout=150)
            if errors:
                raise errors[0]
            if result.returncode:
                print("Native readiness observations:", readiness)
                for journal in studio.glob("sessions/*/native-journal.jsonl"):
                    print(journal.read_text())
                for log in studio.glob("state/*/session-*/launcher.log"):
                    print(log.read_text()[-10000:])
                raise AssertionError((result.returncode, result.stdout, result.stderr))
            return json.loads(result.stdout)

        export_settings = {"target": "h264_project", "width": 320, "height": 180,
            "fps": 24, "range": "custom", "startSeconds": 0, "endSeconds": 2,
            "includeAudio": False}
        def delivery(filename, *, observe=False):
            steps = [
                ("save_project", {"previewOnly": False}),
                ("check_export_readiness", export_settings),
                ("export_timeline", lambda _, output: {**export_settings,
                    "outputPath": str(output.with_name(filename)), "previewOnly": False}),
                ("zx7_verify_native_export", lambda _, output: verify(output.with_name(filename))),
            ]
            if observe:
                steps.append(("zx7_observe_verified_export_frame", lambda _, output: {
                    "path": str(output.with_name(filename)), "at_seconds": 0.5}))
            return steps
        with ThreadingHTTPServer(("127.0.0.1", 0), Fixture) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                studio_command("init", studio, "--base-url",
                               f"http://127.0.0.1:{server.server_port}")
                settings = json.loads((studio / "studio.json").read_text(encoding="utf-8"))
                assert Path(settings["editor_source"]) == source
                assert settings["model_id"] == "scripted-installation-fixture"
                assert studio_command("doctor", studio)["ready"]
                runner = ("run", studio, "--xvfb-binary", xvfb, "--display", "127.0.0.1:95",
                          "--model-timeout", "90")
                selected_steps[:] = [
                    ("create_project", {"name": "Installed project proof", "width": 320,
                        "height": 180, "fps": 24, "previewOnly": False}),
                    ("import_asset_from_path", lambda owner, _: {
                        "path": owner["authorized_sources"][0]["path"], "previewOnly": False}),
                    ("add_asset_to_timeline", lambda owner, _: {
                        "assetName": Path(owner["authorized_sources"][0]["path"]).name,
                        "startSeconds": 0, "includeAudio": False, "previewOnly": False}),
                    *delivery("fixture.mp4"), (None, None),
                ]
                first = studio_command(*runner, "--brief", "एक नया project बनाओ।",
                                       "--asset", original, "--rights", "Generated installation fixture")
                assert not selected_steps and first["state"] == "completed"
                saved, = (studio / "projects").glob("*/project.comfystudio")
                initial = json.loads(saved.read_text())
                initial_sha = digest(saved)
                copied = saved.parent / initial["assets"][0]["path"]
                assert digest(copied) == original_sha == digest(original)
                first_frames = decode(Path(first["outputs_directory"]) / "fixture.mp4")
                selected_steps[:] = [
                    *delivery("before.mp4", observe=True),
                    ("add_track", {"type": "video", "name": "Revision titles", "previewOnly": False}),
                    ("add_text_clip", {"text": "INSTALLED REVISION", "startSeconds": 0,
                        "durationSeconds": 2, "style": {"fontSize": 28}, "previewOnly": False}),
                    *delivery("fixture.mp4", observe=True), (None, None),
                ]
                revised = studio_command(*runner, "--brief", "उसी project में title जोड़ो।",
                    "--project", saved.parent, "--reviewed-revision", "--max-turns", "48")
                assert not selected_steps and revised["state"] == "completed"
                assert revised["result"]["owner_project_setup"]["active_project_identity_verified"]
                assert list((studio / "projects").glob("*/project.comfystudio")) == [saved]
                assert digest(saved) != initial_sha and digest(copied) == digest(original) == original_sha
                assert "INSTALLED REVISION" in saved.read_text()
                revised_outputs = Path(revised["outputs_directory"])
                before_file, after_file = (revised_outputs / name for name in ("before.mp4", "fixture.mp4"))
                pair = revised["result"]["reviewed_native_render_pair"]
                assert [item["export_sha256"] for item in pair] == [digest(before_file), digest(after_file)]
                assert len(observed_frame_requests) >= 2
                assert decode(before_file) == first_frames
                final_frames = decode(after_file)
                assert len(first_frames) == len(final_frames) and first_frames != final_frames
                assert {s["session_id"] for s in studio_command("status", studio)["sessions"]} == {
                    first["session_id"], revised["session_id"]}
                print("Installed console created, exported, reopened and revised a real native project.")
            finally:
                server.shutdown()
                thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--xvfb-binary", type=Path, required=True)
    options = parser.parse_args()
    exercise(options.source.resolve(strict=True), options.xvfb_binary.resolve(strict=True))
