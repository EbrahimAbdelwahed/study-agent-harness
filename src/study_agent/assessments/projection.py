"""Pure reducers for canonical assessment ledger state."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256

from study_agent.artifacts.content import AssessmentItemContent, StudyArtifactEnvelope
from study_agent.domain import (
    ArtifactRevisionStatus,
    AssessmentFormat,
    DomainEvent,
    GradeLifecycle,
    PrincipalKind,
    StudyArtifactKind,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.state import EventRegistry, canonical_json_bytes

from .contracts import FreeResponse, MultipleChoiceResponse, SingleChoiceResponse
from .events import (
    ASSESSMENT_SCHEMA_VERSION,
    ATTEMPT_RECORDED,
    GRADE_CONTESTED,
    GRADE_RECORDED,
    ITEM_PRESENTED,
    AttemptRecorded,
    GradeContested,
    GradeRecorded,
    ItemPresented,
    decode_attempt_recorded,
    decode_grade_contested,
    decode_grade_recorded,
    decode_item_presented,
)


def reduce_item_presented(
    state: JsonObject, event: DomainEvent, payload: ItemPresented
) -> Mapping[str, JsonValue]:
    _require_session(state, event)
    presentations, attempts, grades, contests, commands = _parts(state, event)
    _new_command(commands, event, str(payload.presentation_id))
    if str(payload.presentation_id) in presentations:
        raise ValueError("assessment presentation already exists")
    revision = _artifact_revision(state, event, str(payload.revision_id))
    if revision.get("status") != ArtifactRevisionStatus.ACCEPTED.value:
        raise ValueError("only an accepted assessment item can be presented")
    if revision.get("kind") != StudyArtifactKind.ASSESSMENT_ITEM.value:
        raise ValueError("presentation revision is not an assessment item")
    content_text = _text(revision, "content")
    content_bytes = content_text.encode()
    if sha256(content_bytes).hexdigest() != payload.content_fingerprint:
        raise ValueError("presented assessment content fingerprint drifted")
    envelope = StudyArtifactEnvelope.from_bytes(content_bytes)
    if not isinstance(envelope.content, AssessmentItemContent):
        raise ValueError("assessment revision content is invalid")
    content = envelope.content
    _validate_item_encoding(content)
    if (payload.format, payload.prompt, payload.options) != (
        content.format,
        content.prompt,
        content.options,
    ):
        raise ValueError("learner delivery snapshot does not match accepted content")
    record: JsonObject = {
        "presentation_id": str(payload.presentation_id),
        "course_id": str(event.course_id),
        "session_id": str(event.session_id),
        "revision_id": str(payload.revision_id),
        "content_fingerprint": payload.content_fingerprint,
        "content": content_text,
        "presented_at": _timestamp(event.occurred_at),
    }
    return _replace(
        state,
        {**presentations, str(payload.presentation_id): record},
        attempts,
        grades,
        contests,
        _with_command(commands, event, payload.command_fingerprint, str(payload.presentation_id)),
    )


def reduce_attempt_recorded(
    state: JsonObject, event: DomainEvent, payload: AttemptRecorded
) -> Mapping[str, JsonValue]:
    _require_session(state, event)
    presentations, attempts, grades, contests, commands = _parts(state, event)
    _new_command(commands, event, str(payload.attempt_id))
    if str(payload.attempt_id) in attempts:
        raise ValueError("assessment attempt already exists")
    presentation = _owned(presentations.get(str(payload.presentation_id)), event, "presentation")
    content = _assessment_content(presentation)
    _validate_response(content, payload.response)
    from .contracts import response_to_json

    record: JsonObject = {
        "attempt_id": str(payload.attempt_id),
        "course_id": str(event.course_id),
        "session_id": str(event.session_id),
        "presentation_id": str(payload.presentation_id),
        "response": response_to_json(payload.response),
        "response_fingerprint": payload.response_fingerprint,
        "latency_ms": payload.latency_ms,
        "recorded_at": _timestamp(event.occurred_at),
    }
    return _replace(
        state,
        presentations,
        {**attempts, str(payload.attempt_id): record},
        grades,
        contests,
        _with_command(commands, event, payload.command_fingerprint, str(payload.attempt_id)),
    )


def reduce_grade_recorded(
    state: JsonObject, event: DomainEvent, payload: GradeRecorded
) -> Mapping[str, JsonValue]:
    _require_session(state, event)
    presentations, attempts, grades, contests, commands = _parts(state, event)
    _new_command(commands, event, str(payload.grade_id))
    if str(payload.grade_id) in grades:
        raise ValueError("assessment grade already exists")
    attempt = _owned(attempts.get(str(payload.attempt_id)), event, "attempt")
    presentation = _owned(
        presentations.get(_text(attempt, "presentation_id")), event, "presentation"
    )
    content = _assessment_content(presentation)
    expected_criteria = content.evaluation_criteria
    actual_criteria = tuple(item.criterion for item in payload.criterion_results)
    if actual_criteria != expected_criteria:
        raise ValueError("grade criterion results must match the immutable rubric")
    rubric_fingerprint = sha256(
        canonical_json_bytes({"evaluation_criteria": expected_criteria})
    ).hexdigest()
    if payload.provenance.rubric_fingerprint != rubric_fingerprint:
        raise ValueError("grade provenance does not bind the immutable rubric")
    updated_grades = dict(grades)
    predecessor_id = (
        str(payload.supersedes_grade_id) if payload.supersedes_grade_id is not None else None
    )
    active = tuple(
        key
        for key, value in grades.items()
        if isinstance(value, Mapping)
        and value.get("attempt_id") == str(payload.attempt_id)
        and value.get("lifecycle") == GradeLifecycle.ACTIVE.value
    )
    if predecessor_id is None:
        if active:
            raise ValueError("a later grade must supersede the active predecessor")
    elif active != (predecessor_id,):
        raise ValueError("supersession must name the active grade for the same attempt")
    if predecessor_id is not None:
        predecessor = dict(_owned(grades.get(predecessor_id), event, "grade predecessor"))
        if predecessor.get("attempt_id") != str(payload.attempt_id):
            raise ValueError("a grade cannot supersede another attempt's grade")
        predecessor["lifecycle"] = GradeLifecycle.SUPERSEDED.value
        updated_grades[predecessor_id] = predecessor
    from .events import _criterion_json, _provenance_json

    updated_grades[str(payload.grade_id)] = {
        "grade_id": str(payload.grade_id),
        "course_id": str(event.course_id),
        "session_id": str(event.session_id),
        "attempt_id": str(payload.attempt_id),
        "status": payload.status.value,
        "criterion_results": tuple(_criterion_json(item) for item in payload.criterion_results),
        "provenance": _provenance_json(payload.provenance),
        "lifecycle": GradeLifecycle.ACTIVE.value,
        "supersedes_grade_id": predecessor_id,
        "recorded_at": _timestamp(event.occurred_at),
    }
    return _replace(
        state,
        presentations,
        attempts,
        updated_grades,
        contests,
        _with_command(commands, event, payload.command_fingerprint, str(payload.grade_id)),
    )


def reduce_grade_contested(
    state: JsonObject, event: DomainEvent, payload: GradeContested
) -> Mapping[str, JsonValue]:
    _require_session(state, event)
    presentations, attempts, grades, contests, commands = _parts(state, event)
    _new_command(commands, event, str(payload.grade_id))
    _owned(grades.get(str(payload.grade_id)), event, "contested grade")
    contest: JsonObject = {
        "grade_id": str(payload.grade_id),
        "course_id": str(event.course_id),
        "session_id": str(event.session_id),
        "reason": payload.reason,
        "contested_at": _timestamp(event.occurred_at),
    }
    return _replace(
        state,
        presentations,
        attempts,
        grades,
        (*contests, contest),
        _with_command(commands, event, payload.command_fingerprint, str(payload.grade_id)),
    )


def register_assessment_events(registry: EventRegistry) -> None:
    registry.register_event(
        ITEM_PRESENTED,
        ASSESSMENT_SCHEMA_VERSION,
        decode_item_presented,
        reduce_item_presented,
    )
    registry.register_event(
        ATTEMPT_RECORDED,
        ASSESSMENT_SCHEMA_VERSION,
        decode_attempt_recorded,
        reduce_attempt_recorded,
    )
    registry.register_event(
        GRADE_RECORDED,
        ASSESSMENT_SCHEMA_VERSION,
        decode_grade_recorded,
        reduce_grade_recorded,
    )
    registry.register_event(
        GRADE_CONTESTED,
        ASSESSMENT_SCHEMA_VERSION,
        decode_grade_contested,
        reduce_grade_contested,
    )


def _parts(
    state: JsonObject, event: DomainEvent
) -> tuple[
    Mapping[str, JsonValue],
    Mapping[str, JsonValue],
    Mapping[str, JsonValue],
    tuple[JsonValue, ...],
    Mapping[str, JsonValue],
]:
    raw = state.get("assessments", {})
    if not isinstance(raw, Mapping) or (
        raw and set(raw) != {"presentations", "attempts", "grades", "contests", "commands"}
    ):
        raise ValueError("assessment projection fields are corrupt")
    presentations = _mapping(raw.get("presentations", {}), "presentations")
    attempts = _mapping(raw.get("attempts", {}), "attempts")
    grades = _mapping(raw.get("grades", {}), "grades")
    contests = raw.get("contests", ())
    commands = _mapping(raw.get("commands", {}), "assessment commands")
    if not isinstance(contests, tuple):
        raise ValueError("assessment contest history is corrupt")
    _validate_existing(event, presentations, attempts, grades, contests, commands)
    return presentations, attempts, grades, contests, commands


def _replace(
    state: JsonObject,
    presentations: Mapping[str, JsonValue],
    attempts: Mapping[str, JsonValue],
    grades: Mapping[str, JsonValue],
    contests: tuple[JsonValue, ...],
    commands: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    return {
        **state,
        "assessments": {
            "presentations": presentations,
            "attempts": attempts,
            "grades": grades,
            "contests": contests,
            "commands": commands,
        },
    }


def _validate_existing(
    event: DomainEvent,
    presentations: Mapping[str, JsonValue],
    attempts: Mapping[str, JsonValue],
    grades: Mapping[str, JsonValue],
    contests: tuple[JsonValue, ...],
    commands: Mapping[str, JsonValue],
) -> None:
    for values, id_field, name in (
        (presentations, "presentation_id", "presentation"),
        (attempts, "attempt_id", "attempt"),
        (grades, "grade_id", "grade"),
    ):
        for key, raw in values.items():
            record = _valid_record(raw, event, name)
            if record.get(id_field) != key:
                raise ValueError(f"assessment {name} identity is corrupt")
    for raw in contests:
        _valid_record(raw, event, "contest")
    for raw in commands.values():
        record = _mapping(raw, "assessment command")
        if set(record) != {"command_fingerprint", "result_id"}:
            raise ValueError("assessment command receipt is corrupt")


def _require_session(state: JsonObject, event: DomainEvent) -> None:
    if event.session_id is None or event.actor.kind is PrincipalKind.MODEL:
        raise ValueError("assessment events require trusted session authority")
    sessions = _mapping(state.get("sessions"), "sessions")
    session = sessions.get(str(event.session_id))
    if not isinstance(session, Mapping) or session.get("course_id") != str(event.course_id):
        raise ValueError("assessment event session was not found in its course")


def _artifact_revision(
    state: JsonObject, event: DomainEvent, revision_id: str
) -> Mapping[str, JsonValue]:
    artifacts = _mapping(state.get("study_artifacts"), "study_artifacts")
    revisions = _mapping(artifacts.get("revisions"), "artifact revisions")
    revision = _mapping(revisions.get(revision_id), "assessment artifact revision")
    batches = _mapping(artifacts.get("batches"), "artifact batches")
    batch = _mapping(batches.get(_text(revision, "batch_id")), "artifact batch")
    if batch.get("course_id") != str(event.course_id) or batch.get("session_id") != str(
        event.session_id
    ):
        raise ValueError("assessment artifact belongs to another course or session")
    return revision


def _assessment_content(presentation: Mapping[str, JsonValue]) -> AssessmentItemContent:
    envelope = StudyArtifactEnvelope.from_bytes(_text(presentation, "content").encode())
    if not isinstance(envelope.content, AssessmentItemContent):
        raise ValueError("presentation content is not an assessment item")
    return envelope.content


def _validate_item_encoding(content: AssessmentItemContent) -> None:
    if content.format is AssessmentFormat.SINGLE_CHOICE:
        if content.expected_response not in content.options:
            raise ValueError("single-choice expected response must name one listed option")
    elif content.format is AssessmentFormat.MULTIPLE_CHOICE:
        try:
            selected = json.loads(content.expected_response)
        except json.JSONDecodeError as error:
            raise ValueError("multiple-choice expected response must be canonical JSON") from error
        if (
            not isinstance(selected, list)
            or not selected
            or any(not isinstance(item, str) for item in selected)
            or len(selected) != len(set(selected))
            or any(item not in content.options for item in selected)
        ):
            raise ValueError("multiple-choice expected response must name unique listed options")
        ordered = tuple(item for item in content.options if item in selected)
        canonical = json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
        if canonical != content.expected_response:
            raise ValueError("multiple-choice expected response must use artifact option order")


def _validate_response(content: AssessmentItemContent, response: object) -> None:
    if content.format is AssessmentFormat.FREE_RESPONSE:
        if not isinstance(response, FreeResponse):
            raise ValueError("free-response item requires free text")
        return
    if content.format is AssessmentFormat.SINGLE_CHOICE:
        if (
            not isinstance(response, SingleChoiceResponse)
            or response.selected_option not in content.options
        ):
            raise ValueError("single-choice response must name exactly one listed option")
        return
    if not isinstance(response, MultipleChoiceResponse):
        raise ValueError("multiple-choice item requires a canonical selection array")
    if any(item not in content.options for item in response.selected_options):
        raise ValueError("multiple-choice response contains an unknown option")
    expected_order = tuple(item for item in content.options if item in response.selected_options)
    if response.selected_options != expected_order:
        raise ValueError("multiple-choice response must follow artifact option order")


def _new_command(commands: Mapping[str, JsonValue], event: DomainEvent, result_id: str) -> None:
    if str(event.event_id) in commands:
        raise ValueError("assessment command already exists")
    if not result_id:
        raise ValueError("assessment result identity is empty")


def _with_command(
    commands: Mapping[str, JsonValue],
    event: DomainEvent,
    command_fingerprint: str,
    result_id: str,
) -> Mapping[str, JsonValue]:
    return {
        **commands,
        str(event.event_id): {
            "command_fingerprint": command_fingerprint,
            "result_id": result_id,
        },
    }


def _owned(value: JsonValue | None, event: DomainEvent, name: str) -> Mapping[str, JsonValue]:
    record = _mapping(value, name)
    if record.get("course_id") != str(event.course_id) or record.get("session_id") != str(
        event.session_id
    ):
        raise ValueError(f"assessment {name} belongs to another course or session")
    return record


def _valid_record(
    value: JsonValue | None, event: DomainEvent, name: str
) -> Mapping[str, JsonValue]:
    record = _mapping(value, name)
    if record.get("course_id") != str(event.course_id):
        raise ValueError(f"assessment {name} belongs to another course")
    session_id = record.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError(f"assessment {name} session identity is corrupt")
    return record


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _text(value: Mapping[str, JsonValue], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be text")
    return raw


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "reduce_attempt_recorded",
    "reduce_grade_contested",
    "reduce_grade_recorded",
    "reduce_item_presented",
    "register_assessment_events",
]
