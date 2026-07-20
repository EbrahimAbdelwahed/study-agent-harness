"""Durable ownership seam for verified generated artifact batches."""

from __future__ import annotations

from typing import Protocol

from study_agent.domain import RunId


class GeneratedBatchOwnerStore(Protocol):
    """Atomic canonical owner slot keyed only by the verified child run."""

    def create(self, child_run_id: RunId, payload: bytes) -> bool: ...

    def load(self, child_run_id: RunId) -> bytes: ...


__all__ = ["GeneratedBatchOwnerStore"]
