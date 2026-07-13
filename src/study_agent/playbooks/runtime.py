from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from study_agent.domain._validation import JsonObject, freeze_object, require_text
from study_agent.domain.identifiers import RunId
from study_agent.prompts import PromptComposer
from study_agent.skills import ArtifactReference, SemanticVersion

from .contracts import (
    ReadDependency,
    StepTrace,
    ValidationOutcome,
    ValidatorDisposition,
    VersionPins,
)

STRUCTURED_OUTPUT_JSON_FALLBACK = "parse_json_then_validate"
SUPPORTED_FALLBACK_STRATEGIES = frozenset({STRUCTURED_OUTPUT_JSON_FALLBACK})


class ToolExecutor(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def behavior_version(self) -> SemanticVersion: ...

    async def invoke(self, arguments: JsonObject) -> JsonObject: ...


class ValidatorExecutor(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def version(self) -> SemanticVersion: ...

    async def validate(self, inputs: JsonObject) -> ValidationOutcome: ...


@dataclass(frozen=True, slots=True)
class PromptComposerRegistration:
    prompt: ArtifactReference
    composer: PromptComposer


class PlaybookRunStatus(StrEnum):
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    FAILED = "failed"


class EngineErrorCode(StrEnum):
    INCOMPATIBLE_ENGINE = "incompatible_engine"
    INCOMPATIBLE_PINS = "incompatible_pins"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    UNSUPPORTED_TOOL = "unsupported_tool"
    UNSUPPORTED_VALIDATOR = "unsupported_validator"
    INVALID_INPUT = "invalid_input"
    CHECKPOINT_NOT_FOUND = "checkpoint_not_found"
    INCOMPATIBLE_CHECKPOINT = "incompatible_checkpoint"
    STALE_READ_DEPENDENCY = "stale_read_dependency"
    BINDING_ERROR = "binding_error"
    TOOL_ERROR = "tool_error"
    MODEL_ERROR = "model_error"
    VALIDATOR_ERROR = "validator_error"
    RUN_STORE_ERROR = "run_store_error"
    DUPLICATE_RUN = "duplicate_run"
    SCHEMA_ERROR = "schema_error"
    UNSUPPORTED_FALLBACK = "unsupported_fallback"


@dataclass(frozen=True, slots=True)
class EngineFailure:
    code: EngineErrorCode
    message: str
    step_id: str | None = None

    def __post_init__(self) -> None:
        require_text(self.message, "engine failure message")


class PlaybookEngineError(Exception):
    def __init__(self, failure: EngineFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


@dataclass(frozen=True, slots=True)
class CompletedRunResult:
    outputs: JsonObject
    traces: tuple[StepTrace, ...]
    status: PlaybookRunStatus = field(default=PlaybookRunStatus.COMPLETED, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", freeze_object(self.outputs))
        object.__setattr__(self, "traces", tuple(self.traces))


@dataclass(frozen=True, slots=True)
class SuspendedRunResult:
    outputs: JsonObject
    traces: tuple[StepTrace, ...]
    dialogue_request: str
    status: PlaybookRunStatus = field(default=PlaybookRunStatus.SUSPENDED, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", freeze_object(self.outputs))
        object.__setattr__(self, "traces", tuple(self.traces))
        require_text(self.dialogue_request, "dialogue request")


@dataclass(frozen=True, slots=True)
class TerminatedRunResult:
    outputs: JsonObject
    traces: tuple[StepTrace, ...]
    termination: ValidationOutcome
    status: PlaybookRunStatus = field(default=PlaybookRunStatus.TERMINATED, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", freeze_object(self.outputs))
        object.__setattr__(self, "traces", tuple(self.traces))
        if self.termination.disposition is not ValidatorDisposition.TERMINATE:
            raise ValueError("terminated results require a terminate disposition")


@dataclass(frozen=True, slots=True)
class FailedRunResult:
    outputs: JsonObject
    traces: tuple[StepTrace, ...]
    failure: EngineFailure
    status: PlaybookRunStatus = field(default=PlaybookRunStatus.FAILED, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", freeze_object(self.outputs))
        object.__setattr__(self, "traces", tuple(self.traces))


type PlaybookRunResult = (
    CompletedRunResult | SuspendedRunResult | TerminatedRunResult | FailedRunResult
)


@dataclass(frozen=True, slots=True)
class VerifiedRunRecord:
    """Read-only run state whose persisted execution receipts were revalidated."""

    run_id: RunId
    definition_fingerprint: str
    inputs: JsonObject
    pins: VersionPins
    read_dependencies: tuple[ReadDependency, ...]
    outputs: JsonObject
    traces: tuple[StepTrace, ...]
    status: PlaybookRunStatus
    termination: ValidationOutcome | None = None

    def __post_init__(self) -> None:
        require_text(self.definition_fingerprint, "definition_fingerprint")
        object.__setattr__(self, "inputs", freeze_object(self.inputs))
        object.__setattr__(self, "read_dependencies", tuple(self.read_dependencies))
        object.__setattr__(self, "outputs", freeze_object(self.outputs))
        object.__setattr__(self, "traces", tuple(self.traces))
        if self.status not in {
            PlaybookRunStatus.COMPLETED,
            PlaybookRunStatus.TERMINATED,
        }:
            raise ValueError("verified runs must be completed or terminated")
        if (self.status is PlaybookRunStatus.TERMINATED) != (
            self.termination is not None
        ):
            raise ValueError("terminated verified runs require a termination outcome")


@dataclass(frozen=True, slots=True)
class RuntimeRegistries:
    tools: tuple[ToolExecutor, ...] = field(default_factory=tuple)
    validators: tuple[ValidatorExecutor, ...] = field(default_factory=tuple)
    prompt_composers: tuple[PromptComposerRegistration, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "validators", tuple(self.validators))
        object.__setattr__(self, "prompt_composers", tuple(self.prompt_composers))
        tool_names = tuple(tool.name for tool in self.tools)
        validator_ids = tuple(validator.id for validator in self.validators)
        prompt_refs = tuple(
            (registration.prompt.id, str(registration.prompt.version))
            for registration in self.prompt_composers
        )
        if len(set(tool_names)) != len(tool_names):
            raise ValueError("tool executor names must be unique")
        if len(set(validator_ids)) != len(validator_ids):
            raise ValueError("validator executor ids must be unique")
        if len(set(prompt_refs)) != len(prompt_refs):
            raise ValueError("prompt composer registrations must be unique")
