from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from study_agent.capabilities import (
    CancelledCapabilityOutcome,
    CapabilityGatewayError,
    CapabilityGatewayErrorCode,
    CompletedCapabilityOutcome,
    FailedCapabilityOutcome,
    StaleCapabilityOutcome,
    StudyCapabilityGateway,
    SuspendedCapabilityOutcome,
    TutorCapabilityId,
)
from study_agent.domain import ExecutionContext, PrincipalKind
from study_agent.domain._validation import JsonObject
from study_agent.ports import ModelError, ModelErrorCode
from tests.support.pf06.fixtures import (
    INPUTS,
    Dependencies,
    build_gateway,
    build_model_failure_gateway,
    context,
)


def _start(
    gateway: StudyCapabilityGateway,
    inputs: JsonObject,
    execution_context: ExecutionContext,
) -> object:
    return asyncio.run(gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, inputs, execution_context))


def test_authority_and_schema_rejection_happen_before_dependency_or_tool_effects() -> None:
    for execution_context in (
        context(grants=frozenset()),
        context(principal_kind=PrincipalKind.MODEL),
    ):
        fixture = build_gateway()
        with pytest.raises(CapabilityGatewayError) as caught:
            _start(fixture.gateway, INPUTS, execution_context)
        assert caught.value.code is CapabilityGatewayErrorCode.UNAUTHORIZED
        assert fixture.dependencies.calls == 0
        assert fixture.tool.calls == 0
        assert fixture.store.data == {}

    fixture = build_gateway()
    with pytest.raises(CapabilityGatewayError) as caught:
        _start(fixture.gateway, {"topic": 7}, context())
    assert caught.value.code is CapabilityGatewayErrorCode.INVALID_REQUEST
    assert fixture.dependencies.calls == 0
    assert fixture.tool.calls == 0
    assert fixture.store.data == {}


def test_equal_retry_reuses_one_completed_outcome_and_changed_input_conflicts() -> None:
    fixture = build_gateway()
    first = _start(fixture.gateway, INPUTS, context())
    assert isinstance(first, CompletedCapabilityOutcome)
    exact = _start(fixture.gateway, INPUTS, context(correlation="different"))
    assert isinstance(exact, CompletedCapabilityOutcome)
    assert exact.run == first.run
    assert fixture.tool.calls == 1
    assert fixture.dependencies.calls == 1

    with pytest.raises(CapabilityGatewayError) as caught:
        _start(fixture.gateway, {"topic": "different"}, context())
    assert caught.value.code is CapabilityGatewayErrorCode.CONFLICT
    assert fixture.tool.calls == 1
    assert fixture.dependencies.calls == 1


def test_suspension_resume_binds_continuation_and_does_not_repeat_effects() -> None:
    fixture = build_gateway(supports_suspension=True)
    suspended = _start(fixture.gateway, INPUTS, context())
    assert isinstance(suspended, SuspendedCapabilityOutcome)
    assert fixture.tool.calls == 0

    completed = asyncio.run(
        fixture.gateway.resume(
            suspended.continuation,
            {"text": "focus on cusps"},
            context(),
        )
    )
    assert isinstance(completed, CompletedCapabilityOutcome)
    assert completed.run.run_id == suspended.run_id
    assert fixture.tool.calls == 1

    exact = asyncio.run(
        fixture.gateway.resume(
            suspended.continuation,
            {"text": "focus on cusps"},
            context(),
        )
    )
    assert isinstance(exact, CompletedCapabilityOutcome)
    assert exact.run == completed.run
    assert fixture.tool.calls == 1


def test_forged_continuation_is_rejected_before_resume_effects() -> None:
    fixture = build_gateway(supports_suspension=True)
    suspended = _start(fixture.gateway, INPUTS, context())
    assert isinstance(suspended, SuspendedCapabilityOutcome)
    forged = replace(suspended.continuation, checkpoint_fingerprint="0" * 64)

    with pytest.raises(CapabilityGatewayError) as caught:
        asyncio.run(fixture.gateway.resume(forged, {"text": "focus on cusps"}, context()))
    assert caught.value.code is CapabilityGatewayErrorCode.CONFLICT
    assert fixture.tool.calls == 0
    assert fixture.dependencies.calls == 1


def test_changed_dependency_returns_stale_without_running_bound_tool() -> None:
    fixture = build_gateway(
        supports_suspension=True,
        dependencies=Dependencies(drift_after_first=True),
    )
    suspended = _start(fixture.gateway, INPUTS, context())
    assert isinstance(suspended, SuspendedCapabilityOutcome)
    stale = asyncio.run(
        fixture.gateway.resume(suspended.continuation, {"text": "focus on cusps"}, context())
    )
    assert isinstance(stale, StaleCapabilityOutcome)
    assert fixture.tool.calls == 0
    assert fixture.dependencies.calls == 2


def test_cancellation_is_a_terminal_observation_and_retry_does_not_call_model_again() -> None:
    gateway, model = build_model_failure_gateway(
        ModelError(ModelErrorCode.CANCELLED, "transport cancelled")
    )
    cancelled = _start(gateway, INPUTS, context())
    assert isinstance(cancelled, CancelledCapabilityOutcome)
    retry = _start(gateway, INPUTS, context())
    assert isinstance(retry, CancelledCapabilityOutcome)
    assert model.calls == 1


def test_provider_failure_and_invalid_output_fail_closed_and_are_replayable() -> None:
    failed_provider = build_gateway(tool_error=RuntimeError("provider detail must not escape"))
    provider_failure = _start(failed_provider.gateway, INPUTS, context())
    assert isinstance(provider_failure, FailedCapabilityOutcome)
    assert "provider detail" not in provider_failure.message
    provider_retry = _start(failed_provider.gateway, INPUTS, context())
    assert isinstance(provider_retry, FailedCapabilityOutcome)
    assert failed_provider.tool.calls == 1

    invalid_output = build_gateway(tool_output={"answer": 17})
    invalid = _start(invalid_output.gateway, INPUTS, context(key="invalid-output"))
    assert isinstance(invalid, FailedCapabilityOutcome)
    invalid_retry = _start(invalid_output.gateway, INPUTS, context(key="invalid-output"))
    assert isinstance(invalid_retry, FailedCapabilityOutcome)
    assert invalid_output.tool.calls == 1
