"""Provider-neutral, immutable recall and scheduling values.

The module intentionally contains no scheduler-library imports.  All values are
portable JSON leaves so an event stream can be replayed without optional extras.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256

from study_agent.domain import ArtifactRevisionId, CourseId, ReviewId, ScheduleDecisionId
from study_agent.domain._validation import JsonObject, JsonValue, require_aware, require_text
from study_agent.state import canonical_json_bytes


class RecallRating(StrEnum):
    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


def _utc(value: datetime, name: str) -> datetime:
    require_aware(value, name)
    return value.astimezone(UTC)


def _portable(value: str, name: str) -> None:
    require_text(value, name)
    if re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", value) is None:
        raise ValueError(f"{name} must be a portable lowercase identifier")
    lowered = value.lower()
    if any(token in lowered for token in ("secret", "password", "token", "api_key", "bearer")):
        raise ValueError(f"{name} cannot contain secret-shaped text")


def _version(value: str, name: str) -> None:
    require_text(value, name)
    if re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._+-]*", value) is None:
        raise ValueError(f"{name} must be portable")
    if any(
        token in value.lower() for token in ("secret", "password", "token", "api_key", "bearer")
    ):
        raise ValueError(f"{name} cannot contain secret-shaped text")


def _fp(value: str, name: str) -> None:
    require_text(value, name)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 fingerprint")


def _bounded_int(value: int | None, name: str, *, maximum: int | None = None) -> None:
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError(f"{name} must be a non-negative integer or absent")
    if value is not None and maximum is not None and value > maximum:
        raise ValueError(f"{name} exceeds its bound")


@dataclass(frozen=True, slots=True)
class SchedulingPolicyConfigV1:
    target_retention_bps: int = 9000
    maximum_interval_days: int = 36500
    learning_steps_minutes: tuple[int, ...] = (1, 10)
    relearning_steps_minutes: tuple[int, ...] = (10,)
    fuzzing_enabled: bool = False

    def __post_init__(self) -> None:
        if type(self.target_retention_bps) is not int or not 0 < self.target_retention_bps <= 10000:
            raise ValueError("target_retention_bps must be in 1..10000")
        if type(self.maximum_interval_days) is not int or self.maximum_interval_days < 1:
            raise ValueError("maximum_interval_days must be positive")
        for name, steps in (
            ("learning_steps_minutes", self.learning_steps_minutes),
            ("relearning_steps_minutes", self.relearning_steps_minutes),
        ):
            if not isinstance(steps, tuple) or any(
                type(item) is not int or item <= 0 for item in steps
            ):
                raise ValueError(f"{name} must contain positive integer minutes")
            if len(steps) > 32:
                raise ValueError(f"{name} is too long")
        if self.fuzzing_enabled is not False:
            raise ValueError("fuzzing is not permitted in canonical scheduling")

    @property
    def desired_retention_bps(self) -> int:
        return self.target_retention_bps

    def to_json(self) -> JsonObject:
        return {
            "schema_version": 1,
            "target_retention_bps": self.target_retention_bps,
            "maximum_interval_days": self.maximum_interval_days,
            "learning_steps_minutes": self.learning_steps_minutes,
            "relearning_steps_minutes": self.relearning_steps_minutes,
            "fuzzing_enabled": False,
        }

    @property
    def fingerprint(self) -> str:
        return sha256(
            b"recall-policy-config@1\0" + canonical_json_bytes(self.to_json())
        ).hexdigest()

    @classmethod
    def from_json(cls, value: JsonObject) -> SchedulingPolicyConfigV1:
        _strict(
            value,
            {
                "schema_version",
                "target_retention_bps",
                "maximum_interval_days",
                "learning_steps_minutes",
                "relearning_steps_minutes",
                "fuzzing_enabled",
            },
            "policy",
        )
        if value.get("schema_version") != 1:
            raise ValueError("unsupported scheduling policy schema")
        steps = value.get("learning_steps_minutes")
        relearning = value.get("relearning_steps_minutes")
        if not isinstance(steps, tuple) or not isinstance(relearning, tuple):
            raise ValueError("policy step lists must be canonical tuples")
        fuzzing_enabled = value.get("fuzzing_enabled")
        if type(fuzzing_enabled) is not bool:
            raise ValueError("fuzzing_enabled must be boolean")
        return cls(
            _exact_int(value.get("target_retention_bps"), "target_retention_bps"),
            _exact_int(value.get("maximum_interval_days"), "maximum_interval_days"),
            tuple(_exact_int(item, "learning step") for item in steps),
            tuple(_exact_int(item, "relearning step") for item in relearning),
            fuzzing_enabled,
        )


@dataclass(frozen=True, slots=True)
class ReviewHistoryEntry:
    review_id: ReviewId
    revision_id: ArtifactRevisionId
    rating: RecallRating
    latency_ms: int | None
    confidence_bps: int | None
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.review_id, ReviewId) or not isinstance(
            self.revision_id, ArtifactRevisionId
        ):
            raise TypeError("review history ids are invalid")
        if not isinstance(self.rating, RecallRating):
            raise TypeError("review rating is invalid")
        _bounded_int(self.latency_ms, "latency_ms")
        _bounded_int(self.confidence_bps, "confidence_bps", maximum=10000)
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "occurred_at"))


@dataclass(frozen=True, slots=True)
class SchedulingRequest:
    revision_id: ArtifactRevisionId
    enrollment_at: datetime
    history: tuple[ReviewHistoryEntry, ...]
    policy: SchedulingPolicyConfigV1

    def __post_init__(self) -> None:
        if not isinstance(self.revision_id, ArtifactRevisionId):
            raise TypeError("scheduling revision_id is invalid")
        object.__setattr__(self, "enrollment_at", _utc(self.enrollment_at, "enrollment_at"))
        object.__setattr__(self, "history", tuple(self.history))
        if any(item.revision_id != self.revision_id for item in self.history):
            raise ValueError("history contains another revision")
        if any(item.occurred_at < self.enrollment_at for item in self.history):
            raise ValueError("review occurred before enrollment")

    @property
    def history_fingerprint(self) -> str:
        return history_fingerprint(self.revision_id, self.enrollment_at, self.history)


@dataclass(frozen=True, slots=True)
class SchedulingResult:
    due_at: datetime
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    implementation_id: str
    implementation_version: str
    history_fingerprint: str
    result_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "due_at", _utc(self.due_at, "due_at"))
        _portable(self.policy_id, "policy_id")
        _version(self.policy_version, "policy_version")
        _fp(self.policy_fingerprint, "policy_fingerprint")
        _portable(self.implementation_id, "implementation_id")
        _version(self.implementation_version, "implementation_version")
        _fp(self.history_fingerprint, "history_fingerprint")
        _fp(self.result_fingerprint, "result_fingerprint")


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    review_id: ReviewId
    revision_id: ArtifactRevisionId
    rating: RecallRating
    latency_ms: int | None
    confidence_bps: int | None
    occurred_at: datetime
    idempotency_key: str
    command_fingerprint: str

    def __post_init__(self) -> None:
        entry = ReviewHistoryEntry(
            self.review_id,
            self.revision_id,
            self.rating,
            self.latency_ms,
            self.confidence_bps,
            self.occurred_at,
        )
        object.__setattr__(self, "occurred_at", entry.occurred_at)
        require_text(self.idempotency_key, "idempotency_key")
        _fp(self.command_fingerprint, "command_fingerprint")

    def to_json(self) -> JsonObject:
        return {
            "review_id": str(self.review_id),
            "revision_id": str(self.revision_id),
            "rating": self.rating.value,
            "latency_ms": self.latency_ms,
            "confidence_bps": self.confidence_bps,
            "occurred_at": _timestamp(self.occurred_at),
            "idempotency_key": self.idempotency_key,
            "command_fingerprint": self.command_fingerprint,
        }

    def history_entry(self) -> ReviewHistoryEntry:
        return ReviewHistoryEntry(
            self.review_id,
            self.revision_id,
            self.rating,
            self.latency_ms,
            self.confidence_bps,
            self.occurred_at,
        )


@dataclass(frozen=True, slots=True)
class AppliedSchedule:
    decision_id: ScheduleDecisionId
    revision_id: ArtifactRevisionId
    trigger: str
    review_id: ReviewId | None
    enrollment_at: datetime
    due_at: datetime
    policy: SchedulingPolicyConfigV1
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    implementation_id: str
    implementation_version: str
    history_fingerprint: str
    result_fingerprint: str
    idempotency_key: str
    command_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.decision_id, ScheduleDecisionId) or not isinstance(
            self.revision_id, ArtifactRevisionId
        ):
            raise TypeError("schedule ids are invalid")
        if self.trigger not in {"enrollment", "review"}:
            raise ValueError("schedule trigger is invalid")
        if self.trigger == "enrollment" and self.review_id is not None:
            raise ValueError("enrollment cannot carry review_id")
        if self.trigger == "review" and not isinstance(self.review_id, ReviewId):
            raise ValueError("review schedule requires review_id")
        object.__setattr__(self, "enrollment_at", _utc(self.enrollment_at, "enrollment_at"))
        object.__setattr__(self, "due_at", _utc(self.due_at, "due_at"))
        if self.due_at < self.enrollment_at:
            raise ValueError("due_at cannot precede enrollment")
        receipt = SchedulingResult(
            self.due_at,
            self.policy_id,
            self.policy_version,
            self.policy_fingerprint,
            self.implementation_id,
            self.implementation_version,
            self.history_fingerprint,
            self.result_fingerprint,
        )
        del receipt
        require_text(self.idempotency_key, "idempotency_key")
        _fp(self.command_fingerprint, "command_fingerprint")

    def to_json(self) -> JsonObject:
        return {
            "decision_id": str(self.decision_id),
            "revision_id": str(self.revision_id),
            "trigger": self.trigger,
            "review_id": str(self.review_id) if self.review_id else None,
            "enrollment_at": _timestamp(self.enrollment_at),
            "due_at": _timestamp(self.due_at),
            "policy": self.policy.to_json(),
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_fingerprint": self.policy_fingerprint,
            "implementation_id": self.implementation_id,
            "implementation_version": self.implementation_version,
            "history_fingerprint": self.history_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "idempotency_key": self.idempotency_key,
            "command_fingerprint": self.command_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class RecallSnapshot:
    course_id: CourseId
    sequence: int
    enrollments: tuple[AppliedSchedule, ...] = ()
    reviews: tuple[ReviewRecord, ...] = ()
    schedules: tuple[AppliedSchedule, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.course_id, CourseId)
            or type(self.sequence) is not int
            or self.sequence < 0
        ):
            raise ValueError("recall snapshot identity is invalid")
        object.__setattr__(self, "enrollments", tuple(self.enrollments))
        object.__setattr__(self, "reviews", tuple(self.reviews))
        object.__setattr__(self, "schedules", tuple(self.schedules))


@dataclass(frozen=True, slots=True)
class RecallViewRow:
    artifact_id: str
    revision_id: ArtifactRevisionId
    due_at: datetime
    schedule: AppliedSchedule

    def __post_init__(self) -> None:
        require_text(self.artifact_id, "artifact_id")
        if not isinstance(self.revision_id, ArtifactRevisionId):
            raise TypeError("revision_id is invalid")
        object.__setattr__(self, "due_at", _utc(self.due_at, "due_at"))


def history_fingerprint(
    revision_id: ArtifactRevisionId,
    enrollment_at: datetime,
    history: tuple[ReviewHistoryEntry, ...],
) -> str:
    payload: JsonObject = {
        "schema_version": 1,
        "revision_id": str(revision_id),
        "enrollment_at": _timestamp(_utc(enrollment_at, "enrollment_at")),
        "reviews": tuple(
            {
                "review_id": str(item.review_id),
                "revision_id": str(item.revision_id),
                "rating": item.rating.value,
                "latency_ms": item.latency_ms,
                "confidence_bps": item.confidence_bps,
                "occurred_at": _timestamp(item.occurred_at),
            }
            for item in history
        ),
    }
    return sha256(b"recall-history@1\0" + canonical_json_bytes(payload)).hexdigest()


def result_fingerprint(
    request: SchedulingRequest,
    result: SchedulingResult | None = None,
    *,
    due_at: datetime | None = None,
    policy_id: str | None = None,
    policy_version: str | None = None,
    implementation_id: str | None = None,
    implementation_version: str | None = None,
) -> str:
    """Bind a schedule result to its complete request and normalized receipt."""
    if result is not None:
        due_at = result.due_at
        policy_id, policy_version = result.policy_id, result.policy_version
        implementation_id, implementation_version = (
            result.implementation_id,
            result.implementation_version,
        )
        policy_fingerprint, history_fp = result.policy_fingerprint, result.history_fingerprint
    else:
        policy_fingerprint, history_fp = request.policy.fingerprint, request.history_fingerprint
    if (
        due_at is None
        or policy_id is None
        or policy_version is None
        or implementation_id is None
        or implementation_version is None
    ):
        raise ValueError("complete scheduling receipt is required")
    payload: JsonObject = {
        "schema_version": 1,
        "revision_id": str(request.revision_id),
        "enrollment_at": _timestamp(request.enrollment_at),
        "history": tuple(_history_json(item) for item in request.history),
        "policy": request.policy.to_json(),
        "policy_id": policy_id,
        "policy_version": policy_version,
        "policy_fingerprint": policy_fingerprint,
        "implementation_id": implementation_id,
        "implementation_version": implementation_version,
        "history_fingerprint": history_fp,
        "due_at": _timestamp(_utc(due_at, "due_at")),
    }
    return sha256(b"recall-result@1\0" + canonical_json_bytes(payload)).hexdigest()


def _history_json(item: ReviewHistoryEntry) -> JsonObject:
    return {
        "review_id": str(item.review_id),
        "revision_id": str(item.revision_id),
        "rating": item.rating.value,
        "latency_ms": item.latency_ms,
        "confidence_bps": item.confidence_bps,
        "occurred_at": _timestamp(item.occurred_at),
    }


def _strict(value: Mapping[str, JsonValue], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} fields are not exact")


def _exact_int(value: object, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "AppliedSchedule",
    "RecallRating",
    "RecallSnapshot",
    "RecallViewRow",
    "ReviewHistoryEntry",
    "ReviewRecord",
    "SchedulingPolicyConfigV1",
    "SchedulingRequest",
    "SchedulingResult",
    "history_fingerprint",
    "result_fingerprint",
]
