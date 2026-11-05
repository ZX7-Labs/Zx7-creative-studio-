"""Adversarial technical trace tests, not a neural-creativity benchmark."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from studio_next.native_creative_audit import (
    NativeJournalError, audit_native_journal, read_native_journal,
)


A = "a" * 64
B = "b" * 64
C = "c" * 64
HOST = {
    "export_timeline": "write",
    "update_text_clip": "write",
    "get_timeline": "read",
    "zx7_verify_native_export": "read",
    "zx7_observe_verified_export_frame": "read",
    "zx7_observe_verified_export_audio": "read",
}


def trace():
    events = []
    def add(kind, **kw):
        events.append({"sequence": len(events), "kind": kind, **kw})
    def call(tool, n):
        add("native_tool_submitted", tool=tool, turn=n,
            inputs_sha256=hashlib.sha256(f"tool-{n}".encode()).hexdigest(),
            model_reason=f"Independent model requested tool at turn {n}",
            uncertain_write_do_not_replay=True)
    def result(tool, n, **kw):
        fields = dict(tool=tool, turn=n, text_sha256=[C],
                      image_sha256=[], audio_sha256=None,
                      independently_verified_export_sha256=None, observed_export_sha256=None,
                      human_or_artistic_quality_approved=False)
        if HOST.get(tool) == "write":
            # Fixture-only app ACK shapes. These are intentionally fabricated
            # technical protocol examples, never real neural or host proof.
            fields["host_application_write_acknowledged"] = True
            fields["host_application_write_receipt_sha256"] = C
        fields.update(kw)
        add("native_tool_result", **fields)
    # Build a real-shaped transcript with *fixture bytes only*. It cannot
    # certify actual model intelligence or physical media quality.
    add("session_started", brief_sha256=A,
        model_id_reported="scripted-fixture-NOT-NEURAL",
        neural_autonomy_or_artistic_quality_verified=False)
    call("get_timeline", 0); result("get_timeline", 0)
    call("update_text_clip", 1); result("update_text_clip", 1)
    call("export_timeline", 2); result("export_timeline", 2)
    call("zx7_verify_native_export", 3)
    result("zx7_verify_native_export", 3,
           independently_verified_export_sha256=A)
    call("zx7_observe_verified_export_frame", 4)
    result("zx7_observe_verified_export_frame", 4,
           image_sha256=[C], observed_export_sha256=A)
    call("update_text_clip", 5); result("update_text_clip", 5)
    call("export_timeline", 6); result("export_timeline", 6)
    call("zx7_verify_native_export", 7)
    result("zx7_verify_native_export", 7,
           independently_verified_export_sha256=B)
    call("zx7_observe_verified_export_frame", 8)
    result("zx7_observe_verified_export_frame", 8,
           image_sha256=[C], observed_export_sha256=B)
    add("model_finished", turn=9, summary="I revised it",
        creative_quality_independently_approved=False)
    return events


class NativeCreativeAuditTests(unittest.TestCase):
    def test_forged_first_event_cannot_hide_missing_session_identity(self):
        # A positional journal parser must never skip an unrecognized first
        # event, even if all later steps satisfy their own local contracts.
        for forged in (
            {"kind": "model_action_rejected", "tool": "update_text_clip",
             "inputs_sha256": A, "validation_keyword": "type",
             "no_native_dispatch": True},
            {"kind": "discovered", "tools": ["update_text_clip"]},
            {"kind": "native_tool_result", "tool": "update_text_clip",
             "host_application_write_acknowledged": True},
            {"kind": "unrecognized_first_event"},
        ):
            with self.subTest(forged=forged):
                events = trace()
                events[0] = {"sequence": 0, **forged}
                with self.assertRaisesRegex(NativeJournalError, "session_started"):
                    audit_native_journal(events,host_tool_access=HOST)

    def test_host_timeline_picture_guard_is_read_evidence_not_a_native_edit(self):
        before = audit_native_journal(trace(), host_tool_access=HOST)
        variants = [
            {"kind": "host_native_timeline_picture_observation", "turn": 0,
             "picture_state": "absent", "host_attested_read_only": True,
             "no_native_edit_dispatched": True},
            {"kind": "host_native_timeline_picture_observation", "turn": 0,
             "picture_state": "present", "host_attested_read_only": True,
             "no_native_edit_dispatched": True,
             "observed_text_sha256": A},
            {"kind": "host_native_timeline_read_unknown", "turn": 0,
             "error_type": "TimeoutError", "no_native_edit_dispatched": True},
        ]
        for observed in variants:
            with self.subTest(observation=observed):
                events = trace()
                events.insert(3, {"sequence": 3, **observed})
                for idx, event in enumerate(events):
                    event["sequence"] = idx
                audited = audit_native_journal(events, host_tool_access=HOST)
                self.assertTrue(audited["journal_chain_structurally_valid"])
                self.assertEqual(audited["recorded_native_write_result_count"],
                                 before["recorded_native_write_result_count"])
                self.assertEqual(audited["export_digests_independently_reported_by_native_host"],
                                 before["export_digests_independently_reported_by_native_host"])
                self.assertFalse(audited["human_or_artistic_quality_approved"])
                with self.assertRaises(NativeJournalError):
                    audit_native_journal(events, host_tool_access={
                        **HOST, "get_timeline": "write"})

    def test_host_timeline_guard_denies_forged_picture_and_read_errors(self):
        picture = {
            "kind": "host_native_timeline_picture_observation", "turn": 0,
            "picture_state": "absent", "host_attested_read_only": True,
            "no_native_edit_dispatched": True,
        }
        forged = [
            {**picture, "turn": -1},
            {**picture, "turn": True},
            {**picture, "picture_state": "cut_is_artistically_amazing"},
            {**picture, "picture_state": "present"},
            {**picture, "host_attested_read_only": False},
            {**picture, "no_native_edit_dispatched": False},
            {**picture, "observed_text_sha256": "invalid"},
            {**picture, "secret_source_path": "/home/private"},
            {"kind": "host_native_timeline_read_unknown", "turn": 1,
             "error_type": "private source path", "no_native_edit_dispatched": True},
            {"kind": "host_native_timeline_read_unknown", "turn": 1,
             "error_type": "OSError", "no_native_edit_dispatched": False},
            {"kind": "host_native_timeline_read_unknown", "turn": 1,
             "error_type": "OSError", "no_native_edit_dispatched": True,
             "fabricated_certified_output": True},
        ]
        for event in forged:
            with self.subTest(event=event):
                events = trace()
                events.insert(3, {"sequence": 3, **event})
                for idx, record in enumerate(events):
                    record["sequence"] = idx
                with self.assertRaises(NativeJournalError):
                    audit_native_journal(events, host_tool_access=HOST)

    def test_every_emitted_native_kind_has_a_reviewed_auditor_case(self):
        import re
        from pathlib import Path
        root=Path(__file__).resolve().parent
        emitted=(root/"native_creative_control.py").read_text(encoding="utf-8")
        verified=(root/"native_creative_audit.py").read_text(encoding="utf-8")
        kinds=set(re.findall(r'"kind"\s*:\s*"([a-z][a-z0-9_]+)"',emitted))
        self.assertTrue(kinds)
        auditor_literals=set(re.findall(r'"([a-z][a-z0-9_]+)"',verified))
        self.assertEqual(kinds-auditor_literals,set(),
                         "New controller event needs explicit independent auditor validation")

    def test_real_read_only_native_asset_receipts_cannot_forge_media_proof(self):
        events = trace()
        inventory = {"sequence": 1, "kind":"host_native_asset_inventory",
                     "turn":0, "tool":"get_assets",
                     "host_attested_read_only":True,
                     "actual_imported_asset_total": 0,
                     "source_identities_count": 0,
                     "complete_inventory": True,
                     "text_sha256": [C],
                     "no_native_edit_dispatched": True}
        events.insert(1,inventory)
        for idx, record in enumerate(events):
            record["sequence"]=idx
        grants={**HOST,"get_assets":"read"}
        baseline=audit_native_journal(events,host_tool_access=grants)
        self.assertTrue(baseline["journal_chain_structurally_valid"])
        with self.assertRaises(NativeJournalError):
            audit_native_journal(events,host_tool_access=HOST)
        for field,value in (("host_attested_read_only",False),
                            ("source_identities_count",1),
                            ("text_sha256",["invalid"]),
                            ("no_native_edit_dispatched",False)):
            mutated=copy.deepcopy(events)
            mutated[1][field]=value
            with self.subTest(field=field),self.assertRaises(NativeJournalError):
                audit_native_journal(mutated,host_tool_access=grants)

    def test_new_edit_invalidates_previous_export_and_frame_completion_proofs(self):
        def review_audit(events, **kwargs):
            return audit_native_journal(
                events, host_content_revision_tools=("update_text_clip",), **kwargs)
        events = trace()
        required = ["native_write_acknowledged", "physical_export_verified",
                    "post_observation_native_write_acknowledged",
                    "verified_export_frame_observed"]
        # Existing technical proof has two verified exports and observed frames.
        # A later native revision makes all historical frames stale for
        # completion, without erasing their immutable source custody.
        events[0]["required_completion_evidence"] = required
        prior_finish = events.pop()
        events.extend([
            {"kind": "native_tool_submitted", "turn": 9,
             "tool": "update_text_clip", "inputs_sha256": A,
             "model_reason": "Independent model chose an additional edit"},
            {"kind": "native_tool_result", "turn": 9, "tool": "update_text_clip",
             "text_sha256": [C], "image_sha256": [], "audio_sha256": None,
             "host_application_write_acknowledged": True,
             "host_application_write_receipt_sha256": C,
             "independently_verified_export_sha256": None,
             "observed_export_sha256": None, "human_or_artistic_quality_approved": False},
        ])
        events.append(prior_finish)
        for idx, event in enumerate(events):
            event["sequence"] = idx
        with self.assertRaisesRegex(NativeJournalError, "unresolved native write"):
            review_audit(events, host_tool_access=HOST,
                                 expected_required_evidence=required)
        events[-1] = {"sequence": len(events)-1, "kind": "model_finish_rejected",
                      "turn": 10, "no_native_dispatch": True,
                      "missing_completion_evidence": [
                          "physical_export_verified", "verified_export_frame_observed"]}
        checked = review_audit(events, host_tool_access=HOST,
                                       expected_required_evidence=required)
        self.assertTrue(checked["host_completion_policy_independently_matched"])
        self.assertEqual(checked["observed_verified_export_digests"], [A, B])
        self.assertFalse(checked["video_editing_capability_complete"])

    def test_post_observation_revision_requires_a_real_native_write(self):
        def review_audit(events, **kwargs):
            return audit_native_journal(
                events, host_content_revision_tools=("update_text_clip",), **kwargs)
        events = trace()
        # A first edit/export/frame is insufficient to prove the requested
        # review-and-revision loop. Remove the later edit, keeping both valid
        # frame reads. The auditor must not infer a revision from the model.
        events = [event for event in events if not (
            event.get("tool") == "update_text_clip" and event.get("turn") == 5)]
        for index, event in enumerate(events):
            event["sequence"] = index
        required = ["post_observation_native_write_acknowledged"]
        events[0]["required_completion_evidence"] = required
        with self.assertRaisesRegex(NativeJournalError, "unresolved native write"):
            review_audit(events, host_tool_access=HOST,
                                 expected_required_evidence=required)
        events[-1] = {
            "sequence": len(events) - 1, "kind": "model_finish_rejected",
            "turn": 9, "no_native_dispatch": True,
            "missing_completion_evidence": required}
        verified = review_audit(
            events, host_tool_access=HOST, expected_required_evidence=required)
        self.assertTrue(verified["host_completion_policy_independently_matched"])

    def test_host_required_completion_evidence_is_independently_recomputed(self):
        def review_audit(events, **kwargs):
            return audit_native_journal(
                events, host_content_revision_tools=("update_text_clip",), **kwargs)
        original = trace()
        required = ["native_write_acknowledged", "physical_export_verified",
                    "post_observation_native_write_acknowledged",
                    "verified_export_frame_observed"]
        original[0]["required_completion_evidence"] = required
        refusal = {"kind": "model_finish_rejected", "turn": 0,
                   "missing_completion_evidence": required,
                   "no_native_dispatch": True}
        original.insert(1, refusal)
        for index, event in enumerate(original):
            event["sequence"] = index
        verified = review_audit(
            original, host_tool_access=HOST,
            expected_required_evidence=required)
        self.assertTrue(verified["journal_chain_structurally_valid"])
        self.assertTrue(verified["host_completion_policy_independently_matched"])
        self.assertFalse(review_audit(
            original, host_tool_access=HOST)["host_completion_policy_independently_matched"])
        altered_policy = copy.deepcopy(original)
        altered_policy[0]["required_completion_evidence"] = []
        with self.assertRaisesRegex(NativeJournalError, "differs from trusted host"):
            review_audit(altered_policy, host_tool_access=HOST,
                                 expected_required_evidence=required)
        with self.assertRaisesRegex(NativeJournalError, "Invalid independent host completion policy"):
            review_audit(original, host_tool_access=HOST,
                                 expected_required_evidence=["invented_quality"])

        forged = copy.deepcopy(original)
        forged[1]["missing_completion_evidence"] = ["physical_export_verified"]
        with self.assertRaisesRegex(NativeJournalError, "completion refusal"):
            review_audit(forged, host_tool_access=HOST)
        forged = copy.deepcopy(original)
        forged[1]["no_native_dispatch"] = False
        with self.assertRaisesRegex(NativeJournalError, "completion refusal"):
            review_audit(forged, host_tool_access=HOST)
        forged = copy.deepcopy(original)
        forged[0]["required_completion_evidence"] = ["invented_quality_claim"]
        with self.assertRaisesRegex(NativeJournalError, "completion requirements"):
            review_audit(forged, host_tool_access=HOST)
        # All surviving receipts may be structurally valid, yet a final model
        # declaration still cannot satisfy a required frame that never arrived.
        missing_frames = [event for event in trace()
                          if event.get("tool") != "zx7_observe_verified_export_frame"]
        for index, event in enumerate(missing_frames):
            event["sequence"] = index
        missing_frames[0]["required_completion_evidence"] = [
            "verified_export_frame_observed"]
        with self.assertRaisesRegex(NativeJournalError, "unresolved native write"):
            review_audit(missing_frames, host_tool_access=HOST)


    def test_native_write_acknowledgment_downgrade_cannot_mint_edit_proof(self):
        """A fabricated transport-level result without application ACK is rejected."""
        base = trace()
        edit = next(event for event in base
                    if event.get("kind") == "native_tool_result" and
                    event.get("tool") == "update_text_clip")
        for update in (
            {"host_application_write_acknowledged": None},
            {"host_application_write_acknowledged": "true"},
            {"host_application_write_acknowledged": False},
            {"host_application_write_receipt_sha256": None},
            {"host_application_write_receipt_sha256": B},
            {"text_sha256": []},
            {"image_sha256": [A]},
        ):
            variant = copy.deepcopy(base)
            variant[edit["sequence"]].update(update)
            with self.subTest(update=update), self.assertRaisesRegex(
                    NativeJournalError, "application acknowledgment"):
                audit_native_journal(variant, host_tool_access=HOST)

    def test_honest_technical_custody_without_fake_artistic_claim(self):
        evidence = audit_native_journal(trace(), host_tool_access=HOST)
        self.assertTrue(evidence["journal_chain_structurally_valid"])
        self.assertEqual(evidence["recorded_native_write_result_count"], 4)
        self.assertEqual(evidence["export_digests_independently_reported_by_native_host"], [A, B])
        self.assertEqual(evidence["observed_verified_export_digests"], [A, B])
        self.assertGreater(evidence["model_selected_writes_after_first_verified_observation"], 0)
        self.assertFalse(evidence["physical_media_bytes_redecoded_by_this_audit"])
        self.assertFalse(evidence["real_neural_model_weights_or_inference_independently_attested"])
        self.assertFalse(evidence["human_or_artistic_quality_approved"])
        self.assertFalse(evidence["video_editing_capability_complete"])

    def test_forgery_and_unbound_proofs_fail_closed(self):
        variants = []
        variants.append(lambda x: x[0].update(brief_sha256="bad"))
        variants.append(lambda x: x[5].update(sequence=1))
        variants.append(lambda x: x[10].update(observed_export_sha256=B))
        variants.append(lambda x: x[10].update(tool="get_timeline"))
        variants.append(lambda x: x[10].update(human_or_artistic_quality_approved=True))
        variants.append(lambda x: x[10].update(image_sha256=[]))
        variants.append(lambda x: x[10].update(image_sha256=["invalid"]))
        variants.append(lambda x: x[6].update(independently_verified_export_sha256="c"*64))
        variants.append(lambda x: x[7].update(tool="ungranted_media_reader"))
        variants.append(lambda x: x[11].update(inputs_sha256="0"*63))
        variants.append(lambda x: x[-1].update(creative_quality_independently_approved=True))
        for change in variants:
            events=trace()
            change(events)
            with self.subTest(change=str(change)), self.assertRaises(NativeJournalError):
                audit_native_journal(events, host_tool_access=HOST)

    def test_broken_write_history_never_silently_reports_completion(self):
        events = trace()
        with self.assertRaisesRegex(NativeJournalError, "outcome"):
            audit_native_journal(events[:-1] + [{"sequence": len(events)-1,
                "kind": "native_tool_submitted", "tool": "update_text_clip", "turn": 9,
                "inputs_sha256": A, "model_reason": "lost write"}],
                host_tool_access=HOST)
        events = trace()
        pos = next(i for i, event in enumerate(events)
                   if event["kind"] == "native_tool_result" and event["tool"] == "update_text_clip")
        events[pos] = {"sequence": pos, "kind": "native_tool_reported_error",
                       "tool": "update_text_clip", "turn": 1,
                       "must_reconcile_native_state": True}
        with self.assertRaisesRegex(NativeJournalError, "followed by unsafe"):
            audit_native_journal(events, host_tool_access=HOST)
        events = trace()
        events[-1].update(kind="model_finished",
                          creative_quality_independently_approved=True)
        with self.assertRaises(NativeJournalError):
            audit_native_journal(events, host_tool_access=HOST)

    def test_sensor_roles_are_host_grants_not_a_model_imitation(self):
        events=trace()
        with self.assertRaisesRegex(NativeJournalError, "host grant"):
            audit_native_journal(events, host_tool_access={
                k:v for k,v in HOST.items() if k != "zx7_verify_native_export"})
        events=trace()
        obs=next(e for e in events if e["kind"] == "native_tool_result"
                 and e["tool"] == "zx7_observe_verified_export_frame")
        obs["audio_sha256"]=A
        with self.assertRaisesRegex(NativeJournalError, "audio"):
            audit_native_journal(events, host_tool_access=HOST)

    def test_model_inference_failure_is_terminal_and_cannot_be_forged_as_completion(self):
        events = [
            {"kind": "session_started", "sequence": 0, "brief_sha256": A},
            {"kind": "model_decision_failed", "sequence": 1, "turn": 0,
             "measured_model_wall_ms": 2.1, "error_type": "TimeoutError",
             "no_automatic_retry": True,
             "creative_quality_independently_approved": False},
        ]
        evidence = audit_native_journal(events, host_tool_access=HOST)
        self.assertEqual(evidence["model_reported_end_state"], "model_decision_failed")
        self.assertFalse(evidence["video_editing_capability_complete"])
        for corrupt in (
            {"no_automatic_retry": False},
            {"measured_model_wall_ms": -1},
            {"measured_model_wall_ms": float("inf")},
            {"measured_model_wall_ms": True},
            {"creative_quality_independently_approved": True},
        ):
            broken = copy.deepcopy(events)
            broken[-1].update(corrupt)
            with self.subTest(corrupt=corrupt), self.assertRaises(NativeJournalError):
                audit_native_journal(broken, host_tool_access=HOST)
        extended = copy.deepcopy(events)
        extended.append({"kind": "model_finished", "sequence": 2, "turn": 1,
                         "summary": "fake completion",
                         "creative_quality_independently_approved": False})
        with self.assertRaises(NativeJournalError):
            audit_native_journal(extended, host_tool_access=HOST)

    def test_a_real_jsonl_file_cannot_be_swapped_by_symlink_or_forged_keys(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            source=root/"verified.jsonl"
            source.write_text("".join(json.dumps(ev,sort_keys=True)+"\n" for ev in trace()))
            self.assertEqual(read_native_journal(source), trace())
            redirected=root/"alias.jsonl"
            redirected.symlink_to(source)
            with self.assertRaisesRegex(NativeJournalError,"symlink"):
                read_native_journal(redirected)
            source.write_bytes(b'{"sequence":0,"sequence":1,"kind":"session_started"}\n')
            with self.assertRaisesRegex(NativeJournalError,"Duplicate"):
                read_native_journal(source)
            source.write_bytes(b'{"sequence":0,"kind":"session_started","v":NaN}\n')
            with self.assertRaisesRegex(NativeJournalError,"Nonfinite"):
                read_native_journal(source)
            source.write_bytes(b'{"sequence":0,"kind":"session_started","v":1e999}\n')
            with self.assertRaisesRegex(NativeJournalError,"Overflowed"):
                read_native_journal(source)
            source.write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(NativeJournalError,"UTF-8"):
                read_native_journal(source)


    def test_new_private_intent_receipts_and_legacy_proofs_are_both_checked(self):
        events = trace()
        for event in events:
            if event["kind"] == "native_tool_submitted":
                reason = event.pop("model_reason")
                event["model_reason_sha256"] = hashlib.sha256(reason.encode()).hexdigest()
                event["model_reason_utf8_bytes"] = len(reason.encode())
            if event["kind"] == "model_finished":
                summary = event.pop("summary")
                event["summary_sha256"] = hashlib.sha256(summary.encode()).hexdigest()
                event["summary_utf8_bytes"] = len(summary.encode())
        accepted = audit_native_journal(events, host_tool_access=HOST)
        self.assertTrue(accepted["journal_chain_structurally_valid"])
        # Ambiguous old+new envelopes must not become an escape hatch.
        modifications = [
            (1, {"model_reason": "private leak"}),
            (1, {"model_reason_utf8_bytes": True}),
            (1, {"model_reason_sha256": "invalid"}),
            (1, {"model_reason_utf8_bytes": -1}),
            (-1, {"summary": "private leak"}),
            (-1, {"summary_utf8_bytes": True}),
            (-1, {"summary_sha256": "bad"}),
            (-1, {"summary_utf8_bytes": 0}),
        ]
        for index, change in modifications:
            with self.subTest(index=index, change=change):
                broken = copy.deepcopy(events)
                broken[index].update(change)
                with self.assertRaises(NativeJournalError):
                    audit_native_journal(broken, host_tool_access=HOST)


    def test_forged_model_preflight_cannot_claim_no_native_mutation(self):
        events = trace()
        before = {"sequence": 1, "kind": "model_action_rejected",
                  "turn": 0, "tool": "update_text_clip",
                  "inputs_sha256": A, "validation_keyword": "type",
                  "no_native_dispatch": True}
        events.insert(1, before)
        for i, event in enumerate(events):
            event["sequence"] = i
        result = audit_native_journal(events, host_tool_access=HOST)
        self.assertTrue(result["journal_chain_structurally_valid"])
        self.assertEqual(result["recorded_native_write_result_count"], 4)
        for change in (
            {"no_native_dispatch": False},
            {"tool": "not_granted"},
            {"validation_keyword": ""},
            {"inputs_sha256": "wrong"},
        ):
            broken = copy.deepcopy(events)
            broken[1].update(change)
            with self.subTest(change=change), self.assertRaises(NativeJournalError):
                audit_native_journal(broken, host_tool_access=HOST)
        # A preflight rejection cannot be interleaved after an unresolved write.
        broken = trace()
        broken.insert(2, copy.deepcopy(before))
        for i, event in enumerate(broken):
            event["sequence"] = i
        with self.assertRaisesRegex(NativeJournalError, "preflight"):
            audit_native_journal(broken, host_tool_access=HOST)


    def test_read_only_error_can_be_followed_by_another_model_action(self):
        baseline = trace()
        marker = baseline.index(next(x for x in baseline if x["kind"] == "native_tool_result"))
        submission = baseline[marker-1]
        submission["tool"] = "get_timeline"
        read_error = {"sequence": marker, "kind": "native_read_tool_reported_error",
                      "turn": submission["turn"], "tool": "get_timeline",
                      "error_sha256": A, "error_text_exceeded_evidence_budget": False,
                      "host_attested_read_only": True,
                      "no_successful_native_observation": True}
        baseline[marker] = read_error
        for i, event in enumerate(baseline):
            event["sequence"] = i
        good = audit_native_journal(baseline, host_tool_access=HOST)
        self.assertTrue(good["journal_chain_structurally_valid"])
        self.assertEqual(good["model_reported_end_state"], "model_finished")
        for change in (
            {"host_attested_read_only": False},
            {"no_successful_native_observation": False},
            {"error_sha256": None},
            {"error_text_exceeded_evidence_budget": True},
            {"tool": "update_text_clip"},
        ):
            bad = copy.deepcopy(baseline)
            bad[marker].update(change)
            with self.subTest(change=change), self.assertRaises(NativeJournalError):
                audit_native_journal(bad, host_tool_access=HOST)


    def test_initial_project_read_requires_real_host_read_grant_and_sequence(self):
        events = trace()
        read = {"kind": "host_project_bootstrap_observation", "sequence": 1,
                "tool": "get_project", "host_attested_read_only": True,
                "text_sha256": [A], "project_presence": "absent",
                "no_model_selected_mutation": True}
        events.insert(1, read)
        for i, event in enumerate(events):
            event["sequence"] = i
        access = dict(HOST, get_project="read")
        self.assertTrue(audit_native_journal(events, host_tool_access=access)
                        ["journal_chain_structurally_valid"])
        for change in ({"host_attested_read_only": False}, {"project_presence": "magic"},
                       {"text_sha256": []}, {"no_model_selected_mutation": False}):
            altered = copy.deepcopy(events)
            altered[1].update(change)
            with self.subTest(change=change), self.assertRaises(NativeJournalError):
                audit_native_journal(altered, host_tool_access=access)
        with self.assertRaises(NativeJournalError):
            audit_native_journal(events, host_tool_access=dict(HOST, get_project="write"))
        misplaced = copy.deepcopy(events)
        misplaced.insert(2, misplaced.pop(1))
        for i, event in enumerate(misplaced):
            event["sequence"] = i
        with self.assertRaises(NativeJournalError):
            audit_native_journal(misplaced, host_tool_access=access)

    def test_capability_search_audit_fails_on_ungranted_or_forged_identity(self):
        baseline = trace()
        template = {"kind": "capability_searched", "turn": 0,
                    "query_sha256": A, "catalog_revision": B,
                    "result_tool_names": ["get_timeline"],
                    "no_native_dispatch": True}
        baseline.insert(1, {"sequence": 1, **template})
        for i, event in enumerate(baseline):
            event["sequence"] = i
        self.assertTrue(audit_native_journal(
            baseline, host_tool_access=HOST)["journal_chain_structurally_valid"])
        for wrong in ({"result_tool_names": ["invented"]},
                      {"result_tool_names": ["get_timeline", "get_timeline"]},
                      {"result_tool_names": "get_timeline"},
                      {"catalog_revision": "bad"},
                      {"no_native_dispatch": False}):
            clone = copy.deepcopy(baseline)
            clone[1].update(wrong)
            with self.subTest(wrong=wrong), self.assertRaises(NativeJournalError):
                audit_native_journal(clone, host_tool_access=HOST)


    def test_source_attested_machine_frontier_rejects_forged_project_state(self):
        events = trace()
        # The same ordered native bootstrap previously established in this
        # test suite, then an advisory no-RPC candidate list.
        bootstrap = {"kind": "host_project_bootstrap_observation",
            "tool": "get_project", "host_attested_read_only": True,
            "text_sha256": [A], "project_presence": "absent",
            "no_model_selected_mutation": True}
        frontier = {"kind": "host_capability_frontier",
                    "catalog_revision": A,
                    "result_tool_names": ["get_timeline"],
                    "trusted_machine_fact": "project_open",
                    "host_observed_value": False,
                    "no_native_dispatch": True}
        events.insert(1, bootstrap)
        events.insert(2, frontier)
        for idx, item in enumerate(events):
            item["sequence"] = idx
        grants = dict(HOST, get_project="read")
        self.assertTrue(audit_native_journal(events, host_tool_access=grants)[
            "journal_chain_structurally_valid"])
        for change in ({"host_observed_value": True},
                       {"result_tool_names": ["fantasy"]},
                       {"trusted_machine_fact": "model_guess"},
                       {"no_native_dispatch": False}):
            invalid = copy.deepcopy(events)
            invalid[2].update(change)
            with self.subTest(change=change), self.assertRaises(NativeJournalError):
                audit_native_journal(invalid, host_tool_access=grants)


if __name__ == "__main__":
    unittest.main()
