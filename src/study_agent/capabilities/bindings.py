"""Trusted composition-root bindings for executable tutor capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from study_agent.domain import ExecutionContext
from study_agent.domain._validation import JsonObject, freeze_object, require_text
from study_agent.pedagogy import PedagogicalProfileRef, ProfileSelectionReceipt
from study_agent.playbooks import (
    DataSourceKind,
    DialogueStep,
    ModelStep,
    PlaybookDefinition,
    ReadDependency,
    ToolStep,
    ValidateStep,
    VersionPins,
)
from study_agent.skills import ArtifactReference, SkillPackage

from .contracts import CapabilityManifest


class CapabilityDependencyResolver(Protocol):
    def __call__(
        self, *, context: ExecutionContext, inputs: JsonObject
    ) -> tuple[ReadDependency, ...]: ...


@dataclass(frozen=True, slots=True)
class CapabilityBinding:
    manifest: CapabilityManifest
    manifest_fingerprint: str
    skill: SkillPackage
    playbook: PlaybookDefinition
    pins: VersionPins
    output_key: str
    dependency_resolver: CapabilityDependencyResolver

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, CapabilityManifest):
            raise TypeError("binding manifest must be CapabilityManifest")
        if not isinstance(self.manifest_fingerprint, str):
            raise TypeError("binding manifest fingerprint must be text")
        if not isinstance(self.skill, SkillPackage):
            raise TypeError("binding skill must be SkillPackage")
        if not isinstance(self.playbook, PlaybookDefinition):
            raise TypeError("binding playbook must be PlaybookDefinition")
        if not isinstance(self.pins, VersionPins):
            raise TypeError("binding pins must be VersionPins")
        require_text(self.output_key, "binding output_key")
        if not callable(self.dependency_resolver):
            raise TypeError("binding dependency_resolver must be callable")
        if self.manifest_fingerprint != self.manifest.fingerprint:
            raise ValueError("binding manifest fingerprint is stale")
        if self.skill.id != self.manifest.id.value or self.skill.version != self.manifest.version:
            raise ValueError("binding skill identity differs from capability manifest")
        if self.skill.input_schema.value != self.manifest.input_schema:
            raise ValueError("binding skill input schema differs from manifest")
        if self.skill.output_schema.value != self.manifest.output_schema:
            raise ValueError("binding skill output schema differs from manifest")
        definition_ref = ArtifactReference(self.playbook.id, self.playbook.version)
        if self.skill.playbook != definition_ref:
            raise ValueError("binding skill does not reference the bound playbook")
        if self.pins.skill != ArtifactReference(self.skill.id, self.skill.version):
            raise ValueError("binding skill pin differs from the bound skill")
        if self.pins.playbook != definition_ref:
            raise ValueError("binding playbook pin differs from the bound playbook")
        required_tools = {
            (item.name, str(item.behavior_version)) for item in self.skill.required_tools
        }
        pinned_tools = {
            (item.tool_name, str(item.version)) for item in self.pins.tool_behaviors
        }
        if pinned_tools != required_tools:
            raise ValueError("binding tool behavior pins differ from skill requirements")
        for step in self.playbook.steps:
            if isinstance(step, ToolStep) and (
                step.tool.id,
                str(step.tool.version),
            ) not in required_tools:
                raise ValueError("binding tool step differs from skill requirements")
            if isinstance(step, ModelStep) and step.prompt != self.pins.prompt:
                raise ValueError("binding model-step prompt differs from the prompt pin")
        has_dialogue = any(isinstance(step, DialogueStep) for step in self.playbook.steps)
        if self.manifest.supports_suspension != has_dialogue:
            raise ValueError("manifest suspension support differs from playbook shape")
        output_steps = tuple(
            index
            for index, step in enumerate(self.playbook.steps)
            if step.output_key == self.output_key
        )
        if output_steps != (len(self.playbook.steps) - 1,):
            raise ValueError("binding output key must identify the final playbook step")
        properties = self.manifest.input_schema.get("properties")
        required = self.manifest.input_schema.get("required")
        if not isinstance(properties, Mapping):
            raise ValueError("capability input schema must be an object schema")
        if not isinstance(required, tuple) or not all(
            isinstance(item, str) for item in required
        ):
            raise ValueError("capability input schema must declare required fields")
        property_names = tuple(properties)
        if set(property_names) != set(self.playbook.input_keys) or set(required) != set(
            self.playbook.input_keys
        ):
            raise ValueError("manifest inputs must exactly match playbook inputs")


PROFILE_SELECTION_RECEIPT_INPUT = "profile_selection_receipt"


def profiled_execution_inputs(
    public_inputs: JsonObject, receipt: ProfileSelectionReceipt
) -> JsonObject:
    """Add trusted selection provenance without widening the public manifest."""

    if not isinstance(receipt, ProfileSelectionReceipt):
        raise TypeError("profile selection receipt is invalid")
    return freeze_object(
        {
            **public_inputs,
            PROFILE_SELECTION_RECEIPT_INPUT: receipt.to_bytes().decode("utf-8"),
        }
    )


@dataclass(frozen=True, slots=True)
class ProfiledCapabilityBinding:
    """One closed internal implementation of the public flashcard capability."""

    manifest: CapabilityManifest
    manifest_fingerprint: str
    profile: PedagogicalProfileRef
    skill: SkillPackage
    playbook: PlaybookDefinition
    pins: VersionPins
    output_key: str
    dependency_resolver: CapabilityDependencyResolver

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, CapabilityManifest):
            raise TypeError("profiled binding manifest must be CapabilityManifest")
        if self.manifest.id.value != "propose_flashcards":
            raise ValueError("profiled binding accepts only propose_flashcards")
        if self.manifest_fingerprint != self.manifest.fingerprint:
            raise ValueError("profiled binding manifest fingerprint is stale")
        if not isinstance(self.profile, PedagogicalProfileRef):
            raise TypeError("profiled binding profile must use PedagogicalProfileRef")
        if not isinstance(self.skill, SkillPackage):
            raise TypeError("profiled binding skill must be SkillPackage")
        if not isinstance(self.playbook, PlaybookDefinition):
            raise TypeError("profiled binding playbook must be PlaybookDefinition")
        if not isinstance(self.pins, VersionPins):
            raise TypeError("profiled binding pins must be VersionPins")
        require_text(self.output_key, "profiled binding output_key")
        if not callable(self.dependency_resolver):
            raise TypeError("profiled binding dependency_resolver must be callable")
        if self.skill.id == self.manifest.id.value:
            raise ValueError("profile implementation skill identity must remain internal")
        if self.skill.version != self.manifest.version:
            raise ValueError("profile implementation version differs from manifest")
        if self.skill.input_schema.value != self.manifest.input_schema:
            raise ValueError("profile skill input schema differs from public manifest")
        if self.skill.output_schema.value != self.manifest.output_schema:
            raise ValueError("profile skill output schema differs from public manifest")
        if self.skill.state_write_policy.allowed_event_types:
            raise ValueError("flashcard proposal bindings forbid state writes")
        definition_ref = ArtifactReference(self.playbook.id, self.playbook.version)
        if self.skill.playbook != definition_ref:
            raise ValueError("profile skill does not reference the bound playbook")
        if self.pins.skill != ArtifactReference(self.skill.id, self.skill.version):
            raise ValueError("profile skill pin differs from the bound skill")
        if self.pins.playbook != definition_ref:
            raise ValueError("profile playbook pin differs from the bound playbook")
        required_tools = {
            (item.name, str(item.behavior_version)) for item in self.skill.required_tools
        }
        pinned_tools = {
            (item.tool_name, str(item.version)) for item in self.pins.tool_behaviors
        }
        if pinned_tools != required_tools:
            raise ValueError("profile tool behavior pins differ from skill requirements")
        validator_refs = {
            (item.validator.id, item.validator.version)
            for item in self.playbook.steps
            if isinstance(item, ValidateStep)
        }
        declared_validators = {item.id: item.version for item in self.skill.validators}
        fallback_validator_ids = {
            validator_id
            for fallback in self.skill.fallbacks
            for validator_id in fallback.validator_ids
        }
        if not fallback_validator_ids <= set(declared_validators):
            raise ValueError("profile fallback references an undeclared validator")
        if any(
            declared_validators.get(validator_id) != version
            for validator_id, version in validator_refs
        ):
            raise ValueError("profile validate-step version differs from skill validator")
        bound_validator_ids = {validator_id for validator_id, _ in validator_refs}
        if bound_validator_ids | fallback_validator_ids != set(declared_validators):
            raise ValueError("profile validator pins differ from skill validators")
        for step in self.playbook.steps:
            if isinstance(step, ToolStep) and (
                step.tool.id,
                str(step.tool.version),
            ) not in required_tools:
                raise ValueError("profile tool step differs from skill requirements")
            if isinstance(step, ModelStep) and step.prompt != self.pins.prompt:
                raise ValueError("profile model-step prompt differs from prompt pin")
            bindings = (
                step.prompt_bindings
                if isinstance(step, ModelStep)
                else step.bindings
                if isinstance(step, ToolStep | ValidateStep)
                else ()
            )
            if any(
                item.source.source is DataSourceKind.RUN_INPUT
                and item.source.key == PROFILE_SELECTION_RECEIPT_INPUT
                for item in bindings
            ):
                raise ValueError("effects cannot read the profile selection receipt")
        has_dialogue = any(isinstance(step, DialogueStep) for step in self.playbook.steps)
        if self.manifest.supports_suspension != has_dialogue:
            raise ValueError("profile manifest suspension support differs from playbook shape")
        output_steps = tuple(
            index
            for index, step in enumerate(self.playbook.steps)
            if step.output_key == self.output_key
        )
        if output_steps != (len(self.playbook.steps) - 1,):
            raise ValueError("profile output key must identify the final playbook step")
        properties = self.manifest.input_schema.get("properties")
        required = self.manifest.input_schema.get("required")
        if not isinstance(properties, Mapping) or not isinstance(required, tuple):
            raise ValueError("profile manifest input schema must be an object schema")
        public_fields = set(properties)
        if PROFILE_SELECTION_RECEIPT_INPUT in public_fields:
            raise ValueError("profile receipt key must be disjoint from public inputs")
        if set(required) != public_fields:
            raise ValueError("all profile public inputs must be required")
        if set(self.playbook.input_keys) != public_fields | {
            PROFILE_SELECTION_RECEIPT_INPUT
        }:
            raise ValueError("profile playbook inputs must add exactly the reserved receipt")
