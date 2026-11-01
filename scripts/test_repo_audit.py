"""Reality-based tests for the full Git source integrity/AST audit."""
import tempfile
import hashlib
import shutil
import subprocess
import unittest
from pathlib import Path

from repo_audit import audit


class EntireTrackedSourceAudit(unittest.TestCase):
    def test_exact_digest_and_line_number_for_native_file_publication(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)
            (source/"native_movie.py").write_text(
                "import os\ndef publish(stage,master):\n    os.link(stage,master)\n")
            (source/"plan.json").write_text('{"original":true}')
            report=audit(source,["native_movie.py","plan.json"])
            self.assertEqual(report["blocking_source_format_errors"],[])
            self.assertEqual(report["total_file_count"],2)
            self.assertEqual(report["counts"]["python"],1)
            self.assertEqual(report["counts"]["json"],1)
            self.assertEqual(report["static_source_change_sites"][0]["call"],"os.link")
            self.assertEqual(report["static_source_change_sites"][0]["line"],3)
            self.assertFalse(report["film_release_production_approved"])

    def test_corrupted_original_source_prevents_clean_repository_audit(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            (folder/"broken.py").write_text("def missing(:\n")
            (folder/"invalid.json").write_bytes(b"not json")
            report=audit(folder,["broken.py","invalid.json","missing.otio"])
            self.assertEqual(len(report["blocking_source_format_errors"]),3)
            self.assertFalse(report["all_twelve_quality_gates_complete"])

    def test_unapproved_shell_and_destructive_path_is_visible_as_risk_not_approval(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            (folder/"editor.py").write_text(
                "import subprocess\n"
                "def edit(movie):\n"
                "    subprocess.run('echo hi', shell=True)\n"
                "    movie.unlink()\n")
            report=audit(folder,["editor.py"])
            risky=report["static_source_change_sites"]
            self.assertEqual(len(risky),2)
            self.assertTrue(risky[0]["shell_true"])
            self.assertFalse(risky[1]["independently_security_reviewed"])


class PinnedSubmoduleSourceAudit(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"parent"
        self.root.mkdir()
        self.git(self.root,"init","-q")
        self.child=self.root/"third_party"/"editor"
        self.child.mkdir(parents=True)
        self.git(self.child,"init","-q")
        (self.child/"editor.py").write_text("def edit():\n    return 'native'\n")
        (self.child/"native.json").write_text('{"editable":true}')
        self.git(self.child,"add","editor.py","native.json")
        self.commit_child()
        self.pin=self.git(self.child,"rev-parse","HEAD").strip()
        (self.root/".gitmodules").write_text(
            '[submodule "editor"]\n\tpath = third_party/editor\n\turl = https://example.invalid/editor.git\n')
        self.git(self.root,"add",".gitmodules")
        self.git(self.root,"update-index","--add","--cacheinfo",f"160000,{self.pin},third_party/editor")

    @staticmethod
    def git(root,*args):
        return subprocess.run(["git","-C",str(root),*args],capture_output=True,
                              text=True,check=True,timeout=15).stdout

    def commit_child(self):
        self.git(self.child,"-c","user.name=Source test","-c","user.email=test@example.invalid",
                 "commit","-qm","Native source")

    def report(self):
        return audit(self.root,[".gitmodules","third_party/editor"])

    def assert_blocked(self):
        report=self.report()
        self.assertTrue(report["blocking_source_format_errors"])
        self.assertEqual(report.get("pinned_sources",[]),[])
        return report

    def test_exact_pin_recursively_hashes_real_sources(self):
        report=self.report()
        self.assertEqual(report["blocking_source_format_errors"],[])
        self.assertEqual(report["pinned_sources"][0]["commit"],self.pin)
        files={entry["path"]:entry for entry in report["files"]}
        self.assertNotIn("third_party/editor",files)
        self.assertEqual(files["third_party/editor/editor.py"]["sha256"],
                         hashlib.sha256((self.child/"editor.py").read_bytes()).hexdigest())
        self.assertEqual(report["counts"]["python"],1)

    def test_standard_git_file_checkout_is_supported(self):
        metadata=Path(self.temp.name)/"editor-git"
        shutil.move(self.child/".git",metadata)
        (self.child/".git").write_text(f"gitdir: {metadata}\n")
        report=self.report()
        self.assertEqual(report["blocking_source_format_errors"],[])
        self.assertEqual(report["pinned_sources"][0]["commit"],self.pin)

    def test_uninitialized_submodule_is_blocked(self):
        shutil.rmtree(self.child)
        self.assert_blocked()

    def test_arbitrary_directory_cannot_inherit_parent_repository(self):
        # Moving metadata out proves the exact missing repository boundary
        # without recursively racing transient Git object maintenance files.
        shutil.move(self.child/".git", Path(self.temp.name)/"orphaned-git-metadata")
        self.assert_blocked()

    def test_wrong_checked_out_commit_is_blocked(self):
        (self.child/"new.txt").write_text("new source")
        self.git(self.child,"add","new.txt")
        self.commit_child()
        self.assert_blocked()

    def test_modified_tracked_source_is_blocked(self):
        (self.child/"editor.py").write_text("changed=True\n")
        self.assert_blocked()

    def test_staged_tracked_source_change_is_blocked(self):
        (self.child/"editor.py").write_text("changed=True\n")
        self.git(self.child,"add","editor.py")
        self.assert_blocked()

    def test_assume_unchanged_source_cannot_hide_mutation(self):
        self.git(self.child,"update-index","--assume-unchanged","editor.py")
        (self.child/"editor.py").write_text("changed=True\n")
        self.assert_blocked()

    def test_sparse_source_index_flags_are_blocked(self):
        self.git(self.child,"update-index","--skip-worktree","editor.py")
        self.assert_blocked()

    def test_unregistered_gitlink_is_blocked(self):
        (self.root/".gitmodules").write_text('[submodule "other"]\n\tpath = elsewhere\n')
        self.assert_blocked()

    def test_duplicate_gitlink_registration_is_blocked(self):
        with (self.root/".gitmodules").open("a") as output:
            output.write('[submodule "duplicate"]\n\tpath = third_party/editor\n')
        self.assert_blocked()

    def test_nested_source_parse_error_is_reported_with_full_path(self):
        (self.child/"native.json").write_text("invalid json")
        self.git(self.child,"add","native.json")
        self.commit_child()
        pin=self.git(self.child,"rev-parse","HEAD").strip()
        self.git(self.root,"update-index","--cacheinfo",f"160000,{pin},third_party/editor")
        report=self.report()
        self.assertEqual(report["blocking_source_format_errors"][0]["path"],
                         "third_party/editor/native.json")


if __name__=="__main__":
    unittest.main()
