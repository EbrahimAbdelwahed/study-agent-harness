"""Deterministic, adjacent event schema upcasting."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from study_agent.domain._validation import JsonObject, freeze_object
from study_agent.domain.errors import ConflictFailure, ValidationFailure
from study_agent.domain.events import EventEnvelope

type Upcaster = Callable[[JsonObject], Mapping[str, Any]]


class EventUpcasterRegistry:
    """Explicit registry for pure adjacent schema migrations.

    Registration is intentionally closed before runtime use.  A registry has
    at most one edge per event type/version and always walks that edge in
    ascending order, making mixed-version replay deterministic.
    """

    def __init__(self) -> None:
        self._upcasters: dict[tuple[str, int], tuple[int, Upcaster]] = {}
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> EventUpcasterRegistry:
        self._closed = True
        return self

    freeze = close

    def register(
        self,
        event_type: str,
        from_schema_version: int | None = None,
        upcaster: Upcaster | None = None,
        to_schema_version: int | None = None,
        *,
        old_schema_version: int | None = None,
    ) -> None:
        if self._closed:
            raise ValidationFailure("event upcaster registration is closed")
        if (
            not isinstance(event_type, str)
            or not event_type.strip()
            or event_type != event_type.strip()
        ):
            raise ValidationFailure("event type must be non-empty and trimmed")
        if from_schema_version is None:
            from_schema_version = old_schema_version
        elif old_schema_version is not None and old_schema_version != from_schema_version:
            raise ValidationFailure("source schema versions disagree")
        if type(from_schema_version) is not int or from_schema_version < 1:
            raise ValidationFailure("source schema version must be positive")
        target = from_schema_version + 1 if to_schema_version is None else to_schema_version
        if type(target) is not int or target != from_schema_version + 1:
            raise ValidationFailure("upcasters must advance exactly one schema version")
        if not callable(upcaster):
            raise ValidationFailure("upcaster must be callable")
        key = (event_type, from_schema_version)
        if key in self._upcasters:
            raise ConflictFailure("event upcaster already registered")
        self._upcasters[key] = (target, upcaster)

    register_upcaster = register

    def current_version(self, event_type: str) -> int:
        versions = [
            from_version + 1
            for (name, from_version) in self._upcasters
            if name == event_type
        ]
        if not versions:
            raise ValidationFailure("unknown event schema")
        return max(versions)

    def upcast(
        self, envelope: EventEnvelope, target_schema_version: int | None = None
    ) -> EventEnvelope:
        if not isinstance(envelope, EventEnvelope):
            raise ValidationFailure("upcast requires an event envelope")
        target = (
            self.current_version(envelope.event_type)
            if target_schema_version is None
            else target_schema_version
        )
        if type(target) is not int or target < envelope.schema_version:
            raise ValidationFailure("target schema version is unsupported")
        if target == envelope.schema_version:
            return envelope
        current = envelope.schema_version
        payload = envelope.payload
        while current < target:
            try:
                next_version, upcaster = self._upcasters[(envelope.event_type, current)]
            except KeyError as error:
                raise ValidationFailure("event schema upcast path is incomplete") from error
            if next_version != current + 1:
                raise ValidationFailure("event schema upcast path is malformed")
            try:
                candidate = upcaster(payload)
                if not isinstance(candidate, Mapping):
                    raise TypeError("upcaster must return a JSON object")
                migrated = freeze_object(candidate)
                # A second invocation against the same frozen input must be
                # byte-identical; this rejects stateful/non-deterministic edges.
                repeat = freeze_object(upcaster(payload))
                if migrated != repeat:
                    raise ValueError("upcaster is not deterministic")
            except ValidationFailure:
                raise
            except Exception as error:
                raise ValidationFailure("event upcaster produced an invalid payload") from error
            payload = migrated
            current = next_version
        return replace(envelope, schema_version=current, payload=payload)

    migrate = upcast
