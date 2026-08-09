from __future__ import annotations

import json
import math
import sqlite3
from typing import cast

import pytest

from study_agent.api.authority import (
    ConflictFailure,
    HarnessError,
    InternalFailure,
    NotFoundFailure,
    StaleFailure,
    UnauthorizedFailure,
    UnavailableDependencyFailure,
    ValidationFailure,
    translate_exception,
    translate_study_error,
)
from study_agent.application.errors import _ERROR_CODE_TO_FAILURE
from study_agent.domain.errors import ErrorCode, StudyError

PUBLIC_FAILURES = (
    ValidationFailure,
    StaleFailure,
    UnauthorizedFailure,
    ConflictFailure,
    NotFoundFailure,
    UnavailableDependencyFailure,
    InternalFailure,
)


def test_public_failure_taxonomy_is_closed_and_safe() -> None:
    assert set(HarnessError.__subclasses__()) == set(PUBLIC_FAILURES)

    failure = ValidationFailure(
        "request rejected; Authorization: Basic top-secret",
        correlation_id="corr-1",
        details={
            "safe": "kept",
            "api_key": "secret-key",
            "nested": {
                "headers": {"Authorization": "Bearer secret"},
                "query": "prompt=private prompt",
            },
        },
    )
    serialized = failure.to_json()
    json.dumps(serialized, allow_nan=False)

    assert serialized["code"] == "validation"
    assert serialized["correlation_id"] == "corr-1"
    details = cast(dict[str, object], serialized["details"])
    assert details["safe"] == "kept"
    rendered = json.dumps(serialized, sort_keys=True)
    for secret in ("top-secret", "secret-key", "Bearer secret", "private prompt"):
        assert secret not in rendered
    assert details["nested"] != {"headers": {"Authorization": "Bearer secret"}}
    with pytest.raises(TypeError):
        failure.details["safe"] = "changed"  # type: ignore[index]


@pytest.mark.parametrize(
    ("exception", "expected", "retryable"),
    (
        (sqlite3.OperationalError("database is locked"), UnavailableDependencyFailure, True),
        (FileNotFoundError("/secret/private.db"), NotFoundFailure, False),
        (PermissionError("/secret/private.db"), UnauthorizedFailure, False),
        (ValueError("malformed command"), ValidationFailure, False),
        (RuntimeError("provider exploded with credentials"), InternalFailure, False),
    ),
)
def test_dependency_and_unknown_exceptions_map_to_safe_failures(
    exception: Exception, expected: type[HarnessError], retryable: bool
) -> None:
    failure = translate_exception(exception, correlation_id="corr-2")
    assert isinstance(failure, expected)
    assert failure.retryable is retryable
    assert failure.correlation_id == "corr-2"
    assert str(exception) not in json.dumps(failure.to_json())
    assert failure.__cause__ is exception


def test_failure_serialization_is_bounded_and_strict() -> None:
    cycle: dict[str, object] = {}
    cycle["self"] = cycle
    deep: object = "leaf"
    for _ in range(12):
        deep = {"next": deep}
    failure = ValidationFailure(
        details={
            "cycle": cycle,
            "deep": deep,
            "items": list(range(100)),
            "long": "é" * 700,
            "nan": math.nan,
            3: "non-string key",  # type: ignore[dict-item]
        }
    )
    rendered = failure.serialize()
    assert len(rendered) <= 20 * 1024
    decoded = json.loads(rendered)
    assert decoded["details"]["cycle"]["self"] == "[CYCLE]"
    assert decoded["details"]["nan"] == "[NON_FINITE]"
    assert decoded["details"]["long"] == "[STRING_LIMIT]"
    assert "[NON_STRING_KEY]" in decoded["details"]
    json.dumps(decoded, allow_nan=False)

    details = {f"item-{index}": "x" * 1000 for index in range(64)}
    bounded = ValidationFailure(details=details)
    assert bounded.to_json()["details"] == {"_": "[DETAILS_LIMIT]"}


def test_sanitizer_never_calls_arbitrary_string_conversion() -> None:
    class Hostile:
        def __str__(self) -> str:
            raise AssertionError("must not stringify")

        def __repr__(self) -> str:
            raise AssertionError("must not repr")

    failure = ValidationFailure(details={"hostile": Hostile()})
    details = cast(dict[str, object], failure.to_json()["details"])
    assert details["hostile"] == "[UNSUPPORTED]"


def test_every_legacy_error_code_maps_explicitly() -> None:
    assert set(_ERROR_CODE_TO_FAILURE) == set(ErrorCode)
    expected = {
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
    for code, failure_type in expected.items():
        translated = translate_study_error(StudyError(code, "private internal detail"))
        assert isinstance(translated, failure_type)
        assert "private internal detail" not in json.dumps(translated.to_json())


def test_failure_cause_is_local_only() -> None:
    cause = RuntimeError("provider traceback api_key=secret")
    failure = translate_exception(cause)
    assert "cause" not in failure.to_json()
    assert "secret" not in json.dumps(failure.to_json())
    assert failure.__cause__ is cause
