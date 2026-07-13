from __future__ import annotations

from datetime import UTC, datetime, timedelta

from study_agent.domain import (
    AnswerId,
    AnswerProvenance,
    AnswerRecord,
    AnswerStatus,
    GroundedAnswer,
    InteractionId,
    InteractionKind,
    InteractionRecord,
    PromptProvenance,
    RetrievalProvenance,
    RunId,
    ValidatorProvenance,
    VersionPins,
)
from study_agent.sessions import build_continuation_summary

HASH = "a" * 64


def _answer(index: int) -> AnswerRecord:
    run_id = RunId(f"run-{index}")
    provenance = AnswerProvenance(
        (),
        PromptProvenance("grounded_answer", "1"),
        None,
        RetrievalProvenance("fts", "1", HASH, "index", "b" * 64),
        (ValidatorProvenance("evidence_sufficiency", "1", True, "terminate", "c" * 64),),
        VersionPins("skill@1", "flow@1", "prompt@1", None, "state@1", "tools@1"),
        run_id,
    )
    grounded = GroundedAnswer(
        AnswerStatus.INSUFFICIENT_EVIDENCE, (), f"unsupported-{index}", provenance
    )
    return AnswerRecord(
        AnswerId(f"answer-{index}"),
        InteractionId(f"assistant-{index}"),
        InteractionId(f"question-{index}"),
        run_id,
        f"key-{index}",
        f"{index:064x}",
        grounded,
    )


def test_summary_is_deterministic_newest_preserving_and_unicode_bounded() -> None:
    now = datetime(2026, 7, 11, tzinfo=UTC)
    interactions: list[InteractionRecord] = []
    answers: dict[str, AnswerRecord] = {}
    for index in range(6):
        answer = _answer(index)
        answers[str(answer.id)] = answer
        interactions.extend(
            (
                InteractionRecord(
                    answer.question_interaction_id,
                    InteractionKind.HUMAN,
                    now + timedelta(seconds=index * 2),
                    f"question-{index}-" + "🧠" * 350,
                ),
                InteractionRecord(
                    answer.interaction_id,
                    InteractionKind.ASSISTANT,
                    now + timedelta(seconds=index * 2 + 1),
                    f"answer-{index}-" + "é" * 350,
                    answer.id,
                    answer.run_id,
                ),
            )
        )

    first = build_continuation_summary(interactions, answers)
    second = build_continuation_summary(tuple(interactions), dict(answers))

    assert first == second
    assert len(first.recent_exchanges) <= 4
    assert first.recent_exchanges[-1].question_interaction_id == InteractionId("question-5")
    assert first.character_count <= 2_000
    assert first.character_count == sum(
        len(item.learner_excerpt)
        + len(item.assistant_excerpt)
        + (len(item.unsupported_note) if item.unsupported_note is not None else 0)
        for item in first.recent_exchanges
    ) + sum(map(len, (*first.grounded_points, *first.unresolved_notes)))
    assert first.through_interaction_id == InteractionId("assistant-5")
    assert first.interaction_count == 12
