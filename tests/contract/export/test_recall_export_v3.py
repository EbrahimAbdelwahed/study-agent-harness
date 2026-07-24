from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from study_agent.application import ExportService, ExportStateError, ExportVersion
from study_agent.domain import (
    Actor,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
    SessionId,
)
from tests.contract.export.test_deterministic_export import _stack

COURSE = CourseId("course-export")
SESSION = SessionId("session-export")


class ReadOnlyEvents:
    def __init__(self, values: Sequence[DomainEvent]) -> None:
        self.values = tuple(values)

    def read(self, course_id: CourseId, after_sequence: int = 0) -> Sequence[DomainEvent]:
        assert course_id == COURSE
        return self.values[after_sequence:]

    def append(self, course_id: CourseId, expected_sequence: int, events: object) -> int:
        del course_id, expected_sequence, events
        raise AssertionError("export is read-only")


def test_v1_and_v2_fail_exactly_when_recall_is_present(tmp_path: Path) -> None:
    blobs, events, _, _ = _stack(tmp_path)
    stream = tuple(events.read(COURSE))
    recall = DomainEvent(
        EventId("recall-test-event"),
        COURSE,
        len(stream) + 1,
        "recall.review_recorded",
        1,
        Actor(PrincipalKind.HUMAN, "reviewer"),
        datetime(2026, 7, 24, tzinfo=UTC),
        CorrelationId("recall-test"),
        {},
        SESSION,
    )
    source = ReadOnlyEvents((*stream, recall))

    for version in (ExportVersion.V1, ExportVersion.V2):
        with pytest.raises(ExportStateError, match=r"^recall export requires v3$"):
            ExportService(source).assemble(COURSE, version=version)
    blobs.close()
