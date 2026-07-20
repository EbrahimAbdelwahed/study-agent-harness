from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
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
    artifact_provenance_to_bytes,
    artifact_revision_id_for,
    human_authored_artifact_batch_id_for,
)
from study_agent.artifacts.contracts import (
    ArtifactProposalOrigin,
    GeneratedBatchProofReceipt,
    ServiceDecisionPolicyReceipt,
)
from study_agent.artifacts.events import (
    ARTIFACT_SCHEMA_VERSION,
    DECISION_RECORDED,
    PROPOSAL_BATCH_RECORDED,
    RecordedArtifactProposal,
    decision_payload,
    decode_decision_recorded,
    decode_proposal_batch_recorded,
    proposal_batch_payload,
)
from study_agent.domain import (
    Actor,
    ArtifactBatchId,
    ArtifactDecision,
    ArtifactId,
    ArtifactReadDependency,
    ArtifactRevisionId,
    ChunkId,
    CorrelationId,
    CourseId,
    DomainEvent,
    HybridFlashcardRole,
    InteractionId,
    ModelProvenance,
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
    artifact_event_id_for,
)
from study_agent.domain._validation import JsonObject
from study_agent.pedagogy import (
    HYBRID_MACRO_DETAIL_V1,
    ProfileSelectionBasis,
    ProfileSelectionMode,
    ProfileSelectionReceipt,
    ProfileSelectorKind,
)

COURSE = CourseId("course-artifacts")
SESSION = SessionId("session-artifacts")
RUN = RunId("run-artifacts")
SOURCE = SourceId("source-heart")
REVISION = RevisionId("revision-heart")
CHUNK = ChunkId("chunk-heart")
INTERACTION = InteractionId("interaction-human")
COMMITMENT = SourceCommitment(SOURCE, REVISION, CHUNK, 0, 32)
DEPENDENCY = ArtifactReadDependency("source_revision", str(SOURCE), str(REVISION))
NOW = datetime(2026, 7, 16, 9, tzinfo=UTC)
PROOF = GeneratedBatchProofReceipt("verified-run", "1.0.0", "9" * 64)


def content(
    *, parent_ordinal: int | None = None, text: str = "Three cusps"
) -> StudyArtifactEnvelope:
    return StudyArtifactEnvelope(
        StudyArtifactKind.FLASHCARD,
        HybridFlashcardContent(
            RetrievalForm.DIRECT_RECALL,
            "How many cusps does the aortic valve have?",
            (AnswerBlock("Answer", text),),
            HybridFlashcardRole.DETAIL,
            "This fact is fragile and worth direct recall.",
            (0,),
            parent_ordinal=parent_ordinal,
        ),
    )


def selection() -> ProfileSelectionReceipt:
    return ProfileSelectionReceipt(
        HYBRID_MACRO_DETAIL_V1,
        ProfileSelectionMode.DEFAULT,
        ProfileSelectorKind.HOST,
        PrincipalKind.SERVICE,
        ProfileSelectionBasis(),
    )


def generated_provenance(
    envelope: StudyArtifactEnvelope,
    *,
    run_id: RunId = RUN,
    prior: ArtifactRevisionId | None = None,
) -> GeneratedArtifactProvenance:
    return GeneratedArtifactProvenance(
        (COMMITMENT,),
        PromptProvenance("artifact-proposal", "1.0.0", "a" * 64, ("b" * 64,)),
        ModelProvenance("generic", "1.0.0", "fixture", "response-1", run_id),
        RetrievalProvenance("lexical", "1.0.0", "c" * 64, "index-1", "d" * 64),
        (ValidatorProvenance("artifact-integrity", "1.0.0", True, "continue", "e" * 64),),
        VersionPins(
            "artifact-skill@1",
            "artifact-flow@1",
            "artifact-prompt@1",
            "generic@1.0.0",
            "event-state@1",
            "source.search@1",
        ),
        selection(),
        (DEPENDENCY,),
        sha256(envelope.to_bytes()).hexdigest(),
        run_id,
        prior,
    )


def human_provenance(
    *, prior: ArtifactRevisionId | None = None
) -> HumanAuthoredArtifactProvenance:
    return HumanAuthoredArtifactProvenance(
        PrincipalKind.HUMAN,
        INTERACTION,
        (COMMITMENT,),
        (DEPENDENCY,),
        prior,
    )


def recorded(
    ordinal: int = 0,
    *,
    batch_id: ArtifactBatchId | None = None,
    envelope: StudyArtifactEnvelope | None = None,
    provenance: GeneratedArtifactProvenance | HumanAuthoredArtifactProvenance | None = None,
    artifact_id: ArtifactId | None = None,
    prior: ArtifactRevisionId | None = None,
    parent_artifact_id: ArtifactId | None = None,
) -> RecordedArtifactProposal:
    selected_batch = batch_id or artifact_batch_id_for(COURSE, SESSION, RUN, "proposal-1")
    selected_content = envelope or content()
    selected_provenance = provenance or generated_provenance(selected_content, prior=prior)
    selected_artifact = artifact_id or artifact_id_for(selected_batch, ordinal)
    content_bytes = selected_content.to_bytes()
    provenance_bytes = artifact_provenance_to_bytes(selected_provenance)
    revision_id = artifact_revision_id_for(
        selected_artifact,
        selected_content.kind,
        content_bytes,
        provenance_bytes,
        prior,
    )
    return RecordedArtifactProposal(
        ordinal,
        selected_artifact,
        revision_id,
        selected_content.kind,
        content_bytes,
        provenance_bytes,
        prior,
        parent_artifact_id,
    )


def proposal_event(
    *,
    actor: PrincipalKind = PrincipalKind.SERVICE,
    proposals: tuple[RecordedArtifactProposal, ...] | None = None,
    origin: ArtifactProposalOrigin = ArtifactProposalOrigin.GENERATED,
    key: str = "proposal-1",
    payload: JsonObject | None = None,
    event_id: object | None = None,
    session_id: SessionId = SESSION,
    run_id: RunId = RUN,
) -> DomainEvent:
    batch_id = (
        artifact_batch_id_for(COURSE, SESSION, run_id, key)
        if origin is ArtifactProposalOrigin.GENERATED
        else human_authored_artifact_batch_id_for(COURSE, SESSION, INTERACTION, key)
    )
    values = proposals or (recorded(batch_id=batch_id),)
    manifest = payload or proposal_batch_payload(
        batch_id,
        origin,
        values,
        SESSION,
        key,
        run_id=run_id if origin is ArtifactProposalOrigin.GENERATED else None,
        proof=PROOF if origin is ArtifactProposalOrigin.GENERATED else None,
    )
    return DomainEvent(
        event_id or artifact_event_id_for(COURSE, SESSION, key, "proposal"),  # type: ignore[arg-type]
        COURSE,
        2,
        PROPOSAL_BATCH_RECORDED,
        ARTIFACT_SCHEMA_VERSION,
        Actor(actor, "artifact-test"),
        NOW,
        CorrelationId("correlation-artifacts"),
        manifest,
        session_id,
    )


def decision_event(
    revision_id: ArtifactRevisionId,
    decision: ArtifactDecision,
    *,
    actor: PrincipalKind = PrincipalKind.HUMAN,
    supersedes: ArtifactRevisionId | None = None,
    receipt: ServiceDecisionPolicyReceipt | None = None,
    key: str = "decision-1",
    payload: JsonObject | None = None,
) -> DomainEvent:
    manifest = payload or decision_payload(
        revision_id, decision, supersedes, SESSION, key, receipt
    )
    return DomainEvent(
        artifact_event_id_for(COURSE, SESSION, key, "decision"),
        COURSE,
        3,
        DECISION_RECORDED,
        1,
        Actor(actor, "artifact-test"),
        NOW,
        CorrelationId("correlation-artifacts"),
        manifest,
        SESSION,
    )


def test_exact_generated_and_human_proposal_event_codecs_round_trip() -> None:
    generated = decode_proposal_batch_recorded(proposal_event())
    assert generated.origin is ArtifactProposalOrigin.GENERATED
    assert generated.run_id == RUN
    assert generated.proof == PROOF
    assert len(generated.proposals) == 1

    batch = human_authored_artifact_batch_id_for(COURSE, SESSION, INTERACTION, "human-1")
    envelope = content(text="Human revision")
    human = recorded(
        batch_id=batch,
        envelope=envelope,
        provenance=human_provenance(),
    )
    decoded = decode_proposal_batch_recorded(
        proposal_event(
            actor=PrincipalKind.HUMAN,
            proposals=(human,),
            origin=ArtifactProposalOrigin.HUMAN_AUTHORED,
            key="human-1",
        )
    )
    assert decoded.origin is ArtifactProposalOrigin.HUMAN_AUTHORED
    assert decoded.run_id is None and decoded.proof is None


def test_proposal_codec_rejects_extra_fields_authority_origin_and_session_forgery() -> None:
    valid = proposal_event()
    extra = cast(JsonObject, {**valid.payload, "unexpected": True})
    cases = (
        proposal_event(payload=extra),
        proposal_event(actor=PrincipalKind.MODEL),
        proposal_event(actor=PrincipalKind.HUMAN),
        proposal_event(event_id="forged-event"),
        proposal_event(session_id=SessionId("other-session")),
    )
    for event in cases:
        with pytest.raises((TypeError, ValueError)):
            decode_proposal_batch_recorded(event)


def test_proposal_codec_rejects_forged_identity_fingerprint_and_lifecycle_content() -> None:
    valid = proposal_event()
    bad_fingerprint = cast(JsonObject, {**valid.payload, "command_fingerprint": "0" * 64})
    with pytest.raises(ValueError, match="fingerprint"):
        decode_proposal_batch_recorded(proposal_event(payload=bad_fingerprint))

    proposal = recorded()
    forged = replace(proposal, revision_id=ArtifactRevisionId("forged-revision"))
    forged_event = proposal_event(proposals=(forged,))
    with pytest.raises(ValueError, match=r"identity|revision"):
        decode_proposal_batch_recorded(forged_event)

    manifest: dict[str, object] = dict(valid.payload)
    raw_proposals = [
        dict(cast(JsonObject, item))
        for item in cast(tuple[object, ...], manifest["proposals"])
    ]
    raw_proposals[0]["content"] = proposal.content_bytes.decode().replace(
        '"schema_version":1', '"schema_version":1,"status":"accepted"'
    )
    manifest["proposals"] = raw_proposals
    with pytest.raises(ValueError):
        decode_proposal_batch_recorded(proposal_event(payload=cast(JsonObject, manifest)))


def test_decision_codec_pins_actor_receipt_union_and_no_content_or_provenance() -> None:
    revision_id = recorded().revision_id
    human = decode_decision_recorded(
        decision_event(revision_id, ArtifactDecision.ACCEPT)
    )
    assert human.policy_receipt is None

    request_id = str(artifact_event_id_for(COURSE, SESSION, "service-1", "decision"))
    receipt = ServiceDecisionPolicyReceipt(
        request_id,
        ArtifactDecision.REJECT,
        None,
        "trusted-policy",
        "1.0.0",
        "7" * 64,
        "8" * 64,
    )
    service = decode_decision_recorded(
        decision_event(
            revision_id,
            ArtifactDecision.REJECT,
            actor=PrincipalKind.SERVICE,
            receipt=receipt,
            key="service-1",
        )
    )
    assert service.policy_receipt == receipt

    for event in (
        decision_event(revision_id, ArtifactDecision.REJECT, actor=PrincipalKind.MODEL),
        decision_event(revision_id, ArtifactDecision.REJECT, actor=PrincipalKind.SERVICE),
        decision_event(
            revision_id,
            ArtifactDecision.REJECT,
            receipt=receipt,
        ),
    ):
        with pytest.raises(ValueError):
            decode_decision_recorded(event)

    valid = decision_event(revision_id, ArtifactDecision.REJECT)
    for forbidden in ("content", "provenance"):
        payload = cast(JsonObject, {**valid.payload, forbidden: "forged"})
        with pytest.raises(ValueError):
            decode_decision_recorded(
                decision_event(revision_id, ArtifactDecision.REJECT, payload=payload)
            )


def test_service_policy_receipt_must_bind_exact_decision_request_and_result() -> None:
    revision_id = recorded().revision_id
    event_id = artifact_event_id_for(COURSE, SESSION, "bound", "decision")
    valid = ServiceDecisionPolicyReceipt(
        str(event_id),
        ArtifactDecision.ACCEPT,
        None,
        "trusted-policy",
        "1.0.0",
        "7" * 64,
        "8" * 64,
    )
    for receipt in (
        replace(valid, request_id="other-request"),
        replace(valid, decision=ArtifactDecision.REJECT),
    ):
        with pytest.raises(ValueError, match=r"receipt|policy|request|decision"):
            decode_decision_recorded(
                decision_event(
                    revision_id,
                    ArtifactDecision.ACCEPT,
                    actor=PrincipalKind.SERVICE,
                    receipt=receipt,
                    key="bound",
                )
            )


def test_policy_receipts_reject_secret_shaped_durable_fields() -> None:
    with pytest.raises(ValueError, match=r"secret|portable"):
        ServiceDecisionPolicyReceipt(
            "request-1",
            ArtifactDecision.REJECT,
            None,
            "api_key=secret",
            "1.0.0",
            "7" * 64,
            "8" * 64,
        )
