"""Single-writer SQLite event log with synchronous projection updates."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from pathlib import Path

from study_agent.domain.events import DomainEvent
from study_agent.domain.identifiers import CourseId
from study_agent.ports.storage import EventSequenceConflictError
from study_agent.state import (
    EventRegistry,
    Projection,
    canonical_json_bytes,
    canonical_json_object,
    event_from_bytes,
    event_to_bytes,
    replay,
)


class SequenceConflictError(EventSequenceConflictError):
    """The stream changed after the caller read its expected sequence."""

    def __init__(self, course_id: CourseId, expected: int, actual: int) -> None:
        super().__init__(course_id, expected, actual)


class EventBatchError(ValueError):
    """An append batch does not form the requested contiguous course stream."""


class ProjectionConsistencyError(RuntimeError):
    """The derived projection is absent or behind its canonical event stream."""


class UnsupportedSQLiteDatabaseError(ValueError):
    """The adapter requires a path-backed database for connection-safe persistence."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    course_id TEXT NOT NULL,
    course_sequence INTEGER NOT NULL CHECK (course_sequence >= 1),
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
    envelope BLOB NOT NULL,
    PRIMARY KEY (course_id, course_sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS projections (
    course_id TEXT PRIMARY KEY,
    course_sequence INTEGER NOT NULL CHECK (course_sequence >= 0),
    state BLOB NOT NULL
) STRICT;

CREATE TRIGGER IF NOT EXISTS events_are_append_only_update
BEFORE UPDATE ON events BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS events_are_append_only_delete
BEFORE DELETE ON events BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;
"""


class SQLiteEventStore:
    """Reference event store; SQLite serializes writers with ``BEGIN IMMEDIATE``."""

    def __init__(
        self, database: str | Path, registry: EventRegistry, *, read_only: bool = False
    ) -> None:
        self._database = str(database)
        if self._database == ":memory:":
            raise UnsupportedSQLiteDatabaseError(
                "SQLiteEventStore requires a path-backed database; ':memory:' is unsupported"
            )
        if type(read_only) is not bool:
            raise TypeError("read_only must be a boolean")
        self._read_only = read_only
        self._registry = registry
        if not read_only:
            with closing(self._connect()) as connection:
                connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        database = self._database
        uri = False
        if self._read_only:
            database = (
                Path(database).absolute().as_uri() + "?mode=ro&immutable=1"
            )
            uri = True
        connection = sqlite3.connect(
            database, isolation_level=None, timeout=30, uri=uri
        )
        if not self._read_only:
            connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        if self._read_only:
            raise PermissionError("read-only event store cannot start a write transaction")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _current_sequence(connection: sqlite3.Connection, course_id: CourseId) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(course_sequence), 0) FROM events WHERE course_id = ?",
            (str(course_id),),
        ).fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _load_projection(
        connection: sqlite3.Connection, course_id: CourseId, stream_sequence: int
    ) -> Projection:
        row = connection.execute(
            "SELECT course_sequence, state FROM projections WHERE course_id = ?",
            (str(course_id),),
        ).fetchone()
        if row is None:
            if stream_sequence:
                raise ProjectionConsistencyError(
                    f"projection for course {course_id} is missing; rebuild it before appending"
                )
            return Projection(course_id)
        sequence = int(row[0])
        if sequence != stream_sequence:
            raise ProjectionConsistencyError(
                f"projection for course {course_id} is at {sequence}, "
                f"stream is at {stream_sequence}"
            )
        return Projection(course_id, sequence, canonical_json_object(bytes(row[1])))

    def append(
        self, course_id: CourseId, expected_sequence: int, events: Sequence[DomainEvent]
    ) -> int:
        if expected_sequence < 0:
            raise EventBatchError("expected_sequence cannot be negative")
        event_batch = tuple(events)
        for offset, event in enumerate(event_batch, start=1):
            if event.course_id != course_id:
                raise EventBatchError("every event must belong to the appended course")
            expected_event_sequence = expected_sequence + offset
            if event.course_sequence != expected_event_sequence:
                raise EventBatchError(
                    f"expected batch event sequence {expected_event_sequence}, "
                    f"got {event.course_sequence}"
                )
        with self._transaction() as connection:
            current = self._current_sequence(connection, course_id)
            if current != expected_sequence:
                raise SequenceConflictError(course_id, expected_sequence, current)
            decoded_payloads = tuple(self._registry.decode(event) for event in event_batch)
            projection = self._load_projection(connection, course_id, current)
            for event, decoded_payload in zip(event_batch, decoded_payloads, strict=True):
                connection.execute(
                    """
                    INSERT INTO events (
                        course_id, course_sequence, event_id, event_type, schema_version, envelope
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(course_id),
                        event.course_sequence,
                        str(event.event_id),
                        event.event_type,
                        event.schema_version,
                        event_to_bytes(event),
                    ),
                )
                expected = projection.sequence + 1
                if event.course_sequence != expected:
                    raise EventBatchError(
                        f"expected projection event sequence {expected}, "
                        f"got {event.course_sequence}"
                    )
                next_state = self._registry.reduce_decoded(
                    projection.state, event, decoded_payload
                )
                projection = Projection(event.course_id, event.course_sequence, next_state)

            if event_batch:
                connection.execute(
                    """
                    INSERT INTO projections (course_id, course_sequence, state)
                    VALUES (?, ?, ?)
                    ON CONFLICT(course_id) DO UPDATE SET
                        course_sequence = excluded.course_sequence,
                        state = excluded.state
                    """,
                    (str(course_id), projection.sequence, canonical_json_bytes(projection.state)),
                )
            return projection.sequence

    def read(self, course_id: CourseId, after_sequence: int = 0) -> Sequence[DomainEvent]:
        if after_sequence < 0:
            raise ValueError("after_sequence cannot be negative")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT envelope FROM events
                WHERE course_id = ? AND course_sequence > ?
                ORDER BY course_sequence
                """,
                (str(course_id), after_sequence),
            ).fetchall()
        return tuple(event_from_bytes(bytes(row[0])) for row in rows)

    def list_course_ids(self) -> tuple[CourseId, ...]:
        """List canonical stream owners without introducing mutable catalog state."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT DISTINCT course_id FROM events ORDER BY course_id"
            ).fetchall()
        return tuple(CourseId(row[0]) for row in rows)

    def projection(self, course_id: CourseId) -> Projection:
        with closing(self._connect()) as connection:
            current = self._current_sequence(connection, course_id)
            return self._load_projection(connection, course_id, current)

    def projection_bytes(self, course_id: CourseId) -> bytes:
        return self.projection(course_id).canonical_bytes()

    def rebuild_projection(self, course_id: CourseId) -> bytes:
        """Replace one discardable projection solely by replaying canonical events."""
        with self._transaction() as connection:
            connection.execute("DELETE FROM projections WHERE course_id = ?", (str(course_id),))
            rows = connection.execute(
                "SELECT envelope FROM events WHERE course_id = ? ORDER BY course_sequence",
                (str(course_id),),
            ).fetchall()
            events = tuple(event_from_bytes(bytes(row[0])) for row in rows)
            projection = replay(course_id, events, self._registry)
            if projection.sequence:
                connection.execute(
                    "INSERT INTO projections (course_id, course_sequence, state) VALUES (?, ?, ?)",
                    (
                        str(course_id),
                        projection.sequence,
                        canonical_json_bytes(projection.state),
                    ),
                )
            return projection.canonical_bytes()

    def verify_projection(self, course_id: CourseId) -> bool:
        """Compare persisted projection bytes with an independent in-memory replay."""
        persisted = self.projection_bytes(course_id)
        events = tuple(self.read(course_id))
        replayed = replay(course_id, events, self._registry).canonical_bytes()
        return persisted == replayed
