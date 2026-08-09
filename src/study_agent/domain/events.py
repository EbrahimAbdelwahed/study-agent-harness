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
        if type(self.course_sequence) is not int or self.course_sequence < 1:
            raise ValueError("course_sequence must be positive")
        if type(self.schema_version) is not int or self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        validate_event_type(self.event_type)
        require_aware(self.occurred_at, "occurred_at")
        if self.causation_id == self.event_id:
            raise ValueError("an event cannot cause itself")
        object.__setattr__(self, "payload", freeze_object(self.payload))


_NAMESPACED_EVENT_TYPE = re.compile(r"^[a-z][a-z0-9]*(?:[._:/-][a-z0-9]+)+$")


def validate_event_type(value: object) -> str:
    """Validate and return one canonical namespaced event type."""
    if not isinstance(value, str) or _NAMESPACED_EVENT_TYPE.fullmatch(value) is None:
        raise ValidationFailure("event_type must be a lowercase namespaced name")
    return value


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


def _normalize_id(
    value: object, identifier_type: type[Identifier], field_name: str
) -> Identifier:
    candidate = _text_id(value, field_name)
    try:
        return identifier_type(candidate)
    except (TypeError, ValueError) as error:
        raise ValidationFailure(f"invalid {field_name}") from error


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


@dataclass(frozen=True, slots=True, init=False)
class EventEnvelope:
    """Immutable, canonical event boundary shared by hosts and the kernel.

    The envelope deliberately contains only trusted primitive identifiers and a
    deeply frozen JSON payload.  Product modules may attach meaning to the
    event type, but cannot smuggle executable/provider objects across this
    boundary.
    """

    event_id: EventId
    event_type: str
    schema_version: int
    stream_id: CourseId
    stream_sequence: int
    occurred_at: datetime
    correlation_id: CorrelationId
    actor: Actor
    payload: JsonObject = field(default_factory=dict)
    session_id: SessionId | None = None
    causation_id: EventId | None = None

    def __init__(
        self,
        event_id: EventId | str,
        event_type: str,
        schema_version: int,
        stream_id: CourseId | str,
        stream_sequence: int,
        occurred_at: datetime,
        correlation_id: CorrelationId | str,
        actor: Actor,
        payload: JsonObject | None = None,
        session_id: SessionId | str | None = None,
        causation_id: EventId | str | None = None,
    ) -> None:
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "stream_id", stream_id)
        object.__setattr__(self, "stream_sequence", stream_sequence)
        object.__setattr__(self, "occurred_at", occurred_at)
        object.__setattr__(self, "correlation_id", correlation_id)
        object.__setattr__(self, "actor", actor)
        object.__setattr__(self, "payload", {} if payload is None else payload)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "causation_id", causation_id)
        self.__post_init__()

    def __post_init__(self) -> None:
        validate_event_type(self.event_type)
        if type(self.schema_version) is not int or self.schema_version < 1:
            raise ValidationFailure("schema_version must be positive")
        if type(self.stream_sequence) is not int or self.stream_sequence < 1:
            raise ValidationFailure("stream_sequence must be positive")
        if (
            not isinstance(self.actor, Actor)
            or not isinstance(self.actor.kind, PrincipalKind)
            or not isinstance(self.actor.principal_id, str)
        ):
            raise ValidationFailure("actor must be a trusted Actor")
        if not isinstance(self.occurred_at, datetime):
            raise ValidationFailure("occurred_at must be a datetime")
        try:
            require_aware(self.occurred_at, "occurred_at")
        except (TypeError, ValueError) as error:
            raise ValidationFailure(str(error)) from error
        event_id = _normalize_id(self.event_id, EventId, "event_id")
        stream_id = _normalize_id(self.stream_id, CourseId, "stream_id")
        correlation_id = _normalize_id(self.correlation_id, CorrelationId, "correlation_id")
        session_id = (
            None
            if self.session_id is None
            else _normalize_id(self.session_id, SessionId, "session_id")
        )
        if self.causation_id is not None:
            causation_id = _normalize_id(self.causation_id, EventId, "causation_id")
            if causation_id == event_id:
                raise ValidationFailure("an event cannot cause itself")
        else:
            causation_id = None
        if not isinstance(self.payload, Mapping):
            raise ValidationFailure("payload must be a JSON object")
        _reject_unsafe_json(self.payload)
        try:
            frozen_payload = freeze_object(self.payload)
        except (TypeError, ValueError) as error:
            raise ValidationFailure("payload is not valid JSON") from error
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "stream_id", stream_id)
        object.__setattr__(self, "correlation_id", correlation_id)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "causation_id", causation_id)
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
        result = {
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
        if self.session_id is not None:
            result["session_id"] = _text_id(self.session_id, "session_id")
        return result

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
        keys = set(value)
        if keys not in (expected, expected | {"session_id"}):
            raise ValidationFailure("event envelope fields are not canonical")
        actor_value = value["actor"]
        if not isinstance(actor_value, Mapping) or set(actor_value) != {"kind", "principal_id"}:
            raise ValidationFailure("actor must contain kind and principal_id")
        try:
            actor = Actor(PrincipalKind(actor_value["kind"]), actor_value["principal_id"])
            occurred_at_value = value["occurred_at"]
            if not isinstance(occurred_at_value, str):
                raise ValidationFailure("occurred_at must be an ISO-8601 string")
            occurred_at = datetime.fromisoformat(
                occurred_at_value.replace("Z", "+00:00")
            )
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
                session_id=cast(SessionId | str | None, value.get("session_id")),
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
