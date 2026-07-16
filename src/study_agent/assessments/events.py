"""Exact schema-v1 codecs for canonical assessment events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from study_agent.domain import (
    ArtifactRevisionId,
    AssessmentFormat,
    AttemptId,
    CourseId,
    DomainEvent,
    GradeId,
    GradeStatus,
    PresentationId,
    PrincipalKind,
    RunId,
    SessionId,
    assessment_event_id_for,
    attempt_id_for,
    grade_id_for,
    presentation_id_for,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.state import canonical_json_bytes

from .contracts import (
    CanonicalResponse,
    CriterionResult,
    DeterministicGradeProvenance,
    FreeResponse,
    GradeProvenance,
    MultipleChoiceResponse,
    SingleChoiceResponse,
    ValidatorReceipt,
    VerifiedCapabilityGradeProvenance,
    response_fingerprint,
    response_to_json,
)

ITEM_PRESENTED = "assessment.item_presented"
ATTEMPT_RECORDED = "assessment.attempt_recorded"
GRADE_RECORDED = "assessment.grade_recorded"
GRADE_CONTESTED = "assessment.grade_contested"
ASSESSMENT_SCHEMA_VERSION = 1
ASSESSMENT_EVENT_TYPES = frozenset(
    {ITEM_PRESENTED, ATTEMPT_RECORDED, GRADE_RECORDED, GRADE_CONTESTED}
)


@dataclass(frozen=True, slots=True)
class ItemPresented:
    presentation_id: PresentationId
    revision_id: ArtifactRevisionId
    content_fingerprint: str
    format: AssessmentFormat
    prompt: str
    options: tuple[str, ...]
    idempotency_key: str
    command_fingerprint: str


@dataclass(frozen=True, slots=True)
class AttemptRecorded:
    attempt_id: AttemptId
    presentation_id: PresentationId
    response: CanonicalResponse
    response_fingerprint: str
    latency_ms: int | None
    idempotency_key: str
    command_fingerprint: str


@dataclass(frozen=True, slots=True)
class GradeRecorded:
    grade_id: GradeId
    attempt_id: AttemptId
    status: GradeStatus
    criterion_results: tuple[CriterionResult, ...]
    provenance: GradeProvenance
    supersedes_grade_id: GradeId | None
    idempotency_key: str
    command_fingerprint: str


@dataclass(frozen=True, slots=True)
class GradeContested:
    grade_id: GradeId
    reason: str
    idempotency_key: str
    command_fingerprint: str


def item_presented_payload(
    revision_id: ArtifactRevisionId,
    content_fingerprint: str,
    format: AssessmentFormat,
    prompt: str,
    options: tuple[str, ...],
    idempotency_key: str,
    *,
    course_id: CourseId,
    session_id: SessionId,
) -> JsonObject:
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("presentation payload requires typed course and session ids")
    presentation_id = presentation_id_for(course_id, session_id, revision_id, idempotency_key)
    core: JsonObject = {
        "presentation_id": str(presentation_id),
        "revision_id": str(revision_id),
        "content_fingerprint": content_fingerprint,
        "format": format.value,
        "prompt": prompt,
        "options": tuple(options),
        "idempotency_key": idempotency_key,
    }
    return {**core, "command_fingerprint": _sha(core)}


def attempt_recorded_payload(
    presentation_id: PresentationId,
    response: CanonicalResponse,
    latency_ms: int | None,
    idempotency_key: str,
    *,
    course_id: CourseId,
    session_id: SessionId,
) -> JsonObject:
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("attempt payload requires typed course and session ids")
    attempt_id = attempt_id_for(course_id, session_id, presentation_id, idempotency_key)
    core: JsonObject = {
        "attempt_id": str(attempt_id),
        "presentation_id": str(presentation_id),
        "response": response_to_json(response),
        "response_fingerprint": response_fingerprint(response),
        "latency_ms": latency_ms,
        "idempotency_key": idempotency_key,
    }
    return {**core, "command_fingerprint": _sha(core)}


def grade_recorded_payload(
    attempt_id: AttemptId,
    status: GradeStatus,
    criterion_results: tuple[CriterionResult, ...],
    provenance: GradeProvenance,
    supersedes_grade_id: GradeId | None,
    idempotency_key: str,
    *,
    course_id: CourseId,
    session_id: SessionId,
) -> JsonObject:
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("grade payload requires typed course and session ids")
    grade_id = grade_id_for(course_id, session_id, attempt_id, idempotency_key)
    core: JsonObject = {
        "grade_id": str(grade_id),
        "attempt_id": str(attempt_id),
        "status": status.value,
        "criterion_results": tuple(_criterion_json(item) for item in criterion_results),
        "provenance": _provenance_json(provenance),
        "supersedes_grade_id": str(supersedes_grade_id) if supersedes_grade_id else None,
        "idempotency_key": idempotency_key,
    }
    return {**core, "command_fingerprint": _sha(core)}


def grade_contested_payload(grade_id: GradeId, reason: str, idempotency_key: str) -> JsonObject:
    core: JsonObject = {
        "grade_id": str(grade_id),
        "reason": reason,
        "idempotency_key": idempotency_key,
    }
    return {**core, "command_fingerprint": _sha(core)}


def decode_item_presented(event: DomainEvent) -> ItemPresented:
    payload = _envelope(event, ITEM_PRESENTED, PrincipalKind.SERVICE)
    _exact(
        payload,
        {
            "presentation_id",
            "revision_id",
            "content_fingerprint",
            "format",
            "prompt",
            "options",
            "idempotency_key",
            "command_fingerprint",
        },
        "item presentation",
    )
    revision_id = ArtifactRevisionId(_text(payload, "revision_id"))
    options = _texts(payload, "options", allow_empty=True)
    decoded = ItemPresented(
        PresentationId(_text(payload, "presentation_id")),
        revision_id,
        _fingerprint(payload, "content_fingerprint"),
        AssessmentFormat(_text(payload, "format")),
        _text(payload, "prompt"),
        options,
        _key(payload),
        _command_fingerprint(payload),
    )
    assert event.session_id is not None
    if decoded.presentation_id != presentation_id_for(
        event.course_id, event.session_id, revision_id, decoded.idempotency_key
    ):
        raise ValueError("presentation identity does not bind its trusted target")
    _verify_command(payload)
    return decoded


def decode_attempt_recorded(event: DomainEvent) -> AttemptRecorded:
    payload = _envelope(event, ATTEMPT_RECORDED, PrincipalKind.HUMAN)
    _exact(
        payload,
        {
            "attempt_id",
            "presentation_id",
            "response",
            "response_fingerprint",
            "latency_ms",
            "idempotency_key",
            "command_fingerprint",
        },
        "assessment attempt",
    )
    presentation_id = PresentationId(_text(payload, "presentation_id"))
    response = _response(payload.get("response"))
    latency = payload.get("latency_ms")
    if latency is not None and (type(latency) is not int or latency < 0):
        raise ValueError("latency_ms must be non-negative or absent")
    decoded = AttemptRecorded(
        AttemptId(_text(payload, "attempt_id")),
        presentation_id,
        response,
        _fingerprint(payload, "response_fingerprint"),
        latency,
        _key(payload),
        _command_fingerprint(payload),
    )
    assert event.session_id is not None
    if decoded.attempt_id != attempt_id_for(
        event.course_id, event.session_id, presentation_id, decoded.idempotency_key
    ):
        raise ValueError("attempt identity does not bind its presentation")
    if decoded.response_fingerprint != response_fingerprint(response):
        raise ValueError("response fingerprint mismatch")
    _verify_command(payload)
    return decoded


def decode_grade_recorded(event: DomainEvent) -> GradeRecorded:
    payload = _envelope(event, GRADE_RECORDED, PrincipalKind.SERVICE)
    _exact(
        payload,
        {
            "grade_id",
            "attempt_id",
            "status",
            "criterion_results",
            "provenance",
            "supersedes_grade_id",
            "idempotency_key",
            "command_fingerprint",
        },
        "assessment grade",
    )
    attempt_id = AttemptId(_text(payload, "attempt_id"))
    supersedes_raw = payload.get("supersedes_grade_id")
    if supersedes_raw is not None and not isinstance(supersedes_raw, str):
        raise ValueError("supersedes_grade_id must be text or null")
    decoded = GradeRecorded(
        GradeId(_text(payload, "grade_id")),
        attempt_id,
        GradeStatus(_text(payload, "status")),
        tuple(_criterion(item) for item in _objects(payload, "criterion_results")),
        _provenance(payload.get("provenance")),
        GradeId(supersedes_raw) if isinstance(supersedes_raw, str) else None,
        _key(payload),
        _command_fingerprint(payload),
    )
    assert event.session_id is not None
    if decoded.grade_id != grade_id_for(
        event.course_id, event.session_id, attempt_id, decoded.idempotency_key
    ):
        raise ValueError("grade identity does not bind its attempt")
    _verify_command(payload)
    return decoded


def decode_grade_contested(event: DomainEvent) -> GradeContested:
    payload = _envelope(event, GRADE_CONTESTED, PrincipalKind.HUMAN)
    _exact(
        payload,
        {"grade_id", "reason", "idempotency_key", "command_fingerprint"},
        "grade contest",
    )
    decoded = GradeContested(
        GradeId(_text(payload, "grade_id")),
        _text(payload, "reason"),
        _key(payload),
        _command_fingerprint(payload),
    )
    if len(decoded.reason) > 4096:
        raise ValueError("grade contest reason is too long")
    _verify_command(payload)
    return decoded


def _envelope(
    event: DomainEvent, event_type: str, authority: PrincipalKind
) -> Mapping[str, JsonValue]:
    if event.event_type != event_type or event.schema_version != ASSESSMENT_SCHEMA_VERSION:
        raise ValueError("assessment event type or schema is invalid")
    if event.actor.kind is not authority or event.session_id is None:
        raise ValueError(f"{event_type} requires {authority.value.upper()} session authority")
    _reject_forbidden(event.payload)
    expected = assessment_event_id_for(
        event.course_id,
        event.session_id,
        _text(event.payload, "idempotency_key"),
        event_type,
    )
    if event.event_id != expected:
        raise ValueError("assessment event id does not match command identity")
    return event.payload


def _reject_forbidden(value: JsonValue, *, key: str | None = None) -> None:
    forbidden = {
        "mastery",
        "mastery_state",
        "schedule",
        "scheduling",
        "learner_model",
        "provider",
        "provider_id",
        "credential",
        "credentials",
        "api_key",
        "access_token",
        "password",
        "secret",
        "raw_trace",
        "trace",
    }
    if key is not None and key.lower() in forbidden:
        raise ValueError("assessment payload contains a forbidden field")
    if isinstance(value, Mapping):
        for nested_key, nested in value.items():
            _reject_forbidden(nested, key=nested_key)
    elif isinstance(value, tuple):
        for nested in value:
            _reject_forbidden(nested)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(
            marker in lowered
            for marker in (
                "api_key",
                "apikey",
                "access_token",
                "bearer ",
                "password=",
                "secret=",
                "token=",
                "sk-live-",
                "sk_test_",
            )
        ):
            raise ValueError("assessment payload contains a secret-shaped value")


def _response(value: JsonValue | None) -> CanonicalResponse:
    if not isinstance(value, Mapping):
        raise ValueError("response must be an object")
    _exact(value, {"kind", "value"}, "response")
    kind = _text(value, "kind")
    raw = _text(value, "value")
    if kind == "free_response":
        return FreeResponse(raw)
    if kind == "single_choice":
        return SingleChoiceResponse(raw)
    if kind == "multiple_choice":
        import json

        try:
            selected = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("multiple-choice response must be canonical JSON") from error
        if not isinstance(selected, list) or any(not isinstance(item, str) for item in selected):
            raise ValueError("multiple-choice response must be a JSON string array")
        response = MultipleChoiceResponse(tuple(selected))
        if response_to_json(response)["value"] != raw:
            raise ValueError("multiple-choice response JSON is not canonical")
        return response
    raise ValueError("response kind is invalid")


def _criterion(value: Mapping[str, JsonValue]) -> CriterionResult:
    from study_agent.domain import CriterionStatus

    _exact(value, {"criterion", "status", "rationale"}, "criterion result")
    return CriterionResult(
        _text(value, "criterion"),
        CriterionStatus(_text(value, "status")),
        _text(value, "rationale"),
    )


def _criterion_json(value: CriterionResult) -> JsonObject:
    return {
        "criterion": value.criterion,
        "status": value.status.value,
        "rationale": value.rationale,
    }


def _provenance(value: JsonValue | None) -> GradeProvenance:
    if not isinstance(value, Mapping):
        raise ValueError("grade provenance must be an object")
    kind = _text(value, "kind")
    if kind == "deterministic":
        _exact(
            value,
            {
                "kind",
                "policy_id",
                "policy_version",
                "policy_fingerprint",
                "rubric_fingerprint",
            },
            "deterministic provenance",
        )
        return DeterministicGradeProvenance(
            _text(value, "policy_id"),
            _text(value, "policy_version"),
            _fingerprint(value, "policy_fingerprint"),
            _fingerprint(value, "rubric_fingerprint"),
        )
    if kind == "verified_capability":
        expected = {
            "kind",
            "run_id",
            "capability_id",
            "capability_version",
            "capability_fingerprint",
            "definition_fingerprint",
            "proof_fingerprint",
            "prompt_fingerprint",
            "model_fingerprint",
            "validators",
            "rubric_fingerprint",
        }
        _exact(value, expected, "verified grade provenance")
        return VerifiedCapabilityGradeProvenance(
            RunId(_text(value, "run_id")),
            _text(value, "capability_id"),
            _text(value, "capability_version"),
            _fingerprint(value, "capability_fingerprint"),
            _fingerprint(value, "definition_fingerprint"),
            _fingerprint(value, "proof_fingerprint"),
            _fingerprint(value, "prompt_fingerprint"),
            _fingerprint(value, "model_fingerprint"),
            tuple(_validator(item) for item in _objects(value, "validators")),
            _fingerprint(value, "rubric_fingerprint"),
        )
    raise ValueError("grade provenance kind is invalid")


def _provenance_json(value: GradeProvenance) -> JsonObject:
    if isinstance(value, DeterministicGradeProvenance):
        return {
            "kind": "deterministic",
            "policy_id": value.policy_id,
            "policy_version": value.policy_version,
            "policy_fingerprint": value.policy_fingerprint,
            "rubric_fingerprint": value.rubric_fingerprint,
        }
    if isinstance(value, VerifiedCapabilityGradeProvenance):
        return {
            "kind": "verified_capability",
            "run_id": str(value.run_id),
            "capability_id": value.capability_id,
            "capability_version": value.capability_version,
            "capability_fingerprint": value.capability_fingerprint,
            "definition_fingerprint": value.definition_fingerprint,
            "proof_fingerprint": value.proof_fingerprint,
            "prompt_fingerprint": value.prompt_fingerprint,
            "model_fingerprint": value.model_fingerprint,
            "validators": tuple(_validator_json(item) for item in value.validators),
            "rubric_fingerprint": value.rubric_fingerprint,
        }
    raise TypeError("unknown grade provenance")


def _validator(value: Mapping[str, JsonValue]) -> ValidatorReceipt:
    _exact(
        value,
        {"validator_id", "validator_version", "validator_fingerprint", "passed"},
        "validator receipt",
    )
    passed = value.get("passed")
    if type(passed) is not bool:
        raise ValueError("validator passed must be boolean")
    return ValidatorReceipt(
        _text(value, "validator_id"),
        _text(value, "validator_version"),
        _fingerprint(value, "validator_fingerprint"),
        passed,
    )


def _validator_json(value: ValidatorReceipt) -> JsonObject:
    return {
        "validator_id": value.validator_id,
        "validator_version": value.validator_version,
        "validator_fingerprint": value.validator_fingerprint,
        "passed": value.passed,
    }


def _objects(value: Mapping[str, JsonValue], key: str) -> tuple[Mapping[str, JsonValue], ...]:
    raw = value.get(key)
    if not isinstance(raw, tuple) or any(not isinstance(item, Mapping) for item in raw):
        raise ValueError(f"{key} must be an array of objects")
    return tuple(item for item in raw if isinstance(item, Mapping))


def _texts(
    value: Mapping[str, JsonValue], key: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    raw = value.get(key)
    if not isinstance(raw, tuple) or any(not isinstance(item, str) for item in raw):
        raise ValueError(f"{key} must be an array of text")
    result = tuple(item for item in raw if isinstance(item, str))
    if not allow_empty and not result:
        raise ValueError(f"{key} cannot be empty")
    return result


def _text(value: Mapping[str, JsonValue], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw or raw != raw.strip():
        raise ValueError(f"{key} must be non-empty trimmed text")
    return raw


def _fingerprint(value: Mapping[str, JsonValue], key: str) -> str:
    raw = _text(value, key)
    if len(raw) != 64 or any(char not in "0123456789abcdef" for char in raw):
        raise ValueError(f"{key} must be a lowercase SHA-256 fingerprint")
    return raw


def _key(value: Mapping[str, JsonValue]) -> str:
    return _text(value, "idempotency_key")


def _command_fingerprint(value: Mapping[str, JsonValue]) -> str:
    return _fingerprint(value, "command_fingerprint")


def _verify_command(value: Mapping[str, JsonValue]) -> None:
    core = {key: item for key, item in value.items() if key != "command_fingerprint"}
    if _command_fingerprint(value) != _sha(core):
        raise ValueError("assessment command fingerprint mismatch")


def _sha(value: Mapping[str, JsonValue]) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _exact(value: Mapping[str, JsonValue], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} fields must match the exact schema")


__all__ = [
    "ASSESSMENT_EVENT_TYPES",
    "ASSESSMENT_SCHEMA_VERSION",
    "ATTEMPT_RECORDED",
    "GRADE_CONTESTED",
    "GRADE_RECORDED",
    "ITEM_PRESENTED",
    "AttemptRecorded",
    "GradeContested",
    "GradeRecorded",
    "ItemPresented",
    "attempt_recorded_payload",
    "decode_attempt_recorded",
    "decode_grade_contested",
    "decode_grade_recorded",
    "decode_item_presented",
    "grade_contested_payload",
    "grade_recorded_payload",
    "item_presented_payload",
]
