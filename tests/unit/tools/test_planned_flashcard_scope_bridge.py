from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, cast

import pytest

from study_agent.domain._validation import JsonObject, freeze_object
from study_agent.flashcards.lesson_worker_contracts import LessonWorkerRequest
from study_agent.flashcards.planning import PreparedPlannedFlashcardScope
from study_agent.tools import public_study_tool_manifests
from study_agent.tools.planned_flashcard_scope_bridge import (
    BoundPlannedFlashcardScopeExecutor,
    planned_flashcard_scope_tool,
)


@dataclass(frozen=True)
class _RequestDouble:
    query: str = "Generate grounded cards"
    scope: str = "the uploaded lesson"
    plan: object = "exact-plan"


class _ScopeDouble:
    def __init__(self) -> None:
        self.validated_plan: object | None = None

    def validate_against_plan(self, plan: object) -> None:
        self.validated_plan = plan

    def to_json(self) -> JsonObject:
        return freeze_object({"wrapper_fingerprint": "a" * 64})


def _bound() -> tuple[LessonWorkerRequest, PreparedPlannedFlashcardScope]:
    return (
        cast(Any, _RequestDouble()),
        cast(Any, _ScopeDouble()),
    )


def test_private_executor_returns_only_the_exact_construction_bound_wrapper() -> None:
    request, wrapper = _bound()
    executor = planned_flashcard_scope_tool(request, wrapper)

    result = asyncio.run(executor.invoke({"query": request.query, "scope": request.scope}))

    assert result == wrapper.to_json()
    assert executor.name == "source.prepare_planned_flashcard_scope@1"
    assert "context" not in inspect.signature(executor.invoke).parameters
    assert cast(Any, wrapper).validated_plan == request.plan


@pytest.mark.parametrize(
    "arguments",
    (
        {"query": "changed", "scope": "the uploaded lesson"},
        {"query": "Generate grounded cards", "scope": "changed"},
        {"query": "Generate grounded cards"},
        {
            "query": "Generate grounded cards",
            "scope": "the uploaded lesson",
            "authority": "forged",
        },
    ),
)
def test_private_executor_rejects_changed_missing_or_extra_arguments(
    arguments: dict[str, str],
) -> None:
    request, wrapper = _bound()
    executor = BoundPlannedFlashcardScopeExecutor(
        request=request,
        prepared_scope=wrapper,
    )

    with pytest.raises(ValueError):
        asyncio.run(executor.invoke(arguments))


def test_private_executor_is_absent_from_the_seven_public_tools() -> None:
    names = tuple(manifest.name for manifest in public_study_tool_manifests())
    assert len(names) == 7
    assert "source.prepare_planned_flashcard_scope" not in names
    assert "source.prepare_planned_flashcard_scope@1" not in names
