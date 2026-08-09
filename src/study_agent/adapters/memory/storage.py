"""Provider-neutral in-memory storage adapters used by the offline kit."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import TypeVar, cast

from study_agent.adapters.filesystem.blob_store import BlobIntegrityError, BlobNotFoundError
from study_agent.domain.authority import IdempotencyKey
from study_agent.domain.errors import ConflictFailure, InternalFailure, ValidationFailure
from study_agent.domain.events import DomainEvent, EventEnvelope
from study_agent.domain.identifiers import CourseId, Identifier, RunId
from study_agent.domain.source import BlobRef
from study_agent.ports.clock import require_utc
from study_agent.ports.id_factory import IdFactory
from study_agent.ports.storage import (
    BlobStore,
    EventSequenceConflictError,
    EventStore,
    IdempotencyConflictError,
    Repository,
    RunNotFoundError,
    RunStore,
    RunStoreConflictFailure,
    SourceContentPort,
)
from study_agent.state import EventRegistry, Projection, event_to_bytes

_EventInput = DomainEvent | EventEnvelope
_IdentifierT = TypeVar("_IdentifierT", bound=Identifier)


def _event_as_envelope(event: _EventInput) -> EventEnvelope:
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


def _idempotency_material(key: IdempotencyKey | str) -> tuple[str, bytes]:
    if isinstance(key, IdempotencyKey):
        return key.key, f"{key.command_kind}\0{key.input_fingerprint}".encode()
    if not isinstance(key, str) or not key or key != key.strip():
        raise ValidationFailure("idempotency key must be non-empty text")
    return key, b""


def _append_fingerprint(
    stream_id: CourseId,
    expected_sequence: int,
    events: Sequence[_EventInput],
    key_material: bytes,
) -> str:
    digest = hashlib.sha256()
    digest.update(key_material)
    digest.update(str(stream_id).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(expected_sequence).encode("ascii"))
    for event in events:
        encoded = event_to_bytes(event)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


class MemoryEventStore:
    """Thread-safe append-only event store with optional projection reduction."""

    def __init__(self, registry: EventRegistry | None = None) -> None:
        self._registry = registry
        self._events: dict[CourseId, list[_EventInput]] = {}
        self._idempotency: dict[str, tuple[str, int]] = {}
        self._projections: dict[CourseId, Projection] = {}
        self._lock = RLock()

    def append(
        self,
        stream_id: CourseId,
        expected_sequence: int,
        events: Sequence[_EventInput],
        idempotency_key: IdempotencyKey | str | None = None,
    ) -> int:
        if not isinstance(stream_id, CourseId):
            raise ValidationFailure("stream_id must be CourseId")
        if type(expected_sequence) is not int or expected_sequence < 0:
            raise ValidationFailure("expected_sequence must be a non-negative integer")
        batch = tuple(events)
        if any(not isinstance(event, (DomainEvent, EventEnvelope)) for event in batch):
            raise ValidationFailure("every event must be a trusted event value")
        key_name: str | None = None
        fingerprint: str | None = None
        if idempotency_key is not None:
            key_name, key_material = _idempotency_material(idempotency_key)
            fingerprint = _append_fingerprint(stream_id, expected_sequence, batch, key_material)

        with self._lock:
            if key_name is not None and fingerprint is not None:
                existing = self._idempotency.get(key_name)
                if existing is not None:
                    if existing[0] != fingerprint:
                        raise IdempotencyConflictError(key_name)
                    return existing[1]

            current = len(self._events.get(stream_id, ()))
            if current != expected_sequence:
                raise EventSequenceConflictError(stream_id, expected_sequence, current)
            for offset, event in enumerate(batch, start=1):
                if (
                    event.course_id != stream_id
                    or event.course_sequence != expected_sequence + offset
                ):
                    raise ValidationFailure("event stream sequence is not contiguous")
            existing_ids = {str(event.event_id) for event in self._events.get(stream_id, ())}
            incoming_ids = [str(event.event_id) for event in batch]
            if len(incoming_ids) != len(set(incoming_ids)) or existing_ids.intersection(
                incoming_ids
            ):
                raise ConflictFailure("canonical event identity already exists")

            prepared: list[_EventInput] = []
            projection = self._projections.get(stream_id, Projection(stream_id))
            if self._registry is not None:
                try:
                    for event in batch:
                        normalized = self._registry.prepare(event)
                        decoded = self._registry.decode(normalized)
                        next_state = self._registry.reduce_decoded(
                            projection.state, normalized, decoded
                        )
                        projection = Projection(stream_id, normalized.course_sequence, next_state)
                        prepared.append(event)
                except Exception as error:
                    if isinstance(error, (ValidationFailure, InternalFailure)):
                        raise
                    raise ValidationFailure("event batch failed validation") from error
            else:
                prepared.extend(batch)

            self._events.setdefault(stream_id, []).extend(prepared)
            if self._registry is not None:
                self._projections[stream_id] = projection
            result = expected_sequence + len(batch)
            if key_name is not None and fingerprint is not None:
                self._idempotency[key_name] = (fingerprint, result)
            return result

    def read(self, stream_id: CourseId, after_sequence: int = 0) -> tuple[EventEnvelope, ...]:
        if (
            not isinstance(stream_id, CourseId)
            or type(after_sequence) is not int
            or after_sequence < 0
        ):
            raise ValidationFailure("stream and high-water position are invalid")
        with self._lock:
            return tuple(
                _event_as_envelope(event)
                for event in self._events.get(stream_id, ())
                if event.course_sequence > after_sequence
            )

    def _read_records(
        self, stream_id: CourseId, after_sequence: int = 0
    ) -> tuple[_EventInput, ...]:
        if (
            not isinstance(stream_id, CourseId)
            or type(after_sequence) is not int
            or after_sequence < 0
        ):
            raise ValidationFailure("stream and high-water position are invalid")
        with self._lock:
            return tuple(
                event
                for event in self._events.get(stream_id, ())
                if event.course_sequence > after_sequence
            )

    def projection(self, stream_id: CourseId) -> Projection:
        with self._lock:
            if self._registry is None:
                raise ValidationFailure("projection reduction requires an EventRegistry")
            return self._projections.get(stream_id, Projection(stream_id))

    def projection_bytes(self, stream_id: CourseId) -> bytes:
        return self.projection(stream_id).canonical_bytes()


class MemoryBlobStore:
    """Immutable in-memory SHA-256 content-addressed storage."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self._lock = RLock()

    @staticmethod
    def _reference(content: bytes) -> BlobRef:
        digest = hashlib.sha256(content).hexdigest()
        from study_agent.domain.identifiers import BlobId

        return BlobRef(BlobId(f"sha256:{digest}"), digest, len(content))

    @staticmethod
    def _validate_reference(ref: BlobRef, content: bytes | None = None) -> None:
        if not isinstance(ref, BlobRef) or str(ref.id) != f"sha256:{ref.checksum_sha256}":
            raise ValidationFailure("blob reference is not a canonical SHA-256 identity")
        if content is not None and (
            len(content) != ref.byte_length
            or hashlib.sha256(content).hexdigest() != ref.checksum_sha256
        ):
            raise BlobIntegrityError("immutable blob failed integrity verification")

    def put(self, content: bytes, ref: BlobRef | None = None) -> BlobRef:
        if type(content) is not bytes:
            raise ValidationFailure("blob content must be bytes")
        actual = self._reference(content)
        if ref is not None:
            self._validate_reference(ref)
            if ref != actual:
                raise ValidationFailure("blob reference does not match content")
        with self._lock:
            existing = self._objects.get(actual.checksum_sha256)
            if existing is not None and existing != content:
                raise InternalFailure("immutable blob identity contains different bytes")
            self._objects[actual.checksum_sha256] = content
        return actual

    def get(self, ref: BlobRef) -> bytes:
        self._validate_reference(ref)
        with self._lock:
            content = self._objects.get(ref.checksum_sha256)
        if content is None:
            raise BlobNotFoundError("blob was not found")
        self._validate_reference(ref, content)
        return content


class MemoryRunStore:
    """Operational byte checkpoints with compare-and-set semantics."""

    def __init__(self) -> None:
        self._payloads: dict[RunId, bytes] = {}
        self._lock = RLock()

    def create(self, run_id: RunId, payload: bytes) -> bool:
        if not isinstance(run_id, RunId) or type(payload) is not bytes:
            raise ValidationFailure("run identity and payload are invalid")
        with self._lock:
            if run_id in self._payloads:
                return False
            self._payloads[run_id] = payload
            return True

    def compare_and_set(
        self, run_id: RunId, expected: bytes, replacement: bytes
    ) -> bool:
        if (
            not isinstance(run_id, RunId)
            or type(expected) is not bytes
            or type(replacement) is not bytes
        ):
            raise ValidationFailure("run identity and payloads are invalid")
        with self._lock:
            if self._payloads.get(run_id) != expected:
                return cast(
                    bool,
                    RunStoreConflictFailure("operational run changed before compare-and-set"),
                )
            self._payloads[run_id] = replacement
            return True

    def load(self, run_id: RunId) -> bytes:
        if not isinstance(run_id, RunId):
            raise ValidationFailure("run_id must be RunId")
        with self._lock:
            try:
                return self._payloads[run_id]
            except KeyError:
                raise RunNotFoundError(run_id) from None


class FixedClock:
    """Deterministic aware-UTC clock for contract fixtures."""

    def __init__(self, value: datetime) -> None:
        self._value = require_utc(value)
        self._lock = RLock()

    def now(self) -> datetime:
        with self._lock:
            return self._value

    def set(self, value: datetime) -> None:
        with self._lock:
            self._value = require_utc(value)


class DeterministicIdFactory(IdFactory):
    """Simple monotonic typed-ID factory with no hidden global state."""

    def __init__(self, prefix: str = "id") -> None:
        if not isinstance(prefix, str) or not prefix or prefix != prefix.strip():
            raise ValueError("identifier prefix must be non-empty text")
        self._prefix = prefix
        self._counter = 0
        self._lock = RLock()

    def new(self, identifier_type: type[_IdentifierT]) -> _IdentifierT:
        if not isinstance(identifier_type, type) or not issubclass(identifier_type, Identifier):
            raise TypeError("identifier_type must be an Identifier subclass")
        with self._lock:
            self._counter += 1
            return identifier_type(f"{self._prefix}-{self._counter}")


@dataclass(frozen=True, slots=True)
class MemoryRepository(Repository):
    """Explicit host composition bundle for the memory reference adapters."""

    event_store: EventStore
    blob_store: BlobStore
    run_store: RunStore
    source_content: SourceContentPort | None = None


InMemoryEventStore = MemoryEventStore
InMemoryBlobStore = MemoryBlobStore
InMemoryRunStore = MemoryRunStore


__all__ = [
    "DeterministicIdFactory",
    "FixedClock",
    "InMemoryBlobStore",
    "InMemoryEventStore",
    "InMemoryRunStore",
    "MemoryBlobStore",
    "MemoryEventStore",
    "MemoryRepository",
    "MemoryRunStore",
]
