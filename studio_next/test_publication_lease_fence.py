"""Original media publication lease fencing across native BODY renderers.

The controlled bytes below are only concurrency fixtures; they do not prove
picture, sound, final-delivery integrity or model creativity. Existing physical
Inkscape/FFmpeg process-death tests cover genuine decoded publication.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from studio_next.body_integration import _commit_actual_body_output
from studio_next.body_publication import (
    authorized_publication, physical_tool_attempt)
from studio_next.body_stage_lease import RunningStageHeartbeat
from studio_next.durable_graph import DurableFilmGraph, RecoveryBlocked


class OriginalPublicationLeaseFenceTests(unittest.TestCase):
    PROJECT = "original-film"
    NODE = "render-original"
    INPUT = "sha256-original-source"
    TOOL = "body.vector_png"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clock = [1000.0]
        self.store = DurableFilmGraph(
            self.root / "owner-ledger.sqlite3", clock=lambda: self.clock[0])

    def acquire(self, *, seconds=.2):
        status, _, owner = self.store.start_or_reuse(
            self.PROJECT,self.NODE,self.INPUT,
            trusted_idempotent=True,
            existing_result_verifier=lambda value: True,
            lease_seconds=seconds)
        self.assertEqual(status, "execute")
        return owner

    def _witness(self, path):
        data=Path(path).read_bytes()
        return {"path":str(Path(path).absolute()),
                "sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)}

    def _render_with_guard(self, owner, target, render):
        with patch("studio_next.body_integration._witness", self._witness), \
             patch("studio_next.body_integration._verify_witness",
                   lambda receipt: receipt["bytes"]>=100):
            with physical_tool_attempt(
                self.PROJECT,self.NODE,self.INPUT,self.TOOL,
                publication_guard=lambda:self.store.publication_lease(
                    self.PROJECT,self.NODE,self.INPUT,owner,
                    lease_seconds=.2)):
                return _commit_actual_body_output(target,render)

    def test_expired_worker_cannot_write_receipt_or_link_after_takeover(self):
        stale = self.acquire()
        self.clock[0]+=1
        live = self.acquire()
        self.assertNotEqual(stale,live)
        target=self.root/"original.png"
        old_renders=[]
        with self.assertRaisesRegex(RecoveryBlocked,"no longer owns"):
            self._render_with_guard(
                stale,target,lambda path:old_renders.append(str(path)))
        self.assertEqual(old_renders,[])
        self.assertFalse(target.exists())
        self.assertFalse((self.root/".zx7-publications").exists())
        restored=self._render_with_guard(
            live,target,lambda path:Path(path).write_bytes(b"v"*1024))
        self.assertEqual(restored["sha256"],
                         hashlib.sha256(b"v"*1024).hexdigest())
        self.assertEqual(target.read_bytes(),b"v"*1024)
        self.assertEqual(len(list((self.root/".zx7-publications").glob("*.json"))),1)

    def test_worker_loses_lease_during_render_and_cannot_publish(self):
        stale=self.acquire()
        target=self.root/"original.png"
        successors=[]
        def original_renderer(stage):
            Path(stage).write_bytes(b"old"*400)
            self.clock[0]+=1
            successors.append(self.acquire())
        with self.assertRaisesRegex(RecoveryBlocked,"no longer owns"):
            self._render_with_guard(stale,target,original_renderer)
        self.assertEqual(len(successors),1)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob(".zx7-uncommitted-*")))
        accepted=self._render_with_guard(
            successors[0],target,
            lambda stage:Path(stage).write_bytes(b"new"*400))
        self.assertEqual(accepted["sha256"],
                         hashlib.sha256(b"new"*400).hexdigest())
        self.assertEqual(target.read_bytes(),b"new"*400)

    def test_live_fence_rearms_lease_after_slow_physical_publication(self):
        owner=self.acquire(seconds=.15)
        heart=RunningStageHeartbeat(
            self.store,self.PROJECT,self.NODE,self.INPUT,owner,
            lease_seconds=.15)
        heart.start()
        try:
            with heart.publication_guard():
                self.clock[0]+=1
                time.sleep(.22)
            with self.store._connect() as db:
                row=db.execute("""SELECT owner,lease_until
                    FROM node_results WHERE project_key=? AND node_id=?""",
                    (self.PROJECT,self.NODE)).fetchone()
            self.assertEqual(row[0],owner)
            self.assertGreater(row[1],self.clock[0])
            heart.stop()
            self.store.complete(
                self.PROJECT,self.NODE,self.INPUT,owner,
                {"artifact_sha256":"a"*64})
        finally:
            heart.abort()
        self.assertEqual(self.store.inspect(self.PROJECT)[0]["status"],
                         "completed")

    def test_guard_rejects_unknown_owner_and_does_not_leak_outside_context(self):
        owner=self.acquire()
        with self.assertRaisesRegex(RecoveryBlocked,"no longer owns"):
            with self.store.publication_lease(
                    self.PROJECT,self.NODE,self.INPUT,"wrong-owner",
                    lease_seconds=.2):
                self.fail("Invalid lease entered publication")
        with physical_tool_attempt(self.PROJECT,self.NODE,self.INPUT,self.TOOL):
            with self.assertRaisesRegex(PermissionError,"active host worker lease"):
                with authorized_publication():
                    self.fail("Unfenced graph publisher admitted")
        # A legacy direct tool call has no verified producer receipt and does
        # not inherit an expired graph worker's private authority.
        with authorized_publication():
            pass
        with self.store.publication_lease(
                self.PROJECT,self.NODE,self.INPUT,owner,
                lease_seconds=.2):
            pass

    def test_failed_link_receipt_can_be_replaced_by_later_verified_owner(self):
        old=self.acquire()
        target=self.root/"original.png"
        interrupted=[False]
        def die_before_link(source,final):
            interrupted[0]=True
            raise OSError("Simulated post-receipt native disk failure")
        with patch("studio_next.body_integration.os.link",side_effect=die_before_link):
            with self.assertRaises(OSError):
                self._render_with_guard(
                    old,target,lambda stage:Path(stage).write_bytes(b"stable"*210))
        self.assertTrue(interrupted[0])
        self.assertFalse(target.exists())
        receipts=list((self.root/".zx7-publications").glob("*.json"))
        self.assertEqual(len(receipts),1)
        # The stage was removed after a caught error. A process-death test
        # instead retains it (the existing physical crash suite covers that).
        self.clock[0]+=1
        newer=self.acquire()
        self.assertNotEqual(newer,old)
        self._render_with_guard(
            newer,target,lambda stage:Path(stage).write_bytes(b"fresh"*250))
        self.assertEqual(len(list((self.root/".zx7-publications").glob("*.json"))),1)
        self.assertEqual(target.read_bytes(),b"fresh"*250)


    def test_actual_child_process_death_after_receipt_recovers_under_new_owner(self):
        # This deliberately kills the process with the SQLite transaction
        # open after a fsynced receipt but before the final hardlink.
        # Bytes are fixtures: this proves crash ownership, not art quality.
        child=r'''
import hashlib,os,sys
from pathlib import Path
from unittest.mock import patch
from studio_next.durable_graph import DurableFilmGraph
from studio_next.body_publication import physical_tool_attempt
from studio_next.body_integration import _commit_actual_body_output
root=Path(sys.argv[1])
store=DurableFilmGraph(root/"owner-ledger.sqlite3",clock=lambda:1000.0)
_,_,owner=store.start_or_reuse(
    "original-film","render-original","sha256-original-source",
    trusted_idempotent=True,
    existing_result_verifier=lambda _:True,lease_seconds=.10)
def witness(path):
    data=Path(path).read_bytes()
    return {"path":str(Path(path).absolute()),
            "sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)}
with patch("studio_next.body_integration._witness",side_effect=witness), \
     patch("studio_next.body_integration._verify_witness",return_value=True), \
     patch("studio_next.body_integration.os.link",
           side_effect=lambda *_:os._exit(73)):
    with physical_tool_attempt(
        "original-film","render-original","sha256-original-source",
        "body.vector_png",
        publication_guard=lambda:store.publication_lease(
            "original-film","render-original","sha256-original-source",
            owner,lease_seconds=.10)):
        _commit_actual_body_output(
            root/"original.png",
            lambda path:Path(path).write_bytes(b"crashed-original"*100))
raise SystemExit("Expected process-death hook was not reached")
'''
        run=subprocess.run([sys.executable,"-c",child,str(self.root)],
            capture_output=True,text=True,timeout=25)
        self.assertEqual(run.returncode,73,run.stderr)
        target=self.root/"original.png"
        self.assertFalse(target.exists())
        self.assertEqual(len(list(self.root.glob(".zx7-uncommitted-*"))),1)
        before_receipts=list((self.root/".zx7-publications").glob("*.json"))
        self.assertEqual(len(before_receipts),1)
        # Advance only the lease clock. The process death, SQLite rollback,
        # fsync and publication recovery are real regardless of CI scheduling.
        store=DurableFilmGraph(self.root/"owner-ledger.sqlite3",clock=lambda:1000.15)
        status,_,new_owner=store.start_or_reuse(
            self.PROJECT,self.NODE,self.INPUT,
            trusted_idempotent=True,
            existing_result_verifier=lambda _:True,lease_seconds=.20)
        self.assertEqual(status,"execute")
        rendered_again=[]
        with patch("studio_next.body_integration._witness",self._witness), \
             patch("studio_next.body_integration._verify_witness",
                   lambda receipt:receipt["bytes"]>=100):
            with physical_tool_attempt(
                    self.PROJECT,self.NODE,self.INPUT,self.TOOL,
                    publication_guard=lambda:store.publication_lease(
                        self.PROJECT,self.NODE,self.INPUT,new_owner,
                        lease_seconds=.20)):
                result=_commit_actual_body_output(
                    target,lambda stage:rendered_again.append(stage))
        self.assertEqual(rendered_again,[])
        self.assertEqual(target.read_bytes(),b"crashed-original"*100)
        self.assertEqual(
            result["sha256"],
            hashlib.sha256(b"crashed-original"*100).hexdigest())
        self.assertFalse(list(self.root.glob(".zx7-uncommitted-*")))
        self.assertEqual(
            len(list((self.root/".zx7-publications").glob("*.json"))),1)


if __name__ == "__main__":
    unittest.main()
