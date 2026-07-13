"""Runnable external-agent composition using only public host seams."""

from __future__ import annotations

import asyncio
from typing import Any

from study_agent.cli.repository import LocalRepository
from study_agent.domain import CorrelationId, CourseId, ExecutionContext, PrincipalKind

EXPECTED_TOOLS = (
    "citation.resolve",
    "course.get",
    "grounding.ask",
    "session.get_context",
    "session.record_note",
    "source.list",
    "source.search",
)


async def invoke_read_tool(
    repository_root: str,
    course_id: str,
    tool_name: str,
    model_arguments: dict[str, Any],
) -> object:
    """Let a model propose arguments while the host retains all authority."""
    with LocalRepository.open(repository_root) as repository:
        registry = repository.study_tools(CourseId(course_id))
        assert tuple(manifest.name for manifest in registry.manifests) == EXPECTED_TOOLS
        trusted_context = ExecutionContext(
            PrincipalKind.SERVICE,
            "external-agent-host",
            CourseId(course_id),
            CorrelationId("external-agent-request-1"),
            frozenset({"study:read"}),
        )
        return await registry.invoke(tool_name, model_arguments, trusted_context)


if __name__ == "__main__":  # pragma: no cover - replace with an initialized repository
    asyncio.run(invoke_read_tool("./study-repository", "course-id", "course.get", {}))
