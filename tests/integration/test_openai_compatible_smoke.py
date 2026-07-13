from __future__ import annotations

import asyncio
import os

import pytest

from study_agent.adapters.model import OpenAICompatibleConfig, OpenAICompatibleModel
from study_agent.ports import MessageRole, ModelMessage, ModelRequest

pytestmark = pytest.mark.skipif(
    os.environ.get("STUDY_AGENT_MODEL_SMOKE") != "1",
    reason="opt-in network model smoke is disabled",
)


def test_opt_in_openai_compatible_generate_smoke() -> None:
    endpoint = os.environ.get("STUDY_AGENT_MODEL_ENDPOINT")
    model_id = os.environ.get("STUDY_AGENT_MODEL_ID")
    api_key = os.environ.get("STUDY_AGENT_MODEL_API_KEY")
    if not endpoint or not model_id or not api_key:
        pytest.skip("endpoint, model id, and API key are required for opt-in smoke")
    adapter = OpenAICompatibleModel(OpenAICompatibleConfig(endpoint, model_id, api_key))

    response = asyncio.run(
        adapter.generate(
            ModelRequest(
                (ModelMessage(MessageRole.USER, "Reply with the word OK."),),
                max_output_tokens=8,
                temperature=0,
            )
        )
    )

    assert response.content.strip()
