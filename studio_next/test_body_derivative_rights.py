"""Physical visual derivative lineage: exact grants, not legal inference."""
import sqlite3
from contextlib import closing
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from studio_next.body_integration import run_body_project
from studio_next.media_vault import MediaVault, MediaCustodyError, sha256_file
from studio_next.test_body_visual_graph import field, plan


def owner(vault, path, identity):
    return vault.ingest(path, mime="image/png", rights="owner_supplied",
        source_type="owner_upload", source_id=identity, evidence="Owner grant",
        owner_or_generator="owner")


def derivative_ir(root, name, source, ref):
    nodes = [{"id":"photo","op":"source","inputs":{},"params":{
        "media":{"source":source.name,"asset_id":ref["asset_id"],
                 "attestation_id":ref["attestation_id"]},
        "kind":"image","color_space":"srgb","frame":0}},
        field("edit","photo_r*.5","photo_g","photo_b","1",inputs={"photo":"photo"})]
    (root/(name+".json")).write_text(json.dumps(plan(nodes,width=16,height=16)))
    ir={"project":{"creative_intent":"Real editable source revision "+name},
        "shots":[{"id":"image","purpose":"Actual source revision"}],
        "tool_graph":[{"id":"image","tool_id":"body.visual_graph","purpose":"Render",
            "inputs":{"plan":name+".json","out":name+".png"},"depends_on":[]},
            {"id":"custody","tool_id":"body.asset_vault","purpose":"Exact producer custody",
            "inputs":{"source_witness":{"$node_output":"image"}},"depends_on":["image"]}]}
    return ir


def derivative(root, vault, name, source, ref):
    ir=derivative_ir(root,name,source,ref)
    result=run_body_project(ir,root)
    if result["status"]!="all_tool_results_verified":raise AssertionError(result)
    output=root/(name+".png")
    record=vault.inspect(sha256_file(output))
    att=next(a for a in record["rights_attestations"] if a["source_type"]=="trusted_renderer")
    return output,{"asset_id":record["asset_id"],"attestation_id":att["attestation_id"]},ir


class PhysicalDerivativeRightsTests(unittest.TestCase):
    def test_transitive_visual_derivative_withdrawal_preserves_independent_grants(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home);vault=MediaVault(root/"vault")
            original=root/"photo.png";Image.new("RGBA",(16,16),(75,143,215,255)).save(original)
            a=owner(vault,original,"source-grant")
            alt=owner(vault,original,"independent-source-grant")
            first,b,ir=derivative(root,vault,"first",original,a)
            second,c,_=derivative(root,vault,"second",first,b)
            self.assertNotEqual(a["asset_id"],b["asset_id"])
            self.assertNotEqual(b["asset_id"],c["asset_id"])
            self.assertEqual(run_body_project(ir,root)["reused"],["image","custody"])
            independent=owner(vault,first,"separate-owner-derivative-grant")
            self.assertEqual(vault.checkout(c["asset_id"],c["attestation_id"],root/"before.png")["asset_id"],c["asset_id"])
            vault.withdraw_attestation(a["asset_id"],a["attestation_id"],reason="Source grant withdrawn")
            vault=MediaVault(root/"vault")
            for n,ref in (("first",b),("second",c)):
                with self.subTest(derivative=n), self.assertRaisesRegex(MediaCustodyError,"withdrawn"):
                    vault.checkout(ref["asset_id"],ref["attestation_id"],root/(n+"-denied.png"))
                self.assertFalse((root/(n+"-denied.png")).exists())
            self.assertEqual([x["attestation_id"] for x in vault.inspect(b["asset_id"])["rights_attestations"]],[independent["attestation_id"]])
            self.assertEqual(vault.inspect(a["asset_id"],attestation_id=alt["attestation_id"])["asset_id"],a["asset_id"])
            self.assertEqual(sha256_file(second),c["asset_id"])
            self.assertEqual(sha256_file(root/"before.png"),c["asset_id"])
            self.assertNotEqual(run_body_project(ir,root)["status"],"all_tool_results_verified")

    def test_ancestor_withdrawal_at_checkout_commit_refuses_new_link(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home);vault=MediaVault(root/"vault")
            original=root/"photo.png";Image.new("RGBA",(16,16),(80,143,215,255)).save(original)
            a=owner(vault,original,"source-grant")
            _,b,_=derivative(root,vault,"first",original,a)
            real=vault.inspect;calls=0
            def withdraw_at_boundary(*args,**kwargs):
                nonlocal calls
                result=real(*args,**kwargs);calls+=1
                if calls==2:vault.withdraw_attestation(a["asset_id"],a["attestation_id"],reason="Withdraw at link")
                return result
            with patch.object(vault,"inspect",side_effect=withdraw_at_boundary):
                with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):
                    vault.checkout(b["asset_id"],b["attestation_id"],root/"denied.png")
            self.assertFalse((root/"denied.png").exists())

    def test_recovery_retains_exact_source_grants_without_rerender(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home);vault=MediaVault(root/"vault")
            original=root/"photo.png";Image.new("RGBA",(16,16),(80,143,215,255)).save(original)
            a=owner(vault,original,"source-grant")
            ir=derivative_ir(root,"recovered",original,a)
            with patch("studio_next.durable_graph.DurableFilmGraph.complete",side_effect=OSError("Interrupted after physical publication")):
                failed=run_body_project(ir,root)
            self.assertNotEqual(failed["status"],"all_tool_results_verified")
            output=root/"recovered.png";digest=sha256_file(output)
            with patch("studio_next.body_integration.render_visual_graph",side_effect=AssertionError("Must recover exact prior bytes")):
                result=run_body_project(ir,root)
            self.assertEqual(result["status"],"all_tool_results_verified",result)
            record=vault.inspect(digest)["rights_attestations"][0]
            self.assertEqual(record["source_attestations"],[{"asset_id":a["asset_id"],"attestation_id":a["attestation_id"]}])
            vault.withdraw_attestation(a["asset_id"],a["attestation_id"],reason="Withdraw recovered source")
            with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):
                vault.checkout(digest,record["attestation_id"],root/"denied.png")
            self.assertEqual(sha256_file(output),digest)

    def test_missing_lineage_row_cannot_turn_derivative_into_independent_grant(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home);vault=MediaVault(root/"vault")
            original=root/"photo.png";Image.new("RGBA",(16,16),(80,143,215,255)).save(original)
            a=owner(vault,original,"source-grant")
            first,b,_=derivative(root,vault,"first",original,a)
            independent=owner(vault,first,"independent-owner-grant")
            with closing(sqlite3.connect(vault.db)) as db:
                db.execute("DELETE FROM attestation_lineage WHERE digest=? AND attestation_id=?",(b["asset_id"],b["attestation_id"]))
                db.commit()
            with self.assertRaisesRegex(MediaCustodyError,"lineage commitment"):
                vault.inspect(b["asset_id"],attestation_id=b["attestation_id"])
            self.assertEqual(vault.inspect(independent["asset_id"],attestation_id=independent["attestation_id"])["asset_id"],b["asset_id"])
