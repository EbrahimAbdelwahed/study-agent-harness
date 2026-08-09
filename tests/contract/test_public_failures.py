from __future__ import annotations

import json
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
        "request rejected; token=super-secret",
        correlation_id="corr-1",
        details={
            "safe": "kept",
            "api_key": "secret-key",
            "cookie": "session-cookie",
            "prompt": "private prompt",
            "traceback": "private traceback",
            "nested": {"authorization": "Bearer secret"},
        },
    )
    serialized = failure.to_json()
    json.dumps(serialized)

    assert serialized["code"] == "validation"
    assert serialized["correlation_id"] == "corr-1"
    details = cast(dict[str, object], serialized["details"])
    assert details["safe"] == "kept"
    rendered = json.dumps(serialized, sort_keys=True)
    secrets = (
        "super-secret",
        "secret-key",
        "session-cookie",
        "private prompt",
        "private traceback",
    )
    for secret in secrets:
        assert secret not in rendered
    assert "Bearer secret" not in rendered
    with pytest.raises(TypeError):
        failure.details["safe"] = "changed"  # type: ignore[index]
    nested = failure.details["nested"]
    assert isinstance(nested, dict) is False


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


def test_failure_serialization_does_not_include_local_cause() -> None:
    cause = RuntimeError("provider traceback api_key=secret")
    failure = translate_exception(cause)

    assert "cause" not in failure.to_json()
    assert "secret" not in json.dumps(failure.to_json())


def test_legacy_internal_codes_map_explicitly_to_the_closed_taxonomy() -> None:
    assert isinstance(
        translate_study_error(StudyError(ErrorCode.NOT_FOUND, "private path")), NotFoundFailure
    )
    assert isinstance(
        translate_study_error(StudyError(ErrorCode.CONFLICT, "duplicate")), ConflictFailure
    )
    assert isinstance(
        translate_study_error(StudyError(ErrorCode.PERSISTENCE_ERROR, "sqlite traceback")),
        UnavailableDependencyFailure,
    )
