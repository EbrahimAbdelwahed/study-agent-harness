from __future__ import annotations

from dataclasses import replace

import pytest

from study_agent.capabilities import PROFILE_SELECTION_RECEIPT_INPUT
from study_agent.capabilities.bindings import ProfiledCapabilityBinding
from study_agent.capabilities.morphology_flashcards import (
    MorphologyFlashcardTaskBinding,
    morphology_flashcards_binding,
)
from study_agent.domain import PrincipalKind, RevisionId
from study_agent.flashcards.lesson_worker_contracts import ProfileTaskExpectation
from study_agent.pedagogy import (
    HYBRID_MACRO_DETAIL_V1,
    MORPHOLOGY_FIRST_ANATOMY_V1,
    ProfileSelectionBasis,
    ProfileSelectionMode,
    ProfileSelectionReceipt,
    ProfileSelectorKind,
)
from study_agent.playbooks import playbook_definition_fingerprint
from study_agent.prompts.morphology_flashcards_v1 import MORPHOLOGY_FLASHCARDS_LAYERS
from study_agent.skills import ArtifactReference, SemanticVersion
from study_agent.workers import (
    ValidationExpectation,
    ValidationReceiptSource,
    fingerprint_output_schema,
)
from tests.unit.flashcards.test_lesson_worker_contracts import _request, _wrapper
from tests.unit.flashcards.test_lesson_worker_service import _parent

V1 = SemanticVersion.parse("1.0.0")


def _binding() -> ProfiledCapabilityBinding:
    return morphology_flashcards_binding(
        dependency_resolver=lambda *, context, inputs: (),
        model_adapter=ArtifactReference("model-adapter", V1),
        state_contract=ArtifactReference("event-state", V1),
    )


def _receipt() -> ProfileSelectionReceipt:
    return ProfileSelectionReceipt(
        MORPHOLOGY_FIRST_ANATOMY_V1,
        ProfileSelectionMode.TRUSTED_METADATA,
        ProfileSelectorKind.TRUSTED_MATERIAL,
        PrincipalKind.SERVICE,
        ProfileSelectionBasis(source_revision_id=RevisionId("rev-a")),
    )


def _expectation() -> ProfileTaskExpectation:
    binding = _binding()
    return ProfileTaskExpectation(
        _receipt(),
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
                "check_morphology_readiness",
                ValidationReceiptSource.VALIDATE_STEP,
                "morphology_flashcards_readiness",
                "1.0.0",
            ),
            ValidationExpectation(
                "generate_morphology_flashcards",
                ValidationReceiptSource.STRUCTURED_OUTPUT_FALLBACK,
                "morphology_flashcards_integrity",
                "1.0.0",
            ),
            ValidationExpectation(
                "validate_morphology_flashcards",
                ValidationReceiptSource.VALIDATE_STEP,
                "morphology_flashcards_integrity",
                "1.0.0",
            ),
        ),
    )


def test_morphology_prompt_is_reconstruction_first_and_exporter_neutral() -> None:
    text = " ".join(layer.template for layer in MORPHOLOGY_FLASHCARDS_LAYERS).lower()
    assert "macro reconstruction first" in text
    assert "at most three atomic" in text
    assert "ceilings are maxima, never quotas" in text
    assert "verified prepared scope" in text
    assert "anki fields" in text and "filenames" in text


def test_morphology_task_uses_trusted_receipt_outside_public_payload() -> None:
    request = replace(_request(), profile_expectation=_expectation())
    wrapper = _wrapper(request)
    task_binding = MorphologyFlashcardTaskBinding(request, _binding())
    context = replace(_parent(), requested_capabilities=frozenset({"course:read"}))
    task = task_binding.build("morphology-page-0", request.to_public_inputs(), wrapper, context)
    assert PROFILE_SELECTION_RECEIPT_INPUT not in task.payload
    assert (
        task_binding.execution_descriptor.execution_inputs(task)[PROFILE_SELECTION_RECEIPT_INPUT]
        == _receipt().to_bytes().decode()
    )

    hybrid = replace(
        request.profile_expectation,
        profile_selection_receipt=replace(
            _receipt(),
            profile=HYBRID_MACRO_DETAIL_V1,
            mode=ProfileSelectionMode.DEFAULT,
            selector_kind=ProfileSelectorKind.HOST,
            basis=ProfileSelectionBasis(),
        ),
    )
    with pytest.raises(ValueError, match="not morphology"):
        MorphologyFlashcardTaskBinding(replace(request, profile_expectation=hybrid), _binding())
