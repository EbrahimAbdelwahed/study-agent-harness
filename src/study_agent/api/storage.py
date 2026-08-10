"""Curated envelope-only event and storage-port facade."""

import typing as _typing

from study_agent.domain.events import Actor, EventEnvelope, PrincipalKind
from study_agent.ports.clock import Clock
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
)

__all__: tuple[str, ...] = (
    "Actor",
    "BlobStore",
    "Clock",
    "EventEnvelope",
    "EventSequenceConflictError",
    "EventStore",
    "IdFactory",
    "IdempotencyConflictError",
    "PrincipalKind",
    "Repository",
    "RunNotFoundError",
    "RunStore",
    "RunStoreConflictFailure",
)

if _typing.TYPE_CHECKING:
    __all__ += ("CourseStreamHighWater", "CourseStreamHighWaterPort")
    from study_agent.ports.storage import (
        CourseStreamHighWater,
        CourseStreamHighWaterPort,
    )


def __getattr__(name: str) -> object:
    """Resolve the PF-06 storage seam without widening the stable roster."""
    if name == "CourseStreamHighWater":
        from study_agent.ports.storage import CourseStreamHighWater

        return CourseStreamHighWater
    if name == "CourseStreamHighWaterPort":
        from study_agent.ports.storage import CourseStreamHighWaterPort

        return CourseStreamHighWaterPort
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
