from __future__ import annotations

from dataclasses import fields

from study_agent.playbooks import (
    DialogueStep,
    ModelStep,
    PlaybookDefinition,
    ToolStep,
    ValidateStep,
)
from study_agent.skills import CapabilityFallback, SkillPackage


def test_skill_and_playbook_definitions_have_no_provider_or_model_selector_fields() -> None:
    definition_types = (
        SkillPackage,
        CapabilityFallback,
        PlaybookDefinition,
        ToolStep,
        ModelStep,
        DialogueStep,
        ValidateStep,
    )
    forbidden = {"provider", "provider_id", "provider_name", "model_id", "model_name"}

    for contract_type in definition_types:
        assert forbidden.isdisjoint(field.name for field in fields(contract_type))


def test_v01_playbook_ast_has_no_branching_or_execution_control_fields() -> None:
    forbidden = {"condition", "branches", "children", "loop", "parallel", "retry"}
    for step_type in (ToolStep, ModelStep, DialogueStep, ValidateStep):
        assert forbidden.isdisjoint(field.name for field in fields(step_type))
