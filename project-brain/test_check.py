"""Negative and positive tests for the repository-only continuity contract."""
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
    shutil.copyfile(_here.parent / "docs" / "ZX7_CREATIVE_STUDIO_MASTER_PLAN.md",
                    docs / "ZX7_CREATIVE_STUDIO_MASTER_PLAN.md")
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
            self.assertEqual(_module.validate(root), [])
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


if __name__ == "__main__":
    unittest.main()
