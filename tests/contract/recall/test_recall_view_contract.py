from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from study_agent.domain import ArtifactRevisionId, CourseId, ReviewId, ScheduleDecisionId
from study_agent.domain._validation import JsonValue
from study_agent.ports.recall import RecallViewPort
from study_agent.recall.contracts import (
    AppliedSchedule,
    RecallRating,
    RecallSnapshot,
    RecallViewRow,
    RetentionObservation,
    ReviewRecord,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    effective_policy_fingerprint,
    result_fingerprint,
)
from study_agent.recall.view import CompositeRecallView, ProjectionRecallView
from study_agent.state import Projection


def test_projection_recall_view_is_read_only_and_high_water_marked() -> None:
    course = CourseId("course-1")
    projection = Projection(
        course, 12, {"recall": {"enrollments": {}, "reviews": {}, "schedules": {}, "commands": {}}}
    )
    view = ProjectionRecallView(
        lambda requested: projection if requested == course else Projection(requested)
    )
    snapshot = view.get(course)
    assert isinstance(snapshot, RecallSnapshot)
    assert snapshot.course_id == course
    assert snapshot.sequence == 12
    assert snapshot.reviews == ()
    assert snapshot.schedules == ()
    assert projection.state == {
        "recall": {"enrollments": {}, "reviews": {}, "schedules": {}, "commands": {}}
    }


def test_projection_recall_view_rejects_missing_or_opaque_sections() -> None:
    course = CourseId("course-1")
    recalls: tuple[dict[str, JsonValue], ...] = (
        {"enrollments": {}, "reviews": {}, "schedules": {}},
        {
            "enrollments": {},
            "reviews": {},
            "schedules": {},
            "commands": {},
            "opaque_package_state": {},
        },
    )
    for recall in recalls:
        with pytest.raises(ValueError, match="projection fields"):
            projection = Projection(course, 1, {"recall": recall})

            def load(_: CourseId, projection: Projection = projection) -> Projection:
                return projection

            ProjectionRecallView(load).get(course)


def test_host_composite_recall_view_owns_snapshot_and_due_rows() -> None:
    class _Projection:
        def get(self, course_id: CourseId) -> RecallSnapshot:
            return RecallSnapshot(course_id, 0)

    class _Due:
        def due(
            self, course_id: CourseId, *, now: datetime | None = None
        ) -> tuple[RecallViewRow, ...]:
            return ()

    view: RecallViewPort = CompositeRecallView(_Projection(), _Due())
    course = CourseId("course-1")
    assert view.get(course).course_id == course
    assert view.due(course) == ()


def test_retention_observation_derives_only_from_matching_review_and_schedule() -> None:
    revision = ArtifactRevisionId("revision-1")
    review_id = ReviewId("review-1")
    now = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
    policy = SchedulingPolicyConfigV1()
    request = SchedulingRequest(revision, now - timedelta(days=1), (), policy)
    effective = effective_policy_fingerprint(policy, "deterministic", "1", "builtin", "1")
    partial = SchedulingResult(
        now + timedelta(days=1),
        "deterministic",
        "1",
        effective,
        "builtin",
        "1",
        request.history_fingerprint,
        "0" * 64,
    )
    schedule = AppliedSchedule(
        ScheduleDecisionId("decision-1"),
        revision,
        "review",
        review_id,
        request.enrollment_at,
        partial.due_at,
        policy,
        partial.policy_id,
        partial.policy_version,
        partial.policy_fingerprint,
        partial.implementation_id,
        partial.implementation_version,
        partial.history_fingerprint,
        result_fingerprint(request, partial),
        "retry-1",
        "a" * 64,
    )
    review = ReviewRecord(
        review_id, revision, RecallRating.GOOD, 1200, 8500, now, "retry-2", "b" * 64
    )
    observation = RetentionObservation.from_review(review, schedule)
    assert observation.revision_id == revision
    assert observation.review_id == review_id
    assert observation.due_at == schedule.due_at
    with pytest.raises(ValueError, match="does not match"):
        RetentionObservation.from_review(review, replace(schedule, review_id=ReviewId("other")))
