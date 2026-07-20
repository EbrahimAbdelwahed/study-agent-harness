from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

import pytest

from study_agent.domain import (
    CourseId,
    EventId,
    InteractionId,
    SessionId,
    SessionStatus,
    StatementId,
    StudyStatementKind,
)
from study_agent.domain._validation import JsonObject
from study_agent.domain.tutor_snapshot import (
    TutorConfiguredHint,
    TutorConfiguredSourceField,
    TutorContextField,
    TutorContextState,
    TutorHintDivergence,
    TutorNote,
    TutorSnapshotV1,
    TutorStatementEvidence,
    TutorTimelineEntry,
    TutorTimelineKind,
)
from study_agent.state import canonical_json_bytes

NOW = datetime(2026, 7, 15, 8, tzinfo=UTC)
COURSE = CourseId("course-snapshot")
SESSION = SessionId("session-snapshot")


def _missing_context() -> tuple[TutorContextField, ...]:
    return tuple(
        TutorContextField(kind, TutorContextState.MISSING)
        for kind in StudyStatementKind
    )


def _snapshot(
    *,
    context: tuple[TutorContextField, ...] | None = None,
    timeline: tuple[TutorTimelineEntry, ...] = (),
    notes: tuple[TutorNote, ...] = (),
) -> TutorSnapshotV1:
    return TutorSnapshotV1(
        COURSE,
        SESSION,
        9,
        SessionStatus.ACTIVE,
        None,
        (
            TutorConfiguredHint(
                StudyStatementKind.OBJECTIVE,
                ("Pass",),
                TutorConfiguredSourceField.LEARNING_GOALS,
            ),
        ),
        context or _missing_context(),
        (),
        timeline,
        notes,
        (),
    )


def _evidence(
    kind: StudyStatementKind, value: str | date | int, suffix: str
) -> TutorStatementEvidence:
    del kind
    return TutorStatementEvidence(
        StatementId(f"statement-{suffix}"),
        SESSION,
        InteractionId(f"interaction-{suffix}"),
        value,
        NOW,
    )


def test_all_five_context_states_are_typed_and_scalar_conflict_is_explicit() -> None:
    active = {
        StudyStatementKind.OBJECTIVE: (_evidence(StudyStatementKind.OBJECTIVE, "Pass", "o"),),
        StudyStatementKind.DEADLINE: (
            _evidence(StudyStatementKind.DEADLINE, date(2026, 9, 8), "d1"),
            _evidence(StudyStatementKind.DEADLINE, date(2026, 9, 15), "d2"),
        ),
        StudyStatementKind.WEEKLY_TIME_BUDGET: (
            _evidence(StudyStatementKind.WEEKLY_TIME_BUDGET, 600, "t"),
        ),
        StudyStatementKind.ASSESSMENT_FORMAT: (
            _evidence(StudyStatementKind.ASSESSMENT_FORMAT, "oral", "a1"),
            _evidence(StudyStatementKind.ASSESSMENT_FORMAT, "written", "a2"),
        ),
        StudyStatementKind.TESTING_PREFERENCE: (),
    }
    context = tuple(
        TutorContextField(
            kind,
            (
                TutorContextState.MISSING
                if not active[kind]
                else TutorContextState.CONFLICTING
                if kind is StudyStatementKind.DEADLINE
                else TutorContextState.KNOWN
            ),
            active[kind],
        )
        for kind in StudyStatementKind
    )
    snapshot = _snapshot(context=context)
    assert tuple((item.kind, item.state) for item in snapshot.learner_context) == (
        (StudyStatementKind.OBJECTIVE, TutorContextState.KNOWN),
        (StudyStatementKind.DEADLINE, TutorContextState.CONFLICTING),
        (StudyStatementKind.WEEKLY_TIME_BUDGET, TutorContextState.KNOWN),
        (StudyStatementKind.ASSESSMENT_FORMAT, TutorContextState.KNOWN),
        (StudyStatementKind.TESTING_PREFERENCE, TutorContextState.MISSING),
    )
    with pytest.raises(ValueError, match="only scalar"):
        TutorContextField(
            StudyStatementKind.OBJECTIVE,
            TutorContextState.CONFLICTING,
            active[StudyStatementKind.OBJECTIVE],
        )


def test_configured_hint_and_learner_divergence_remain_separate() -> None:
    statement_id = StatementId("statement-deadline")
    divergence = TutorHintDivergence(
        StudyStatementKind.DEADLINE,
        (date(2026, 9, 8),),
        (date(2026, 9, 15),),
        (statement_id,),
    )
    snapshot = _snapshot()
    configured = (
        *snapshot.configured_hints,
        TutorConfiguredHint(
            StudyStatementKind.DEADLINE,
            (date(2026, 9, 8),),
            TutorConfiguredSourceField.EXAM_DATE,
        ),
    )
    context = list(snapshot.learner_context)
    context[1] = TutorContextField(
        StudyStatementKind.DEADLINE,
        TutorContextState.KNOWN,
        (
            TutorStatementEvidence(
                statement_id,
                SESSION,
                InteractionId("interaction-deadline"),
                date(2026, 9, 15),
                NOW,
            ),
        ),
    )
    with pytest.raises(ValueError, match="exactly report"):
        TutorSnapshotV1(
            snapshot.course_id,
            snapshot.session_id,
            snapshot.high_water_sequence,
            snapshot.session_status,
            snapshot.continuation_summary,
            configured,
            tuple(context),
            (),
            snapshot.timeline,
            snapshot.notes,
            snapshot.materials,
        )
    snapshot = TutorSnapshotV1(
        snapshot.course_id,
        snapshot.session_id,
        snapshot.high_water_sequence,
        snapshot.session_status,
        snapshot.continuation_summary,
        configured,
        tuple(context),
        (divergence,),
        snapshot.timeline,
        snapshot.notes,
        snapshot.materials,
    )
    document = snapshot.to_json()
    configured_json = cast(tuple[JsonObject, ...], document["configured_hints"])
    assert configured_json[1]["values"] == ("2026-09-08",)
    assert document["divergences"] == (
        {
            "kind": "deadline",
            "configured_values": ("2026-09-08",),
            "learner_values": ("2026-09-15",),
            "learner_statement_ids": ("statement-deadline",),
        },
    )
    with pytest.raises(ValueError, match="do not diverge"):
        TutorHintDivergence(
            StudyStatementKind.OBJECTIVE,
            ("Pass",),
            ("Pass",),
            (StatementId("statement-objective"),),
        )


def test_note_evidence_must_exactly_mirror_ordered_timeline() -> None:
    timeline = (
        TutorTimelineEntry(
            TutorTimelineKind.LEARNER,
            InteractionId("learner-1"),
            NOW,
            "I have lecture notes.",
            EventId("event-learner"),
            3,
        ),
        TutorTimelineEntry(
            TutorTimelineKind.NOTE,
            InteractionId("note-1"),
            NOW,
            "Review the brachial plexus.",
            EventId("event-note"),
            4,
        ),
    )
    note = TutorNote(
        InteractionId("note-1"),
        "Review the brachial plexus.",
        NOW,
        EventId("event-note"),
        4,
    )
    assert _snapshot(timeline=timeline, notes=(note,)).notes == (note,)
    with pytest.raises(ValueError, match="exactly mirror"):
        _snapshot(timeline=timeline)
    with pytest.raises(ValueError, match="unique course-sequence"):
        _snapshot(timeline=(timeline[0], timeline[0]))


def test_canonical_bytes_are_stable_and_have_no_policy_or_provider_fields() -> None:
    first = _snapshot()
    second = _snapshot()
    first_bytes = canonical_json_bytes(first.to_json())
    second_bytes = canonical_json_bytes(second.to_json())
    assert first_bytes == second_bytes
    assert first_bytes.startswith(b'{"configured_hints"')
    forbidden = (
        b"next_action",
        b"capabilities",
        b"provider",
        b"hypothesis",
        b"mastery",
        b"learning_style",
    )
    assert all(field not in first_bytes for field in forbidden)
