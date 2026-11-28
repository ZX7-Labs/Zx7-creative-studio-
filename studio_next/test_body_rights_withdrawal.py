"""Exact owner-authorized attestation withdrawal, not deletion of media history."""
import io
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from studio_next.media_vault import MediaVault, MediaCustodyError
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.body_service import LocalBodyCoordinator, make_body_http_handler
from studio_next.body_client import ZX7BodyClient


def ingest(vault,path,source_id="original"):
    return vault.ingest(path,mime="application/octet-stream",rights="owner_supplied",
        source_type="owner_upload",source_id=source_id,evidence="Owner original",
        owner_or_generator="owner")


class ExactRightsWithdrawalTests(unittest.TestCase):
    def test_restart_preserves_withdrawal_and_other_attestation_on_same_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/"original.bin";source.write_bytes(b"original-owner-data")
            vault=MediaVault(root/"vault");first=ingest(vault,source);second=ingest(vault,source,"other-grant")
            digest=first["asset_id"];identity=first["attestation_id"]
            receipt=vault.withdraw_attestation(digest,identity,reason="License withdrawn")
            self.assertTrue(receipt["withdrawn"]);self.assertFalse(receipt["historical_copies_deleted"])
            reopened=MediaVault(root/"vault")
            self.assertEqual(reopened.withdraw_attestation(digest,identity,reason="License withdrawn"),receipt)
            with self.assertRaises(MediaCustodyError):reopened.withdraw_attestation(digest,identity,reason="Rewritten history")
            with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):reopened.inspect(digest,attestation_id=identity)
            with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):ingest(reopened,source)
            dest=root/"denied.bin"
            with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):reopened.checkout(digest,identity,dest)
            self.assertFalse(dest.exists())
            self.assertEqual([x["attestation_id"] for x in reopened.inspect(digest)["rights_attestations"]],[second["attestation_id"]])
            self.assertEqual(Path(reopened.inspect(digest)["path"]).read_bytes(),source.read_bytes())
            with closing(sqlite3.connect(reopened.db)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM attestations").fetchone()[0],2)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM withdrawn_attestations").fetchone()[0],1)
            reopened.withdraw_attestation(digest,second["attestation_id"],reason="Second grant withdrawn")
            with self.assertRaises(MediaCustodyError):reopened.inspect(digest)

    def test_legacy_and_machine_neutral_exact_references_fail_preflight_after_withdrawal(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/"original.bin";source.write_bytes(b"licensed source")
            vault=MediaVault(root/"vault");ref=ingest(vault,source)
            for name,path in (("legacy","original.bin"),("neutral","zx7:sha256:"+ref["asset_id"])):
                (root/(name+".json")).write_text(json.dumps({"media":{"source":path,
                    "asset_id":ref["asset_id"],"attestation_id":ref["attestation_id"]}}))
                before=fingerprint_physical_inputs("body.subtitle_delivery",{"plan":name+".json"},root)
                self.assertIn(ref["asset_id"],[x["sha256"] for x in before])
            vault.withdraw_attestation(ref["asset_id"],ref["attestation_id"],reason="Permission ended")
            for name in ("legacy","neutral"):
                with self.assertRaisesRegex(ValueError,"withdrawn"):
                    fingerprint_physical_inputs("body.subtitle_delivery",{"plan":name+".json"},root)

    def test_checkout_rechecks_withdrawal_at_exclusive_publication_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/"original.bin";source.write_bytes(b"owned source")
            vault=MediaVault(root/"vault");ref=ingest(vault,source)
            real=vault.inspect;reads=0
            def inspect_then_withdraw(*args,**kwargs):
                nonlocal reads
                result=real(*args,**kwargs);reads+=1
                if reads==2:
                    vault.withdraw_attestation(ref["asset_id"],ref["attestation_id"],reason="Owner revoked at copy boundary")
                return result
            with patch.object(vault,"inspect",side_effect=inspect_then_withdraw):
                with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):
                    vault.checkout(ref["asset_id"],ref["attestation_id"],root/"checkout.bin")
            self.assertFalse((root/"checkout.bin").exists())
            self.assertFalse(list(root.glob(".zx7-vault-checkout-*")))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"Actual video tools required")
    def test_withdrawn_exact_source_blocks_new_and_cached_native_delivery(self):
        from studio_next.body_integration import run_body_project,body_catalog
        from studio_next.body_archive import create_body_archive,restore_body_archive
        with tempfile.TemporaryDirectory() as temp:
            outer=Path(temp);root=outer/"film";root.mkdir();source=root/"original.mp4"
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","color=c=blue:s=64x48:r=12:d=1",
                "-c:v","libx264","-pix_fmt","yuv420p",str(source)],check=True,timeout=40)
            vault=MediaVault(root/"vault");ref=vault.ingest(source,mime="video/mp4",rights="owner_supplied",
                source_type="owner_upload",source_id="licensed-original",evidence="Actual fixture",owner_or_generator="owner")
            plan={"media":{"source":"original.mp4","asset_id":ref["asset_id"],"attestation_id":ref["attestation_id"]},
                "tracks":[{"language":"eng","default":True,"cues":[{"start_ms":100,"end_ms":800,"text":"Original caption"}]}]}
            (root/"plan.json").write_text(json.dumps(plan))
            graph={"project":{"creative_intent":"Owner fixture"},"shots":[{"id":"shot","purpose":"Rights control"}],
                "tool_graph":[{"id":"caption","tool_id":"body.subtitle_delivery","purpose":"Actual native caption",
                "inputs":{"plan":"plan.json","out":"approved.mp4"},"depends_on":[]}]}
            before=run_body_project(graph,root);self.assertEqual(before["status"],"all_tool_results_verified",before)
            movie=(root/"approved.mp4").read_bytes()
            vault.withdraw_attestation(ref["asset_id"],ref["attestation_id"],reason="Owner withdrew original grant")
            after=run_body_project(graph,root)
            self.assertNotEqual(after["status"],"all_tool_results_verified",after)
            self.assertNotIn("caption",after.get("reused",[]));self.assertEqual((root/"approved.mp4").read_bytes(),movie)
            with self.assertRaisesRegex(ValueError,"withdrawn"):
                body_catalog(root).invoke("body.subtitle_delivery",{"plan":"plan.json","out":"denied.mp4"},allowed_access={"read","write"})
            self.assertFalse((root/"denied.mp4").exists())
            backup=outer/"backup.tar.gz";receipt=create_body_archive(root,backup)
            root.rename(outer/"original-preserved");restored=root
            restore_body_archive(backup,restored,expected_sha256=receipt["sha256"])
            with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):
                MediaVault(restored/"vault").inspect(ref["asset_id"],attestation_id=ref["attestation_id"])

    def test_owner_service_auth_and_idle_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            entered=threading.Event();release=threading.Event()
            def execute(ir,workspace):
                entered.set()
                if not release.wait(5):raise RuntimeError("test executor not released")
                return {"status":"all_tool_results_verified"}
            owner=LocalBodyCoordinator(temp,execute=execute)
            token="local-owner-"+"a"*48
            server=ThreadingHTTPServer(("127.0.0.1",0),make_body_http_handler(owner,token))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            endpoint=f"http://127.0.0.1:{server.server_port}"
            client=ZX7BodyClient(endpoint=endpoint,token=token)
            try:
                data=b"Original license control bytes"
                ref=owner.upload_owner_media("film","source.bin",io.BytesIO(data),len(data),mime="application/octet-stream",source_id="owner-original",rights_evidence="Original licensed material")
                args=("film",ref["asset_id"],ref["attestation_id"])
                bad=ZX7BodyClient(endpoint=endpoint,token="not-owner-"+"b"*48)
                with self.assertRaisesRegex(RuntimeError,"401"):bad.withdraw_attestation(*args,reason="Not authorized")
                plan={"project":{"creative_intent":"Fixture"},"shots":[],"tool_graph":[]}
                owner.submit(plan,workspace_id="film",job_id="active")
                self.assertTrue(entered.wait(3))
                with self.assertRaisesRegex(RuntimeError,"active"):
                    client.withdraw_attestation(*args,reason="Owner request")
                release.set();self.assertEqual(client.wait("active",poll_seconds=.1,max_seconds=5)["status"],"completed")
                receipt=client.withdraw_attestation(*args,reason="Owner request")
                self.assertTrue(receipt["withdrawn"])
                self.assertEqual(receipt["scope"],"current_vault_exact_attestation_future_admissions")
                with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):
                    MediaVault(owner._workspace("film")/"vault").inspect(args[1],attestation_id=args[2])
                self.assertEqual((owner._workspace("film")/"source.bin").read_bytes(),data)
            finally:
                release.set();server.shutdown();server.server_close();thread.join(timeout=5);owner.close()
