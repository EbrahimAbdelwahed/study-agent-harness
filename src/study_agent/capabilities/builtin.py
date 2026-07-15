from __future__ import annotations

from study_agent.playbooks import ToolBehaviorPin, VersionPins
from study_agent.playbooks.builtin import (
    ASSESS_UNDERSTANDING_FLOW,
    EXPLAIN_CONCEPT_FLOW,
)
from study_agent.prompts import (
    ASSESS_UNDERSTANDING_PROMPT,
    EXPLAIN_CONCEPT_PROMPT,
)
from study_agent.skills import ArtifactReference
from study_agent.skills.builtin import (
    ASSESS_UNDERSTANDING_INPUT_SCHEMA,
    ASSESS_UNDERSTANDING_OUTPUT_SCHEMA,
    ASSESS_UNDERSTANDING_SKILL,
    EXPLAIN_CONCEPT_INPUT_SCHEMA,
    EXPLAIN_CONCEPT_OUTPUT_SCHEMA,
    EXPLAIN_CONCEPT_SKILL,
)

from .bindings import CapabilityBinding, CapabilityDependencyResolver
from .contracts import CapabilityManifest, TutorCapabilityId

VERSION = EXPLAIN_CONCEPT_SKILL.version

EXPLAIN_CONCEPT_MANIFEST = CapabilityManifest(
    TutorCapabilityId.EXPLAIN_CONCEPT,
    VERSION,
    EXPLAIN_CONCEPT_INPUT_SCHEMA.value,
    EXPLAIN_CONCEPT_OUTPUT_SCHEMA.value,
    ("course:read",),
    True,
)

ASSESS_UNDERSTANDING_MANIFEST = CapabilityManifest(
    TutorCapabilityId.ASSESS_UNDERSTANDING,
    VERSION,
    ASSESS_UNDERSTANDING_INPUT_SCHEMA.value,
    ASSESS_UNDERSTANDING_OUTPUT_SCHEMA.value,
    ("course:read",),
    True,
)


def explain_concept_binding(
    *,
    dependency_resolver: CapabilityDependencyResolver,
    model_adapter: ArtifactReference,
    state_contract: ArtifactReference,
) -> CapabilityBinding:
    pins = VersionPins(
        ArtifactReference(EXPLAIN_CONCEPT_SKILL.id, EXPLAIN_CONCEPT_SKILL.version),
        ArtifactReference(EXPLAIN_CONCEPT_FLOW.id, EXPLAIN_CONCEPT_FLOW.version),
        EXPLAIN_CONCEPT_PROMPT,
        (ToolBehaviorPin("source.search", VERSION),),
        model_adapter,
        state_contract,
    )
    return CapabilityBinding(
        EXPLAIN_CONCEPT_MANIFEST,
        EXPLAIN_CONCEPT_MANIFEST.fingerprint,
        EXPLAIN_CONCEPT_SKILL,
        EXPLAIN_CONCEPT_FLOW,
        pins,
        "explanation",
        dependency_resolver,
    )


def assess_understanding_binding(
    *,
    dependency_resolver: CapabilityDependencyResolver,
    model_adapter: ArtifactReference,
    state_contract: ArtifactReference,
) -> CapabilityBinding:
    pins = VersionPins(
        ArtifactReference(
            ASSESS_UNDERSTANDING_SKILL.id,
            ASSESS_UNDERSTANDING_SKILL.version,
        ),
        ArtifactReference(
            ASSESS_UNDERSTANDING_FLOW.id,
            ASSESS_UNDERSTANDING_FLOW.version,
        ),
        ASSESS_UNDERSTANDING_PROMPT,
        (ToolBehaviorPin("source.search", VERSION),),
        model_adapter,
        state_contract,
    )
    return CapabilityBinding(
        ASSESS_UNDERSTANDING_MANIFEST,
        ASSESS_UNDERSTANDING_MANIFEST.fingerprint,
        ASSESS_UNDERSTANDING_SKILL,
        ASSESS_UNDERSTANDING_FLOW,
        pins,
        "assessment",
        dependency_resolver,
    )


def builtin_capability_bindings(
    *,
    explain_dependency_resolver: CapabilityDependencyResolver,
    assess_dependency_resolver: CapabilityDependencyResolver,
    model_adapter: ArtifactReference,
    state_contract: ArtifactReference,
) -> tuple[CapabilityBinding, CapabilityBinding]:
    return (
        explain_concept_binding(
            dependency_resolver=explain_dependency_resolver,
            model_adapter=model_adapter,
            state_contract=state_contract,
        ),
        assess_understanding_binding(
            dependency_resolver=assess_dependency_resolver,
            model_adapter=model_adapter,
            state_contract=state_contract,
        ),
    )
