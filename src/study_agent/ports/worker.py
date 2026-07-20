"""Inward operational ports for isolated generation workers."""

from __future__ import annotations

from typing import Protocol

from study_agent.capabilities.contracts import CapabilityContinuation
from study_agent.domain import ExecutionContext, RunId
from study_agent.domain._validation import JsonValue
from study_agent.workers.contracts import (
    ChildCapabilityObservation,
    GenerationWorkerTask,
)


class GenerationWorkerStore(Protocol):
    """Atomic byte store for one exact worker task state."""

    def create(self, task_id: str, payload: bytes) -> bool: ...

    def compare_and_set(self, task_id: str, expected: bytes, replacement: bytes) -> bool: ...

    def load(self, task_id: str) -> bytes: ...


class IsolatedCapabilityRunPort(Protocol):
    """Execute a named capability without exposing its gateway implementation."""

    async def start(
        self, task: GenerationWorkerTask, context: ExecutionContext
    ) -> ChildCapabilityObservation: ...

    async def resume(
        self,
        task: GenerationWorkerTask,
        continuation: CapabilityContinuation,
        response: JsonValue,
        context: ExecutionContext,
    ) -> ChildCapabilityObservation: ...


class VerifiedChildProofStore(Protocol):
    """Atomic canonical proof slot keyed by a child capability run."""

    def create(self, run_id: RunId, payload: bytes) -> bool: ...

    def load(self, run_id: RunId) -> bytes: ...
