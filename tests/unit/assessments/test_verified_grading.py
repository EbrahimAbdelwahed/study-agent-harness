from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from study_agent.assessments import (
    CriterionResult,
    FreeResponse,
    ProjectionAssessmentView,
    RationalScore,
    ValidatorReceipt,
    VerifiedCapabilityGradeProvenance,
    grade_response_binding,
    response_fingerprint,
)
from study_agent.assessments.grade_scope import (
    GradeEvidence,
    PreparedGradeScope,
    evidence_handle,
    rubric_fingerprint,
    source_commitments_fingerprint,
)
from study_agent.assessments.service import (
    AssessmentCommandError,
    AssessmentConflictError,
    AssessmentService,
    RetryableAssessmentConflictError,
)
from study_agent.assessments.verified_grading import (
    GradeResponseTaskFactory,
    VerifiedGradeAdapter,
    VerifiedGradeConflictError,
    VerifiedGradeOutcome,
    VerifiedGradeOwnerReceipt,
    VerifiedGradeOwnerRegistry,
    VerifiedGradeOwnerWriter,
)
from study_agent.domain import (
    ArtifactRevisionId,
    AssessmentFormat,
    AttemptId,
    ChunkId,
    Citation,
    CorrelationId,
    CourseId,
    CriterionStatus,
    ExecutionContext,
    GradeStatus,
    PrincipalKind,
    ResolvedCitation,
    RevisionId,
    RunId,
    SessionId,
    SourceId,
)
from study_agent.domain._validation import freeze_object
from study_agent.playbooks import ValidatorDisposition
from study_agent.skills import ArtifactReference, SemanticVersion
from study_agent.workers import (
    GenerationWorkerReceipt,
    GenerationWorkerStatus,
    ObservedValidationReceipt,
    TechnicalModelReceipt,
    VerifiedChildExecutionProof,
    VerifiedPromptReceipt,
    VerifiedToolOutput,
    generation_worker_child_context,
)
from study_agent.workers.contracts import fingerprint_output, fingerprint_validations
from study_agent.workers.proof import verified_child_value_fingerprint
from tests.unit.assessments.test_assessment_service import (
    REVISION,
    Artifacts,
    Clock,
    MemoryEvents,
    Sessions,
    _content,
    _context,
)

SHA_A = "a" * 64
SHA_B = "b" * 64


class _OwnerStore:
    def __init__(self) -> None:
        self.values: dict[RunId, bytes] = {}

    def create(self, run_id: RunId, payload: bytes) -> bool:
        if run_id in self.values:
            return False
        self.values[run_id] = payload
        return True

    def load(self, run_id: RunId) -> bytes:
        return self.values[run_id]


class _Proofs:
    def __init__(self, proof: VerifiedChildExecutionProof) -> None:
        self.proof = proof
        self.contexts: list[ExecutionContext] = []

    def load(self, task, run_id, receipt, context):  # type: ignore[no-untyped-def]
        assert run_id == self.proof.run_id
        self.contexts.append(context)
        return self.proof


class _Content:
    def __init__(self, scope: PreparedGradeScope, *, changed: bool = False) -> None:
        self.scope = scope
        self.changed = changed

    def get_text(self, revision_id: RevisionId) -> str:
        raise AssertionError(f"unexpected text load: {revision_id}")

    def resolve(self, citation: Citation) -> ResolvedCitation:
        if self.changed:
            return ResolvedCitation(replace(citation, quoted_snippet=None), "changed")
        return ResolvedCitation(citation, citation.quoted_snippet or "")


def _parent() -> ExecutionContext:
    return ExecutionContext(
        PrincipalKind.SERVICE,
        "assessment-host",
        CourseId("course"),
        CorrelationId("verified-grade"),
        frozenset({"source.read"}),
        SessionId("session"),
        idempotency_key="grade-request",
    )


def _binding():  # type: ignore[no-untyped-def]
    version = SemanticVersion.parse("1.0.0")
    return grade_response_binding(
        dependency_resolver=lambda **_kwargs: (),
        model_adapter=ArtifactReference("fixture-adapter", version),
        state_contract=ArtifactReference("fixture-state", version),
    )


def _scope(task_attempt_id=None) -> PreparedGradeScope:  # type: ignore[no-untyped-def]
    text = "The valve prevents diastolic backflow."
    citation = Citation(
        SourceId("source"),
        RevisionId("source-revision"),
        ChunkId("chunk"),
        0,
        len(text),
        "Valve",
        text,
    )
    evidence = (GradeEvidence(evidence_handle(citation), citation, text),)
    response = "It prevents backflow."
    from study_agent.domain import AttemptId, PresentationId

    return PreparedGradeScope(
        CourseId("course"),
        SessionId("session"),
        task_attempt_id or AttemptId("attempt"),
        PresentationId("presentation"),
        ArtifactRevisionId("artifact-revision"),
        response,
        response_fingerprint(FreeResponse(response)),
        "It prevents diastolic backflow.",
        ("selection", "exactness"),
        rubric_fingerprint(("selection", "exactness")),
        SHA_A,
        source_commitments_fingerprint(evidence),
        evidence,
        "Italian",
    )


def _material(scope: PreparedGradeScope | None = None):  # type: ignore[no-untyped-def]
    scope = scope or _scope()
    task = GradeResponseTaskFactory(_binding()).build(
        scope.attempt_id, scope.language, "opaque-grade-key"
    )
    output = freeze_object(
        {
            "status": "graded",
            "criteria": tuple(
                {
                    "criterion": criterion,
                    "status": "met",
                    "rationale": "Supported by the immutable evidence.",
                    "evidence_ids": (scope.evidence[0].handle,),
                    "confidence": 0.9,
                    "evidence_insufficient": False,
                }
                for criterion in scope.rubric
            ),
            "score": {"numerator": 2, "denominator": 2},
        }
    )
    validations = tuple(
        ObservedValidationReceipt(
            item.step_id,
            item.source,
            item.validator_id,
            item.validator_version,
            True,
            sha256(f"validator-{index}".encode()).hexdigest(),
            ValidatorDisposition.CONTINUE,
        )
        for index, item in enumerate(task.expected_validations)
    )
    wrapper = freeze_object(
        {"prepared_scope": scope.to_json(), "prompt_projection": scope.prompt_projection}
    )
    proof = VerifiedChildExecutionProof(
        RunId("verified-grade-run"),
        GenerationWorkerStatus.COMPLETED,
        task.definition_fingerprint,
        task.pins,
        task.payload_fingerprint,
        output,
        fingerprint_output(output),
        (),
        (
            VerifiedToolOutput(
                "prepare_grade_scope",
                "prepared_grade",
                "assessment.prepare_grade_scope",
                "1.0.0",
                wrapper,
                verified_child_value_fingerprint(wrapper),
            ),
        ),
        TechnicalModelReceipt("fixture-adapter", "1.0.0", "fixture-model", None, 10, 5),
        VerifiedPromptReceipt("grade_response.v1", "1.0.0", SHA_B),
        validations,
    )
    receipt = GenerationWorkerReceipt(
        task.task_id,
        task.task_kind,
        GenerationWorkerStatus.COMPLETED,
        proof.run_id,
        task.fingerprint,
        task.pins_fingerprint,
        task.payload_fingerprint,
        proof.output_fingerprint,
        fingerprint_validations(validations),
        SHA_A,
        proof.prompt.composition_fingerprint,
    )
    return task, receipt, proof, scope


def test_task_factory_is_stable_provider_neutral_and_child_context_is_derived() -> None:
    binding = _binding()
    task = GradeResponseTaskFactory(binding).build(_scope().attempt_id, "Italian", "key-1")
    retry = GradeResponseTaskFactory(binding).build(_scope().attempt_id, "Italian", "key-1")
    other = GradeResponseTaskFactory(binding).build(_scope().attempt_id, "Italian", "key-2")

    assert task == retry
    assert task.task_id != other.task_id
    assert task.payload == {"attempt_id": "attempt", "language": "Italian"}
    assert "provider" not in task.to_bytes().decode()
    assert generation_worker_child_context(task, _parent()) == generation_worker_child_context(
        task, replace(_parent(), idempotency_key="another-parent-retry")
    )


def test_owner_codec_registry_writer_and_adapter_recover_exact_proof() -> None:
    task, receipt, proof, scope = _material()
    store = _OwnerStore()
    registry = VerifiedGradeOwnerRegistry(store)
    proofs = _Proofs(proof)
    owner = VerifiedGradeOwnerWriter(registry, proofs).publish(task, receipt, _parent())
    recovered = VerifiedGradeAdapter(registry, proofs, _Content(scope)).recover(
        proof.run_id, _parent()
    )

    assert VerifiedGradeOwnerReceipt.from_bytes(owner.to_bytes()) == owner
    assert registry.create(owner) == owner
    assert owner.task_bytes == task.to_bytes()
    assert owner.worker_receipt_bytes == receipt.to_bytes()
    assert proofs.contexts == [
        generation_worker_child_context(task, _parent()),
        generation_worker_child_context(task, _parent()),
    ]
    assert recovered.attempt_id == scope.attempt_id
    assert recovered.score == RationalScore(2, 2)
    assert recovered.provenance.run_id == proof.run_id
    persisted = repr(recovered.provenance).lower()
    assert not any(word in persisted for word in ("credential", "api_key", "provider"))


@pytest.mark.parametrize(
    "mutation, match",
    [
        (
            lambda task, receipt, proof: (
                task,
                replace(receipt, output_fingerprint=SHA_A),
                proof,
            ),
            "execution commitments",
        ),
        (
            lambda task, receipt, proof: (
                task,
                receipt,
                replace(
                    proof,
                    output=freeze_object({"forged": True}),
                    output_fingerprint=fingerprint_output(freeze_object({"forged": True})),
                ),
            ),
            "execution commitments",
        ),
    ],
)
def test_writer_rejects_drift(mutation, match: str) -> None:  # type: ignore[no-untyped-def]
    task, receipt, proof, _ = _material()
    task, receipt, proof = mutation(task, receipt, proof)
    with pytest.raises(VerifiedGradeConflictError, match=match):
        VerifiedGradeOwnerWriter(VerifiedGradeOwnerRegistry(_OwnerStore()), _Proofs(proof)).publish(
            task, receipt, _parent()
        )


def test_registry_rejects_run_reuse_and_adapter_rejects_context_evidence_and_output() -> None:
    task, receipt, proof, scope = _material()
    registry = VerifiedGradeOwnerRegistry(_OwnerStore())
    proofs = _Proofs(proof)
    owner = VerifiedGradeOwnerWriter(registry, proofs).publish(task, receipt, _parent())
    with pytest.raises(VerifiedGradeConflictError, match="another owner"):
        registry.create(replace(owner, response_fingerprint=SHA_B))

    adapter = VerifiedGradeAdapter(registry, proofs, _Content(scope))
    for context in (
        replace(_parent(), session_id=SessionId("other")),
        replace(_parent(), course_id=CourseId("other")),
    ):
        with pytest.raises(VerifiedGradeConflictError, match="another context"):
            adapter.recover(proof.run_id, context)
    with pytest.raises(VerifiedGradeConflictError, match="evidence changed"):
        VerifiedGradeAdapter(registry, proofs, _Content(scope, changed=True)).recover(
            proof.run_id, _parent()
        )
    changed_output = freeze_object({**proof.output, "status": "needs_review"})
    proofs.proof = replace(
        proof, output=changed_output, output_fingerprint=fingerprint_output(changed_output)
    )
    with pytest.raises(VerifiedGradeConflictError, match="commitments changed"):
        adapter.recover(proof.run_id, _parent())


@pytest.mark.parametrize("kind", ["failed", "wrong_identity"])
def test_adapter_rejects_failed_or_wrong_validation_set(kind: str) -> None:
    task, receipt, proof, scope = _material()
    changed = (
        replace(proof.validations[0], passed=False)
        if kind == "failed"
        else replace(proof.validations[0], validator_id="unrelated_validator")
    )
    validations = (changed, *proof.validations[1:])
    changed_proof = replace(proof, validations=validations)
    changed_receipt = replace(receipt, validator_fingerprint=fingerprint_validations(validations))
    registry = VerifiedGradeOwnerRegistry(_OwnerStore())
    proofs = _Proofs(changed_proof)
    if kind == "wrong_identity":
        with pytest.raises(VerifiedGradeConflictError, match="execution commitments"):
            VerifiedGradeOwnerWriter(registry, proofs).publish(task, changed_receipt, _parent())
        return
    VerifiedGradeOwnerWriter(registry, proofs).publish(task, changed_receipt, _parent())
    with pytest.raises(VerifiedGradeConflictError):
        VerifiedGradeAdapter(registry, proofs, _Content(scope)).recover(proof.run_id, _parent())


@pytest.mark.parametrize(
    "status",
    [
        GenerationWorkerStatus.FAILED,
        GenerationWorkerStatus.CANCELLED,
        GenerationWorkerStatus.STALE,
        GenerationWorkerStatus.TERMINATED,
    ],
)
def test_writer_rejects_noncompleted_terminal_receipt(status: GenerationWorkerStatus) -> None:
    task, receipt, proof, _ = _material()
    changed = replace(receipt, status=status, prompt_fingerprint=None, failure_code="failed")
    with pytest.raises(VerifiedGradeConflictError, match="execution commitments"):
        VerifiedGradeOwnerWriter(VerifiedGradeOwnerRegistry(_OwnerStore()), _Proofs(proof)).publish(
            task, changed, _parent()
        )


class _VerifiedPort:
    def __init__(self, outcome: VerifiedGradeOutcome) -> None:
        self.outcome = outcome

    def recover(self, run_id: RunId, context: ExecutionContext) -> VerifiedGradeOutcome:
        assert run_id == self.outcome.provenance.run_id
        return self.outcome


def _verified_service():  # type: ignore[no-untyped-def]
    content = _content(AssessmentFormat.FREE_RESPONSE)
    events = MemoryEvents(content)
    view = ProjectionAssessmentView(lambda _course_id: events.projection)
    service = AssessmentService(events, Clock(), view, Artifacts(content), Sessions())
    presentation = service.present_item(REVISION, _context(PrincipalKind.SERVICE, "present"), 1)
    attempt = service.record_attempt(
        presentation.id,
        FreeResponse("Alpha"),
        20,
        _context(PrincipalKind.HUMAN, "attempt"),
        2,
    )
    provenance = VerifiedCapabilityGradeProvenance(
        RunId("service-grade-run"),
        "grade_response",
        "1.0.0",
        SHA_A,
        SHA_B,
        "c" * 64,
        "d" * 64,
        "e" * 64,
        (ValidatorReceipt("validator", "1.0.0", "f" * 64, True),),
        rubric_fingerprint(presentation.content.evaluation_criteria),
    )
    outcome = VerifiedGradeOutcome(
        presentation.course_id,
        presentation.session_id,
        attempt.id,
        presentation.id,
        presentation.revision_id,
        presentation.content_fingerprint,
        attempt.response_fingerprint,
        GradeStatus.GRADED,
        tuple(
            CriterionResult(item, CriterionStatus.MET, "Verified")
            for item in presentation.content.evaluation_criteria
        ),
        RationalScore(2, 2),
        provenance,
    )
    port = _VerifiedPort(outcome)
    service = AssessmentService(
        events,
        Clock(),
        view,
        Artifacts(content),
        Sessions(),
        verified_grades=port,
    )
    return service, events, outcome, port


def test_service_verified_commit_retry_run_uniqueness_and_contested_regrade() -> None:
    service, events, outcome, port = _verified_service()
    context = _context(PrincipalKind.SERVICE, "grade")
    first = service.record_verified_grade(outcome.provenance.run_id, context, 3)
    assert service.record_verified_grade(outcome.provenance.run_id, context, 4) == first

    port.outcome = replace(
        outcome, provenance=replace(outcome.provenance, run_id=RunId("second-run"))
    )
    service.contest_grade(first.id, "Please review", _context(PrincipalKind.HUMAN, "contest"), 4)
    successor = service.record_verified_grade(
        RunId("second-run"),
        _context(PrincipalKind.SERVICE, "regrade"),
        5,
        supersedes_grade_id=first.id,
    )
    snapshot = ProjectionAssessmentView(lambda _course_id: events.projection).get(
        CourseId("course")
    )
    assert successor.supersedes_grade_id == first.id
    assert len(snapshot.grades) == 2
    assert len(snapshot.contests) == 1

    port.outcome = outcome
    with pytest.raises(AssessmentConflictError, match="already committed"):
        service.record_verified_grade(
            outcome.provenance.run_id,
            _context(PrincipalKind.SERVICE, "reuse-run"),
            6,
        )


def test_service_verified_commit_fails_closed_for_configuration_target_and_predecessor() -> None:
    content = _content(AssessmentFormat.FREE_RESPONSE)
    events = MemoryEvents(content)
    plain = AssessmentService(
        events,
        Clock(),
        ProjectionAssessmentView(lambda _course_id: events.projection),
        Artifacts(content),
        Sessions(),
    )
    with pytest.raises(AssessmentCommandError, match="not configured"):
        plain.record_verified_grade(RunId("run"), _context(PrincipalKind.SERVICE, "grade"), 1)

    service, _, outcome, port = _verified_service()
    port.outcome = replace(outcome, response_fingerprint=SHA_A)
    with pytest.raises(AssessmentConflictError, match="commitments changed"):
        service.record_verified_grade(
            outcome.provenance.run_id,
            _context(PrincipalKind.SERVICE, "grade"),
            3,
        )
    port.outcome = replace(outcome, attempt_id=AttemptId("another-attempt"))
    with pytest.raises(AssessmentCommandError, match="target was not found"):
        service.record_verified_grade(
            outcome.provenance.run_id,
            _context(PrincipalKind.SERVICE, "wrong-attempt"),
            3,
        )
    port.outcome = replace(
        outcome,
        provenance=replace(outcome.provenance, rubric_fingerprint=SHA_A),
    )
    with pytest.raises(AssessmentConflictError, match="rubric changed"):
        service.record_verified_grade(
            outcome.provenance.run_id,
            _context(PrincipalKind.SERVICE, "stale-rubric"),
            3,
        )
    port.outcome = outcome
    from study_agent.domain import GradeId

    with pytest.raises(AssessmentConflictError, match="initial verified grade"):
        service.record_verified_grade(
            outcome.provenance.run_id,
            _context(PrincipalKind.SERVICE, "other-key"),
            3,
            supersedes_grade_id=GradeId("unrelated"),
        )


def test_service_verified_commit_preserves_exact_race_semantics() -> None:
    service, events, outcome, _ = _verified_service()
    events.race_mode = "commit_then_fail"
    committed = service.record_verified_grade(
        outcome.provenance.run_id,
        _context(PrincipalKind.SERVICE, "grade"),
        3,
    )
    assert committed.provenance == outcome.provenance

    service, events, outcome, _ = _verified_service()
    events.race_mode = "fail"
    with pytest.raises(RetryableAssessmentConflictError):
        service.record_verified_grade(
            outcome.provenance.run_id,
            _context(PrincipalKind.SERVICE, "grade"),
            3,
        )


def test_canonical_ledger_and_service_do_not_import_provider_or_proof_store_modules() -> None:
    from pathlib import Path

    package = Path(__file__).parents[3] / "src" / "study_agent" / "assessments"
    for name in ("contracts.py", "events.py", "projection.py", "service.py"):
        source = (package / name).read_text()
        assert "openai" not in source.lower()
        assert "deepseek" not in source.lower()
        assert "VerifiedChildProofStore" not in source
