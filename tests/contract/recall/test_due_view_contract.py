from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from study_agent.domain import (
    ArtifactId,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    CourseId,
    ScheduleDecisionId,
    StudyArtifactKind,
)
from study_agent.recall import (
    DueRecallView,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    result_fingerprint,
)
from study_agent.recall.contracts import AppliedSchedule
from study_agent.state import Projection

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
        POLICY.fingerprint,
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
    first = ArtifactRevisionId("revision-a")
    second = ArtifactRevisionId("revision-b")
    first_schedule = _schedule(first, NOW, "decision-a")
    second_schedule = _schedule(second, NOW, "decision-b")
    state = Projection(
        COURSE,
        12,
        {
            "recall": {
                "enrollments": {},
                "reviews": {},
                "schedules": {
                    "decision-a": {**first_schedule.to_json(), "course_sequence": 3},
                    "decision-b": {**second_schedule.to_json(), "course_sequence": 2},
                },
                "commands": {},
            }
        },
    )
    revisions = {
        first: SimpleNamespace(
            id=first,
            artifact_id=ArtifactId("artifact-z"),
            status=ArtifactRevisionStatus.ACCEPTED,
            kind=StudyArtifactKind.FLASHCARD,
        ),
        second: SimpleNamespace(
            id=second,
            artifact_id=ArtifactId("artifact-a"),
            status=ArtifactRevisionStatus.ACCEPTED,
            kind=StudyArtifactKind.FLASHCARD,
        ),
    }
    artifacts = SimpleNamespace(
        get=lambda _: SimpleNamespace(revision=lambda revision: revisions[revision])
    )
    clock = FakeClock()
    view = DueRecallView(lambda _: state, clock, artifact_view=artifacts)
    rows = view.due_rows(COURSE)
    assert [(row.artifact_id, row.revision_id) for row in rows] == [
        ("artifact-a", second),
        ("artifact-z", first),
    ]
    clock.current = NOW - timedelta(seconds=1)
    assert view.get(COURSE) == ()


def test_due_view_uses_one_projection_and_never_mutates_it() -> None:
    revision = ArtifactRevisionId("revision-a")
    schedule = _schedule(revision, NOW, "decision-a")
    state = Projection(
        COURSE,
        7,
        {
            "recall": {
                "enrollments": {},
                "reviews": {},
                "schedules": {"decision-a": {**schedule.to_json(), "course_sequence": 1}},
                "commands": {},
            }
        },
    )
    artifacts = SimpleNamespace(
        get=lambda _: SimpleNamespace(
            revision=lambda requested: SimpleNamespace(
                id=requested,
                artifact_id=ArtifactId("artifact-a"),
                status=ArtifactRevisionStatus.PROPOSED,
                kind=StudyArtifactKind.FLASHCARD,
            )
        )
    )
    before = state.canonical_bytes()
    assert DueRecallView(lambda _: state, FakeClock(), artifact_view=artifacts).due(COURSE) == ()
    assert state.canonical_bytes() == before
