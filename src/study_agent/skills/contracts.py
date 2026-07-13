from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from functools import total_ordering

from study_agent.domain._validation import JsonObject, JsonValue, freeze_object, require_text
from study_agent.ports import ModelCapabilities

_SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_PORTABLE_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_FORBIDDEN_SELECTOR_KEYS = frozenset(
    {
        "model",
        "model_id",
        "model_name",
        "provider",
        "provider_id",
        "provider_name",
        "vendor",
        "vendor_id",
        "vendor_name",
    }
)


def _require_portable_name(value: str, field_name: str) -> None:
    require_text(value, field_name)
    if _PORTABLE_NAME.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a portable lowercase identifier")


def _reject_provider_selectors(value: JsonValue, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = key.lower().replace("-", "_")
            if normalized in _FORBIDDEN_SELECTOR_KEYS or normalized.startswith("provider_"):
                raise ValueError(f"{path}.{key} is provider/model-specific")
            if normalized.startswith("model_") and normalized not in {
                "model_input",
                "model_output",
            }:
                raise ValueError(f"{path}.{key} is provider/model-specific")
            _reject_provider_selectors(item, f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            _reject_provider_selectors(item, f"{path}[{index}]")


@total_ordering
@dataclass(frozen=True, slots=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = field(default=(), compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "prerelease", tuple(self.prerelease))
        object.__setattr__(self, "build", tuple(self.build))
        if min(self.major, self.minor, self.patch) < 0:
            raise ValueError("semantic version numbers must be non-negative")
        if any(not part or not re.fullmatch(r"[0-9A-Za-z-]+", part) for part in self.prerelease):
            raise ValueError("invalid semantic-version prerelease")
        if any(
            part.isdigit() and len(part) > 1 and part.startswith("0")
            for part in self.prerelease
        ):
            raise ValueError("numeric prerelease identifiers must not have leading zeroes")
        if any(not part or not re.fullmatch(r"[0-9A-Za-z-]+", part) for part in self.build):
            raise ValueError("invalid semantic-version build metadata")

    @classmethod
    def parse(cls, value: str) -> SemanticVersion:
        require_text(value, "semantic version")
        match = _SEMVER.fullmatch(value)
        if match is None:
            raise ValueError(f"invalid semantic version: {value}")
        prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
        build = tuple(match.group(5).split(".")) if match.group(5) else ()
        return cls(int(match.group(1)), int(match.group(2)), int(match.group(3)), prerelease, build)

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            value += f"-{'.'.join(self.prerelease)}"
        if self.build:
            value += f"+{'.'.join(self.build)}"
        return value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        self_core = (self.major, self.minor, self.patch)
        other_core = (other.major, other.minor, other.patch)
        if self_core != other_core:
            return self_core < other_core
        if not self.prerelease:
            return False
        if not other.prerelease:
            return True
        for left, right in zip(self.prerelease, other.prerelease, strict=False):
            if left == right:
                continue
            if left.isdigit() and right.isdigit():
                return int(left) < int(right)
            if left.isdigit() != right.isdigit():
                return left.isdigit()
            return left < right
        return len(self.prerelease) < len(other.prerelease)


@dataclass(frozen=True, slots=True)
class VersionRange:
    minimum: SemanticVersion
    maximum_exclusive: SemanticVersion

    def __post_init__(self) -> None:
        if self.minimum >= self.maximum_exclusive:
            raise ValueError("version range minimum must precede maximum_exclusive")

    def contains(self, version: SemanticVersion) -> bool:
        return self.minimum <= version < self.maximum_exclusive


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    id: str
    version: SemanticVersion

    def __post_init__(self) -> None:
        _require_portable_name(self.id, "artifact id")


@dataclass(frozen=True, slots=True)
class JsonSchema:
    value: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", freeze_object(self.value))


class PromptLayerKind(StrEnum):
    STUDY_SECURITY_POLICY = "study_security_policy"
    COURSE_PROFILE = "course_profile"
    TASK_INSTRUCTION = "task_instruction"
    CONTINUATION_SUMMARY = "continuation_summary"
    RETRIEVED_EVIDENCE = "retrieved_evidence"
    OUTPUT_SCHEMA = "output_schema"


@dataclass(frozen=True, slots=True)
class PromptLayer:
    id: str
    version: SemanticVersion
    kind: PromptLayerKind
    template: str
    input_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_fields", tuple(self.input_fields))
        _require_portable_name(self.id, "prompt layer id")
        require_text(self.template, "prompt layer template")
        if len(set(self.input_fields)) != len(self.input_fields):
            raise ValueError("prompt layer input_fields must be unique")
        for field_name in self.input_fields:
            _require_portable_name(field_name, "prompt layer input field")


@dataclass(frozen=True, slots=True)
class GroundingPolicy:
    require_citations: bool
    insufficient_evidence_status: str
    retrieved_content_is_untrusted: bool = True

    def __post_init__(self) -> None:
        _require_portable_name(self.insufficient_evidence_status, "insufficient evidence status")


@dataclass(frozen=True, slots=True)
class StateWritePolicy:
    allowed_event_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_event_types", tuple(self.allowed_event_types))
        if len(set(self.allowed_event_types)) != len(self.allowed_event_types):
            raise ValueError("allowed event types must be unique")
        for event_type in self.allowed_event_types:
            _require_portable_name(event_type, "allowed event type")


@dataclass(frozen=True, slots=True)
class ToolRequirement:
    name: str
    behavior_version: SemanticVersion

    def __post_init__(self) -> None:
        _require_portable_name(self.name, "tool name")


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    name: str

    def __post_init__(self) -> None:
        _require_portable_name(self.name, "capability name")


@dataclass(frozen=True, slots=True)
class CapabilityFallback:
    missing_capability: str
    strategy: str
    required_capabilities: frozenset[str] = frozenset()
    validator_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "required_capabilities", frozenset(self.required_capabilities)
        )
        object.__setattr__(self, "validator_ids", tuple(self.validator_ids))
        _require_portable_name(self.missing_capability, "missing capability")
        _require_portable_name(self.strategy, "fallback strategy")
        for capability in self.required_capabilities:
            _require_portable_name(capability, "fallback required capability")
        if len(set(self.validator_ids)) != len(self.validator_ids):
            raise ValueError("fallback validator_ids must be unique")
        for validator_id in self.validator_ids:
            _require_portable_name(validator_id, "fallback validator id")


@dataclass(frozen=True, slots=True)
class ValidatorDefinition:
    id: str
    version: SemanticVersion
    purpose: str

    def __post_init__(self) -> None:
        _require_portable_name(self.id, "validator id")
        require_text(self.purpose, "validator purpose")


@dataclass(frozen=True, slots=True)
class EvalFixture:
    id: str
    input: JsonObject
    expected: JsonObject

    def __post_init__(self) -> None:
        _require_portable_name(self.id, "fixture id")
        frozen_input = freeze_object(self.input)
        frozen_expected = freeze_object(self.expected)
        object.__setattr__(self, "input", frozen_input)
        object.__setattr__(self, "expected", frozen_expected)


@dataclass(frozen=True, slots=True)
class SkillPackage:
    id: str
    version: SemanticVersion
    purpose: str
    engine_compatibility: VersionRange
    input_schema: JsonSchema
    output_schema: JsonSchema
    prompt_layers: tuple[PromptLayer, ...]
    course_profile_fields: tuple[str, ...]
    grounding_policy: GroundingPolicy
    state_write_policy: StateWritePolicy
    required_capabilities: tuple[CapabilityRequirement, ...]
    required_tools: tuple[ToolRequirement, ...]
    playbook: ArtifactReference
    fallbacks: tuple[CapabilityFallback, ...] = ()
    validators: tuple[ValidatorDefinition, ...] = ()
    known_failure_modes: tuple[str, ...] = ()
    eval_fixtures: tuple[EvalFixture, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "prompt_layers",
            "course_profile_fields",
            "required_capabilities",
            "required_tools",
            "fallbacks",
            "validators",
            "known_failure_modes",
            "eval_fixtures",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        _require_portable_name(self.id, "skill id")
        require_text(self.purpose, "skill purpose")
        if not self.prompt_layers:
            raise ValueError("skill package requires at least one prompt layer")
        _require_unique((layer.id for layer in self.prompt_layers), "prompt layer ids")
        _require_unique(self.course_profile_fields, "course profile fields")
        _require_unique((item.name for item in self.required_capabilities), "capabilities")
        _require_unique((item.name for item in self.required_tools), "tools")
        _require_unique(
            (item.missing_capability for item in self.fallbacks), "fallback capabilities"
        )
        _require_unique((item.id for item in self.validators), "validator ids")
        _require_unique((item.id for item in self.eval_fixtures), "fixture ids")
        for field_name in self.course_profile_fields:
            _require_portable_name(field_name, "course profile field")
        for failure_mode in self.known_failure_modes:
            require_text(failure_mode, "known failure mode")
        required = {item.name for item in self.required_capabilities}
        validator_ids = {item.id for item in self.validators}
        for fallback in self.fallbacks:
            if fallback.missing_capability not in required:
                raise ValueError("fallback must target a required capability")
            if not set(fallback.validator_ids) <= validator_ids:
                raise ValueError("fallback references an undeclared validator")


def _require_unique(values: Iterable[str], label: str) -> None:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise ValueError(f"{label} must be unique")


class NegotiationStatus(StrEnum):
    SUPPORTED = "supported"
    DECLARED_FALLBACK = "declared_fallback"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class CapabilityNegotiation:
    status: NegotiationStatus
    activated_fallbacks: tuple[CapabilityFallback, ...] = ()
    unsupported_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "activated_fallbacks", tuple(self.activated_fallbacks))
        object.__setattr__(
            self, "unsupported_capabilities", tuple(self.unsupported_capabilities)
        )


@dataclass(frozen=True, slots=True)
class ToolNegotiation:
    status: NegotiationStatus
    unsupported_requirements: tuple[ToolRequirement, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "unsupported_requirements", tuple(self.unsupported_requirements)
        )


def model_capability_names(capabilities: ModelCapabilities) -> frozenset[str]:
    names = set(capabilities.extensions)
    for name in ("streaming", "structured_output", "tool_calls", "cancellation"):
        if getattr(capabilities, name):
            names.add(name)
    if capabilities.context_window_tokens is not None:
        names.add("bounded_context_window")
    return frozenset(names)


def negotiate_capabilities(
    package: SkillPackage,
    available: ModelCapabilities | frozenset[str],
) -> CapabilityNegotiation:
    available_names = (
        model_capability_names(available) if isinstance(available, ModelCapabilities) else available
    )
    missing = sorted(
        requirement.name
        for requirement in package.required_capabilities
        if requirement.name not in available_names
    )
    if not missing:
        return CapabilityNegotiation(NegotiationStatus.SUPPORTED)

    fallbacks_by_capability = {item.missing_capability: item for item in package.fallbacks}
    activated: list[CapabilityFallback] = []
    unsupported: list[str] = []
    for capability in missing:
        fallback = fallbacks_by_capability.get(capability)
        if fallback is None or not fallback.required_capabilities <= available_names:
            unsupported.append(capability)
        else:
            activated.append(fallback)
    if unsupported:
        return CapabilityNegotiation(
            NegotiationStatus.UNSUPPORTED,
            unsupported_capabilities=tuple(unsupported),
        )
    return CapabilityNegotiation(
        NegotiationStatus.DECLARED_FALLBACK,
        activated_fallbacks=tuple(activated),
    )


def negotiate_tools(
    package: SkillPackage,
    available: Mapping[str, SemanticVersion],
) -> ToolNegotiation:
    available_versions = dict(available)
    unsupported = tuple(
        requirement
        for requirement in sorted(package.required_tools, key=lambda item: item.name)
        if available_versions.get(requirement.name) != requirement.behavior_version
    )
    if unsupported:
        return ToolNegotiation(NegotiationStatus.UNSUPPORTED, unsupported)
    return ToolNegotiation(NegotiationStatus.SUPPORTED)
