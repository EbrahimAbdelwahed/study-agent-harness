"""Request-bound private executor for one exact planned flashcard scope."""

from __future__ import annotations

from study_agent.domain._validation import JsonObject
from study_agent.flashcards.lesson_worker_contracts import LessonWorkerRequest
from study_agent.flashcards.planning import PreparedPlannedFlashcardScope
from study_agent.playbooks import ToolExecutor
from study_agent.skills import SemanticVersion

VERSION = SemanticVersion.parse("1.0.0")


class BoundPlannedFlashcardScopeExecutor:
    name = "source.prepare_planned_flashcard_scope@1"
    behavior_version = VERSION

    def __init__(
        self,
        *,
        request: LessonWorkerRequest,
        prepared_scope: PreparedPlannedFlashcardScope,
    ) -> None:
        prepared_scope.validate_against_plan(request.plan)
        self._request = request
        self._prepared_scope = prepared_scope

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        if set(arguments) != {"query", "scope"}:
            raise ValueError(
                "source.prepare_planned_flashcard_scope@1 requires exactly query and scope"
            )
        if (
            arguments.get("query") != self._request.query
            or arguments.get("scope") != self._request.scope
        ):
            raise ValueError("planned flashcard scope arguments must equal the trusted request")
        return self._prepared_scope.to_json()


def planned_flashcard_scope_tool(
    request: LessonWorkerRequest,
    prepared_scope: PreparedPlannedFlashcardScope,
) -> ToolExecutor:
    return BoundPlannedFlashcardScopeExecutor(
        request=request,
        prepared_scope=prepared_scope,
    )


__all__ = ["BoundPlannedFlashcardScopeExecutor", "planned_flashcard_scope_tool"]
