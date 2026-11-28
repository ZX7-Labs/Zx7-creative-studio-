"""Negative and positive tests for the repository-only continuity contract."""
import json
import pathlib
import shutil
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location

_here = pathlib.Path(__file__).resolve().parent
_spec = spec_from_file_location("zx7_project_brain_check", _here / "check.py")
_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)


def _copy_scope_fixture(temp):
    root = pathlib.Path(temp) / "project-brain"
    shutil.copytree(_here, root, ignore=shutil.ignore_patterns("__pycache__"))
    docs = root.parent / "docs"
    docs.mkdir()
    for document in ("ZX7_CREATIVE_STUDIO_MASTER_PLAN.md", "BUILD_BLUEPRINT.md", "DOCUMENT_MAP.md"):
        shutil.copyfile(_here.parent / "docs" / document, docs / document)
    return root


class ProjectBrainContractTests(unittest.TestCase):
    def test_real_repo_brain_is_complete_and_connected(self):
        self.assertEqual(_module.validate(_here), [])

    def test_secret_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            (root / "BRIEF.md").write_text("# bad\nnvapi-" + "A" * 40)
            self.assertIn("sensitive_material: BRIEF.md", _module.validate(root))
            (root / "BRIEF.md").unlink()
            (root / "BRIEF.md").symlink_to(root / "STATE.md")
            self.assertIn("missing_or_symlink: BRIEF.md", _module.validate(root))

    def test_missing_and_unsafe_source_links_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            with (root / "RISKS.md").open("a", encoding="utf-8") as stream:
                stream.write("\n[unsafe](../../../../some-private-file.md)\n")
            self.assertTrue(any("broken_or_escaping_link: RISKS.md" in x
                                for x in _module.validate(root)))


    def test_master_scope_regression_and_fixture_loss(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            # Synthetic fixture intentionally lacks unrelated canonical repo docs;
            # test only the targeted scope-regression signal, not zero errors.
            plan = root.parent / "docs" / "ZX7_CREATIVE_STUDIO_MASTER_PLAN.md"
            original = plan.read_text(encoding="utf-8")
            self.assertIn("| **L —", original)
            plan.write_text(original.replace("| **L —", "| **Z —", 1),
                            encoding="utf-8")
            self.assertIn("missing_or_duplicate_coverage: A-L",
                          _module.validate(root))
            plan.write_text(original, encoding="utf-8")

            fixtures = root / "EVIDENCE" / "2026-11-12-G0-COVERAGE.md"
            original_fixtures = fixtures.read_text(encoding="utf-8")
            self.assertIn("| F14 |", original_fixtures)
            fixtures.write_text(original_fixtures.replace("| F14 |", "| F99 |", 1),
                                encoding="utf-8")
            self.assertIn("missing_or_duplicate_coverage: F01-F14",
                          _module.validate(root))

    def test_master_missing_and_test_case_id_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            plan = root.parent / "docs" / "ZX7_CREATIVE_STUDIO_MASTER_PLAN.md"
            source = plan.read_text(encoding="utf-8")
            self.assertIn("| T24 |", source)
            plan.write_text(source.replace("| T24 |", "| T99 |", 1), encoding="utf-8")
            self.assertIn("missing_or_duplicate_coverage: T01-T24",
                          _module.validate(root))
            plan.unlink()
            self.assertIn("missing_or_symlink: ../docs/ZX7_CREATIVE_STUDIO_MASTER_PLAN.md",
                          _module.validate(root))


    def test_ledger_json_invalid_source_and_unearned_field_acceptance_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            path = root / "EXECUTION_LEDGER.json"
            original = path.read_text(encoding="utf-8")
            path.write_text("{ definitely not json", encoding="utf-8")
            self.assertIn("invalid_execution_ledger_json", _module.validate(root))
            data = json.loads(original)
            data["domains"][0]["independent_field_acceptance"] = "ACCEPTED"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn("unsupported_execution_ledger_field_acceptance",
                          _module.validate(root))

    def test_deleted_domain_duplicate_failures_and_false_neural_pass_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            path = root / "EXECUTION_LEDGER.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["domains"] = data["domains"][:-1]
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn("invalid_execution_ledger_domain_coverage",
                          _module.validate(root))
            data = json.loads((_here / "EXECUTION_LEDGER.json").read_text(encoding="utf-8"))
            data["failures"][1]["id"] = data["failures"][0]["id"]
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn("invalid_execution_ledger_failure_ids",
                          _module.validate(root))
            data["failures"][1]["id"] = "F-REAL-002"
            data["failures"][0]["post_fix_real_model_retest"] = "PASSED"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn("unreviewed_execution_ledger_neural_success",
                          _module.validate(root))

    def test_fixed_fabric_boundary_and_full_g1_plan_cannot_disappear_silently(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            blueprint = root.parent / "docs" / "BUILD_BLUEPRINT.md"
            original = blueprint.read_text(encoding="utf-8")
            self.assertIn("CANDIDATE / G2", original)
            blueprint.write_text(original.replace("CANDIDATE / G2", "FIXED / G2", 1),
                                 encoding="utf-8")
            self.assertIn("invalid_blueprint_fixed_vs_hypothesis_boundary",
                          _module.validate(root))
            blueprint.write_text(original.replace("G1-07", "G1-XX", 1), encoding="utf-8")
            self.assertIn("invalid_blueprint_fixed_vs_hypothesis_boundary",
                          _module.validate(root))

    def test_ledger_g1_priorities_and_failure_provenance_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            path = root / "EXECUTION_LEDGER.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["open_gates"][0]["state"] = "ACCEPTED"
            data["failures"][0]["run_url"] = "https://invalid.example"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn("invalid_execution_ledger_g1_priority",
                          _module.validate(root))
            self.assertIn("invalid_execution_ledger_failure_evidence",
                          _module.validate(root))


    def test_future_evidence_backed_progress_is_structurally_admissible(self):
        """Synthetic evidence shape proves checker can advance; not real acceptance."""
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            path = root / "EXECUTION_LEDGER.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            synthetic = {
                "source_sha": "a" * 40,
                "report_url": "https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/999000001",
                "reviewer": "synthetic-external-review-fixture",
                "scope": "defined-source-and-professional-review",
            }
            data["domains"][0]["independent_field_acceptance"] = "ACCEPTED"
            data["domains"][0]["acceptance_evidence"] = dict(synthetic)
            data["failures"][0]["post_fix_real_model_retest"] = "PASSED"
            data["failures"][0]["post_fix_retest_evidence"] = {
                "source_sha": "b" * 40,
                "run_url": "https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/999000002",
                "same_task_as": "F-REAL-001",
                "artifact_sha256": "c" * 64,
            }
            data["open_gates"][0]["state"] = "ACCEPTED"
            data["open_gates"][0]["acceptance_evidence"] = dict(synthetic)
            path.write_text(json.dumps(data), encoding="utf-8")
            problems = _module.validate(root)
            self.assertNotIn("unsupported_execution_ledger_field_acceptance", problems)
            self.assertNotIn("unreviewed_execution_ledger_neural_success", problems)
            self.assertNotIn("invalid_execution_ledger_g1_priority", problems)

    def test_append_only_decision_history_can_expand_safely(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            decisions = root / "DECISIONS.md"
            with decisions.open("a", encoding="utf-8") as stream:
                stream.write("\\n- **D044 · SYNTHETIC FIXTURE:** " + "A" * 10000 + "\\n")
            self.assertNotIn("too_large: DECISIONS.md", _module.validate(root))

    def test_current_owner_provider_policy_is_not_mixed_with_old_now_commands(self):
        brief = (_here / "BRIEF.md").read_text(encoding="utf-8")
        # Validate a single dated current owner policy, not a frozen historical date.
        self.assertRegex(brief, r"\*\*Owner clarification · \d{4}-\d{2}-\d{2} \(CURRENT\):\*\*")
        self.assertEqual(brief.count("(CURRENT):**"), 1)
        self.assertIn("Normal CI must never call a hosted provider implicitly", brief)
        self.assertIn("private", brief.lower())
        self.assertNotIn("- **NOW (historical):**", brief)
        self.assertNotIn("updated 2026-11-10 following the founder's NVIDIA-first", brief)

    def test_active_build_plan_has_no_historical_failure_as_locked_requirement(self):
        blueprint = (_here.parent / "docs" / "BUILD_BLUEPRINT.md").read_text(encoding="utf-8")
        self.assertNotIn("Known actual neural negative baseline", blueprint)
        master = (_here.parent / "docs" / "ZX7_CREATIVE_STUDIO_MASTER_PLAN.md").read_text(encoding="utf-8")
        self.assertNotIn("Authoritative *planning consolidation candidate*", master[:850])



    def test_current_state_is_bound_to_exact_mutable_ledger_blob(self):
        # No private data or model calls: this is only a stale-document guard.
        self.assertNotIn("state_ledger_content_mismatch", _module.validate(_here))
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            path = root / "EXECUTION_LEDGER.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["snapshot"]["notes"] += " synthetic-state-drift"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn("state_ledger_content_mismatch", _module.validate(root))
            state = root / "STATE.md"
            state.write_text(state.read_text(encoding="utf-8").replace(
                "LEDGER_GIT_BLOB=", "LEDGER_BINDING_REMOVED="
            ), encoding="utf-8")
            self.assertIn("state_missing_ledger_binding", _module.validate(root))



    def test_future_independent_review_can_link_a_pr_or_versioned_report(self):
        # Synthetic receipt shapes only: the tool does not authenticate judges.
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            path = root / "EXECUTION_LEDGER.json"
            base = json.loads(path.read_text(encoding="utf-8"))
            for report_url in (
                "https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/123",
                "https://github.com/ZX7-Labs/Zx7-creative-studio-/blob/main/docs/report.md",
            ):
                data = json.loads(json.dumps(base))
                data["domains"][0]["independent_field_acceptance"] = "ACCEPTED"
                data["domains"][0]["acceptance_evidence"] = {
                    "source_sha": "f" * 40,
                    "report_url": report_url,
                    "reviewer": "synthetic-evaluator",
                    "scope": "synthetic-domain-task",
                }
                path.write_text(json.dumps(data), encoding="utf-8")
                self.assertNotIn("unsupported_execution_ledger_field_acceptance",
                                 _module.validate(root))
            data["domains"][0]["acceptance_evidence"]["report_url"] = (
                "https://malicious.invalid/claimed-review"
            )
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn("unsupported_execution_ledger_field_acceptance",
                          _module.validate(root))


    def test_typed_execution_ledger_grows_beyond_old_limit_but_stays_bounded(self):
        # RED at 40 KB: exact-head #356 integrity run 44099891001 rejected
        # an otherwise valid 41+ KB typed ledger. Preserve limits elsewhere.
        with tempfile.TemporaryDirectory() as temp:
            root = _copy_scope_fixture(temp)
            path = root / "EXECUTION_LEDGER.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            # Measure the serialization used by the fixture, not the source
            # file's whitespace. A ledger close to the bound must not be
            # accidentally inflated by reindenting historical records.
            def packed(value):
                return json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
            baseline_bytes = len(packed(record).encode("utf-8"))
            padding = max(0, 43_000 - baseline_bytes)
            if padding:
                record["snapshot"]["notes"] += " synthetic-source-linked-receipts " + "r" * padding
            path.write_text(packed(record), encoding="utf-8")
            self.assertGreater(path.stat().st_size, 40_000)
            self.assertLess(path.stat().st_size, 80_000)
            self.assertNotIn("too_large: EXECUTION_LEDGER.json", _module.validate(root))
            # No unlimited diary: the typed ledger still fails closed above 80 KB.
            with path.open("ab") as stream:
                stream.write(b" " * (80_001 - path.stat().st_size))
            self.assertIn("too_large: EXECUTION_LEDGER.json", _module.validate(root))


if __name__ == "__main__":
    unittest.main()
