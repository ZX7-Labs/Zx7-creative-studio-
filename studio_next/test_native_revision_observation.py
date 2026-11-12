"""Host-bound model READ tools for real saved native revision evidence, no inference."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest import IsolatedAsyncioTestCase

from studio_next.capability_gateway import CapabilityGateway
from studio_next.capability_mcp_session import CapabilityGatewayMcpSession
from studio_next.capability_session_budget import CapabilitySessionBudget
from studio_next.native_creative_revision import NativeRevisionReviewError
from studio_next.native_revision_observation import NativeRevisionObservationMcpSession
from studio_next.test_native_creative_revision import example


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class NativeRevisionObservationTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "saved"
        self.root.mkdir(mode=0o700)
        self.tool = NativeRevisionObservationMcpSession(self.root)
        self.output_ids = []

    def capture(self, payload, *, export_number):
        eid = digest(f"actual host destination {export_number}".encode())
        content = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        (self.root / (eid + ".comfystudio")).write_bytes(content)
        witness = self.tool.register_host_captured_render(
            eid, digest(content), digest(f"actual export options {export_number}".encode()))
        self.assertEqual(witness["project_sha256"], digest(content))
        self.output_ids.append(eid)
        return eid

    async def invoke(self, name, arguments):
        receipt = await self.tool.call_tool(name, arguments)
        self.assertEqual(len(receipt.content), 1)
        return receipt, receipt.content[0].text

    async def test_without_host_capture_model_cannot_observe_arbitrary_paths(self):
        r, txt = await self.invoke("zx7_list_saved_render_revisions", {})
        self.assertFalse(r.is_error)
        self.assertEqual(json.loads(txt)["count"], 0)
        for args in (
            {"before_export_id": "../etc/private", "after_export_id": "a" * 64},
            {"before_export_id": "a" * 64, "after_export_id": "b" * 64},
            {"before_export_id": "a" * 64, "after_export_id": "b" * 64,
             "path": "/tmp/private-owner"},
        ):
            receipt, text = await self.invoke(
                "zx7_compare_saved_render_revisions", args)
            self.assertTrue(receipt.is_error)
            self.assertNotIn("/tmp/private-owner", text)

    async def test_after_two_host_captures_model_can_inspect_editable_changes(self):
        original = example()
        modified = deepcopy(original)
        modified["timelines"][0]["clips"][0]["textProperties"]["text"] = "PRIVATE OWNER SCRIPT"
        modified["timelines"][0]["clips"][0]["keyframes"]["opacity"][0]["value"] = 32
        modified["timelines"][0]["clips"][1]["duration"] = 1.5
        before = self.capture(original, export_number=1)
        after = self.capture(modified, export_number=2)
        r, txt = await self.invoke("zx7_list_saved_render_revisions", {})
        self.assertFalse(r.is_error)
        listing = json.loads(txt)
        self.assertEqual(listing["count"], 2)
        for secret in ("owner-private-voice.wav", "SECRET CREATIVE BRIEF",
                       "PRIVATE OWNER SCRIPT", "/secret/owner"):
            self.assertNotIn(secret, txt)
        r2, txt2 = await self.invoke("zx7_compare_saved_render_revisions", {
            "before_export_id": before, "after_export_id": after,
            "offset": 0, "limit": 1})
        self.assertFalse(r2.is_error)
        first = json.loads(txt2)
        self.assertEqual(first["review"]["returned_count"], 1)
        self.assertTrue(first["review"]["has_more_entries"])
        self.assertEqual(first["review"]["next_offset"], 1)
        self.assertFalse(first["impact"]["actual_media_decoded"])
        self.assertFalse(first["impact"]["creative_quality_assessed"])
        self.assertTrue(first["native_source_binding_verified_for_both"])
        self.assertTrue(first["not_an_authorization_to_apply_edits"])
        self.assertNotIn("PRIVATE OWNER SCRIPT", txt2)
        r3, txt3 = await self.invoke("zx7_compare_saved_render_revisions", {
            "before_export_id": before, "after_export_id": after,
            "offset": 1, "limit": 20})
        self.assertFalse(r3.is_error)
        further = json.loads(txt3)
        self.assertTrue(any("/duration" in entry.get("changed_fields", ())
                            for entry in further["review"]["entries"]))

    async def test_three_way_conflict_reads_registered_sources_without_merge(self):
        base = example()
        human, ai = deepcopy(base), deepcopy(base)
        human["timelines"][0]["clips"][0]["textProperties"]["text"] = "Human private"
        ai["timelines"][0]["clips"][0]["textProperties"]["text"] = "AI private"
        p0 = self.capture(base, export_number=1)
        p1 = self.capture(human, export_number=2)
        p2 = self.capture(ai, export_number=3)
        r, txt = await self.invoke("zx7_review_saved_render_candidates", {
            "base_export_id": p0, "human_candidate_export_id": p1,
            "ai_candidate_export_id": p2})
        self.assertFalse(r.is_error)
        result = json.loads(txt)
        self.assertEqual(result["status"], "conflicting_changes")
        self.assertTrue(result["origin_role_labels_not_authenticated"])
        self.assertFalse(result["automatic_merge_permitted"])
        self.assertTrue(result["live_native_revision_CAS_required_for_every_write"])
        self.assertNotIn("Human private", txt)
        self.assertNotIn("AI private", txt)

    async def test_tampering_after_host_registration_fails_closed(self):
        initial = example()
        eid = self.capture(initial, export_number=1)
        location = self.root / (eid + ".comfystudio")
        location.write_text(json.dumps({**initial, "modified": "attacker"}))
        r, text = await self.invoke("zx7_list_saved_render_revisions", {})
        self.assertTrue(r.is_error)
        self.assertEqual(text, "Native revision review unavailable or refused")

    async def test_forged_capture_sha_duplicate_and_registry_limit_rejected(self):
        raw = example()
        eid = digest(b"trusted export")
        location = self.root / (eid + ".comfystudio")
        location.write_text(json.dumps(raw))
        with self.assertRaises(NativeRevisionReviewError):
            self.tool.register_host_captured_render(
                eid, "b" * 64, "c" * 64)
        self.tool.register_host_captured_render(
            eid, digest(location.read_bytes()), "c" * 64)
        with self.assertRaises(NativeRevisionReviewError):
            self.tool.register_host_captured_render(
                eid, digest(location.read_bytes()), "c" * 64)

    async def test_symlink_snapshot_is_not_a_trusted_host_capture(self):
        eid = digest(b"render")
        real = self.root / "actual-private-project.comfystudio"
        real.write_text(json.dumps(example()))
        (self.root / (eid + ".comfystudio")).symlink_to(real)
        with self.assertRaises(NativeRevisionReviewError):
            self.tool.register_host_captured_render(
                eid, digest(real.read_bytes()), "c" * 64)

    async def test_existing_capability_gateway_grants_and_discovery_are_reused(self):
        a = self.capture(example(), export_number=1)
        gateway = CapabilityGateway({"native_review": (
            self.tool, self.tool.grants)}, session_budget=CapabilitySessionBudget(
                max_calls=12, max_writes=1))
        await gateway.refresh()
        session = CapabilityGatewayMcpSession(gateway, "native_review")
        advertised = (await session.list_tools()).tools
        self.assertEqual(
            set(tool.name for tool in advertised),
            {"zx7_list_saved_render_revisions",
             "zx7_compare_saved_render_revisions",
             "zx7_review_saved_render_candidates"})
        read = await session.call_tool("zx7_list_saved_render_revisions", {})
        self.assertFalse(read.is_error)
        self.assertEqual(json.loads(read.content[0].text)["snapshots"][0]["export_id"], a)
        self.assertFalse(any(action.get("access") == "write"
                             for action in gateway.evidence()))

    async def test_schema_blocks_unbounded_page_and_unregistered_tools(self):
        eid = self.capture(example(), export_number=1)
        for args in (
            {"before_export_id": eid, "after_export_id": eid, "limit": 2000},
            {"before_export_id": eid, "after_export_id": eid, "offset": -1},
            {"before_export_id": eid, "after_export_id": eid, "limit": True},
        ):
            r, _ = await self.invoke("zx7_compare_saved_render_revisions", args)
            self.assertTrue(r.is_error)
        r, _ = await self.invoke("read_arbitrary_file", {})
        self.assertTrue(r.is_error)
