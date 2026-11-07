"""Prove native capability audit does not mistake installation for AI control."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from studio_next.native_capability_audit import audit_native_coverage


def tool(name, properties=None):
    return {"name": name, "inputSchema": {
        "type": "object", "properties": properties or {}}}


class NativeCapabilityCoverageTests(unittest.TestCase):
    def test_catalog_discloses_exact_missing_grants_without_executing_tools(self):
        source = [tool("get_project"), tool("add_text_clip",
                                          {"text": {"type": "string"}}),
                  tool("generate_music", {"prompt": {"type": "string"}})]
        audit = audit_native_coverage(
            source, {"get_project": "read", "add_text_clip": "write"})
        self.assertEqual((audit["native_advertised"], audit["host_granted"],
                          audit["host_ungranted"]), (3, 2, 1))
        self.assertEqual(audit["ungranted_native_names"], ["generate_music"])
        self.assertEqual(audit["schema_property_counts_for_granted"]
                         ["add_text_clip"], 1)
        self.assertEqual(audit["host_granted_read"], 1)
        self.assertEqual(audit["host_granted_write"], 1)
        self.assertFalse(audit["autonomous_execution_or_professional_quality_verified"])
        self.assertTrue(audit["no_tools_dispatched_by_this_audit"])
        self.assertNotIn("generate_music",
                         audit["schema_property_counts_for_granted"])

    def test_pinned_profile_has_exact_existing_grants_not_all_native_tools(self):
        config = (Path(__file__).resolve().parents[1] / "engines" /
                  "velorn" / "editor.example.json")
        grants = json.loads(config.read_text(encoding="utf-8"))["allowed_tools"]
        self.assertEqual(len(grants), 77)
        self.assertNotIn("generate_music", grants)
        self.assertNotIn("import_stock_media", grants)

    def test_invalid_or_bogus_grants_fail_closed(self):
        cases = [
            ([tool("get_project")], {"invented": "write"}),
            ([tool("get_project"), tool("get_project")], {"get_project": "read"}),
            ([tool("get_project", {"broken": False})],
             {"get_project": "read"}),
            ([{"name": "get_project", "inputSchema": {"type": "array"}}],
             {"get_project": "read"}),
            ([], {}),
            ([tool("get_project")], {"get_project": "admin"}),
        ]
        for catalog, grants in cases:
            with self.subTest(catalog=catalog, grants=grants):
                with self.assertRaises(ValueError):
                    audit_native_coverage(catalog, grants)


if __name__ == "__main__":
    unittest.main()
