"""Translate private adapter and domain exceptions at the application facade."""

from __future__ import annotations

import sqlite3

from study_agent.domain.errors import (
    ConflictFailure,
    ErrorCode,
    HarnessError,
    InternalFailure,
    NotFoundFailure,
    StaleFailure,
    StudyError,
    UnauthorizedFailure,
    UnavailableDependencyFailure,
    ValidationFailure,
)

_ERROR_CODE_TO_FAILURE: dict[ErrorCode, type[HarnessError]] = {
    ErrorCode.INVALID_INPUT: ValidationFailure,
    ErrorCode.VALIDATION_ERROR: ValidationFailure,
    ErrorCode.INSUFFICIENT_EVIDENCE: ValidationFailure,
    ErrorCode.CANCELLED: ValidationFailure,
    ErrorCode.BUDGET_EXCEEDED: ValidationFailure,
    ErrorCode.NOT_FOUND: NotFoundFailure,
    ErrorCode.UNSUPPORTED_CAPABILITY: NotFoundFailure,
    ErrorCode.CONFLICT: ConflictFailure,
    ErrorCode.SOURCE_INTEGRITY_ERROR: ConflictFailure,
    ErrorCode.RETRIEVAL_ERROR: UnavailableDependencyFailure,
    ErrorCode.MODEL_UNAVAILABLE: UnavailableDependencyFailure,
    ErrorCode.MODEL_PROTOCOL_ERROR: UnavailableDependencyFailure,
    ErrorCode.PERSISTENCE_ERROR: UnavailableDependencyFailure,
}

if set(_ERROR_CODE_TO_FAILURE) != set(ErrorCode):  # pragma: no cover - import guard
    raise RuntimeError("every ErrorCode must have an explicit public failure mapping")


def translate_exception(
    error: BaseException, *, correlation_id: object | None = None
) -> HarnessError:
    """Map known dependency families to safe public failures.

    The original exception is retained only as a local ``__cause__``. It is
    never included in the public failure document.
    """

    if isinstance(error, HarnessError):
        return error

    error_name = type(error).__name__
    if error_name in {"SequenceConflictError", "EventSequenceConflictError"}:
        failure: HarnessError = StaleFailure(
            "the durable stream changed before commit", correlation_id=correlation_id
        )
    elif error_name in {"IdempotencyConflictError", "ConflictError"}:
        failure = ConflictFailure("idempotency input conflicts", correlation_id=correlation_id)
    elif error_name in {"AuthenticationError", "UnauthorizedError"} or isinstance(
        error, PermissionError
    ):
        failure = UnauthorizedFailure("operation is not authorized", correlation_id=correlation_id)
    elif isinstance(error, FileNotFoundError):
        failure = NotFoundFailure("requested resource was not found", correlation_id=correlation_id)
    elif isinstance(error, sqlite3.Error):
        failure = UnavailableDependencyFailure(
            "storage dependency is unavailable", retryable=True, correlation_id=correlation_id
        )
    elif _is_model_error(error):
        failure = _translate_model_error(error, correlation_id=correlation_id)
    elif type(error).__module__.startswith("study_agent.adapters") or isinstance(
        error, (TimeoutError, ConnectionError, OSError)
    ):
        failure = UnavailableDependencyFailure(
            "external dependency is unavailable", retryable=True, correlation_id=correlation_id
        )
    elif isinstance(error, LookupError):
        failure = NotFoundFailure("requested resource was not found", correlation_id=correlation_id)
    elif isinstance(error, (TypeError, ValueError, KeyError)):
        failure = ValidationFailure("request failed validation", correlation_id=correlation_id)
    else:
        failure = InternalFailure("operation failed safely", correlation_id=correlation_id)

    failure.__cause__ = error
    return failure


def _is_model_error(error: BaseException) -> bool:
    return type(error).__name__ == "ModelError" and hasattr(error, "code")


def _translate_model_error(
    error: BaseException, *, correlation_id: object | None = None
) -> HarnessError:
    code = str(getattr(getattr(error, "code", None), "value", getattr(error, "code", "")))
    if code == "authentication":
        return UnauthorizedFailure(
            "model dependency is not authorized", correlation_id=correlation_id
        )
    if code in {"unavailable", "rate_limited", "timeout"}:
        return UnavailableDependencyFailure(
            "model dependency is unavailable", retryable=True, correlation_id=correlation_id
        )
    if code == "cancelled":
        return ValidationFailure("model operation was cancelled", correlation_id=correlation_id)
    if code == "protocol_error":
        return UnavailableDependencyFailure(
            "model dependency returned an invalid response",
            retryable=False,
            correlation_id=correlation_id,
        )
    if code == "unsupported_operation":
        return ValidationFailure(
            "model dependency returned an invalid response", correlation_id=correlation_id
        )
    return InternalFailure("model dependency failed safely", correlation_id=correlation_id)


def failure_from_exception(
    error: BaseException, *, correlation_id: object | None = None
) -> HarnessError:
    """Compatibility spelling for callers that use explicit failure mapping."""

    return translate_exception(error, correlation_id=correlation_id)


def translate_study_error(
    error: StudyError, *, correlation_id: object | None = None
) -> HarnessError:
    """Translate every legacy ``StudyError`` code through one exhaustive table."""

    if not isinstance(error, StudyError):
        raise TypeError("error must be StudyError")
    failure_type = _ERROR_CODE_TO_FAILURE[error.code]
    retryable = error.retryable if failure_type is UnavailableDependencyFailure else None
    return failure_type(
        "operation failed safely", retryable=retryable, correlation_id=correlation_id
    )


__all__ = [
    "ConflictFailure",
    "HarnessError",
    "InternalFailure",
    "NotFoundFailure",
    "StaleFailure",
    "UnauthorizedFailure",
    "UnavailableDependencyFailure",
    "ValidationFailure",
    "failure_from_exception",
    "translate_exception",
    "translate_study_error",
]
