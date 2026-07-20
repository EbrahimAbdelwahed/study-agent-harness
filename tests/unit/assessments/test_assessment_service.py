from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from study_agent.artifacts import AssessmentItemContent, StudyArtifactEnvelope
from study_agent.artifacts.contracts import (
    ArtifactBatchRecord,
    ArtifactProposalOrigin,
    ArtifactRevisionRecord,
    ArtifactSnapshot,
)
from study_agent.assessments import (
    AttemptRecord,
    MultipleChoiceResponse,
    PresentationRecord,
    ProjectionAssessmentView,
    RationalScore,
    SingleChoiceResponse,
    register_assessment_events,
)
from study_agent.assessments.grading import (
    EXACT_CLOSED_POLICY_FINGERPRINT,
    EXACT_CLOSED_POLICY_ID,
    EXACT_CLOSED_POLICY_VERSION,
    ExactClosedGradingPolicy,
)
from study_agent.assessments.service import (
    AssessmentCommandError,
    AssessmentConflictError,
    AssessmentService,
    RetryableAssessmentConflictError,
)
from study_agent.domain import (
    Actor,
    AnswerId,
    ArtifactBatchId,
    ArtifactId,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    AssessmentFormat,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    ExecutionContext,
    PrincipalKind,
    RunId,
    SessionId,
    StudyArtifactKind,
)
from study_agent.domain.session import (
    AnswerRecord,
    ContinuationSummaryV1,
    InteractionRecord,
    SessionStatus,
    StudySessionRecord,
)
from study_agent.ports import EventSequenceConflictError
from study_agent.state import EventRegistry, Projection, apply_event
from tests.unit.artifacts.test_lifecycle_events import generated_provenance

COURSE = CourseId("course")
SESSION = SessionId("session")
REVISION = ArtifactRevisionId("assessment-revision")
BATCH = ArtifactBatchId("assessment-batch")
RUN = RunId("assessment-run")
NOW = datetime(2026, 7, 16, 12, tzinfo=UTC)


class Clock:
    def now(self) -> datetime:
        return NOW


class MemoryEvents:
    def __init__(self, content: AssessmentItemContent) -> None:
        envelope = StudyArtifactEnvelope(StudyArtifactKind.ASSESSMENT_ITEM, content)
        self.registry = EventRegistry()
        register_assessment_events(self.registry)
        self.projection = Projection(
            COURSE,
            1,
            {
                "course": {"course_id": str(COURSE)},
                "sessions": {str(SESSION): {"course_id": str(COURSE)}},
                "study_artifacts": {
                    "batches": {
                        str(BATCH): {
                            "course_id": str(COURSE),
                            "session_id": str(SESSION),
                        }
                    },
                    "revisions": {
                        str(REVISION): {
                            "batch_id": str(BATCH),
                            "status": ArtifactRevisionStatus.ACCEPTED.value,
                            "kind": StudyArtifactKind.ASSESSMENT_ITEM.value,
                            "content": envelope.to_bytes().decode(),
                        }
                    },
                },
            },
        )
        self.values: list[DomainEvent] = [
            DomainEvent(
                EventId("fixture-initialized"),
                COURSE,
                1,
                "fixture.initialized",
                1,
                Actor(PrincipalKind.SERVICE, "fixture"),
                NOW,
                CorrelationId("fixture"),
            )
        ]
        self.race_mode: str | None = None

    def append(
        self, course_id: CourseId, expected_sequence: int, events: Sequence[DomainEvent]
    ) -> int:
        assert course_id == COURSE
        event = events[0]
        if self.race_mode == "fail":
            raise EventSequenceConflictError(course_id, expected_sequence, expected_sequence + 1)
        if self.race_mode == "commit_then_fail":
            self.projection = apply_event(self.projection, event, self.registry)
            self.values.append(event)
            raise EventSequenceConflictError(course_id, expected_sequence, expected_sequence + 1)
        self.projection = apply_event(self.projection, event, self.registry)
        self.values.append(event)
        return event.course_sequence

    def read(self, course_id: CourseId, after_sequence: int = 0) -> Sequence[DomainEvent]:
        assert course_id == COURSE
        return tuple(self.values[after_sequence:])


class Artifacts:
    def __init__(self, content: AssessmentItemContent) -> None:
        envelope = StudyArtifactEnvelope(StudyArtifactKind.ASSESSMENT_ITEM, content)
        revision = ArtifactRevisionRecord(
            REVISION,
            ArtifactId("assessment-artifact"),
            BATCH,
            0,
            StudyArtifactKind.ASSESSMENT_ITEM,
            ArtifactRevisionStatus.ACCEPTED,
            envelope,
            generated_provenance(envelope, run_id=RUN),
            None,
            None,
            NOW,
            NOW,
        )
        batch = ArtifactBatchRecord(
            BATCH,
            COURSE,
            SESSION,
            ArtifactProposalOrigin.GENERATED,
            (REVISION,),
            RUN,
            NOW,
        )
        self.snapshot = ArtifactSnapshot(COURSE, 1, (batch,), (revision,))

    def get(self, course_id: CourseId) -> ArtifactSnapshot:
        assert course_id == COURSE
        return self.snapshot

    def command_fingerprint(self, course_id: CourseId, event_id: EventId) -> str | None:
        assert course_id == COURSE
        return None


class Sessions:
    def list_sessions(self, course_id: CourseId) -> tuple[StudySessionRecord, ...]:
        return (self.get_session(course_id, SESSION),)

    def get_session(self, course_id: CourseId, session_id: SessionId) -> StudySessionRecord:
        return StudySessionRecord(session_id, course_id, SessionStatus.ACTIVE, NOW)

    def interactions(
        self, course_id: CourseId, session_id: SessionId
    ) -> tuple[InteractionRecord, ...]:
        return ()

    def answers(
        self, course_id: CourseId, session_id: SessionId
    ) -> tuple[AnswerRecord, ...]:
        return ()

    def get_answer(
        self, course_id: CourseId, session_id: SessionId, answer_id: AnswerId
    ) -> AnswerRecord:
        raise AssertionError("assessment tests do not read session answers")

    def get_context(
        self, course_id: CourseId, session_id: SessionId
    ) -> ContinuationSummaryV1 | None:
        return None


def _content(
    format: AssessmentFormat = AssessmentFormat.MULTIPLE_CHOICE,
) -> AssessmentItemContent:
    options = () if format is AssessmentFormat.FREE_RESPONSE else ("Alpha", "Beta", "Gamma")
    expected = '["Alpha","Gamma"]' if format is AssessmentFormat.MULTIPLE_CHOICE else "Alpha"
    return AssessmentItemContent(
        format,
        "Which answer?",
        options,
        expected,
        ("selection", "exactness"),
    )


def _context(kind: PrincipalKind, key: str, session_id: SessionId = SESSION) -> ExecutionContext:
    return ExecutionContext(
        kind,
        "assessment-host",
        COURSE,
        CorrelationId("assessment-correlation"),
        frozenset(),
        session_id,
        idempotency_key=key,
    )


def _service(
    content: AssessmentItemContent | None = None,
) -> tuple[AssessmentService, MemoryEvents]:
    item = _content() if content is None else content
    events = MemoryEvents(item)
    view = ProjectionAssessmentView(lambda _course_id: events.projection)
    return AssessmentService(events, Clock(), view, Artifacts(item), Sessions()), events


def _through_attempt(
    service: AssessmentService,
    *,
    response: MultipleChoiceResponse | SingleChoiceResponse,
) -> tuple[PresentationRecord, AttemptRecord]:
    presentation = service.present_item(REVISION, _context(PrincipalKind.SERVICE, "present"), 1)
    attempt = service.record_attempt(
        presentation.id,
        response,
        25,
        _context(PrincipalKind.HUMAN, "attempt"),
        2,
    )
    return presentation, attempt


def test_service_commits_one_ordered_event_per_stage_and_exact_grade_provenance() -> None:
    service, events = _service()
    _, attempt = _through_attempt(
        service, response=MultipleChoiceResponse(("Alpha", "Gamma"))
    )
    grade = service.grade_closed(
        attempt.id,
        _context(PrincipalKind.SERVICE, "grade"),
        3,
    )
    contest = service.contest_grade(
        grade.id,
        "Please review",
        _context(PrincipalKind.HUMAN, "contest"),
        4,
    )

    assert tuple(event.event_type for event in events.values[1:]) == (
        "assessment.item_presented",
        "assessment.attempt_recorded",
        "assessment.grade_recorded",
        "assessment.grade_contested",
    )
    assert grade.score == RationalScore(1, 1)
    assert (
        grade.provenance.policy_id,  # type: ignore[union-attr]
        grade.provenance.policy_version,  # type: ignore[union-attr]
        grade.provenance.policy_fingerprint,  # type: ignore[union-attr]
    ) == (
        EXACT_CLOSED_POLICY_ID,
        EXACT_CLOSED_POLICY_VERSION,
        EXACT_CLOSED_POLICY_FINGERPRINT,
    )
    assert contest.grade_id == grade.id
    for event in events.values[1:]:
        assert not {"mastery", "schedule", "learner_model"}.intersection(event.payload)


def test_exact_retries_return_committed_records_and_drift_fails_closed() -> None:
    service, events = _service(_content(AssessmentFormat.SINGLE_CHOICE))
    presentation, attempt = _through_attempt(
        service, response=SingleChoiceResponse("Alpha")
    )
    count = len(events.values)

    assert service.record_attempt(
        presentation.id,
        SingleChoiceResponse("Alpha"),
        25,
        _context(PrincipalKind.HUMAN, "attempt"),
        2,
    ) == attempt
    assert len(events.values) == count
    with pytest.raises(AssessmentConflictError, match="different command"):
        service.record_attempt(
            presentation.id,
            SingleChoiceResponse("Beta"),
            25,
            _context(PrincipalKind.HUMAN, "attempt"),
            3,
        )
    with pytest.raises(AssessmentConflictError, match="already has"):
        service.record_attempt(
            presentation.id,
            SingleChoiceResponse("Alpha"),
            25,
            _context(PrincipalKind.HUMAN, "attempt-again"),
            3,
        )


def test_authority_free_text_cross_session_and_stale_sequence_fail_closed() -> None:
    service, _events = _service(_content(AssessmentFormat.SINGLE_CHOICE))
    with pytest.raises(AssessmentCommandError, match="SERVICE"):
        service.present_item(REVISION, _context(PrincipalKind.MODEL, "present"), 1)
    presentation, attempt = _through_attempt(
        service, response=SingleChoiceResponse("Alpha")
    )
    with pytest.raises(AssessmentCommandError, match="HUMAN"):
        service.record_attempt(
            presentation.id,
            SingleChoiceResponse("Alpha"),
            None,
            _context(PrincipalKind.SERVICE, "wrong-authority"),
            3,
        )
    with pytest.raises(AssessmentCommandError, match="another session"):
        service.grade_closed(
            attempt.id,
            _context(PrincipalKind.SERVICE, "cross-scope", SessionId("other")),
            3,
        )
    with pytest.raises(RetryableAssessmentConflictError):
        service.grade_closed(
            attempt.id,
            _context(PrincipalKind.SERVICE, "stale"),
            2,
        )

    free_service, _ = _service(_content(AssessmentFormat.FREE_RESPONSE))
    free_presentation = free_service.present_item(
        REVISION, _context(PrincipalKind.SERVICE, "free-present"), 1
    )
    from study_agent.assessments import FreeResponse

    free_attempt = free_service.record_attempt(
        free_presentation.id,
        FreeResponse("Alpha"),
        None,
        _context(PrincipalKind.HUMAN, "free-attempt"),
        2,
    )
    with pytest.raises(AssessmentCommandError, match="free responses"):
        free_service.grade_closed(
            free_attempt.id,
            _context(PrincipalKind.SERVICE, "free-grade"),
            3,
        )


def test_append_races_are_retryable_unless_the_exact_event_committed() -> None:
    service, events = _service()
    events.race_mode = "fail"
    with pytest.raises(RetryableAssessmentConflictError):
        service.present_item(REVISION, _context(PrincipalKind.SERVICE, "present"), 1)

    service, events = _service()
    events.race_mode = "commit_then_fail"
    committed = service.present_item(
        REVISION, _context(PrincipalKind.SERVICE, "present"), 1
    )
    assert committed.revision_id == REVISION
    assert len(events.values) == 2


def test_policy_port_can_be_injected_without_importing_a_model_runtime() -> None:
    content = _content(AssessmentFormat.SINGLE_CHOICE)
    events = MemoryEvents(content)
    view = ProjectionAssessmentView(lambda _course_id: events.projection)
    policy = ExactClosedGradingPolicy()
    service = AssessmentService(events, Clock(), view, Artifacts(content), Sessions(), policy)
    _, attempt = _through_attempt(service, response=SingleChoiceResponse("Beta"))
    grade = service.grade_closed(
        attempt.id,
        _context(PrincipalKind.SERVICE, "grade"),
        3,
    )
    assert grade.score == RationalScore(0, 1)
