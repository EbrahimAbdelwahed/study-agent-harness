from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import cast

from ._validation import JsonObject, freeze_object, require_aware, require_text
from .errors import ValidationFailure
from .identifiers import CorrelationId, CourseId, EventId, Identifier, SessionId


class PrincipalKind(StrEnum):
    HUMAN = "human"
    SERVICE = "service"
    MODEL = "model"


@dataclass(frozen=True, slots=True)
class Actor:
    kind: PrincipalKind
    principal_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PrincipalKind):
            raise ValueError("kind must be a trusted PrincipalKind")
        require_text(self.principal_id, "principal_id")


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: EventId
    course_id: CourseId
    course_sequence: int
    event_type: str
    schema_version: int
    actor: Actor
    occurred_at: datetime
    correlation_id: CorrelationId
    payload: JsonObject = field(default_factory=dict)
    session_id: SessionId | None = None
    causation_id: EventId | None = None

    def __post_init__(self) -> None:
        if self.course_sequence < 1:
            raise ValueError("course_sequence must be positive")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        require_text(self.event_type, "event_type")
        require_aware(self.occurred_at, "occurred_at")
        if self.causation_id == self.event_id:
            raise ValueError("an event cannot cause itself")
        object.__setattr__(self, "payload", freeze_object(self.payload))


_NAMESPACED_EVENT_TYPE = re.compile(r"^[a-z][a-z0-9]*(?:[._:/-][a-z0-9]+)+$")


def _text_id(value: object, field_name: str) -> str:
    """Read an opaque identifier without invoking provider-specific objects."""
    candidate = value.value if isinstance(value, Identifier) else value
    if not isinstance(candidate, str):
        raise ValidationFailure(f"{field_name} must be text")
    try:
        require_text(candidate, field_name)
    except ValueError as error:
        raise ValidationFailure(str(error)) from error
    return candidate


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def _reject_unsafe_json(value: object) -> None:
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise ValidationFailure("binary values are not JSON")
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValidationFailure("JSON object keys must be strings")
        for item in value.values():
            _reject_unsafe_json(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_unsafe_json(item)


def _timestamp(value: datetime) -> str:
    normalized = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return normalized


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Immutable, canonical event boundary shared by hosts and the kernel.

    The envelope deliberately contains only trusted primitive identifiers and a
    deeply frozen JSON payload.  Product modules may attach meaning to the
    event type, but cannot smuggle executable/provider objects across this
    boundary.
    """

    event_id: EventId | str
    event_type: str
    schema_version: int
    stream_id: CourseId | str
    stream_sequence: int
    occurred_at: datetime
    correlation_id: CorrelationId | str
    actor: Actor
    payload: JsonObject = field(default_factory=dict)
    causation_id: EventId | str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.event_type, str)
            or _NAMESPACED_EVENT_TYPE.fullmatch(self.event_type) is None
        ):
            raise ValidationFailure("event_type must be a lowercase namespaced name")
        if type(self.schema_version) is not int or self.schema_version < 1:
            raise ValidationFailure("schema_version must be positive")
        if type(self.stream_sequence) is not int or self.stream_sequence < 1:
            raise ValidationFailure("stream_sequence must be positive")
        if not isinstance(self.actor, Actor):
            raise ValidationFailure("actor must be a trusted Actor")
        require_aware(self.occurred_at, "occurred_at")
        _text_id(self.event_id, "event_id")
        _text_id(self.stream_id, "stream_id")
        _text_id(self.correlation_id, "correlation_id")
        if self.causation_id is not None:
            _text_id(self.causation_id, "causation_id")
            if _text_id(self.causation_id, "causation_id") == _text_id(self.event_id, "event_id"):
                raise ValidationFailure("an event cannot cause itself")
        if not isinstance(self.payload, Mapping):
            raise ValidationFailure("payload must be a JSON object")
        _reject_unsafe_json(self.payload)
        try:
            frozen_payload = freeze_object(self.payload)
        except (TypeError, ValueError) as error:
            raise ValidationFailure("payload is not valid JSON") from error
        object.__setattr__(self, "payload", frozen_payload)

    @property
    def course_id(self) -> CourseId | str:
        """Compatibility alias for the historical course event stream."""
        return self.stream_id

    @property
    def course_sequence(self) -> int:
        return self.stream_sequence

    def to_json(self) -> dict[str, object]:
        actor = {"kind": self.actor.kind.value, "principal_id": self.actor.principal_id}
        return {
            "actor": actor,
            "causation_id": (
                None
                if self.causation_id is None
                else _text_id(self.causation_id, "causation_id")
            ),
            "correlation_id": _text_id(self.correlation_id, "correlation_id"),
            "event_id": _text_id(self.event_id, "event_id"),
            "event_type": self.event_type,
            "occurred_at": _timestamp(self.occurred_at),
            "payload": _json_value(self.payload),
            "schema_version": self.schema_version,
            "stream_id": _text_id(self.stream_id, "stream_id"),
            "stream_sequence": self.stream_sequence,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_json(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @classmethod
    def from_json(cls, value: Mapping[str, object]) -> EventEnvelope:
        expected = {
            "actor",
            "causation_id",
            "correlation_id",
            "event_id",
            "event_type",
            "occurred_at",
            "payload",
            "schema_version",
            "stream_id",
            "stream_sequence",
        }
        if set(value) != expected:
            raise ValidationFailure("event envelope fields are not canonical")
        actor_value = value["actor"]
        if not isinstance(actor_value, Mapping) or set(actor_value) != {"kind", "principal_id"}:
            raise ValidationFailure("actor must contain kind and principal_id")
        try:
            actor = Actor(PrincipalKind(actor_value["kind"]), actor_value["principal_id"])
            occurred_at = datetime.fromisoformat(str(value["occurred_at"]).replace("Z", "+00:00"))
            payload = value["payload"]
            if not isinstance(payload, Mapping):
                raise ValidationFailure("payload must be a JSON object")
            return cls(
                event_id=cast(EventId | str, value["event_id"]),
                event_type=cast(str, value["event_type"]),
                schema_version=cast(int, value["schema_version"]),
                stream_id=cast(CourseId | str, value["stream_id"]),
                stream_sequence=cast(int, value["stream_sequence"]),
                occurred_at=occurred_at,
                correlation_id=cast(CorrelationId | str, value["correlation_id"]),
                actor=actor,
                payload=cast(JsonObject, payload),
                causation_id=cast(EventId | str | None, value["causation_id"]),
            )
        except (TypeError, ValueError, KeyError) as error:
            raise ValidationFailure("invalid event envelope") from error

    @classmethod
    def from_bytes(cls, value: bytes) -> EventEnvelope:
        if not isinstance(value, bytes):
            raise ValidationFailure("event envelope bytes are required")
        try:
            decoded = json.loads(value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValidationFailure("invalid event envelope bytes") from error
        if not isinstance(decoded, Mapping):
            raise ValidationFailure("event envelope must be a JSON object")
        envelope = cls.from_json(decoded)
        if envelope.canonical_bytes() != value:
            raise ValidationFailure("event envelope bytes are not canonical")
        return envelope
