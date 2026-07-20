from __future__ import annotations

import pytest

from study_agent.capabilities import (
    CapabilityManifest,
    StudyCapabilityRegistry,
    TutorCapabilityId,
)
from study_agent.domain._validation import JsonObject
from study_agent.skills import SemanticVersion


def _manifest(
    identifier: TutorCapabilityId,
    version: str = "1.0.0",
) -> CapabilityManifest:
    schema: JsonObject = {
        "type": "object",
        "required": (),
        "properties": {},
        "additionalProperties": False,
    }
    return CapabilityManifest(
        identifier,
        SemanticVersion.parse(version),
        schema,
        schema,
        ("study:write",),
        False,
    )


def test_discovery_is_sorted_stable_and_returns_an_immutable_tuple() -> None:
    assess = _manifest(TutorCapabilityId.ASSESS_UNDERSTANDING)
    explain = _manifest(TutorCapabilityId.EXPLAIN_CONCEPT)
    registry = StudyCapabilityRegistry((explain, assess))

    discovered = registry.discover()
    assert isinstance(discovered, tuple)
    assert tuple(item.identity for item in discovered) == (
        "assess_understanding@1",
        "explain_concept@1",
    )
    assert registry.discover() == discovered
    assert tuple(item.fingerprint for item in registry.discover()) == tuple(
        item.fingerprint for item in discovered
    )
    assert registry.get(TutorCapabilityId.EXPLAIN_CONCEPT) is explain
    missing = StudyCapabilityRegistry((assess,))
    with pytest.raises(KeyError):
        missing.get(TutorCapabilityId.EXPLAIN_CONCEPT)
    assert not hasattr(registry, "register")


def test_duplicate_identity_and_multiple_versions_of_one_id_fail_closed() -> None:
    first = _manifest(TutorCapabilityId.EXPLAIN_CONCEPT)
    with pytest.raises(ValueError, match=r"duplicate|identit"):
        StudyCapabilityRegistry((first, first))

    v2 = _manifest(TutorCapabilityId.EXPLAIN_CONCEPT, "2.0.0")
    with pytest.raises(ValueError, match=r"one version|capability id"):
        StudyCapabilityRegistry((v2, first))


def test_manifest_output_never_advertises_policy_or_runtime_selection() -> None:
    registry = StudyCapabilityRegistry(
        (
            _manifest(TutorCapabilityId.EXPLAIN_CONCEPT),
            _manifest(TutorCapabilityId.ASSESS_UNDERSTANDING),
        )
    )
    documents = tuple(item.to_json() for item in registry.discover())
    serialized = repr(documents).lower()
    for forbidden in (
        "next_action",
        "ranking",
        "provider",
        "model",
        "learner_hypothesis",
    ):
        assert forbidden not in serialized
