"""Deterministic due-work view over one projection high-water mark."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import cast

from study_agent.domain import ArtifactRevisionStatus, CourseId, StudyArtifactKind
from study_agent.domain._validation import JsonObject
from study_agent.ports.clock import ClockPort
from study_agent.state import Projection

from .contracts import RecallViewRow
from .view import schedule_from_json


class DueRecallView:
    """Read due schedules without invoking a scheduler or mutating state."""

    def __init__(
        self,
        load_projection: Callable[[CourseId], Projection],
        clock: ClockPort,
    ) -> None:
        self._load_projection = load_projection
        self._clock = clock

    def due(self, course_id: CourseId, *, now: datetime | None = None) -> tuple[RecallViewRow, ...]:
        projection = self._load_projection(course_id)
        if projection.course_id != course_id:
            raise ValueError("projection loader returned another course")
        from study_agent.artifacts.view import ProjectionArtifactView

        if "study_artifacts" not in projection.state:
            raise ValueError("projection has no artifact lifecycle state")
        artifact_snapshot = ProjectionArtifactView(lambda _: projection).get(course_id)
        raw = projection.state.get("recall", {})
        if not isinstance(raw, Mapping):
            raise ValueError("recall projection is corrupt")
        schedules_raw = raw.get("schedules", {})
        if not isinstance(schedules_raw, Mapping):
            raise ValueError("recall schedules projection is corrupt")
        clock_now = _utc(now if now is not None else self._clock.now())
        latest: dict[str, tuple[int, Mapping[str, object]]] = {}
        for value in schedules_raw.values():
            if not isinstance(value, Mapping):
                raise ValueError("recall schedule projection is corrupt")
            revision_id = value.get("revision_id")
            sequence = value.get("course_sequence")
            if not isinstance(revision_id, str) or type(sequence) is not int:
                raise ValueError("recall schedule identity or sequence is corrupt")
            prior = latest.get(revision_id)
            if prior is None or sequence > prior[0]:
                latest[revision_id] = (sequence, value)

        rows: list[RecallViewRow] = []
        for revision_id, (_, raw_schedule) in latest.items():
            schedule = schedule_from_json(cast(JsonObject, raw_schedule))
            try:
                revision = artifact_snapshot.revision(schedule.revision_id)
            except LookupError:
                continue
            if (
                revision.id.value != revision_id
                or revision.status is not ArtifactRevisionStatus.ACCEPTED
                or revision.kind is not StudyArtifactKind.FLASHCARD
                or schedule.due_at > clock_now
            ):
                continue
            accepted_for_artifact = getattr(artifact_snapshot, "accepted", None)
            if callable(accepted_for_artifact):
                current_accepted = tuple(
                    item
                    for item in accepted_for_artifact(StudyArtifactKind.FLASHCARD)
                    if item.artifact_id == revision.artifact_id
                )
                if any(item.id != revision.id for item in current_accepted):
                    continue
            rows.append(
                RecallViewRow(
                    str(revision.artifact_id),
                    revision.id,
                    schedule.due_at,
                    schedule,
                )
            )
        return tuple(
            sorted(rows, key=lambda row: (row.due_at, row.artifact_id, str(row.revision_id)))
        )

    def get(self, course_id: CourseId, *, now: datetime | None = None) -> tuple[RecallViewRow, ...]:
        return self.due(course_id, now=now)

    def due_rows(
        self, course_id: CourseId, *, now: datetime | None = None
    ) -> tuple[RecallViewRow, ...]:
        return self.due(course_id, now=now)

    def get_due(
        self, course_id: CourseId, *, now: datetime | None = None
    ) -> tuple[RecallViewRow, ...]:
        return self.due(course_id, now=now)


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("due view clock must return an aware datetime")
    return value.astimezone(UTC)


__all__ = ["DueRecallView"]
