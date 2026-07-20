"""Strict v1 codecs for canonical progressive study context events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import cast

from study_agent.domain import (
    Actor,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    InteractionId,
    PrincipalKind,
    SessionId,
    StatementId,
    StudyStatementInput,
    StudyStatementKind,
    statement_id_for,
    study_context_event_id_for,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.state import canonical_json_bytes

STATEMENT_RECORDED = "study_context.statement_recorded"
STATEMENT_RETRACTED = "study_context.statement_retracted"
CONFLICT_RESOLVED = "study_context.conflict_resolved"
STUDY_CONTEXT_SCHEMA_VERSION = 1
STUDY_CONTEXT_EVENT_TYPES = frozenset(
    {STATEMENT_RECORDED, STATEMENT_RETRACTED, CONFLICT_RESOLVED}
)

_COMMAND_KEYS = frozenset({"idempotency_key", "command_fingerprint", "session_id"})
_RECORDED_KEYS = _COMMAND_KEYS | frozenset(
    {"statement_id", "origin_interaction_id", "kind", "value"}
)
_RETRACTED_KEYS = _COMMAND_KEYS | frozenset({"statement_id"})
_RESOLVED_KEYS = _COMMAND_KEYS | frozenset(
    {"kind", "selected_statement_id", "superseded_statement_ids"}
)


@dataclass(frozen=True, slots=True)
class StatementRecorded:
    statement_id: StatementId
    origin_interaction_id: InteractionId
    statement: StudyStatementInput
    idempotency_key: str
    command_fingerprint: str


@dataclass(frozen=True, slots=True)
class StatementRetracted:
    statement_id: StatementId
    idempotency_key: str
    command_fingerprint: str


@dataclass(frozen=True, slots=True)
class ConflictResolved:
    kind: StudyStatementKind
    selected_statement_id: StatementId
    superseded_statement_ids: tuple[StatementId, ...]
    idempotency_key: str
    command_fingerprint: str


def statement_recorded_payload(
    statement_id: StatementId,
    origin_interaction_id: InteractionId,
    statement: StudyStatementInput,
    session_id: SessionId,
    idempotency_key: str,
) -> JsonObject:
    fingerprint = record_command_fingerprint(statement, origin_interaction_id)
    return {
        "statement_id": str(statement_id),
        "session_id": str(session_id),
        "origin_interaction_id": str(origin_interaction_id),
        "kind": statement.kind.value,
        "value": statement_value_manifest(statement),
        "idempotency_key": idempotency_key,
        "command_fingerprint": fingerprint,
    }


def statement_retracted_payload(
    statement_id: StatementId, session_id: SessionId, idempotency_key: str
) -> JsonObject:
    return {
        "statement_id": str(statement_id),
        "session_id": str(session_id),
        "idempotency_key": idempotency_key,
        "command_fingerprint": retract_command_fingerprint(statement_id),
    }


def conflict_resolved_payload(
    kind: StudyStatementKind,
    selected_statement_id: StatementId,
    superseded_statement_ids: tuple[StatementId, ...],
    session_id: SessionId,
    idempotency_key: str,
) -> JsonObject:
    return {
        "kind": kind.value,
        "selected_statement_id": str(selected_statement_id),
        "superseded_statement_ids": tuple(map(str, superseded_statement_ids)),
        "session_id": str(session_id),
        "idempotency_key": idempotency_key,
        "command_fingerprint": resolve_command_fingerprint(kind, selected_statement_id),
    }


def decode_statement_recorded(event: DomainEvent) -> StatementRecorded:
    payload = _envelope(event, STATEMENT_RECORDED, _RECORDED_KEYS, "record")
    statement = _decode_statement(payload)
    origin = InteractionId(_text(payload.get("origin_interaction_id"), "origin_interaction_id"))
    command_id = study_context_event_id_for(
        event.course_id, cast(SessionId, event.session_id), _key(payload), "record"
    )
    if event.event_id != command_id:
        raise ValueError("record event id does not match command identity")
    statement_id = StatementId(_text(payload.get("statement_id"), "statement_id"))
    if statement_id != statement_id_for(command_id):
        raise ValueError("statement id does not match record command")
    fingerprint = _fingerprint(payload)
    if fingerprint != record_command_fingerprint(statement, origin):
        raise ValueError("record command fingerprint mismatch")
    return StatementRecorded(statement_id, origin, statement, _key(payload), fingerprint)


def decode_statement_retracted(event: DomainEvent) -> StatementRetracted:
    payload = _envelope(event, STATEMENT_RETRACTED, _RETRACTED_KEYS, "retract")
    statement_id = StatementId(_text(payload.get("statement_id"), "statement_id"))
    fingerprint = _fingerprint(payload)
    if fingerprint != retract_command_fingerprint(statement_id):
        raise ValueError("retract command fingerprint mismatch")
    return StatementRetracted(statement_id, _key(payload), fingerprint)


def decode_conflict_resolved(event: DomainEvent) -> ConflictResolved:
    payload = _envelope(event, CONFLICT_RESOLVED, _RESOLVED_KEYS, "resolve")
    kind = _kind(payload.get("kind"))
    if not kind.is_scalar:
        raise ValueError("only scalar statement kinds can be resolved")
    selected = StatementId(
        _text(payload.get("selected_statement_id"), "selected_statement_id")
    )
    raw_superseded = payload.get("superseded_statement_ids")
    if not isinstance(raw_superseded, tuple):
        raise ValueError("superseded_statement_ids must be an array")
    superseded = tuple(
        StatementId(_text(item, f"superseded_statement_ids[{index}]"))
        for index, item in enumerate(raw_superseded)
    )
    if not superseded or selected in superseded or len(set(superseded)) != len(superseded):
        raise ValueError("resolution must contain unique superseded losers")
    if tuple(sorted(superseded, key=str)) != superseded:
        raise ValueError("superseded statement ids must be canonically ordered")
    fingerprint = _fingerprint(payload)
    if fingerprint != resolve_command_fingerprint(kind, selected):
        raise ValueError("resolve command fingerprint mismatch")
    return ConflictResolved(kind, selected, superseded, _key(payload), fingerprint)


def decode_study_context_event(event: DomainEvent) -> object:
    decoders = {
        STATEMENT_RECORDED: decode_statement_recorded,
        STATEMENT_RETRACTED: decode_statement_retracted,
        CONFLICT_RESOLVED: decode_conflict_resolved,
    }
    try:
        return decoders[event.event_type](event)
    except KeyError as error:
        raise ValueError("event is not a study-context event") from error


def record_command_fingerprint(
    statement: StudyStatementInput, origin_interaction_id: InteractionId
) -> str:
    return _sha(
        {
            "origin_interaction_id": str(origin_interaction_id),
            "kind": statement.kind.value,
            "value": statement_value_manifest(statement),
        }
    )


def retract_command_fingerprint(statement_id: StatementId) -> str:
    return _sha({"statement_id": str(statement_id)})


def resolve_command_fingerprint(
    kind: StudyStatementKind, selected_statement_id: StatementId
) -> str:
    return _sha({"kind": kind.value, "selected_statement_id": str(selected_statement_id)})


def statement_value_manifest(statement: StudyStatementInput) -> JsonValue:
    value = statement.value
    return value.isoformat() if isinstance(value, date) else value


def _decode_statement(payload: JsonObject) -> StudyStatementInput:
    kind = _kind(payload.get("kind"))
    raw = payload.get("value")
    if kind is StudyStatementKind.DEADLINE:
        text = _text(raw, "value")
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError as error:
            raise ValueError("value must be a canonical ISO calendar date") from error
        if parsed_date.isoformat() != text:
            raise ValueError("value must be a canonical ISO calendar date")
        value: str | date | int = parsed_date
    else:
        value = cast(str | int, raw)
    return StudyStatementInput(kind, value)


def _envelope(
    event: DomainEvent, event_type: str, keys: frozenset[str], command_kind: str
) -> JsonObject:
    if event.event_type != event_type or event.schema_version != STUDY_CONTEXT_SCHEMA_VERSION:
        raise ValueError(f"event envelope does not match {event_type}@1")
    if set(event.payload) != keys:
        raise ValueError("study-context payload fields mismatch")
    if event.session_id is None:
        raise ValueError("study-context events must be session-scoped")
    if not isinstance(event.session_id, SessionId):
        raise ValueError("study-context event session envelope is not typed")
    if not isinstance(event.course_id, CourseId) or event.course_sequence < 2:
        raise ValueError("study-context event course envelope is invalid")
    if _text(event.payload.get("session_id"), "session_id") != str(event.session_id):
        raise ValueError("payload session id must match event envelope")
    if not isinstance(event.event_id, EventId) or not isinstance(
        event.correlation_id, CorrelationId
    ):
        raise ValueError("study-context event identity envelope is not typed")
    if event.causation_id is not None and not isinstance(event.causation_id, EventId):
        raise ValueError("study-context event causation envelope is not typed")
    if (
        not isinstance(event.actor, Actor)
        or not isinstance(event.actor.kind, PrincipalKind)
        or event.actor.kind not in (PrincipalKind.HUMAN, PrincipalKind.SERVICE)
    ):
        raise ValueError("study-context writes require a trusted human or service actor")
    expected = study_context_event_id_for(
        event.course_id, event.session_id, _key(event.payload), command_kind
    )
    if event.event_id != expected:
        raise ValueError("study-context event id does not match command identity")
    return event.payload


def _kind(value: JsonValue | None) -> StudyStatementKind:
    try:
        return StudyStatementKind(_text(value, "kind"))
    except ValueError as error:
        raise ValueError("kind is not a supported study statement kind") from error


def _key(payload: JsonObject) -> str:
    return _text(payload.get("idempotency_key"), "idempotency_key")


def _fingerprint(payload: JsonObject) -> str:
    value = _text(payload.get("command_fingerprint"), "command_fingerprint")
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("command_fingerprint must be a lowercase SHA-256 digest")
    return value


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


def _sha(value: JsonObject) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()
