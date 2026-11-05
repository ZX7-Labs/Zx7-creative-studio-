"""Cross-domain, crash-backed non-replay tests for the universal BODY gateway.

These synthetic engines only prove execution authority, durability and privacy.
They are not artistic-quality or physical-editor conformance evidence.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from studio_next.capability_attempts import (
    CapabilityAttemptError, CapabilityAttemptStore)
from studio_next.capability_gateway import (
    CapabilityExecutionError, CapabilityGateway)


REV = "a" * 64
DIGEST = "b" * 64


def tool(name):
    return SimpleNamespace(name=name, description="Installed original creative operation",
        input_schema={"type":"object", "properties":{
            "content":{"type":"string"}}})


class CreativeEngine:
    def __init__(self, name="create_layer"):
        self.operations = [tool(name)]
        self.calls = []
        self.error = None
        self.fail = False

    async def list_tools(self):
        return SimpleNamespace(tools=self.operations)

    async def call_tool(self, name, args):
        self.calls.append((name,args))
        if self.error is not None:
            raise self.error
        await asyncio.sleep(0)
        return SimpleNamespace(is_error=self.fail, content=[
            SimpleNamespace(type="text", text='{"success":true}')])


class AttemptStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private" / "attempts.sqlite3"
        self.store = CapabilityAttemptStore(self.path)

    def reserve(self, request_id="host-attempt-1"):
        self.store.admit(request_id=request_id, operation_id="graphics/create_layer",
            catalog_revision=REV,input_sha256=DIGEST)

    def test_intent_survives_process_reopen_and_never_automatically_replays(self):
        self.reserve()
        reopened = CapabilityAttemptStore(self.path)
        observed = reopened.inspect("host-attempt-1")
        self.assertEqual(observed["state"],"submitted_unconfirmed")
        self.assertEqual(observed["input_sha256"],DIGEST)
        self.assertIsNone(observed["settled_ns"])
        with self.assertRaisesRegex(CapabilityAttemptError,"already admitted"):
            reopened.admit(request_id="host-attempt-1",
                operation_id="graphics/create_layer", catalog_revision=REV,
                input_sha256=DIGEST)
        with self.assertRaises(CapabilityAttemptError):
            reopened.admit(request_id="host-attempt-1",
                operation_id="audio/create_layer",catalog_revision=REV,
                input_sha256="c"*64)

    def test_durable_pre_dispatch_crash_survives_process_death(self):
        child = (
            "import os,sys\n"
            "from studio_next.capability_attempts import CapabilityAttemptStore\n"
            "s=CapabilityAttemptStore(sys.argv[1]);"
            "s.admit(request_id='crashed-host-request',"
            "operation_id='motion/create_curve',"
            "catalog_revision='a'*64,input_sha256='b'*64)\n"
            "os._exit(37)\n"
        )
        run = subprocess.run([sys.executable,"-c",child,str(self.path)],
            check=False, timeout=20)
        self.assertEqual(run.returncode,37)
        journal = CapabilityAttemptStore(self.path)
        self.assertEqual(journal.inspect("crashed-host-request")["state"],
                         "submitted_unconfirmed")
        with self.assertRaises(CapabilityAttemptError):
            journal.admit(request_id="crashed-host-request",
                operation_id="motion/create_curve",
                catalog_revision=REV,input_sha256=DIGEST)

    def test_one_way_settlement_and_secret_free_private_journal(self):
        self.reserve()
        self.store.settle(request_id="host-attempt-1",
                          state="host_reported_success_unverified")
        self.assertEqual(self.store.inspect("host-attempt-1")["state"],
                         "host_reported_success_unverified")
        with self.assertRaises(CapabilityAttemptError):
            self.store.settle(request_id="host-attempt-1",
                              state="write_uncertain_reconciliation_required")
        with self.assertRaises(CapabilityAttemptError):
            self.store.admit(request_id="host-attempt-1",
                operation_id="graphics/create_layer",
                catalog_revision=REV,input_sha256=DIGEST)
        self.assertEqual(self.path.stat().st_mode & 0o077, 0)
        self.assertEqual(self.path.parent.stat().st_mode & 0o077, 0)
        self.assertNotIn(b"my private footage",self.path.read_bytes())

    def test_malformed_ids_and_public_or_linked_database_are_refused(self):
        for bad in ("", "../escape", "wrong secret\n", "a"*129, None):
            with self.subTest(request_id=bad),self.assertRaises(CapabilityAttemptError):
                self.store.admit(request_id=bad,operation_id="graphics/create_layer",
                    catalog_revision=REV,input_sha256=DIGEST)
        with self.assertRaises(CapabilityAttemptError):
            self.store.admit(request_id="ok",operation_id="graphics/create_layer",
                catalog_revision="not-a-digest",input_sha256=DIGEST)
        linked=Path(self.temp.name)/"linked.sqlite3"
        linked.symlink_to(self.path)
        with self.assertRaises(CapabilityAttemptError):
            CapabilityAttemptStore(linked)
        unsafe=Path(self.temp.name)/"unsafe"
        unsafe.mkdir(mode=0o755)
        unsafe.chmod(0o755)
        with self.assertRaises(CapabilityAttemptError):
            CapabilityAttemptStore(unsafe/"attempts.db")


class DurableGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"private"/"journal.sqlite3"
        self.store = CapabilityAttemptStore(self.path)
        self.graphics = CreativeEngine("create_layer")
        self.audio = CreativeEngine("create_track")

    async def _gateway(self):
        gateway = CapabilityGateway({
            "graphics": (self.graphics, {"create_layer":"write"}),
            "audio": (self.audio, {"create_track":"write"})
        }, attempt_store=CapabilityAttemptStore(self.path))
        revision = (await gateway.refresh())["revision"]
        return gateway,revision

    async def test_two_future_domains_accept_distinct_host_attempts(self):
        gateway,revision=await self._gateway()
        for operation,request,content in (
                ("graphics/create_layer","host-graphics-1","visual content"),
                ("audio/create_track","host-audio-1","sound content")):
            result=await gateway.invoke(operation,revision=revision,
                inputs={"content":content},request_id=request)
            self.assertEqual(result["state"],"host_reported_success_unverified")
            self.assertEqual(self.store.inspect(request)["state"],
                             "host_reported_success_unverified")
        self.assertEqual(len(self.graphics.calls),1)
        self.assertEqual(len(self.audio.calls),1)
        record=str(gateway.evidence())
        self.assertNotIn("visual content",record)
        self.assertNotIn("sound content",record)
        self.assertNotIn("visual content",self.path.read_bytes().decode("latin-1"))

    async def test_duplicate_host_attempt_is_refused_across_gateway_restarts(self):
        first,rev=await self._gateway()
        await first.invoke("graphics/create_layer",revision=rev,
                           inputs={"content":"Private owner original"},
                           request_id="same-host-request")
        second,new_revision=await self._gateway()
        with self.assertRaisesRegex(CapabilityAttemptError,"already admitted"):
            await second.invoke("graphics/create_layer",revision=new_revision,
                inputs={"content":"Private owner original"},request_id="same-host-request")
        self.assertEqual(len(self.graphics.calls),1)
        self.assertEqual(second.evidence(),[])

    async def test_write_without_stable_host_identity_is_never_dispatched(self):
        gateway,rev=await self._gateway()
        with self.assertRaises(CapabilityAttemptError):
            await gateway.invoke("graphics/create_layer",revision=rev,
                                 inputs={"content":"not sent"})
        self.assertEqual(self.graphics.calls,[])
        self.assertIsNone(self.store.inspect("not-sent"))

    async def test_native_transport_error_persists_as_uncertain(self):
        self.graphics.error=ConnectionError("private path must never reach ledger")
        gateway,rev=await self._gateway()
        with self.assertRaises(ConnectionError):
            await gateway.invoke("graphics/create_layer",revision=rev,
                inputs={"content":"private material"},request_id="broken-native-1")
        self.assertEqual(self.store.inspect("broken-native-1")["state"],
                         "write_uncertain_reconciliation_required")
        self.assertEqual(gateway.evidence()[0]["state"],
                         "write_uncertain_reconciliation_required")
        self.assertNotIn("private material",self.path.read_bytes().decode("latin-1"))
        self.graphics.error=None
        with self.assertRaises(CapabilityAttemptError):
            await gateway.invoke("graphics/create_layer",revision=rev,
                inputs={"content":"private material"},request_id="broken-native-1")
        self.assertEqual(len(self.graphics.calls),1)

    async def test_native_reported_write_failure_is_not_a_safe_retry(self):
        self.audio.fail=True
        gateway,rev=await self._gateway()
        result=await gateway.invoke("audio/create_track",revision=rev,
            inputs={"content":"private track"},request_id="audio-failed-1")
        self.assertEqual(result["state"],"write_uncertain_reconciliation_required")
        self.assertEqual(self.store.inspect("audio-failed-1")["state"],
                         "write_uncertain_reconciliation_required")
        self.assertEqual(len(self.audio.calls),1)

    async def test_invalid_or_ungranted_inputs_never_enter_durable_ledger(self):
        gateway,rev=await self._gateway()
        with self.assertRaises(CapabilityExecutionError):
            await gateway.invoke("graphics/create_layer",revision=rev,
                inputs={"not_declared":"sensitive"},request_id="rejected-1")
        self.assertEqual(self.graphics.calls,[])
        self.assertIsNone(self.store.inspect("rejected-1"))

    async def test_concurrent_duplicate_request_admitted_once(self):
        gateway,rev=await self._gateway()
        async def once():
            return await gateway.invoke("audio/create_track",revision=rev,
                inputs={"content":"a"},request_id="concurrent-1")
        results=await asyncio.gather(once(),once(),return_exceptions=True)
        self.assertEqual(sum(isinstance(x,CapabilityAttemptError)
                             for x in results),1)
        self.assertEqual(sum(isinstance(x,dict) for x in results),1)
        self.assertEqual(len(self.audio.calls),1)


if __name__=="__main__":
    unittest.main()
