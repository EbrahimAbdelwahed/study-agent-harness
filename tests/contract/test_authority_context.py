from __future__ import annotations

import pytest

from study_agent.api.authority import (
    AuthorityContext,
    CancellationOutcome,
    ConflictFailure,
    Grant,
    IdempotencyKey,
    Principal,
    PrincipalKind,
    Scope,
    StaleFailure,
    UnauthorizedFailure,
    canonical_input_fingerprint,
    ensure_idempotency_compatible,
)


def _context(kind: PrincipalKind = PrincipalKind.HUMAN) -> AuthorityContext:
    return AuthorityContext(
        Principal(kind, "caller-1"),
        grants=(Grant("study:read"), Grant("study:write")),
        scopes=(Scope("course:one"),),
        correlation_id="corr-1",
        session_id="session-1",
    )


def test_authority_values_are_frozen_and_host_supplied() -> None:
    context = _context()
    assert context.principal.kind is PrincipalKind.HUMAN
    assert context.grants == frozenset({"study:read", "study:write"})
    assert context.scopes == frozenset({"course:one"})
    assert context.can("study:write", scope="course:one")
    assert not context.can("study:admin", scope="course:one")
    with pytest.raises(AttributeError):
        context.grants = frozenset({"study:admin"})  # type: ignore[misc]
    with pytest.raises(AttributeError):
        context.principal.principal_id = "other"  # type: ignore[misc]


def test_model_is_rejected_before_schema_or_adapter_access() -> None:
    context = _context(PrincipalKind.MODEL)
    calls: list[str] = []

    with pytest.raises(UnauthorizedFailure, match="model"):
        context.require_durable(
            required_grants=("study:write",),
            required_scopes=("course:one",),
            schema_validator=lambda: calls.append("schema"),
            adapter=lambda: calls.append("adapter"),
        )
    assert calls == []


def test_human_and_service_grants_and_scopes_are_enforced() -> None:
    _context().require_durable(("study:write",), ("course:one",))
    _context(PrincipalKind.SERVICE).require_durable(("study:write",), ("course:one",))

    with pytest.raises(UnauthorizedFailure):
        _context().require_durable(("study:admin",), ("course:one",))
    with pytest.raises(UnauthorizedFailure):
        _context().require_durable(("study:write",), ("course:two",))


def test_idempotency_uses_canonical_command_kind_and_bytes() -> None:
    payload_a = {"b": 2, "a": ["x", 1]}
    payload_b = {"a": ["x", 1], "b": 2}
    first = IdempotencyKey.from_command("retry-1", "course.create", payload_a)
    same = IdempotencyKey.from_command("retry-1", "course.create", payload_b)
    changed = IdempotencyKey.from_command("retry-1", "course.create", {"a": ["x", 2], "b": 2})
    other_kind = IdempotencyKey.from_command("retry-1", "course.delete", payload_a)

    assert first == same
    assert first.input_fingerprint == canonical_input_fingerprint("course.create", payload_a)
    ensure_idempotency_compatible(first, same)
    with pytest.raises(ConflictFailure):
        ensure_idempotency_compatible(first, changed)
    with pytest.raises(ConflictFailure):
        ensure_idempotency_compatible(first, other_kind)


def test_stale_and_cancellation_are_typed_and_non_mutating() -> None:
    with pytest.raises(StaleFailure) as caught:
        AuthorityContext.check_expected_sequence(expected=2, actual=3, correlation_id="corr-1")
    assert caught.value.details["expected"] == 2
    assert caught.value.details["actual"] == 3

    outcome = CancellationOutcome.before_commit(correlation_id="corr-1")
    assert outcome.cancelled is True
    assert outcome.committed is False
    assert outcome.to_json()["status"] == "cancelled"
