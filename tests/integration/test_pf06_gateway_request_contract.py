from __future__ import annotations

import asyncio

import pytest

from study_agent.capabilities import (
    CancelledCapabilityOutcome,
    CapabilityGatewayError,
    CapabilityGatewayErrorCode,
    StaleCapabilityOutcome,
)
from study_agent.capabilities.contracts import CapabilityRequest
from study_agent.domain import ExecutionContext, PrincipalKind
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import ReadDependency
from study_agent.ports.authority import HostAuthority
from tests.support.pf06.fixtures import (
    INPUTS,
    SESSION,
    Dependencies,
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


def _request(
    manifest_identity: str,
    *,
    issuer: HostAuthority | None = None,
    inputs: JsonObject = INPUTS,
    expected_high_water: int = 1,
    key: str = "pf06-request",
) -> tuple[CapabilityRequest, ExecutionContext]:
    selected_issuer = issuer or HostAuthority()
    authority = selected_issuer.issue(
        PrincipalKind.SERVICE,
        "pf06-host",
        grants=("study:explain",),
        correlation_id="pf06-correlation",
        session_id=str(SESSION),
    )
    return (
        CapabilityRequest(
            manifest_identity,
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
        fixture.binding.manifest.identity,
        expected_high_water=999,
        key="unrelated-high-water",
    )

    outcome = asyncio.run(fixture.gateway.start(request, execution_context))

    assert isinstance(outcome, StaleCapabilityOutcome)
    assert dependencies.calls == 1
    assert fixture.tool.calls == 0
    assert fixture.store.data == {}


def test_stale_request_key_cannot_be_reused_with_changed_input_bytes() -> None:
    fixture = build_gateway(supports_suspension=True)
    issuer = HostAuthority()
    stale_request, stale_context = _request(
        fixture.binding.manifest.identity,
        issuer=issuer,
        expected_high_water=2,
        key="stale-retry-key",
    )

    stale = asyncio.run(fixture.gateway.start(stale_request, stale_context))

    assert isinstance(stale, StaleCapabilityOutcome)
    changed_request, changed_context = _request(
        fixture.binding.manifest.identity,
        issuer=issuer,
        inputs={"topic": "mitral valve"},
        expected_high_water=1,
        key="stale-retry-key",
    )
    with pytest.raises(CapabilityGatewayError) as caught:
        asyncio.run(fixture.gateway.start(changed_request, changed_context))

    assert caught.value.code is CapabilityGatewayErrorCode.CONFLICT
    assert fixture.dependencies.calls == 1
    assert fixture.tool.calls == 0


def test_cancellation_between_last_preflight_and_commit_converges_safely() -> None:
    fixture = build_gateway()
    cancellation_state = {"requested": False}
    original_invoke = fixture.tool.invoke

    async def invoke(arguments: JsonObject) -> JsonObject:
        cancellation_state["requested"] = True
        return await original_invoke(arguments)

    object.__setattr__(fixture.tool, "invoke", invoke)
    request, execution_context = _request(
        fixture.binding.manifest.identity,
        key="cancel-at-commit",
    )

    outcome = asyncio.run(
        fixture.gateway.start(
            request,
            execution_context,
            cancellation=lambda: cancellation_state["requested"],
        )
    )

    assert isinstance(outcome, CancelledCapabilityOutcome)
    assert fixture.tool.calls == 1
