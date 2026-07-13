from __future__ import annotations

import asyncio

import pytest

from study_agent.adapters.model import ScriptedExchange, ScriptedModel
from study_agent.ports import (
    CancellationToken,
    MessageRole,
    ModelCapabilities,
    ModelError,
    ModelErrorCode,
    ModelFinishReason,
    ModelInvocation,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventKind,
)


def request(token: CancellationToken | None = None) -> ModelRequest:
    return ModelRequest((ModelMessage(MessageRole.USER, "question"),), cancellation=token)


def response() -> ModelResponse:
    return ModelResponse(
        "answer",
        None,
        ModelFinishReason.STOP,
        ModelInvocation("scripted-model", "1.0.0", "scripted", "response-1"),
    )


def test_scripted_model_is_strict_fifo_records_immutable_history_and_exhausts() -> None:
    first, second = request(), request(CancellationToken("second"))
    model = ScriptedModel(
        (ScriptedExchange(first, response()), ScriptedExchange(second, response())),
        ModelCapabilities(),
    )

    assert asyncio.run(model.generate(first)) == response()
    assert asyncio.run(model.generate(second)) == response()
    assert model.requests == (first, second)
    model.assert_exhausted()
    with pytest.raises(ModelError, match="unexpected"):
        asyncio.run(model.generate(first))


def test_scripted_model_owns_invocation_provenance_and_preserves_response_id() -> None:
    expected = request()
    spoofed = ModelResponse(
        "answer",
        None,
        ModelFinishReason.STOP,
        ModelInvocation("spoofed", "99", "wrong-model", "fixture-response"),
    )
    model = ScriptedModel(
        (ScriptedExchange(expected, spoofed),),
        ModelCapabilities(),
        adapter_id="portable-scripted",
        adapter_version="2.1.0",
        model_id="fixture-model",
    )

    result = asyncio.run(model.generate(expected))

    assert result.invocation == ModelInvocation(
        "portable-scripted", "2.1.0", "fixture-model", "fixture-response"
    )
    assert spoofed.invocation.adapter_id == "spoofed"


def test_scripted_model_rejects_request_mismatch_and_supports_deterministic_stream_cancel() -> None:
    expected = request()
    stream_events = (
        ModelStreamEvent(ModelStreamEventKind.CONTENT_DELTA, content_delta="answer"),
        ModelStreamEvent(
            ModelStreamEventKind.COMPLETED,
            finish_reason=ModelFinishReason.STOP,
        ),
    )
    model = ScriptedModel(
        (ScriptedExchange(expected, response(), stream_events),),
        ModelCapabilities(streaming=True, cancellation=True),
    )

    async def consume() -> tuple[ModelStreamEvent, ...]:
        return tuple([event async for event in model.stream(expected)])

    assert asyncio.run(consume()) == stream_events
    model.assert_exhausted()

    cancelled = CancellationToken("cancelled")
    second = ScriptedModel(
        (ScriptedExchange(request(cancelled), response()),),
        ModelCapabilities(cancellation=True),
    )
    asyncio.run(second.cancel(cancelled))
    with pytest.raises(ModelError) as caught:
        asyncio.run(second.generate(request(cancelled)))
    assert caught.value.code is ModelErrorCode.CANCELLED


def test_stream_event_tagged_union_rejects_mixed_payloads() -> None:
    with pytest.raises(ValueError, match="invalid payload"):
        ModelStreamEvent(
            ModelStreamEventKind.CONTENT_DELTA,
            content_delta="text",
            finish_reason=ModelFinishReason.STOP,
        )
