"""Schema-aware reducer registration, preparation, and dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.domain.errors import ValidationFailure
from study_agent.domain.events import (
    Actor,
    DomainEvent,
    EventEnvelope,
    validate_event_type,
)
from study_agent.domain.identifiers import (
    CorrelationId,
    CourseId,
    EventId,
    Identifier,
    SessionId,
)

if TYPE_CHECKING:
    from study_agent.events.upcasting import EventUpcasterRegistry

type PayloadDecoder[PayloadT] = Callable[[JsonObject], PayloadT]
type EventDecoder[PayloadT] = Callable[[DomainEvent], PayloadT]
type TypedEventReducer[PayloadT] = Callable[
    [JsonObject, DomainEvent, PayloadT], Mapping[str, JsonValue]
]
type _ErasedReducer = Callable[[JsonObject, DomainEvent, object], Mapping[str, JsonValue]]
type ProjectionMigrator = Callable[[JsonObject], Mapping[str, JsonValue]]
type EventInput = DomainEvent | EventEnvelope


class ReducerRegistrationError(ValueError):
    """Raised when a reducer registration is invalid or duplicated."""


class UnknownEventSchemaError(ValidationFailure, LookupError):
    """Raised when no reducer exists for an event type and schema version."""


class PayloadValidationError(ValueError):
    """Raised when a registered decoder rejects an event payload."""


@dataclass(frozen=True, slots=True)
class _Registration:
    decoder: EventDecoder[object]
    reducer: _ErasedReducer


class EventRegistry:
    """Dispatch immutable event inputs through declared current schemas.

    ``DomainEvent`` is retained only as a private transition shape for existing
    reducers.  Public envelope inputs are normalized and upcast to that shape
    before a decoder or reducer can observe them.
    """

    def __init__(
        self,
        upcasters: EventUpcasterRegistry | None = None,
        *,
        upcaster_registry: EventUpcasterRegistry | None = None,
    ) -> None:
        if (
            upcasters is not None
            and upcaster_registry is not None
            and upcasters is not upcaster_registry
        ):
            raise ValidationFailure("multiple upcaster registries were supplied")
        self._registrations: dict[tuple[str, int], _Registration] = {}
        self._projection_migrations: list[ProjectionMigrator] = []
        self._closed = False
        selected = upcasters or upcaster_registry
        if selected is None:
            from study_agent.events.upcasting import EventUpcasterRegistry

            selected = EventUpcasterRegistry()
        self._upcasters = selected

    @property
    def upcasters(self) -> EventUpcasterRegistry:
        return self._upcasters

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> EventRegistry:
        self._upcasters.close()
        self._closed = True
        return self

    def register_projection_migration(self, migrator: ProjectionMigrator) -> None:
        """Register one deterministic, projection-only state migration."""
        if self._closed:
            raise ValidationFailure("event registry is closed")
        if migrator in self._projection_migrations:
            return
        self._projection_migrations.append(migrator)

    def migrate_projection(self, state: JsonObject) -> JsonObject:
        migrated = state
        for migrator in self._projection_migrations:
            migrated = freeze_object(migrator(migrated))
        return migrated

    def register_upcaster(
        self,
        event_type: str,
        from_schema_version: int | None = None,
        upcaster: Callable[[JsonObject], Mapping[str, object]] | None = None,
        to_schema_version: int | None = None,
        *,
        old_schema_version: int | None = None,
    ) -> None:
        if self._closed:
            raise ValidationFailure("event registry is closed")
        self._upcasters.register(
            event_type,
            from_schema_version,
            upcaster,
            to_schema_version,
            old_schema_version=old_schema_version,
        )

    def register[PayloadT](
        self,
        event_type: str,
        schema_version: int,
        decoder: PayloadDecoder[PayloadT],
        reducer: TypedEventReducer[PayloadT],
    ) -> None:
        """Register a payload decoder and reducer for one exact schema."""
        if self._closed:
            raise ValidationFailure("event registry is closed")

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
        """Register validation against the complete prepared event."""

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
        self.register(event_type, schema_version, decoder, reducer)

    def register_erased(
        self,
        event_type: str,
        schema_version: int,
        decoder: Callable[[JsonObject], object],
        reducer: _ErasedReducer,
    ) -> None:
        """Register a compiled module's already-erased decoder/reducer pair."""
        self._register(
            event_type,
            schema_version,
            lambda event: decoder(event.payload),
            reducer,
        )

    def _register(
        self,
        event_type: str,
        schema_version: int,
        decoder: EventDecoder[object],
        reducer: _ErasedReducer,
    ) -> None:
        if self._closed:
            raise ValidationFailure("event registry is closed")
        try:
            validate_event_type(event_type)
        except ValidationFailure as error:
            raise ReducerRegistrationError(str(error)) from error
        if type(schema_version) is not int or schema_version < 1:
            raise ReducerRegistrationError("schema_version must be positive")
        key = (event_type, schema_version)
        if key in self._registrations:
            raise ReducerRegistrationError(
                f"reducer already registered for {event_type}@{schema_version}"
            )
        self._registrations[key] = _Registration(decoder, reducer)

    def current_schema_version(self, event_type: str) -> int:
        validate_event_type(event_type)
        versions = [version for name, version in self._registrations if name == event_type]
        if not versions:
            raise UnknownEventSchemaError(f"no reducer registered for {event_type}")
        return max(versions)

    def _registration(self, event: DomainEvent) -> _Registration:
        try:
            return self._registrations[(event.event_type, event.schema_version)]
        except KeyError as error:
            raise UnknownEventSchemaError(
                f"no reducer registered for {event.event_type}@{event.schema_version}"
            ) from error

    @staticmethod
    def _envelope_to_domain(event: EventEnvelope) -> DomainEvent:
        return DomainEvent(
            event_id=event.event_id,
            course_id=event.stream_id,
            course_sequence=event.stream_sequence,
            event_type=event.event_type,
            schema_version=event.schema_version,
            actor=Actor(event.actor.kind, event.actor.principal_id),
            occurred_at=event.occurred_at,
            correlation_id=event.correlation_id,
            payload=event.payload,
            causation_id=event.causation_id,
        )

    @staticmethod
    def _legacy_to_domain(event: DomainEvent) -> DomainEvent:
        """Normalize transitional legacy values before they reach a reducer."""

        def identifier(
            value: object, identifier_type: type[Identifier], field: str
        ) -> Identifier:
            raw = value.value if isinstance(value, Identifier) else value
            if not isinstance(raw, str) or not raw.strip() or raw != raw.strip():
                raise ValidationFailure(f"{field} must be non-empty text")
            try:
                return identifier_type(raw)
            except (TypeError, ValueError) as error:
                raise ValidationFailure(f"invalid {field}") from error

        if not isinstance(event.actor, Actor):
            raise ValidationFailure("actor must be a trusted Actor")
        if not hasattr(event.occurred_at, "tzinfo"):
            raise ValidationFailure("occurred_at must be a datetime")
        try:
            return DomainEvent(
                event_id=cast(EventId, identifier(event.event_id, EventId, "event_id")),
                course_id=cast(CourseId, identifier(event.course_id, CourseId, "course_id")),
                course_sequence=event.course_sequence,
                event_type=event.event_type,
                schema_version=event.schema_version,
                actor=event.actor,
                occurred_at=event.occurred_at,
                correlation_id=cast(
                    CorrelationId,
                    identifier(event.correlation_id, CorrelationId, "correlation_id"),
                ),
                payload=event.payload,
                session_id=(
                    None
                    if event.session_id is None
                    else cast(SessionId, identifier(event.session_id, SessionId, "session_id"))
                ),
                causation_id=(
                    None
                    if event.causation_id is None
                    else cast(EventId, identifier(event.causation_id, EventId, "causation_id"))
                ),
            )
        except ValidationFailure:
            raise
        except (AttributeError, TypeError, ValueError) as error:
            raise ValidationFailure("invalid legacy event") from error

    def prepare(
        self,
        event: EventInput,
        target_schema_version: int | None = None,
    ) -> DomainEvent:
        """Normalize a stream input and upcast it to its declared current schema."""

        if not isinstance(event, (DomainEvent, EventEnvelope)):
            raise ValidationFailure("event must be a DomainEvent or EventEnvelope")
        validate_event_type(event.event_type)
        current = self.current_schema_version(event.event_type)
        target = current if target_schema_version is None else target_schema_version
        if type(target) is not int or target < 1 or target > current:
            raise ValidationFailure("target schema version is unsupported")
        normalized: EventInput = (
            self._legacy_to_domain(event) if isinstance(event, DomainEvent) else event
        )
        if event.schema_version > target:
            raise UnknownEventSchemaError(
                f"no reducer registered for {event.event_type}@{event.schema_version}"
            )
        if normalized.schema_version < target:
            normalized = (
                self._upcasters._upcast_legacy(normalized, target)
                if isinstance(normalized, DomainEvent)
                else self._upcasters.upcast(normalized, target)
            )
        prepared = (
            normalized
            if isinstance(normalized, DomainEvent)
            else self._envelope_to_domain(normalized)
        )
        if prepared.schema_version != target:
            raise ValidationFailure("event schema did not reach declared current version")
        # Constructing the legacy shape above also validates normalized IDs,
        # timestamps, payload, and causation before dispatch.
        return prepared

    def prepare_for_replay(self, event: EventInput) -> DomainEvent:
        """Prepare one retained event without rewriting an exact old schema.

        Current append validation intentionally targets the newest registered
        schema.  Stored history is different: when an exact decoder is
        registered for an older envelope, replay must dispatch that decoder
        with the original schema and payload so its compatibility verifier can
        preserve the event identity and bytes.  Other event types continue
        through the normal deterministic upcaster path.
        """

        if not isinstance(event, (DomainEvent, EventEnvelope)):
            raise ValidationFailure("event must be a DomainEvent or EventEnvelope")
        validate_event_type(event.event_type)
        key = (event.event_type, event.schema_version)
        normalized = (
            self._legacy_to_domain(event) if isinstance(event, DomainEvent) else event
        )
        if key in self._registrations:
            return (
                normalized
                if isinstance(normalized, DomainEvent)
                else self._envelope_to_domain(normalized)
            )
        return self.prepare(normalized)

    def decode(self, event: EventInput) -> object:
        prepared = self.prepare(event)
        registration = self._registration(prepared)
        try:
            return registration.decoder(prepared)
        except (ValidationFailure, UnknownEventSchemaError):
            raise
        except Exception as error:
            raise PayloadValidationError(
                f"invalid payload for {prepared.event_type}@{prepared.schema_version}: {error}"
            ) from error

    def decode_for_replay(self, event: EventInput) -> object:
        """Decode a stored event using its exact registered schema."""

        prepared = self.prepare_for_replay(event)
        registration = self._registration(prepared)
        try:
            return registration.decoder(prepared)
        except (ValidationFailure, UnknownEventSchemaError):
            raise
        except Exception as error:
            raise PayloadValidationError(
                f"invalid payload for {prepared.event_type}@{prepared.schema_version}: {error}"
            ) from error

    def reduce_decoded(
        self, state: JsonObject, event: EventInput, decoded_payload: object
    ) -> JsonObject:
        prepared = self.prepare(event)
        registration = self._registration(prepared)
        return freeze_object(registration.reducer(state, prepared, decoded_payload))

    def reduce_decoded_for_replay(
        self, state: JsonObject, event: EventInput, decoded_payload: object
    ) -> JsonObject:
        """Reduce a retained event without changing its envelope schema."""

        prepared = self.prepare_for_replay(event)
        registration = self._registration(prepared)
        return freeze_object(registration.reducer(state, prepared, decoded_payload))

    def reduce(self, state: JsonObject, event: EventInput) -> JsonObject:
        prepared = self.prepare(event)
        return self.reduce_decoded(state, prepared, self.decode(prepared))

    def reduce_for_replay(self, state: JsonObject, event: EventInput) -> JsonObject:
        """Decode and reduce one stored event through exact-schema replay."""

        prepared = self.prepare_for_replay(event)
        return self.reduce_decoded_for_replay(
            state, prepared, self.decode_for_replay(prepared)
        )
