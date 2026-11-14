"""Model-authored editable visual graph projects: source, safety and physical pixels.

Contract-first. The installed BODY validates creative *data*, never executes
model-generated Python/JS. All work remains inside one authorized workspace.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from studio_next.body_visual_document import (
    author_visual_document, read_visual_document,
)


def graph(red="u"):
    return {
        "version": "zx7-visual-graph/1",
        "canvas": {"width": 32, "height": 24,
                   "frame_rate": {"numerator": 24, "denominator": 1},
                   "frames": 16, "working_space": "linear_srgb"},
        "nodes": [{
            "id": "authored", "op": "expression", "inputs": {},
            "params": {"channels": {"r": red, "g": "v", "b": "0", "a": "1"},
                       "uniforms": {}},
        }],
        "output": "authored",
        "render": {"first_frame": 0, "frame_count": 1,
                   "format": "png", "rgb_range": "clip_to_sdr",
                   "audio": "separate_tracks"},
    }


class AuthoredGraphDocuments(unittest.TestCase):
    def test_create_read_and_revise_editable_native_graph_without_overwriting_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = graph()
            saved = author_visual_document(root, document=first,
                                           out="creative-graphs/shot-a.json")
            self.assertEqual(saved["kind"], "authored_native_visual_graph")
            self.assertEqual(saved["relative_path"], "creative-graphs/shot-a.json")
            path = root / saved["relative_path"]
            self.assertTrue(path.is_file() and not path.is_symlink())
            self.assertEqual(path.stat().st_mode & 0o077, 0)
            self.assertEqual((root / "creative-graphs").stat().st_mode & 0o077, 0)
            self.assertEqual(saved["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            read = read_visual_document(root, plan=saved["relative_path"])
            self.assertEqual(read["graph"], first)
            self.assertEqual(read["sha256"], saved["sha256"])
            old_bytes = path.read_bytes()
            second = graph("1-u")
            revised = author_visual_document(
                root, document=second,
                out="creative-graphs/shot-a-v2.json",
                base="creative-graphs/shot-a.json",
                expected_sha256=saved["sha256"])
            self.assertEqual(revised["previous"]["sha256"], saved["sha256"])
            self.assertEqual(read_visual_document(
                root, plan=revised["relative_path"])["graph"], second)
            self.assertEqual(path.read_bytes(), old_bytes)
            self.assertNotEqual(revised["sha256"], saved["sha256"])
            for bad in ("f" * 64, "", "bad", 10):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    author_visual_document(root, document=second,
                        out="creative-graphs/no-commit.json",
                        base="creative-graphs/shot-a.json",
                        expected_sha256=bad)
                self.assertFalse((root / "creative-graphs/no-commit.json").exists())

    def test_no_model_control_over_workspace_paths_or_existing_private_files(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root = Path(temp)
            config = root / "studio.json"
            config.write_text('{"secret":"do-not-read"}')
            with self.assertRaises(ValueError):
                read_visual_document(root, plan="studio.json")
            with self.assertRaises(ValueError):
                read_visual_document(root, plan="../studio.json")
            for name in ("studio.json", "../other.json",
                         "/tmp/malicious.json",
                         "creative-graphs/../studio.json",
                         "creative-graphs/.hidden.json",
                         "creative-graphs/nested/graph.json"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    author_visual_document(root, document=graph(), out=name)
            first = author_visual_document(
                root, document=graph(), out="creative-graphs/one.json")
            old = (root / first["relative_path"]).read_bytes()
            with self.assertRaises(FileExistsError):
                author_visual_document(
                    root, document=graph("1"), out="creative-graphs/one.json")
            self.assertEqual((root / first["relative_path"]).read_bytes(), old)
            self.assertIn("do-not-read", config.read_text())
            (root / "creative-graphs/fake.json").symlink_to(config)
            with self.assertRaises(ValueError):
                read_visual_document(root, plan="creative-graphs/fake.json")
            with self.assertRaises(ValueError):
                author_visual_document(
                    root, document=graph(), out="creative-graphs/fake.json")
            bad_root = Path(outside) / "redirect"
            bad_root.symlink_to(root / "creative-graphs", target_is_directory=True)
            # A redirected on-disk authoring directory must refuse, not follow.
            (root / "creative-graphs").rename(root / "backup")
            (root / "creative-graphs").symlink_to(bad_root, target_is_directory=True)
            with self.assertRaises(ValueError):
                author_visual_document(
                    root, document=graph(), out="creative-graphs/cross.json")

    def test_untrusted_expression_or_impossible_graph_denied_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for red in ('__import__("os").system("echo unsafe")', "1/0", "u*(",):
                with self.subTest(red=red), self.assertRaises(ValueError):
                    author_visual_document(
                        root, document=graph(red), out="creative-graphs/denied.json")
                self.assertFalse((root / "creative-graphs/denied.json").exists())
            too_large = graph()
            too_large["canvas"]["width"] = 999999999
            with self.assertRaises(ValueError):
                author_visual_document(
                    root, document=too_large, out="creative-graphs/denied.json")
            malformed = graph()
            malformed["nodes"][0]["params"]["arbitrary_host_code"] = "rm -rf"
            with self.assertRaises(ValueError):
                author_visual_document(
                    root, document=malformed, out="creative-graphs/denied.json")
            source = graph()
            source["nodes"] = [{"id": "media", "op": "source", "inputs": {},
                "params": {"media": {"source": "untrusted.png",
                                     "asset_id": "0" * 64, "attestation_id": "fake"},
                           "kind": "image", "color_space": "srgb", "frame": 0}}]
            source["output"] = "media"
            with self.assertRaises((ValueError, PermissionError)):
                author_visual_document(
                    root, document=source, out="creative-graphs/denied.json")
            self.assertFalse((root / "creative-graphs/denied.json").exists())

    def test_two_independent_writers_cannot_overwrite_one_editable_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def create(red):
                try:
                    return author_visual_document(
                        root, document=graph(red), out="creative-graphs/one.json")
                except FileExistsError:
                    return None
            with ThreadPoolExecutor(max_workers=2) as workers:
                results = list(workers.map(create, ("u", "1-u")))
            winners = [r for r in results if r]
            self.assertEqual(len(winners), 1)
            actual = read_visual_document(root, plan="creative-graphs/one.json")
            self.assertIn(actual["graph"], (graph("u"), graph("1-u")))
            self.assertEqual(actual["sha256"], winners[0]["sha256"])


class ModelVisibleAuthoringTool(unittest.IsolatedAsyncioTestCase):
    async def test_installed_body_creates_reads_and_physically_renders_authored_visual_project(self):
        import importlib.util
        import shutil
        if (not shutil.which("ffmpeg") or not shutil.which("ffprobe")
                or importlib.util.find_spec("numpy") is None
                or importlib.util.find_spec("PIL") is None):
            self.skipTest("Real pixel renderer and decoder not installed")
        from studio_next.body_capability_adapter import InstalledBodyAdapter
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = InstalledBodyAdapter(root, allowed_access=("read", "write"))
            names = {x.name for x in (await source.list_tools()).tools}
            self.assertTrue({"body.visual_author", "body.visual_document",
                             "body.visual_graph"}.issubset(names))
            doc = graph()
            created = await source.call_tool("body.visual_author", {
                "document": doc, "out": "creative-graphs/generated.json"})
            self.assertFalse(created.is_error)
            actual = json.loads(created.content[0].text)
            self.assertEqual(actual["relative_path"], "creative-graphs/generated.json")
            inspected = await source.call_tool("body.visual_document", {
                "plan": actual["relative_path"]})
            self.assertFalse(inspected.is_error)
            self.assertEqual(json.loads(inspected.content[0].text)["graph"], doc)
            rendered = await source.call_tool("body.visual_graph", {
                "plan": actual["relative_path"], "out": "generated.png"})
            self.assertFalse(rendered.is_error)
            with Image.open(root / "generated.png") as picture:
                self.assertEqual(picture.size, (32, 24))
                self.assertNotEqual(picture.getpixel((0, 0)),
                                    picture.getpixel((31, 23)))
            self.assertEqual(hashlib.sha256(
                (root / actual["relative_path"]).read_bytes()).hexdigest(),
                actual["sha256"])


if __name__ == "__main__":
    unittest.main()
