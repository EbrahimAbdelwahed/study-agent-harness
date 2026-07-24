"""Pure replay reducers for the canonical per-course recall ledger."""

from __future__ import annotations

from collections.abc import Mapping

from study_agent.domain import (
    ArtifactRevisionStatus,
    DomainEvent,
    PrincipalKind,
    StudyArtifactKind,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.state import EventRegistry

from .contracts import (
    AppliedSchedule,
    ReviewHistoryEntry,
    ReviewRecord,
    SchedulingRequest,
    SchedulingResult,
    history_fingerprint,
    result_fingerprint,
)
from .events import (
    RECALL_SCHEMA_VERSION,
    REVIEW_RECORDED,
    SCHEDULE_APPLIED,
    ReviewRecorded,
    ScheduleApplied,
    decode_review_recorded,
    decode_schedule_applied,
)


def reduce_review_recorded(
    state: JsonObject, event: DomainEvent, payload: ReviewRecorded
) -> Mapping[str, JsonValue]:
    _require_scope(state, event)
    if event.actor.kind is not PrincipalKind.HUMAN:
        raise ValueError("reviews require HUMAN authority")
    recall = _parts(state)
    record = payload.review
    _accepted_flashcard(state, str(record.revision_id))
    if str(record.review_id) in recall["reviews"]:
        raise ValueError("review identity already exists")
    enrollment = recall["enrollments"].get(str(record.revision_id))
    if enrollment is None:
        raise ValueError("review requires enrollment")
    review_count = sum(
        1
        for value in recall["reviews"].values()
        if _mapping(value).get("revision_id") == str(record.revision_id)
    )
    applied_count = sum(
        1
        for value in recall["schedules"].values()
        if _mapping(value).get("revision_id") == str(record.revision_id)
        and _mapping(value).get("trigger") == "review"
    )
    if review_count != applied_count:
        raise ValueError("a prior review is awaiting its matching schedule")
    # Persist immutable event evidence, including its trusted occurrence sequence.
    reviews = dict(recall["reviews"])
    reviews[str(record.review_id)] = {
        **record.to_json(),
        "course_sequence": event.course_sequence,
        "session_id": str(event.session_id),
    }
    commands = dict(recall["commands"])
    command_id = str(event.event_id)
    if command_id in commands:
        raise ValueError("recall command already exists")
    commands[command_id] = {
        "command_fingerprint": record.command_fingerprint,
        "result_id": str(record.review_id),
    }
    return _replace(state, recall["enrollments"], reviews, recall["schedules"], commands)


def reduce_schedule_applied(
    state: JsonObject, event: DomainEvent, payload: ScheduleApplied
) -> Mapping[str, JsonValue]:
    _require_scope(state, event)
    if event.actor.kind is not PrincipalKind.SERVICE:
        raise ValueError("schedules require SERVICE authority")
    recall = _parts(state)
    schedule = payload.schedule
    revision = str(schedule.revision_id)
    _accepted_flashcard(state, revision)
    if str(schedule.decision_id) in recall["schedules"]:
        raise ValueError("schedule decision identity already exists")
    if schedule.policy.fingerprint != schedule.policy_fingerprint:
        raise ValueError("policy fingerprint does not match exact configuration")
    if schedule.trigger == "enrollment":
        if revision in recall["enrollments"]:
            raise ValueError("duplicate enrollment")
        if schedule.review_id is not None:
            raise ValueError("enrollment cannot bind review")
        expected_history = history_fingerprint(schedule.revision_id, schedule.enrollment_at, ())
        if schedule.history_fingerprint != expected_history:
            raise ValueError("initial schedule history fingerprint is invalid")
        expected_decision = _enrollment_decision_id(event, schedule)
        if str(schedule.decision_id) != str(expected_decision):
            raise ValueError("enrollment decision identity is invalid")
        history: tuple[ReviewHistoryEntry, ...] = ()
        enrollment = schedule
    else:
        if schedule.review_id is None:
            raise ValueError("review schedule requires review id")
        enrollment_raw = recall["enrollments"].get(revision)
        if enrollment_raw is None:
            raise ValueError("review schedule requires enrollment")
        enrollment = _schedule_from_json(enrollment_raw)
        review_raw = recall["reviews"].get(str(schedule.review_id))
        if review_raw is None:
            raise ValueError("review schedule requires its recorded review")
        review = _review_from_json(review_raw)
        if review.revision_id != schedule.revision_id:
            raise ValueError("review schedule binds another revision")
        pending = _pending_reviews(recall, revision)
        if pending != (str(schedule.review_id),):
            raise ValueError("schedule must apply the sole newest pending review")
        history = tuple(
            _review_from_json(value).history_entry()
            for value in sorted(
                (
                    v
                    for v in recall["reviews"].values()
                    if _mapping(v).get("revision_id") == revision
                ),
                key=lambda v: _int(_mapping(v).get("course_sequence")),
            )
        )
        if history[-1].review_id != schedule.review_id:
            raise ValueError("schedule review is out of order")
        expected_history = history_fingerprint(
            schedule.revision_id, enrollment.enrollment_at, history
        )
        if schedule.history_fingerprint != expected_history:
            raise ValueError("schedule history fingerprint is invalid")
        expected_decision = _review_decision_id(event, schedule)
        if str(schedule.decision_id) != str(expected_decision):
            raise ValueError("review decision identity is invalid")

    request = SchedulingRequest(
        schedule.revision_id, schedule.enrollment_at, history, schedule.policy
    )
    receipt = SchedulingResult(
        schedule.due_at,
        schedule.policy_id,
        schedule.policy_version,
        schedule.policy_fingerprint,
        schedule.implementation_id,
        schedule.implementation_version,
        schedule.history_fingerprint,
        schedule.result_fingerprint,
    )
    expected_result = result_fingerprint(request, receipt)
    if schedule.result_fingerprint != expected_result:
        raise ValueError("schedule result fingerprint is invalid")
    schedules = dict(recall["schedules"])
    schedules[str(schedule.decision_id)] = {
        **schedule.to_json(),
        "course_sequence": event.course_sequence,
        "session_id": str(event.session_id),
    }
    enrollments = dict(recall["enrollments"])
    if schedule.trigger == "enrollment":
        enrollments[revision] = schedule.to_json()
    commands = dict(recall["commands"])
    command_id = str(event.event_id)
    if command_id in commands:
        raise ValueError("recall command already exists")
    commands[command_id] = {
        "command_fingerprint": schedule.command_fingerprint,
        "result_id": str(schedule.decision_id),
    }
    return _replace(state, enrollments, recall["reviews"], schedules, commands)


def register_recall_events(registry: EventRegistry) -> None:
    registry.register_event(
        REVIEW_RECORDED, RECALL_SCHEMA_VERSION, decode_review_recorded, reduce_review_recorded
    )
    registry.register_event(
        SCHEDULE_APPLIED, RECALL_SCHEMA_VERSION, decode_schedule_applied, reduce_schedule_applied
    )


def _parts(state: JsonObject) -> dict[str, Mapping[str, JsonValue]]:
    raw = state.get("recall", {})
    if not isinstance(raw, Mapping):
        raise ValueError("recall projection is corrupt")
    expected = {"enrollments", "reviews", "schedules", "commands"}
    if raw and set(raw) != expected:
        raise ValueError("recall projection fields are corrupt")
    parts = {key: _mapping(raw.get(key, {})) for key in expected}
    _validate_prior(parts)
    return parts


def _validate_prior(parts: Mapping[str, Mapping[str, JsonValue]]) -> None:
    """Fail closed when a discardable recall projection was tampered with."""
    for key, raw in parts["reviews"].items():
        if not isinstance(key, str) or not isinstance(raw, Mapping):
            raise ValueError("recall review projection is corrupt")
        if raw.get("review_id") != key or type(raw.get("course_sequence")) is not int:
            raise ValueError("recall review identity or sequence is corrupt")
        if raw.get("session_id") is None:
            raise ValueError("recall review session is corrupt")
        _review_from_json(raw)
    for key, raw in parts["schedules"].items():
        if not isinstance(key, str) or not isinstance(raw, Mapping):
            raise ValueError("recall schedule projection is corrupt")
        if raw.get("decision_id") != key or type(raw.get("course_sequence")) is not int:
            raise ValueError("recall schedule identity or sequence is corrupt")
        if raw.get("session_id") is None:
            raise ValueError("recall schedule session is corrupt")
        _schedule_from_json(raw)
    for key, raw in parts["enrollments"].items():
        if not isinstance(key, str) or not isinstance(raw, Mapping):
            raise ValueError("recall enrollment projection is corrupt")
        if raw.get("revision_id") != key:
            raise ValueError("recall enrollment identity is corrupt")
        _schedule_from_json(raw)
    for key, raw in parts["commands"].items():
        if not isinstance(key, str) or not isinstance(raw, Mapping):
            raise ValueError("recall command projection is corrupt")
        if set(raw) != {"command_fingerprint", "result_id"}:
            raise ValueError("recall command projection fields are corrupt")
        fingerprint = raw.get("command_fingerprint")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("recall command fingerprint is corrupt")


def _replace(
    state: JsonObject,
    enrollments: Mapping[str, JsonValue],
    reviews: Mapping[str, JsonValue],
    schedules: Mapping[str, JsonValue],
    commands: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    return {
        **state,
        "recall": {
            "enrollments": enrollments,
            "reviews": reviews,
            "schedules": schedules,
            "commands": commands,
        },
    }


def _require_scope(state: JsonObject, event: DomainEvent) -> None:
    if "course" not in state or event.session_id is None:
        raise ValueError("recall requires an existing course/session")
    sessions = _mapping(state.get("sessions"))
    session = _mapping(sessions.get(str(event.session_id)))
    if session.get("course_id") != str(event.course_id):
        raise ValueError("recall session does not belong to course")


def _accepted_flashcard(state: JsonObject, revision_id: str) -> None:
    artifacts = _mapping(state.get("study_artifacts"))
    revisions = _mapping(artifacts.get("revisions"))
    revision = _mapping(revisions.get(revision_id))
    if (
        revision.get("status") != ArtifactRevisionStatus.ACCEPTED.value
        or revision.get("kind") != StudyArtifactKind.FLASHCARD.value
    ):
        raise ValueError("recall target must be an accepted flashcard revision")


def _pending_reviews(
    recall: Mapping[str, Mapping[str, JsonValue]], revision: str
) -> tuple[str, ...]:
    reviewed = {
        str(_mapping(v).get("review_id"))
        for v in recall["reviews"].values()
        if _mapping(v).get("revision_id") == revision
    }
    applied = {
        str(_mapping(v).get("review_id"))
        for v in recall["schedules"].values()
        if _mapping(v).get("revision_id") == revision and _mapping(v).get("trigger") == "review"
    }
    return tuple(sorted(reviewed - applied))


def _enrollment_decision_id(event: DomainEvent, schedule: AppliedSchedule) -> object:
    from study_agent.domain import enrollment_decision_id_for

    if event.session_id is None:
        raise ValueError("recall requires a session")
    return enrollment_decision_id_for(
        event.course_id, event.session_id, schedule.revision_id, schedule.idempotency_key
    )


def _review_decision_id(event: DomainEvent, schedule: AppliedSchedule) -> object:
    from study_agent.domain import review_decision_id_for

    if event.session_id is None or schedule.review_id is None:
        raise ValueError("review schedule requires session and review")
    return review_decision_id_for(
        event.course_id, event.session_id, schedule.revision_id, schedule.review_id
    )


def _mapping(value: object) -> dict[str, JsonValue] | Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError("recall projection value is corrupt")
    return value


def _int(value: object) -> int:
    if type(value) is not int:
        raise ValueError("recall sequence is corrupt")
    return value


def _review_from_json(value: JsonValue) -> ReviewRecord:
    from .view import review_record_from_json

    return review_record_from_json(_mapping(value))


def _schedule_from_json(value: JsonValue) -> AppliedSchedule:
    from .view import schedule_from_json

    return schedule_from_json(_mapping(value))


__all__ = ["reduce_review_recorded", "reduce_schedule_applied", "register_recall_events"]
