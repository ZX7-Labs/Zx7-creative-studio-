"""Independent geometry, animation, alpha and persisted native render controls."""
import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from studio_next.body_visual_graph import VisualGraph, VisualBudget, revision_impact
from studio_next.body_visual_contract import visual_graph_contract
from studio_next.test_body_visual_graph import field, plan, linear


def line(end):
    # Collinear control points at the destination are an exact straight segment.
    return {"control1": end, "control2": end, "end": end}


def rectangle(x0, y0, x1, y1, *, reverse=False):
    points = [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
    if reverse: points.reverse()
    return {"start":points[0], "segments":[line(p) for p in points[1:]]}


def masked(contours, *, rule="evenodd", invert=False, frames=8):
    return plan([field("paint","1","0","0",".5"),
        {"id":"cutout","op":"path_mask","inputs":{"image":"paint"},
         "params":{"contours":contours,"fill_rule":rule,"invert":invert}}],
        width=32,height=24,frames=frames)


@unittest.skipUnless(importlib.util.find_spec("numpy"), "Native NumPy required")
class EditablePathMaskTests(unittest.TestCase):
    def test_fractional_rectangle_preserves_associated_alpha(self):
        import numpy as np
        doc=masked([rectangle(2.5,3,12,14)])
        a=VisualGraph(doc).frame(0)
        self.assertEqual(float(a[4,1,3]),0)
        self.assertEqual(float(a[4,2,3]),.25)
        np.testing.assert_array_equal(a[4,3],[.5,0,0,.5])
        np.testing.assert_array_equal(a[...,0],a[...,3])
        self.assertAlmostEqual(float(a[...,3].sum()),9.5*11*.5)

    def test_holes_and_inversion_are_explicit(self):
        import numpy as np
        outside=rectangle(2,2,20,20); inside=rectangle(6,6,12,12)
        even=VisualGraph(masked([outside,inside])).frame(0)
        same=VisualGraph(masked([outside,inside],rule="nonzero")).frame(0)
        opposed=VisualGraph(masked([outside,rectangle(6,6,12,12,reverse=True)],rule="nonzero")).frame(0)
        inverse=VisualGraph(masked([outside,inside],invert=True)).frame(0)
        self.assertEqual(float(even[8,8,3]),0)
        self.assertEqual(float(same[8,8,3]),.5)
        np.testing.assert_array_equal(even,opposed)
        np.testing.assert_allclose(even[...,3]+inverse[...,3],.5)

    def test_cubic_curves_and_original_clock(self):
        import numpy as np
        # Symmetric cubic arch, y(t)=3+27t(1-t), x(t)=2+18t.
        contour={"start":[2,3],"segments":[{"control1":[8,12],"control2":[14,12],"end":[20,3]}]}
        doc=masked([contour]); a=VisualGraph(doc).frame(0)
        # Area under the exact parametric parabola, independently computed.
        self.assertAlmostEqual(float(a[...,3].sum()),18*27/6*.5,delta=.5)
        self.assertGreater(float(a[7,11,3]),.49)
        self.assertEqual(float(a[10,11,3]),0)
        shift=rectangle(linear(2,10),3,linear(6,14),8)
        moving=masked([shift]); g=VisualGraph(moving)
        self.assertEqual(tuple(np.argwhere(g.frame(0)[...,3]>.49)[0]),(3,2))
        self.assertEqual(tuple(np.argwhere(g.frame(7)[...,3]>.49)[0]),(3,10))
        after=copy.deepcopy(moving); after['nodes'][1]['params']['invert']=True
        self.assertEqual(revision_impact(moving,after)['changed_or_dependent_nodes'],['cutout'])

    def test_bad_geometry_and_resource_limits_refused(self):
        base=masked([rectangle(1,1,10,10)])
        for key,value in (("fill_rule","guess"),("invert",1),("contours",[])):
            b=copy.deepcopy(base);b['nodes'][1]['params'][key]=value
            with self.assertRaises(ValueError):VisualGraph(b)
        b=copy.deepcopy(base);b['nodes'][1]['params']['contours'][0]['start']=[1e8,0]
        with self.assertRaises(ValueError):VisualGraph(b).frame(0)
        with self.assertRaisesRegex(ValueError,'budget'):VisualGraph(base,budget=VisualBudget(max_expression_work=100))
        b=copy.deepcopy(base);b['nodes'][1]['params']['contours'][0]['segments']=[line([1,2])]*513
        with self.assertRaises(ValueError):VisualGraph(b)
        schema=visual_graph_contract()
        import jsonschema
        jsonschema.validate(base,schema)

    def test_animated_mask_real_mov_and_excerpt_pixel_equality(self):
        from studio_next.body_visual_render import render_visual_graph
        import json
        import shutil
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("Real FFmpeg required")
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            doc=masked([rectangle(linear(2,10),3,linear(6,14),8)])
            doc["render"].update(format="rgba_mov",frame_count=8)
            path=root/"motion.json";path.write_text(json.dumps(doc))
            full=render_visual_graph(path,root,root/"vault",root/"full.mov")
            self.assertTrue(full["decoded_rgba_exact"])
            self.assertEqual(len(set(full["rendered_frame_pixel_sha256"])),8)
            doc["render"].update(first_frame=3,frame_count=3)
            path.write_text(json.dumps(doc))
            cut=render_visual_graph(path,root,root/"vault",root/"cut.mov")
            self.assertEqual(cut["rendered_frame_pixel_sha256"],full["rendered_frame_pixel_sha256"][3:6])
            self.assertEqual(cut["original_first_frame"],3)

    def test_persisted_native_graph_png_revision_preserves_original(self):
        from studio_next.body_visual_document import author_visual_document,read_visual_document
        from studio_next.body_visual_render import render_visual_graph
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve(); doc=masked([rectangle(2.5,3,12,14)])
            out='creative-graphs/original.json'
            first=author_visual_document(root,document=doc,out=out)
            old=(root/out).read_bytes()
            observed=read_visual_document(root,plan=out)
            self.assertEqual(observed['graph'],doc)
            render_visual_graph(root/out,root,root/'vault',root/'original.png')
            revised=copy.deepcopy(doc);revised['nodes'][1]['params']['contours']=[rectangle(10,3,20,14)]
            author_visual_document(root,document=revised,out='creative-graphs/child.json',base=out,expected_sha256=observed['sha256'])
            render_visual_graph(root/'creative-graphs/child.json',root,root/'vault',root/'child.png')
            self.assertEqual((root/out).read_bytes(),old)
            with Image.open(root/'original.png') as im:
                self.assertEqual(im.getpixel((2,4)),(255,0,0,64))
                self.assertEqual(im.getpixel((4,4)),(255,0,0,128))
            with Image.open(root/'child.png') as im:self.assertEqual(im.getpixel((4,4))[3],0)
