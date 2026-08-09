from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from study_agent.domain._validation import JsonObject, freeze_object, require_text


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: MessageRole
    content: str
    name: str | None = None
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.role, MessageRole):
            raise TypeError("role must use MessageRole")
        require_text(self.content, "content")
        if self.name is not None:
            require_text(self.name, "name")
        if self.tool_call_id is not None:
            require_text(self.tool_call_id, "tool_call_id")
        if self.role is MessageRole.TOOL and self.tool_call_id is None:
            raise ValueError("tool messages require tool_call_id")
        if self.role is not MessageRole.TOOL and self.tool_call_id is not None:
            raise ValueError("only tool messages may carry tool_call_id")


@dataclass(frozen=True, slots=True)
class StructuredOutputConstraint:
    name: str
    schema: JsonObject
    strict: bool = True

    def __post_init__(self) -> None:
        require_text(self.name, "name")
        object.__setattr__(self, "schema", freeze_object(self.schema))


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    streaming: bool = False
    structured_output: bool = False
    tool_calls: bool = False
    cancellation: bool = False
    context_window_tokens: int | None = None
    extensions: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for name in ("streaming", "structured_output", "tool_calls", "cancellation"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be boolean")
        object.__setattr__(self, "extensions", frozenset(self.extensions))
        if not all(isinstance(item, str) and item for item in self.extensions):
            raise TypeError("extensions must contain non-empty strings")
        if self.context_window_tokens is not None and self.context_window_tokens < 1:
            raise ValueError("context_window_tokens must be positive")


@dataclass(frozen=True, slots=True)
class CancellationToken:
    id: str

    def __post_init__(self) -> None:
        require_text(self.id, "id")


@dataclass(frozen=True, slots=True)
class ModelRequest:
    messages: tuple[ModelMessage, ...]
    structured_output: StructuredOutputConstraint | None = None
    cancellation: CancellationToken | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    metadata: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "messages", tuple(self.messages))
        if not self.messages:
            raise ValueError("messages must not be empty")
        if not all(isinstance(item, ModelMessage) for item in self.messages):
            raise TypeError("messages must use ModelMessage")
        if self.structured_output is not None and not isinstance(
            self.structured_output, StructuredOutputConstraint
        ):
            raise TypeError("structured_output must use StructuredOutputConstraint")
        if self.cancellation is not None and not isinstance(
            self.cancellation, CancellationToken
        ):
            raise TypeError("cancellation must use CancellationToken")
        if self.max_output_tokens is not None:
            if type(self.max_output_tokens) is not int:
                raise TypeError("max_output_tokens must be an integer")
            if self.max_output_tokens < 1:
                raise ValueError("max_output_tokens must be positive")
        if self.temperature is not None:
            if not isinstance(self.temperature, (int, float)) or isinstance(
                self.temperature, bool
            ):
                raise TypeError("temperature must be a number")
            if not 0 <= self.temperature <= 2:
                raise ValueError("temperature must be between 0 and 2")
        object.__setattr__(self, "metadata", freeze_object(self.metadata))


@dataclass(frozen=True, slots=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token usage must be non-negative")


class ModelFinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CANCELLED = "cancelled"
    CONTENT_FILTER = "content_filter"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ModelInvocation:
    adapter_id: str
    adapter_version: str
    model_id: str
    response_id: str | None = None

    def __post_init__(self) -> None:
        require_text(self.adapter_id, "adapter_id")
        require_text(self.adapter_version, "adapter_version")
        require_text(self.model_id, "model_id")
        if self.response_id is not None:
            require_text(self.response_id, "response_id")


class ModelErrorCode(StrEnum):
    UNAVAILABLE = "unavailable"
    AUTHENTICATION = "authentication"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    PROTOCOL_ERROR = "protocol_error"
    CANCELLED = "cancelled"
    UNSUPPORTED_OPERATION = "unsupported_operation"


class ModelError(Exception):
    """Safe portable adapter failure with no provider response details."""

    def __init__(self, code: ModelErrorCode, message: str, *, retryable: bool = False) -> None:
        if not isinstance(code, ModelErrorCode):
            raise TypeError("model error code must use ModelErrorCode")
        if type(retryable) is not bool:
            raise TypeError("model error retryable flag must be boolean")
        require_text(message, "model error message")
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: JsonObject

    def __post_init__(self) -> None:
        require_text(self.id, "id")
        require_text(self.name, "name")
        object.__setattr__(self, "arguments", freeze_object(self.arguments))


@dataclass(frozen=True, slots=True)
class ModelResponse:
    content: str
    usage: ModelUsage | None
    finish_reason: ModelFinishReason
    invocation: ModelInvocation
    tool_calls: tuple[ToolCall, ...] = ()
    structured_output: JsonObject | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("content must be text")
        if self.usage is not None and not isinstance(self.usage, ModelUsage):
            raise TypeError("usage must use ModelUsage")
        if not isinstance(self.invocation, ModelInvocation):
            raise TypeError("invocation must use ModelInvocation")
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))
        if not all(isinstance(item, ToolCall) for item in self.tool_calls):
            raise TypeError("tool_calls must use ToolCall")
        try:
            object.__setattr__(self, "finish_reason", ModelFinishReason(self.finish_reason))
        except ValueError as error:
            raise ValueError("finish_reason must use the portable vocabulary") from error
        if not self.content and not self.tool_calls and self.structured_output is None:
            raise ValueError("response must contain content, tool calls, or structured output")
        if self.finish_reason is ModelFinishReason.TOOL_CALLS and not self.tool_calls:
            raise ValueError("tool_calls finish reason requires at least one tool call")
        if self.tool_calls and self.finish_reason is not ModelFinishReason.TOOL_CALLS:
            raise ValueError("tool call responses require the tool_calls finish reason")
        if self.structured_output is not None:
            if not isinstance(self.structured_output, Mapping):
                raise TypeError("structured_output must be a JSON object")
            object.__setattr__(
                self, "structured_output", freeze_object(self.structured_output)
            )


class ModelStreamEventKind(StrEnum):
    CONTENT_DELTA = "content_delta"
    TOOL_CALL = "tool_call"
    USAGE = "usage"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ModelStreamEvent:
    kind: ModelStreamEventKind
    content_delta: str | None = None
    tool_call: ToolCall | None = None
    usage: ModelUsage | None = None
    finish_reason: ModelFinishReason | None = None
    error: ModelError | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ModelStreamEventKind):
            raise TypeError("stream event kind must use ModelStreamEventKind")
        if self.tool_call is not None and not isinstance(self.tool_call, ToolCall):
            raise TypeError("tool_call must use ToolCall")
        if self.usage is not None and not isinstance(self.usage, ModelUsage):
            raise TypeError("usage must use ModelUsage")
        if self.finish_reason is not None and not isinstance(
            self.finish_reason, ModelFinishReason
        ):
            raise TypeError("finish_reason must use ModelFinishReason")
        if self.error is not None and not isinstance(self.error, ModelError):
            raise TypeError("error must use ModelError")
        present = {
            "content_delta": self.content_delta is not None,
            "tool_call": self.tool_call is not None,
            "usage": self.usage is not None,
            "finish_reason": self.finish_reason is not None,
            "error": self.error is not None,
        }
        expected = {
            ModelStreamEventKind.CONTENT_DELTA: "content_delta",
            ModelStreamEventKind.TOOL_CALL: "tool_call",
            ModelStreamEventKind.USAGE: "usage",
            ModelStreamEventKind.COMPLETED: "finish_reason",
            ModelStreamEventKind.ERROR: "error",
        }.get(self.kind)
        if self.kind is ModelStreamEventKind.CANCELLED:
            if any(present.values()):
                raise ValueError("cancelled stream events carry no payload")
        elif expected is None or not present[expected] or sum(present.values()) != 1:
            raise ValueError(f"{self.kind.value} stream event has invalid payload fields")
        if self.content_delta is not None:
            require_text(self.content_delta, "content_delta")


class ModelPort(Protocol):
    @property
    def capabilities(self) -> ModelCapabilities: ...

    async def generate(self, request: ModelRequest) -> ModelResponse: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...

    async def cancel(self, token: CancellationToken) -> None: ...
