from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

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


# PF-02's facade error values intentionally live beside the legacy internal
# ``StudyError`` value.  Existing application services still consume the latter;
# new facade ports consume only this closed taxonomy.
_SECRET_FIELD = re.compile(
    r"(?:api[_-]?key|authorization|cookie|credential|password|secret|token|prompt|"
    r"chain[-_ ]of[-_ ]thought|traceback|stack[_ -]?trace|exception|provider)",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|authorization|cookie|credential|password|secret|token)\s*[:=]\s*[^\s,;]+"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_SECRET_VALUE = re.compile(r"(?i)\bsk-[A-Za-z0-9_-]+\b|-----BEGIN [^-]+-----")


def _safe_message(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "operation failed safely"
    message = value.strip()
    has_secret_field = _SECRET_FIELD.search(message) and not _SECRET_ASSIGNMENT.search(message)
    if has_secret_field or _SECRET_VALUE.search(message):
        return "operation failed safely"
    message = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", message)
    message = _BEARER.sub("Bearer [REDACTED]", message)
    return message


def _safe_value(value: object, *, key: str | None = None) -> object:
    if key is not None and _SECRET_FIELD.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(item_key): _safe_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (tuple, list)):
        return tuple(_safe_value(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _safe_message(value) if isinstance(value, str) else value
    return "[REDACTED]"


def _freeze_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_safe(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_safe(item) for item in value)
    return value


class HarnessError(RuntimeError):
    """Facade-visible base for the seven safe public failure categories."""

    code = "internal"
    default_retryable = False

    def __init__(
        self,
        message: str = "operation failed safely",
        *,
        retryable: bool | None = None,
        correlation_id: object | None = None,
        details: Mapping[str, object] | None = None,
    ) -> None:
        if retryable is not None and type(retryable) is not bool:
            raise TypeError("retryable must be a boolean")
        self.message = _safe_message(message)
        self.retryable = self.default_retryable if retryable is None else retryable
        self.correlation_id = None if correlation_id is None else str(correlation_id)
        if self.correlation_id == "":
            raise ValueError("correlation_id must be non-empty when supplied")
        safe_details = _safe_value(details or {})
        if not isinstance(safe_details, Mapping):  # pragma: no cover - narrowed by input
            raise TypeError("details must be a mapping")
        frozen_details = _freeze_safe(safe_details)
        if not isinstance(frozen_details, Mapping):  # pragma: no cover - narrowed above
            raise TypeError("details must be a mapping")
        self.details = frozen_details
        super().__init__(self.message)

    def to_json(self) -> dict[str, object]:
        """Return a stable JSON-safe public failure document."""

        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "correlation_id": self.correlation_id,
            "details": _safe_value(self.details),
        }

    def as_dict(self) -> dict[str, object]:
        return self.to_json()

    def serialize(self) -> bytes:
        return json.dumps(
            self.to_json(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def __str__(self) -> str:
        return self.message


class ValidationFailure(HarnessError):
    code = "validation"


class StaleFailure(HarnessError):
    code = "stale"
    default_retryable = True


class UnauthorizedFailure(HarnessError):
    code = "unauthorized"


class ConflictFailure(HarnessError):
    code = "conflict"


class NotFoundFailure(HarnessError):
    code = "not_found"


class UnavailableDependencyFailure(HarnessError):
    code = "unavailable_dependency"
    default_retryable = True


class InternalFailure(HarnessError):
    code = "internal"


def map_internal_failure(
    error: BaseException, *, correlation_id: object | None = None
) -> HarnessError:
    """Map an implementation exception without importing adapter packages.

    The application translation layer supplies richer provider/SQLite mappings;
    this dependency-free fallback keeps domain code safe if an unknown adapter
    crosses the boundary.
    """

    if isinstance(error, HarnessError):
        return error
    module = type(error).__module__
    name = type(error).__name__
    failure: HarnessError
    if name in {"SequenceConflictError", "EventSequenceConflictError"}:
        failure = StaleFailure(correlation_id=correlation_id)
    elif name in {"IdempotencyConflictError", "ConflictError"}:
        failure = ConflictFailure(correlation_id=correlation_id)
    elif name in {"ValidationError", "EventBatchError"} or isinstance(
        error, (TypeError, ValueError)
    ):
        failure = ValidationFailure(correlation_id=correlation_id)
    elif name in {
        "NotFoundError",
        "CourseNotFoundError",
        "SessionNotFoundError",
        "BlobNotFoundError",
    } or isinstance(error, LookupError):
        failure = NotFoundFailure(correlation_id=correlation_id)
    elif name in {"PermissionError", "AuthenticationError"}:
        failure = UnauthorizedFailure(correlation_id=correlation_id)
    elif module.startswith("sqlite3") or module.startswith("study_agent.adapters") or isinstance(
        error, (OSError, TimeoutError, ConnectionError)
    ):
        failure = UnavailableDependencyFailure(correlation_id=correlation_id)
    else:
        failure = InternalFailure(correlation_id=correlation_id)
    failure.__cause__ = error
    return failure


__all__ = [
    "ConflictFailure",
    "ErrorCode",
    "HarnessError",
    "InternalFailure",
    "NotFoundFailure",
    "StaleFailure",
    "StudyError",
    "UnauthorizedFailure",
    "UnavailableDependencyFailure",
    "ValidationFailure",
    "map_internal_failure",
]
