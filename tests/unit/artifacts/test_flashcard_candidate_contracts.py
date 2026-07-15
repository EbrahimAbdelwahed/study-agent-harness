from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import pytest

from study_agent.artifacts.candidates import (
    FlashcardAnswerBlock,
    FlashcardCandidate,
    FlashcardCandidateBatch,
    FlashcardOmission,
    FlashcardPedagogicalRole,
)
from study_agent.domain import (
    MorphologyCognitiveFunction,
    MorphologyFamily,
    RetrievalForm,
)
from study_agent.domain._validation import freeze_object


def _candidate(
    key: str = "overview",
    *,
    parent: str | None = None,
    role: FlashcardPedagogicalRole = FlashcardPedagogicalRole.OVERVIEW,
) -> FlashcardCandidate:
    morphology = role in {
        FlashcardPedagogicalRole.MACRO_RECONSTRUCTION,
        FlashcardPedagogicalRole.ATOMIC_DISCRIMINATION,
    }
    return FlashcardCandidate(
        candidate_key=key,
        parent_candidate_key=parent,
        retrieval_form=RetrievalForm.DIRECT_RECALL,
        prompt="Reconstruct the organization of the aortic root.",
        answer_blocks=(
            FlashcardAnswerBlock(
                "Framework",
                "The root links the left ventricular outflow tract to the ascending aorta.",
                ("annulus", "sinuses", "sinotubular junction"),
            ),
        ),
        pedagogical_role=role,
        morphology_family=(MorphologyFamily.COMPONENTS if morphology else None),
        cognitive_function=(
            MorphologyCognitiveFunction.RECONSTRUCT if morphology else None
        ),
        rationale="This structure is not recoverable from an isolated detail.",
        evidence_ids=("evidence-1",),
        media_evidence_ids=(),
    )


def _plain(value: object) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def test_candidate_batch_round_trips_canonical_bytes_and_accepts_closed_edges() -> None:
    empty = FlashcardCandidateBatch((), ())
    full = FlashcardCandidateBatch(
        tuple(_candidate(f"card-{index}") for index in range(24)),
        (FlashcardOmission("Insufficient evidence for a fragile detail.", ("evidence-2",)),),
    )

    assert FlashcardCandidateBatch.from_bytes(empty.to_bytes()) == empty
    assert FlashcardCandidateBatch.from_bytes(full.to_bytes()) == full
    assert len(full.candidates) == 24

    with pytest.raises(ValueError, match=r"0\.\.24"):
        FlashcardCandidateBatch(
            tuple(_candidate(f"card-{index}") for index in range(25)), ()
        )
    with pytest.raises(ValueError, match="canonical"):
        FlashcardCandidateBatch.from_bytes(b'{"omissions": [], "candidates": []}')


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        (lambda batch: batch["candidates"][1].update(candidate_key="overview"), "unique"),
        (lambda batch: batch["candidates"][0].update(parent_candidate_key="detail"), "lower"),
        (lambda batch: batch["candidates"][1].update(parent_candidate_key="detail"), "parent"),
        (
            lambda batch: batch["candidates"][0].update(
                candidate_key="artifact-sha256:" + "a" * 64
            ),
            "temporary",
        ),
        (
            lambda batch: batch["candidates"][0].update(
                evidence_ids=["evidence-1", "evidence-1"]
            ),
            "unique",
        ),
        (lambda batch: batch["candidates"][0].update(prompt="x" * 4001), "4000"),
        (
            lambda batch: batch["candidates"][0].update(
                pedagogical_role="macro_reconstruction"
            ),
            "require",
        ),
    ),
)
def test_candidate_codec_rejects_cross_record_and_codec_only_violations(
    mutation: Any, match: str
) -> None:
    value = _plain(
        FlashcardCandidateBatch(
            (_candidate("overview"), _candidate("detail")), ()
        ).to_json()
    )
    mutation(value)

    with pytest.raises(ValueError, match=match):
        FlashcardCandidateBatch.from_json(freeze_object(value))


@pytest.mark.parametrize(
    ("field", "value", "match"),
    (
        ("provider", "openai", "fields"),
        ("model", "gpt", "fields"),
        ("api_key", "secret", "fields"),
        ("deck", "Anatomy", "fields"),
        ("tags", ["exam"], "fields"),
        ("template", "Basic", "fields"),
        ("status", "accepted", "fields"),
        ("profile", "hybrid-macro-detail@1", "fields"),
        ("blob_id", "blob-1", "fields"),
        ("verifier_id", "trusted", "fields"),
    ),
)
def test_candidate_codec_rejects_runtime_export_lifecycle_and_receipt_fields(
    field: str, value: object, match: str
) -> None:
    payload = _plain(FlashcardCandidateBatch((_candidate(),), ()).to_json())
    payload["candidates"][0][field] = value
    with pytest.raises(ValueError, match=match):
        FlashcardCandidateBatch.from_json(freeze_object(payload))


@pytest.mark.parametrize(
    ("field", "value", "match"),
    (
        ("prompt", "<b>Recall this</b>", "HTML"),
        ("rationale", "<em>important</em>", "HTML"),
        ("media_evidence_ids", ["diagram.png"], "filenames"),
        ("media_evidence_ids", ["folder/media"], "filenames"),
    ),
)
def test_candidate_codec_rejects_presentation_markup_and_media_filenames(
    field: str, value: object, match: str
) -> None:
    payload = _plain(FlashcardCandidateBatch((_candidate(),), ()).to_json())
    payload["candidates"][0][field] = value
    with pytest.raises(ValueError, match=match):
        FlashcardCandidateBatch.from_json(freeze_object(payload))


def test_candidate_parent_must_be_preceding_and_cannot_be_self() -> None:
    with pytest.raises(ValueError, match="own parent"):
        _candidate("same", parent="same")

    child = _candidate("child", parent="parent")
    parent = _candidate("parent")
    with pytest.raises(ValueError, match="lower"):
        FlashcardCandidateBatch((child, parent), ())


def test_hybrid_and_morphology_fields_are_conditionally_exact() -> None:
    hybrid = _candidate()
    morphology = _candidate(
        "macro", role=FlashcardPedagogicalRole.MACRO_RECONSTRUCTION
    )
    assert hybrid.morphology_family is None
    assert morphology.morphology_family is MorphologyFamily.COMPONENTS

    with pytest.raises(ValueError, match="forbid"):
        replace(
            hybrid,
            morphology_family=MorphologyFamily.COMPONENTS,
            cognitive_function=MorphologyCognitiveFunction.RECONSTRUCT,
        )


@pytest.mark.parametrize(
    "evidence_id",
    (
        "source:1",
        "revision-1",
        "chunk_1",
        "blob.1",
        "digest/1",
        "verifier\\1",
        "sha256:" + "a" * 64,
        "a" * 64,
    ),
)
def test_candidate_rejects_canonical_and_receipt_shaped_evidence_handles(
    evidence_id: str,
) -> None:
    with pytest.raises(ValueError, match="opaque handle"):
        replace(_candidate(), evidence_ids=(evidence_id,))


@pytest.mark.parametrize("media_id", ("media.png", "folder/media", "folder\\media"))
def test_candidate_rejects_any_filename_shaped_media_handle(media_id: str) -> None:
    with pytest.raises(ValueError, match=r"opaque handle|filenames"):
        replace(_candidate(), media_evidence_ids=(media_id,))


def test_candidate_requires_at_least_one_evidence_handle() -> None:
    with pytest.raises(ValueError, match=r"1\.\.16"):
        replace(_candidate(), evidence_ids=())
