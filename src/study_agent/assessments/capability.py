"""Trusted binding for the free-response grading capability."""

from study_agent.capabilities.bindings import CapabilityBinding, CapabilityDependencyResolver
from study_agent.capabilities.builtin import GRADE_RESPONSE_MANIFEST
from study_agent.playbooks import ToolBehaviorPin, ValidateStep, VersionPins
from study_agent.playbooks.builtin.grade_response_flow import GRADE_RESPONSE_FLOW
from study_agent.prompts.grade_response_v1 import GRADE_RESPONSE_PROMPT
from study_agent.skills import ArtifactReference
from study_agent.skills.builtin.grade_response import GRADE_RESPONSE_SKILL


def grade_response_binding(
    *,
    dependency_resolver: CapabilityDependencyResolver,
    model_adapter: ArtifactReference,
    state_contract: ArtifactReference,
) -> CapabilityBinding:
    pins = VersionPins(
        ArtifactReference(GRADE_RESPONSE_SKILL.id, GRADE_RESPONSE_SKILL.version),
        ArtifactReference(GRADE_RESPONSE_FLOW.id, GRADE_RESPONSE_FLOW.version),
        GRADE_RESPONSE_PROMPT,
        (ToolBehaviorPin("assessment.prepare_grade_scope", GRADE_RESPONSE_SKILL.version),),
        model_adapter,
        state_contract,
    )
    binding = CapabilityBinding(
        GRADE_RESPONSE_MANIFEST,
        GRADE_RESPONSE_MANIFEST.fingerprint,
        GRADE_RESPONSE_SKILL,
        GRADE_RESPONSE_FLOW,
        pins,
        "grade",
        dependency_resolver,
    )
    declared_validators = {
        (item.id, item.version) for item in GRADE_RESPONSE_SKILL.validators
    }
    bound_validators = {
        (step.validator.id, step.validator.version)
        for step in GRADE_RESPONSE_FLOW.steps
        if isinstance(step, ValidateStep)
    }
    if bound_validators != declared_validators:
        raise ValueError("grade-response validator pins differ from the bound skill")
    if GRADE_RESPONSE_SKILL.state_write_policy.allowed_event_types:
        raise ValueError("grade-response capability forbids state writes")
    return binding


__all__ = ["grade_response_binding"]
