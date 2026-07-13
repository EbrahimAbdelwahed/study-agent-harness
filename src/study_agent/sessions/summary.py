"""Deterministic, bounded continuation summaries derived from canonical history."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from study_agent.domain.grounding import SegmentKind
from study_agent.domain.session import (
    AnswerRecord,
    ContinuationSummaryV1,
    InteractionKind,
    InteractionRecord,
    SummaryExchange,
)

MAX_RECENT_EXCHANGES = 4
MAX_SUMMARY_CHARACTERS = 2_000
_ELLIPSIS = "…"


def build_continuation_summary(
    interactions: Sequence[InteractionRecord],
    answers: Mapping[str, AnswerRecord],
) -> ContinuationSummaryV1:
    """Build v1 context from ordered canonical interactions, never raw model state."""
    ordered = tuple(interactions)
    if not ordered:
        raise ValueError("cannot summarize an empty session")
    if len({item.id for item in ordered}) != len(ordered):
        raise ValueError("canonical interactions must have unique ids")
    by_id = {str(item.id): item for item in ordered}
    candidates: list[tuple[InteractionRecord, InteractionRecord, AnswerRecord]] = []
    for assistant in ordered:
        if assistant.kind is not InteractionKind.ASSISTANT:
            continue
        if assistant.answer_id is None:
            raise ValueError("assistant interaction is missing answer linkage")
        try:
            answer = answers[str(assistant.answer_id)]
            learner = by_id[str(answer.question_interaction_id)]
        except KeyError as error:
            raise ValueError("assistant summary linkage is not canonical") from error
        if learner.kind is not InteractionKind.HUMAN:
            raise ValueError("answer question linkage must target a human interaction")
        if answer.interaction_id != assistant.id or answer.run_id != assistant.run_id:
            raise ValueError("answer and assistant interaction linkage disagree")
        candidates.append((learner, assistant, answer))

    # Allocate a single Unicode-character budget newest first. Older exchanges
    # are dropped before any newer one; individual excerpts keep their prefix.
    remaining = MAX_SUMMARY_CHARACTERS
    selected_reversed: list[SummaryExchange] = []
    selected_records: list[AnswerRecord] = []
    for learner, assistant, answer in reversed(candidates[-MAX_RECENT_EXCHANGES:]):
        needs_unsupported = answer.answer.unsupported_information_note is not None
        minimum = 3 if needs_unsupported else 2
        if remaining < minimum:
            break
        # Reserve at least one character for each remaining required field.
        learner_excerpt, used = _bounded_excerpt(
            learner.content, remaining - (2 if needs_unsupported else 1)
        )
        remaining -= used
        assistant_excerpt, used = _bounded_excerpt(
            assistant.content, remaining - (1 if needs_unsupported else 0)
        )
        remaining -= used
        unsupported_note = None
        if answer.answer.unsupported_information_note is not None:
            unsupported_note, used = _bounded_excerpt(
                answer.answer.unsupported_information_note, remaining
            )
            remaining -= used
        selected_reversed.append(
            SummaryExchange(
                learner.id,
                assistant.id,
                learner_excerpt,
                assistant_excerpt,
                answer.answer.status,
                unsupported_note,
            )
        )
        selected_records.append(answer)
    exchanges = tuple(reversed(selected_reversed))
    selected_records.reverse()

    grounded: list[str] = []
    unresolved: list[str] = []
    for answer in selected_records:
        for segment in answer.answer.segments:
            if segment.kind in (SegmentKind.SUPPORTED_CLAIM, SegmentKind.SYNTHESIS):
                grounded.append(segment.text)
        if answer.answer.unsupported_information_note is not None:
            unresolved.append(answer.answer.unsupported_information_note)
    # Notes are canonical learner context. Keep only notes at or before the
    # through interaction and newest-first under a bounded four-item window.
    notes = [item.content for item in ordered if item.kind is InteractionKind.NOTE]
    unresolved.extend(notes[-MAX_RECENT_EXCHANGES:])

    grounded_points, remaining = _bounded_values(_deduplicate(grounded), remaining)
    unresolved_notes, remaining = _bounded_values(
        _deduplicate(unresolved), remaining
    )
    del remaining
    character_count = sum(
        len(exchange.learner_excerpt)
        + len(exchange.assistant_excerpt)
        + (len(exchange.unsupported_note) if exchange.unsupported_note is not None else 0)
        for exchange in exchanges
    ) + sum(map(len, (*grounded_points, *unresolved_notes)))
    return ContinuationSummaryV1(
        through_interaction_id=ordered[-1].id,
        interaction_count=len(ordered),
        recent_exchanges=exchanges,
        grounded_points=grounded_points,
        unresolved_notes=unresolved_notes,
        character_count=character_count,
    )


def verify_continuation_summary(
    summary: ContinuationSummaryV1,
    interactions: Sequence[InteractionRecord],
    answers: Mapping[str, AnswerRecord],
) -> None:
    expected = build_continuation_summary(interactions, answers)
    if summary != expected:
        raise ValueError("continuation summary does not match canonical session history")


def _bounded_excerpt(value: str, remaining: int) -> tuple[str, int]:
    if remaining < 1:
        return "", 0
    if len(value) <= remaining:
        return value, len(value)
    if remaining == 1:
        return _ELLIPSIS, 1
    result = value[: remaining - 1] + _ELLIPSIS
    return result, len(result)


def _deduplicate(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _bounded_values(values: Sequence[str], remaining: int) -> tuple[tuple[str, ...], int]:
    selected_reversed: list[str] = []
    for value in reversed(values):
        if remaining == 0:
            break
        excerpt, used = _bounded_excerpt(value, remaining)
        selected_reversed.append(excerpt)
        remaining -= used
    return tuple(reversed(selected_reversed)), remaining
