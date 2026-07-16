"""Proof-bound recovery of provider-neutral free-response grades."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from study_agent.capabilities.bindings import CapabilityBinding
from study_agent.capabilities.builtin import GRADE_RESPONSE_MANIFEST
from study_agent.domain import (
    ArtifactRevisionId,
    AttemptId,
    CourseId,
    CriterionStatus,
    ExecutionContext,
    GradeStatus,
    PresentationId,
    RunId,
    SessionId,
)
from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.playbooks import playbook_definition_fingerprint
from study_agent.ports import SourceContentPort
from study_agent.ports.assessment import VerifiedGradeOwnerStore
from study_agent.skills.builtin.grade_response import GRADE_RESPONSE_OUTPUT_SCHEMA
from study_agent.state import canonical_json_bytes
from study_agent.tools.schema import validate_schema_definition
from study_agent.workers import (
    GenerationWorkerReceipt,
    GenerationWorkerStatus,
    GenerationWorkerTask,
    GenerationWorkerTaskKind,
    ObservedValidationReceipt,
    ValidationExpectation,
    ValidationReceiptSource,
    VerifiedChildExecutionProof,
    generation_worker_child_context,
)
from study_agent.workers.contracts import fingerprint_output_schema, fingerprint_validations

from .contracts import (
    CriterionResult,
    RationalScore,
    ValidatorReceipt,
    VerifiedCapabilityGradeProvenance,
)
from .grade_scope import PreparedGradeScope

_OWNER_DOMAIN = b"verified-grade-owner@1\0"
_MAX_OWNER_BYTES = 768 * 1024


class VerifiedGradeConflictError(RuntimeError):
    """A grading run or its immutable proof commitments changed."""


class VerifiedGradeProofReader(Protocol):
    def load(
        self,
        task: GenerationWorkerTask,
        run_id: RunId,
        receipt: GenerationWorkerReceipt,
        context: ExecutionContext,
    ) -> VerifiedChildExecutionProof: ...


@dataclass(frozen=True, slots=True)
class VerifiedGradeOwnerReceipt:
    run_id: RunId
    course_id: CourseId
    session_id: SessionId
    attempt_id: AttemptId
    presentation_id: PresentationId
    revision_id: ArtifactRevisionId
    artifact_content_fingerprint: str
    response_fingerprint: str
    rubric_fingerprint: str
    prepared_scope_fingerprint: str
    task_bytes: bytes
    worker_receipt_bytes: bytes
    proof_fingerprint: str

    def __post_init__(self) -> None:
        for identity, expected, name in (
            (self.run_id, RunId, "run_id"),
            (self.course_id, CourseId, "course_id"),
            (self.session_id, SessionId, "session_id"),
            (self.attempt_id, AttemptId, "attempt_id"),
            (self.presentation_id, PresentationId, "presentation_id"),
            (self.revision_id, ArtifactRevisionId, "revision_id"),
        ):
            if not isinstance(identity, expected):
                raise TypeError(f"verified grade owner {name} has the wrong type")
        task = GenerationWorkerTask.from_bytes(self.task_bytes)
        receipt = GenerationWorkerReceipt.from_bytes(self.worker_receipt_bytes)
        if (
            task.task_kind is not GenerationWorkerTaskKind.GRADE_RESPONSE
            or receipt.status is not GenerationWorkerStatus.COMPLETED
            or receipt.child_run_id != self.run_id
            or receipt.task_fingerprint != task.fingerprint
        ):
            raise ValueError("verified grade owner task or receipt is inconsistent")
        for fingerprint, name in (
            (self.artifact_content_fingerprint, "artifact_content_fingerprint"),
            (self.response_fingerprint, "response_fingerprint"),
            (self.rubric_fingerprint, "rubric_fingerprint"),
            (self.prepared_scope_fingerprint, "prepared_scope_fingerprint"),
            (self.proof_fingerprint, "proof_fingerprint"),
        ):
            _sha(fingerprint, name)

    @property
    def fingerprint(self) -> str:
        return sha256(_OWNER_DOMAIN + self.to_bytes()).hexdigest()

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "run_id": str(self.run_id),
                "course_id": str(self.course_id),
                "session_id": str(self.session_id),
                "attempt_id": str(self.attempt_id),
                "presentation_id": str(self.presentation_id),
                "revision_id": str(self.revision_id),
                "artifact_content_fingerprint": self.artifact_content_fingerprint,
                "response_fingerprint": self.response_fingerprint,
                "rubric_fingerprint": self.rubric_fingerprint,
                "prepared_scope_fingerprint": self.prepared_scope_fingerprint,
                "task_bytes": base64.b64encode(self.task_bytes).decode("ascii"),
                "worker_receipt_bytes": base64.b64encode(self.worker_receipt_bytes).decode(
                    "ascii"
                ),
                "proof_fingerprint": self.proof_fingerprint,
            }
        )

    def to_bytes(self) -> bytes:
        encoded = canonical_json_bytes(self.to_json())
        if len(encoded) > _MAX_OWNER_BYTES:
            raise ValueError("verified grade owner exceeds 768 KiB")
        return encoded

    @classmethod
    def from_bytes(cls, data: bytes) -> VerifiedGradeOwnerReceipt:
        if not isinstance(data, bytes) or len(data) > _MAX_OWNER_BYTES:
            raise ValueError("verified grade owner bytes are invalid")
        try:
            raw = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("verified grade owner is not canonical JSON") from error
        fields = {
            "run_id",
            "course_id",
            "session_id",
            "attempt_id",
            "presentation_id",
            "revision_id",
            "artifact_content_fingerprint",
            "response_fingerprint",
            "rubric_fingerprint",
            "prepared_scope_fingerprint",
            "task_bytes",
            "worker_receipt_bytes",
            "proof_fingerprint",
        }
        if not isinstance(raw, dict) or set(raw) != fields:
            raise ValueError("verified grade owner fields are not exact")
        owner = cls(
            RunId(_string(raw, "run_id")),
            CourseId(_string(raw, "course_id")),
            SessionId(_string(raw, "session_id")),
            AttemptId(_string(raw, "attempt_id")),
            PresentationId(_string(raw, "presentation_id")),
            ArtifactRevisionId(_string(raw, "revision_id")),
            _string(raw, "artifact_content_fingerprint"),
            _string(raw, "response_fingerprint"),
            _string(raw, "rubric_fingerprint"),
            _string(raw, "prepared_scope_fingerprint"),
            _base64(raw, "task_bytes"),
            _base64(raw, "worker_receipt_bytes"),
            _string(raw, "proof_fingerprint"),
        )
        if owner.to_bytes() != data:
            raise ValueError("verified grade owner bytes are not canonical")
        return owner


class VerifiedGradeOwnerRegistry:
    def __init__(self, store: VerifiedGradeOwnerStore) -> None:
        self._store = store

    def create(self, owner: VerifiedGradeOwnerReceipt) -> VerifiedGradeOwnerReceipt:
        if not isinstance(owner, VerifiedGradeOwnerReceipt):
            raise TypeError("owner must be VerifiedGradeOwnerReceipt")
        payload = owner.to_bytes()
        if self._store.create(owner.run_id, payload):
            return owner
        existing = self.load(owner.run_id)
        if existing.to_bytes() != payload:
            raise VerifiedGradeConflictError("grading run already has another owner")
        return existing

    def load(self, run_id: RunId) -> VerifiedGradeOwnerReceipt:
        if not isinstance(run_id, RunId):
            raise TypeError("run_id must be RunId")
        owner = VerifiedGradeOwnerReceipt.from_bytes(self._store.load(run_id))
        if owner.run_id != run_id:
            raise VerifiedGradeConflictError("verified grade owner run identity changed")
        return owner


class GradeResponseTaskFactory:
    def __init__(self, binding: CapabilityBinding) -> None:
        if binding.manifest != GRADE_RESPONSE_MANIFEST:
            raise ValueError("grade task factory requires grade_response@1")
        self._binding = binding

    def build(
        self, attempt_id: AttemptId, language: str, opaque_request_key: str
    ) -> GenerationWorkerTask:
        if not isinstance(attempt_id, AttemptId):
            raise TypeError("attempt_id must be AttemptId")
        if not language or language != language.strip() or len(language) > 64:
            raise ValueError("language must be bounded trimmed text")
        if not opaque_request_key or not opaque_request_key.replace("-", "").isalnum():
            raise ValueError("opaque request key must be portable")
        binding = self._binding
        payload = freeze_object({"attempt_id": str(attempt_id), "language": language})
        identity = sha256(
            b"grade-response-task@1\0"
            + canonical_json_bytes(payload)
            + b"\0"
            + opaque_request_key.encode()
        ).hexdigest()
        schema = GRADE_RESPONSE_OUTPUT_SCHEMA.value
        validate_schema_definition(schema)
        return GenerationWorkerTask(
            f"grade-response-sha256:{identity}",
            GenerationWorkerTaskKind.GRADE_RESPONSE,
            binding.manifest.id,
            binding.manifest.version,
            binding.manifest_fingerprint,
            binding.manifest.required_authority,
            binding.pins,
            playbook_definition_fingerprint(binding.playbook),
            language,
            {},
            None,
            (f"attempt:{attempt_id}",),
            (),
            payload,
            schema,
            fingerprint_output_schema(schema),
            grade_response_validation_expectations(),
        )


def grade_response_validation_expectations() -> tuple[ValidationExpectation, ...]:
    return (
        ValidationExpectation(
            "check_grade_readiness",
            ValidationReceiptSource.VALIDATE_STEP,
            "grade_response_readiness",
            "1.0.0",
        ),
        ValidationExpectation(
            "grade_free_response",
            ValidationReceiptSource.STRUCTURED_OUTPUT_FALLBACK,
            "grade_response_integrity",
            "1.0.0",
        ),
        ValidationExpectation(
            "validate_grade",
            ValidationReceiptSource.VALIDATE_STEP,
            "grade_response_integrity",
            "1.0.0",
        ),
    )


class VerifiedGradeOwnerWriter:
    def __init__(
        self,
        owners: VerifiedGradeOwnerRegistry,
        proofs: VerifiedGradeProofReader,
    ) -> None:
        self._owners = owners
        self._proofs = proofs

    def publish(
        self,
        task: GenerationWorkerTask,
        receipt: GenerationWorkerReceipt,
        context: ExecutionContext,
    ) -> VerifiedGradeOwnerReceipt:
        proof = self._proofs.load(
            task,
            receipt.child_run_id,
            receipt,
            generation_worker_child_context(task, context),
        )
        _verify_execution(task, receipt, proof)
        scope = _prepared_scope(proof)
        _verify_task_scope(task, scope)
        _verify_context(scope, context)
        owner = VerifiedGradeOwnerReceipt(
            proof.run_id,
            scope.course_id,
            scope.session_id,
            scope.attempt_id,
            scope.presentation_id,
            scope.revision_id,
            scope.artifact_content_fingerprint,
            scope.response_fingerprint,
            scope.rubric_fingerprint,
            scope.scope_fingerprint,
            task.to_bytes(),
            receipt.to_bytes(),
            proof.fingerprint,
        )
        return self._owners.create(owner)


@dataclass(frozen=True, slots=True)
class VerifiedGradeOutcome:
    course_id: CourseId
    session_id: SessionId
    attempt_id: AttemptId
    presentation_id: PresentationId
    revision_id: ArtifactRevisionId
    artifact_content_fingerprint: str
    response_fingerprint: str
    status: GradeStatus
    criterion_results: tuple[CriterionResult, ...]
    score: RationalScore
    provenance: VerifiedCapabilityGradeProvenance


@dataclass(frozen=True, slots=True)
class VerifiedGradeRuntime:
    """Shared owner/proof graph for publication and later grade recovery."""

    owners: VerifiedGradeOwnerRegistry
    writer: VerifiedGradeOwnerWriter
    grades: VerifiedGradeAdapter


class VerifiedGradeAdapter:
    def __init__(
        self,
        owners: VerifiedGradeOwnerRegistry,
        proofs: VerifiedGradeProofReader,
        content: SourceContentPort,
    ) -> None:
        self._owners = owners
        self._proofs = proofs
        self._content = content

    def recover(self, run_id: RunId, context: ExecutionContext) -> VerifiedGradeOutcome:
        owner = self._owners.load(run_id)
        if owner.course_id != context.course_id or owner.session_id != context.session_id:
            raise VerifiedGradeConflictError("verified grade owner belongs to another context")
        task = GenerationWorkerTask.from_bytes(owner.task_bytes)
        receipt = GenerationWorkerReceipt.from_bytes(owner.worker_receipt_bytes)
        proof = self._proofs.load(
            task,
            run_id,
            receipt,
            generation_worker_child_context(task, context),
        )
        _verify_execution(task, receipt, proof)
        if proof.fingerprint != owner.proof_fingerprint:
            raise VerifiedGradeConflictError("verified grade proof changed")
        scope = _prepared_scope(proof)
        _verify_task_scope(task, scope)
        _verify_owner_scope(owner, scope)
        for evidence in scope.evidence:
            resolved = self._content.resolve(evidence.citation)
            if resolved.citation != evidence.citation or resolved.text != evidence.text:
                raise VerifiedGradeConflictError("verified grade evidence changed")
        status, criteria, score = _outcome(proof.output, scope)
        validators = tuple(_validator(item) for item in proof.validations)
        provenance = VerifiedCapabilityGradeProvenance(
            proof.run_id,
            task.capability_id.value,
            str(task.capability_version),
            task.manifest_fingerprint,
            proof.definition_fingerprint,
            proof.fingerprint,
            proof.prompt.composition_fingerprint,
            sha256(
                b"verified-grade-model@1\0" + canonical_json_bytes(proof.model.to_json())
            ).hexdigest(),
            validators,
            scope.rubric_fingerprint,
        )
        return VerifiedGradeOutcome(
            scope.course_id,
            scope.session_id,
            scope.attempt_id,
            scope.presentation_id,
            scope.revision_id,
            scope.artifact_content_fingerprint,
            scope.response_fingerprint,
            status,
            criteria,
            score,
            provenance,
        )


def compose_verified_grade_runtime(
    *,
    owner_store: VerifiedGradeOwnerStore,
    proofs: VerifiedGradeProofReader,
    content: SourceContentPort,
) -> VerifiedGradeRuntime:
    owners = VerifiedGradeOwnerRegistry(owner_store)
    return VerifiedGradeRuntime(
        owners,
        VerifiedGradeOwnerWriter(owners, proofs),
        VerifiedGradeAdapter(owners, proofs, content),
    )


def _verify_execution(
    task: GenerationWorkerTask,
    receipt: GenerationWorkerReceipt,
    proof: VerifiedChildExecutionProof,
) -> None:
    if (
        task.task_kind is not GenerationWorkerTaskKind.GRADE_RESPONSE
        or task.capability_id != GRADE_RESPONSE_MANIFEST.id
        or task.capability_version != GRADE_RESPONSE_MANIFEST.version
        or task.manifest_fingerprint != GRADE_RESPONSE_MANIFEST.fingerprint
        or task.payload.get("attempt_id") is None
        or receipt.status is not GenerationWorkerStatus.COMPLETED
        or receipt.task_id != task.task_id
        or receipt.task_kind is not task.task_kind
        or receipt.child_run_id != proof.run_id
        or receipt.task_fingerprint != task.fingerprint
        or receipt.pins_fingerprint != task.pins_fingerprint
        or receipt.input_fingerprint != task.payload_fingerprint
        or receipt.output_fingerprint != proof.output_fingerprint
        or receipt.validator_fingerprint != fingerprint_validations(proof.validations)
        or receipt.prompt_fingerprint != proof.prompt.composition_fingerprint
        or proof.status is not GenerationWorkerStatus.COMPLETED
        or proof.input_fingerprint != task.payload_fingerprint
        or proof.definition_fingerprint != task.definition_fingerprint
        or proof.pins != task.pins
        or tuple(
            (item.step_id, item.source, item.validator_id, item.validator_version)
            for item in proof.validations
        )
        != tuple(
            (item.step_id, item.source, item.validator_id, item.validator_version)
            for item in task.expected_validations
        )
    ):
        raise VerifiedGradeConflictError("verified grading execution commitments changed")


def _verify_task_scope(task: GenerationWorkerTask, scope: PreparedGradeScope) -> None:
    if task.payload != freeze_object(
        {"attempt_id": str(scope.attempt_id), "language": scope.language}
    ):
        raise VerifiedGradeConflictError("verified grade task names another prepared scope")


def _prepared_scope(proof: VerifiedChildExecutionProof) -> PreparedGradeScope:
    matches = tuple(
        item
        for item in proof.tool_outputs
        if item.step_id == "prepare_grade_scope"
        and item.output_key == "prepared_grade"
        and item.tool_id == "assessment.prepare_grade_scope"
        and item.tool_version == "1.0.0"
    )
    if len(matches) != 1 or not isinstance(matches[0].value, Mapping):
        raise VerifiedGradeConflictError("verified grade prepared scope is unavailable")
    value = matches[0].value
    if set(value) != {"prepared_scope", "prompt_projection"}:
        raise VerifiedGradeConflictError("verified grade prepared wrapper changed")
    scope = PreparedGradeScope.from_json(value["prepared_scope"])
    if value["prompt_projection"] != scope.prompt_projection:
        raise VerifiedGradeConflictError("verified grade prompt projection changed")
    return scope


def _verify_context(scope: PreparedGradeScope, context: ExecutionContext) -> None:
    if scope.course_id != context.course_id or scope.session_id != context.session_id:
        raise VerifiedGradeConflictError("prepared grade belongs to another context")


def _verify_owner_scope(
    owner: VerifiedGradeOwnerReceipt, scope: PreparedGradeScope
) -> None:
    if (
        owner.course_id != scope.course_id
        or owner.session_id != scope.session_id
        or owner.attempt_id != scope.attempt_id
        or owner.presentation_id != scope.presentation_id
        or owner.revision_id != scope.revision_id
        or owner.artifact_content_fingerprint != scope.artifact_content_fingerprint
        or owner.response_fingerprint != scope.response_fingerprint
        or owner.rubric_fingerprint != scope.rubric_fingerprint
        or owner.prepared_scope_fingerprint != scope.scope_fingerprint
    ):
        raise VerifiedGradeConflictError("verified grade prepared scope changed")


def _outcome(
    raw: JsonValue, scope: PreparedGradeScope
) -> tuple[GradeStatus, tuple[CriterionResult, ...], RationalScore]:
    if not isinstance(raw, Mapping) or set(raw) != {"status", "criteria", "score"}:
        raise VerifiedGradeConflictError("verified grade output fields are not exact")
    criteria_raw = raw["criteria"]
    score_raw = raw["score"]
    if not isinstance(criteria_raw, tuple) or not isinstance(score_raw, Mapping):
        raise VerifiedGradeConflictError("verified grade output is malformed")
    if set(score_raw) != {"numerator", "denominator"}:
        raise VerifiedGradeConflictError("verified grade score fields are not exact")
    results: list[CriterionResult] = []
    for item in criteria_raw:
        if not isinstance(item, Mapping) or set(item) != {
            "criterion",
            "status",
            "rationale",
            "evidence_ids",
            "confidence",
            "evidence_insufficient",
        }:
            raise VerifiedGradeConflictError("verified grade criterion fields are not exact")
        results.append(
            CriterionResult(
                _mapping_string(item, "criterion"),
                CriterionStatus(_mapping_string(item, "status")),
                _mapping_string(item, "rationale"),
            )
        )
    if tuple(item.criterion for item in results) != scope.rubric:
        raise VerifiedGradeConflictError("verified grade rubric changed")
    numerator = score_raw.get("numerator")
    denominator = score_raw.get("denominator")
    if type(numerator) is not int or type(denominator) is not int:
        raise VerifiedGradeConflictError("verified grade score must be integral")
    score = RationalScore(numerator, denominator)
    if score.denominator != len(results) or score.numerator != sum(
        item.status is CriterionStatus.MET for item in results
    ):
        raise VerifiedGradeConflictError("verified grade score is not derived")
    status_raw = raw["status"]
    if not isinstance(status_raw, str):
        raise VerifiedGradeConflictError("verified grade status is invalid")
    status = GradeStatus(status_raw)
    expected = (
        GradeStatus.UNGRADABLE
        if all(
            isinstance(item, Mapping) and item.get("evidence_insufficient") is True
            for item in criteria_raw
        )
        else GradeStatus.NEEDS_REVIEW
        if any(item.status is CriterionStatus.UNCERTAIN for item in results)
        else GradeStatus.GRADED
    )
    if status is not expected:
        raise VerifiedGradeConflictError("verified grade status is not derived")
    return status, tuple(results), score


def _validator(value: ObservedValidationReceipt) -> ValidatorReceipt:
    if not value.passed:
        raise VerifiedGradeConflictError("verified grade contains a failed validator")
    return ValidatorReceipt(
        value.validator_id,
        value.validator_version,
        value.result_fingerprint,
        True,
    )


def _string(value: dict[str, object], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be text")
    return raw


def _mapping_string(value: Mapping[str, JsonValue], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str):
        raise VerifiedGradeConflictError(f"{key} must be text")
    return raw


def _base64(value: dict[str, object], key: str) -> bytes:
    try:
        return base64.b64decode(_string(value, key), validate=True)
    except ValueError as error:
        raise ValueError(f"{key} must be canonical base64") from error


def _sha(value: str, name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be lowercase SHA-256")


__all__ = [
    "GradeResponseTaskFactory",
    "VerifiedGradeAdapter",
    "VerifiedGradeConflictError",
    "VerifiedGradeOutcome",
    "VerifiedGradeOwnerReceipt",
    "VerifiedGradeOwnerRegistry",
    "VerifiedGradeOwnerWriter",
    "VerifiedGradeProofReader",
    "VerifiedGradeRuntime",
    "compose_verified_grade_runtime",
    "grade_response_validation_expectations",
]
