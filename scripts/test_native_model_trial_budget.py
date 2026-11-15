"""Admission-only local model budget checks; never load weights or start an editor."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from scripts.run_native_model_trial import RecordedModel, build_trial_parser, retain_safe_native_editor_logs
from scripts.run_nvidia_native_trial import synthetic_trial_delivery_requirement


class NativeModelTrialBudgetTests(unittest.TestCase):
    @staticmethod
    def arguments(*extra):
        return ["--source", "/tmp/pinned-velorn", "--runtime", "/tmp/local-runtime",
                "--artifacts", "/tmp/retained-trial", *extra]

    def test_local_trial_brief_names_the_full_physical_delivery_contract(self):
        requirement = synthetic_trial_delivery_requirement(max_seconds=8)
        for term in ("H.264 MP4", "640x360", "24 fps", "at most 8 seconds"):
            self.assertIn(term, requirement)

    def test_default_remains_bounded_for_non_extended_local_runs(self):
        args = build_trial_parser().parse_args(self.arguments())
        self.assertEqual(args.model_timeout, 300)
        self.assertEqual(args.trial_timeout, 2400)

    def test_extended_cpu_evaluation_requires_explicit_allowed_values(self):
        args = build_trial_parser().parse_args(self.arguments(
            "--model-timeout", "480", "--trial-timeout", "13200"))
        self.assertEqual(args.model_timeout, 480)
        self.assertEqual(args.trial_timeout, 13200)
        for bad in ("0", "-1", "13201", "14400", "999999", "3600"):
            with self.subTest(invalid_trial_budget=bad), self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    build_trial_parser().parse_args(self.arguments("--trial-timeout", bad))
        for bad in ("0", "1200", "481", "99999"):
            with self.subTest(invalid_turn_budget=bad), self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    build_trial_parser().parse_args(self.arguments("--model-timeout", bad))

    def test_opt_in_ci_workflow_has_an_outer_timeout_and_artifact_preservation(self):
        # Regression guard for the workflow's relationship to the parser, not
        # a substitute for a live model trial or proof of quality.
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/zx7-live-native-model.yml").read_text()
        job = workflow.split("  actual-local-model-and-native-editor:", 1)[1]
        self.assertIn("    timeout-minutes: 240", job)
        self.assertIn("--model-timeout 480 --trial-timeout 13200", job)
        self.assertIn("github.event_name != 'pull_request'", job)
        self.assertIn("needs.pr-local-model-opt-in.outputs.requested == 'true'", job)
        self.assertIn("if: always()", job)
        self.assertIn("name: zx7-live-native-model-", job)

    def test_real_native_diagnostics_never_copy_chromium_storage(self):
        # Reproduces archived real Qwen 4B run #42650208249, whose previous
        # recursive "*.log" copy included IndexedDB, Local Storage, Session
        # Storage and Chromium proto_db LevelDB files in a public ZIP.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "runtime" / "editor-state"
            session = private / "session-Vhz0Xu"
            velorn = session / "velorn"
            velorn.mkdir(parents=True)
            (session / "launcher.log").write_text("native launch check")
            (velorn / "app.log").write_text("native application diagnostics")
            (velorn / "export-worker.log").write_text("physical export worker")
            secret_like = (
                velorn / "IndexedDB" /
                "http_127.0.0.1_5173.indexeddb.leveldb" / "000003.log")
            secret_like.parent.mkdir(parents=True)
            secret_like.write_text("private-session-cookie-like-content")
            for directory in ("Local Storage/leveldb", "Session Storage",
                              "shared_proto_db/metadata"):
                blocked = velorn / directory / "000003.log"
                blocked.parent.mkdir(parents=True, exist_ok=True)
                blocked.write_text("synthetic-private-browser-state")
            evidence = root / "artifact"
            evidence.mkdir()
            self.assertEqual(retain_safe_native_editor_logs(private, evidence), 3)
            copied = sorted(p.relative_to(evidence).as_posix()
                            for p in evidence.rglob("*") if p.is_file())
            self.assertEqual(copied, [
                "engine-logs/session-Vhz0Xu/launcher.log",
                "engine-logs/session-Vhz0Xu/velorn/app.log",
                "engine-logs/session-Vhz0Xu/velorn/export-worker.log",
            ])
            self.assertFalse(any("Storage" in path or "IndexedDB" in path
                                 for path in copied))
            self.assertNotIn("private-session-cookie-like-content",
                             "\n".join(p.read_text() for p in evidence.rglob("*.log")))

    def test_forensic_log_retention_is_bounded_and_never_follows_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            session = root / "runtime" / "editor-state" / "session-Test42"
            (session / "velorn").mkdir(parents=True)
            # Keep the tail only; no unbounded RAM/disk replication.
            tail = b"good-diagnostic-tail"
            (session / "launcher.log").write_bytes(
                b"X" * (1024 * 1024 + 777) + tail)
            outside = root / "private.log"
            outside.write_text("not model/public evidence")
            (session / "velorn" / "app.log").symlink_to(outside)
            (session / "velorn" / "export-worker.log").mkdir()
            artifacts = root / "evidence"
            artifacts.mkdir()
            self.assertEqual(
                retain_safe_native_editor_logs(session.parent, artifacts), 1)
            copied = artifacts / "engine-logs" / session.name / "launcher.log"
            self.assertEqual(copied.stat().st_size, 1024 * 1024)
            self.assertEqual(copied.read_bytes()[-len(tail):], tail)
            self.assertFalse(
                (artifacts / "engine-logs" / session.name /
                 "velorn" / "app.log").exists())
            # The symlink target itself remains fully intact and private.
            self.assertEqual(outside.read_text(), "not model/public evidence")
            self.assertEqual(retain_safe_native_editor_logs(
                root / "missing", artifacts), 0)
            alias = root / "linked-editor-state"
            alias.symlink_to(session.parent, target_is_directory=True)
            self.assertEqual(retain_safe_native_editor_logs(alias, artifacts), 0)



class RecordedNativeModelAudioHandoffTests(unittest.TestCase):
    def test_audio_capable_local_model_receives_original_bytes_without_public_artifact_copy(self):
        # A transport test, not proof of learned audio perception or artistic quality.
        raw = b"synthetic-private-WAV-payload-" * 300
        audio = [("audio/wav", raw)]
        context = {"audio_evidence": {"wav_sha256": hashlib.sha256(raw).hexdigest()}}
        class AudioCapableModel:
            settings = SimpleNamespace(model_id="synthetic-audio-fixture")
            last_call_usage = {"prompt_tokens": 4}
            def decide_with_audio(self, supplied_context, supplied_audio):
                self.received = (supplied_context, supplied_audio)
                return {"action": "finish", "arguments": {"summary": "Fixture transport only"}}

        with tempfile.TemporaryDirectory() as temp:
            model = AudioCapableModel()
            recorder = RecordedModel(model, Path(temp))
            self.assertEqual(recorder.decide_with_audio(context, audio)["action"], "finish")
            self.assertEqual(model.received, (context, audio))
            record = json.loads((Path(temp) / "inference-transcript.jsonl").read_text())
            self.assertEqual(record["audio_sha256"],
                             [hashlib.sha256(raw).hexdigest()])
            self.assertEqual(record["audio_mime"], ["audio/wav"])
            self.assertEqual(record["server_reported_token_usage"], {"prompt_tokens": 4})
            self.assertNotIn(raw.decode("ascii"),
                             (Path(temp) / "inference-transcript.jsonl").read_text())
            self.assertFalse((Path(temp) / "observations").exists())
            self.assertEqual(recorder.turn, 1)

    def test_audio_is_not_silently_replaced_with_text_for_incompatible_model(self):
        class TextOnlyModel:
            settings = SimpleNamespace(model_id="synthetic-text-only")
            last_call_usage = None
            def decide(self, context):
                raise AssertionError("Original audio cannot fall back to text")

        with tempfile.TemporaryDirectory() as temp:
            recorder = RecordedModel(TextOnlyModel(), Path(temp))
            with self.assertRaisesRegex(RuntimeError, "audio-capable"):
                recorder.decide_with_audio(
                    {"audio_evidence": {"wav_sha256": "a" * 64}},
                    [("audio/wav", b"synthetic-audio")])
            record = json.loads((Path(temp) / "inference-transcript.jsonl").read_text())
            self.assertEqual(record["error_type"], "RuntimeError")
            self.assertEqual(recorder.turn, 1)

    def test_mixed_images_and_audio_cannot_pass_the_trial_recording_boundary(self):
        class Model:
            settings = SimpleNamespace(model_id="synthetic")
            last_call_usage = None
        with tempfile.TemporaryDirectory() as temp:
            recorder = RecordedModel(Model(), Path(temp))
            with self.assertRaisesRegex(ValueError, "Separate"):
                recorder.infer({"task": "both"}, images=[("image/png", b"x")],
                               audio=[("audio/wav", b"y")])
            self.assertFalse((Path(temp) / "inference-transcript.jsonl").exists())




if __name__ == "__main__":
    unittest.main()
