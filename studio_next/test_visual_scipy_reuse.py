"""Differential native SciPy vs existing NumPy original-image semantics.

Tests require the explicitly installed optional visual_acceleration extra.
They verify numerical semantics and actual PNG outputs, not artistic quality.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from studio_next.body_visual_graph import VisualGraph, _convolve, rgba8
from studio_next.body_visual_render import render_visual_graph


@unittest.skipUnless(importlib.util.find_spec("scipy") is not None,
                     "Explicit optional SciPy native engine is required")
class SciPyNativeReuseTests(unittest.TestCase):
    def test_native_signed_asymmetric_kernels_match_prior_numpy_edges_and_alpha(self):
        import numpy as np
        rng=np.random.default_rng(2217)
        for shape in ((1,1,4),(1,7,4),(7,1,4),(13,17,4),(47,37,4)):
            rgba=rng.random(shape,dtype=np.float32)
            unchanged=rgba.copy()
            # An asymmetric and signed kernel catches accidental correlation
            # instead of actual convolution; arbitrary kernels are artist data.
            for kernels in (([1],[1]),([1,2,1],[1,2,1]),
                            ([.125,-.25,.5,1.,.75],[.2,.4,.8]),
                            ([1/63]*63,[1/31]*31)):
                for border in ("transparent","clamp","wrap"):
                    with self.subTest(shape=shape,kernels=(
                            len(kernels[0]),len(kernels[1])),border=border):
                        baseline=_convolve(rgba,kernels,border,backend="numpy")
                        accelerated=_convolve(rgba,kernels,border,backend="scipy")
                        self.assertEqual(accelerated.dtype,np.float32)
                        self.assertEqual(accelerated.shape,rgba.shape)
                        np.testing.assert_allclose(
                            accelerated,baseline,atol=3e-6,rtol=2e-6)
                        np.testing.assert_array_equal(
                            rgba,unchanged)  # no in-place native mutation

    def test_project_remains_native_and_native_scipy_is_explicit_only(self):
        import numpy as np
        document={
            "version":"zx7-visual-graph/1",
            "canvas":{"width":48,"height":32,
                      "frame_rate":{"numerator":24,"denominator":1},
                      "frames":1,"working_space":"linear_srgb"},
            "nodes":[
                {"id":"art","op":"expression","inputs":{},
                 "params":{"channels":{"r":"u","g":"v","b":"0.4","a":"1"},
                            "uniforms":{}}},
                {"id":"blur","op":"convolve","inputs":{"image":"art"},
                 "params":{"kernel_x":[1,4,6,4,1],
                           "kernel_y":[1,4,6,4,1],
                           "divisor":256,"border":"clamp"}}
            ],
            "output":"blur",
            "render":{"first_frame":0,"frame_count":1,
                      "format":"png","rgb_range":"clip_to_sdr",
                      "audio":"separate_tracks"},
        }
        original=VisualGraph(document)
        compiled=VisualGraph(document,convolution_backend="scipy")
        self.assertEqual(original.convolution_backend,"numpy")
        np.testing.assert_allclose(compiled.frame(0),original.frame(0),
                                   atol=3e-6,rtol=2e-6)
        original_png,_=rgba8(original.frame(0))
        sci_png,_=rgba8(compiled.frame(0))
        self.assertLessEqual(int(np.max(np.abs(
            original_png.astype(np.int16)-sci_png.astype(np.int16)))),1)
        with tempfile.TemporaryDirectory() as temp:
            from PIL import Image
            root=Path(temp)
            native=root/"editable-native-graph.json"
            native.write_text(json.dumps(document),encoding="utf-8")
            source=native.read_bytes()
            old=render_visual_graph(native,root,root/"vault",
                                    root/"numpy.png")
            new=render_visual_graph(
                native,root,root/"vault",root/"scipy.png",
                convolution_backend="scipy")
            self.assertEqual(native.read_bytes(),source)
            self.assertEqual(old["convolution_backend"],"numpy")
            self.assertEqual(new["convolution_backend"],"scipy")
            self.assertTrue(new["convolution_backend_runtime_version"])
            self.assertEqual(old["plan_sha256"],new["plan_sha256"])
            self.assertEqual(old["project_node_fingerprints"],
                             new["project_node_fingerprints"])
            with Image.open(old["path"]) as first,Image.open(new["path"]) as second:
                a=np.asarray(first.convert("RGBA"),dtype=np.int16)
                b=np.asarray(second.convert("RGBA"),dtype=np.int16)
                self.assertLessEqual(int(np.max(np.abs(a-b))),1)
            self.assertFalse(old["aesthetic_quality_approved"])
            self.assertFalse(new["aesthetic_quality_approved"])

    def test_unknown_backend_denied_before_render_creates_any_file(self):
        with self.assertRaisesRegex(ValueError,"Unsupported visual convolution"):
            _convolve(None,(), "clamp",backend="untrusted_model_code")
        with self.assertRaisesRegex(ValueError,"Unsupported visual convolution"):
            VisualGraph({},convolution_backend="remote-only")


if __name__=="__main__":
    unittest.main()
