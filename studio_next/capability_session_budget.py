"""Host-owned, concurrency-safe invocation budget for every BODY engine.

A reservation is an *admission slot*, not a measured token, cost, physical
native edit or successful tool invocation. Failed/uncertain submissions and
durable request-ID conflicts are deliberately not refunded. The budget lives
only as long as this owner process; enforcing quotas across process restarts
requires a separate durable authority.
"""
from __future__ import annotations

from collections.abc import Mapping
import re
from threading import Lock


class CapabilitySessionBudgetError(ValueError):
    """Safe host-side refusal; no private model/tool data in its reason."""


_NAMESPACE = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
_MAX_LIMIT = 1_000_000


class CapabilitySessionBudget:
    """Optional host-created ceilings shared by independent creative engines.

    Brain proposals never create, relax or reset these limits. A reservation
    is atomic even when separate engines run concurrently; admission does not
    prove the remote engine executed the requested operation.
    """

    def __init__(self, *, max_calls: int, max_writes: int,
                 per_source: Mapping[str, int] | None = None):
        if (type(max_calls) is not int or not 0 <= max_calls <= _MAX_LIMIT or
                type(max_writes) is not int or not 0 <= max_writes <= max_calls):
            raise CapabilitySessionBudgetError("invalid_host_execution_budget")
        if per_source is None:
            per_source = {}
        if (not isinstance(per_source, Mapping) or len(per_source) > 256 or
                any(not isinstance(k, str) or not _NAMESPACE.fullmatch(k) or
                    type(v) is not int or not 0 <= v <= max_calls
                    for k, v in per_source.items())):
            raise CapabilitySessionBudgetError("invalid_host_source_budget")
        self._max_calls = max_calls
        self._max_writes = max_writes
        self._per_source = dict(per_source)
        self._lock = Lock()
        self._calls = 0
        self._writes = 0
        self._counts: dict[str, int] = {}

    def validate_sources(self, names):
        """Do not silently ignore a misspelled host source quota."""
        if not self._per_source.keys() <= set(names):
            raise CapabilitySessionBudgetError("unknown_host_budget_source")

    def reserve(self, *, source: str, access: str):
        """Atomic, conservative slot reservation before durable/native work."""
        if (not isinstance(source, str) or not _NAMESPACE.fullmatch(source)
                or access not in ("read", "write")):
            raise CapabilitySessionBudgetError("invalid_capability_budget_request")
        with self._lock:
            if self._calls >= self._max_calls:
                raise CapabilitySessionBudgetError(
                    "host_session_call_budget_exhausted")
            if access == "write" and self._writes >= self._max_writes:
                raise CapabilitySessionBudgetError(
                    "host_session_write_budget_exhausted")
            limit = self._per_source.get(source)
            if limit is not None and self._counts.get(source, 0) >= limit:
                raise CapabilitySessionBudgetError(
                    "host_source_call_budget_exhausted")
            self._calls += 1
            if access == "write":
                self._writes += 1
            self._counts[source] = self._counts.get(source, 0) + 1

    def snapshot(self):
        """Host-only accounting, with no original media or model arguments."""
        with self._lock:
            return {
                "scope": "in_process_admission_reservations_only",
                "limit_calls": self._max_calls,
                "limit_writes": self._max_writes,
                "reserved_calls": self._calls,
                "reserved_writes": self._writes,
                "reserved_calls_by_source": dict(sorted(self._counts.items())),
                "does_not_measure_tokens_cost_or_native_commit": True,
                "not_durable_across_process_restarts": True,
            }
