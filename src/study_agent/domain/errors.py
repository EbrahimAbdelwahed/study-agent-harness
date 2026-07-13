from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ._validation import JsonObject, freeze_object, require_text


class ErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SOURCE_INTEGRITY_ERROR = "source_integrity_error"
    RETRIEVAL_ERROR = "retrieval_error"
    MODEL_UNAVAILABLE = "model_unavailable"
    MODEL_PROTOCOL_ERROR = "model_protocol_error"
    VALIDATION_ERROR = "validation_error"
    PERSISTENCE_ERROR = "persistence_error"
    CANCELLED = "cancelled"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass(frozen=True, slots=True)
class StudyError:
    code: ErrorCode
    message: str
    retryable: bool = False
    details: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.message, "message")
        object.__setattr__(self, "details", freeze_object(self.details))
