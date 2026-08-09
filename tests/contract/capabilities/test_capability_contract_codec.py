from __future__ import annotations

import json
from dataclasses import replace
from typing import cast

import pytest

from study_agent.capabilities import CapabilityContinuation, CapabilityManifest
from study_agent.domain import RunId
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import ReadDependency, ToolBehaviorPin, VersionPins
from study_agent.skills import ArtifactReference, SemanticVersion

V1 = SemanticVersion.parse("1.0.0")
IMPLEMENTATION_V1 = SemanticVersion.parse("1.2.3")
SCHEMA: JsonObject = {
    "type": "object",
    "required": ("topic",),
    "properties": {"topic": {"type": "string"}},
    "additionalProperties": False,
}


def _manifest() -> CapabilityManifest:
    return CapabilityManifest(
        "study.explain",
        V1,
        SCHEMA,
        SCHEMA,
        ("study:read",),
        True,
        IMPLEMENTATION_V1,
    )


def _pins() -> VersionPins:
    return VersionPins(
        ArtifactReference("study.skill", V1),
        ArtifactReference("study.flow", V1),
        ArtifactReference("study.prompt", V1),
        (ToolBehaviorPin("study.lookup", V1),),
        ArtifactReference("study.model", V1),
        ArtifactReference("study.state", V1),
    )


def _continuation() -> CapabilityContinuation:
    manifest = _manifest()
    return CapabilityContinuation(
        RunId("run-1"),
        manifest.id,
        manifest.version,
        manifest.fingerprint,
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "clarify",
        1,
        {"topic": "heart"},
        _pins(),
        (ReadDependency("course", "course-1", "sequence-1"),),
    )


def test_manifest_and_continuation_round_trip_only_from_canonical_bytes() -> None:
    manifest = _manifest()
    assert CapabilityManifest.from_bytes(manifest.to_bytes()) == manifest

    continuation = _continuation()
    assert CapabilityContinuation.from_bytes(continuation.to_bytes()) == continuation

    noncanonical = b'{ "id": "study.explain", "version": "1.0.0" }'
    with pytest.raises(ValueError, match="canonical"):
        CapabilityManifest.from_bytes(noncanonical)


def test_codecs_reject_unknown_fields_and_forged_derived_values() -> None:
    manifest_payload = cast(dict[str, object], json.loads(_manifest().to_bytes()))
    manifest_payload["extra"] = True
    with pytest.raises(ValueError, match="shape"):
        CapabilityManifest.from_bytes(
            json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode()
        )

    continuation = _continuation()
    with pytest.raises(ValueError, match="input_fingerprint"):
        replace(continuation, inputs={"topic": "changed"})

    with pytest.raises(ValueError, match="input_fingerprint"):
        CapabilityContinuation(
            continuation.run_id,
            continuation.capability_id,
            continuation.capability_version,
            continuation.manifest_fingerprint,
            continuation.authority_fingerprint,
            continuation.retry_identity_fingerprint,
            continuation.definition_fingerprint,
            continuation.checkpoint_fingerprint,
            continuation.dialogue_step_id,
            continuation.next_step_index,
            {"topic": "changed"},
            continuation.pins,
            continuation.read_dependencies,
            continuation.input_fingerprint,
        )
