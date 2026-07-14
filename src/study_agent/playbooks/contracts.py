from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from study_agent.domain._validation import JsonObject, freeze_object, require_aware, require_text
from study_agent.domain.identifiers import RunId
from study_agent.portability import reject_provider_selectors
from study_agent.ports import ModelRequest
from study_agent.skills.contracts import (
    ArtifactReference,
    CapabilityRequirement,
    JsonSchema,
    SemanticVersion,
    VersionRange,
    _require_portable_name,
)


class DataSourceKind(StrEnum):
    RUN_INPUT = "run_input"
    STEP_OUTPUT = "step_output"


@dataclass(frozen=True, slots=True)
class DataReference:
    source: DataSourceKind
    key: str
    path: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", tuple(self.path))
        _require_portable_name(self.key, "data reference key")
        for part in self.path:
            _require_portable_name(part, "data reference path part")


@dataclass(frozen=True, slots=True)
class DataBinding:
    target: str
    source: DataReference

    def __post_init__(self) -> None:
        _require_portable_name(self.target, "binding target")
        reject_provider_selectors({self.target: None}, "binding")


@dataclass(frozen=True, slots=True)
class ToolStep:
    id: str
    tool: ArtifactReference
    arguments: JsonObject
    output_key: str
    bindings: tuple[DataBinding, ...] = ()
    kind: str = field(default="tool", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bindings", tuple(self.bindings))
        _require_step_fields(self.id, self.output_key)
        frozen = freeze_object(self.arguments)
        reject_provider_selectors(frozen, "tool arguments")
        object.__setattr__(self, "arguments", frozen)
        _require_unique_binding_targets(self.bindings)


@dataclass(frozen=True, slots=True)
class ModelStep:
    id: str
    prompt: ArtifactReference
    request: ModelRequest
    output_schema: JsonSchema
    output_key: str
    required_capabilities: tuple[CapabilityRequirement, ...] = ()
    prompt_bindings: tuple[DataBinding, ...] = ()
    kind: str = field(default="model", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "required_capabilities", tuple(self.required_capabilities)
        )
        object.__setattr__(self, "prompt_bindings", tuple(self.prompt_bindings))
        _require_step_fields(self.id, self.output_key)
        reject_provider_selectors(self.request.metadata, "model request metadata")
        names = tuple(item.name for item in self.required_capabilities)
        if len(set(names)) != len(names):
            raise ValueError("model step capabilities must be unique")
        _require_unique_binding_targets(self.prompt_bindings)


@dataclass(frozen=True, slots=True)
class DialogueStep:
    id: str
    request_text: str
    response_schema: JsonSchema
    output_key: str
    kind: str = field(default="dialogue", init=False)

    def __post_init__(self) -> None:
        _require_step_fields(self.id, self.output_key)
        require_text(self.request_text, "dialogue request_text")


@dataclass(frozen=True, slots=True)
class ValidateStep:
    id: str
    validator: ArtifactReference
    input_keys: tuple[str, ...]
    output_key: str
    bindings: tuple[DataBinding, ...] = ()
    kind: str = field(default="validate", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_keys", tuple(self.input_keys))
        object.__setattr__(self, "bindings", tuple(self.bindings))
        _require_step_fields(self.id, self.output_key)
        if not self.input_keys:
            raise ValueError("validate step requires at least one input key")
        if len(set(self.input_keys)) != len(self.input_keys):
            raise ValueError("validate step input_keys must be unique")
        for input_key in self.input_keys:
            _require_portable_name(input_key, "validate input key")
        _require_unique_binding_targets(self.bindings)


class ValidatorDisposition(StrEnum):
    CONTINUE = "continue"
    TERMINATE = "terminate"


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    passed: bool
    disposition: ValidatorDisposition
    result: JsonObject
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "result", freeze_object(self.result))
        if self.disposition is ValidatorDisposition.TERMINATE:
            if self.reason is None:
                raise ValueError("terminating validation outcomes require a reason")
            require_text(self.reason, "validation outcome reason")
        elif not self.passed:
            raise ValueError("failed validation outcomes must terminate")


type PlaybookStep = ToolStep | ModelStep | DialogueStep | ValidateStep
_STEP_TYPES = (ToolStep, ModelStep, DialogueStep, ValidateStep)


def _require_step_fields(step_id: str, output_key: str) -> None:
    _require_portable_name(step_id, "step id")
    _require_portable_name(output_key, "step output key")


@dataclass(frozen=True, slots=True)
class PlaybookDefinition:
    id: str
    version: SemanticVersion
    engine_compatibility: VersionRange
    steps: tuple[PlaybookStep, ...]
    input_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "input_keys", tuple(self.input_keys))
        _require_portable_name(self.id, "playbook id")
        if len(set(self.input_keys)) != len(self.input_keys):
            raise ValueError("playbook input_keys must be unique")
        for input_key in self.input_keys:
            _require_portable_name(input_key, "playbook input key")
        if not self.steps:
            raise ValueError("playbook requires at least one step")
        if any(type(step) not in _STEP_TYPES for step in self.steps):
            raise ValueError("v0.1 playbooks accept only tool, model, dialogue, and validate steps")
        ids = tuple(step.id for step in self.steps)
        outputs = tuple(step.output_key for step in self.steps)
        if len(set(ids)) != len(ids):
            raise ValueError("playbook step ids must be unique")
        if len(set(outputs)) != len(outputs):
            raise ValueError("playbook output keys must be unique")
        available_outputs: set[str] = set()
        for step in self.steps:
            if isinstance(step, ValidateStep) and not set(step.input_keys) <= available_outputs:
                raise ValueError("validate steps may reference only previous step outputs")
            for binding in _step_bindings(step):
                if (
                    binding.source.source is DataSourceKind.RUN_INPUT
                    and binding.source.key not in self.input_keys
                ):
                    raise ValueError("binding references an undeclared run input")
                if (
                    binding.source.source is DataSourceKind.STEP_OUTPUT
                    and binding.source.key not in available_outputs
                ):
                    raise ValueError("binding references a non-previous step output")
            available_outputs.add(step.output_key)


def _step_bindings(step: PlaybookStep) -> tuple[DataBinding, ...]:
    if isinstance(step, ToolStep | ValidateStep):
        return step.bindings
    if isinstance(step, ModelStep):
        return step.prompt_bindings
    return ()


def _require_unique_binding_targets(bindings: tuple[DataBinding, ...]) -> None:
    targets = tuple(binding.target for binding in bindings)
    if len(set(targets)) != len(targets):
        raise ValueError("binding targets must be unique within a step")


@dataclass(frozen=True, slots=True)
class ToolBehaviorPin:
    tool_name: str
    version: SemanticVersion

    def __post_init__(self) -> None:
        _require_portable_name(self.tool_name, "tool behavior name")


@dataclass(frozen=True, slots=True)
class VersionPins:
    skill: ArtifactReference
    playbook: ArtifactReference
    prompt: ArtifactReference
    tool_behaviors: tuple[ToolBehaviorPin, ...]
    model_adapter: ArtifactReference
    state_contract: ArtifactReference

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_behaviors", tuple(self.tool_behaviors))
        names = tuple(item.tool_name for item in self.tool_behaviors)
        if len(set(names)) != len(names):
            raise ValueError("tool behavior pins must be unique")


@dataclass(frozen=True, slots=True)
class ReadDependency:
    kind: str
    id: str
    version: str

    def __post_init__(self) -> None:
        _require_portable_name(self.kind, "read dependency kind")
        require_text(self.id, "read dependency id")
        require_text(self.version, "read dependency version")


class RunStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PlaybookCheckpoint:
    run_id: RunId
    pins: VersionPins
    status: RunStatus
    next_step_index: int
    outputs: JsonObject
    read_dependencies: tuple[ReadDependency, ...]
    updated_at: datetime
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "read_dependencies", tuple(self.read_dependencies))
        if self.next_step_index < 0:
            raise ValueError("next_step_index must be non-negative")
        if self.schema_version < 1:
            raise ValueError("checkpoint schema_version must be positive")
        require_aware(self.updated_at, "updated_at")
        frozen = freeze_object(self.outputs)
        object.__setattr__(self, "outputs", frozen)
        dependency_keys = tuple((item.kind, item.id) for item in self.read_dependencies)
        if len(set(dependency_keys)) != len(dependency_keys):
            raise ValueError("read dependencies must be unique by kind and id")


class StepTraceStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StepTrace:
    step_id: str
    step_kind: str
    status: StepTraceStatus
    occurred_at: datetime
    details: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_portable_name(self.step_id, "trace step id")
        if self.step_kind not in {"tool", "model", "dialogue", "validate"}:
            raise ValueError("trace step_kind is not part of the v0.1 AST")
        require_aware(self.occurred_at, "occurred_at")
        frozen = freeze_object(self.details)
        object.__setattr__(self, "details", frozen)
