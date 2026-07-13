"""Event registration, reduction, projection, canonical serialization, and replay."""

from .projection import Projection, ProjectionSequenceError, apply_event, replay
from .registry import (
    EventRegistry,
    PayloadDecoder,
    PayloadValidationError,
    ReducerRegistrationError,
    TypedEventReducer,
    UnknownEventSchemaError,
)
from .serialization import (
    canonical_json_bytes,
    canonical_json_object,
    event_from_bytes,
    event_to_bytes,
)

__all__ = [
    "EventRegistry",
    "PayloadDecoder",
    "PayloadValidationError",
    "Projection",
    "ProjectionSequenceError",
    "ReducerRegistrationError",
    "TypedEventReducer",
    "UnknownEventSchemaError",
    "apply_event",
    "canonical_json_bytes",
    "canonical_json_object",
    "event_from_bytes",
    "event_to_bytes",
    "replay",
]
