"""Strict operational contracts for lesson-scoped flashcard fan-out."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any, cast

from study_agent.capabilities import TutorCapabilityId
from study_agent.domain import RevisionId, RunId
from study_agent.domain._validation import JsonObject, JsonValue, freeze_json, freeze_object
from study_agent.flashcards.planning import (
    FlashcardLessonPlan,
    PlannedFlashcardBundle,
    PreparedPlannedFlashcardScope,
)
from study_agent.flashcards.scope import FlashcardScopeIndexEntry, PreparedFlashcardScope
from study_agent.grounding import EvidenceEnvelope
from study_agent.pedagogy import ProfileSelectionReceipt
from study_agent.playbooks import VersionPins
from study_agent.skills import SemanticVersion
from study_agent.state import canonical_json_bytes
from study_agent.workers.contracts import (
    ValidationExpectation,
    fingerprint_output_schema,
    pins_from_json,
    pins_to_json,
)
from study_agent.workers.view import WorkerDetailView

MAX_LESSON_WORKER_PAGES = 256
MAX_PREPARED_WRAPPER_BYTES = 512 * 1024
MAX_LESSON_WORKER_CHECKPOINT_BYTES = 8 * 1024 * 1024

_REQUEST_DOMAIN = "lesson-worker-request@1"
_PROFILE_DOMAIN = "lesson-worker-profile-expectation@1"
_PROFILE_SELECTION_DOMAIN = b"lesson-worker-profile-selection@1\0"
_RESOLUTION_DOMAIN = "lesson-worker-resolved-evidence@1"
_RUN_DOMAIN = "lesson-worker-run@1"
_CHILD_DOMAIN = "lesson-worker-child@1"
_AUTHORITY_DOMAIN = "lesson-worker-authority@1"
_REVISION_DOMAIN = "lesson-worker-revision-commitments@1"
_RECEIPT_DOMAIN = "lesson-worker-page-receipt@1"
_CHECKPOINT_DOMAIN = "lesson-worker-checkpoint@1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_FORBIDDEN_SUMMARY_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "secret",
        "password",
        "credential",
        "credentials",
        "access_token",
        "refresh_token",
        "authorization",
        "principal",
        "principal_id",
        "principal_kind",
        "authority",
        "requested_capabilities",
        "course_id",
        "session_id",
        "correlation_id",
        "idempotency_key",
        "provider",
        "provider_id",
        "provider_name",
        "model",
        "model_id",
        "model_name",
        "messages",
        "message_history",
        "history",
        "conversation",
        "conversation_history",
        "decision",
        "canonical_decision",
        "artifact_id",
        "artifact_revision_id",
    }
)


class LessonWorkerPageStatus(StrEnum):
    PENDING = "pending"
    RESOLVING = "resolving"
    PREPARED = "prepared"
    CHILD_CLAIMED = "child_claimed"
    CHILD_TERMINAL = "child_terminal"


class LessonWorkerStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RevisionContentCommitment:
    revision_id: RevisionId
    content_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.revision_id, RevisionId):
            raise TypeError("revision_id must be RevisionId")
        _sha(self.content_fingerprint, "content_fingerprint")

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "revision_id": str(self.revision_id),
                "content_fingerprint": self.content_fingerprint,
            }
        )

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> RevisionContentCommitment:
        _exact(value, {"revision_id", "content_fingerprint"}, "revision commitment")
        return cls(
            RevisionId(_string(value, "revision_id")),
            _string(value, "content_fingerprint"),
        )


@dataclass(frozen=True, slots=True)
class ProfileTaskExpectation:
    profile_selection_receipt: ProfileSelectionReceipt
    capability_id: TutorCapabilityId
    capability_version: SemanticVersion
    manifest_fingerprint: str
    required_authority: tuple[str, ...]
    pins: VersionPins
    definition_fingerprint: str
    output_schema: JsonObject
    output_schema_fingerprint: str
    validations: tuple[ValidationExpectation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profile_selection_receipt, ProfileSelectionReceipt):
            raise TypeError("profile_selection_receipt must use ProfileSelectionReceipt")
        for value, name in (
            (self.manifest_fingerprint, "manifest_fingerprint"),
            (self.definition_fingerprint, "definition_fingerprint"),
            (self.output_schema_fingerprint, "output_schema_fingerprint"),
        ):
            _sha(value, name)
        if not isinstance(self.capability_id, TutorCapabilityId):
            raise TypeError("capability_id must use TutorCapabilityId")
        if not isinstance(self.capability_version, SemanticVersion):
            raise TypeError("capability_version must use SemanticVersion")
        if not isinstance(self.pins, VersionPins):
            raise TypeError("pins must use VersionPins")
        authority = tuple(self.required_authority)
        if not authority or len(authority) > 32 or len(set(authority)) != len(authority):
            raise ValueError("required_authority must contain 1..32 unique values")
        for item in authority:
            _text(item, "required authority", 256)
        if authority != tuple(sorted(authority)):
            raise ValueError("required_authority must be sorted")
        schema = freeze_object(self.output_schema)
        if len(canonical_json_bytes(schema)) > 32 * 1024:
            raise ValueError("output schema exceeds 32 KiB")
        if fingerprint_output_schema(schema) != self.output_schema_fingerprint:
            raise ValueError("output schema fingerprint does not match output schema")
        validations = tuple(self.validations)
        if not 1 <= len(validations) <= 32 or not all(
            isinstance(item, ValidationExpectation) for item in validations
        ):
            raise ValueError("validations must contain 1..32 expectations")
        if len({item.to_bytes() for item in validations}) != len(validations):
            raise ValueError("validations must be ordered and unique")
        object.__setattr__(self, "required_authority", authority)
        object.__setattr__(self, "output_schema", schema)
        object.__setattr__(self, "validations", validations)

    @property
    def profile_fingerprint(self) -> str:
        return sha256(
            _PROFILE_SELECTION_DOMAIN + self.profile_selection_receipt.to_bytes()
        ).hexdigest()

    @property
    def fingerprint(self) -> str:
        return _fingerprint(_PROFILE_DOMAIN, self.to_json())

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "profile_selection_receipt": self.profile_selection_receipt.to_json(),
                "capability_id": self.capability_id.value,
                "capability_version": str(self.capability_version),
                "manifest_fingerprint": self.manifest_fingerprint,
                "required_authority": self.required_authority,
                "pins": pins_to_json(self.pins),
                "definition_fingerprint": self.definition_fingerprint,
                "output_schema": self.output_schema,
                "output_schema_fingerprint": self.output_schema_fingerprint,
                "validations": tuple(item.to_json() for item in self.validations),
            }
        )

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> ProfileTaskExpectation:
        _exact(
            value,
            {
                "profile_selection_receipt",
                "capability_id",
                "capability_version",
                "manifest_fingerprint",
                "required_authority",
                "pins",
                "definition_fingerprint",
                "output_schema",
                "output_schema_fingerprint",
                "validations",
            },
            "profile task expectation",
        )
        return cls(
            ProfileSelectionReceipt.from_bytes(
                canonical_json_bytes(
                    _mapping(value["profile_selection_receipt"], "profile_selection_receipt")
                )
            ),
            TutorCapabilityId(_string(value, "capability_id")),
            SemanticVersion.parse(_string(value, "capability_version")),
            _string(value, "manifest_fingerprint"),
            _strings(value, "required_authority"),
            pins_from_json(_mapping(value["pins"], "pins")),
            _string(value, "definition_fingerprint"),
            freeze_object(_mapping(value["output_schema"], "output_schema")),
            _string(value, "output_schema_fingerprint"),
            tuple(
                ValidationExpectation.from_json(_mapping(item, "validation"))
                for item in _array(value, "validations")
            ),
        )


@dataclass(frozen=True, slots=True)
class LessonWorkerRequest:
    plan: FlashcardLessonPlan
    query: str
    scope: str
    language: str
    candidate_ceiling: int
    continuation_summary: JsonObject | None
    profile_expectation: ProfileTaskExpectation
    concurrency: int
    revision_commitments: tuple[RevisionContentCommitment, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.plan, FlashcardLessonPlan):
            raise TypeError("plan must be FlashcardLessonPlan")
        if len(self.plan.bundles) > MAX_LESSON_WORKER_PAGES:
            raise ValueError("lesson_worker_page_limit_exceeded")
        _text(self.query, "query", 8_000)
        _text(self.scope, "scope", 8_000)
        _text(self.language, "language", 64)
        if type(self.candidate_ceiling) is not int or not 1 <= self.candidate_ceiling <= 24:
            raise ValueError("candidate_ceiling must be an integer between 1 and 24")
        if type(self.concurrency) is not int or not 1 <= self.concurrency <= 8:
            raise ValueError("concurrency must be an integer between 1 and 8")
        if not isinstance(self.profile_expectation, ProfileTaskExpectation):
            raise TypeError("profile_expectation must be ProfileTaskExpectation")
        summary = (
            freeze_object(self.continuation_summary)
            if self.continuation_summary is not None
            else None
        )
        if summary is not None and len(_canonical_summary(summary)) > 16 * 1024:
            raise ValueError("continuation summary exceeds 16 KiB")
        if summary is not None:
            _reject_private_summary_keys(summary, "continuation_summary")
        commitments = tuple(self.revision_commitments)
        if any(not isinstance(item, RevisionContentCommitment) for item in commitments):
            raise TypeError("revision_commitments contains an invalid value")
        ids = tuple(str(item.revision_id) for item in commitments)
        if ids != tuple(sorted(ids)) or len(set(ids)) != len(ids):
            raise ValueError("revision_commitments must be sorted and unique")
        expected = tuple(sorted(_plan_revision_ids(self.plan)))
        if ids != expected:
            raise ValueError("revision_commitments must bind every and only plan revision")
        object.__setattr__(self, "continuation_summary", summary)
        object.__setattr__(self, "revision_commitments", commitments)

    @property
    def fingerprint(self) -> str:
        return _fingerprint(_REQUEST_DOMAIN, self.to_json())

    @property
    def revision_commitments_fingerprint(self) -> str:
        return revision_commitments_fingerprint(self.revision_commitments)

    def to_public_inputs(self) -> JsonObject:
        return freeze_object(
            {
                "query": self.query,
                "scope": self.scope,
                "language": self.language,
                "candidate_ceiling": self.candidate_ceiling,
                "continuation_summary_json": (
                    _canonical_summary(self.continuation_summary).decode("utf-8")
                    if self.continuation_summary is not None
                    else None
                ),
            }
        )

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "plan": self.plan.to_json(),
                "query": self.query,
                "scope": self.scope,
                "language": self.language,
                "candidate_ceiling": self.candidate_ceiling,
                "continuation_summary": self.continuation_summary,
                "profile_expectation": self.profile_expectation.to_json(),
                "concurrency": self.concurrency,
                "revision_commitments": tuple(
                    item.to_json() for item in self.revision_commitments
                ),
            }
        )

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> LessonWorkerRequest:
        value = _decode_object(data, "lesson worker request")
        _exact(
            value,
            {
                "plan",
                "query",
                "scope",
                "language",
                "candidate_ceiling",
                "continuation_summary",
                "profile_expectation",
                "concurrency",
                "revision_commitments",
            },
            "lesson worker request",
        )
        summary = value["continuation_summary"]
        request = cls(
            FlashcardLessonPlan.from_json(_mapping(value["plan"], "plan")),
            _string(value, "query"),
            _string(value, "scope"),
            _string(value, "language"),
            _integer(value, "candidate_ceiling"),
            freeze_object(_mapping(summary, "continuation_summary"))
            if summary is not None
            else None,
            ProfileTaskExpectation.from_json(
                _mapping(value["profile_expectation"], "profile_expectation")
            ),
            _integer(value, "concurrency"),
            tuple(
                RevisionContentCommitment.from_json(_mapping(item, "revision commitment"))
                for item in _array(value, "revision_commitments")
            ),
        )
        if request.to_bytes() != data:
            raise ValueError("lesson worker request bytes are not canonical")
        return request


@dataclass(frozen=True, slots=True)
class ResolvedPlannedBundleEvidence:
    envelope: EvidenceEnvelope
    revision_commitments: tuple[RevisionContentCommitment, ...]
    plan_fingerprint: str
    bundle_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.envelope, EvidenceEnvelope):
            raise TypeError("envelope must be EvidenceEnvelope")
        if len(self.envelope.items) > 24:
            raise ValueError("resolved planned evidence exceeds 24 items")
        commitments = tuple(self.revision_commitments)
        if any(not isinstance(item, RevisionContentCommitment) for item in commitments):
            raise TypeError("resolved revision commitments contain an invalid value")
        ids = tuple(str(item.revision_id) for item in commitments)
        if ids != tuple(sorted(ids)) or len(set(ids)) != len(ids):
            raise ValueError("resolved revision commitments must be sorted and unique")
        _sha(self.plan_fingerprint, "plan_fingerprint")
        _text(self.bundle_id, "bundle_id", 256)
        object.__setattr__(self, "revision_commitments", commitments)

    @property
    def fingerprint(self) -> str:
        return _fingerprint(
            _RESOLUTION_DOMAIN,
            freeze_object(
                {
                    "envelope": self.envelope.to_json(),
                    "revision_commitments": tuple(
                        item.to_json() for item in self.revision_commitments
                    ),
                    "plan_fingerprint": self.plan_fingerprint,
                    "bundle_id": self.bundle_id,
                }
            ),
        )

    def validate(
        self,
        plan: FlashcardLessonPlan,
        bundle: PlannedFlashcardBundle,
        commitments: tuple[RevisionContentCommitment, ...],
    ) -> None:
        from study_agent.ports import EvidenceStatus

        if self.plan_fingerprint != plan.plan_fingerprint or self.bundle_id != bundle.bundle_id:
            raise ValueError("resolved evidence plan or bundle changed")
        if self.revision_commitments != commitments:
            raise ValueError("resolved revision commitments changed")
        if self.envelope.status is not EvidenceStatus.SUFFICIENT:
            raise ValueError("resolved planned evidence is insufficient")
        if len(self.envelope.items) != len(bundle.slots):
            raise ValueError("resolved evidence must contain exactly one item per planned slot")
        previous_end_by_revision: dict[tuple[str, str], int] = {}
        for slot, item in zip(bundle.slots, self.envelope.items, strict=True):
            citation = item.evidence.citation
            span = slot.span
            if (
                citation.source_id != span.source_id
                or citation.revision_id != span.revision_id
                or citation.start_offset != span.start_offset
                or citation.end_offset != span.end_offset
                or citation.locator != span.locator
            ):
                raise ValueError("resolved evidence differs from its planned slot")
            key = (str(span.source_id), str(span.revision_id))
            prior = previous_end_by_revision.get(key)
            if prior is not None and span.start_offset < prior:
                raise ValueError("resolved planned evidence overlaps or is reordered")
            previous_end_by_revision[key] = span.end_offset


@dataclass(frozen=True, slots=True)
class VerifiedFlashcardPageResult:
    """Adapter-decoded B1 page summary plus its authorized verified detail."""

    candidate_count: int
    omission_count: int
    output_fingerprint: str
    detail: WorkerDetailView

    def __post_init__(self) -> None:
        for value, name in (
            (self.candidate_count, "candidate_count"),
            (self.omission_count, "omission_count"),
        ):
            if type(value) is not int or not 0 <= value <= 24:
                raise ValueError(f"{name} must be between 0 and 24")
        _sha(self.output_fingerprint, "output_fingerprint")
        if not isinstance(self.detail, WorkerDetailView):
            raise TypeError("detail must be WorkerDetailView")
        if self.detail.receipt.output_fingerprint != self.output_fingerprint:
            raise ValueError("verified page output fingerprint changed")


@dataclass(frozen=True, slots=True)
class LessonWorkerPageReceipt:
    position: int
    bundle_id: str
    child_task_id: str
    child_run_id: RunId
    child_receipt_fingerprint: str
    candidate_count: int
    omission_count: int
    failure_code: str | None

    def __post_init__(self) -> None:
        _position(self.position)
        _text(self.bundle_id, "bundle_id", 256)
        _text(self.child_task_id, "child_task_id", 256)
        if not isinstance(self.child_run_id, RunId):
            raise TypeError("child_run_id must be RunId")
        _sha(self.child_receipt_fingerprint, "child_receipt_fingerprint")
        for value, name in (
            (self.candidate_count, "candidate_count"),
            (self.omission_count, "omission_count"),
        ):
            if type(value) is not int or not 0 <= value <= 24:
                raise ValueError(f"{name} must be between 0 and 24")
        if self.failure_code is not None:
            _text(self.failure_code, "failure_code", 128)

    @property
    def fingerprint(self) -> str:
        return _fingerprint(_RECEIPT_DOMAIN, self.to_json())

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "position": self.position,
                "bundle_id": self.bundle_id,
                "child_task_id": self.child_task_id,
                "child_run_id": str(self.child_run_id),
                "child_receipt_fingerprint": self.child_receipt_fingerprint,
                "candidate_count": self.candidate_count,
                "omission_count": self.omission_count,
                "failure_code": self.failure_code,
            }
        )

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> LessonWorkerPageReceipt:
        _exact(
            value,
            {
                "position",
                "bundle_id",
                "child_task_id",
                "child_run_id",
                "child_receipt_fingerprint",
                "candidate_count",
                "omission_count",
                "failure_code",
            },
            "lesson page receipt",
        )
        return cls(
            _integer(value, "position"),
            _string(value, "bundle_id"),
            _string(value, "child_task_id"),
            RunId(_string(value, "child_run_id")),
            _string(value, "child_receipt_fingerprint"),
            _integer(value, "candidate_count"),
            _integer(value, "omission_count"),
            _optional_string(value, "failure_code"),
        )


@dataclass(frozen=True, slots=True)
class LessonWorkerPageCheckpoint:
    position: int
    bundle_id: str
    status: LessonWorkerPageStatus
    child_task_id: str
    resolution_fingerprint: str | None = None
    wrapper_bytes: bytes | None = None
    child_task_bytes: bytes | None = None
    receipt: LessonWorkerPageReceipt | None = None

    def __post_init__(self) -> None:
        _position(self.position)
        _text(self.bundle_id, "bundle_id", 256)
        _text(self.child_task_id, "child_task_id", 256)
        if not isinstance(self.status, LessonWorkerPageStatus):
            raise TypeError("status must use LessonWorkerPageStatus")
        prepared = self.status in {
            LessonWorkerPageStatus.PREPARED,
            LessonWorkerPageStatus.CHILD_CLAIMED,
            LessonWorkerPageStatus.CHILD_TERMINAL,
        }
        claimed = self.status in {
            LessonWorkerPageStatus.CHILD_CLAIMED,
            LessonWorkerPageStatus.CHILD_TERMINAL,
        }
        terminal = self.status is LessonWorkerPageStatus.CHILD_TERMINAL
        if prepared != (self.resolution_fingerprint is not None and self.wrapper_bytes is not None):
            raise ValueError("prepared page commitments do not match status")
        if self.resolution_fingerprint is not None:
            _sha(self.resolution_fingerprint, "resolution_fingerprint")
        if self.wrapper_bytes is not None:
            if len(self.wrapper_bytes) > MAX_PREPARED_WRAPPER_BYTES:
                raise ValueError("prepared planned wrapper exceeds 512 KiB")
            PreparedPlannedFlashcardScope.from_bytes(self.wrapper_bytes)
        if claimed != (self.child_task_bytes is not None):
            raise ValueError("child task bytes do not match page status")
        if terminal != (self.receipt is not None):
            raise ValueError("page receipt does not match terminal status")
        if self.receipt is not None and (
            self.receipt.position != self.position
            or self.receipt.bundle_id != self.bundle_id
            or self.receipt.child_task_id != self.child_task_id
        ):
            raise ValueError("page receipt identity changed")

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "position": self.position,
                "bundle_id": self.bundle_id,
                "status": self.status.value,
                "child_task_id": self.child_task_id,
                "resolution_fingerprint": self.resolution_fingerprint,
                "wrapper_bytes": _b64(self.wrapper_bytes),
                "child_task_bytes": _b64(self.child_task_bytes),
                "receipt": self.receipt.to_json() if self.receipt else None,
            }
        )

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> LessonWorkerPageCheckpoint:
        _exact(
            value,
            {
                "position",
                "bundle_id",
                "status",
                "child_task_id",
                "resolution_fingerprint",
                "wrapper_bytes",
                "child_task_bytes",
                "receipt",
            },
            "lesson page checkpoint",
        )
        receipt = value["receipt"]
        return cls(
            _integer(value, "position"),
            _string(value, "bundle_id"),
            LessonWorkerPageStatus(_string(value, "status")),
            _string(value, "child_task_id"),
            _optional_string(value, "resolution_fingerprint"),
            _unb64(value["wrapper_bytes"], "wrapper_bytes"),
            _unb64(value["child_task_bytes"], "child_task_bytes"),
            LessonWorkerPageReceipt.from_json(_mapping(receipt, "receipt"))
            if receipt is not None
            else None,
        )


@dataclass(frozen=True, slots=True)
class LessonWorkerCheckpoint:
    request_bytes: bytes
    request_fingerprint: str
    authority_fingerprint: str
    run_id: RunId
    pages: tuple[LessonWorkerPageCheckpoint, ...]

    def __post_init__(self) -> None:
        request = LessonWorkerRequest.from_bytes(self.request_bytes)
        if request.fingerprint != self.request_fingerprint:
            raise ValueError("checkpoint request fingerprint is invalid")
        _sha(self.authority_fingerprint, "authority_fingerprint")
        if not isinstance(self.run_id, RunId):
            raise TypeError("run_id must be RunId")
        if self.run_id != lesson_run_id(request, self.authority_fingerprint):
            raise ValueError("checkpoint lesson run identity is invalid")
        pages = tuple(self.pages)
        if len(pages) > MAX_LESSON_WORKER_PAGES:
            raise ValueError("lesson_worker_page_limit_exceeded")
        if tuple(item.position for item in pages) != tuple(range(len(pages))):
            raise ValueError("checkpoint pages must be in canonical position order")
        if len(pages) != len(request.plan.bundles):
            raise ValueError("checkpoint pages must exactly match plan bundles")
        for page, bundle in zip(pages, request.plan.bundles, strict=True):
            if page.bundle_id != bundle.bundle_id:
                raise ValueError("checkpoint page bundle order changed")
            if page.child_task_id != child_task_id(self.run_id, request, bundle, None):
                # Prepared pages commit the wrapper in the child identity; verify below.
                if page.wrapper_bytes is None:
                    raise ValueError("checkpoint child identity changed")
                wrapper = PreparedPlannedFlashcardScope.from_bytes(page.wrapper_bytes)
                if page.child_task_id != child_task_id(self.run_id, request, bundle, wrapper):
                    raise ValueError("checkpoint child identity changed")
            if page.wrapper_bytes is not None:
                wrapper = PreparedPlannedFlashcardScope.from_bytes(page.wrapper_bytes)
                wrapper.validate_against_plan(request.plan)
                resolution = ResolvedPlannedBundleEvidence(
                    wrapper.prepared_scope.evidence,
                    request.revision_commitments,
                    request.plan.plan_fingerprint,
                    page.bundle_id,
                )
                resolution.validate(
                    request.plan,
                    bundle,
                    request.revision_commitments,
                )
                if page.resolution_fingerprint != resolution.fingerprint:
                    raise ValueError("checkpoint resolution commitment is invalid")
                handles_by_topic: dict[str, list[str]] = {
                    key: [] for key in bundle.active_topic_keys
                }
                for slot, evidence_item in zip(
                    bundle.slots,
                    wrapper.prepared_scope.evidence.items,
                    strict=True,
                ):
                    handles_by_topic[slot.topic_key].append(evidence_item.handle)
                expected_index = tuple(
                    FlashcardScopeIndexEntry(
                        topic_key=item.topic_key,
                        heading=item.title,
                        locator=item.span.locator,
                        relative_position=item.relative_position,
                        character_count=item.subtree_visible_character_count,
                        evidence_handles=tuple(handles_by_topic.get(item.topic_key, ())),
                    )
                    for item in request.plan.index
                )
                expected_scope = PreparedFlashcardScope.prepare(
                    expected_index,
                    wrapper.prepared_scope.evidence,
                )
                expected_wrapper = PreparedPlannedFlashcardScope.prepare(
                    expected_scope,
                    request.plan,
                    bundle.bundle_id,
                )
                if wrapper != expected_wrapper:
                    raise ValueError("checkpoint prepared scope differs from lesson plan")
            if page.child_task_bytes is not None:
                from study_agent.workers.contracts import GenerationWorkerTask

                task = GenerationWorkerTask.from_bytes(page.child_task_bytes)
                if task.task_id != page.child_task_id:
                    raise ValueError("checkpoint child task identity changed")
        object.__setattr__(self, "pages", pages)
        if len(self.to_bytes()) > MAX_LESSON_WORKER_CHECKPOINT_BYTES:
            raise ValueError("lesson_worker_checkpoint_limit_exceeded")

    @property
    def fingerprint(self) -> str:
        return _fingerprint(_CHECKPOINT_DOMAIN, self.to_json())

    @property
    def request(self) -> LessonWorkerRequest:
        return LessonWorkerRequest.from_bytes(self.request_bytes)

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "request_bytes": base64.b64encode(self.request_bytes).decode("ascii"),
                "request_fingerprint": self.request_fingerprint,
                "authority_fingerprint": self.authority_fingerprint,
                "run_id": str(self.run_id),
                "pages": tuple(item.to_json() for item in self.pages),
            }
        )

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> LessonWorkerCheckpoint:
        if len(data) > MAX_LESSON_WORKER_CHECKPOINT_BYTES:
            raise ValueError("lesson_worker_checkpoint_limit_exceeded")
        value = _decode_object(data, "lesson worker checkpoint")
        _exact(
            value,
            {"request_bytes", "request_fingerprint", "authority_fingerprint", "run_id", "pages"},
            "lesson worker checkpoint",
        )
        checkpoint = cls(
            base64.b64decode(_string(value, "request_bytes"), validate=True),
            _string(value, "request_fingerprint"),
            _string(value, "authority_fingerprint"),
            RunId(_string(value, "run_id")),
            tuple(
                LessonWorkerPageCheckpoint.from_json(_mapping(item, "page"))
                for item in _array(value, "pages")
            ),
        )
        if checkpoint.to_bytes() != data:
            raise ValueError("lesson worker checkpoint bytes are not canonical")
        return checkpoint


def revision_commitments_fingerprint(
    commitments: tuple[RevisionContentCommitment, ...],
) -> str:
    return _fingerprint(
        _REVISION_DOMAIN,
        freeze_object({"commitments": tuple(item.to_json() for item in commitments)}),
    )


def lesson_run_id(request: LessonWorkerRequest, authority_fingerprint: str) -> RunId:
    _sha(authority_fingerprint, "authority_fingerprint")
    digest = _fingerprint(
        _RUN_DOMAIN,
        freeze_object(
            {
                "request_fingerprint": request.fingerprint,
                "authority_fingerprint": authority_fingerprint,
            }
        ),
    )
    return RunId(f"lesson-worker-sha256:{digest}")


def child_task_id(
    run_id: RunId,
    request: LessonWorkerRequest,
    bundle: PlannedFlashcardBundle,
    wrapper: PreparedPlannedFlashcardScope | None,
) -> str:
    payload = freeze_object(
        {
            "lesson_run_id": str(run_id),
            "plan_fingerprint": request.plan.plan_fingerprint,
            "profile_expectation_fingerprint": request.profile_expectation.fingerprint,
            "bundle_position": bundle.relative_position,
            "bundle_id": bundle.bundle_id,
            "wrapper_fingerprint": wrapper.wrapper_fingerprint if wrapper else None,
            "read_set_fingerprint": (
                wrapper.prepared_scope.evidence.read_set_fingerprint if wrapper else None
            ),
            "revision_commitments_fingerprint": request.revision_commitments_fingerprint,
        }
    )
    return f"lesson-child-sha256:{_fingerprint(_CHILD_DOMAIN, payload)}"


def authority_fingerprint(value: JsonObject) -> str:
    return _fingerprint(_AUTHORITY_DOMAIN, value)


def _plan_revision_ids(plan: FlashcardLessonPlan) -> set[str]:
    result = {
        str(topic.span.revision_id) for topic in plan.unit.topics
    } | {str(paragraph.span.revision_id) for paragraph in plan.unit.paragraphs}
    result.update(str(item.span.revision_id) for item in plan.index)
    result.update(str(slot.span.revision_id) for bundle in plan.bundles for slot in bundle.slots)
    return result


def _canonical_summary(value: JsonObject) -> bytes:
    try:
        return json.dumps(
            _plain(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("continuation summary must be canonical JSON") from error


def _plain(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _reject_private_summary_keys(value: JsonValue, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            camel_split = _CAMEL_BOUNDARY.sub("_", key)
            normalized = _NON_ALPHANUMERIC.sub("_", camel_split.lower()).strip("_")
            if normalized in _FORBIDDEN_SUMMARY_KEYS or normalized.endswith(
                ("_api_key", "_secret", "_password", "_credential", "_token")
            ):
                raise ValueError(f"{path} contains forbidden structural field {key!r}")
            _reject_private_summary_keys(item, f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            _reject_private_summary_keys(item, f"{path}[{index}]")


def _fingerprint(domain: str, value: JsonObject) -> str:
    return sha256(domain.encode() + b"\0" + canonical_json_bytes(value)).hexdigest()


def _decode_object(data: bytes, name: str) -> JsonObject:
    try:
        decoded: Any = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} must be JSON") from error
    frozen = freeze_json(cast(JsonValue, decoded))
    if not isinstance(frozen, Mapping):
        raise ValueError(f"{name} must be an object")
    return freeze_object(frozen)


def _exact(value: Mapping[str, JsonValue], fields: set[str], name: str) -> None:
    if set(value) != fields:
        raise ValueError(f"{name} must contain exactly {sorted(fields)}")


def _mapping(value: JsonValue, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _array(value: Mapping[str, JsonValue], key: str) -> tuple[JsonValue, ...]:
    raw = value[key]
    if not isinstance(raw, tuple):
        raise ValueError(f"{key} must be an array")
    return raw


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    raw = value[key]
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be text")
    return raw


def _optional_string(value: Mapping[str, JsonValue], key: str) -> str | None:
    raw = value[key]
    if raw is not None and not isinstance(raw, str):
        raise ValueError(f"{key} must be text or null")
    return raw


def _integer(value: Mapping[str, JsonValue], key: str) -> int:
    raw = value[key]
    if type(raw) is not int:
        raise ValueError(f"{key} must be an integer")
    return raw


def _strings(value: Mapping[str, JsonValue], key: str) -> tuple[str, ...]:
    raw = _array(value, key)
    if not all(isinstance(item, str) for item in raw):
        raise ValueError(f"{key} must contain only text")
    return cast(tuple[str, ...], raw)


def _text(value: str, name: str, maximum: int) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")


def _sha(value: str, name: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256")


def _position(value: int) -> None:
    if type(value) is not int or not 0 <= value < MAX_LESSON_WORKER_PAGES:
        raise ValueError("page position must be between 0 and 255")


def _b64(value: bytes | None) -> str | None:
    return base64.b64encode(value).decode("ascii") if value is not None else None


def _unb64(value: JsonValue, name: str) -> bytes | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be base64 text or null")
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as error:
        raise ValueError(f"{name} must be valid base64") from error


__all__ = [
    "LessonWorkerCheckpoint",
    "LessonWorkerPageCheckpoint",
    "LessonWorkerPageReceipt",
    "LessonWorkerPageStatus",
    "LessonWorkerRequest",
    "LessonWorkerStatus",
    "ProfileTaskExpectation",
    "ResolvedPlannedBundleEvidence",
    "RevisionContentCommitment",
    "VerifiedFlashcardPageResult",
    "authority_fingerprint",
    "child_task_id",
    "lesson_run_id",
    "revision_commitments_fingerprint",
]
