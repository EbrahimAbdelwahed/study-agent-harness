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
    map_internal_failure,
)


def translate_exception(
    error: BaseException, *, correlation_id: object | None = None
) -> HarnessError:
    """Map known dependency families to safe public failures.

    The original exception is retained only as ``__cause__`` for local
    diagnostics.  Its message, class, traceback, and backend details never
    enter the serialized failure document.
    """

    if isinstance(error, HarnessError):
        return error

    error_name = type(error).__name__
    failure: HarnessError
    if error_name in {"SequenceConflictError", "EventSequenceConflictError"}:
        failure = StaleFailure(
            "the durable stream changed before commit", correlation_id=correlation_id
        )
    elif error_name in {"IdempotencyConflictError", "ConflictError"}:
        failure = ConflictFailure("idempotency input conflicts", correlation_id=correlation_id)
    elif isinstance(error, sqlite3.Error):
        failure = UnavailableDependencyFailure(
            "storage dependency is unavailable",
            retryable=True,
            correlation_id=correlation_id,
        )
    elif isinstance(error, FileNotFoundError):
        failure = NotFoundFailure("requested resource was not found", correlation_id=correlation_id)
    elif isinstance(error, PermissionError):
        failure = UnauthorizedFailure("operation is not authorized", correlation_id=correlation_id)
    elif type(error).__module__.startswith("study_agent.adapters") or isinstance(
        error, (TimeoutError, ConnectionError, OSError)
    ):
        failure = UnavailableDependencyFailure(
            "external dependency is unavailable",
            retryable=True,
            correlation_id=correlation_id,
        )
    elif _is_model_error(error):
        failure = _translate_model_error(error, correlation_id=correlation_id)
    elif isinstance(error, LookupError):
        failure = NotFoundFailure("requested resource was not found", correlation_id=correlation_id)
    elif isinstance(error, (TypeError, ValueError, KeyError)):
        failure = ValidationFailure("request failed validation", correlation_id=correlation_id)
    else:
        failure = map_internal_failure(error, correlation_id=correlation_id)

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
            "model dependency is unavailable",
            retryable=True,
            correlation_id=correlation_id,
        )
    if code == "cancelled":
        return ValidationFailure(
            "model operation was cancelled", correlation_id=correlation_id
        )
    if code in {"protocol_error", "unsupported_operation"}:
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
    """Translate the legacy private ``StudyError`` code vocabulary explicitly."""

    if not isinstance(error, StudyError):
        raise TypeError("error must be StudyError")
    if error.code in {ErrorCode.INVALID_INPUT, ErrorCode.VALIDATION_ERROR}:
        failure: HarnessError = ValidationFailure(error.message, correlation_id=correlation_id)
    elif error.code is ErrorCode.NOT_FOUND:
        failure = NotFoundFailure("requested resource was not found", correlation_id=correlation_id)
    elif error.code is ErrorCode.CONFLICT:
        failure = ConflictFailure(
            "request conflicts with canonical state", correlation_id=correlation_id
        )
    elif error.code in {
        ErrorCode.MODEL_UNAVAILABLE,
        ErrorCode.RETRIEVAL_ERROR,
        ErrorCode.PERSISTENCE_ERROR,
    }:
        failure = UnavailableDependencyFailure(
            "a required dependency is unavailable",
            retryable=error.retryable,
            correlation_id=correlation_id,
        )
    elif error.code is ErrorCode.CANCELLED:
        failure = ValidationFailure("operation was cancelled", correlation_id=correlation_id)
    elif error.code is ErrorCode.UNSUPPORTED_CAPABILITY:
        failure = NotFoundFailure(
            "requested capability is unavailable", correlation_id=correlation_id
        )
    else:
        failure = InternalFailure("operation failed safely", correlation_id=correlation_id)
    return failure


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
