import json
import tempfile
import unittest
import struct
import zlib
import shutil
import importlib.util
from pathlib import Path
from unittest.mock import patch
from studio_next.body_integration import body_catalog,validate_witness,_require_authentic_generated_media_lineage,_commit_actual_body_output


def actual_rgb_png():
    # Genuine pixel data, IHDR/IDAT/IEND chunk CRC and deflate stream.
    def chunk(kind,payload):
        return (struct.pack(">I",len(payload))+kind+payload+
                struct.pack(">I",zlib.crc32(kind+payload)&0xffffffff))
    width,height=8,8
    pixels=b"".join(bytes([0])+b"".join(
        bytes((x*31%256,y*29%256,(x+y)*12%256))
        for x in range(width)) for y in range(height))
    return (bytes([137,80,78,71,13,10,26,10])+
            chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,2,0,0,0))+
            chunk(b"IDAT",zlib.compress(pixels))+chunk(b"IEND",b""))


class TrustedCreativeBodyToolTests(unittest.TestCase):
    def test_native_motion_is_not_advertised_when_required_python_renderer_is_missing(self):
        actual=importlib.util.find_spec
        with tempfile.TemporaryDirectory() as root:
            with patch("studio_next.body_integration.importlib.util.find_spec",
                       side_effect=lambda name:None if name=="PIL" else actual(name)):
                catalog=body_catalog(root)
            tools={x["id"]:x for x in catalog.discover()}
            self.assertEqual(tools["body.motion2d"]["status"],"needs_setup")
            self.assertNotIn("body.motion2d",catalog.executable_ids({"write"}))

    def test_true_apps_discovered_not_fake_installation(self):
        with tempfile.TemporaryDirectory() as root:
            c=body_catalog(root)
            tools={x["id"]:x for x in c.discover()}
            self.assertIn("body.inspect",tools)
            self.assertIn("body.render_edit",tools)
            self.assertIn("body.otio",tools)
            self.assertIn("body.vector_png",tools)
            self.assertIn("body.asset_vault",tools)
            self.assertNotIn("body.nonexistent",tools)
            self.assertEqual(tools["body.asset_vault"]["status"],"installed")

    def test_physical_media_witness_required_even_after_graph_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"artwork.png"
            p.write_bytes(actual_rgb_png())
            if importlib.util.find_spec("PIL") is None and not shutil.which("ffmpeg"):
                self.skipTest("Actual image decoder unavailable in contract-only runner")
            import hashlib
            result={"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
                    "bytes":p.stat().st_size}
            self.assertTrue(validate_witness("body.vector_png",result))
            p.write_bytes(b"not same artwork"*100)
            self.assertFalse(validate_witness("body.vector_png",result))

    def test_durable_movie_witness_rechecks_actual_physical_dimensions(self):
        # RED before this correction: the old verifier ignored recorded
        # width/height although _witness() persisted both. This test mocks
        # only the ffprobe boundary, never any source/rights/codec approval.
        import hashlib
        with tempfile.TemporaryDirectory() as root:
            movie=Path(root)/"trusted-output.mp4"
            movie.write_bytes(b"original-native-movie-payload"*64)
            physical={"duration_seconds":4.0,"width":1280,"height":720,
                      "audio_stream_present":True}
            receipt={"path":str(movie),
                     "sha256":hashlib.sha256(movie.read_bytes()).hexdigest(),
                     "duration_seconds":4.0,"width":1280,"height":720,
                     "audio_present":True}
            with patch("studio_next.body_integration._probe_details",
                       return_value=physical):
                self.assertTrue(validate_witness("body.render_edit_owned",receipt))
                for name,invalid in (("width",640),("height",360),
                                     ("duration_seconds",6.0),
                                     ("audio_present",False)):
                    with self.subTest(field=name):
                        self.assertFalse(validate_witness(
                            "body.render_edit_owned",{**receipt,name:invalid}))
                for missing in ("width","height","duration_seconds","audio_present"):
                    with self.subTest(missing=missing):
                        bad=dict(receipt)
                        del bad[missing]
                        self.assertFalse(validate_witness("body.render_edit_owned",bad))
                self.assertFalse(validate_witness(
                    "body.render_edit_owned",{**receipt,"duration_seconds":"forged"}))
                movie.write_bytes(movie.read_bytes()+b"tampered")
                self.assertFalse(validate_witness("body.render_edit_owned",receipt))

    def test_single_animated_body_discloses_unavailable_photoreal_gpu_renderer(self):
        with tempfile.TemporaryDirectory() as root:
            fake={"video_generation_options":[{
                "id":"wan21-t2v-13b","ready_for_independent_execution_trial":False}]}
            with patch("studio_next.body_integration.discover_local_generators",
                       return_value=fake):
                body=body_catalog(root)
            specs={x["id"]:x for x in body.discover()}
            self.assertIn("body.generate_video",specs)
            self.assertEqual(specs["body.generate_video"]["status"],"needs_setup")
            self.assertFalse("body.generate_video" in body.executable_ids({"write"}))
            self.assertNotIn("body.generate_video",body.trusted_idempotent_ids())

    def test_render_failure_never_leaves_a_fake_committed_movie(self):
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/"actual-movie.mp4"
            def broken(destination):
                destination.write_bytes(b"partial encoder bytes"*30)
                raise RuntimeError("actual GPU/Blender job crashed")
            with self.assertRaisesRegex(RuntimeError,"crashed"):
                _commit_actual_body_output(target,broken)
            self.assertFalse(target.exists())
            self.assertFalse(list(Path(root).glob(".zx7-uncommitted-*")))

    def test_only_completed_stage_is_atomically_published_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/"actual-movie.mp4"
            def successful(destination):
                destination.write_bytes(b"physically rendered bytes"*50)
            def measured(path):
                return {"path":str(path),"sha256":"real-stage-digest"}
            with patch("studio_next.body_integration._witness",side_effect=measured):
                with patch("studio_next.body_integration._verify_witness",return_value=True):
                    result=_commit_actual_body_output(target,successful)
                    self.assertEqual(result["path"],str(target))
                    self.assertTrue(target.exists())
                    with self.assertRaises(FileExistsError):
                        _commit_actual_body_output(target,successful)
            self.assertEqual(target.read_bytes(),b"physically rendered bytes"*50)

    @unittest.skipUnless(importlib.util.find_spec("PIL") or shutil.which("ffmpeg"),
                         "Requires a genuine decoded image backend")
    def test_late_directory_sync_error_preserves_already_published_original(self):
        # A backend or another editor might have accepted the final file
        # before the filesystem reported a late directory fsync failure.
        # Failure must not delete the public master or leave private stages.
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/"already-accepted.png"
            from studio_next.body_integration import _commit_actual_body_output
            def produce(stage):
                stage.write_bytes(actual_rgb_png())
            with patch("studio_next.body_integration.sync_published_file",
                       side_effect=OSError("simulated postlink durability failure")):
                with self.assertRaisesRegex(OSError,"postlink durability"):
                    _commit_actual_body_output(target,produce)
            self.assertTrue(target.is_file())
            from studio_next.media_vault import verify_media_container
            verify_media_container(target,"image/png")
            self.assertFalse(list(Path(root).glob(".zx7-uncommitted-*")))
            before=target.read_bytes()
            with self.assertRaises(FileExistsError):
                _commit_actual_body_output(target,produce)
            self.assertEqual(target.read_bytes(),before)

    def test_png_header_without_actual_pixels_is_never_a_real_artifact(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"fake-thumbnail.png"
            p.write_bytes(bytes([137,80,78,71,13,10,26,10])+b"x"*300)
            import hashlib
            fake={"path":str(p),
                  "sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
                  "bytes":p.stat().st_size}
            self.assertFalse(validate_witness("body.vector_png",fake))

    def test_model_cannot_issue_rights_certificate_for_arbitrary_file(self):
        original={"id":"old","tool_id":"body.asset_vault","depends_on":[],
                  "inputs":{"source":"found-online.mp4","rights":"generated_original",
                            "evidence":"trust me"}}
        with self.assertRaisesRegex(ValueError,"cannot invent license"):
            _require_authentic_generated_media_lineage({"tool_graph":[original]})
        fabricated={"id":"vault","tool_id":"body.asset_vault",
                    "depends_on":["inspect"],
                    "inputs":{"source_witness":{"$node_output":"inspect"}}}
        read={"id":"inspect","tool_id":"body.inspect",
              "inputs":{"source":"unauthorized.mp4"},"depends_on":[]}
        with self.assertRaisesRegex(ValueError,"trusted renderer dependency"):
            _require_authentic_generated_media_lineage(
                {"tool_graph":[read,fabricated]})
        legacy={"id":"edit","tool_id":"body.render_edit","inputs":{},
                "depends_on":[]}
        valid={"id":"vault","tool_id":"body.asset_vault",
               "depends_on":["edit"],
               "inputs":{"source_witness":{"$node_output":"edit"}}}
        with self.assertRaisesRegex(ValueError,"trusted renderer dependency"):
            _require_authentic_generated_media_lineage(
                {"tool_graph":[legacy,valid]})
        for untrusted in ("body.vector_png","body.film_thumbnail"):
            with self.subTest(tool=untrusted),self.assertRaisesRegex(
                    ValueError,"trusted renderer dependency"):
                _require_authentic_generated_media_lineage(
                    {"tool_graph":[{**legacy,"tool_id":untrusted},valid]})
        trusted={**legacy,"tool_id":"body.render_edit_owned"}
        self.assertIsNone(_require_authentic_generated_media_lineage(
            {"tool_graph":[trusted,valid]}))
        for real_cg in ("body.exr_passes","body.exr_checkpoint"):
            with self.subTest(real_cg=real_cg):
                original={**legacy,"tool_id":real_cg}
                self.assertIsNone(_require_authentic_generated_media_lineage(
                    {"tool_graph":[original,valid]}))
        for unapproved in ("body.aces2_preview","body.inspect",
                           "body.otio","body.render_edit"):
            with self.subTest(unapproved=unapproved):
                original={**legacy,"tool_id":unapproved}
                with self.assertRaisesRegex(ValueError,"trusted renderer dependency"):
                    _require_authentic_generated_media_lineage(
                        {"tool_graph":[original,valid]})

    def test_actual_png_witness_cannot_mint_generated_rights_by_direct_catalog_call(self):
        if importlib.util.find_spec("PIL") is None and not shutil.which("ffmpeg"):
            self.skipTest("Actual PNG decoder required to prove a genuine source witness")
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"real-original-graphic.png"
            path.write_bytes(actual_rgb_png())
            catalog=body_catalog(root)
            import hashlib
            actual={"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes":path.stat().st_size}
            self.assertTrue(validate_witness("body.vector_png",actual))
            with self.assertRaisesRegex(PermissionError,"verified durable producer DAG"):
                catalog.invoke("body.asset_vault",{"source_witness":actual},
                               allowed_access={"write"})
            from studio_next.media_vault import MediaVault,MediaCustodyError
            with self.assertRaises(MediaCustodyError):
                MediaVault(Path(root)/"vault").inspect(actual["sha256"])

    def test_no_model_supplied_shell_or_untrusted_media_rights(self):
        with tempfile.TemporaryDirectory() as root:
            c=body_catalog(root)
            with self.assertRaises(ValueError):
                c.invoke("body.asset_vault",{"source":"../../../private.mp4",
                    "mime":"video/mp4","rights":"found online",
                    "source_type":"licensed_library","source_id":"lie",
                    "evidence":"no","issuer":"model"},allowed_access={"write"})

if __name__=="__main__":unittest.main()
