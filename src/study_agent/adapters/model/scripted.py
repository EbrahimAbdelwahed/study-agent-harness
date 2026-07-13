"""Strict deterministic model adapter for offline tests and evals."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field, replace

from study_agent.ports.model import (
    CancellationToken,
    ModelCapabilities,
    ModelError,
    ModelErrorCode,
    ModelInvocation,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
)


@dataclass(frozen=True, slots=True)
class ScriptedExchange:
    expected_request: ModelRequest
    response: ModelResponse | ModelError
    stream_events: tuple[ModelStreamEvent, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "stream_events", tuple(self.stream_events))


class ScriptedModel:
    def __init__(
        self,
        exchanges: Sequence[ScriptedExchange],
        capabilities: ModelCapabilities,
        *,
        adapter_id: str = "scripted-model",
        adapter_version: str = "1.0.0",
        model_id: str = "scripted",
    ) -> None:
        self._exchanges = tuple(exchanges)
        self._capabilities = capabilities
        self._invocation = ModelInvocation(adapter_id, adapter_version, model_id)
        self._cursor = 0
        self._requests: list[ModelRequest] = []
        self._cancelled: set[str] = set()

    @property
    def capabilities(self) -> ModelCapabilities:
        return self._capabilities

    @property
    def requests(self) -> tuple[ModelRequest, ...]:
        return tuple(self._requests)

    def _next(self, request: ModelRequest) -> ScriptedExchange:
        if self._cursor >= len(self._exchanges):
            raise ModelError(
                ModelErrorCode.PROTOCOL_ERROR,
                "scripted model received an unexpected request",
            )
        exchange = self._exchanges[self._cursor]
        self._cursor += 1
        self._requests.append(request)
        if request != exchange.expected_request:
            raise ModelError(
                ModelErrorCode.PROTOCOL_ERROR,
                "scripted model request did not match the expected request",
            )
        if request.cancellation is not None and request.cancellation.id in self._cancelled:
            raise ModelError(ModelErrorCode.CANCELLED, "model request was cancelled")
        return exchange

    async def generate(self, request: ModelRequest) -> ModelResponse:
        exchange = self._next(request)
        if isinstance(exchange.response, ModelError):
            raise exchange.response
        return replace(
            exchange.response,
            invocation=replace(
                self._invocation,
                response_id=exchange.response.invocation.response_id,
            ),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        if not self.capabilities.streaming:
            raise ModelError(
                ModelErrorCode.UNSUPPORTED_OPERATION,
                "model streaming is not supported",
            )
        exchange = self._next(request)
        if isinstance(exchange.response, ModelError):
            raise exchange.response
        for event in exchange.stream_events:
            yield event

    async def cancel(self, token: CancellationToken) -> None:
        if not self.capabilities.cancellation:
            raise ModelError(
                ModelErrorCode.UNSUPPORTED_OPERATION,
                "model cancellation is not supported",
            )
        self._cancelled.add(token.id)

    def assert_exhausted(self) -> None:
        if self._cursor != len(self._exchanges):
            raise AssertionError(
                f"scripted model has {len(self._exchanges) - self._cursor} unconsumed exchanges"
            )
