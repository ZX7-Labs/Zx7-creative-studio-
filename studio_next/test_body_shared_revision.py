"""CAS decoder implementation changes must invalidate every affected exact render stage."""
import shutil
import tempfile
from collections import Counter
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_integration import _trusted_body_revision, body_catalog

SEALED_RENDER_TOOLS=(
    "body.retime","body.sequence_cuts","body.timeline_revision",
    "body.otio_owned_export","body.otio_owned_import",
    "body.composite_mix","body.film_finish","body.color_lut",
    "body.loudness","body.subtitle_delivery"
)
COMPLETE_DECODE_RENDER_TOOLS=(
    "body.render_edit_owned","body.retime","body.sequence_cuts",
    "body.timeline_revision","body.composite_mix","body.film_finish",
    "body.color_lut"
)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                    "Versioned real codec and probe binaries required")
class SharedSourceCodecRevisionProof(unittest.TestCase):
    def _assert_native_cache_invalidation(self,name,codec_module):
        original=_trusted_body_revision(name)
        real=Path.read_bytes
        def altered(path):
            content=real(path)
            if path.name==codec_module:
                return content+b"\n# changed shared native source verification ABI\n"
            return content
        with patch.object(Path,"read_bytes",altered):
            invalidated=_trusted_body_revision(name)
        self.assertNotEqual(original,invalidated,
            name+" would replay a stale previously verified movie after "+codec_module+" changed")

    def test_every_shared_cas_reader_change_invalidates_associated_editor_and_sound(self):
        for tool in SEALED_RENDER_TOOLS:
            with self.subTest(tool=tool):
                self._assert_native_cache_invalidation(tool,"composite_mix.py")

    def test_critical_full_decoder_change_invalidates_exact_native_witnesses(self):
        for tool in COMPLETE_DECODE_RENDER_TOOLS:
            with self.subTest(tool=tool):
                self._assert_native_cache_invalidation(tool,"production_qc.py")

class CatalogRevisionSnapshotProof(unittest.TestCase):
    def test_shared_source_fingerprinted_once_per_catalog_and_never_across_catalogs(self):
        real = Path.read_bytes
        reads = Counter()
        changed = False

        def instrument(path):
            data = real(path)
            if path.name == "body_publication.py":
                reads[path.name] += 1
                if changed:
                    data += b"\n# changed trusted publication source\n"
            return data

        with tempfile.TemporaryDirectory() as root, patch.object(Path, "read_bytes", instrument):
            first = body_catalog(root, initialize_vault=False).committed_tool_revisions()
            self.assertGreater(len(first), 1)
            self.assertEqual(reads["body_publication.py"], 1)
            changed = True
            second = body_catalog(root, initialize_vault=False).committed_tool_revisions()
            self.assertEqual(reads["body_publication.py"], 2)
            self.assertEqual(first.keys(), second.keys())
            self.assertNotEqual(first["body.timecode_format"], second["body.timecode_format"])
            self.assertEqual(second["body.timecode_format"], _trusted_body_revision("body.timecode_format"))

    def test_catalog_fingerprints_equal_independent_original_per_tool_hashes(self):
        with tempfile.TemporaryDirectory() as root:
            revisions = body_catalog(root, initialize_vault=False).committed_tool_revisions()
            for name in ("body.timecode_format", "body.resolve_asset", "body.voice_inventory", "body.visual_author"):
                with self.subTest(name=name):
                    if name in revisions:
                        self.assertEqual(revisions[name], _trusted_body_revision(name))


if __name__=="__main__":
    unittest.main()
