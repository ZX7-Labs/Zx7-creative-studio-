"""Physical owner-custody multi-engine cut, adversarial source races and ABI."""
from __future__ import annotations
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_owned_edit import validate_owned_edit,render_verified_owned_edit
from studio_next.body_integration import body_catalog,validate_witness
from studio_next.durable_graph import DurableFilmGraph
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.media_vault import MediaVault,sha256_file


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "True original audio/video encoders needed for custody proof")
class TrueOwnerAttestedGenericEditorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        vault=MediaVault(self.root/"vault")
        cuts=[]
        for index,(color,frequency) in enumerate((("red",450),("blue",850))):
            path=self.root/f"actual_{index}.mp4"
            proc=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                "-nostdin","-y","-f","lavfi","-i",
                f"color=c={color}:s=160x90:r=24:d=0.75",
                "-f","lavfi","-i",
                f"sine=frequency={frequency}:sample_rate=48000:duration=0.75",
                "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",
                "-b:a","128k","-shortest",str(path)],
                capture_output=True,text=True,timeout=70)
            self.assertEqual(proc.returncode,0,proc.stderr)
            proof=vault.ingest(path,mime="video/mp4",rights="owner_supplied",
                 source_type="owner_upload",source_id=f"independent-camera-{index}",
                 evidence="Authenticated source material for true FFmpeg test",
                 owner_or_generator="test-owner")
            cuts.append({"id":f"take-{index}","source":path.name,
                "rights":"owner_supplied","audio":"preserve_source",
                "asset_id":proof["asset_id"],"attestation_id":proof["attestation_id"]})
        self.plan={"format":{"width":160,"height":90,"fps":24,
               "framing":"fit","background":"#030508"},"clips":cuts}
        self.plan_file=self.root/"director-edit.json"
        self.write_plan()
    def tearDown(self):
        self.tmp.cleanup()
    def write_plan(self):
        self.plan_file.write_text(json.dumps(self.plan),encoding="utf-8")
    def test_real_picture_sound_custody_and_independent_installed_tool(self):
        old=[sha256_file(self.root/c["source"]) for c in self.plan["clips"]]
        body=body_catalog(self.root)
        self.assertEqual({x["id"]:x for x in body.discover()}[
            "body.render_edit_owned"]["status"],"installed")
        actual=body.trusted_material_fingerprint("body.render_edit_owned",
             {"edit":"director-edit.json","out":"original-owner-final.mp4"})
        self.assertEqual({x["sha256"] for x in actual},
                         set(old+[sha256_file(self.plan_file)]))
        output=body.invoke("body.render_edit_owned",
                 {"edit":"director-edit.json","out":"original-owner-final.mp4"},
                 allowed_access={"write"})
        self.assertTrue(validate_witness("body.render_edit_owned",output))
        self.assertEqual(output["source_custody_count"],2)
        self.assertEqual(output["distinct_originals"],2)
        self.assertTrue(output["full_picture_and_sound_decoder_completed"])
        self.assertEqual([sha256_file(self.root/c["source"]) for c in self.plan["clips"]],old)
        movie=self.root/"original-owner-final.mp4"
        decoded=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
            "-xerror","-i",str(movie),"-map","0:v:0","-map","0:a:0",
            "-f","null","-"],capture_output=True,timeout=40)
        self.assertEqual(decoded.returncode,0,decoded.stderr)
        self.assertTrue(movie.is_file())
        with self.assertRaises(FileExistsError):
            body.invoke("body.render_edit_owned",
                 {"edit":"director-edit.json","out":"original-owner-final.mp4"},
                 allowed_access={"write"})
    def test_exact_owned_cas_render_recovery_reuses_physical_original_without_reencoding(self):
        from studio_next.body_publication import physical_tool_attempt
        body=body_catalog(self.root)
        args={"edit":"director-edit.json","out":"recovered-owner-final.mp4"}
        # A production publication receipt requires a real, currently owned
        # durable stage. A bare context-label is no longer publication authority.
        store=DurableFilmGraph(self.root/"owner-edit-lease.sqlite3")
        state,_,owner=store.start_or_reuse(
            "physical-project","artist-cut","exact-inputs",
            trusted_idempotent=True,
            existing_result_verifier=lambda _:True,
            lease_seconds=60)
        self.assertEqual(state,"execute")
        with physical_tool_attempt("physical-project","artist-cut","exact-inputs",
                                   "body.render_edit_owned",
                                   publication_guard=lambda:store.publication_lease(
                                       "physical-project","artist-cut","exact-inputs",
                                       owner,lease_seconds=60)):
            first=body.invoke("body.render_edit_owned",args,allowed_access={"write"})
            first_sha=first["sha256"]
            # Reopen the same physically verified master. Fail if any native
            # encoder is invoked again; this is not a mocked successful movie.
            with patch("studio_next.body_integration.render_verified_owned_edit",
                       side_effect=AssertionError("Identical accepted movie was re-encoded")):
                second=body.invoke("body.render_edit_owned",args,
                                   allowed_access={"write"})
        self.assertEqual(second["sha256"],first_sha)
        store.complete("physical-project","artist-cut","exact-inputs",owner,first)
        self.assertEqual(store.inspect("physical-project")[0]["status"],"completed")
        self.assertEqual(second["source_custody_count"],2)
        self.assertEqual(second["distinct_originals"],2)
        self.assertEqual(second["director_plan_sha256"],sha256_file(self.plan_file))
        self.assertTrue(validate_witness("body.render_edit_owned",second))
        self.assertFalse(list(self.root.glob(".zx7-uncommitted-*.mp4")))

    def test_model_claim_cannot_invent_licensed_original_or_wrong_sha(self):
        before=sha256_file(self.plan_file)
        for changes in (
            {"attestation_id":"fake-owner-certificate"},
            {"asset_id":"0"*64},
            {"rights":"appropriately_licensed"},
            {"source":"../unapproved.mp4"},
            {"model_command":"ffmpeg -y"}):
            with self.subTest(changes=changes):
                plan=copy.deepcopy(self.plan)
                plan["clips"][0].update(changes)
                self.plan_file.write_text(json.dumps(plan))
                with self.assertRaises((ValueError,TypeError)):
                    fingerprint_physical_inputs("body.render_edit_owned",
                        {"edit":"director-edit.json","out":"never.mp4"},self.root)
        self.write_plan()
        self.assertEqual(sha256_file(self.plan_file),before)
        raw=copy.deepcopy(self.plan)
        raw["clips"][0].pop("attestation_id")
        with self.assertRaises(ValueError):
            validate_owned_edit(raw,self.root,self.root/"vault")
    def test_actual_decoder_reads_read_only_private_cas_not_mutable_source(self):
        from studio_next import body_owned_edit
        original_run=subprocess.run
        invoked=[]
        first=self.root/"actual_0.mp4"
        expected=[sha256_file(self.root/c["source"]) for c in self.plan["clips"]]
        original=first.read_bytes()
        replacement=(self.root/"actual_1.mp4").read_bytes()

        def adversarial_source_swap(argv,**kwargs):
            if argv and argv[0]=="ffmpeg" and "-filter_complex" in argv:
                sources=[Path(argv[pos+1]) for pos,part in enumerate(argv[:-1])
                         if part=="-i"]
                self.assertEqual(len(sources),2)
                for source,digest in zip(sources,expected):
                    self.assertIn(".zx7-owned-sources-",str(source))
                    self.assertEqual(sha256_file(source),digest)
                    self.assertFalse(source.stat().st_mode & 0o222)
                invoked.extend(sources)
                first.write_bytes(replacement)
                try:
                    return original_run(argv,**kwargs)
                finally:
                    first.write_bytes(original)
            return original_run(argv,**kwargs)

        with patch.object(body_owned_edit.subprocess,"run",
                          side_effect=adversarial_source_swap):
            proof=render_verified_owned_edit(self.plan_file,self.root,
                         self.root/"vault",self.root/"sealed-cas-cinema.mp4")
        self.assertEqual(proof["source_custody_count"],2)
        self.assertTrue(proof["sealed_original_cas_during_decode"])
        self.assertTrue(proof["full_picture_and_sound_decoder_completed"])
        self.assertEqual(sha256_file(first),expected[0])
        self.assertEqual(sha256_file(self.root/"actual_1.mp4"),expected[1])
        self.assertTrue((self.root/"sealed-cas-cinema.mp4").is_file())
        self.assertEqual(len(invoked),2)
        self.assertTrue(all(not path.exists() for path in invoked))
        self.assertFalse(list(self.root.glob(".zx7-owned-sources-*")))

    def test_mutated_original_source_after_native_encode_never_published(self):
        from studio_next import body_owned_edit
        real_run=subprocess.run
        did=False
        def race(argv,**kwargs):
            nonlocal did
            result=real_run(argv,**kwargs)
            if not did and argv and argv[0]=="ffmpeg":
                did=True
                (self.root/"actual_0.mp4").write_bytes(b"changed during native encoder")
            return result
        with patch.object(body_owned_edit.subprocess,"run",side_effect=race):
            with self.assertRaisesRegex(ValueError,"changed while encoding"):
                render_verified_owned_edit(self.plan_file,self.root,
                     self.root/"vault",self.root/"never-accepted.mp4")
        self.assertTrue(did)
        self.assertFalse((self.root/"never-accepted.mp4").exists())
    def test_mutated_director_plan_after_native_encode_never_published(self):
        from studio_next import body_owned_edit
        real_run=subprocess.run
        did=False
        def race(argv,**kwargs):
            nonlocal did
            result=real_run(argv,**kwargs)
            if not did and argv and argv[0]=="ffmpeg":
                did=True
                self.plan_file.write_text("{}")
            return result
        with patch.object(body_owned_edit.subprocess,"run",side_effect=race):
            with self.assertRaisesRegex(ValueError,"changed while encoding"):
                render_verified_owned_edit(self.plan_file,self.root,
                    self.root/"vault",self.root/"blocked-plan.mp4")
        self.assertTrue(did)
        self.assertFalse((self.root/"blocked-plan.mp4").exists())

    def test_original_video_longer_than_recorded_sound_never_claims_preservation(self):
        muted=self.root/"long-camera-short-voice.mp4"
        actual=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
            "-nostdin","-y",
            "-f","lavfi","-i","color=c=purple:s=160x90:r=24:d=2",
            "-f","lavfi","-i","sine=frequency=480:sample_rate=48000:duration=1",
            "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",
            "-b:a","128k",str(muted)],capture_output=True,text=True,timeout=55)
        self.assertEqual(actual.returncode,0,actual.stderr)
        proof=MediaVault(self.root/"vault").ingest(
            muted,mime="video/mp4",rights="owner_supplied",
            source_type="owner_upload",source_id="incomplete-camera-microphone",
            evidence="Two seconds of physical picture, one recorded second",
            owner_or_generator="owner")
        one=copy.deepcopy(self.plan)
        one["clips"]=[{"id":"incomplete-recorded-scene","source":muted.name,
                       "rights":"owner_supplied","audio":"preserve_source",
                       "asset_id":proof["asset_id"],
                       "attestation_id":proof["attestation_id"]}]
        self.plan_file.write_text(json.dumps(one))
        output=self.root/"must-not-invent-dialogue.mp4"
        with self.assertRaisesRegex(ValueError,"soundtrack ends before the picture"):
            render_verified_owned_edit(self.plan_file,self.root,self.root/"vault",output)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.root.glob(".zx7-owned-sources-*")))

    def test_real_competing_master_cannot_be_overwritten_or_deleted_at_publication(self):
        import os
        from studio_next import body_owned_edit
        destination=self.root/"rival-owned-master.mp4"
        rival=self.root/"actual_1.mp4"
        rival_sha=sha256_file(rival)
        real_link=os.link
        raced=False
        def competitor_wins(src,dst,*args,**kwargs):
            nonlocal raced
            if Path(dst)==destination:
                self.assertIn(".zx7-owned-sources-",str(src))
                shutil.copyfile(rival,destination)
                raced=True
            return real_link(src,dst,*args,**kwargs)
        with patch.object(body_owned_edit.os,"link",side_effect=competitor_wins):
            with self.assertRaises(FileExistsError):
                render_verified_owned_edit(self.plan_file,self.root,
                                           self.root/"vault",destination)
        self.assertTrue(raced)
        self.assertEqual(sha256_file(destination),rival_sha)
        self.assertFalse(list(self.root.glob(".zx7-owned-sources-*")))
        decoded=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
            "-xerror","-i",str(destination),"-map","0:v:0","-map","0:a:0",
            "-f","null","-"],capture_output=True,timeout=40)
        self.assertEqual(decoded.returncode,0,decoded.stderr)


if __name__=="__main__":unittest.main()
