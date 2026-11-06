"""Trusted renewable render-stage execution lease for long-running filmmakers.

A stage may be physically rendering for hours. The old fixed 3600-second
lease could expire before rendering finishes, making another worker entitled
to retry the very same tool while it is still publishing real media.

This module has NO model/tool-network capability and never changes creative
intent. It only renews the exact SQLite row already acquired by the host,
so an expired/crashed owner cannot regain a stolen lease. Failure is fatal
for proof publication; the body's previous error/recovery semantics remain.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

from .durable_graph import RecoveryBlocked


class RunningStageHeartbeat:
    def __init__(self,store,project,node,input_key,owner,*,lease_seconds):
        self.store=store
        self.project=project
        self.node=node
        self.key=input_key
        self.owner=owner
        self.seconds=lease_seconds
        self.interval=min(30.0,max(.0125,float(lease_seconds)/4))
        self._stop=threading.Event()
        self._thread=None
        self._failure=None
        # Coordinate a potentially slow fsync with the heartbeat: during
        # publication, the SQLite owner transaction itself blocks takeover.
        self._publication_lock=threading.RLock()

    def _pulse(self):
        while not self._stop.wait(self.interval):
            try:
                with self._publication_lock:
                    if self._stop.is_set():
                        return
                    actual=self.store.renew_running_lease(
                        self.project,self.node,self.key,self.owner,self.seconds)
                    if actual is not True:
                        raise RecoveryBlocked(
                            "Original render lease was lost to another worker")
            except BaseException as exc:
                self._failure=exc
                self._stop.set()
                return

    @contextmanager
    def publication_guard(self):
        """Hold current host ownership across the final filesystem commit.

        The regular pulse waits rather than falsely timing out on the same
        transaction. SQLite still prevents other processes from taking over.
        """
        with self._publication_lock:
            if (self._thread is None or self._stop.is_set()
                    or self._failure is not None):
                raise RecoveryBlocked("Renderer has no active publication lease")
            with self.store.publication_lease(
                    self.project,self.node,self.key,self.owner,
                    lease_seconds=self.seconds):
                yield

    def start(self):
        if self._thread is not None:
            raise RuntimeError("One original render must have only one lease owner")
        self._thread=threading.Thread(target=self._pulse,
               daemon=True,name="zx7-verified-render-lease")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=15)
            if self._thread.is_alive():
                raise RecoveryBlocked("Original render lease renewal did not terminate")
        if self._failure is not None:
            raise RecoveryBlocked(
                "Original renderer lost its durable lease: "+
                type(self._failure).__name__+": "+str(self._failure))

    def abort(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=15)
