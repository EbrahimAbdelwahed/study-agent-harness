from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from study_agent.domain import (
    ArtifactDecision,
    ArtifactRevisionId,
    CourseId,
    ScheduleDecisionId,
)
from study_agent.recall import (
    DueRecallView,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    effective_policy_fingerprint,
    result_fingerprint,
)
from study_agent.recall.contracts import AppliedSchedule
from study_agent.state import apply_event
from tests.unit.artifacts.test_lifecycle_events import decision_event
from tests.unit.artifacts.test_lifecycle_projection import proposed_pair, registry

COURSE = CourseId("course-1")
NOW = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
POLICY = SchedulingPolicyConfigV1()


@dataclass
class FakeClock:
    current: datetime = NOW

    def now(self) -> datetime:
        return self.current


def _schedule(revision_id: ArtifactRevisionId, due_at: datetime, key: str) -> AppliedSchedule:
    request = SchedulingRequest(revision_id, NOW - timedelta(days=1), (), POLICY)
    partial = SchedulingResult(
        due_at,
        "fake",
        "1",
        effective_policy_fingerprint(POLICY, "fake", "1", "fake", "1"),
        "fake",
        "1",
        request.history_fingerprint,
        "0" * 64,
    )
    result = replace(partial, result_fingerprint=result_fingerprint(request, partial))
    return AppliedSchedule(
        ScheduleDecisionId(key),
        revision_id,
        "enrollment",
        None,
        request.enrollment_at,
        due_at,
        POLICY,
        result.policy_id,
        result.policy_version,
        result.policy_fingerprint,
        result.implementation_id,
        result.implementation_version,
        result.history_fingerprint,
        result.result_fingerprint,
        key,
        "a" * 64,
    )


def test_due_view_filters_current_accepted_revisions_and_sorts_without_scheduler() -> None:
    artifact_projection, first_record, second_record = proposed_pair()
    artifact_projection = apply_event(
        artifact_projection,
        replace(
            decision_event(first_record.revision_id, ArtifactDecision.ACCEPT, key="first"),
            course_sequence=3,
        ),
        registry(),
    )
    artifact_projection = apply_event(
        artifact_projection,
        replace(
            decision_event(second_record.revision_id, ArtifactDecision.ACCEPT, key="second"),
            course_sequence=4,
        ),
        registry(),
    )
    first = first_record.revision_id
    second = second_record.revision_id
    first_schedule = _schedule(first, NOW, "decision-a")
    second_schedule = _schedule(second, NOW, "decision-b")
    course = artifact_projection.course_id
    state = replace(
        artifact_projection,
        sequence=12,
        state={
            **artifact_projection.state,
            "recall": {
                "enrollments": {},
                "reviews": {},
                "schedules": {
                    "decision-a": {
                        **first_schedule.to_json(),
                        "course_sequence": 3,
                        "session_id": "session-artifacts",
                    },
                    "decision-b": {
                        **second_schedule.to_json(),
                        "course_sequence": 2,
                        "session_id": "session-artifacts",
                    },
                },
                "commands": {},
            },
        },
    )
    clock = FakeClock()
    view = DueRecallView(lambda _: state, clock)
    rows = view.due_rows(course)
    assert {row.revision_id for row in rows} == {first, second}
    assert rows == tuple(
        sorted(rows, key=lambda row: (row.due_at, row.artifact_id, str(row.revision_id)))
    )
    clock.current = NOW - timedelta(seconds=1)
    assert view.get(course) == ()


def test_due_view_uses_one_projection_and_never_mutates_it() -> None:
    revision = ArtifactRevisionId("revision-a")
    schedule = _schedule(revision, NOW, "decision-a")
    artifact_projection, record, _ = proposed_pair()
    course = artifact_projection.course_id
    state = replace(
        artifact_projection,
        sequence=7,
        state={
            **artifact_projection.state,
            "recall": {
                "enrollments": {},
                "reviews": {},
                "schedules": {
                    "decision-a": {
                        **replace(schedule, revision_id=record.revision_id).to_json(),
                        "course_sequence": 1,
                        "session_id": "session-artifacts",
                    }
                },
                "commands": {},
            },
        },
    )
    before = state.canonical_bytes()
    assert DueRecallView(lambda _: state, FakeClock()).due(course) == ()
    assert state.canonical_bytes() == before
