from __future__ import annotations

import asyncio
import json
from typing import cast

import pytest

from study_agent.api import authority as authority_api
from study_agent.api import capabilities as capabilities_api
from study_agent.domain import ExecutionContext, PrincipalKind, RunId
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import ReadDependency
from tests.support.pf06.fixtures import (
    COURSE,
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


def _record_status(payload: bytes) -> str:
    decoded = cast(object, json.loads(payload.decode("utf-8")))
    if not isinstance(decoded, dict):
        raise AssertionError("durable run record must be a JSON object")
    checkpoint = decoded.get("checkpoint")
    if not isinstance(checkpoint, dict):
        raise AssertionError("durable run record must contain a checkpoint")
    status = checkpoint.get("status")
    if not isinstance(status, str):
        raise AssertionError("durable run record checkpoint must contain a status")
    return status


def _typed_course_high_water(payload: bytes) -> tuple[str, int]:
    """Find the one serialized CourseStreamHighWater value in a run record."""

    decoded = cast(object, json.loads(payload.decode("utf-8")))
    observations: list[tuple[str, int]] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            mapping = cast(dict[object, object], value)
            if set(mapping) == {"course_id", "sequence"}:
                course_id = mapping.get("course_id")
                sequence = mapping.get("sequence")
                if isinstance(course_id, str) and type(sequence) is int:
                    observations.append((course_id, sequence))
            for child in mapping.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(decoded)
    if len(observations) != 1:
        raise AssertionError("durable run record must contain one typed course high-water")
    return observations[0]


def _assert_terminal_record(
    fixture: GatewayFixture,
    run_id: RunId,
    *,
    status: str,
    high_water: tuple[str, int],
) -> bytes:
    record = fixture.store.sole_record(run_id)
    assert _record_status(record) == status
    assert _typed_course_high_water(record) == high_water
    return record


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
    assert dependencies.calls == 0
    assert fixture.tool.calls == 0
    assert fixture.model.calls == 0
    record = _assert_terminal_record(
        fixture,
        outcome.run_id,
        status="stale",
        high_water=(str(COURSE), 1),
    )
    snapshot = fixture.store.snapshot()

    restarted_dependencies = UnrelatedSequenceDependencies()
    restarted = build_gateway(
        dependencies=restarted_dependencies,
        store=fixture.store,
        host_authority=fixture.authority,
    )
    retry = asyncio.run(restarted.gateway.start(request, execution_context))

    assert isinstance(retry, capabilities_api.StaleCapabilityOutcome)
    assert retry == outcome
    assert restarted_dependencies.calls == 0
    assert restarted.tool.calls == 0
    assert restarted.model.calls == 0
    assert fixture.store.snapshot() == snapshot
    assert fixture.store.sole_record(outcome.run_id) == record


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
    record = _assert_terminal_record(
        fixture,
        stale.run_id,
        status="stale",
        high_water=(str(COURSE), 1),
    )
    snapshot = fixture.store.snapshot()
    changed_request, changed_context = _request(
        fixture,
        issuer=issuer,
        inputs={"topic": "mitral valve"},
        expected_high_water=1,
        key="stale-retry-key",
    )
    with pytest.raises(authority_api.ConflictFailure):
        asyncio.run(fixture.gateway.start(changed_request, changed_context))

    assert fixture.dependencies.calls == 0
    assert fixture.tool.calls == 0
    assert fixture.model.calls == 0
    assert fixture.store.snapshot() == snapshot
    assert fixture.store.sole_record(stale.run_id) == record


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
    assert fixture.model.calls == 0
    record = _assert_terminal_record(
        fixture,
        outcome.run_id,
        status="cancelled",
        high_water=(str(COURSE), 1),
    )
    snapshot = fixture.store.snapshot()

    restarted = build_gateway(
        store=fixture.store,
        host_authority=fixture.authority,
    )
    retry_cancellation = CancelOnSecondProbe()
    retry = asyncio.run(
        restarted.gateway.start(
            request,
            execution_context,
            cancellation=retry_cancellation,
        )
    )

    assert isinstance(retry, capabilities_api.CancelledCapabilityOutcome)
    assert retry == outcome
    assert retry_cancellation.calls == 0
    assert restarted.dependencies.calls == 0
    assert restarted.tool.calls == 0
    assert restarted.model.calls == 0
    assert fixture.store.snapshot() == snapshot
    assert fixture.store.sole_record(outcome.run_id) == record
