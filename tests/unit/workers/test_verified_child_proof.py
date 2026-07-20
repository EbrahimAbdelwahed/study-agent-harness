from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
from datetime import UTC, datetime

import pytest

from study_agent.capabilities import TutorCapabilityId
from study_agent.domain import (
    CorrelationId,
    CourseId,
    ExecutionContext,
    PrincipalKind,
    RunId,
    SessionId,
)
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import (
    ModelStep,
    PlaybookDefinition,
    PlaybookRunStatus,
    ReadDependency,
    StepTrace,
    StepTraceStatus,
    ToolBehaviorPin,
    ToolStep,
    ValidateStep,
    ValidatorDisposition,
    VerifiedRunRecord,
    VersionPins,
    playbook_definition_fingerprint,
)
from study_agent.ports import MessageRole, ModelMessage, ModelRequest, StructuredOutputConstraint
from study_agent.skills import ArtifactReference, JsonSchema, SemanticVersion, VersionRange
from study_agent.state import canonical_json_bytes
from study_agent.workers.contracts import (
    ChildCapabilityObservation,
    GenerationWorkerReceipt,
    GenerationWorkerStatus,
    GenerationWorkerTask,
    GenerationWorkerTaskKind,
    ObservedValidationReceipt,
    ValidationExpectation,
    ValidationReceiptSource,
    VerifiedPromptReceipt,
    fingerprint_output,
    fingerprint_output_schema,
    fingerprint_run,
    fingerprint_validations,
)
from study_agent.workers.proof import (
    TechnicalModelReceipt,
    VerifiedChildExecutionProof,
    VerifiedChildExecutionProofView,
    VerifiedChildProofOwner,
    VerifiedToolOutput,
    verified_child_value_fingerprint,
)
from study_agent.workers.service import GenerationWorkerConflictError

V1 = SemanticVersion.parse("1.0.0")
V2 = SemanticVersion.parse("2.0.0")
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
OUTPUT = {"cards": ({"front": "Valve?", "back": "Three cusps."},)}
SCHEMA: JsonObject = {
    "type": "object",
    "required": ("cards",),
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ("front", "back"),
                "properties": {
                    "front": {"type": "string"},
                    "back": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }
    },
    "additionalProperties": False,
}


def _pins() -> VersionPins:
    return VersionPins(
        ArtifactReference("hybrid_flashcards", V1),
        ArtifactReference("hybrid_flashcards_flow", V1),
        ArtifactReference("hybrid_flashcards.v1", V1),
        (ToolBehaviorPin("source.prepare_flashcard_scope", V1),),
        ArtifactReference("model-adapter", V1),
        ArtifactReference("event-state", V1),
    )


def _expected() -> tuple[ValidationExpectation, ...]:
    return (
        ValidationExpectation(
            "generate",
            ValidationReceiptSource.STRUCTURED_OUTPUT_FALLBACK,
            "structured_output_schema",
            "1.0.0",
        ),
        ValidationExpectation(
            "integrity",
            ValidationReceiptSource.VALIDATE_STEP,
            "hybrid_flashcard_integrity",
            "1.0.0",
        ),
    )


def _task(**changes: object) -> GenerationWorkerTask:
    values: dict[str, object] = {
        "task_id": "lesson-1:hybrid",
        "task_kind": GenerationWorkerTaskKind.FLASHCARD_BUNDLE,
        "capability_id": TutorCapabilityId.PROPOSE_FLASHCARDS,
        "capability_version": V1,
        "manifest_fingerprint": SHA_A,
        "required_authority": ("source.read",),
        "pins": _pins(),
        "definition_fingerprint": playbook_definition_fingerprint(_definition()),
        "language": "it",
        "preferences": {"exam_format": "oral"},
        "continuation_summary": None,
        "index_references": ("scope:lesson-1",),
        "evidence_references": ("evidence:chunk-1",),
        "payload": {"query": "Generate cards", "scope": "lesson-1"},
        "output_schema": SCHEMA,
        "output_schema_fingerprint": fingerprint_output_schema(SCHEMA),
        "expected_validations": _expected(),
    }
    values.update(changes)
    return GenerationWorkerTask(**values)  # type: ignore[arg-type]


def _parent(*, principal: str = "tutor-service") -> ExecutionContext:
    return ExecutionContext(
        PrincipalKind.SERVICE,
        principal,
        CourseId("course-1"),
        CorrelationId("parent-correlation"),
        frozenset({"source.read"}),
        SessionId("session-1"),
        idempotency_key="parent-retry",
    )


def _validations() -> tuple[ObservedValidationReceipt, ...]:
    return tuple(
        ObservedValidationReceipt(
            item.step_id,
            item.source,
            item.validator_id,
            item.validator_version,
            True,
            SHA_C if index == 0 else SHA_D,
            ValidatorDisposition.CONTINUE,
        )
        for index, item in enumerate(_expected())
    )


def _prompt() -> VerifiedPromptReceipt:
    return VerifiedPromptReceipt("hybrid_flashcards.v1", "1.0.0", SHA_B, (SHA_C,))


def _proof(**changes: object) -> VerifiedChildExecutionProof:
    tool_value: JsonObject = {
        "scope_id": "scope:lesson-1",
        "paragraphs": ("evidence:chunk-1",),
    }
    values: dict[str, object] = {
        "run_id": RunId("child-run-1"),
        "status": GenerationWorkerStatus.COMPLETED,
        "definition_fingerprint": _task().definition_fingerprint,
        "pins": _pins(),
        "input_fingerprint": _task().payload_fingerprint,
        "output": OUTPUT,
        "output_fingerprint": fingerprint_output(OUTPUT),
        "read_dependencies": (ReadDependency("course", "course-1", "sequence-1"),),
        "tool_outputs": (
            VerifiedToolOutput(
                "prepare",
                "prepared_scope",
                "source.prepare_flashcard_scope",
                "1.0.0",
                tool_value,
                verified_child_value_fingerprint(tool_value),
            ),
        ),
        "model": TechnicalModelReceipt(
            "model-adapter", "1.0.0", "test-model", None, 12, 7
        ),
        "prompt": _prompt(),
        "validations": _validations(),
    }
    values.update(changes)
    return VerifiedChildExecutionProof(**values)  # type: ignore[arg-type]


def _definition() -> PlaybookDefinition:
    return PlaybookDefinition(
        "hybrid_flashcards_flow",
        V1,
        VersionRange(V1, V2),
        (
            ToolStep(
                "prepare",
                ArtifactReference("source.prepare_flashcard_scope", V1),
                {},
                "prepared_scope",
            ),
            ModelStep(
                "generate",
                ArtifactReference("hybrid_flashcards.v1", V1),
                ModelRequest(
                    (ModelMessage(MessageRole.USER, "Generate the verified fixture."),),
                    StructuredOutputConstraint("draft", SCHEMA, True),
                ),
                JsonSchema(SCHEMA),
                "draft",
            ),
            ValidateStep(
                "integrity",
                ArtifactReference("hybrid_flashcard_integrity", V1),
                ("draft",),
                "proposal",
            ),
        ),
        ("query", "scope"),
    )


def _source_run(proof: VerifiedChildExecutionProof | None = None) -> VerifiedRunRecord:
    selected = proof or _proof()
    tool_value = selected.tool_outputs[0].value
    validations = selected.validations
    return VerifiedRunRecord(
        selected.run_id,
        _task().definition_fingerprint,
        _task().capability_inputs(),
        _pins(),
        selected.read_dependencies,
        {"prepared_scope": tool_value, "draft": OUTPUT, "proposal": OUTPUT},
        (
            StepTrace(
                "prepare",
                "tool",
                StepTraceStatus.COMPLETED,
                datetime(2026, 7, 16, tzinfo=UTC),
            ),
            StepTrace(
                "generate",
                "model",
                StepTraceStatus.COMPLETED,
                datetime(2026, 7, 16, tzinfo=UTC),
                {
                    "model_invocation": {
                        "adapter_id": selected.model.adapter_id,
                        "adapter_version": selected.model.adapter_version,
                        "model_id": selected.model.model_id,
                        "response_id": selected.model.response_id,
                    },
                    "model_usage": {
                        "input_tokens": selected.model.input_tokens,
                        "output_tokens": selected.model.output_tokens,
                    },
                    "prompt": {
                        "id": selected.prompt.prompt_id,
                        "version": selected.prompt.prompt_version,
                        "fingerprint": selected.prompt.composition_fingerprint,
                        "layers": tuple(
                            {
                                "id": f"layer-{index}",
                                "version": "1.0.0",
                                "kind": "task_instruction",
                                "input_fingerprint": fingerprint,
                            }
                            for index, fingerprint in enumerate(
                                selected.prompt.layer_fingerprints
                            )
                        ),
                    },
                    "fallback_validators": (
                        {
                            **validations[0].to_json(),
                            "result": OUTPUT,
                            "reason": None,
                        },
                    ),
                },
            ),
            StepTrace(
                "integrity",
                "validate",
                StepTraceStatus.COMPLETED,
                datetime(2026, 7, 16, tzinfo=UTC),
                {
                    "validator": {
                        **validations[1].to_json(),
                        "reason": None,
                    }
                },
            ),
        ),
        PlaybookRunStatus.COMPLETED,
    )


def _create(
    owner: VerifiedChildProofOwner,
    task: GenerationWorkerTask,
    receipt: GenerationWorkerReceipt,
    *,
    run: VerifiedRunRecord | None = None,
    definition: PlaybookDefinition | None = None,
    output: JsonObject = OUTPUT,
) -> VerifiedChildExecutionProofView:
    return owner.create(
        task,
        receipt,
        run or _source_run(),
        definition or _definition(),
        output,
        _parent(),
    )


def _receipt(task: GenerationWorkerTask | None = None) -> GenerationWorkerReceipt:
    selected = task or _task()
    proof = _proof(input_fingerprint=selected.payload_fingerprint, pins=selected.pins)
    observation = ChildCapabilityObservation(
        GenerationWorkerStatus.COMPLETED,
        selected.capability_id,
        selected.capability_version,
        selected.manifest_fingerprint,
        proof.run_id,
        selected.pins,
        selected.definition_fingerprint,
        selected.output_schema_fingerprint,
        validations=proof.validations,
        prompt=proof.prompt,
        verified_run=_source_run(proof),
        output=OUTPUT,
    )
    return GenerationWorkerReceipt(
        selected.task_id,
        selected.task_kind,
        GenerationWorkerStatus.COMPLETED,
        proof.run_id,
        selected.fingerprint,
        selected.pins_fingerprint,
        selected.payload_fingerprint,
        proof.output_fingerprint,
        fingerprint_validations(proof.validations),
        fingerprint_run(observation),
        proof.prompt.composition_fingerprint,
    )


class MemoryProofStore:
    def __init__(self) -> None:
        self.values: dict[RunId, bytes] = {}

    def create(self, run_id: RunId, payload: bytes) -> bool:
        if run_id in self.values:
            return False
        self.values[run_id] = payload
        return True

    def load(self, run_id: RunId) -> bytes:
        return self.values[run_id]


def test_proof_codec_is_exact_canonical_bounded_and_preserves_nullable_response_id() -> None:
    proof = _proof()
    assert VerifiedChildExecutionProof.from_bytes(proof.to_bytes()) == proof
    assert proof.model.response_id is None
    assert proof.to_bytes() == canonical_json_bytes(json.loads(proof.to_bytes()))

    unknown = json.loads(proof.to_bytes())
    unknown["raw_inputs"] = {"secret": True}
    with pytest.raises(ValueError, match="fields are not exact"):
        VerifiedChildExecutionProof.from_bytes(canonical_json_bytes(unknown))
    with pytest.raises(ValueError, match="canonical"):
        VerifiedChildExecutionProof.from_bytes(b" " + proof.to_bytes())
    with pytest.raises(ValueError, match="512 KiB"):
        VerifiedChildExecutionProof.from_bytes(b"{" + b"x" * (512 * 1024))


def test_proof_codec_rejects_malformed_technical_receipt_and_changed_commitments() -> None:
    proof = _proof()
    malformed = json.loads(proof.to_bytes())
    malformed["model"]["response_id"] = 42
    with pytest.raises(ValueError, match="response_id"):
        VerifiedChildExecutionProof.from_bytes(canonical_json_bytes(malformed))

    changed = json.loads(proof.to_bytes())
    changed["output_fingerprint"] = SHA_D
    with pytest.raises(ValueError, match="output fingerprint"):
        VerifiedChildExecutionProof.from_bytes(canonical_json_bytes(changed))


def test_owner_slot_is_exact_retry_and_contains_no_task_or_raw_input_bytes() -> None:
    store = MemoryProofStore()
    owner = VerifiedChildProofOwner(store)
    task = _task()
    receipt = _receipt(task)
    proof = _proof()
    assert _create(owner, task, receipt) == proof
    assert _create(owner, task, receipt) == proof
    assert owner.load(task, proof.run_id, receipt, _parent()) == proof

    raw = store.values[proof.run_id]
    assert task.fingerprint.encode() in raw
    assert task.to_bytes() not in raw
    assert b"Generate cards" not in raw
    assert b'"payload"' not in raw


@pytest.mark.parametrize(
    "changed",
    (
        lambda receipt: replace(receipt, pins_fingerprint=SHA_D),
        lambda receipt: replace(receipt, input_fingerprint=SHA_D),
        lambda receipt: replace(receipt, output_fingerprint=SHA_D),
        lambda receipt: replace(receipt, validator_fingerprint=SHA_D),
        lambda receipt: replace(receipt, run_fingerprint=SHA_D),
        lambda receipt: replace(receipt, prompt_fingerprint=SHA_D),
    ),
)
def test_owner_rejects_every_changed_completed_receipt_commitment(
    changed: Callable[[GenerationWorkerReceipt], GenerationWorkerReceipt],
) -> None:
    task = _task()
    owner = VerifiedChildProofOwner(MemoryProofStore())
    receipt = changed(_receipt(task))
    with pytest.raises(GenerationWorkerConflictError):
        _create(owner, task, receipt)


def test_owner_rejects_changed_task_authority_proof_and_competing_owner() -> None:
    store = MemoryProofStore()
    owner = VerifiedChildProofOwner(store)
    task = _task()
    receipt = _receipt(task)
    proof = _proof()
    _create(owner, task, receipt)

    with pytest.raises(GenerationWorkerConflictError):
        owner.load(replace(task, language="en"), proof.run_id, receipt, _parent())
    with pytest.raises(GenerationWorkerConflictError):
        owner.load(task, proof.run_id, receipt, _parent(principal="other-service"))
    with pytest.raises(GenerationWorkerConflictError):
        _create(
            owner,
            task,
            receipt,
            run=_source_run(
                replace(proof, model=replace(proof.model, model_id="other"))
            ),
        )


@pytest.mark.parametrize(
    "changed",
    (
        lambda proof: replace(
            proof,
            read_dependencies=(ReadDependency("course", "course-1", "sequence-2"),),
        ),
        lambda proof: replace(
            proof,
            tool_outputs=(
                replace(
                    proof.tool_outputs[0],
                    value={"scope_id": "fabricated"},
                    fingerprint=verified_child_value_fingerprint(
                        {"scope_id": "fabricated"}
                    ),
                ),
            ),
        ),
        lambda proof: replace(
            proof, model=replace(proof.model, model_id="fabricated-model")
        ),
        lambda proof: replace(
            proof, model=replace(proof.model, response_id="fabricated-response")
        ),
        lambda proof: replace(
            proof, model=replace(proof.model, input_tokens=13, output_tokens=8)
        ),
    ),
)
def test_exact_owner_slot_rejects_competing_operational_provenance(
    changed: Callable[[VerifiedChildExecutionProof], VerifiedChildExecutionProof],
) -> None:
    store = MemoryProofStore()
    owner = VerifiedChildProofOwner(store)
    task = _task()
    receipt = _receipt(task)
    derived = _proof()
    _create(owner, task, receipt)

    with pytest.raises(GenerationWorkerConflictError, match="another owner"):
        _create(owner, task, receipt, run=_source_run(changed(derived)))

    assert owner.load(task, derived.run_id, receipt, _parent()) == derived
    assert tuple(store.values) == (derived.run_id,)


@pytest.mark.parametrize("mutation", ("step", "tool"))
def test_owner_rejects_fabricated_tool_identity_from_competing_definition(
    mutation: str,
) -> None:
    store = MemoryProofStore()
    owner = VerifiedChildProofOwner(store)
    task = _task()
    receipt = _receipt(task)
    _create(owner, task, receipt)

    definition = _definition()
    first = definition.steps[0]
    assert isinstance(first, ToolStep)
    run = _source_run()
    if mutation == "step":
        changed_first = replace(first, id="fabricated-step")
        traces = list(run.traces)
        traces[0] = replace(traces[0], step_id="fabricated-step")
        run = replace(run, traces=tuple(traces))
    else:
        changed_first = replace(first, tool=ArtifactReference("fabricated.tool", V1))
    changed_definition = replace(
        definition, steps=(changed_first, *definition.steps[1:])
    )

    assert playbook_definition_fingerprint(changed_definition) != (
        task.definition_fingerprint
    )
    with pytest.raises(
        GenerationWorkerConflictError, match="engine run differs from worker task"
    ):
        _create(owner, task, receipt, run=run, definition=changed_definition)
    assert tuple(store.values) == (RunId("child-run-1"),)


def test_empty_owner_rejects_same_identity_definition_with_fabricated_tool_trace() -> None:
    store = MemoryProofStore()
    owner = VerifiedChildProofOwner(store)
    task = _task()
    receipt = _receipt(task)
    definition = _definition()
    first = definition.steps[0]
    assert isinstance(first, ToolStep)
    fabricated_step = replace(
        first,
        id="fabricated-step",
        tool=ArtifactReference("fabricated.tool", V1),
    )
    fabricated_definition = replace(
        definition,
        steps=(fabricated_step, *definition.steps[1:]),
    )
    run = _source_run()
    traces = list(run.traces)
    traces[0] = replace(traces[0], step_id="fabricated-step")
    fabricated_run = replace(run, traces=tuple(traces))

    assert playbook_definition_fingerprint(fabricated_definition) != (
        task.definition_fingerprint
    )
    with pytest.raises(
        GenerationWorkerConflictError, match="engine run differs from worker task"
    ):
        _create(
            owner,
            task,
            receipt,
            run=fabricated_run,
            definition=fabricated_definition,
        )
    assert store.values == {}


def test_concurrent_create_has_one_owner_and_identical_callers_converge() -> None:
    store = MemoryProofStore()
    owner = VerifiedChildProofOwner(store)
    task = _task()
    receipt = _receipt(task)
    proof = _proof()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(
            pool.map(lambda _: _create(owner, task, receipt), range(24))
        )
    assert results == (proof,) * 24
    assert tuple(store.values) == (proof.run_id,)


def test_sanitized_view_has_only_the_pinned_fields() -> None:
    assert VerifiedChildExecutionProofView is VerifiedChildExecutionProof
    assert tuple(item.name for item in fields(VerifiedChildExecutionProofView)) == (
        "run_id",
        "status",
        "definition_fingerprint",
        "pins",
        "input_fingerprint",
        "output",
        "output_fingerprint",
        "read_dependencies",
        "tool_outputs",
        "model",
        "prompt",
        "validations",
        "execution_input_fingerprint",
    )
    rendered = repr(_proof()).lower()
    for forbidden in (
        "verifiedrunrecord",
        "raw_inputs",
        "traces",
        "messages",
        "requests",
        "credentials",
        "principal_id",
        "write_authority",
    ):
        assert forbidden not in rendered


def test_execution_input_commitment_is_conditional_and_old_bytes_stay_stable() -> None:
    ordinary = _proof()
    assert "execution_input_fingerprint" not in ordinary.to_json()
    assert VerifiedChildExecutionProof.from_bytes(ordinary.to_bytes()) == ordinary

    profiled = replace(ordinary, execution_input_fingerprint=SHA_A)
    assert profiled.to_json()["execution_input_fingerprint"] == SHA_A
    assert VerifiedChildExecutionProof.from_bytes(profiled.to_bytes()) == profiled

    redundant = json.loads(ordinary.to_bytes())
    redundant["execution_input_fingerprint"] = ordinary.input_fingerprint
    with pytest.raises(ValueError, match="canonical"):
        VerifiedChildExecutionProof.from_bytes(canonical_json_bytes(redundant))
