"""Schema-versioned reducer registration and dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.domain.events import DomainEvent

type PayloadDecoder[PayloadT] = Callable[[JsonObject], PayloadT]
type EventDecoder[PayloadT] = Callable[[DomainEvent], PayloadT]
type TypedEventReducer[PayloadT] = Callable[
    [JsonObject, DomainEvent, PayloadT], Mapping[str, JsonValue]
]
type _ErasedReducer = Callable[[JsonObject, DomainEvent, object], Mapping[str, JsonValue]]


class ReducerRegistrationError(ValueError):
    """Raised when a reducer registration is invalid or duplicated."""


class UnknownEventSchemaError(LookupError):
    """Raised when no reducer exists for an event type and schema version."""


class PayloadValidationError(ValueError):
    """Raised when a registered decoder rejects an event payload."""


@dataclass(frozen=True, slots=True)
class _Registration:
    decoder: EventDecoder[object]
    reducer: _ErasedReducer


class EventRegistry:
    """Dispatch immutable event envelopes to reducers by exact schema version."""

    def __init__(self) -> None:
        self._registrations: dict[tuple[str, int], _Registration] = {}

    def register[PayloadT](
        self,
        event_type: str,
        schema_version: int,
        decoder: PayloadDecoder[PayloadT],
        reducer: TypedEventReducer[PayloadT],
    ) -> None:
        """Register the required decoder and reducer for one exact event schema."""

        def erased_decoder(payload: JsonObject) -> object:
            return decoder(payload)

        def erased_reducer(
            state: JsonObject, event: DomainEvent, payload: object
        ) -> Mapping[str, JsonValue]:
            return reducer(state, event, cast(PayloadT, payload))

        self._register(
            event_type,
            schema_version,
            lambda event: erased_decoder(event.payload),
            erased_reducer,
        )

    def register_event[PayloadT](
        self,
        event_type: str,
        schema_version: int,
        decoder: EventDecoder[PayloadT],
        reducer: TypedEventReducer[PayloadT],
    ) -> None:
        """Register mandatory validation against the complete event envelope."""

        def erased_decoder(event: DomainEvent) -> object:
            return decoder(event)

        def erased_reducer(
            state: JsonObject, event: DomainEvent, payload: object
        ) -> Mapping[str, JsonValue]:
            return reducer(state, event, cast(PayloadT, payload))

        self._register(event_type, schema_version, erased_decoder, erased_reducer)

    def register_typed[PayloadT](
        self,
        event_type: str,
        schema_version: int,
        decoder: PayloadDecoder[PayloadT],
        reducer: TypedEventReducer[PayloadT],
    ) -> None:
        """Alias for :meth:`register`; validation remains mandatory."""
        self.register(event_type, schema_version, decoder, reducer)

    def _register(
        self,
        event_type: str,
        schema_version: int,
        decoder: EventDecoder[object],
        reducer: _ErasedReducer,
    ) -> None:
        if not event_type or event_type != event_type.strip():
            raise ReducerRegistrationError("event_type must be non-empty and trimmed")
        if schema_version < 1:
            raise ReducerRegistrationError("schema_version must be positive")
        key = (event_type, schema_version)
        if key in self._registrations:
            raise ReducerRegistrationError(
                f"reducer already registered for {event_type}@{schema_version}"
            )
        self._registrations[key] = _Registration(decoder, reducer)

    def _registration(self, event: DomainEvent) -> _Registration:
        try:
            return self._registrations[(event.event_type, event.schema_version)]
        except KeyError as error:
            raise UnknownEventSchemaError(
                f"no reducer registered for {event.event_type}@{event.schema_version}"
            ) from error

    def decode(self, event: DomainEvent) -> object:
        """Validate and decode an event payload without reducing state."""
        registration = self._registration(event)
        try:
            return registration.decoder(event)
        except Exception as error:
            raise PayloadValidationError(
                f"invalid payload for {event.event_type}@{event.schema_version}: {error}"
            ) from error

    def reduce_decoded(
        self, state: JsonObject, event: DomainEvent, decoded_payload: object
    ) -> JsonObject:
        """Reduce a payload previously decoded for the same exact event schema."""
        registration = self._registration(event)
        return freeze_object(registration.reducer(state, event, decoded_payload))

    def reduce(self, state: JsonObject, event: DomainEvent) -> JsonObject:
        return self.reduce_decoded(state, event, self.decode(event))
