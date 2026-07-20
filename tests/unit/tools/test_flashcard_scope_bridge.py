from __future__ import annotations

import asyncio
from hashlib import sha256

import pytest

from study_agent.domain import (
    ChunkId,
    Citation,
    CorrelationId,
    CourseId,
    ExecutionContext,
    PrincipalKind,
    RevisionId,
    SourceChunk,
    SourceId,
)
from study_agent.flashcards import FlashcardScopeIndexEntry, PreparedFlashcardScope
from study_agent.grounding import EvidenceEnvelope
from study_agent.ports import (
    EvidenceStatus,
    RetrievalEvidence,
    RetrievalEvidenceSet,
    retrieval_read_set_fingerprint,
)
from study_agent.tools.flashcard_scope_bridge import (
    BoundFlashcardScopeExecutor,
    flashcard_scope_playbook_tools,
)


def _context() -> ExecutionContext:
    return ExecutionContext(
        PrincipalKind.HUMAN,
        "fixture-learner",
        CourseId("fixture-course"),
        CorrelationId("fixture-correlation"),
        frozenset({"course:read"}),
    )


def _prepared() -> PreparedFlashcardScope:
    text = "The aortic root contains three sinuses."
    source_id = SourceId("fixture-source")
    revision_id = RevisionId("fixture-revision")
    chunk = SourceChunk(
        ChunkId("fixture-chunk"),
        source_id,
        revision_id,
        0,
        len(text),
        (),
        0,
        sha256(text.encode()).hexdigest(),
        "fixture-chunker-v1",
    )
    citation = Citation(
        source_id,
        revision_id,
        chunk.chunk_id,
        0,
        len(text),
        "Fixture > aortic root",
        text,
    )
    retrieval = (RetrievalEvidence(chunk, citation, text, 1.0),)
    envelope = EvidenceEnvelope.from_retrieval(
        RetrievalEvidenceSet(
            EvidenceStatus.SUFFICIENT,
            retrieval,
            "a" * 64,
            "fixture_lexical",
            "1.0.0",
            "fixture-index-v1",
            retrieval_read_set_fingerprint(retrieval),
        )
    )
    return PreparedFlashcardScope.prepare(
        (
            FlashcardScopeIndexEntry(
                "aortic-root",
                "Aortic root",
                "Fixture > aortic root",
                0,
                len(text),
                (envelope.items[0].handle,),
            ),
        ),
        envelope,
    )


class RecordingPreparation:
    def __init__(self, result: PreparedFlashcardScope) -> None:
        self.result = result
        self.calls: list[tuple[ExecutionContext, str, str | None]] = []

    def prepare(
        self, context: ExecutionContext, query: str, scope: str | None
    ) -> PreparedFlashcardScope:
        self.calls.append((context, query, scope))
        return self.result


@pytest.mark.parametrize("scope", (None, "Cardiac anatomy"))
def test_bound_executor_returns_exact_port_result_for_the_trusted_request(
    scope: str | None,
) -> None:
    context = _context()
    result = _prepared()
    preparation = RecordingPreparation(result)
    executor = BoundFlashcardScopeExecutor(
        context=context,
        query="Prepare the aortic root",
        scope=scope,
        preparation=preparation,
    )

    output = asyncio.run(
        executor.invoke({"query": "Prepare the aortic root", "scope": scope})
    )

    assert output == result.to_json()
    assert preparation.calls == [(context, "Prepare the aortic root", scope)]
    assert executor.name == "source.prepare_flashcard_scope@1"
    assert str(executor.behavior_version) == "1.0.0"


@pytest.mark.parametrize(
    "arguments",
    (
        {},
        {"query": "Prepare the aortic root"},
        {"scope": None},
        {"query": "different", "scope": None},
        {"query": "Prepare the aortic root", "scope": "different"},
        {
            "query": "Prepare the aortic root",
            "scope": None,
            "course_id": "forged-course",
        },
        {
            "query": "Prepare the aortic root",
            "scope": None,
            "principal_id": "forged-principal",
        },
        {
            "query": "Prepare the aortic root",
            "scope": None,
            "context": {"course_id": "forged-course"},
        },
    ),
)
def test_bound_executor_rejects_mismatch_and_extra_identity_before_port_invocation(
    arguments: dict[str, object],
) -> None:
    preparation = RecordingPreparation(_prepared())
    executor = BoundFlashcardScopeExecutor(
        context=_context(),
        query="Prepare the aortic root",
        scope=None,
        preparation=preparation,
    )

    with pytest.raises(ValueError):
        asyncio.run(executor.invoke(arguments))  # type: ignore[arg-type]

    assert preparation.calls == []


def test_playbook_tool_factory_exposes_only_the_request_bound_private_executor() -> None:
    context = _context()
    preparation = RecordingPreparation(_prepared())

    tools = flashcard_scope_playbook_tools(
        context=context,
        query="Prepare the aortic root",
        scope=None,
        preparation=preparation,
    )

    assert len(tools) == 1
    assert tools[0].name == "source.prepare_flashcard_scope@1"
    output = asyncio.run(
        tools[0].invoke({"query": "Prepare the aortic root", "scope": None})
    )
    assert output == preparation.result.to_json()
    assert preparation.calls == [(context, "Prepare the aortic root", None)]
