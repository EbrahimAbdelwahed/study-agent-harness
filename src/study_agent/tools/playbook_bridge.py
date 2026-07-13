"""Request-bound internal executors for the built-in grounding playbook.

These are deliberately not public study tools.  They close over trusted application
state so playbook arguments cannot select a course, session, principal, or source
policy.
"""

from __future__ import annotations

from collections.abc import Mapping

from study_agent.domain import ExecutionContext
from study_agent.domain._validation import JsonObject, JsonValue, freeze_json, freeze_object
from study_agent.grounding import EvidenceEnvelope
from study_agent.playbooks import ToolExecutor
from study_agent.ports import IndexReceipt, RetrievalPort, RetrievalQuery
from study_agent.skills import SemanticVersion

VERSION = SemanticVersion.parse("1.0.0")


class BoundSessionContextExecutor:
    """Expose canonical prompt context for exactly one trusted request."""

    name = "session.get_context"
    behavior_version = VERSION

    def __init__(
        self,
        *,
        context: ExecutionContext,
        course_profile: JsonObject,
        continuation_summary: JsonValue,
    ) -> None:
        self._context = context
        self._course_profile = freeze_object(course_profile)
        self._continuation_summary = freeze_json(continuation_summary)

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        if arguments:
            raise ValueError("session.get_context accepts no playbook arguments")
        source_policy = self._course_profile["source_policy"]
        return freeze_object(
            {
                "course_profile": self._course_profile,
                "continuation_summary": self._continuation_summary,
                "source_policy": source_policy,
            }
        )


class BoundSourceSearchExecutor:
    """Search one course with its canonical policy and pinned index receipt."""

    name = "source.search"
    behavior_version = VERSION

    def __init__(
        self,
        *,
        context: ExecutionContext,
        question: str,
        retrieval: RetrievalPort,
        course_profile: JsonObject,
        index_receipt: IndexReceipt,
        limit: int,
    ) -> None:
        self._context = context
        self._question = question
        self._retrieval = retrieval
        self._course_profile = freeze_object(course_profile)
        self._index_receipt = index_receipt
        self._limit = limit

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        if set(arguments) != {"query"} or arguments.get("query") != self._question:
            raise ValueError("source.search query must equal the trusted request question")
        policy = self._course_profile["source_policy"]
        if not isinstance(policy, Mapping):
            raise ValueError("canonical course source policy is invalid")
        minimum = policy.get("minimum_trust_level")
        roles = policy.get("allowed_roles")
        if not isinstance(minimum, int) or isinstance(minimum, bool):
            raise ValueError("canonical minimum trust level is invalid")
        if not isinstance(roles, tuple) or any(not isinstance(item, str) for item in roles):
            raise ValueError("canonical source roles are invalid")
        evidence = self._retrieval.search(
            RetrievalQuery(
                self._context.course_id,
                self._question,
                limit=self._limit,
                minimum_trust_level=minimum,
                source_roles=tuple(item for item in roles if isinstance(item, str)),
            )
        )
        if evidence.index_version != self._index_receipt.index_version:
            raise ValueError("retrieval index changed after the request was pinned")
        return EvidenceEnvelope.from_retrieval(evidence).to_json()


def grounding_playbook_tools(
    *,
    context: ExecutionContext,
    question: str,
    retrieval: RetrievalPort,
    course_profile: JsonObject,
    continuation_summary: JsonValue,
    index_receipt: IndexReceipt,
    limit: int = 8,
) -> tuple[ToolExecutor, ...]:
    """Build the exact private tool set required by ``grounded_answer@1``."""

    return (
        BoundSessionContextExecutor(
            context=context,
            course_profile=course_profile,
            continuation_summary=continuation_summary,
        ),
        BoundSourceSearchExecutor(
            context=context,
            question=question,
            retrieval=retrieval,
            course_profile=course_profile,
            index_receipt=index_receipt,
            limit=limit,
        ),
    )


__all__ = [
    "BoundSessionContextExecutor",
    "BoundSourceSearchExecutor",
    "grounding_playbook_tools",
]
