from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from study_agent.capabilities import CapabilityManifest, CapabilityOutcomeStatus
from study_agent.domain._validation import JsonObject
from study_agent.skills import SemanticVersion

V1 = SemanticVersion.parse("1.0.0")
IMPLEMENTATION_V1 = SemanticVersion.parse("1.2.3")
SCHEMA: JsonObject = {
    "type": "object",
    "required": ("topic",),
    "properties": {"topic": {"type": "string"}},
    "additionalProperties": False,
}


def _manifest(**changes: object) -> CapabilityManifest:
    values: dict[str, object] = {
        "id": "study.explain",
        "version": V1,
        "input_schema": SCHEMA,
        "output_schema": SCHEMA,
        "required_authority": ("study:read",),
        "supports_suspension": True,
        "implementation_version": IMPLEMENTATION_V1,
    }
    values.update(changes)
    return CapabilityManifest(**values)  # type: ignore[arg-type]


def test_manifest_uses_namespaced_full_semver_identity_and_required_implementation() -> None:
    manifest = _manifest()
    assert manifest.identity == "study.explain@1.0.0"
    assert manifest.implementation_contract_version is IMPLEMENTATION_V1
    assert manifest.to_json()["implementation_version"] == "1.2.3"
    assert tuple(item.value for item in CapabilityOutcomeStatus) == (
        "completed",
        "suspended",
        "cancelled",
        "stale",
        "failed",
    )

    with pytest.raises((FrozenInstanceError, AttributeError)):
        cast(Any, manifest).implementation_version = V1


@pytest.mark.parametrize("identifier", ("Study.Explain", "study", "study..explain", "study/"))
def test_manifest_rejects_non_namespaced_capability_ids(identifier: str) -> None:
    with pytest.raises(ValueError, match="capability id"):
        _manifest(id=identifier)


def test_manifest_requires_semantic_implementation_version() -> None:
    with pytest.raises(TypeError, match="SemanticVersion"):
        _manifest(implementation_version="1.2.3")
