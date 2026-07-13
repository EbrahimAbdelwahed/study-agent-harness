from __future__ import annotations

from dataclasses import dataclass

from ._validation import require_text
from .events import PrincipalKind
from .identifiers import CorrelationId, CourseId, ModelRunId, SessionId


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    principal_kind: PrincipalKind
    principal_id: str
    course_id: CourseId
    correlation_id: CorrelationId
    requested_capabilities: frozenset[str] = frozenset()
    session_id: SessionId | None = None
    model_run_id: ModelRunId | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_capabilities", frozenset(self.requested_capabilities))
        require_text(self.principal_id, "principal_id")
        for capability in self.requested_capabilities:
            require_text(capability, "requested capability")
        if self.idempotency_key is not None:
            require_text(self.idempotency_key, "idempotency_key")
