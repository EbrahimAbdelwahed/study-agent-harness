from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import cast

import pytest

from study_agent.artifacts import (
    AnswerBlock,
    AssessmentItemContent,
    EvidenceObservation,
    ExamBlueprintContent,
    HybridFlashcardContent,
    MorphologyFlashcardContent,
    StudyArtifactEnvelope,
    StudyBriefContent,
    StudyBriefSection,
)
from study_agent.domain import (
    AssessmentFormat,
    BlobId,
    HybridFlashcardRole,
    MorphologyCognitiveFunction,
    MorphologyFamily,
    MorphologyFlashcardRole,
    RetrievalForm,
    StudyArtifactKind,
    VerifiedMediaRef,
)
from study_agent.domain._validation import JsonObject, JsonValue

DIGEST = "a" * 64
VERIFY = "b" * 64


def _media() -> VerifiedMediaRef:
    return VerifiedMediaRef(
        BlobId(f"sha256:{DIGEST}"),
        DIGEST,
        0,
        "trusted_blob_verifier",
        "1.0.0",
        VERIFY,
        "Anterior view of the aortic valve",
    )


def _envelopes() -> tuple[StudyArtifactEnvelope, ...]:
    hybrid = HybridFlashcardContent(
        RetrievalForm.DIRECT_RECALL,
        "What is the framework of the aortic valve?",
        (AnswerBlock("Framework", "Three cusps", ("right", "left", "non-coronary")),),
        HybridFlashcardRole.OVERVIEW,
        "The framework organizes later detail.",
        (0,),
        media=(_media(),),
    )
    morphology = MorphologyFlashcardContent(
        RetrievalForm.CONTEXTUAL_GAP,
        "Reconstruct the topology of the aortic root.",
        (AnswerBlock("Topology", "Cusps attach within the aortic root."),),
        MorphologyFlashcardRole.MACRO_RECONSTRUCTION,
        MorphologyFamily.TOPOLOGY,
        MorphologyCognitiveFunction.RECONSTRUCT,
        "Spatial reconstruction is the retrieval job.",
        (0,),
    )
    assessment = AssessmentItemContent(
        AssessmentFormat.SINGLE_CHOICE,
        "How many cusps form the aortic valve?",
        ("Three", "Four"),
        "Three",
        ("Identifies the correct cusp count",),
    )
    blueprint = ExamBlueprintContent(
        4,
        (EvidenceObservation("Valve anatomy", (0,)),),
        (EvidenceObservation("Single choice", (0,)),),
        ("The sample is small and descriptive only.",),
    )
    brief = StudyBriefContent(
        "Aortic valve",
        "Reconstruct the valve and its cusps.",
        (
            StudyBriefSection(
                "Framework",
                "The valve has three cusps.",
                ("Name each cusp",),
            ),
        ),
        ("This brief covers supplied valve material only.",),
    )
    return (
        StudyArtifactEnvelope(StudyArtifactKind.FLASHCARD, hybrid),
        StudyArtifactEnvelope(StudyArtifactKind.FLASHCARD, morphology),
        StudyArtifactEnvelope(StudyArtifactKind.ASSESSMENT_ITEM, assessment),
        StudyArtifactEnvelope(StudyArtifactKind.EXAM_BLUEPRINT, blueprint),
        StudyArtifactEnvelope(StudyArtifactKind.STUDY_BRIEF, brief),
    )


def _plain(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@pytest.mark.parametrize(
    "envelope",
    _envelopes(),
    ids=("hybrid", "morphology", "assessment", "blueprint", "brief"),
)
def test_each_content_codec_round_trips_exact_canonical_json(
    envelope: StudyArtifactEnvelope,
) -> None:
    encoded = envelope.to_json()
    assert set(encoded) == {"kind", "schema_version", "content"}
    assert StudyArtifactEnvelope.from_json(encoded) == envelope
    assert StudyArtifactEnvelope.from_bytes(envelope.to_bytes()) == envelope
    assert (
        envelope.to_bytes()
        == StudyArtifactEnvelope.from_bytes(envelope.to_bytes()).to_bytes()
    )
    with pytest.raises(TypeError):
        encoded["unknown"] = True  # type: ignore[index]


@pytest.mark.parametrize("envelope", _envelopes()[1:])
@pytest.mark.parametrize(
    "forbidden",
    (
        "artifact_id",
        "decision",
        "status",
        "provider",
        "model_id",
        "api_key",
        "deck",
        "tags",
        "template",
        "raw_html",
        "filename",
    ),
)
def test_every_kind_rejects_extra_reserved_provider_credential_and_anki_fields(
    envelope: StudyArtifactEnvelope, forbidden: str
) -> None:
    payload = cast(dict[str, object], _plain(envelope.to_json()))
    content = cast(dict[str, object], payload["content"])
    content[forbidden] = "forbidden"
    with pytest.raises((ValueError, TypeError)):
        StudyArtifactEnvelope.from_json(cast(JsonObject, payload))


def test_envelope_dispatch_and_flashcard_discriminated_unions_fail_closed() -> None:
    payload = cast(dict[str, object], _plain(_envelopes()[0].to_json()))
    for key, value in (
        ("kind", "unknown"),
        ("schema_version", 2),
    ):
        mutated = {**payload, key: value}
        with pytest.raises(ValueError):
            StudyArtifactEnvelope.from_json(cast(JsonObject, mutated))

    content = cast(dict[str, object], payload["content"])
    content["profile"] = {"id": "morphology-first-anatomy", "version": 1}
    with pytest.raises(ValueError):
        StudyArtifactEnvelope.from_json(cast(JsonObject, payload))

    wrong_kind = cast(dict[str, object], _plain(_envelopes()[2].to_json()))
    wrong_kind["kind"] = "study_brief"
    with pytest.raises(ValueError):
        StudyArtifactEnvelope.from_json(cast(JsonObject, wrong_kind))


@pytest.mark.parametrize(
    "field",
    ("attempt", "grade", "mastery", "schedule", "learner_model", "deck", "raw_html"),
)
def test_assessment_and_study_brief_pin_future_product_boundaries(field: str) -> None:
    for envelope in (_envelopes()[2], _envelopes()[4]):
        payload = cast(dict[str, object], _plain(envelope.to_json()))
        cast(dict[str, object], payload["content"])[field] = "future product state"
        with pytest.raises(ValueError):
            StudyArtifactEnvelope.from_json(cast(JsonObject, payload))


def test_verified_media_is_closed_linked_and_not_exporter_markup() -> None:
    media = _media()
    assert media.source_commitment_index == 0
    factories: tuple[Callable[[], VerifiedMediaRef], ...] = (
        lambda: replace(media, blob_id=BlobId("diagram.png")),
        lambda: replace(media, blob_id=BlobId(f"sha256:{'c' * 64}")),
        lambda: replace(media, sha256="A" * 64),
        lambda: replace(media, alt_text="<img src=x>"),
    )
    for factory in factories:
        with pytest.raises(ValueError):
            factory()

    with pytest.raises(ValueError, match="source commitment"):
        replace(
            cast(HybridFlashcardContent, _envelopes()[0].content),
            media=(replace(media, source_commitment_index=1),),
        )

    payload = cast(dict[str, object], _plain(_envelopes()[0].to_json()))
    for field in ("verified", "filename"):
        mutated = cast(dict[str, object], _plain(cast(JsonObject, payload)))
        content = cast(dict[str, object], mutated["content"])
        encoded_media = cast(list[dict[str, object]], content["media"])
        encoded_media[0][field] = False
        with pytest.raises(ValueError):
            StudyArtifactEnvelope.from_json(cast(JsonObject, mutated))


def test_ordinary_anki_words_are_text_but_anki_fields_and_noncanonical_bytes_fail() -> None:
    payload = cast(dict[str, object], _plain(_envelopes()[2].to_json()))
    cast(dict[str, object], payload["content"])["prompt"] = "Cloze"
    decoded = StudyArtifactEnvelope.from_json(cast(JsonObject, payload))
    assert cast(AssessmentItemContent, decoded.content).prompt == "Cloze"

    cast(dict[str, object], payload["content"])["note_type"] = "cloze"
    with pytest.raises(ValueError):
        StudyArtifactEnvelope.from_json(cast(JsonObject, payload))
    with pytest.raises(ValueError, match="canonical"):
        StudyArtifactEnvelope.from_bytes(b" " + _envelopes()[0].to_bytes())
