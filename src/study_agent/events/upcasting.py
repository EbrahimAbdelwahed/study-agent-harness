"""Deterministic adjacent event schema upcasting."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from study_agent.domain._validation import JsonObject, freeze_object
from study_agent.domain.errors import ConflictFailure, ValidationFailure
from study_agent.domain.events import DomainEvent, EventEnvelope, validate_event_type

type Upcaster = Callable[[JsonObject], Mapping[str, Any]]


class EventUpcasterRegistry:
    """Explicit registry for pure, one-version-at-a-time migrations."""

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
        validate_event_type(event_type)
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
        validate_event_type(event_type)
        versions = [
            from_version + 1
            for (name, from_version) in self._upcasters
            if name == event_type
        ]
        if not versions:
            raise ValidationFailure("unknown event schema")
        return max(versions)

    def _payload(
        self, event_type: str, payload: JsonObject, current: int, target: int
    ) -> tuple[int, JsonObject]:
        if type(target) is not int or target < current:
            raise ValidationFailure("target schema version is unsupported")
        migrated = payload
        while current < target:
            try:
                next_version, upcaster = self._upcasters[(event_type, current)]
            except KeyError as error:
                raise ValidationFailure("event schema upcast path is incomplete") from error
            if next_version != current + 1:
                raise ValidationFailure("event schema upcast path is malformed")
            try:
                candidate = upcaster(migrated)
                if not isinstance(candidate, Mapping):
                    raise TypeError("upcaster must return a JSON object")
                first = freeze_object(candidate)
                # Calling the edge twice over the exact immutable input proves
                # deterministic behavior and catches stateful migrations.
                repeat_candidate = upcaster(migrated)
                if not isinstance(repeat_candidate, Mapping):
                    raise TypeError("upcaster must return a JSON object")
                if first != freeze_object(repeat_candidate):
                    raise ValueError("upcaster is not deterministic")
            except ValidationFailure:
                raise
            except Exception as error:
                raise ValidationFailure("event upcaster produced an invalid payload") from error
            migrated = first
            current = next_version
        return current, migrated

    def upcast(
        self,
        event: EventEnvelope,
        target_schema_version: int | None = None,
    ) -> EventEnvelope:
        """Upcast a public envelope without changing identity."""

        if not isinstance(event, EventEnvelope):
            raise ValidationFailure("upcast requires an event envelope")
        event_type = event.event_type
        validate_event_type(event_type)
        current_version = event.schema_version
        if target_schema_version is None:
            target_schema_version = self.current_version(event_type)
        target, payload = self._payload(
            event_type, event.payload, current_version, target_schema_version
        )
        return replace(event, schema_version=target, payload=payload)

    def _upcast_legacy(
        self, event: DomainEvent, target_schema_version: int | None = None
    ) -> DomainEvent:
        """Private transitional adapter for legacy reducers and replay."""

        event_type = event.event_type
        validate_event_type(event_type)
        current_version = event.schema_version
        if target_schema_version is None:
            target_schema_version = self.current_version(event_type)
        target, payload = self._payload(
            event_type, event.payload, current_version, target_schema_version
        )
        return replace(event, schema_version=target, payload=payload)

    migrate = upcast
