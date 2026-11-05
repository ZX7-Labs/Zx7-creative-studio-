"""Operator-run diagnostic service tests using local-only, TEST-ONLY model stubs.

The adapter is intentionally monkeypatched: these results are NOT proof of
real weights, actual neural competence or creative quality. Their only job is
to verify the opt-in session, host-authenticated endpoints, and redaction.
"""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from studio_next.body_service import LocalBodyCoordinator, make_body_http_handler
from studio_next.body_client import ZX7BodyClient
from studio_next.providers import LocalCreativeModel, LocalModelSettings


def fixture_decision(self, context):
    """A deliberate test double, never a model quality rating."""
    task=context["task"]
    if "Convert physical video frame index" in task:
        return {"operation_id":"zx7/body.timecode_format",
                "inputs":{"numerator":24,"denominator":1,
                          "frame_index":240,"drop_frame":False}}
    if "Read an already written SMPTE" in task:
        return {"operation_id":"zx7/body.timecode_parse",
                "inputs":{"numerator":24,"denominator":1,
                          "timecode":"00:00:10:00"}}
    if "local voice identities" in task:
        return {"operation_id":"zx7/body.voice_inventory",
                "inputs":{"voice_assets":"voice-fixture-name"}}
    raise AssertionError("Unexpected operator-owned test objective")


class LocalModelAuditionEndpointTests(unittest.TestCase):
    def test_real_authenticated_host_runs_bounded_opt_in_without_body_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            model=LocalCreativeModel(LocalModelSettings(
                model_id="local-fixture-only-not-neural",
                base_url="http://127.0.0.1:8080"))
            with patch.object(LocalCreativeModel,"decide",autospec=True,
                              side_effect=fixture_decision) as mock:
                host=LocalBodyCoordinator(root/"host",creative_model=model)
                token="operator-test-only-"+"q"*48
                server=ThreadingHTTPServer(("127.0.0.1",0),
                                          make_body_http_handler(host,token))
                worker=threading.Thread(target=server.serve_forever,daemon=True)
                worker.start()
                try:
                    client=ZX7BodyClient(endpoint=f"http://127.0.0.1:{server.server_port}",
                                         token=token)
                    before=client.diagnostics()
                    self.assertEqual(before["model"][
                        "operator_initiated_tool_audition"]["status"],"unmeasured")
                    self.assertEqual(mock.call_count,0)
                    response=client.start_model_audition()
                    self.assertEqual(len(response["run_id"]),32)
                    deadline=time.monotonic()+12
                    while time.monotonic()<deadline:
                        status=client.model_audition(response["run_id"])
                        if status["status"] not in ("queued","running"):
                            break
                        time.sleep(.04)
                    self.assertEqual(status["status"],
                                     "completed_measured_not_creative_certification")
                    self.assertEqual(status["cases_recorded"],3)
                    self.assertEqual(mock.call_count,3)
                    self.assertEqual(status["summary"]["matching_tool_and_schema_count"],3)
                    self.assertFalse(status["model_weights_physically_attested"])
                    self.assertTrue(status["no_tool_mutations_executed"])
                    self.assertFalse((root/"host"/"projects").joinpath(
                        "fixture","movies").exists())
                    report=client.diagnostics()
                    measured=report["model"]["operator_initiated_tool_audition"]
                    self.assertEqual(measured["status"],
                                     "completed_measured_not_creative_certification")
                    self.assertEqual(measured["summary"]["evaluated_case_count"],3)
                    self.assertEqual(report["model"]["independent_creativity"],"unmeasured")
                    self.assertIn("model_tool_contract_cases_recorded",
                        [e["code"] for e in report["execution_traces"]["recent_events"]])
                    with self.assertRaises(RuntimeError):
                        client.start_model_audition()
                    self.assertEqual(mock.call_count,3)

                    conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=4)
                    try:
                        conn.request("POST","/v1/diagnostics/audition",
                                     headers={"Content-Length":"0"})
                        reply=conn.getresponse()
                        self.assertEqual(reply.status,401)
                        reply.read()
                    finally:
                        conn.close()
                    as_text=json.dumps(report,ensure_ascii=False)
                    self.assertNotIn("fixture_decision",as_text)
                    self.assertNotIn("http://127.0.0.1:8080",as_text)
                    self.assertNotIn("voice-fixture-name",as_text)
                finally:
                    server.shutdown()
                    server.server_close()
                    worker.join(timeout=5)
                    host.close()

    def test_bounded_caller_substitution_is_refused_before_model_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            model=LocalCreativeModel(LocalModelSettings(
                model_id="test-only",base_url="http://127.0.0.1:8080"))
            host=LocalBodyCoordinator(Path(temporary)/"host",creative_model=model)
            token="operator-test-only-"+"q"*48
            server=ThreadingHTTPServer(("127.0.0.1",0),
                                      make_body_http_handler(host,token))
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            try:
                conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=4)
                try:
                    conn.request("POST","/v1/diagnostics/audition",
                                 body=b'{"task":"execute tool"}',
                                 headers={"Authorization":"Bearer "+token,
                                          "Content-Type":"application/json"})
                    response=conn.getresponse()
                    self.assertEqual(response.status,409)
                    body=response.read().decode()
                    self.assertIn("no caller-authored",body)
                finally:conn.close()
                latest=ZX7BodyClient(
                    endpoint=f"http://127.0.0.1:{server.server_port}",
                    token=token).model_audition()
                self.assertEqual(latest["status"],"unmeasured")
            finally:
                server.shutdown();server.server_close()
                worker.join(timeout=5);host.close()


if __name__=="__main__":
    unittest.main()
