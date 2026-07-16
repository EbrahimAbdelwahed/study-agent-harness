from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import replace

import pytest

from study_agent.capabilities import (
    CompletedCapabilityOutcome,
    GatewayIsolatedCapabilityRunAdapter,
)
from study_agent.domain import RunId
from study_agent.workers import GenerationWorkerService, GenerationWorkerStatus
from study_agent.workers.proof import VerifiedChildProofOwner
from tests.unit.capabilities.test_gateway_worker_adapter import (
    OUTPUT,
    MemoryProofStore,
    RecordingGateway,
    _binding,
    _completed_run,
    _parent,
    _task,
)


class MemoryWorkerStore:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def create(self, task_id: str, payload: bytes) -> bool:
        if task_id in self.values:
            return False
        self.values[task_id] = payload
        return True

    def compare_and_set(self, task_id: str, expected: bytes, replacement: bytes) -> bool:
        if self.values[task_id] != expected:
            return False
        self.values[task_id] = replacement
        return True

    def load(self, task_id: str) -> bytes:
        return self.values[task_id]


class CrashAfterProofWorkerStore(MemoryWorkerStore):
    def __init__(self) -> None:
        super().__init__()
        self.crash_once = True

    def compare_and_set(self, task_id: str, expected: bytes, replacement: bytes) -> bool:
        if self.crash_once:
            self.crash_once = False
            raise RuntimeError("crash after proof ownership")
        return super().compare_and_set(task_id, expected, replacement)


class FailingProofStore(MemoryProofStore):
    def create(self, run_id: RunId, payload: bytes) -> bool:
        del run_id, payload
        raise OSError("proof storage unavailable")


def _service(
    worker_store: MemoryWorkerStore,
    proof_store: MemoryProofStore,
    run,
) -> tuple[GenerationWorkerService, RecordingGateway]:
    gateway = RecordingGateway(CompletedCapabilityOutcome(run, OUTPUT))
    adapter = GatewayIsolatedCapabilityRunAdapter(
        gateway=gateway,
        bindings=(_binding(),),
        proof_owner=VerifiedChildProofOwner(proof_store),
    )
    return GenerationWorkerService(store=worker_store, isolated_runs=adapter), gateway


def _run[T](awaitable: Coroutine[object, object, T]) -> T:
    return asyncio.run(awaitable)


def test_crash_after_atomic_proof_create_recovers_without_a_second_owner_slot() -> None:
    worker_store = CrashAfterProofWorkerStore()
    proof_store = MemoryProofStore()
    service, gateway = _service(worker_store, proof_store, _completed_run())
    with pytest.raises(RuntimeError, match="crash after proof"):
        _run(service.start(_task(), _parent()))
    assert tuple(proof_store.values) == (RunId("child-run-1"),)

    restarted, retry_gateway = _service(worker_store, proof_store, _completed_run())
    view = _run(restarted.start(_task(), _parent()))
    assert view.status is GenerationWorkerStatus.COMPLETED
    assert tuple(proof_store.values) == (RunId("child-run-1"),)
    assert len(gateway.calls) == len(retry_gateway.calls) == 1

    terminal_retry = _run(restarted.start(_task(), _parent()))
    assert terminal_retry == view
    assert len(retry_gateway.calls) == 1


def test_proof_store_failure_is_durable_failed_before_worker_completion() -> None:
    worker_store = MemoryWorkerStore()
    service, gateway = _service(worker_store, FailingProofStore(), _completed_run())
    view = _run(service.start(_task(), _parent()))
    assert view.status is GenerationWorkerStatus.FAILED
    assert view.failure_code == "failed"
    assert not view.verified_detail_available
    assert len(gateway.calls) == 1


def test_oversize_sanitized_tool_proof_fails_before_worker_completion() -> None:
    run = _completed_run()
    outputs = dict(run.outputs)
    outputs["evidence"] = {"items": ({"text": "x" * (512 * 1024)},)}
    oversized = replace(run, outputs=outputs)
    service, gateway = _service(MemoryWorkerStore(), MemoryProofStore(), oversized)
    view = _run(service.start(_task(), _parent()))
    assert view.status is GenerationWorkerStatus.FAILED
    assert view.failure_code == "failed"
    assert len(gateway.calls) == 1
