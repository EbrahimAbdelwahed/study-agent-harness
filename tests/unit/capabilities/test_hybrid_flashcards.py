from __future__ import annotations

from dataclasses import replace

from study_agent.capabilities import PROFILE_SELECTION_RECEIPT_INPUT
from study_agent.capabilities.hybrid_flashcards import (
    HybridFlashcardTaskBinding,
    hybrid_flashcards_binding,
)
from study_agent.flashcards.lesson_worker_contracts import ProfileTaskExpectation
from study_agent.playbooks import playbook_definition_fingerprint
from study_agent.prompts.hybrid_flashcards_v1 import HYBRID_FLASHCARDS_LAYERS
from study_agent.skills import ArtifactReference, SemanticVersion
from study_agent.workers import (
    ValidationExpectation,
    ValidationReceiptSource,
    fingerprint_output_schema,
)
from tests.unit.flashcards.test_lesson_worker_contracts import _request, _wrapper
from tests.unit.flashcards.test_lesson_worker_service import _parent

V1 = SemanticVersion.parse("1.0.0")


def _binding():  # type: ignore[no-untyped-def]
    return hybrid_flashcards_binding(
        dependency_resolver=lambda *, context, inputs: (),
        model_adapter=ArtifactReference("model-adapter", V1),
        state_contract=ArtifactReference("event-state", V1),
    )


def _expectation() -> ProfileTaskExpectation:
    binding = _binding()
    receipt = _request().profile_expectation.profile_selection_receipt
    return ProfileTaskExpectation(
        receipt,
        binding.manifest.id,
        binding.manifest.version,
        binding.manifest_fingerprint,
        binding.manifest.required_authority,
        binding.pins,
        playbook_definition_fingerprint(binding.playbook),
        binding.manifest.output_schema,
        fingerprint_output_schema(binding.manifest.output_schema),
        (
            ValidationExpectation(
                "check_hybrid_readiness",
                ValidationReceiptSource.VALIDATE_STEP,
                "hybrid_flashcards_readiness",
                "1.0.0",
            ),
            ValidationExpectation(
                "generate_hybrid_flashcards",
                ValidationReceiptSource.STRUCTURED_OUTPUT_FALLBACK,
                "hybrid_flashcards_integrity",
                "1.0.0",
            ),
            ValidationExpectation(
                "validate_hybrid_flashcards",
                ValidationReceiptSource.VALIDATE_STEP,
                "hybrid_flashcards_integrity",
                "1.0.0",
            ),
        ),
    )


def test_hybrid_prompt_uses_active_bundle_and_ceilings_not_quotas() -> None:
    text = " ".join(layer.template for layer in HYBRID_FLASHCARDS_LAYERS).lower()
    assert "active eligible bundle" in text
    assert "section framework" in text
    assert "fragile" in text and "not recoverable" in text
    assert "maximum, never a quota" in text
    assert "zero" in text
    assert "16..22" not in text
    assert "deck names" in text and "provider" in text


def test_hybrid_task_binding_builds_exact_public_task_and_private_descriptor() -> None:
    request = replace(_request(), profile_expectation=_expectation())
    wrapper = _wrapper(request)
    task_binding = HybridFlashcardTaskBinding(request, _binding())
    context = replace(_parent(), requested_capabilities=frozenset({"course:read"}))
    task = task_binding.build("lesson-worker-page-0", request.to_public_inputs(), wrapper, context)

    assert task.payload == request.to_public_inputs()
    assert PROFILE_SELECTION_RECEIPT_INPUT not in task.payload
    assert task.index_references[-1] == f"profile-sha256:{_expectation().fingerprint}"
    execution = task_binding.execution_descriptor.execution_inputs(task)
    assert execution[PROFILE_SELECTION_RECEIPT_INPUT] == (
        request.profile_expectation.profile_selection_receipt.to_bytes().decode()
    )
    assert task.pins.tool_behaviors[0].tool_name == ("source.prepare_planned_flashcard_scope")
