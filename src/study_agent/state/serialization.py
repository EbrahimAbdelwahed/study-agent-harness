"""Canonical serialization for event envelopes and projection state."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.domain.events import Actor, DomainEvent, PrincipalKind
from study_agent.domain.identifiers import CorrelationId, CourseId, EventId, SessionId


def _json_value(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def canonical_json_bytes(value: JsonObject) -> bytes:
    """Serialize an immutable JSON object with one stable UTF-8 representation."""
    return json.dumps(
        _json_value(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_json_object(data: bytes) -> JsonObject:
    """Decode JSON bytes and return a deeply immutable JSON object."""
    decoded: Any = json.loads(data)
    if not isinstance(decoded, dict):
        raise ValueError("canonical state must be a JSON object")
    return freeze_object(cast(dict[str, JsonValue], decoded))


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def event_to_bytes(event: DomainEvent) -> bytes:
    """Serialize a complete domain event envelope canonically."""
    envelope: dict[str, JsonValue] = {
        "actor": {"kind": event.actor.kind.value, "principal_id": event.actor.principal_id},
        "causation_id": str(event.causation_id) if event.causation_id else None,
        "correlation_id": str(event.correlation_id),
        "course_id": str(event.course_id),
        "course_sequence": event.course_sequence,
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "occurred_at": _timestamp(event.occurred_at),
        "payload": event.payload,
        "schema_version": event.schema_version,
        "session_id": str(event.session_id) if event.session_id else None,
    }
    return canonical_json_bytes(envelope)


def _required(envelope: Mapping[str, JsonValue], key: str, expected: type[object]) -> object:
    value = envelope.get(key)
    if not isinstance(value, expected):
        raise ValueError(f"event field {key!r} has an invalid type")
    return value


def _required_int(envelope: Mapping[str, JsonValue], key: str) -> int:
    value = envelope.get(key)
    if type(value) is not int:
        raise ValueError(f"event field {key!r} has an invalid type")
    return value


def event_from_bytes(data: bytes) -> DomainEvent:
    """Deserialize a canonical event envelope into the public domain type."""
    envelope = canonical_json_object(data)
    actor = cast(Mapping[str, JsonValue], _required(envelope, "actor", Mapping))
    payload = cast(Mapping[str, JsonValue], _required(envelope, "payload", Mapping))
    occurred_at = str(_required(envelope, "occurred_at", str))
    session_id = envelope.get("session_id")
    causation_id = envelope.get("causation_id")
    if session_id is not None and not isinstance(session_id, str):
        raise ValueError("event field 'session_id' has an invalid type")
    if causation_id is not None and not isinstance(causation_id, str):
        raise ValueError("event field 'causation_id' has an invalid type")

    return DomainEvent(
        event_id=EventId(str(_required(envelope, "event_id", str))),
        course_id=CourseId(str(_required(envelope, "course_id", str))),
        course_sequence=_required_int(envelope, "course_sequence"),
        event_type=str(_required(envelope, "event_type", str)),
        schema_version=_required_int(envelope, "schema_version"),
        actor=Actor(
            PrincipalKind(str(_required(actor, "kind", str))),
            str(_required(actor, "principal_id", str)),
        ),
        occurred_at=datetime.fromisoformat(occurred_at.replace("Z", "+00:00")),
        correlation_id=CorrelationId(str(_required(envelope, "correlation_id", str))),
        payload=payload,
        session_id=SessionId(session_id) if session_id else None,
        causation_id=EventId(causation_id) if causation_id else None,
    )
