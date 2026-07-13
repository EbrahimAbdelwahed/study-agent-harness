"""Immutable JSON-only contracts for externally hosted study tools."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256

from study_agent.domain._validation import JsonObject, JsonValue, freeze_object, require_text


class ToolEffect(StrEnum):
    READ_ONLY = "read_only"
    CANONICAL_WRITE = "canonical_write"
    ORCHESTRATION = "orchestration"


class IdempotencyMode(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    REQUIRED = "required"


class ToolErrorCode(StrEnum):
    INVALID_ARGUMENTS = "invalid_arguments"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RETRYABLE_CONFLICT = "retryable_conflict"
    INCOMPATIBLE_RUNTIME = "incompatible_runtime"
    EXECUTION_FAILED = "execution_failed"


class StudyEventKind(StrEnum):
    GROUNDING_ACCEPTED = "grounding.accepted"
    GROUNDING_COMPLETED = "grounding.completed"
    GROUNDING_SUSPENDED = "grounding.suspended"
    GROUNDING_FAILED = "grounding.failed"


@dataclass(frozen=True, slots=True)
class StudyEvent:
    kind: StudyEventKind
    data: JsonObject

    def __post_init__(self) -> None:
        if not isinstance(self.kind, StudyEventKind):
            raise TypeError("study event kind must use the closed StudyEventKind vocabulary")
        object.__setattr__(self, "data", freeze_object(self.data))
        keys = frozenset(self.data)
        if self.kind is StudyEventKind.GROUNDING_ACCEPTED:
            expected = frozenset({"course_id", "session_id", "run_id"})
        elif self.kind is StudyEventKind.GROUNDING_COMPLETED:
            expected = frozenset({"course_id", "session_id", "run_id", "answer_id"})
        else:
            required = frozenset({"course_id", "error_code"})
            if not required <= keys or not keys <= required | {"session_id"}:
                raise ValueError("failed/suspended study event data has invalid fields")
            expected = keys
        if keys != expected:
            raise ValueError(f"{self.kind.value} study event data has invalid fields")
        for name, value in self.data.items():
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"study event {name} must be non-blank trimmed text")

    def to_json(self) -> JsonObject:
        return {"kind": self.kind.value, "data": self.data}


@dataclass(frozen=True, slots=True)
class ToolError:
    code: ToolErrorCode
    message: str
    retryable: bool = False
    details: JsonObject = field(default_factory=lambda: freeze_object({}))

    def __post_init__(self) -> None:
        if not isinstance(self.code, ToolErrorCode):
            raise TypeError("tool error code must use the safe ToolErrorCode vocabulary")
        if not isinstance(self.retryable, bool):
            raise TypeError("tool error retryable must be boolean")
        require_text(self.message, "tool error message")
        object.__setattr__(self, "details", freeze_object(self.details))
        if self.retryable != (self.code is ToolErrorCode.RETRYABLE_CONFLICT):
            raise ValueError("only retryable_conflict tool errors may be retryable")

    def to_json(self) -> JsonObject:
        return {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class ToolManifest:
    name: str
    version: str
    input_schema: JsonObject
    output_schema: JsonObject
    effect: ToolEffect
    required_capabilities: tuple[str, ...]
    emitted_event_kinds: tuple[str, ...]
    error_codes: tuple[ToolErrorCode, ...]
    idempotency: IdempotencyMode

    def __post_init__(self) -> None:
        if not isinstance(self.effect, ToolEffect):
            raise TypeError("tool effect must use ToolEffect")
        if not isinstance(self.idempotency, IdempotencyMode):
            raise TypeError("tool idempotency must use IdempotencyMode")
        require_text(self.name, "tool name")
        require_text(self.version, "tool version")
        object.__setattr__(self, "input_schema", freeze_object(self.input_schema))
        object.__setattr__(self, "output_schema", freeze_object(self.output_schema))
        object.__setattr__(self, "required_capabilities", tuple(self.required_capabilities))
        object.__setattr__(self, "emitted_event_kinds", tuple(self.emitted_event_kinds))
        object.__setattr__(self, "error_codes", tuple(self.error_codes))
        if not all(isinstance(item, ToolErrorCode) for item in self.error_codes):
            raise TypeError("manifest error codes must use ToolErrorCode")
        for name, values in (
            ("required_capabilities", self.required_capabilities),
            ("emitted_event_kinds", self.emitted_event_kinds),
            ("error_codes", self.error_codes),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must be unique")
        for value in (*self.required_capabilities, *self.emitted_event_kinds):
            require_text(value, "manifest declaration")

    @property
    def identity(self) -> str:
        return f"{self.name}@{self.version}"

    def to_json(self) -> JsonObject:
        return {
            "name": self.name,
            "version": self.version,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "effect": self.effect.value,
            "required_capabilities": self.required_capabilities,
            "emitted_event_kinds": self.emitted_event_kinds,
            "error_codes": tuple(item.value for item in self.error_codes),
            "idempotency": self.idempotency.value,
        }

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            _plain(self.to_json()), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        return sha256(b"study-agent-tool-manifest-v1\0" + payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ToolResult:
    value: JsonObject | None = None
    error: ToolError | None = None
    events: tuple[StudyEvent, ...] = ()

    def __post_init__(self) -> None:
        if (self.value is None) == (self.error is None):
            raise ValueError("tool result requires exactly one of value or error")
        if self.value is not None:
            object.__setattr__(self, "value", freeze_object(self.value))
        object.__setattr__(self, "events", tuple(self.events))
        if self.error is not None and not isinstance(self.error, ToolError):
            raise TypeError("tool result error must be ToolError")
        if not all(isinstance(item, StudyEvent) for item in self.events):
            raise TypeError("tool result events must be StudyEvent values")
        if self.error is not None and self.events:
            raise ValueError("failed tool results cannot claim successful events")

    @classmethod
    def success(cls, value: JsonObject, events: tuple[StudyEvent, ...] = ()) -> ToolResult:
        return cls(value=value, events=events)

    @classmethod
    def failure(cls, error: ToolError) -> ToolResult:
        return cls(error=error)

    def to_json(self) -> JsonObject:
        return {
            "value": self.value,
            "error": None if self.error is None else self.error.to_json(),
            "events": tuple(item.to_json() for item in self.events),
        }


def _plain(value: JsonValue) -> object:
    if isinstance(value, dict) or hasattr(value, "items"):
        return {key: _plain(item) for key, item in value.items()}  # type: ignore[union-attr]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value
