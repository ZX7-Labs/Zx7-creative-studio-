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


class ProjectBrainContractTests(unittest.TestCase):
    def test_real_repo_brain_is_complete_and_connected(self):
        self.assertEqual(_module.validate(_here), [])

    def test_secret_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "project-brain"
            shutil.copytree(_here, root, ignore=shutil.ignore_patterns("__pycache__"))
            (root / "BRIEF.md").write_text("# bad\nnvapi-" + "A" * 40)
            self.assertIn("sensitive_material: BRIEF.md", _module.validate(root))
            (root / "BRIEF.md").unlink()
            (root / "BRIEF.md").symlink_to(root / "STATE.md")
            self.assertIn("missing_or_symlink: BRIEF.md", _module.validate(root))

    def test_missing_and_unsafe_source_links_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "project-brain"
            shutil.copytree(_here, root, ignore=shutil.ignore_patterns("__pycache__"))
            with (root / "RISKS.md").open("a", encoding="utf-8") as stream:
                stream.write("\n[unsafe](../../../../some-private-file.md)\n")
            self.assertTrue(any("broken_or_escaping_link: RISKS.md" in x
                                for x in _module.validate(root)))


if __name__ == "__main__":
    unittest.main()
