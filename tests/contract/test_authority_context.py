from __future__ import annotations

import copy
import dataclasses
import pickle
from collections.abc import Iterable
from typing import cast

import pytest

from study_agent.api.authority import (
    AuthorityContext,
    CancellationOutcome,
    ConflictFailure,
    Grant,
    HostAuthority,
    IdempotencyKey,
    Principal,
    PrincipalKind,
    Scope,
    StaleFailure,
    UnauthorizedFailure,
    ensure_idempotency_compatible,
)


def _issued(kind: PrincipalKind = PrincipalKind.HUMAN) -> tuple[HostAuthority, AuthorityContext]:
    issuer = HostAuthority()
    context = issuer.issue(
        kind,
        "caller-1",
        grants=("study:read", "study:write"),
        scopes=("course:one",),
        correlation_id="corr-1",
        session_id="session-1",
    )
    return issuer, context


def test_authority_values_are_opaque_read_only_and_host_issued() -> None:
    issuer, context = _issued()
    assert context.principal.kind is PrincipalKind.HUMAN
    assert {grant.name for grant in context.grants} == {"study:read", "study:write"}
    assert {scope.name for scope in context.scopes} == {"course:one"}
    assert not hasattr(issuer.port, "issue")
    with pytest.raises(TypeError):
        Principal(PrincipalKind.HUMAN, "forged")
    with pytest.raises(TypeError):
        Grant("study:write")
    with pytest.raises(TypeError):
        Scope("course:one")
    with pytest.raises(TypeError):
        AuthorityContext(context.principal, correlation_id="forged")
    with pytest.raises(AttributeError):
        context.grants = ()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        context.principal = context.principal  # type: ignore[misc]
    with pytest.raises(TypeError):
        dataclasses.replace(context)  # type: ignore[type-var]
    for value in (context, context.principal, *context.grants, *context.scopes):
        with pytest.raises(TypeError):
            copy.copy(value)
        with pytest.raises(TypeError):
            pickle.dumps(value)


def test_cross_issuer_context_is_rejected_before_claims() -> None:
    issuer_a, context_a = _issued()
    issuer_b, context_b = _issued()
    issuer_a.port.require(context_a, ("study:read",), ("course:one",))
    with pytest.raises(UnauthorizedFailure, match="different host"):
        issuer_b.port.require(context_a, (object(),), (object(),))  # type: ignore[arg-type]
    with pytest.raises(UnauthorizedFailure, match="different host"):
        issuer_a.port.require(context_b, (object(),), (object(),))  # type: ignore[arg-type]


def test_issue_rejects_scalar_grant_and_scope_collections() -> None:
    issuer = HostAuthority()
    for scalar in ("study:write", b"study:write"):
        with pytest.raises(TypeError):
            issuer.issue(
                PrincipalKind.HUMAN,
                "caller",
                grants=cast(Iterable[str | Grant], scalar),
                correlation_id="corr",
            )
        with pytest.raises(TypeError):
            issuer.issue(
                PrincipalKind.HUMAN,
                "caller",
                scopes=cast(Iterable[str | Scope], scalar),
                correlation_id="corr",
            )


def test_model_is_rejected_before_schema_or_adapter_access() -> None:
    issuer, context = _issued(PrincipalKind.MODEL)
    calls: list[str] = []

    with pytest.raises(UnauthorizedFailure, match="model"):
        issuer.port.require_durable(
            context,
            required_grants=(object(),),  # type: ignore[arg-type]
            required_scopes=(object(),),  # type: ignore[arg-type]
            schema_validator=lambda: calls.append("schema"),
            adapter=lambda: calls.append("adapter"),
        )
    assert calls == []
    issuer.port.require(context, ("study:write",), ("course:one",))


def test_human_and_service_grants_and_scopes_are_enforced() -> None:
    human_issuer, human = _issued()
    service_issuer, service = _issued(PrincipalKind.SERVICE)
    human_issuer.port.require_durable(human, ("study:write",), ("course:one",))
    service_issuer.port.require_durable(service, ("study:write",), ("course:one",))

    with pytest.raises(UnauthorizedFailure):
        human_issuer.port.require_durable(human, ("study:admin",), ("course:one",))
    with pytest.raises(UnauthorizedFailure):
        human_issuer.port.require_durable(human, ("study:write",), ("course:two",))


def test_idempotency_uses_canonical_command_kind_and_bytes() -> None:
    payload_a = {"b": 2, "a": ["x", 1]}
    payload_b = {"a": ["x", 1], "b": 2}
    first = IdempotencyKey.from_command("retry-1", "course.create", payload_a)
    same = IdempotencyKey.from_command("retry-1", "course.create", payload_b)
    changed = IdempotencyKey.from_command("retry-1", "course.create", {"a": ["x", 2], "b": 2})
    other_kind = IdempotencyKey.from_command("retry-1", "course.delete", payload_a)

    assert first == same
    ensure_idempotency_compatible(first, same)
    with pytest.raises(ConflictFailure):
        ensure_idempotency_compatible(first, changed)
    with pytest.raises(ConflictFailure):
        ensure_idempotency_compatible(first, other_kind)


def test_stale_and_cancellation_are_typed_and_non_mutating() -> None:
    with pytest.raises(StaleFailure) as caught:
        AuthorityContext.check_expected_sequence(expected=2, actual=3, correlation_id="corr-1")
    assert cast(dict[str, object], caught.value.to_json()["details"])["expected"] == 2
    assert cast(dict[str, object], caught.value.to_json()["details"])["actual"] == 3

    outcome = CancellationOutcome.before_commit(correlation_id="corr-1")
    assert outcome.cancelled is True
    assert outcome.committed is False
    assert outcome.to_json()["status"] == "cancelled"
