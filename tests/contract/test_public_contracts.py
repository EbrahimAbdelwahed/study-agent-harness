from __future__ import annotations

import inspect
from typing import cast

import pytest

from study_agent.domain import ExecutionContext, GroundedAnswer
from study_agent.domain._validation import JsonObject
from study_agent.ports import (
    MessageRole,
    ModelCapabilities,
    ModelFinishReason,
    ModelInvocation,
    ModelMessage,
    ModelPort,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    RetrievalPort,
    ToolCall,
)


def test_public_contracts_are_importable_without_implementation_packages() -> None:
    assert GroundedAnswer.__module__.startswith("study_agent.domain")
    assert ExecutionContext.__module__.startswith("study_agent.domain")
    assert ModelPort.__module__.startswith("study_agent.ports")
    assert RetrievalPort.__module__.startswith("study_agent.ports")


def test_model_port_is_transport_only_and_exposes_stream_and_cancellation() -> None:
    members = dict(inspect.getmembers(ModelPort))
    assert {"capabilities", "generate", "stream", "cancel"} <= members.keys()
    assert "prompt" not in ModelRequest.__dataclass_fields__
    assert "study_policy" not in ModelRequest.__dataclass_fields__


def test_model_contracts_own_collection_inputs_and_freeze_structured_output() -> None:
    messages = [ModelMessage(MessageRole.USER, "Question")]
    extensions = {"json_schema"}
    calls = [ToolCall("call-1", "source.search", {"query": "heart"})]
    structured = {"answer": {"citations": ["chunk-1"]}}

    request = ModelRequest(messages)  # type: ignore[arg-type]
    capabilities = ModelCapabilities(extensions=extensions)  # type: ignore[arg-type]
    response = ModelResponse(
        "",
        ModelUsage(3, 2),
        ModelFinishReason.TOOL_CALLS,
        ModelInvocation("test", "1.0.0", "scripted"),
        calls,  # type: ignore[arg-type]
        cast(JsonObject, structured),
    )
    messages.clear()
    extensions.clear()
    calls.clear()
    structured["answer"] = {"citations": []}

    assert len(request.messages) == 1
    assert capabilities.extensions == frozenset({"json_schema"})
    assert len(response.tool_calls) == 1
    assert response.structured_output == {"answer": {"citations": ("chunk-1",)}}
    with pytest.raises(TypeError):
        assert response.structured_output is not None
        response.structured_output["answer"] = {}  # type: ignore[index]


def test_model_response_validates_finish_reason_and_output_presence() -> None:
    usage = ModelUsage(0, 0)
    invocation = ModelInvocation("test", "1.0.0", "scripted")
    with pytest.raises(ValueError, match="finish_reason"):
        ModelResponse("answer", usage, " ", invocation)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must contain"):
        ModelResponse("", usage, ModelFinishReason.STOP, invocation)
