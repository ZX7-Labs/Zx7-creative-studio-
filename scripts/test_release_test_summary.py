"""Regression tests for the release evidence's unittest result parser."""
import unittest

from release_test_summary import parse_unittest_summary

from release_artifact_integrity import (
    ReleaseArtifactIntegrityError, verify_release_tree,
)
import hashlib
import json
from pathlib import Path
import tempfile
from zipfile import ZipFile


class ReleaseTestSummaryTests(unittest.TestCase):
    def test_unittest_success_with_skips_is_a_successful_release_test_run(self):
        log = ("test_one (Tests.test_one) ... ok\n"
               "test_two (Tests.test_two) ... skipped 'optional engine'\n"
               "\n----------------------------------------------------------------------\n"
               "Ran 2 tests in 0.042s\n\nOK (skipped=1)\n")
        self.assertEqual(parse_unittest_summary(log), (2, 1))

    def test_real_release_sized_run_accepts_fourteen_actual_skips(self):
        # A real installed-body release measured 873 tests and 14 optional
        # skips. It must not be marked failed merely for having >1 skip.
        log = "".join(f"test_{i} (Suite.test_{i}) ... ok\n"
                      for i in range(859))
        log += "".join(f"test_optional_{i} (Suite.test_optional_{i}) ... skipped 'unavailable'\n"
                       for i in range(14))
        log += "\n----------------------------------------------------------------------\n"
        log += "Ran 873 tests in 997.918s\n\nOK (skipped=14)\n"
        self.assertEqual(parse_unittest_summary(log), (873, 14))
        with self.assertRaises(ValueError):
            parse_unittest_summary(log.replace("OK (skipped=14)", "OK (skipped=13)"))
        with self.assertRaises(ValueError):
            parse_unittest_summary(log.replace("OK (skipped=14)", "FAILED (failures=1)"))

    def test_success_without_skips(self):
        self.assertEqual(parse_unittest_summary(
            "test_one (Tests.test_one) ... ok\nRan 1 test in 0.1s\n\nOK\n"), (1, 0))

    def test_reject_failed_missing_or_truncated_results(self):
        logs = (
            "test_one (Tests.test_one) ... FAIL\nRan 1 test in 1s\nFAILED (failures=1)",
            "test_one (Tests.test_one) ... ok\nRan 1 test in 1s\n",
            "test_one (Tests.test_one) ... ok\nOK",
            "Ran 0 tests in 0.1s\nOK",
            "test_one (Tests.test_one) ... skipped 'not installed'\nRan 1 test in 1s\nOK",
            "Ran 1 test in 1s\nOK (skipped=1)",
            "test_one (Tests.test_one) ... skipped 'not installed'\nRan 1 test in 1s\nOK (skipped=2)",
        )
        for log in logs:
            with self.subTest(log=log), self.assertRaises(ValueError):
                parse_unittest_summary(log)

    def test_uses_final_unittest_run_not_prior_nested_result(self):
        log = ("Ran 1 test in 0.1s\nOK\n"
               "test_a (Outer.test_a) ... ok\n"
               "test_b (Outer.test_b) ... skipped 'platform'\n"
               "Ran 2 tests in 0.2s\nOK (skipped=1)\n")
        self.assertEqual(parse_unittest_summary(log), (2, 1))


class ReleaseArtifactUploadIntegrityTests(unittest.TestCase):
    """Model a real actions/upload-artifact omission and post-download audit."""

    @staticmethod
    def fixture(root: Path):
        media = root / "native" / "sample.mp4"
        media.parent.mkdir()
        media.write_bytes(b"synthetic self-hosted release bytes" * 12)
        digest = hashlib.sha256(media.read_bytes()).hexdigest()
        receipt_dir = media.parent / ".zx7-publications"
        receipt_dir.mkdir()
        identity = {"project_key": "1" * 64, "node_id": "render",
                    "input_key": "2" * 64, "tool_id": "body.render"}
        canonical = hashlib.sha256(json.dumps(
            {"identity": identity, "output": str(media.absolute())},
            sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        receipt = receipt_dir / (canonical + ".json")
        record = {
            "schema": 1,
            "identity": identity,
            "output": str(media.absolute()),
            "stage": ".zx7-uncommitted-" + "b" * 32 + ".mp4",
            "sha256": digest, "bytes": media.stat().st_size,
        }
        receipt.write_text(json.dumps(record), encoding="utf-8")
        ReleaseArtifactUploadIntegrityTests.write_manifest(root)
        return media, receipt

    @staticmethod
    def write_manifest(root: Path):
        manifest = []
        for p in root.rglob("*"):
            if p.is_file() and p.name != "verified-release-evidence.json":
                manifest.append({
                    "path": p.relative_to(root).as_posix(),
                    "bytes": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                })
        (root / "verified-release-evidence.json").write_text(
            json.dumps({"schema": 1, "artifacts": manifest}), encoding="utf-8")

    @staticmethod
    def extracted_archive(root: Path, destination: Path, *, include_hidden: bool):
        archive = destination.parent / (destination.name + ".zip")
        with ZipFile(archive, "w") as target:
            for p in root.rglob("*"):
                if p.is_file() and (include_hidden or
                                    not any(part.startswith(".") for part in
                                            p.relative_to(root).parts)):
                    target.write(p, p.relative_to(root).as_posix())
        with ZipFile(archive) as saved:
            saved.extractall(destination)

    def test_hidden_receipts_must_survive_actual_artifact_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            source.mkdir()
            self.fixture(source)
            self.assertEqual(verify_release_tree(source)["source_bound_publication_receipts"], 1)

            omitted = base / "omitted"
            self.extracted_archive(source, omitted, include_hidden=False)
            with self.assertRaisesRegex(
                    ReleaseArtifactIntegrityError, "disagree with manifest"):
                verify_release_tree(omitted)

            retained = base / "retained"
            self.extracted_archive(source, retained, include_hidden=True)
            proof = verify_release_tree(retained, relocated=True)
            self.assertTrue(proof["verified"])
            self.assertEqual(proof["files"], 2)
            self.assertEqual(proof["source_bound_publication_receipts"], 1)
            self.assertFalse(proof["artistic_quality_approved"])

    def test_reject_tampering_unlisted_files_and_unexpected_hidden_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            media, receipt = self.fixture(root)
            media.write_bytes(b"changed physical bytes")
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "changed"):
                verify_release_tree(root)
            media.write_bytes(b"synthetic self-hosted release bytes" * 12)
            (root / ".env").write_text("NOT_A_REAL_SECRET=fixture")
            self.write_manifest(root)
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "hidden"):
                verify_release_tree(root)
            (root / ".env").unlink()
            self.write_manifest(root)
            (root / "unlisted-extra.txt").write_text("outside proof inventory")
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "disagree"):
                verify_release_tree(root)
            (root / "unlisted-extra.txt").unlink()
            self.assertTrue(verify_release_tree(root)["verified"])

            record = json.loads(receipt.read_text())
            record["output"] = "/not-in-release/source.mp4"
            receipt.write_text(json.dumps(record))
            self.write_manifest(root)
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "external output"):
                verify_release_tree(root)

    def test_reject_linked_receipts_and_ambiguous_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, receipt = self.fixture(root)
            target = root / "receipt-copy.json"
            target.write_bytes(receipt.read_bytes())
            receipt.unlink()
            receipt.symlink_to(target)
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "Linked"):
                verify_release_tree(root)
            receipt.unlink()
            target.replace(receipt)
            self.write_manifest(root)
            evidence_file = root / "verified-release-evidence.json"
            record = json.loads(evidence_file.read_text())
            record["artifacts"].append(dict(record["artifacts"][0]))
            evidence_file.write_text(json.dumps(record))
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "Duplicated"):
                verify_release_tree(root)

    def test_forged_publication_receipts_cannot_pass_rewritten_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            media, receipt = self.fixture(root)
            fake_name = receipt.with_name("0" * 64 + ".json")
            receipt.rename(fake_name)
            self.write_manifest(root)
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "identity filename"):
                verify_release_tree(root)
            fake_name.rename(receipt)

            original = json.loads(receipt.read_text())
            changed_identity = json.loads(json.dumps(original))
            changed_identity["identity"]["node_id"] = "other-render"
            receipt.write_text(json.dumps(changed_identity))
            self.write_manifest(root)
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "identity filename"):
                verify_release_tree(root)

            changed_digest = json.loads(json.dumps(original))
            changed_digest["sha256"] = "f" * 64
            receipt.write_text(json.dumps(changed_digest))
            self.write_manifest(root)
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "media digest"):
                verify_release_tree(root)

            changed_bytes = json.loads(json.dumps(original))
            changed_bytes["bytes"] += 1
            receipt.write_text(json.dumps(changed_bytes))
            self.write_manifest(root)
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "media digest"):
                verify_release_tree(root)

            dangerous_tool = json.loads(json.dumps(original))
            dangerous_tool["identity"]["tool_id"] = "body.render\nSECRET=never-publish"
            receipt.write_text(json.dumps(dangerous_tool))
            self.write_manifest(root)
            with self.assertRaisesRegex(ReleaseArtifactIntegrityError, "attempt identity"):
                verify_release_tree(root)

            receipt.write_text(json.dumps(original))
            self.write_manifest(root)
            self.assertEqual(verify_release_tree(root)["source_bound_publication_receipts"], 1)



if __name__ == "__main__":
    unittest.main()
