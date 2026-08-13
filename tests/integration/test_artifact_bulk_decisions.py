from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from study_agent.adapters.sqlite.event_store import SQLiteEventStore
from study_agent.domain import (
    Actor,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
)

COURSE = CourseId("artifact-bulk-sqlite")
NOW = datetime(2026, 8, 12, 16, tzinfo=UTC)


def _event(sequence: int, name: str) -> DomainEvent:
    return DomainEvent(
        EventId(f"artifact-bulk-sqlite-{name}"),
        COURSE,
        sequence,
        "study_artifact.decision_recorded",
        1,
        Actor(PrincipalKind.HUMAN, "bulk-host"),
        NOW,
        CorrelationId("bulk-sqlite-test"),
        {"name": name},
    )


def test_sqlite_event_store_persists_one_decision_batch_and_replays_after_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(path)
    store.append(COURSE, 0, (_event(1, "seed"),))
    assert store.append(COURSE, 1, (_event(2, "accept"), _event(3, "reject"))) == 3

    reopened = SQLiteEventStore(path)
    assert tuple(item.stream_sequence for item in reopened.read(COURSE)) == (1, 2, 3)


def test_sqlite_event_store_rejects_invalid_last_batch_without_partial_append(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    store.append(COURSE, 0, (_event(1, "seed"),))
    with pytest.raises(ValueError, match="expected batch event sequence"):
        store.append(COURSE, 1, (_event(2, "valid"), _event(4, "invalid-last")))
    assert tuple(item.stream_sequence for item in store.read(COURSE)) == (1,)
