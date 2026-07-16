from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import replace
from hashlib import sha256
from typing import cast

import pytest

from study_agent.artifacts import (
    AnswerBlock,
    GeneratedArtifactProvenance,
    HumanAuthoredArtifactProvenance,
    HybridFlashcardContent,
    StudyArtifactEnvelope,
    artifact_batch_id_for,
    artifact_id_for,
    artifact_provenance_from_bytes,
    artifact_provenance_from_json,
    artifact_provenance_to_bytes,
    artifact_provenance_to_json,
    artifact_revision_id_for,
    human_authored_artifact_batch_id_for,
)
from study_agent.domain import (
    ArtifactBatchId,
    ArtifactId,
    ArtifactReadDependency,
    ArtifactRevisionId,
    ChunkId,
    CourseId,
    HybridFlashcardRole,
    InteractionId,
    ModelProvenance,
    ModelUsageProvenance,
    PrincipalKind,
    PromptProvenance,
    RetrievalForm,
    RetrievalProvenance,
    RevisionId,
    RunId,
    SessionId,
    SourceCommitment,
    SourceId,
    StudyArtifactKind,
    ValidatorProvenance,
    VersionPins,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.pedagogy import (
    HYBRID_MACRO_DETAIL_V1,
    ProfileSelectionBasis,
    ProfileSelectionMode,
    ProfileSelectionReceipt,
    ProfileSelectorKind,
)

RUN = RunId("run-artifact-1")
SOURCE = SourceId("source-heart")
REVISION = RevisionId("revision-heart-1")
COMMITMENT = SourceCommitment(SOURCE, REVISION, ChunkId("chunk-heart-1"), 0, 32)
DEPENDENCY = ArtifactReadDependency("source_revision", str(SOURCE), str(REVISION))


def _selection() -> ProfileSelectionReceipt:
    return ProfileSelectionReceipt(
        HYBRID_MACRO_DETAIL_V1,
        ProfileSelectionMode.DEFAULT,
        ProfileSelectorKind.HOST,
        PrincipalKind.SERVICE,
        ProfileSelectionBasis(),
    )


def _generated() -> GeneratedArtifactProvenance:
    return GeneratedArtifactProvenance(
        (COMMITMENT,),
        PromptProvenance("artifact-proposal", "1.0.0", "a" * 64, ("b" * 64,)),
        ModelProvenance(
            "generic_model",
            "1.0.0",
            "observed-model",
            "response-1",
            RUN,
            ModelUsageProvenance(40, 20),
        ),
        RetrievalProvenance("lexical", "1.0.0", "c" * 64, "index-1", "d" * 64),
        (ValidatorProvenance("artifact_integrity", "1.0.0", True, "continue", "e" * 64),),
        VersionPins(
            "artifact_skill@1",
            "artifact_flow@1",
            "artifact_prompt@1",
            "generic_model@1.0.0",
            "event_state@1",
            "source.search@1",
        ),
        _selection(),
        (DEPENDENCY,),
        sha256(_content().to_bytes()).hexdigest(),
        RUN,
    )


def test_generated_provenance_round_trips_nullable_technical_response_id() -> None:
    generated = _generated()
    assert generated.model is not None
    without_response_id = replace(
        generated,
        model=replace(generated.model, response_id=None),
    )

    assert (
        artifact_provenance_from_bytes(artifact_provenance_to_bytes(without_response_id))
        == without_response_id
    )


def _human() -> HumanAuthoredArtifactProvenance:
    return HumanAuthoredArtifactProvenance(
        PrincipalKind.HUMAN,
        InteractionId("interaction-human-1"),
        (COMMITMENT,),
        (DEPENDENCY,),
    )


def _content() -> StudyArtifactEnvelope:
    return StudyArtifactEnvelope(
        StudyArtifactKind.FLASHCARD,
        HybridFlashcardContent(
            RetrievalForm.DIRECT_RECALL,
            "How many cusps does the aortic valve have?",
            (AnswerBlock("Answer", "Three cusps"),),
            HybridFlashcardRole.DETAIL,
            "The count is fragile and worth direct recall.",
            (0,),
        ),
    )


def _plain(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def test_batch_artifact_and_revision_identities_are_typed_and_golden() -> None:
    batch = artifact_batch_id_for(
        CourseId("course-1"), SessionId("session-1"), RUN, "retry-1"
    )
    artifact = artifact_id_for(batch, 0)
    revision = artifact_revision_id_for(
        artifact,
        StudyArtifactKind.FLASHCARD,
        _content().to_bytes(),
        artifact_provenance_to_bytes(_generated()),
    )

    assert batch == ArtifactBatchId(
        "artifact-batch-sha256:23532f013fd13eb882f801883b6e6888883964d6b4d322578d2b2af8e2ffebb4"
    )
    assert artifact == ArtifactId(
        "artifact-sha256:05ee4e8ae452d68e76e543916d7201f8cceca07b9f21ca0827dd2159c4162aa8"
    )
    assert revision == ArtifactRevisionId(
        "artifact-revision-sha256:f0e9741f3b19cd42e8d187ea5cd368c38dc438cd0760e5b9bb8a9d9891de733f"
    )
    assert batch != ArtifactBatchId(str(artifact))
    assert artifact_id_for(batch, 1) != artifact
    human_batch = human_authored_artifact_batch_id_for(
        CourseId("course-1"),
        SessionId("session-1"),
        InteractionId("interaction-human-1"),
        "retry-1",
    )
    assert human_batch != batch


def test_identity_inputs_exclude_candidate_timestamp_and_credentials() -> None:
    assert tuple(inspect.signature(artifact_batch_id_for).parameters) == (
        "course_id",
        "session_id",
        "run_id",
        "retry_identity",
    )
    assert tuple(inspect.signature(artifact_id_for).parameters) == ("batch_id", "ordinal")
    assert tuple(inspect.signature(artifact_revision_id_for).parameters) == (
        "artifact_id",
        "kind",
        "content_bytes",
        "provenance_bytes",
        "prior_revision_id",
    )
    forbidden = {"candidate_id", "candidate_key", "timestamp", "credential", "api_key"}
    assert forbidden.isdisjoint(inspect.signature(artifact_revision_id_for).parameters)


def test_generated_provenance_round_trips_exact_observed_technical_receipts() -> None:
    value = _generated()
    encoded = artifact_provenance_to_json(value)
    assert artifact_provenance_from_json(encoded) == value
    assert artifact_provenance_from_bytes(artifact_provenance_to_bytes(value)) == value
    model = cast(Mapping[str, JsonValue], encoded["model"])
    assert model["adapter_id"] == "generic_model"
    assert model["model_id"] == "observed-model"
    assert encoded["profile_selection"] == _selection().to_json()


@pytest.mark.parametrize("case", ("missing", "failed", "duplicate"))
def test_generated_provenance_rejects_invalid_validator_proof(case: str) -> None:
    value = _generated()
    valid = value.validators[0]
    validators = {
        "missing": (),
        "failed": (replace(valid, passed=False),),
        "duplicate": (valid, valid),
    }[case]
    with pytest.raises(ValueError):
        replace(value, validators=validators)


def test_generated_provenance_rejects_source_dependency_and_run_pin_drift() -> None:
    value = _generated()
    factories: tuple[Callable[[], GeneratedArtifactProvenance], ...] = (
        lambda: replace(
            value,
            read_dependencies=(
                ArtifactReadDependency(
                    "source_revision", str(SOURCE), "revision-heart-2"
                ),
            ),
        ),
        lambda: replace(
            value,
            model=replace(cast(ModelProvenance, value.model), run_id=RunId("other")),
        ),
        lambda: replace(
            value, pins=replace(value.pins, model_adapter="other@1.0.0")
        ),
    )
    for factory in factories:
        with pytest.raises(ValueError):
            factory()


@pytest.mark.parametrize(
    "mutation",
    (
        lambda value: {**value, "output_fingerprint": "A" * 64},
        lambda value: {**value, "api_key": "secret"},
        lambda value: {**value, "policy_internals": {"selector": "private"}},
    ),
)
def test_provenance_codec_rejects_malformed_fingerprints_and_secret_shapes(
    mutation: Callable[[dict[str, object]], dict[str, object]],
) -> None:
    payload = cast(dict[str, object], _plain(artifact_provenance_to_json(_generated())))
    changed = mutation(payload)
    with pytest.raises(ValueError):
        artifact_provenance_from_json(cast(JsonObject, changed))


def test_human_authored_provenance_is_human_exact_and_generated_fields_fail_closed() -> None:
    value = _human()
    encoded = artifact_provenance_to_json(value)
    assert artifact_provenance_from_json(encoded) == value
    assert artifact_provenance_from_bytes(artifact_provenance_to_bytes(value)) == value
    assert set(encoded) == {
        "origin",
        "authority",
        "interaction_id",
        "source_commitments",
        "read_dependencies",
        "prior_revision_id",
    }
    for authority in (PrincipalKind.SERVICE, PrincipalKind.MODEL):
        with pytest.raises(ValueError):
            replace(value, authority=authority)

    for generated_only in (
        "prompt",
        "model",
        "validators",
        "pins",
        "run_id",
        "output_fingerprint",
        "profile_selection",
    ):
        payload = cast(dict[str, object], _plain(encoded))
        payload[generated_only] = None
        with pytest.raises(ValueError):
            artifact_provenance_from_json(cast(JsonObject, payload))


def test_generated_origin_cannot_omit_required_proof_fields() -> None:
    encoded = cast(dict[str, object], _plain(artifact_provenance_to_json(_generated())))
    for field in (
        "prompt",
        "retrieval",
        "validators",
        "pins",
        "read_dependencies",
        "output_fingerprint",
        "run_id",
    ):
        payload = dict(encoded)
        del payload[field]
        with pytest.raises(ValueError):
            artifact_provenance_from_json(cast(JsonObject, payload))
