"""Request-bound private whole-scope preparation executor."""

from __future__ import annotations

from study_agent.domain import ExecutionContext
from study_agent.domain._validation import JsonObject, require_text
from study_agent.playbooks import ToolExecutor
from study_agent.ports.flashcard import FlashcardScopePreparationPort
from study_agent.skills import SemanticVersion

VERSION = SemanticVersion.parse("1.0.0")


class BoundFlashcardScopeExecutor:
    """Expose preparation only for the exact trusted request bound at construction."""

    name = "source.prepare_flashcard_scope@1"
    behavior_version = VERSION

    def __init__(
        self,
        *,
        context: ExecutionContext,
        query: str,
        scope: str | None,
        preparation: FlashcardScopePreparationPort,
    ) -> None:
        require_text(query, "query")
        if scope is not None:
            require_text(scope, "scope")
        self._context = context
        self._query = query
        self._scope = scope
        self._preparation = preparation

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        if set(arguments) != {"query", "scope"}:
            raise ValueError(
                "source.prepare_flashcard_scope@1 requires exactly query and scope"
            )
        if arguments.get("query") != self._query or arguments.get("scope") != self._scope:
            raise ValueError("flashcard scope arguments must equal the trusted request")
        return self._preparation.prepare(
            self._context, self._query, self._scope
        ).to_json()


def flashcard_scope_playbook_tools(
    *,
    context: ExecutionContext,
    query: str,
    scope: str | None,
    preparation: FlashcardScopePreparationPort,
) -> tuple[ToolExecutor, ...]:
    return (
        BoundFlashcardScopeExecutor(
            context=context,
            query=query,
            scope=scope,
            preparation=preparation,
        ),
    )


__all__ = ["BoundFlashcardScopeExecutor", "flashcard_scope_playbook_tools"]
