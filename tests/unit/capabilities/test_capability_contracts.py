from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from study_agent.capabilities import (
    CapabilityManifest,
    CapabilityOutcomeStatus,
    TutorCapabilityId,
)
from study_agent.domain._validation import JsonObject
from study_agent.skills import SemanticVersion

V1 = SemanticVersion.parse("1.0.0")


def _schema(*, selector: tuple[str, object] | None = None) -> JsonObject:
    properties: dict[str, object] = {"topic": {"type": "string"}}
    if selector is not None:
        properties[selector[0]] = selector[1]
    return cast(
        JsonObject,
        {
            "type": "object",
            "required": ("topic",),
            "properties": properties,
            "additionalProperties": False,
        },
    )


def _manifest(
    identifier: TutorCapabilityId = TutorCapabilityId.EXPLAIN_CONCEPT,
    *,
    input_schema: JsonObject | None = None,
    output_schema: JsonObject | None = None,
    authority: tuple[str, ...] = ("study:write",),
    suspension: bool = True,
) -> CapabilityManifest:
    return CapabilityManifest(
        identifier,
        V1,
        input_schema or _schema(),
        output_schema or _schema(),
        authority,
        suspension,
    )


def test_public_ids_and_outcome_statuses_are_exact_closed_values() -> None:
    assert tuple(TutorCapabilityId) == (
        TutorCapabilityId.EXPLAIN_CONCEPT,
        TutorCapabilityId.ASSESS_UNDERSTANDING,
    )
    assert tuple(item.value for item in TutorCapabilityId) == (
        "explain_concept",
        "assess_understanding",
    )
    assert tuple(item.value for item in CapabilityOutcomeStatus) == (
        "completed",
        "suspended",
        "terminated",
        "cancelled",
        "stale",
        "failed",
    )


def test_manifest_identity_json_fingerprint_and_immutability_are_stable() -> None:
    first = _manifest()
    second = _manifest()
    assert first.identity == "explain_concept@1"
    assert first.to_json() == second.to_json()
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
    assert set(first.to_json()) == {
        "id",
        "version",
        "identity",
        "input_schema",
        "output_schema",
        "required_authority",
        "supports_suspension",
    }
    assert not {
        "next_action",
        "ranking",
        "provider",
        "model",
        "hypothesis",
    } & set(first.to_json())
    with pytest.raises((FrozenInstanceError, AttributeError)):
        cast(Any, first).supports_suspension = False
    with pytest.raises(TypeError):
        cast(Any, first.input_schema)["type"] = "string"


@pytest.mark.parametrize(
    "selector",
    (
        ("provider", {"type": "string"}),
        ("model", {"type": "string"}),
        ("providerId", {"type": "string"}),
        ("modelId", {"type": "string"}),
        ("provider.name", {"type": "string"}),
        ("vendorName", {"type": "string"}),
        ("preferredProvider", {"type": "string"}),
        ("selectedModel", {"type": "string"}),
        ("openaiProvider", {"type": "string"}),
        ("OpenAIProvider", {"type": "string"}),
        ("OpenAIModel", {"type": "string"}),
        (
            "request",
            {
                "type": "object",
                "required": ("routing",),
                "additionalProperties": False,
                "properties": {
                    "routing": {
                        "type": "object",
                        "required": ("model_id",),
                        "additionalProperties": False,
                        "properties": {"model_id": {"type": "string"}},
                    }
                },
            },
        ),
        (
            "items",
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ("provider_name",),
                    "additionalProperties": False,
                    "properties": {"provider_name": {"type": "string"}},
                },
            },
        ),
    ),
)
def test_provider_and_model_selectors_are_rejected_recursively(
    selector: tuple[str, object],
) -> None:
    with pytest.raises(ValueError, match=r"provider|model|selector"):
        _manifest(input_schema=_schema(selector=selector))


@pytest.mark.parametrize(
    "schema",
    (
        {"type": "object"},
        {
            "type": "object",
            "properties": {"topic": {"type": "imaginary"}},
            "additionalProperties": False,
        },
    ),
)
def test_invalid_or_non_strict_public_schemas_are_rejected(schema: JsonObject) -> None:
    with pytest.raises(ValueError):
        _manifest(input_schema=schema)


def test_authority_and_suspension_fields_are_strict() -> None:
    with pytest.raises(ValueError, match="authority"):
        _manifest(authority=())
    with pytest.raises(ValueError, match="authority"):
        _manifest(authority=("study:write", "study:write"))
    with pytest.raises(ValueError, match="authority"):
        _manifest(authority=("",))
    with pytest.raises(TypeError, match="authority"):
        _manifest(authority=cast(tuple[str, ...], (1,)))
    for selector in (
        "provider:openai",
        "model:gpt-5",
        "vendorName:acme",
        "runtime:model:gpt-5",
    ):
        with pytest.raises(ValueError, match=r"provider|model"):
            _manifest(authority=(selector,))
    with pytest.raises(TypeError, match=r"bool|boolean"):
        _manifest(suspension=1)  # type: ignore[arg-type]


def test_authority_order_is_canonical_for_json_and_fingerprint() -> None:
    first = _manifest(authority=("study:write", "course:read"))
    second = _manifest(authority=("course:read", "study:write"))

    assert first.required_authority == ("course:read", "study:write")
    assert first.to_json() == second.to_json()
    assert first.fingerprint == second.fingerprint
