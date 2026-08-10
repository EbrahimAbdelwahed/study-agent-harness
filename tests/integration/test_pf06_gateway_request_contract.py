from __future__ import annotations

import asyncio

import pytest

from study_agent.api import authority as authority_api
from study_agent.api import capabilities as capabilities_api
from study_agent.domain import ExecutionContext, PrincipalKind
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import ReadDependency
from tests.support.pf06.fixtures import (
    INPUTS,
    SESSION,
    Dependencies,
    GatewayFixture,
    build_gateway,
    context,
)


class UnrelatedSequenceDependencies(Dependencies):
    def __call__(
        self, *, context: ExecutionContext, inputs: JsonObject
    ) -> tuple[ReadDependency, ...]:
        del context, inputs
        self.calls += 1
        return (ReadDependency("unrelated", "other-resource", "sequence-999"),)


class CancelOnSecondProbe:
    """Request cancellation at the deterministic last pre-dispatch probe."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls == 2


def _request(
    fixture: GatewayFixture,
    *,
    issuer: authority_api.HostAuthority | None = None,
    inputs: JsonObject = INPUTS,
    expected_high_water: int = 1,
    key: str = "pf06-request",
) -> tuple[capabilities_api.CapabilityRequest, ExecutionContext]:
    selected_issuer = fixture.authority if issuer is None else issuer
    authority = selected_issuer.issue(
        PrincipalKind.SERVICE,
        "pf06-host",
        grants=("study:explain",),
        correlation_id="pf06-correlation",
        session_id=str(SESSION),
    )
    return (
        capabilities_api.CapabilityRequest(
            fixture.binding.manifest.identity,
            inputs,
            authority,
            "pf06-correlation",
            expected_high_water,
            key,
        ),
        context(key=key),
    )


def test_high_water_requires_the_authoritative_course_stream_proof() -> None:
    dependencies = UnrelatedSequenceDependencies()
    fixture = build_gateway(dependencies=dependencies)
    request, execution_context = _request(
        fixture,
        expected_high_water=999,
        key="unrelated-high-water",
    )

    outcome = asyncio.run(fixture.gateway.start(request, execution_context))

    assert isinstance(outcome, capabilities_api.StaleCapabilityOutcome)
    assert dependencies.calls == 1
    assert fixture.tool.calls == 0
    assert fixture.store.data == {}


def test_stale_request_key_cannot_be_reused_with_changed_input_bytes() -> None:
    fixture = build_gateway(supports_suspension=True)
    issuer = fixture.authority
    stale_request, stale_context = _request(
        fixture,
        issuer=issuer,
        expected_high_water=2,
        key="stale-retry-key",
    )

    stale = asyncio.run(fixture.gateway.start(stale_request, stale_context))

    assert isinstance(stale, capabilities_api.StaleCapabilityOutcome)
    assert fixture.store.data == {}
    changed_request, changed_context = _request(
        fixture,
        issuer=issuer,
        inputs={"topic": "mitral valve"},
        expected_high_water=1,
        key="stale-retry-key",
    )
    with pytest.raises(authority_api.ConflictFailure):
        asyncio.run(fixture.gateway.start(changed_request, changed_context))

    assert fixture.dependencies.calls == 1
    assert fixture.tool.calls == 0
    assert fixture.store.data == {}


def test_cancellation_at_last_pre_dispatch_probe_has_no_effects() -> None:
    fixture = build_gateway()
    cancellation = CancelOnSecondProbe()
    request, execution_context = _request(
        fixture,
        key="cancel-before-dispatch",
    )

    outcome = asyncio.run(
        fixture.gateway.start(
            request,
            execution_context,
            cancellation=cancellation,
        )
    )

    assert isinstance(outcome, capabilities_api.CancelledCapabilityOutcome)
    assert cancellation.calls == 2
    assert fixture.dependencies.calls == 1
    assert fixture.tool.calls == 0
    assert fixture.store.data == {}
