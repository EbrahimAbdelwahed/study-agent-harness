"""Curated envelope-only event and storage-port facade."""

from collections.abc import Sequence as _Sequence
from typing import TYPE_CHECKING as _TYPE_CHECKING
from typing import Protocol as _Protocol

from study_agent.domain.authority import IdempotencyKey as _IdempotencyKey
from study_agent.domain.events import Actor, EventEnvelope, PrincipalKind
from study_agent.domain.identifiers import CourseId as _CourseId
from study_agent.ports.clock import Clock as _Clock
from study_agent.ports.id_factory import IdFactory as _IdFactory
from study_agent.ports.storage import (
    BlobStore as _BlobStore,
)
from study_agent.ports.storage import (
    EventSequenceConflictError,
)
from study_agent.ports.storage import (
    IdempotencyConflictError as _IdempotencyConflictError,
)
from study_agent.ports.storage import (
    Repository as _Repository,
)
from study_agent.ports.storage import (
    RunNotFoundError as _RunNotFoundError,
)
from study_agent.ports.storage import (
    RunStore as _RunStore,
)
from study_agent.ports.storage import (
    RunStoreConflictFailure as _RunStoreConflictFailure,
)

if _TYPE_CHECKING:
    BlobStore = _BlobStore
    Clock = _Clock
    IdFactory = _IdFactory
    Repository = _Repository
    RunNotFoundError = _RunNotFoundError
    RunStore = _RunStore
    RunStoreConflictFailure = _RunStoreConflictFailure


class EventStore(_Protocol):
    """Public canonical event store; legacy DomainEvent is not in this API."""

    def append(
        self,
        stream_id: _CourseId,
        expected_sequence: int,
        events: _Sequence[EventEnvelope],
        idempotency_key: _IdempotencyKey | str | None = None,
    ) -> int: ...

    def read(
        self, stream_id: _CourseId, after_sequence: int = 0
    ) -> _Sequence[EventEnvelope]: ...

__all__ = (
    "Actor",
    "EventEnvelope",
    "EventSequenceConflictError",
    "EventStore",
    "PrincipalKind",
)

_ADDITIONAL_PUBLIC = {
    "BlobStore": _BlobStore,
    "Clock": _Clock,
    "IdFactory": _IdFactory,
    "IdempotencyConflictError": _IdempotencyConflictError,
    "Repository": _Repository,
    "RunNotFoundError": _RunNotFoundError,
    "RunStore": _RunStore,
    "RunStoreConflictFailure": _RunStoreConflictFailure,
}


def __getattr__(name: str) -> object:
    """Resolve the PF-04 additions without eager adapter imports.

    ``__all__`` retains the PF-03 facade manifest until the next manifest
    revision; direct typed imports of the new ports are nevertheless stable.
    """

    try:
        return _ADDITIONAL_PUBLIC[name]
    except KeyError:
        raise AttributeError(name) from None


def __dir__() -> list[str]:
    return sorted(name for name in globals() if not name.startswith("_"))
