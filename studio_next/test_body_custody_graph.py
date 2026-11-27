"""Genuine ownership-preserving film DAG → decoded movie → CAS → restart proof.

This is an end-to-end chain, not mocked model-generated scene inference.
Every asset and publication starts from actual FFmpeg decoded owner footage.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio_next.body_integration import run_body_project,validate_witness
from studio_next.media_vault import MediaCustodyError,MediaVault,sha256_file


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real original MP4 and sound decoder required")
class OwnerAssetProductionGraphProof(unittest.TestCase):
    def test_rights_attested_edit_generated_master_cas_and_exact_restart_reuse(self):
        with tempfile.TemporaryDirectory() as workspace:
            root=Path(workspace)
            vault=MediaVault(root/"vault")
            clips=[]
            for k,(color,hz) in enumerate((("red",365),("blue",735))):
                media=root/f"owned-original-{k}.mp4"
                command=["ffmpeg","-hide_banner","-loglevel","error",
                    "-nostdin","-y","-f","lavfi","-i",
                    f"color=c={color}:s=160x90:r=24:d=0.6",
                    "-f","lavfi","-i",
                    f"sine=frequency={hz}:sample_rate=48000:duration=0.6",
                    "-c:v","libx264","-pix_fmt","yuv420p",
                    "-c:a","aac","-shortest",str(media)]
                run=subprocess.run(command,capture_output=True,text=True,timeout=60)
                self.assertEqual(run.returncode,0,run.stderr)
                proof=vault.ingest(media,mime="video/mp4",rights="owner_supplied",
                    source_type="owner_upload",source_id=f"original-creator-{k}",
                    evidence="Actually decoded owner-supplied original cinema source",
                    owner_or_generator="authenticated-original-owner")
                clips.append({"id":f"owner-shot-{k}","source":media.name,
                    "rights":"owner_supplied","audio":"preserve_source",
                    "asset_id":proof["asset_id"],"attestation_id":proof["attestation_id"]})
            edit={"format":{"width":160,"height":90,"fps":24,
                    "framing":"fit","background":"#141414"},"clips":clips}
            (root/"owner-edit.json").write_text(json.dumps(edit))
            ir={"project":{"creative_intent":"Independent rights-verified original footage"},
                "assets":[],"shots":[{"id":"scene","purpose":"Real owner-authored ordered mixed-source cut",
                            "duration_seconds":1.2}],
                "tool_graph":[
                    {"id":"movie","tool_id":"body.render_edit_owned",
                     "purpose":"Edit only explicitly attested original camera footage",
                     "inputs":{"edit":"owner-edit.json","out":"verified-original.mp4"},
                     "depends_on":[]},
                    {"id":"custody","tool_id":"body.asset_vault",
                     "purpose":"Store actually verified edited master and exact producer",
                     "inputs":{"source_witness":{"$node_output":"movie"}},
                     "depends_on":["movie"]}]}
            original_bytes=[sha256_file(root/x["source"]) for x in clips]
            first=run_body_project(ir,root)
            self.assertEqual(first["status"],"all_tool_results_verified",first)
            self.assertEqual(first["completed"],["movie","custody"])
            finished=root/"verified-original.mp4"
            actual=sha256_file(finished)
            proof=vault.inspect(actual)
            self.assertTrue(any(x["rights"]=="generated_original"
                                and x["source_type"]=="trusted_renderer"
                                for x in proof["rights_attestations"]))
            decoded=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                "-xerror","-i",str(finished),"-map","0:v:0","-map","0:a:0",
                "-f","null","-"],capture_output=True,timeout=45)
            self.assertEqual(decoded.returncode,0,decoded.stderr)
            second=run_body_project(ir,root)
            self.assertEqual(second["status"],"all_tool_results_verified",second)
            self.assertEqual(second["reused"],["movie","custody"])
            self.assertEqual(sha256_file(finished),actual)
            self.assertEqual([sha256_file(root/x["source"]) for x in clips],
                             original_bytes)
            invalid=copy.deepcopy(ir)
            invalid["tool_graph"][0]["tool_id"]="body.render_edit"
            with self.assertRaisesRegex(ValueError,"trusted renderer dependency"):
                run_body_project(invalid,root)
            self.assertEqual(sha256_file(finished),actual)
            master_grant=proof["rights_attestations"][0]["attestation_id"]
            descendant=vault.ingest(finished,mime="video/mp4",rights="generated_original",
                source_type="trusted_renderer",source_id="second-generation",
                evidence="Verified derivative of the master",owner_or_generator="trusted-renderer",
                parent_attestations=[(actual,master_grant)])
            vault.inspect(actual,attestation_id=descendant["attestation_id"])
            vault.withdraw_attestation(clips[0]["asset_id"],clips[0]["attestation_id"],
                                       reason="Withdraw exact input rights")
            reopened=MediaVault(root/"vault")
            with self.assertRaises(MediaCustodyError):
                reopened.inspect(actual,attestation_id=master_grant)
            with self.assertRaises(MediaCustodyError):
                reopened.inspect(actual)
            with self.assertRaises(MediaCustodyError):
                reopened.checkout(actual,master_grant,root/"denied.mp4")
            with self.assertRaises(MediaCustodyError):
                reopened.inspect(actual,attestation_id=descendant["attestation_id"])
            with self.assertRaises(MediaCustodyError):
                reopened.ingest(finished,mime="video/mp4",rights="generated_original",
                    source_type="trusted_renderer",source_id="denied-generation",
                    evidence="Attempted reuse of a withdrawn source",owner_or_generator="trusted-renderer",
                    parent_attestations=[(actual,master_grant)])
            self.assertNotEqual(run_body_project(ir,root)["status"],"all_tool_results_verified")
            self.assertFalse((root/"denied.mp4").exists())
            self.assertEqual(sha256_file(finished),actual)
            # Independent source rights are not withdrawn by association.
            reopened.inspect(clips[1]["asset_id"],attestation_id=clips[1]["attestation_id"])
            independent=reopened.ingest(finished,mime="video/mp4",rights="owner_supplied",
                source_type="owner_upload",source_id="separate-owner-grant",
                evidence="Independent authorization for identical bytes",
                owner_or_generator="authenticated-original-owner")
            self.assertEqual([x["attestation_id"] for x in reopened.inspect(actual)["rights_attestations"]],
                             [independent["attestation_id"]])
            reopened.checkout(actual,independent["attestation_id"],root/"allowed.mp4")
            self.assertEqual(sha256_file(root/"allowed.mp4"),actual)


    def test_derivative_admission_rechecks_parent_at_transaction_boundary(self):
        from unittest.mock import patch
        from studio_next.media_vault import verify_media_container
        with tempfile.TemporaryDirectory() as workspace:
            root=Path(workspace)
            vault=MediaVault(root/"vault")
            media=root/"source.mp4"
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i",
                "color=c=green:s=64x48:r=12:d=1","-c:v","libx264",
                "-pix_fmt","yuv420p",str(media)],check=True,timeout=40)
            parent=vault.ingest(media,mime="video/mp4",rights="owner_supplied",
                source_type="owner_upload",source_id="parent",evidence="Original",
                owner_or_generator="owner")
            refs=[(parent["asset_id"],parent["attestation_id"])]
            args=dict(mime="video/mp4",rights="generated_original",
                source_type="trusted_renderer",source_id="new-derivative",
                evidence="Trusted source-bound output",owner_or_generator="renderer",
                parent_attestations=refs)
            with self.assertRaisesRegex(MediaCustodyError,"Unknown derivative source"):
                vault.ingest(media,**{**args,"parent_attestations":[("0"*64,"1"*64)]})
            def decode_then_withdraw(path,mime):
                verify_media_container(path,mime)
                vault.withdraw_attestation(*refs[0],reason="Withdraw during validation")
            with patch("studio_next.media_vault.verify_media_container",side_effect=decode_then_withdraw):
                with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):
                    vault.ingest(media,**args)
            with self.assertRaises(MediaCustodyError):
                vault.inspect(parent["asset_id"])
            self.assertEqual(sha256_file(media),parent["asset_id"])


if __name__=="__main__":
    unittest.main()
