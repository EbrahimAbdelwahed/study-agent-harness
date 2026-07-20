"""Sanitized application views for isolated generation workers."""

from __future__ import annotations

from dataclasses import dataclass

from study_agent.domain._validation import JsonValue, freeze_json
from study_agent.domain.identifiers import RunId

from .contracts import (
    GenerationWorkerReceipt,
    GenerationWorkerStatus,
    GenerationWorkerTaskKind,
)


@dataclass(frozen=True, slots=True)
class WorkerCompactView:
    task_id: str
    task_kind: GenerationWorkerTaskKind
    status: GenerationWorkerStatus
    generation: int
    task_fingerprint: str
    child_run_id: RunId | None
    receipt_fingerprint: str | None
    failure_code: str | None
    verified_detail_available: bool

    def __post_init__(self) -> None:
        if type(self.generation) is not int or self.generation < 0:
            raise ValueError("worker generation must be non-negative")
        if self.status is GenerationWorkerStatus.COMPLETED:
            if not self.verified_detail_available:
                raise ValueError("completed workers must expose verified detail availability")
        elif self.verified_detail_available:
            raise ValueError("only completed workers can expose verified detail")


@dataclass(frozen=True, slots=True)
class WorkerDetailView:
    receipt: GenerationWorkerReceipt
    output: JsonValue

    def __post_init__(self) -> None:
        if self.receipt.status is not GenerationWorkerStatus.COMPLETED:
            raise ValueError("worker detail requires a completed receipt")
        object.__setattr__(self, "output", freeze_json(self.output))
