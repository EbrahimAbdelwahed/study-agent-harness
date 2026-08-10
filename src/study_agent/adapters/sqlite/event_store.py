"""Single-writer SQLite event log with synchronous projection updates."""

from __future__ import annotations

import os
import sqlite3
import stat
from collections.abc import Callable, Iterator, Sequence
from contextlib import closing, contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from study_agent.domain.authority import IdempotencyKey
from study_agent.domain.errors import (
    ConflictFailure,
    HarnessError,
    InternalFailure,
    UnauthorizedFailure,
    UnavailableDependencyFailure,
    ValidationFailure,
)
from study_agent.domain.events import DomainEvent, EventEnvelope
from study_agent.domain.identifiers import CourseId
from study_agent.kernel.module import KernelModuleRegistry, KernelSnapshot
from study_agent.ports.storage import (
    CourseStreamHighWater,
    EventSequenceConflictError,
    IdempotencyConflictError,
    _require_canonical_course_id,
)
from study_agent.state import (
    EventRegistry,
    PayloadValidationError,
    Projection,
    canonical_json_bytes,
    canonical_json_object,
    event_from_bytes,
    event_to_bytes,
    replay,
)
from study_agent.state.registry import EventInput


class SequenceConflictError(EventSequenceConflictError):
    """The stream changed after the caller read its expected sequence."""

    def __init__(self, course_id: CourseId, expected: int, actual: int) -> None:
        super().__init__(course_id, expected, actual)


class EventBatchError(ValidationFailure, ValueError):
    """An append batch does not form the requested contiguous course stream."""


class ProjectionConsistencyError(InternalFailure):
    """The derived projection is absent or behind its canonical event stream."""


class UnsupportedSQLiteDatabaseError(ValidationFailure, ValueError):
    """The adapter requires a path-backed database for connection-safe persistence."""


SQLITE_BUSY_TIMEOUT_SECONDS = 5
"""Bounded SQLite lock wait for request-path adapter operations."""

_MAX_SQLITE_SEQUENCE = 2**63 - 1


class SQLiteConnectionGuard(Protocol):
    """Technical seam that proves which regular file SQLite actually opened."""

    def connect(
        self, opener: Callable[[], sqlite3.Connection]
    ) -> sqlite3.Connection: ...


class SQLiteConnectionIdentityError(InternalFailure):
    """SQLite did not retain the database identity authorized by its host."""


class SQLiteConnectionIdentityGuard:
    """Fail closed unless SQLite retains exactly the host-authorized inode."""

    def __init__(
        self,
        expected_identity: tuple[int, int],
        verify_owner: Callable[[], None],
    ) -> None:
        self._expected_identity = expected_identity
        self._verify_owner = verify_owner

    def connect(
        self, opener: Callable[[], sqlite3.Connection]
    ) -> sqlite3.Connection:
        self._verify_owner()
        before = _live_file_descriptors()
        try:
            connection = opener()
        except sqlite3.Error:
            self._verify_owner()
            raise
        try:
            after = _live_file_descriptors()
            opened_regular = _new_regular_identities(before, after)
            if not opened_regular:
                connection.execute("PRAGMA schema_version").fetchone()
                after = _live_file_descriptors()
                opened_regular = _new_regular_identities(before, after)
            if self._expected_identity not in opened_regular:
                raise SQLiteConnectionIdentityError(
                    "SQLite connection did not retain the authorized database binding"
                )
            self._verify_owner()
            return connection
        except BaseException:
            connection.close()
            raise


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

CREATE TABLE IF NOT EXISTS event_idempotency (
    idempotency_key TEXT PRIMARY KEY,
    stream_id TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    result_sequence INTEGER NOT NULL CHECK (result_sequence >= 0)
) STRICT;
"""


def _idempotency_material(key: IdempotencyKey | str) -> tuple[str, bytes]:
    if isinstance(key, IdempotencyKey):
        return key.key, f"{key.command_kind}\0{key.input_fingerprint}".encode()
    if not isinstance(key, str) or not key or key != key.strip():
        raise ValidationFailure("idempotency key must be non-empty text")
    return key, b""


def _append_fingerprint(
    stream_id: CourseId,
    expected_sequence: int,
    events: Sequence[EventInput],
    key_material: bytes,
) -> str:
    digest = sha256()
    digest.update(key_material)
    digest.update(str(stream_id).encode())
    digest.update(b"\0")
    digest.update(str(expected_sequence).encode("ascii"))
    for event in events:
        encoded = event_to_bytes(event)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


class SQLiteEventStore:
    """Reference event store; SQLite serializes writers with ``BEGIN IMMEDIATE``."""

    def __init__(
        self,
        database: str | Path,
        registry: EventRegistry | KernelModuleRegistry | KernelSnapshot | None = None,
        *,
        read_only: bool = False,
        connection_identity_guard: SQLiteConnectionGuard | None = None,
    ) -> None:
        self._database = str(database)
        if self._database == ":memory:":
            raise UnsupportedSQLiteDatabaseError(
                "SQLiteEventStore requires a path-backed database; ':memory:' is unsupported"
            )
        if type(read_only) is not bool:
            raise TypeError("read_only must be a boolean")
        if read_only and connection_identity_guard is None:
            # Resolve once so a later replacement of the caller's final symlink
            # cannot redirect observations to a different database path.
            self._database = str(Path(self._database).resolve(strict=False))
        self._read_only = read_only
        self._connection_identity_guard = (
            _read_only_identity_guard(self._database)
            if read_only and connection_identity_guard is None
            else connection_identity_guard
        )
        if isinstance(registry, KernelModuleRegistry):
            registry.close()
            registry = registry.compile()
        self._registry = (
            registry._event_registry()
            if isinstance(registry, KernelSnapshot)
            else registry
        )
        if not read_only:
            try:
                with closing(self._connect()) as connection:
                    connection.executescript(_SCHEMA)
            except HarnessError:
                raise
            except sqlite3.Error as error:
                raise UnavailableDependencyFailure(
                    "storage dependency is unavailable", retryable=True
                ) from error

    def _connect(self) -> sqlite3.Connection:
        database = self._database
        uri = False
        if self._read_only:
            database = Path(database).absolute().as_uri() + "?mode=ro"
            uri = True
        elif self._connection_identity_guard is not None:
            database = _writable_nofollow_uri(database)
            uri = True
        def opener() -> sqlite3.Connection:
            return sqlite3.connect(
                database,
                isolation_level=None,
                timeout=SQLITE_BUSY_TIMEOUT_SECONDS,
                uri=uri,
            )
        connection = (
            opener()
            if self._connection_identity_guard is None
            else self._connection_identity_guard.connect(opener)
        )
        if not self._read_only:
            connection.execute(
                f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_SECONDS * 1000}"
            )
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
            """
            SELECT MAX(course_sequence), COUNT(*)
            FROM events WHERE course_id = ?
            """,
            (str(course_id),),
        ).fetchone()
        if type(row) is not tuple or len(row) != 2:
            raise ValidationFailure("stored event stream high-water is invalid")
        raw_sequence, raw_count = row
        if type(raw_count) is not int or raw_count < 0:
            raise ValidationFailure("stored event stream high-water is invalid")
        if raw_count == 0:
            if raw_sequence is not None:
                raise ValidationFailure("stored event stream high-water is invalid")
            return 0
        if (
            type(raw_sequence) is not int
            or raw_sequence < 1
            or raw_sequence > _MAX_SQLITE_SEQUENCE
            or raw_sequence != raw_count
        ):
            raise ValidationFailure("stored event stream high-water is invalid")
        return raw_sequence

    def _load_projection(
        self,
        connection: sqlite3.Connection,
        course_id: CourseId,
        stream_sequence: int,
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
        if self._registry is None:
            raise ValidationFailure("projection reduction requires an EventRegistry")
        raw_state = canonical_json_object(bytes(row[1]))
        state = self._registry.migrate_projection(raw_state)
        if state != raw_state and not self._read_only:
            connection.execute(
                "UPDATE projections SET state = ? WHERE course_id = ?",
                (canonical_json_bytes(state), str(course_id)),
            )
        return Projection(course_id, sequence, state)

    def append(
        self,
        course_id: CourseId,
        expected_sequence: int,
        events: Sequence[EventInput],
        idempotency_key: IdempotencyKey | str | None = None,
        *,
        _legacy: bool = False,
    ) -> int:
        course_id = _require_canonical_course_id(course_id)
        if type(expected_sequence) is not int or expected_sequence < 0:
            raise EventBatchError("expected_sequence cannot be negative")
        event_batch = tuple(events)
        for event in event_batch:
            if not isinstance(event, (DomainEvent, EventEnvelope)):
                raise EventBatchError("every item must be a DomainEvent or EventEnvelope")
            event_course_id = _require_canonical_course_id(event.course_id)
            if event_course_id != course_id:
                raise EventBatchError("every event must belong to the appended course")
        if idempotency_key is None and not _legacy:
            legacy_batch = tuple(
                event for event in event_batch if isinstance(event, DomainEvent)
            )
            if event_batch and len(legacy_batch) == len(event_batch):
                return self._append_legacy(course_id, expected_sequence, legacy_batch)
            raise EventBatchError(
                "public event append requires a non-empty idempotency key"
            )
        key_name: str | None = None
        fingerprint: str | None = None
        if idempotency_key is not None:
            key_name, key_material = _idempotency_material(idempotency_key)
            fingerprint = _append_fingerprint(
                course_id, expected_sequence, event_batch, key_material
            )
        try:
            with self._transaction() as connection:
                if key_name is not None and fingerprint is not None:
                    row = connection.execute(
                        """
                        SELECT stream_id, input_fingerprint, result_sequence
                        FROM event_idempotency WHERE idempotency_key = ?
                        """,
                        (key_name,),
                    ).fetchone()
                    if row is not None:
                        if row[1] != fingerprint:
                            raise IdempotencyConflictError(key_name)
                        return int(row[2])

                current = self._current_sequence(connection, course_id)
                if current != expected_sequence:
                    raise SequenceConflictError(course_id, expected_sequence, current)
                for offset, event in enumerate(event_batch, start=1):
                    expected_event_sequence = expected_sequence + offset
                    if event.course_sequence != expected_event_sequence:
                        raise EventBatchError(
                            f"expected batch event sequence {expected_event_sequence}, "
                            f"got {event.course_sequence}"
                        )

                next_projection: Projection | None = None
                if self._registry is not None:
                    # Prepare and decode the complete batch before touching any
                    # projection or event row. Original input bytes are retained
                    # while reducers consume the normalized current schema.
                    prepared_events: list[DomainEvent] = []
                    decoded_payloads: list[object] = []
                    for event in event_batch:
                        prepared = self._registry.prepare(event)
                        decoded_payload = self._registry.decode(prepared)
                        if prepared.course_id != course_id:
                            raise EventBatchError(
                                "every event must belong to the appended course"
                            )
                        prepared_events.append(prepared)
                        decoded_payloads.append(decoded_payload)

                    projection = self._load_projection(connection, course_id, current)
                    next_projection = projection
                    for prepared, decoded_payload in zip(
                        prepared_events, decoded_payloads, strict=True
                    ):
                        expected = next_projection.sequence + 1
                        if prepared.course_sequence != expected:
                            raise EventBatchError(
                                f"expected projection event sequence {expected}, "
                                f"got {prepared.course_sequence}"
                            )
                        next_state = self._registry.reduce_decoded(
                            next_projection.state, prepared, decoded_payload
                        )
                        next_projection = Projection(
                            course_id, prepared.course_sequence, next_state
                        )

                for event in event_batch:
                    connection.execute(
                        """
                        INSERT INTO events (
                            course_id, course_sequence, event_id, event_type,
                            schema_version, envelope
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

                result = expected_sequence + len(event_batch)
                if next_projection is not None and event_batch:
                    connection.execute(
                        """
                        INSERT INTO projections (course_id, course_sequence, state)
                        VALUES (?, ?, ?)
                        ON CONFLICT(course_id) DO UPDATE SET
                            course_sequence = excluded.course_sequence,
                            state = excluded.state
                        """,
                        (
                            str(course_id),
                            next_projection.sequence,
                            canonical_json_bytes(next_projection.state),
                        ),
                    )
                if key_name is not None and fingerprint is not None:
                    connection.execute(
                        """
                        INSERT INTO event_idempotency (
                            idempotency_key, stream_id, input_fingerprint, result_sequence
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (key_name, str(course_id), fingerprint, result),
                    )
                return result
        except (HarnessError, EventBatchError, PayloadValidationError):
            raise
        except PermissionError as error:
            raise UnauthorizedFailure(
                "read-only event store cannot append canonical events"
            ) from error
        except sqlite3.IntegrityError as error:
            raise ConflictFailure("canonical event append conflicts with existing state") from error
        except sqlite3.Error as error:
            raise UnavailableDependencyFailure(
                "storage dependency is unavailable", retryable=True
            ) from error
        # Reducers historically use ``ValueError`` as a domain-level signal
        # that callers translate at their service boundary.  Preserve that
        # signal; backend-specific sqlite failures were handled above.
        except (TypeError, ValueError):
            raise

    def _append_legacy(
        self,
        course_id: CourseId,
        expected_sequence: int,
        events: Sequence[DomainEvent],
    ) -> int:
        return self.append(
            course_id,
            expected_sequence,
            events,
            _legacy=True,
        )

    def observe_high_water(self, course_id: CourseId) -> CourseStreamHighWater:
        """Read the canonical stream high-water from the existing events table."""
        canonical_course_id = _require_canonical_course_id(course_id)
        try:
            with closing(self._connect()) as connection:
                sequence = self._current_sequence(connection, canonical_course_id)
            if (
                type(sequence) is not int
                or sequence < 0
                or sequence > _MAX_SQLITE_SEQUENCE
            ):
                raise ValidationFailure("stored event stream high-water is invalid")
            try:
                return CourseStreamHighWater(canonical_course_id, sequence)
            except ValidationFailure as error:
                raise InternalFailure("stored event stream high-water is invalid") from error
        except ValidationFailure as error:
            raise InternalFailure("stored event stream high-water is invalid") from error
        except HarnessError:
            raise
        except (OSError, sqlite3.Error) as error:
            raise UnavailableDependencyFailure(
                "storage dependency is unavailable", retryable=True
            ) from error
        except (TypeError, ValueError) as error:
            raise InternalFailure("stored event stream high-water is invalid") from error
        except Exception as error:
            raise InternalFailure("event stream high-water observation failed") from error

    def read(
        self, course_id: CourseId, after_sequence: int = 0
    ) -> Sequence[EventEnvelope]:
        """Read the curated envelope stream, including legacy rows."""
        return tuple(
            _event_to_envelope(event)
            for event in self._read_records(course_id, after_sequence)
        )

    def _read_records(
        self, course_id: CourseId, after_sequence: int = 0
    ) -> Sequence[EventInput]:
        """Read typed legacy records for reducers and projection replay."""
        course_id = _require_canonical_course_id(course_id)
        if type(after_sequence) is not int:
            raise ValidationFailure("stream and high-water position are invalid")
        if after_sequence < 0:
            raise ValidationFailure("after_sequence cannot be negative")
        try:
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
        except HarnessError:
            raise
        except sqlite3.Error as error:
            raise UnavailableDependencyFailure(
                "storage dependency is unavailable", retryable=True
            ) from error
        except (TypeError, ValueError) as error:
            raise ValidationFailure("stored event bytes are invalid") from error

    def list_course_ids(self) -> tuple[CourseId, ...]:
        """List canonical stream owners without introducing mutable catalog state."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT DISTINCT course_id FROM events ORDER BY course_id"
            ).fetchall()
        return tuple(CourseId(row[0]) for row in rows)

    def projection(self, course_id: CourseId) -> Projection:
        course_id = _require_canonical_course_id(course_id)
        if self._registry is None:
            raise ValidationFailure("projection reduction requires an EventRegistry")
        with closing(self._connect()) as connection:
            current = self._current_sequence(connection, course_id)
            return self._load_projection(connection, course_id, current)

    def projection_bytes(self, course_id: CourseId) -> bytes:
        return self.projection(_require_canonical_course_id(course_id)).canonical_bytes()

    def rebuild_projection(self, course_id: CourseId) -> bytes:
        """Replace one discardable projection solely by replaying canonical events."""
        course_id = _require_canonical_course_id(course_id)
        if self._registry is None:
            raise ValidationFailure("projection reduction requires an EventRegistry")
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
        course_id = _require_canonical_course_id(course_id)
        if self._registry is None:
            raise ValidationFailure("projection reduction requires an EventRegistry")
        persisted = self.projection_bytes(course_id)
        events = tuple(self._read_records(course_id))
        replayed = replay(course_id, events, self._registry).canonical_bytes()
        return persisted == replayed


def _event_to_envelope(event: EventInput) -> EventEnvelope:
    """Convert a stored legacy record to the curated public envelope."""

    if isinstance(event, EventEnvelope):
        return event
    return EventEnvelope(
        event_id=event.event_id,
        event_type=event.event_type,
        schema_version=event.schema_version,
        stream_id=event.course_id,
        stream_sequence=event.course_sequence,
        occurred_at=event.occurred_at,
        correlation_id=event.correlation_id,
        actor=event.actor,
        payload=event.payload,
        causation_id=event.causation_id,
    )


def _writable_nofollow_uri(database: str) -> str:
    """Open an existing database without following its final path component."""

    path = Path(database)
    base = (
        path.as_uri()
        if path.is_absolute()
        else f"file:{quote(path.as_posix(), safe='/')}"
    )
    return f"{base}?mode=rw&nofollow=1"


def _read_only_identity_guard(database: str) -> SQLiteConnectionGuard:
    """Bind a read-only adapter to one existing regular-file identity."""

    if not hasattr(os, "O_NOFOLLOW"):
        raise SQLiteConnectionIdentityError("read-only database binding is unavailable")
    path = Path(database).absolute()
    flags = os.O_RDONLY | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        try:
            metadata = os.fstat(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise SQLiteConnectionIdentityError(
            "read-only database binding is unavailable"
        ) from error
    if not stat.S_ISREG(metadata.st_mode):
        raise SQLiteConnectionIdentityError("read-only database binding is unavailable")
    identity = (metadata.st_dev, metadata.st_ino)

    def verify_owner() -> None:
        try:
            current = os.open(path, flags)
            try:
                current_metadata = os.fstat(current)
            finally:
                os.close(current)
        except OSError as error:
            raise SQLiteConnectionIdentityError("read-only database binding changed") from error
        if not stat.S_ISREG(current_metadata.st_mode) or (
            current_metadata.st_dev,
            current_metadata.st_ino,
        ) != identity:
            raise SQLiteConnectionIdentityError("read-only database binding changed")

    return SQLiteConnectionIdentityGuard(identity, verify_owner)


def _live_file_descriptors() -> dict[int, tuple[int, int] | None]:
    for root in (Path("/dev/fd"), Path("/proc/self/fd")):
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        live: dict[int, tuple[int, int] | None] = {}
        for entry in entries:
            try:
                descriptor = int(entry)
                metadata = os.fstat(descriptor)
            except (OSError, ValueError):
                continue
            live[descriptor] = (
                (metadata.st_dev, metadata.st_ino)
                if stat.S_ISREG(metadata.st_mode)
                else None
            )
        return live
    raise SQLiteConnectionIdentityError(
        "platform cannot inspect SQLite connection file descriptors"
    )


def _new_regular_identities(
    before: dict[int, tuple[int, int] | None],
    after: dict[int, tuple[int, int] | None],
) -> tuple[tuple[int, int], ...]:
    return tuple(
        identity
        for descriptor, identity in after.items()
        if descriptor not in before and identity is not None
    )
