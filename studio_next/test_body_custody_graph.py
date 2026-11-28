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
from studio_next.media_vault import MediaVault,MediaCustodyError,sha256_file,canonical_source_attestations


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
            bound=next(x for x in proof["rights_attestations"] if x["source_type"]=="trusted_renderer")
            self.assertEqual(bound.get("source_attestations"),canonical_source_attestations([
                {k:clip[k] for k in ("asset_id","attestation_id")} for clip in clips]))
            self.assertEqual([sha256_file(root/x["source"]) for x in clips],
                             original_bytes)
            invalid=copy.deepcopy(ir)
            invalid["tool_graph"][0]["tool_id"]="body.render_edit"
            with self.assertRaisesRegex(ValueError,"trusted renderer dependency"):
                run_body_project(invalid,root)
            self.assertEqual(sha256_file(finished),actual)
            # Render a second-generation picture and sound master, then revoke one grant.
            # The fit/fill adapter can emit VFR; do not silently weaken the
            # lossless sound-only finishing contract to support this source.
            spec={"media":{"source":finished.name,"asset_id":actual,
                "attestation_id":bound["attestation_id"]},
                "ops":{"video_ops":[{"kind":"color_eq","brightness":.03,"contrast":1.1,
                    "saturation":1.1,"gamma":1}],"audio_ops":[{"kind":"gain","db":-6}]}}
            (root/"finish.json").write_text(json.dumps(spec))
            finishing={"project":{"creative_intent":"Independently selected picture grade and sound gain"},
                "shots":[{"id":"finish","purpose":"Original master picture and audio revision"}],
                "tool_graph":[{"id":"film","tool_id":"body.film_finish","purpose":"Native finish",
                    "inputs":{"plan":"finish.json","out":"finished-master.mp4"},"depends_on":[]},
                    {"id":"custody","tool_id":"body.asset_vault","purpose":"Keep source grants",
                    "inputs":{"source_witness":{"$node_output":"film"}},"depends_on":["film"]}]}
            done=run_body_project(finishing,root)
            self.assertEqual(done["status"],"all_tool_results_verified",done)
            master=root/"finished-master.mp4";master_id=sha256_file(master)
            master_grant=vault.inspect(master_id)["rights_attestations"][0]
            self.assertEqual(master_grant.get("source_attestations"),[
                {"asset_id":actual,"attestation_id":bound["attestation_id"]}])
            self.assertEqual(run_body_project(finishing,root)["reused"],["film","custody"])
            vault.withdraw_attestation(clips[0]["asset_id"],clips[0]["attestation_id"],reason="Withdraw first source")
            vault=MediaVault(root/"vault")
            for digest,grant in ((actual,bound),(master_id,master_grant)):
                with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):
                    vault.checkout(digest,grant["attestation_id"],root/"denied.mp4")
            self.assertFalse((root/"denied.mp4").exists())
            self.assertEqual(sha256_file(master),master_id)
            self.assertEqual(vault.inspect(clips[1]["asset_id"],attestation_id=clips[1]["attestation_id"])["asset_id"],clips[1]["asset_id"])


if __name__=="__main__":
    unittest.main()
