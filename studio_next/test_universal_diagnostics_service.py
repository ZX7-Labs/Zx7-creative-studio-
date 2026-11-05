"""Real local-service/phone UI diagnostics integration and authorization.

Fixture-only durable rows check data projection. They are never real-model
benchmarks and never certify a professional film.
"""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from studio_next.body_mobile import PAGE, SCRIPT
from studio_next.test_body_controls import local_service


class UniversalDiagnosticsServiceTests(unittest.TestCase):
    def test_authenticated_real_service_reports_live_tools_and_unknown_model_quality(self):
        with tempfile.TemporaryDirectory() as temporary:
            with local_service(Path(temporary) / "host") as (host, client):
                report = client.diagnostics()
                self.assertEqual(report["schema"], 1)
                self.assertEqual(report["kind"], "zx7_universal_evidence_diagnostics")
                self.assertEqual(report["body"]["presence"], "measured_live_registry")
                self.assertEqual(report["model"]["independent_creativity"], "unmeasured")
                self.assertFalse(report["model"]["configured"])
                self.assertGreater(report["body"]["capability_families"], 0)
                self.assertEqual(report["controlled_comparisons"]["observed_pairs"], 0)
                self.assertIsNone(report["model"]["identity"])
                self.assertNotIn("model_power_score", json.dumps(report))
                connection = http.client.HTTPConnection(client.hostname, client.port, timeout=5)
                try:
                    connection.request("GET", "/v1/diagnostics")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 401)
                    self.assertNotIn("installed_operations", response.read().decode())
                finally:
                    connection.close()

    def test_existing_durable_states_count_without_model_blame_or_leaking_prompts(self):
        with tempfile.TemporaryDirectory() as temporary:
            with local_service(Path(temporary) / "host") as (host, client):
                with host._connect() as db:
                    db.execute("""INSERT INTO jobs VALUES(?,?,?,?,?,?,?)""", (
                        "diagnostic_fixture_only", "unit_fixture",
                        json.dumps({"tool_graph": [], "owner_facts": {
                            "private_avoid_log": "sensitive user creative prompt"}}),
                        "failed", 1,
                        json.dumps({"status": "failed", "message": "sensitive private file /tmp/secret"}),
                        0.0,
                    ))
                    db.execute("""CREATE TABLE IF NOT EXISTS creative_sessions(
                        id TEXT PRIMARY KEY, workspace TEXT NOT NULL, state TEXT NOT NULL)""")
                    db.execute("INSERT INTO creative_sessions VALUES(?,?,?)", (
                        "fixture_session", "unit_fixture",
                        json.dumps({
                            "status": "blocked", "brief": "unlogged private business concept",
                            "events": [{"result": {"error": "private original source"}}],
                        }),
                    ))
                report=client.diagnostics()
                self.assertEqual(report["jobs"]["by_state"]["failed"],1)
                self.assertEqual(report["model"]["observed_creative_sessions"],1)
                self.assertEqual(report["model"]["session_dispatch_error_results"],1)
                self.assertIn("durable_jobs_blocked_or_failed",
                              [x["code"] for x in report["diagnostics"]])
                encoded=json.dumps(report)
                for private in ("sensitive", "private original", "unlogged private",
                                "/tmp/secret"):
                    self.assertNotIn(private, encoded)
                self.assertFalse(report["truth_policy"][
                    "installed_operations_are_not_verified_execution"] is False)

    def test_mobile_startup_dashboard_uses_authenticated_data_without_embedded_secrets(self):
        self.assertIn('id="diagnostics-panel"', PAGE)
        self.assertIn('id="diagnostic-grid"', PAGE)
        self.assertIn("await api('/v1/diagnostics')", SCRIPT)
        self.assertIn("await Promise.all([tools(),jobs(),resources(),diagnostics()])", SCRIPT)
        self.assertIn("document.createElement", SCRIPT)
        self.assertIn(".textContent", SCRIPT)
        self.assertNotIn("innerHTML", SCRIPT)
        self.assertNotIn("localStorage", SCRIPT)

    @unittest.skipUnless(shutil.which("node"), "Node.js syntax checker is unavailable")
    def test_shipped_mobile_dashboard_has_valid_javascript(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"studio.js"
            path.write_text(SCRIPT,encoding="utf-8")
            subprocess.run(["node","--check",str(path)],check=True,
                           capture_output=True,text=True,timeout=15)


if __name__ == "__main__":
    unittest.main()
