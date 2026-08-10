from __future__ import annotations

import asyncio

import pytest

from study_agent.capabilities import CapabilityGatewayError, CapabilityGatewayErrorCode
from study_agent.capabilities.contracts import CapabilityRequest
from study_agent.domain import PrincipalKind
from study_agent.domain._validation import JsonObject
from study_agent.ports.authority import HostAuthority
from tests.support.pf06.fixtures import INPUTS, SESSION, build_gateway, context

INVALID_INPUTS: JsonObject = {"topic": 7}


@pytest.mark.parametrize(
    "inputs",
    (INPUTS, INVALID_INPUTS),
    ids=("valid-schema", "invalid-schema"),
)
def test_foreign_issuer_is_rejected_before_schema_and_effects(
    inputs: JsonObject,
) -> None:
    fixture = build_gateway(supports_suspension=True)
    foreign_issuer = HostAuthority()
    authority = foreign_issuer.issue(
        PrincipalKind.SERVICE,
        "pf06-host",
        grants=("study:explain",),
        correlation_id="pf06-correlation",
        session_id=str(SESSION),
    )
    request = CapabilityRequest(
        fixture.binding.manifest.identity,
        inputs,
        authority,
        "pf06-correlation",
        1,
        "foreign-issuer",
    )

    with pytest.raises(CapabilityGatewayError) as caught:
        asyncio.run(fixture.gateway.start(request, context(key="foreign-issuer")))

    assert caught.value.code is CapabilityGatewayErrorCode.UNAUTHORIZED
    assert fixture.dependencies.calls == 0
    assert fixture.tool.calls == 0
    assert fixture.store.data == {}
