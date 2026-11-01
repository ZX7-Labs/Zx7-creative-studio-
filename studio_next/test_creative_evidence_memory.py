"""Persistent memory contract: real observed film, no fictional training claims."""
from __future__ import annotations

import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from .creative_evidence_memory import CreativeEvidenceMemory, EvidenceMemoryError
from .reference_evidence_tools import inspect_authorized_reference


class CreativeEvidenceMemoryTests(unittest.TestCase):
    def _movie(self, root):
        movie = root / "reference.mp4"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=s=160x90:r=24:d=3",
            "-f", "lavfi", "-i", "sine=frequency=310:duration=3",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-c:a", "aac", str(movie)],
            check=True, timeout=45)
        return movie

    def test_real_observation_deduplicated_persistent_and_checked(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            self._movie(root)
            report = inspect_authorized_reference(root, "reference.mp4", bins=20)
            db = root / "memory.sqlite3"
            memory = CreativeEvidenceMemory(db, max_compressed_bytes=4096*4)
            first = memory.store(report)
            repeated = memory.store(report)
            self.assertEqual(first["id"], repeated["id"])
            self.assertFalse(first["deduplicated"])
            self.assertTrue(repeated["deduplicated"])
            self.assertEqual(memory.recall(first["id"]), report)
            self.assertEqual(memory.usage()["records"], 1)
            self.assertLess(first["compressed_bytes"],
                            len(str(report).encode("utf-8")))
            memory.close()
            reopened = CreativeEvidenceMemory(db)
            self.assertEqual(reopened.recall(first["id"]), report)
            reopened.db.execute("UPDATE evidence SET compressed=? WHERE id=?",
                                (b"malformed", first["id"]))
            reopened.db.commit()
            with self.assertRaises(EvidenceMemoryError):
                reopened.recall(first["id"])
            reopened.close()

    def test_quota_and_invalid_evidence_fail_closed(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            self._movie(root)
            report = inspect_authorized_reference(root, "reference.mp4", bins=32)
            memory = CreativeEvidenceMemory(root / "memory.sqlite3",
                                            max_compressed_bytes=4096)
            other = dict(report)
            other["schema"] = "invented"
            with self.assertRaises(EvidenceMemoryError):
                memory.store(other)
            with self.assertRaises(EvidenceMemoryError):
                memory.store({"schema":"ZX7_AUTHORIZED_REFERENCE_GRAPH_V1"})
            # An intentionally small host budget rejects new evidence rather
            # than evicting or deleting any previous research case.
            large = dict(report)
            large["original_arbitrary_blob"] = "".join(
                chr((i*8191) % 0x10ffff) for i in range(2800)
                if (i*8191)%0x10ffff not in range(0xD800,0xE000))
            with self.assertRaises(EvidenceMemoryError):
                memory.store(large)
            self.assertEqual(memory.usage()["records"], 0)
            memory.close()


if __name__ == "__main__":
    unittest.main()
