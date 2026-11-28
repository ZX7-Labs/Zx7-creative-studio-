"""Offline proof of the real owner delivery option through the installed editor.

Only the decision provider is a scripted fixture. The actual native source,
MCP bridge, host session, saved bytes, export worker and decoder are mandatory.
This does not test or assert neural creative competence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time
from unittest.mock import patch


async def prove_owner_delivery(*, options, connected, call, wait, fixture, config,
                               project, video_id, staging, outputs):
    from studio_next import native_editor_session as runner
    from studio_next.native_creative_audit import read_native_journal
    from studio_next.native_render_evidence import (
        DESTINATION_FIELD, SAVED_RENDER_FIELD, SAVED_RENDER_OPTIONS_FIELD,
        SAVED_RENDER_MEDIA_FIELD, destination_digest)

    profile = {"width": 320, "height": 180, "fps": 24,
               "max_duration": 2, "video_codec": "h264"}
    host_config = json.loads(config.read_text(encoding="utf-8"))
    host_config["required_export_delivery"] = profile
    # The prior physical test session is closed. The real production launcher
    # will read this independently scoped owner configuration on each reopen.
    config.write_text(json.dumps(host_config), encoding="utf-8")
    source_hashes = {name: hashlib.sha256((staging/name).read_bytes()).hexdigest()
                     for name in ("source.mp4", "tone.wav")}
    brief = fixture / "owner-delivery-proof.txt"
    brief.write_text("Technical fixture: exercise explicit owner delivery choice, not neural art.",
                     encoding="utf-8")

    async def prepare_timeline(name, width, height):
        async with connected() as session:
            await call(session, "open_project", {"projectPath": str(project), "previewOnly": False})
            await wait(session, lambda x: (x.get("project") or {}).get("path") == str(project))
            await call(session, "create_timeline", {"name": name, "width": width,
                "height": height, "fps": 24, "durationSeconds": 60,
                "switchToTimeline": True, "previewOnly": False})
            await wait(session, lambda x: (x.get("currentTimeline") or {}).get("name") == name
                       and (x.get("currentTimeline") or {}).get("clipCount") == 0)
            await call(session, "add_asset_to_timeline", {"assetId": video_id,
                "startSeconds": 0, "includeAudio": False, "previewOnly": False})
            await wait(session, lambda x: (x.get("currentTimeline") or {}).get("clipCount") == 1)
            await call(session, "add_asset_to_timeline", {"assetName": "tone.wav",
                "startSeconds": 0, "previewOnly": False})
            await wait(session, lambda x: (x.get("currentTimeline") or {}).get("clipCount") == 2)
            await call(session, "save_project", {"previewOnly": False})

    class FixtureDecisionProvider:
        requires_native_function_contracts = True

        def __init__(self, state, *, matching):
            self.state = state
            self.matching = matching
            self.turn = 0
            self.output = None
            self.full_duration = None

        def decide(self, context):
            self.turn += 1
            def invoke(tool, inputs):
                assert tool in context["selectable_native_tools"], (tool, context["selectable_native_tools"])
                return {"action": "invoke", "arguments": {"tool": tool, "inputs": inputs},
                        "reason": "Explicitly selected technical fixture operation, not neural creativity"}
            if self.turn == 1:
                assert "host_owner_delivery_candidate" not in context
                return invoke("save_project", {"previewOnly": False})
            if not self.matching:
                assert "host_owner_delivery_candidate" not in context
                feedback = context["host_owner_delivery_feedback"]
                assert feedback["status"] == "profile_mismatch", feedback
                assert feedback["observed_delivery"]["width"] == 640, feedback
                assert "explicit_owner_window_readiness" not in feedback
                return {"action": "search", "arguments": {"query": "export"},
                        "reason": "Observe mismatch without dispatch"}
            if self.turn == 2:
                offer = context["host_owner_delivery_candidate"]
                assert offer["native_readiness_verified"] is True
                assert offer["owner_delivery_profile"] == profile
                assert offer["excludes_later_timeline_time"] is True
                self.full_duration = offer["full_timeline_observed_duration_seconds"]
                assert self.full_duration > profile["max_duration"]
                inputs = offer["arguments"]
                assert {k: inputs[k] for k in ("range", "startSeconds", "endSeconds")} == {
                    "range": "custom", "startSeconds": 0, "endSeconds": 2}
                assert offer["observed_delivery"]["rangeStart"] == 0
                assert offer["observed_delivery"]["rangeEnd"] == 2
                self.output = Path(inputs["outputPath"])
                assert self.output.parent == outputs and not self.output.exists()
                return invoke(offer["tool"], inputs)
            assert self.turn == 3 and self.output is not None
            # Wait for the actual asynchronous worker in this test provider;
            # no native write is retried or inserted by the host.
            deadline = time.monotonic() + 100
            while time.monotonic() < deadline:
                logs = self.state.glob("session-*/velorn/export-worker.log")
                if any("[ExportWorker] Export complete" in line and json.dumps(str(self.output)) in line
                       for log in logs for line in log.read_text(encoding="utf-8").splitlines()):
                    break
                time.sleep(.2)
            else:
                raise AssertionError("Actual owner-window export never completed")
            return invoke("zx7_verify_native_export", {"path": str(self.output), "expected": {
                "width": 320, "height": 180, "duration_seconds": 2, "require_audio": True}})

    before = set(outputs.iterdir())
    positive = None
    for matching in (False, True):
        name = "owner-window-match" if matching else "owner-window-mismatch"
        await prepare_timeline(name, 320 if matching else 640, 180 if matching else 360)
        state = fixture / name
        state.mkdir(mode=0o700)
        receipt = state / "journal.jsonl"
        brain = FixtureDecisionProvider(state, matching=matching)
        argv = ["--source", str(options.source), "--config", str(config), "--project", str(project),
                "--state", str(state), "--brief-file", str(brief), "--receipt", str(receipt),
                "--provider", "local", "--model-id", "offline-technical-fixture", "--indexed-catalog",
                "--structured-actions", "--record-av-project-snapshots", "--evaluation-evidence",
                "reviewed-av-revision", "--max-turns", "3" if matching else "2"]
        for field in ("xvfb_binary", "xvfb_lib_dir", "display"):
            if getattr(options, field):
                argv += ["--" + field.replace("_", "-"), str(getattr(options, field))]
        if options.software_gpu:
            argv.append("--software-gpu")
        with patch.object(runner, "native_decision_model", return_value=brain):
            report = await runner.run_native_session(runner.build_parser().parse_args(argv))
        events = read_native_journal(receipt)
        reads = [event for event in events if event["kind"] == "host_owner_delivery_readiness_observation"]
        assert [event["native_readiness_status"] for event in reads] == (
            ["profile_mismatch", "matched"] if matching else ["profile_mismatch"]), reads
        assert report["status"] == "turn_budget_exhausted" and not report["evaluation_evidence_satisfied"]
        assert report["model_selected_write_receipts"] == (2 if matching else 1), report
        assert report["independently_verified_export_receipts"] == (1 if matching else 0), report
        assert not report["neural_autonomy_independently_verified"] and not report["artistic_quality_independently_approved"]
        if not matching:
            assert set(outputs.iterdir()) == before
            continue
        positive = brain.output
        assert set(outputs.iterdir()) == before | {positive}
        bound = [event for event in events if event.get("kind") == "native_tool_result"
                 and event.get("tool") == "export_timeline"]
        assert len(bound) == 1 and bound[0].get(DESTINATION_FIELD) == destination_digest(str(positive))
        assert all(isinstance(bound[0].get(field), str) and len(bound[0][field]) == 64
                   for field in (SAVED_RENDER_FIELD, SAVED_RENDER_OPTIONS_FIELD, SAVED_RENDER_MEDIA_FIELD)), bound
        assert (state / "av-project-snapshots" / (bound[0][DESTINATION_FIELD] + ".comfystudio")).is_file()
        assert brain.full_duration > 2
    assert positive is not None
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-count_frames",
        "-show_streams", "-of", "json", str(positive)], timeout=30))["streams"]
    video, = (stream for stream in probe if stream["codec_type"] == "video")
    audio, = (stream for stream in probe if stream["codec_type"] == "audio")
    assert (video["codec_name"], video["width"], video["height"], video["r_frame_rate"],
            int(video["nb_read_frames"])) == ("h264", 320, 180, "24/1", 48), video
    assert audio["codec_name"] == "aac"
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(positive),
                    "-f", "null", "-"], check=True, timeout=30)
    pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(positive), "-vn",
        "-f", "s16le", "-ac", "1", "-ar", "8000", "-"], timeout=30)
    assert any(pcm) and len(pcm) >= 31900
    assert all(hashlib.sha256((staging/name).read_bytes()).hexdigest() == expected
               for name, expected in source_hashes.items())
    print("ACTUAL_OWNER_DELIVERY_WINDOW " + json.dumps({"real_pinned_native_source": True,
        "wrong_dimensions_offer_refused": True, "full_timeline_exceeded_owner_limit": True,
        "explicit_window_model_fixture_selected": True, "no_hidden_render_or_trim": True,
        "native_saved_source_and_options_bound": True, "independent_decoded_frames": 48,
        "actual_nonzero_audio": True, "original_source_hashes_unchanged": True,
        "neural_or_artistic_acceptance": False}, sort_keys=True), flush=True)
