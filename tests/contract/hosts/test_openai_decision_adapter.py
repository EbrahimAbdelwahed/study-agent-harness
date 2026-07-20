from __future__ import annotations

import asyncio

from study_agent.adapters.host import OpenAIResponsesTutorConfig, OpenAIResponsesTutorDecisionPort
from study_agent.hosts import TutorHostContext


def test_adapter_import_and_protocol_are_offline_safe() -> None:
    assert callable(OpenAIResponsesTutorDecisionPort)
    assert OpenAIResponsesTutorConfig("gpt-5.6", "OPENAI_API_KEY")
    assert callable(TutorHostContext)
    assert asyncio.run is not None
