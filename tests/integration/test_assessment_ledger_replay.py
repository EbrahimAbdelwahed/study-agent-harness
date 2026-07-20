from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from study_agent.artifacts import AssessmentItemContent, StudyArtifactEnvelope
from study_agent.assessments import (
    ATTEMPT_RECORDED,
    GRADE_RECORDED,
    ITEM_PRESENTED,
    CriterionResult,
    DeterministicGradeProvenance,
    ProjectionAssessmentView,
    RationalScore,
    SingleChoiceResponse,
    attempt_recorded_payload,
    grade_recorded_payload,
    item_presented_payload,
    register_assessment_events,
)
from study_agent.domain import (
    Actor,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    AssessmentFormat,
    CorrelationId,
    CourseId,
    CriterionStatus,
    DomainEvent,
    GradeStatus,
    PrincipalKind,
    SessionId,
    StudyArtifactKind,
    assessment_event_id_for,
    attempt_id_for,
    presentation_id_for,
)
from study_agent.state import EventRegistry, Projection, apply_event, canonical_json_bytes

COURSE = CourseId("course")
SESSION = SessionId("session")
REVISION = ArtifactRevisionId("revision")


def _fixture() -> tuple[Projection, tuple[DomainEvent, ...], EventRegistry]:
    content = AssessmentItemContent(
        AssessmentFormat.SINGLE_CHOICE,
        "Which answer?",
        ("Alpha", "Beta"),
        "Alpha",
        ("correct",),
    )
    encoded = StudyArtifactEnvelope(StudyArtifactKind.ASSESSMENT_ITEM, content).to_bytes()
    seed = Projection(
        COURSE,
        state={
            "course": {"course_id": str(COURSE)},
            "sessions": {str(SESSION): {"course_id": str(COURSE)}},
            "study_artifacts": {
                "batches": {"batch": {"course_id": str(COURSE), "session_id": str(SESSION)}},
                "revisions": {
                    str(REVISION): {
                        "batch_id": "batch",
                        "status": ArtifactRevisionStatus.ACCEPTED.value,
                        "kind": StudyArtifactKind.ASSESSMENT_ITEM.value,
                        "content": encoded.decode(),
                    }
                },
            },
        },
    )
    presentation_payload: dict[str, object] = dict(
        item_presented_payload(
            REVISION,
            sha256(encoded).hexdigest(),
            content.format,
            content.prompt,
            content.options,
            "present",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    presentation_id = presentation_id_for(COURSE, SESSION, REVISION, "present")
    attempt_payload: dict[str, object] = dict(
        attempt_recorded_payload(
            presentation_id,
            SingleChoiceResponse("Alpha"),
            42,
            "attempt",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    attempt_id = attempt_id_for(COURSE, SESSION, presentation_id, "attempt")
    rubric = sha256(canonical_json_bytes({"evaluation_criteria": ("correct",)})).hexdigest()
    grade_payload: dict[str, object] = dict(
        grade_recorded_payload(
            attempt_id,
            GradeStatus.GRADED,
            (CriterionResult("correct", CriterionStatus.MET, "Exact"),),
            RationalScore(1, 1),
            DeterministicGradeProvenance("exact-choice", "1", "a" * 64, rubric),
            None,
            "grade",
            course_id=COURSE,
            session_id=SESSION,
        )
    )

    def event(
        sequence: int, event_type: str, payload: dict[str, object], kind: PrincipalKind
    ) -> DomainEvent:
        key = payload["idempotency_key"]
        assert isinstance(key, str)
        return DomainEvent(
            assessment_event_id_for(COURSE, SESSION, key, event_type),
            COURSE,
            sequence,
            event_type,
            1,
            Actor(kind, "actor"),
            datetime(2026, 7, 16, tzinfo=UTC) + timedelta(seconds=sequence),
            CorrelationId("correlation"),
            payload,  # type: ignore[arg-type]
            SESSION,
        )

    registry = EventRegistry()
    register_assessment_events(registry)
    return (
        seed,
        (
            event(1, ITEM_PRESENTED, presentation_payload, PrincipalKind.SERVICE),
            event(2, ATTEMPT_RECORDED, attempt_payload, PrincipalKind.HUMAN),
            event(3, GRADE_RECORDED, grade_payload, PrincipalKind.SERVICE),
        ),
        registry,
    )


def _replay(
    seed: Projection, events: tuple[DomainEvent, ...], registry: EventRegistry
) -> Projection:
    result = seed
    for event in events:
        result = apply_event(result, event, registry)
    return result


def _assessment_records(projection: Projection, kind: str) -> Mapping[str, object]:
    assessments = projection.state["assessments"]
    assert isinstance(assessments, Mapping)
    records = assessments[kind]
    assert isinstance(records, Mapping)
    return records


def test_same_event_sequence_replays_to_byte_identical_projection_and_typed_snapshot() -> None:
    seed, events, registry = _fixture()
    first = _replay(seed, events, registry)
    second = _replay(seed, events, registry)

    assert first.canonical_bytes() == second.canonical_bytes()
    first_snapshot = ProjectionAssessmentView(lambda _: first).get(COURSE)
    second_snapshot = ProjectionAssessmentView(lambda _: second).get(COURSE)
    assert first_snapshot == second_snapshot
    assert first.sequence == 3
    assert tuple(record.id for record in first_snapshot.presentations)
    assert tuple(record.id for record in first_snapshot.attempts)
    assert tuple(record.id for record in first_snapshot.grades)


def test_replay_preserves_every_prior_projection_and_strictly_increases_sequence() -> None:
    seed, events, registry = _fixture()
    snapshots = [seed]
    for event in events:
        previous = snapshots[-1]
        previous_bytes = previous.canonical_bytes()
        snapshots.append(apply_event(previous, event, registry))
        assert previous.canonical_bytes() == previous_bytes

    assert tuple(item.sequence for item in snapshots) == (0, 1, 2, 3)
    assert len(_assessment_records(snapshots[1], "presentations")) == 1
    assert len(_assessment_records(snapshots[1], "attempts")) == 0
    assert len(_assessment_records(snapshots[2], "attempts")) == 1
    assert len(_assessment_records(snapshots[2], "grades")) == 0
