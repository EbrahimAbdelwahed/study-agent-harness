from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping

import pytest

from study_agent.adapters.model import (
    HttpResponse,
    OpenAICompatibleConfig,
    OpenAICompatibleModel,
    ScriptedExchange,
    ScriptedModel,
)
from study_agent.ports import (
    CancellationToken,
    MessageRole,
    ModelCapabilities,
    ModelError,
    ModelErrorCode,
    ModelFinishReason,
    ModelInvocation,
    ModelMessage,
    ModelPort,
    ModelRequest,
    ModelResponse,
)


class FakeTransport:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls: list[tuple[str, Mapping[str, str], bytes, float]] = []

    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        self.calls.append((url, headers, body, timeout_seconds))
        return HttpResponse(200, self.body)


def request() -> ModelRequest:
    return ModelRequest((ModelMessage(MessageRole.USER, "Canonical request"),))


def adapters() -> tuple[ModelPort, ...]:
    expected = request()
    scripted = ScriptedModel(
        (
            ScriptedExchange(
                expected,
                ModelResponse(
                    "answer",
                    None,
                    ModelFinishReason.STOP,
                    ModelInvocation("scripted", "1.0.0", "fixture"),
                ),
            ),
        ),
        ModelCapabilities(),
        adapter_id="contract-scripted",
        adapter_version="1.2.3",
        model_id="fixture",
    )
    response = json.dumps(
        {
            "id": "response-1",
            "choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}],
        }
    ).encode()
    http = OpenAICompatibleModel(
        OpenAICompatibleConfig("https://example.invalid/v1/chat/completions", "fixture", "key"),
        FakeTransport(response),
    )
    return scripted, http


@pytest.mark.parametrize("adapter", adapters())
def test_model_adapter_generate_contract(adapter: ModelPort) -> None:
    response = asyncio.run(adapter.generate(request()))

    assert response.content == "answer"
    assert response.invocation.adapter_id
    assert response.invocation.adapter_version
    assert response.invocation.model_id
    if isinstance(adapter, ScriptedModel):
        assert response.invocation == ModelInvocation(
            "contract-scripted", "1.2.3", "fixture"
        )
    assert not adapter.capabilities.streaming
    assert not adapter.capabilities.cancellation


@pytest.mark.parametrize("adapter", adapters())
def test_unadvertised_streaming_and_cancellation_fail_explicitly(adapter: ModelPort) -> None:
    async def consume() -> None:
        async for _ in adapter.stream(request()):
            pass

    with pytest.raises(ModelError) as stream_error:
        asyncio.run(consume())
    assert stream_error.value.code is ModelErrorCode.UNSUPPORTED_OPERATION

    with pytest.raises(ModelError) as cancel_error:
        asyncio.run(adapter.cancel(CancellationToken("cancel-1")))
    assert cancel_error.value.code is ModelErrorCode.UNSUPPORTED_OPERATION
