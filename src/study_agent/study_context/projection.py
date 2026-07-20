"""Pure reducers for progressive study-context state."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

from study_agent.domain import (
    DomainEvent,
    InteractionKind,
    StatementStatus,
    StudyStatementInput,
    StudyStatementKind,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.state import EventRegistry

from .events import (
    CONFLICT_RESOLVED,
    STATEMENT_RECORDED,
    STATEMENT_RETRACTED,
    STUDY_CONTEXT_SCHEMA_VERSION,
    ConflictResolved,
    StatementRecorded,
    StatementRetracted,
    decode_conflict_resolved,
    decode_statement_recorded,
    decode_statement_retracted,
    statement_value_manifest,
)


def reduce_statement_recorded(
    state: JsonObject, event: DomainEvent, payload: StatementRecorded
) -> Mapping[str, JsonValue]:
    if "course" not in state:
        raise ValueError("study context requires an existing course")
    session_id = _require_session(state, event)
    _require_human_origin(state, session_id, payload)
    context, statements, resolutions, commands = _parts(state, event)
    key = str(event.event_id)
    if key in commands or str(payload.statement_id) in statements:
        raise ValueError("study-context record command already exists")
    statement = {
        "statement_id": str(payload.statement_id),
        "course_id": str(event.course_id),
        "session_id": str(event.session_id),
        "origin_interaction_id": str(payload.origin_interaction_id),
        "kind": payload.statement.kind.value,
        "value": statement_value_manifest(payload.statement),
        "status": StatementStatus.ACTIVE.value,
        "recorded_at": event.occurred_at.isoformat(),
    }
    return _replace(
        state,
        context,
        {**statements, str(payload.statement_id): statement},
        resolutions,
        {
            **commands,
            key: {
                "command_fingerprint": payload.command_fingerprint,
                "statement_id": str(payload.statement_id),
            },
        },
    )


def reduce_statement_retracted(
    state: JsonObject, event: DomainEvent, payload: StatementRetracted
) -> Mapping[str, JsonValue]:
    _require_session(state, event)
    context, statements, resolutions, commands = _parts(state, event)
    if str(event.event_id) in commands:
        raise ValueError("study-context retract command already exists")
    raw = statements.get(str(payload.statement_id))
    if not isinstance(raw, Mapping) or raw.get("status") != StatementStatus.ACTIVE.value:
        raise ValueError("retraction target must be an active statement")
    updated = {**raw, "status": StatementStatus.RETRACTED.value}
    return _replace(
        state,
        context,
        {**statements, str(payload.statement_id): updated},
        resolutions,
        {
            **commands,
            str(event.event_id): {
                "command_fingerprint": payload.command_fingerprint,
                "statement_id": str(payload.statement_id),
            },
        },
    )


def reduce_conflict_resolved(
    state: JsonObject, event: DomainEvent, payload: ConflictResolved
) -> Mapping[str, JsonValue]:
    _require_session(state, event)
    context, statements, resolutions, commands = _parts(state, event)
    if str(event.event_id) in commands:
        raise ValueError("study-context resolution command already exists")
    selected = statements.get(str(payload.selected_statement_id))
    if not isinstance(selected, Mapping):
        raise ValueError("resolution winner was not found")
    if (
        selected.get("status") != StatementStatus.ACTIVE.value
        or selected.get("kind") != payload.kind.value
    ):
        raise ValueError("resolution winner must be active and match the scalar kind")
    active = {
        statement_id: raw
        for statement_id, raw in statements.items()
        if isinstance(raw, Mapping)
        and raw.get("kind") == payload.kind.value
        and raw.get("status") == StatementStatus.ACTIVE.value
    }
    distinct_values = {_value_key(raw.get("value")) for raw in active.values()}
    if len(distinct_values) < 2:
        raise ValueError("resolution requires a current scalar conflict")
    selected_value = _value_key(selected.get("value"))
    expected_losers = tuple(
        sorted(
            (
                statement_id
                for statement_id, raw in active.items()
                if _value_key(raw.get("value")) != selected_value
            )
        )
    )
    actual_losers = tuple(map(str, payload.superseded_statement_ids))
    if actual_losers != expected_losers:
        raise ValueError("resolution losers do not match the current conflict")
    updated_statements = dict(statements)
    for statement_id in expected_losers:
        raw = active[statement_id]
        updated_statements[statement_id] = {
            **raw,
            "status": StatementStatus.SUPERSEDED.value,
        }
    resolution: JsonObject = {
        "event_id": str(event.event_id),
        "kind": payload.kind.value,
        "selected_statement_id": str(payload.selected_statement_id),
        "superseded_statement_ids": actual_losers,
        "resolved_at": event.occurred_at.isoformat(),
    }
    return _replace(
        state,
        context,
        updated_statements,
        (*resolutions, resolution),
        {
            **commands,
            str(event.event_id): {
                "command_fingerprint": payload.command_fingerprint,
                "statement_id": str(payload.selected_statement_id),
            },
        },
    )


def register_study_context_events(registry: EventRegistry) -> None:
    registry.register_event(
        STATEMENT_RECORDED,
        STUDY_CONTEXT_SCHEMA_VERSION,
        decode_statement_recorded,
        reduce_statement_recorded,
    )
    registry.register_event(
        STATEMENT_RETRACTED,
        STUDY_CONTEXT_SCHEMA_VERSION,
        decode_statement_retracted,
        reduce_statement_retracted,
    )
    registry.register_event(
        CONFLICT_RESOLVED,
        STUDY_CONTEXT_SCHEMA_VERSION,
        decode_conflict_resolved,
        reduce_conflict_resolved,
    )


def _parts(
    state: JsonObject, event: DomainEvent
) -> tuple[
    Mapping[str, JsonValue],
    Mapping[str, JsonValue],
    tuple[JsonValue, ...],
    Mapping[str, JsonValue],
]:
    raw = state.get("study_context", {})
    if not isinstance(raw, Mapping):
        raise ValueError("study-context projection is corrupt")
    expected = {"statements", "resolutions", "commands"}
    if raw and set(raw) != expected:
        raise ValueError("study-context projection fields are corrupt")
    statements = raw.get("statements", {})
    resolutions = raw.get("resolutions", ())
    commands = raw.get("commands", {})
    if (
        not isinstance(statements, Mapping)
        or not isinstance(resolutions, tuple)
        or not isinstance(commands, Mapping)
    ):
        raise ValueError("study-context projection collections are corrupt")
    _validate_statements(event, statements)
    _validate_resolutions(resolutions)
    _validate_commands(commands)
    return raw, statements, resolutions, commands


def _replace(
    state: JsonObject,
    _: Mapping[str, JsonValue],
    statements: Mapping[str, JsonValue],
    resolutions: tuple[JsonValue, ...],
    commands: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    return {
        **state,
        "study_context": {
            "statements": statements,
            "resolutions": resolutions,
            "commands": commands,
        },
    }


def _value_key(value: JsonValue | None) -> tuple[str, str]:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("projected scalar statement value is corrupt")
    return type(value).__name__, str(value)


def _require_session(state: JsonObject, event: DomainEvent) -> str:
    session_id = str(event.session_id)
    sessions = state.get("sessions")
    if not isinstance(sessions, Mapping):
        raise ValueError("study context requires canonical session state")
    session = sessions.get(session_id)
    if (
        not isinstance(session, Mapping)
        or session.get("session_id") != session_id
        or session.get("course_id") != str(event.course_id)
    ):
        raise ValueError("study-context event session was not found in its course")
    return session_id


def _require_human_origin(
    state: JsonObject, session_id: str, payload: StatementRecorded
) -> None:
    interactions = state.get("session_interactions")
    if not isinstance(interactions, Mapping):
        raise ValueError("study context requires canonical interaction state")
    origin = interactions.get(str(payload.origin_interaction_id))
    if (
        not isinstance(origin, Mapping)
        or origin.get("session_id") != session_id
        or origin.get("kind") != InteractionKind.HUMAN.value
    ):
        raise ValueError(
            "statement origin must be a canonical human interaction in the event session"
        )


def _validate_statements(
    event: DomainEvent, statements: Mapping[str, JsonValue]
) -> None:
    expected = {
        "statement_id",
        "course_id",
        "session_id",
        "origin_interaction_id",
        "kind",
        "value",
        "status",
        "recorded_at",
    }
    for statement_id, raw in statements.items():
        if (
            not isinstance(statement_id, str)
            or not isinstance(raw, Mapping)
            or set(raw) != expected
            or raw.get("statement_id") != statement_id
            or raw.get("course_id") != str(event.course_id)
        ):
            raise ValueError("study-context statement entries are corrupt")
        _text(raw.get("session_id"), "statement session_id")
        _text(raw.get("origin_interaction_id"), "statement origin_interaction_id")
        kind = _kind(raw.get("kind"))
        _statement_value(kind, raw.get("value"))
        try:
            StatementStatus(_text(raw.get("status"), "statement status"))
        except ValueError as error:
            raise ValueError("study-context statement status is corrupt") from error
        _timestamp(raw.get("recorded_at"), "statement recorded_at")


def _validate_resolutions(resolutions: tuple[JsonValue, ...]) -> None:
    expected = {
        "event_id",
        "kind",
        "selected_statement_id",
        "superseded_statement_ids",
        "resolved_at",
    }
    for raw in resolutions:
        if not isinstance(raw, Mapping) or set(raw) != expected:
            raise ValueError("study-context resolution entries are corrupt")
        _text(raw.get("event_id"), "resolution event_id")
        kind = _kind(raw.get("kind"))
        if not kind.is_scalar:
            raise ValueError("study-context resolution kind is corrupt")
        selected = _text(
            raw.get("selected_statement_id"), "resolution selected_statement_id"
        )
        losers = raw.get("superseded_statement_ids")
        if not isinstance(losers, tuple):
            raise ValueError("study-context resolution losers are corrupt")
        decoded_losers = tuple(
            _text(item, "resolution superseded_statement_id") for item in losers
        )
        if (
            not decoded_losers
            or selected in decoded_losers
            or tuple(sorted(decoded_losers)) != decoded_losers
            or len(set(decoded_losers)) != len(decoded_losers)
        ):
            raise ValueError("study-context resolution losers are corrupt")
        _timestamp(raw.get("resolved_at"), "resolution resolved_at")


def _validate_commands(commands: Mapping[str, JsonValue]) -> None:
    for event_id, raw in commands.items():
        if (
            not isinstance(event_id, str)
            or not event_id
            or not isinstance(raw, Mapping)
            or set(raw) != {"command_fingerprint", "statement_id"}
        ):
            raise ValueError("study-context command entries are corrupt")
        fingerprint = raw.get("command_fingerprint")
        _text(raw.get("statement_id"), "command statement_id")
        if (
            not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or any(char not in "0123456789abcdef" for char in fingerprint)
        ):
            raise ValueError("study-context command fingerprint is corrupt")


def _kind(value: JsonValue | None) -> StudyStatementKind:
    try:
        return StudyStatementKind(_text(value, "statement kind"))
    except ValueError as error:
        raise ValueError("study-context statement kind is corrupt") from error


def _statement_value(
    kind: StudyStatementKind, raw: JsonValue | None
) -> str | date | int:
    value: str | date | int
    if kind is StudyStatementKind.DEADLINE:
        raw_text = _text(raw, "statement value")
        try:
            value = date.fromisoformat(raw_text)
        except ValueError as error:
            raise ValueError("study-context statement value is corrupt") from error
        if value.isoformat() != raw_text:
            raise ValueError("study-context statement value is corrupt")
    elif isinstance(raw, (str, int)) and not isinstance(raw, bool):
        value = raw
    else:
        raise ValueError("study-context statement value is corrupt")
    try:
        return StudyStatementInput(kind, value).value
    except (TypeError, ValueError) as error:
        raise ValueError("study-context statement value is corrupt") from error


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} is corrupt")
    return value


def _timestamp(value: JsonValue | None, name: str) -> datetime:
    try:
        result = datetime.fromisoformat(_text(value, name))
    except ValueError as error:
        raise ValueError(f"{name} is corrupt") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{name} is corrupt")
    return result
