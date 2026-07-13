from __future__ import annotations

import inspect

from study_agent.domain import RunId
from study_agent.ports import RunStore


class AtomicMemoryRunStore:
    def __init__(self) -> None:
        self.data: dict[RunId, bytes] = {}

    def create(self, run_id: RunId, payload: bytes) -> bool:
        if run_id in self.data:
            return False
        self.data[run_id] = payload
        return True

    def compare_and_set(self, run_id: RunId, expected: bytes, replacement: bytes) -> bool:
        if self.data.get(run_id) != expected:
            return False
        self.data[run_id] = replacement
        return True

    def load(self, run_id: RunId) -> bytes:
        return self.data[run_id]


def test_run_store_contract_exposes_atomic_create_and_compare_and_set() -> None:
    members = dict(inspect.getmembers(RunStore))
    assert {"create", "compare_and_set", "load"} <= members.keys()


def test_atomic_run_store_semantics_reject_duplicate_and_stale_writers() -> None:
    store = AtomicMemoryRunStore()
    run_id = RunId("run-1")

    assert store.create(run_id, b"running")
    assert not store.create(run_id, b"duplicate")
    assert not store.compare_and_set(run_id, b"stale", b"replacement")
    assert store.compare_and_set(run_id, b"running", b"suspended")
    assert store.load(run_id) == b"suspended"
