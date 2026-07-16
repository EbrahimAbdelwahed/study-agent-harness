"""Immutable contracts for the canonical assessment ledger."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from types import MappingProxyType

from study_agent.artifacts.content import AssessmentItemContent
from study_agent.domain import (
    ArtifactRevisionId,
    AssessmentFormat,
    AttemptId,
    CourseId,
    CriterionStatus,
    GradeId,
    GradeLifecycle,
    GradeStatus,
    PresentationId,
    RunId,
    SessionId,
)
from study_agent.domain._validation import JsonObject, require_aware, require_text
from study_agent.state import canonical_json_bytes

_MAX_TEXT = 4096
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "access_token",
    "bearer ",
    "password",
    "secret",
    "token=",
    "sk-live-",
    "sk_test_",
)


@dataclass(frozen=True, slots=True)
class FreeResponse:
    text: str

    def __post_init__(self) -> None:
        _bounded_text(self.text, "free response")


@dataclass(frozen=True, slots=True)
class SingleChoiceResponse:
    selected_option: str

    def __post_init__(self) -> None:
        _bounded_text(self.selected_option, "selected option")


@dataclass(frozen=True, slots=True)
class MultipleChoiceResponse:
    selected_options: tuple[str, ...]

    def __post_init__(self) -> None:
        values = tuple(self.selected_options)
        if not values or len(values) != len(set(values)):
            raise ValueError("multiple-choice response must be non-empty and unique")
        for value in values:
            _bounded_text(value, "selected option")
        object.__setattr__(self, "selected_options", values)


type CanonicalResponse = FreeResponse | SingleChoiceResponse | MultipleChoiceResponse


@dataclass(frozen=True, slots=True)
class CriterionResult:
    criterion: str
    status: CriterionStatus
    rationale: str

    def __post_init__(self) -> None:
        _bounded_text(self.criterion, "criterion")
        if not isinstance(self.status, CriterionStatus):
            raise TypeError("criterion status is invalid")
        _bounded_text(self.rationale, "criterion rationale")


@dataclass(frozen=True, slots=True)
class RationalScore:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise TypeError("rational score terms must be integers")
        if self.denominator <= 0 or not 0 <= self.numerator <= self.denominator:
            raise ValueError("rational score must satisfy 0 <= numerator <= denominator")


@dataclass(frozen=True, slots=True)
class DeterministicGradeProvenance:
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    rubric_fingerprint: str

    def __post_init__(self) -> None:
        _portable(self.policy_id, "policy_id")
        _version(self.policy_version, "policy_version")
        _fingerprint(self.policy_fingerprint, "policy_fingerprint")
        _fingerprint(self.rubric_fingerprint, "rubric_fingerprint")
        _reject_secret((self.policy_id, self.policy_version))


@dataclass(frozen=True, slots=True)
class ValidatorReceipt:
    validator_id: str
    validator_version: str
    validator_fingerprint: str
    passed: bool

    def __post_init__(self) -> None:
        _portable(self.validator_id, "validator_id")
        _version(self.validator_version, "validator_version")
        _fingerprint(self.validator_fingerprint, "validator_fingerprint")
        if self.passed is not True:
            raise ValueError("persisted grade validators must have passed")


@dataclass(frozen=True, slots=True)
class VerifiedCapabilityGradeProvenance:
    run_id: RunId
    capability_id: str
    capability_version: str
    capability_fingerprint: str
    definition_fingerprint: str
    proof_fingerprint: str
    prompt_fingerprint: str
    model_fingerprint: str
    validators: tuple[ValidatorReceipt, ...]
    rubric_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("verified grade run_id must be RunId")
        _portable(self.capability_id, "capability_id")
        _version(self.capability_version, "capability_version")
        for value, name in (
            (self.capability_fingerprint, "capability_fingerprint"),
            (self.definition_fingerprint, "definition_fingerprint"),
            (self.proof_fingerprint, "proof_fingerprint"),
            (self.prompt_fingerprint, "prompt_fingerprint"),
            (self.model_fingerprint, "model_fingerprint"),
            (self.rubric_fingerprint, "rubric_fingerprint"),
        ):
            _fingerprint(value, name)
        validators = tuple(self.validators)
        if not validators or any(not isinstance(item, ValidatorReceipt) for item in validators):
            raise ValueError("verified grade requires passed validator receipts")
        object.__setattr__(self, "validators", validators)
        _reject_secret((self.capability_id, self.capability_version, str(self.run_id)))


type GradeProvenance = DeterministicGradeProvenance | VerifiedCapabilityGradeProvenance


@dataclass(frozen=True, slots=True)
class PresentationRecord:
    id: PresentationId
    course_id: CourseId
    session_id: SessionId
    revision_id: ArtifactRevisionId
    content_fingerprint: str
    content: AssessmentItemContent
    presented_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, PresentationId) or not isinstance(
            self.revision_id, ArtifactRevisionId
        ):
            raise TypeError("presentation record identities are invalid")
        if not isinstance(self.course_id, CourseId) or not isinstance(self.session_id, SessionId):
            raise TypeError("presentation record scope is invalid")
        if not isinstance(self.content, AssessmentItemContent):
            raise TypeError("presentation content must be an assessment item")
        _fingerprint(self.content_fingerprint, "content_fingerprint")
        require_aware(self.presented_at, "presented_at")


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    id: AttemptId
    course_id: CourseId
    session_id: SessionId
    presentation_id: PresentationId
    response: CanonicalResponse
    response_fingerprint: str
    latency_ms: int | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, AttemptId) or not isinstance(
            self.presentation_id, PresentationId
        ):
            raise TypeError("attempt record identities are invalid")
        if not isinstance(
            self.response, (FreeResponse, SingleChoiceResponse, MultipleChoiceResponse)
        ):
            raise TypeError("attempt response is invalid")
        _fingerprint(self.response_fingerprint, "response_fingerprint")
        if self.latency_ms is not None and (
            type(self.latency_ms) is not int or self.latency_ms < 0
        ):
            raise ValueError("latency_ms must be non-negative or absent")
        require_aware(self.recorded_at, "recorded_at")


@dataclass(frozen=True, slots=True)
class GradeRecord:
    id: GradeId
    course_id: CourseId
    session_id: SessionId
    attempt_id: AttemptId
    status: GradeStatus
    criterion_results: tuple[CriterionResult, ...]
    score: RationalScore
    provenance: GradeProvenance
    lifecycle: GradeLifecycle
    supersedes_grade_id: GradeId | None
    recorded_at: datetime
    event_sequence: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.status, GradeStatus) or not isinstance(
            self.lifecycle, GradeLifecycle
        ):
            raise TypeError("grade status or lifecycle is invalid")
        object.__setattr__(self, "criterion_results", tuple(self.criterion_results))
        if not isinstance(self.score, RationalScore):
            raise TypeError("grade score must be RationalScore")
        if not isinstance(
            self.provenance,
            (DeterministicGradeProvenance, VerifiedCapabilityGradeProvenance),
        ):
            raise TypeError("grade provenance is invalid")
        require_aware(self.recorded_at, "recorded_at")
        if type(self.event_sequence) is not int or self.event_sequence < 0:
            raise ValueError("grade event_sequence must be non-negative")


@dataclass(frozen=True, slots=True)
class GradeContestRecord:
    grade_id: GradeId
    course_id: CourseId
    session_id: SessionId
    reason: str
    contested_at: datetime
    event_sequence: int = 0

    def __post_init__(self) -> None:
        _bounded_text(self.reason, "contest reason")
        require_aware(self.contested_at, "contested_at")
        if type(self.event_sequence) is not int or self.event_sequence < 0:
            raise ValueError("contest event_sequence must be non-negative")


@dataclass(frozen=True, slots=True)
class LearnerPresentationView:
    presentation_id: PresentationId
    revision_id: ArtifactRevisionId
    format: AssessmentFormat
    prompt: str
    options: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssessmentSnapshot:
    course_id: CourseId
    sequence: int
    presentations: tuple[PresentationRecord, ...] = ()
    attempts: tuple[AttemptRecord, ...] = ()
    grades: tuple[GradeRecord, ...] = ()
    contests: tuple[GradeContestRecord, ...] = ()
    _presentation_by_id: Mapping[PresentationId, PresentationRecord] = field(
        init=False, repr=False, compare=False
    )
    _attempt_by_id: Mapping[AttemptId, AttemptRecord] = field(
        init=False, repr=False, compare=False
    )
    _grade_by_id: Mapping[GradeId, GradeRecord] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("assessment snapshot sequence must be non-negative")
        for name in ("presentations", "attempts", "grades", "contests"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        values = {item.id: item for item in self.presentations}
        if len(values) != len(self.presentations):
            raise ValueError("assessment snapshot has duplicate presentations")
        object.__setattr__(self, "_presentation_by_id", MappingProxyType(values))
        attempts = {item.id: item for item in self.attempts}
        grades = {item.id: item for item in self.grades}
        if len(attempts) != len(self.attempts) or len(grades) != len(self.grades):
            raise ValueError("assessment snapshot has duplicate attempts or grades")
        object.__setattr__(self, "_attempt_by_id", MappingProxyType(attempts))
        object.__setattr__(self, "_grade_by_id", MappingProxyType(grades))

    def presentation(self, presentation_id: PresentationId) -> PresentationRecord:
        try:
            return self._presentation_by_id[presentation_id]
        except KeyError as error:
            raise LookupError(f"presentation {presentation_id} was not found") from error

    def attempt(self, attempt_id: AttemptId) -> AttemptRecord:
        try:
            return self._attempt_by_id[attempt_id]
        except KeyError as error:
            raise LookupError(f"attempt {attempt_id} was not found") from error

    def grade(self, grade_id: GradeId) -> GradeRecord:
        try:
            return self._grade_by_id[grade_id]
        except KeyError as error:
            raise LookupError(f"grade {grade_id} was not found") from error

    def learner_presentation(self, presentation_id: PresentationId) -> LearnerPresentationView:
        item = self.presentation(presentation_id)
        return LearnerPresentationView(
            item.id,
            item.revision_id,
            item.content.format,
            item.content.prompt,
            item.content.options,
        )


def response_fingerprint(response: CanonicalResponse) -> str:
    return sha256(canonical_json_bytes(response_to_json(response))).hexdigest()


def response_to_json(response: CanonicalResponse) -> JsonObject:
    if isinstance(response, FreeResponse):
        return {"kind": "free_response", "value": response.text}
    if isinstance(response, SingleChoiceResponse):
        return {"kind": "single_choice", "value": response.selected_option}
    if isinstance(response, MultipleChoiceResponse):
        return {
            "kind": "multiple_choice",
            "value": json.dumps(
                response.selected_options, ensure_ascii=False, separators=(",", ":")
            ),
        }
    raise TypeError("unknown canonical response")


def canonical_multiple_choice(options: tuple[str, ...]) -> str:
    return json.dumps(tuple(options), ensure_ascii=False, separators=(",", ":"))


def _bounded_text(value: str, name: str) -> None:
    require_text(value, name)
    if len(value) > _MAX_TEXT:
        raise ValueError(f"{name} exceeds {_MAX_TEXT} characters")
    _reject_secret((value,))


def _fingerprint(value: str, name: str) -> None:
    require_text(value, name)
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 fingerprint")


def _portable(value: str, name: str) -> None:
    require_text(value, name)
    if re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", value) is None:
        raise ValueError(f"{name} must be a portable lowercase identifier")


def _version(value: str, name: str) -> None:
    require_text(value, name)
    if re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._-]*", value) is None:
        raise ValueError(f"{name} must be portable")


def _reject_secret(values: tuple[str, ...]) -> None:
    text = " ".join(values).lower()
    if any(marker in text for marker in _SECRET_MARKERS):
        raise ValueError("assessment state cannot contain secret-shaped values")


__all__ = [
    "AssessmentSnapshot",
    "AttemptRecord",
    "CanonicalResponse",
    "CriterionResult",
    "DeterministicGradeProvenance",
    "FreeResponse",
    "GradeContestRecord",
    "GradeProvenance",
    "GradeRecord",
    "LearnerPresentationView",
    "MultipleChoiceResponse",
    "PresentationRecord",
    "RationalScore",
    "SingleChoiceResponse",
    "ValidatorReceipt",
    "VerifiedCapabilityGradeProvenance",
    "canonical_multiple_choice",
    "response_fingerprint",
    "response_to_json",
]
