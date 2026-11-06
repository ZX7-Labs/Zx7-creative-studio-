"""Actual SQLite and host-facing cross-capability plan-head revision proofs.

Plan selection does NOT claim a real native editor was observed or that an
output or asset has owner rights. Other suites prove those physical properties.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from studio_next.body_archive import create_body_archive,restore_body_archive
from studio_next.body_project_heads import (
    DocumentHeadLedger,DocumentHeadConflict,DocumentHeadCorrupt)
from studio_next.body_service import LocalBodyCoordinator
from studio_next.body_signal import (
    BodyAuthority,BodyCommandRejected,LiveBodySignal)
from studio_next.durable_sqlite import connect_durable_database


A="a"*64
B="b"*64
C="c"*64


class CrossCapabilityDocumentHeadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace=Path(self.temp.name)/"project"
        self.workspace.mkdir()
        self.ledger=DocumentHeadLedger(self.workspace)

    def select(self,document,*,project="original",tool="graphics/mask",
               slot="plan",parent=None,base=None):
        return self.ledger.select(project_id=project,tool_id=tool,
            input_name=slot,document_sha256=document,
            expected_revision_id=parent,expected_document_sha256=base)

    def _bundle(self, selections, project="original"):
        return self.ledger.select_bundle(project_id=project,selections=selections)

    @staticmethod
    def _entry(tool, document, *, slot="plan", parent=None, base=None):
        return {"tool_id":tool,"input_name":slot,
                "document_sha256":document,
                "expected_revision_id":parent,
                "expected_document_sha256":base}

    def test_original_graphics_audio_motion_heads_commit_as_one_transaction(self):
        entries=[self._entry("graphics/mask",A),
                 self._entry("audio/score",B),
                 self._entry("motion/rig",C,slot="scene_json")]
        selected=self._bundle(entries)
        self.assertTrue(selected["atomic_plan_head_selection"])
        self.assertFalse(selected["native_project_state_applied_or_verified"])
        self.assertEqual(len(selected["revisions"]),3)
        observed=self.ledger.heads("original")["heads"]
        self.assertEqual(len(observed),3)
        self.assertEqual({x["document_sha256"] for x in observed},{A,B,C})
        self.assertEqual(len(DocumentHeadLedger(self.workspace).heads("original")["heads"]),3)

    def test_stale_audio_parent_refuses_new_video_and_motion_in_one_bundle(self):
        art=self.select(A,tool="graphics/mask")
        sound=self.select(B,tool="audio/score")
        candidate=[self._entry("graphics/mask",C,
                    parent=art["revision_id"],base=A),
                   self._entry("audio/score",A,
                    parent=art["revision_id"],base=B)]
        with self.assertRaisesRegex(DocumentHeadConflict,"Stale"):
            self._bundle(candidate)
        unchanged=self.ledger.heads("original")["heads"]
        self.assertEqual(
            {(x["tool_id"],x["document_sha256"]) for x in unchanged},
            {("graphics/mask",A),("audio/score",B)})
        for tool in ("graphics/mask","audio/score"):
            self.assertEqual(len(self.ledger.history(
                project_id="original",tool_id=tool,input_name="plan")["revisions"]),1)

    def test_sqlite_abort_on_second_instrument_rolls_back_first(self):
        from studio_next.durable_sqlite import connect_durable_database
        with connect_durable_database(self.workspace/"production.sqlite3") as db:
            self.ledger._create_tables(db)
            db.execute("""CREATE TRIGGER refuse_audio
                BEFORE INSERT ON creative_document_revisions
                WHEN NEW.tool_id='audio/score'
                BEGIN SELECT RAISE(ABORT,'forced second insert failure'); END""")
        with self.assertRaisesRegex(Exception,"forced second insert failure"):
            self._bundle([self._entry("graphics/mask",A),
                          self._entry("audio/score",B)])
        self.assertEqual(self.ledger.heads("original")["heads"],[])
        with connect_durable_database(self.workspace/"production.sqlite3") as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM creative_document_revisions").fetchone()[0],0)

    def test_real_process_death_mid_bundle_restores_no_partial_head(self):
        # The child is killed inside SQLite itself after the FIRST instrument
        # head has been written and while the SECOND history row is inserting.
        # This is physical SQLite rollback recovery, not a mocked exception.
        child=r'''
import os,sys
from studio_next.body_project_heads import DocumentHeadLedger
from studio_next.durable_sqlite import connect_durable_database
store=DocumentHeadLedger(sys.argv[1])
with connect_durable_database(store.path) as db:
    store._create_tables(db)
    db.execute("""CREATE TRIGGER kill_mid_bundle
        BEFORE INSERT ON creative_document_revisions
        WHEN NEW.tool_id='audio/score'
        BEGIN SELECT die_for_test(); END""")
original=store._connect
def installed_connection():
    db=original()
    db.create_function("die_for_test",0,lambda:os._exit(79))
    return db
store._connect=installed_connection
store.select_bundle(project_id="original",selections=[
    {"tool_id":"graphics/mask","input_name":"plan",
     "document_sha256":"a"*64,
     "expected_revision_id":None,"expected_document_sha256":None},
    {"tool_id":"audio/score","input_name":"plan",
     "document_sha256":"b"*64,
     "expected_revision_id":None,"expected_document_sha256":None}])
raise SystemExit("Native crash hook was not reached")
'''
        killed=subprocess.run([sys.executable,"-c",child,str(self.workspace)],
                              capture_output=True,text=True,timeout=20)
        self.assertEqual(killed.returncode,79,killed.stderr)
        self.assertEqual(DocumentHeadLedger(self.workspace).heads("original")["heads"],[])
        with connect_durable_database(self.workspace/"production.sqlite3") as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM creative_document_revisions").fetchone()[0],0)
            db.execute("DROP TRIGGER kill_mid_bundle")
        recovered=self._bundle([self._entry("graphics/mask",A),
                                self._entry("audio/score",B)])
        self.assertTrue(recovered["atomic_plan_head_selection"])
        self.assertEqual(len(self.ledger.heads("original")["heads"]),2)

    def test_two_concurrent_cross_engine_bundles_never_publish_mixed_heads(self):
        barrier=threading.Barrier(2)
        def worker(first,second):
            barrier.wait(timeout=10)
            try:
                return self._bundle([
                    self._entry("graphics/mask",first),
                    self._entry("audio/score",second)])
            except DocumentHeadConflict as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda item:worker(*item),[(A,B),(B,C)]))
        self.assertEqual(sum(isinstance(x,dict) for x in results),1)
        self.assertEqual(sum(isinstance(x,DocumentHeadConflict) for x in results),1)
        heads=self.ledger.heads("original")["heads"]
        current={h["tool_id"]:h["document_sha256"] for h in heads}
        self.assertIn(current,[
            {"graphics/mask":A,"audio/score":B},
            {"graphics/mask":B,"audio/score":C}])
        self.assertEqual(len(heads),2)

    def test_duplicate_or_oversized_bundle_never_publishes_partial_history(self):
        same=self._entry("graphics/mask",A)
        for entries in ([same,same],
                        [],
                        [same]*33,
                        [same,{"tool_id":"audio/score","extra":"untrusted"}]):
            with self.subTest(count=len(entries)),self.assertRaises(ValueError):
                self._bundle(entries)
        self.assertEqual(self.ledger.heads("original")["heads"],[])

    def test_bundled_undo_keeps_every_original_and_new_revision(self):
        first=self._bundle([self._entry("graphics/mask",A),
                            self._entry("audio/score",B)])["revisions"]
        updated=self._bundle([
            self._entry("graphics/mask",C,parent=first[0]["revision_id"],base=A),
            self._entry("audio/score",A,parent=first[1]["revision_id"],base=B),
        ])["revisions"]
        undone=self._bundle([
            self._entry("graphics/mask",A,parent=updated[0]["revision_id"],base=C),
            self._entry("audio/score",B,parent=updated[1]["revision_id"],base=A),
        ])["revisions"]
        self.assertNotEqual(undone[0]["revision_id"],first[0]["revision_id"])
        for tool in ("graphics/mask","audio/score"):
            history=self.ledger.history(
                project_id="original",tool_id=tool,input_name="plan")
            self.assertEqual(len(history["revisions"]),3)
            self.assertFalse(history["native_project_state_applied_or_verified"])

    def test_project_streams_keep_multiple_native_capabilities_independent(self):
        artwork=self.select(A,tool="graphics/mask",slot="scene_json")
        sound=self.select(B,tool="audio/music",slot="plan")
        motion=self.select(C,tool="motion/rig",slot="scene_json")
        heads=self.ledger.heads("original")
        self.assertEqual(len(heads["heads"]),3)
        self.assertEqual(
            {(h["tool_id"],h["document_sha256"]) for h in heads["heads"]},
            {("graphics/mask",A),("audio/music",B),("motion/rig",C)})
        self.assertFalse(heads["native_project_state_applied_or_verified"])
        self.assertNotEqual(artwork["revision_id"],sound["revision_id"])
        self.assertNotEqual(sound["revision_id"],motion["revision_id"])
        reopened=DocumentHeadLedger(self.workspace)
        self.assertEqual(reopened.heads("original")["heads"],heads["heads"])
        self.assertFalse(self.workspace.joinpath("rendered.mp4").exists())

    def test_stale_plan_refused_and_explicit_undo_creates_new_immutable_event(self):
        one=self.select(A)
        two=self.select(B,parent=one["revision_id"],base=A)
        with self.assertRaisesRegex(DocumentHeadConflict,"Stale"):
            self.select(C,parent=one["revision_id"],base=A)
        with self.assertRaisesRegex(DocumentHeadConflict,"No changed"):
            self.select(B,parent=two["revision_id"],base=B)
        undo=self.select(A,parent=two["revision_id"],base=B)
        self.assertNotEqual(undo["revision_id"],one["revision_id"])
        self.assertEqual(undo["parent_revision_id"],two["revision_id"])
        self.assertEqual(self.ledger.heads("original")["heads"][0]["document_sha256"],A)
        history=self.ledger.history(
            project_id="original",tool_id="graphics/mask",input_name="plan")
        self.assertEqual([x["revision_id"] for x in history["revisions"]],
            [undo["revision_id"],two["revision_id"],one["revision_id"]])
        self.assertFalse(history["has_more"])
        self.assertFalse(undo["native_project_state_applied_or_verified"])
        self.assertFalse(undo["media_source_rights_independently_verified"])

    def test_two_simultaneous_model_workers_cannot_both_select_stale_head(self):
        barrier=threading.Barrier(2)
        def worker(document):
            barrier.wait(timeout=5)
            try:
                return self.select(document)
            except DocumentHeadConflict as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(worker,d) for d in (A,B)]
            outcomes=[f.result(timeout=15) for f in futures]
        self.assertEqual(sum(isinstance(x,dict) for x in outcomes),1)
        self.assertEqual(sum(isinstance(x,DocumentHeadConflict) for x in outcomes),1)
        head=self.ledger.heads("original")["heads"][0]
        self.assertIn(head["document_sha256"],(A,B))
        history=self.ledger.history(project_id="original",tool_id="graphics/mask",
                                   input_name="plan")
        self.assertEqual(len(history["revisions"]),1)

    def test_host_crash_after_commit_can_inspect_but_never_duplicate_revision(self):
        child=(
            "import os,sys\n"
            "from studio_next.body_project_heads import DocumentHeadLedger\n"
            "store=DocumentHeadLedger(sys.argv[1]);"
            "store.select(project_id='original',tool_id='graphics/mask',"
            "input_name='plan',document_sha256='a'*64,"
            "expected_revision_id=None,expected_document_sha256=None)\n"
            "os._exit(77)\n"
        )
        completed=subprocess.run(
            [sys.executable,"-c",child,str(self.workspace)],timeout=20)
        self.assertEqual(completed.returncode,77)
        recorded=self.ledger.heads("original")["heads"]
        self.assertEqual(len(recorded),1)
        with self.assertRaises(DocumentHeadConflict):
            self.select(A)
        self.assertEqual(len(self.ledger.history(
            project_id="original",tool_id="graphics/mask",
            input_name="plan")["revisions"]),1)

    def test_many_future_engine_inputs_are_discoverable_in_bounded_pages(self):
        for number in range(115):
            self.select(A,tool=f"creative/instrument-{number:03}",
                        slot="scene_json")
        pages=[self.ledger.heads("original",limit=31,offset=offset)
               for offset in (0,31,62,93)]
        self.assertEqual([len(x["heads"]) for x in pages],[31,31,31,22])
        self.assertEqual([x["next_offset"] for x in pages],[31,62,93,None])
        self.assertEqual(sum(len(x["heads"]) for x in pages),115)
        names=[h["tool_id"] for page in pages for h in page["heads"]]
        self.assertEqual(len(names),len(set(names)))
        self.assertEqual(names,sorted(names))
        for value in (-1,True,100001):
            with self.assertRaises(ValueError):
                self.ledger.heads("original",offset=value)

    def test_history_pages_retain_every_immutable_parent_without_dumping_all(self):
        previous=None
        prev_doc=None
        for number in range(1,16):
            digest=f"{number:064x}"
            recorded=self.select(digest,tool="audio/original_mix",
                parent=previous,base=prev_doc)
            previous=recorded["revision_id"]
            prev_doc=digest
        pages=[self.ledger.history(project_id="original",
            tool_id="audio/original_mix",input_name="plan",
            limit=6,offset=offset) for offset in (0,6,12)]
        self.assertEqual([len(x["revisions"]) for x in pages],[6,6,3])
        self.assertEqual([x["next_offset"] for x in pages],[6,12,None])
        self.assertEqual(pages[0]["revisions"][0]["revision_id"],previous)
        for value in (0,101,True):
            with self.assertRaises(ValueError):
                self.ledger.history(project_id="original",
                    tool_id="audio/original_mix",input_name="plan",
                    limit=value)

    def test_corruption_is_not_a_trusted_active_head_or_history(self):
        valid=self.select(A)
        with connect_durable_database(self.workspace/"production.sqlite3") as db:
            db.execute("""UPDATE creative_document_revisions SET document_sha256=?
                WHERE revision_id=?""",(B,valid["revision_id"]))
        with self.assertRaises(DocumentHeadCorrupt):
            self.ledger.heads("original")
        with self.assertRaises(DocumentHeadCorrupt):
            self.ledger.history(project_id="original",
                tool_id="graphics/mask",input_name="plan")

    def test_invalid_inputs_never_create_project_version(self):
        invalid=[
            {"project":"../outside"},{"tool":"bad\noperation"},
            {"slot":"../../../pass"},{"document":"bad-digest"},
            {"parent":True},{"parent":A,"base":None},
            {"parent":None,"base":A}]
        for problem in invalid:
            with self.subTest(problem=problem),self.assertRaises(ValueError):
                arguments={"document":A,"project":"original","tool":"graphics/mask",
                           "slot":"plan","parent":None,"base":None}
                arguments.update(problem)
                self.select(**arguments)
        self.assertEqual(self.ledger.heads("original")["heads"],[])

    def test_same_path_restore_preserves_active_original_revision_history(self):
        first=self.select(A)
        second=self.select(B,parent=first["revision_id"],base=A)
        before=self.ledger.heads("original")["heads"]
        archive=Path(self.temp.name)/"original-backup.tar.gz"
        receipt=create_body_archive(self.workspace,archive)
        # Preserve the original independently instead of deleting it to
        # exercise a same-path recovery into its previously occupied address.
        self.workspace.rename(Path(self.temp.name)/"offline-original-copy")
        actual=restore_body_archive(
            archive,self.workspace,expected_sha256=receipt["sha256"])
        self.assertTrue(actual["all_physical_bytes_verified"])
        self.assertFalse(actual["relocated"])
        restored=DocumentHeadLedger(self.workspace)
        self.assertEqual(restored.heads("original")["heads"],before)
        self.assertEqual(len(restored.history(project_id="original",
            tool_id="graphics/mask",input_name="plan")["revisions"]),2)
        self.assertEqual(restored.heads("original")["heads"][0]["revision_id"],
                         second["revision_id"])

    def test_cross_host_relocation_preserves_history_but_quarantines_active_heads(self):
        first=self.select(A)
        second=self.select(B,parent=first["revision_id"],base=A)
        archive=Path(self.temp.name)/"portable-project.tar.gz"
        receipt=create_body_archive(self.workspace,archive)
        relocated=Path(self.temp.name)/"new-host"
        actual=restore_body_archive(
            archive,relocated,expected_sha256=receipt["sha256"],relocate=True)
        self.assertTrue(actual["all_physical_bytes_verified"])
        self.assertTrue(actual["relocated"])
        self.assertTrue(actual["old_execution_state_quarantined"])
        self.assertFalse((relocated/"production.sqlite3").exists())
        self.assertEqual(DocumentHeadLedger(relocated).heads("original")["heads"],[])
        historical=DocumentHeadLedger(relocated/".zx7-relocated-history")
        self.assertEqual(historical.heads("original")["heads"][0]["revision_id"],
                         second["revision_id"])
        self.assertEqual(len(historical.history(project_id="original",
            tool_id="graphics/mask",input_name="plan")["revisions"]),2)
        self.assertTrue((relocated/".zx7-relocation-report.json").is_file())

    def test_read_only_uncreated_workspace_does_not_create_an_empty_database(self):
        empty=Path(self.temp.name)/"never-authored"
        self.assertEqual(DocumentHeadLedger(empty).heads("project")["heads"],[])
        self.assertFalse(empty.exists())


class ActualBodySignalPlanHeadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.host=LocalBodyCoordinator(self.temp.name)
        self.addCleanup(self.host.close)
        authority=BodyAuthority(
            workspace_ids=frozenset({"artist"}),
            operations=frozenset({"author_plan","revise_plan","select_plan",
                                  "select_plan_bundle"}),
            tool_access=frozenset({"read","write"}))
        self.signal=LiveBodySignal(self.host,authority=authority)
        self.plan={
            "format":{"width":128,"height":96,"fps":12,
                      "framing":"fit","background":"#111111"},
            "clips":[{"id":"a","source":"unprovided.mp4",
                      "rights":"owner_supplied","audio":"preserve_source",
                      "asset_id":"0"*64,"attestation_id":"not-yet-attested"}],
        }

    def _author(self,plan):
        return self.signal.command("author_plan",{
            "workspace_id":"artist","tool_id":"body.render_edit_owned",
            "document":plan})

    def _select(self,document,*,parent=None,base=None,project="film"):
        return self.signal.command("select_plan",{
            "workspace_id":"artist","project_id":project,
            "tool_id":"body.render_edit_owned",
            "document_sha256":document,
            "expected_revision_id":parent,
            "expected_document_sha256":base})

    def test_host_validates_two_installed_instruments_and_commits_together(self):
        rendered=self._author(self.plan)
        mixed=self.signal.command("author_plan",{
            "workspace_id":"artist","tool_id":"body.composite_mix",
            "document":{
                "canvas":{"width":128,"height":96,"fps":12,
                          "duration":1,"background":"#111111"},
                "video_layers":[],"audio_tracks":[]}})
        submitted=self.signal.command("select_plan_bundle",{
            "workspace_id":"artist","project_id":"film",
            "selections":[
                {"tool_id":"body.render_edit_owned",
                 "document_sha256":rendered["sha256"],
                 "expected_revision_id":None,
                 "expected_document_sha256":None},
                {"tool_id":"body.composite_mix",
                 "document_sha256":mixed["sha256"],
                 "expected_revision_id":None,
                 "expected_document_sha256":None},
            ]})
        self.assertTrue(submitted["atomic_plan_head_selection"])
        self.assertTrue(submitted["host_installed_document_schema_revalidated"])
        self.assertFalse(submitted["native_media_rendered_or_approved"])
        self.assertEqual(len(submitted["revisions"]),2)
        self.assertEqual(len(self.signal.inspect_plan_heads("artist","film")["heads"]),2)
        self.assertEqual(
            {r["tool_id"] for r in submitted["revisions"]},
            {"body.render_edit_owned","body.composite_mix"})
        # The model could not force even one native writer to run by
        # selecting multiple approved plans.
        self.assertFalse((self.host._workspace("artist")/"export.mp4").exists())

    def test_host_refuses_one_tampered_plan_without_selecting_other_head(self):
        valid=self._author(self.plan)
        untrusted=self.signal.command("author_plan",{
            "workspace_id":"artist","tool_id":"body.composite_mix",
            "document":{
                "canvas":{"width":128,"height":96,"fps":12,
                          "duration":1,"background":"#111111"},
                "video_layers":[],"audio_tracks":[]}})
        (self.host._workspace("artist")/untrusted["path"]).write_bytes(b'{"fake":true}')
        before=self.signal.inspect_plan_heads("artist","film")
        with self.assertRaises(BodyCommandRejected):
            self.signal.command("select_plan_bundle",{
                "workspace_id":"artist","project_id":"film",
                "selections":[
                    {"tool_id":"body.render_edit_owned",
                     "document_sha256":valid["sha256"],
                     "expected_revision_id":None,
                     "expected_document_sha256":None},
                    {"tool_id":"body.composite_mix",
                     "document_sha256":untrusted["sha256"],
                     "expected_revision_id":None,
                     "expected_document_sha256":None}]})
        self.assertEqual(self.signal.inspect_plan_heads("artist","film"),before)

    def test_bundle_selection_requires_explicit_host_grant(self):
        original=self._author(self.plan)
        read_only=LiveBodySignal(self.host,authority=BodyAuthority(
            workspace_ids=frozenset({"artist"})))
        with self.assertRaises(PermissionError):
            read_only.command("select_plan_bundle",{
                "workspace_id":"artist","project_id":"film","selections":[{
                    "tool_id":"body.render_edit_owned",
                    "document_sha256":original["sha256"],
                    "expected_revision_id":None,
                    "expected_document_sha256":None}]})
        self.assertEqual(self.signal.inspect_plan_heads("artist","film")["heads"],[])

    def test_real_installed_body_document_head_schema_cas_and_undo(self):
        self.assertEqual(self.signal.inspect_plan_heads("artist","film")["heads"],[])
        before=self._author(self.plan)
        initial=self._select(before["sha256"])
        self.assertTrue(initial["host_installed_document_schema_revalidated"])
        self.assertFalse(initial["native_media_rendered_or_approved"])
        self.assertEqual(self.signal.inspect_plan_heads(
            "artist","film")["heads"][0]["document_sha256"],before["sha256"])
        candidate=self.signal.command("revise_plan",{
            "workspace_id":"artist","tool_id":"body.render_edit_owned",
            "base_sha256":before["sha256"],
            "operations":[{"op":"replace","path":"/format/width","value":640}]})
        after=self._select(candidate["sha256"],
            parent=initial["revision_id"],base=before["sha256"])
        with self.assertRaises(BodyCommandRejected):
            self._select(candidate["sha256"],
                parent=initial["revision_id"],base=before["sha256"])
        undo=self._select(before["sha256"],
            parent=after["revision_id"],base=candidate["sha256"])
        self.assertNotEqual(initial["revision_id"],undo["revision_id"])
        history=self.signal.inspect_plan_history(
            "artist","film","body.render_edit_owned","edit")
        self.assertEqual(len(history["revisions"]),3)
        self.assertEqual(history["revisions"][0]["revision_id"],
                         undo["revision_id"])
        self.assertEqual(self.signal.inspect_plan(
            "artist",before["sha256"],pointer="/format/width")["value"],128)
        self.assertEqual(self.signal.inspect_plan(
            "artist",candidate["sha256"],pointer="/format/width")["value"],640)
        self.assertTrue((self.host._workspace("artist")/
                         "production.sqlite3").is_file())
        self.assertFalse((self.host._workspace("artist")/
                          "original-cinema.mp4").exists())

    def test_untrusted_plan_bytes_or_absent_grant_cannot_select_project_head(self):
        original=self._author(self.plan)
        read_only=LiveBodySignal(self.host,authority=BodyAuthority(
            workspace_ids=frozenset({"artist"})))
        with self.assertRaises(PermissionError):
            read_only.command("select_plan",{
                "workspace_id":"artist","project_id":"film",
                "tool_id":"body.render_edit_owned",
                "document_sha256":original["sha256"],
                "expected_revision_id":None,"expected_document_sha256":None})
        with self.assertRaises(PermissionError):
            self.signal.inspect_plan_heads("another-owner","film")
        path=self.host._workspace("artist")/original["path"]
        path.write_bytes(b'{"untrusted":true}')
        with self.assertRaises(BodyCommandRejected):
            self._select(original["sha256"])
        self.assertEqual(self.signal.inspect_plan_heads("artist","film")["heads"],[])

    def test_invalid_plan_revision_looks_like_data_not_native_execution(self):
        original=self._author(self.plan)
        with self.assertRaises(BodyCommandRejected):
            self._select(original["sha256"],project="../../other-owner")
        with self.assertRaises(BodyCommandRejected):
            self.signal.command("select_plan",{
                "workspace_id":"artist","project_id":"film",
                "tool_id":"body.not_installed",
                "document_sha256":original["sha256"],
                "expected_revision_id":None,"expected_document_sha256":None})
        self.assertEqual(self.signal.inspect_plan_heads("artist","film")["heads"],[])


if __name__ == "__main__":
    unittest.main()
