from __future__ import annotations

import asyncio

import pytest

from study_agent.api import authority as authority_api
from study_agent.api import capabilities as capabilities_api
from study_agent.domain._validation import JsonObject
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
    foreign_issuer = authority_api.HostAuthority()
    authority = foreign_issuer.issue(
        authority_api.PrincipalKind.SERVICE,
        "pf06-host",
        grants=("study:explain",),
        correlation_id="pf06-correlation",
        session_id=str(SESSION),
    )
    request = capabilities_api.CapabilityRequest(
        fixture.binding.manifest.identity,
        inputs,
        authority,
        "pf06-correlation",
        1,
        "foreign-issuer",
    )

    with pytest.raises(authority_api.UnauthorizedFailure):
        asyncio.run(fixture.gateway.start(request, context(key="foreign-issuer")))

    assert fixture.dependencies.calls == 0
    assert fixture.tool.calls == 0
    assert fixture.store.data == {}
