from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest

from study_agent.adapters.filesystem import FilesystemBlobStore, FilesystemExportWriter
from study_agent.application import (
    ExportBundleV2,
    ExportService,
    ExportStateError,
    ExportVersion,
)
from study_agent.artifacts import (
    AnswerBlock,
    ArtifactProposalOrigin,
    GeneratedArtifactProvenance,
    GeneratedBatchProofReceipt,
    HumanAuthoredArtifactProvenance,
    HybridFlashcardContent,
    ServiceDecisionPolicyReceipt,
    ServiceDecisionPolicyRequest,
    StudyArtifactEnvelope,
    artifact_batch_id_for,
    artifact_id_for,
    artifact_provenance_to_bytes,
    artifact_revision_id_for,
    human_authored_artifact_batch_id_for,
    service_decision_result_fingerprint,
)
from study_agent.artifacts.events import (
    ARTIFACT_SCHEMA_VERSION,
    DECISION_RECORDED,
    PROPOSAL_BATCH_RECORDED,
    RecordedArtifactProposal,
    decision_payload,
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
    BlobId,
    ChunkId,
    CorrelationId,
    DomainEvent,
    EventId,
    HybridFlashcardRole,
    InteractionId,
    InteractionKind,
    ModelProvenance,
    PrincipalKind,
    PromptProvenance,
    RetrievalForm,
    RetrievalProvenance,
    RunId,
    SourceCommitment,
    StudyArtifactKind,
    ValidatorProvenance,
    VerifiedMediaRef,
    VersionPins,
    artifact_event_id_for,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.ingestion import (
    SOURCE_REVISION_SELECTED,
    SOURCE_REVISION_SELECTED_SCHEMA_VERSION,
    decode_source_revision_ingested,
    source_revision_selected_event_id_for,
    source_revision_selected_payload,
)
from study_agent.pedagogy import (
    HYBRID_MACRO_DETAIL_V1,
    ProfileSelectionBasis,
    ProfileSelectionMode,
    ProfileSelectionReceipt,
    ProfileSelectorKind,
)
from study_agent.sessions import interaction_recorded_payload
from tests.contract.export.test_deterministic_export import (
    COURSE,
    NOW,
    SESSION,
    _files,
    _stack,
)


class Events:
    def __init__(self, values: Sequence[DomainEvent]) -> None:
        self.values = tuple(values)

    def read(
        self, course_id: object, after_sequence: int = 0
    ) -> Sequence[DomainEvent]:
        assert course_id == COURSE
        return self.values[after_sequence:]

    def append(self, course_id: object, expected: int, events: object) -> int:
        del course_id, expected, events
        raise AssertionError("export is read-only")


def _selection() -> ProfileSelectionReceipt:
    return ProfileSelectionReceipt(
        HYBRID_MACRO_DETAIL_V1,
        ProfileSelectionMode.DEFAULT,
        ProfileSelectorKind.HOST,
        PrincipalKind.SERVICE,
        ProfileSelectionBasis(),
    )


def _content(answer: str) -> StudyArtifactEnvelope:
    return StudyArtifactEnvelope(
        kind=StudyArtifactKind.FLASHCARD,
        content=HybridFlashcardContent(
            RetrievalForm.DIRECT_RECALL,
            "How many cusps does the aortic valve have?",
            (AnswerBlock("Answer", answer),),
            HybridFlashcardRole.DETAIL,
            "A fragile count benefits from direct recall.",
            (0,),
        ),
    )


def _generated_provenance(
    content: StudyArtifactEnvelope,
    commitment: SourceCommitment,
    run_id: RunId,
    *,
    prior: ArtifactRevisionId | None = None,
) -> GeneratedArtifactProvenance:
    dependency = ArtifactReadDependency(
        "source_revision", str(commitment.source_id), str(commitment.revision_id)
    )
    return GeneratedArtifactProvenance(
        (commitment,),
        PromptProvenance("public-artifact-prompt", "1.0.0", "a" * 64, ("b" * 64,)),
        ModelProvenance(
            "adapter-secret-must-not-export",
            "1.0.0",
            "model-secret-must-not-export",
            "response-secret-must-not-export",
            run_id,
        ),
        RetrievalProvenance("lexical", "1.0.0", "c" * 64, "index-1", "d" * 64),
        (
            ValidatorProvenance(
                "artifact-integrity", "1.0.0", True, "continue", "e" * 64
            ),
        ),
        VersionPins(
            "hybrid-skill@1",
            "hybrid-flow@1",
            "hybrid-prompt@1",
            "adapter-secret-must-not-export@1.0.0",
            "event-state@1",
            "source.prepare-flashcard-scope@1",
        ),
        _selection(),
        (dependency,),
        sha256(content.to_bytes()).hexdigest(),
        run_id,
        prior,
    )


def _recorded(
    batch_id: ArtifactBatchId,
    ordinal: int,
    content: StudyArtifactEnvelope,
    provenance: GeneratedArtifactProvenance | HumanAuthoredArtifactProvenance,
    *,
    artifact_id: ArtifactId | None = None,
    prior: ArtifactRevisionId | None = None,
) -> RecordedArtifactProposal:
    selected_id = artifact_id or artifact_id_for(batch_id, ordinal)
    content_bytes = content.to_bytes()
    provenance_bytes = artifact_provenance_to_bytes(provenance)
    revision_id = artifact_revision_id_for(
        selected_id,
        content.kind,
        content_bytes,
        provenance_bytes,
        prior,
    )
    return RecordedArtifactProposal(
        ordinal,
        selected_id,
        revision_id,
        content.kind,
        content_bytes,
        provenance_bytes,
        prior,
        None,
    )


def _proposal_event(
    sequence: int,
    key: str,
    proposal: RecordedArtifactProposal,
    *,
    run_id: RunId | None,
    origin: ArtifactProposalOrigin,
    interaction_id: InteractionId,
) -> DomainEvent:
    batch_id = (
        artifact_batch_id_for(COURSE, SESSION, run_id, key)
        if run_id is not None
        else human_authored_artifact_batch_id_for(COURSE, SESSION, interaction_id, key)
    )
    payload = proposal_batch_payload(
        batch_id,
        origin,
        (proposal,),
        SESSION,
        key,
        run_id=run_id,
        proof=(
            GeneratedBatchProofReceipt("verified-run", "1.0.0", "f" * 64)
            if run_id is not None
            else None
        ),
    )
    return DomainEvent(
        artifact_event_id_for(COURSE, SESSION, key, "proposal"),
        COURSE,
        sequence,
        PROPOSAL_BATCH_RECORDED,
        ARTIFACT_SCHEMA_VERSION,
        Actor(
            PrincipalKind.SERVICE
            if origin is ArtifactProposalOrigin.GENERATED
            else PrincipalKind.HUMAN,
            "principal-secret-must-not-export",
        ),
        NOW,
        CorrelationId(f"correlation-{key}"),
        payload,
        SESSION,
    )


def _decision_event(
    sequence: int,
    key: str,
    revision_id: ArtifactRevisionId,
    decision: ArtifactDecision,
    supersedes: ArtifactRevisionId | None = None,
    *,
    service_policy: bool = False,
) -> DomainEvent:
    event_id = artifact_event_id_for(COURSE, SESSION, key, "decision")
    receipt = (
        ServiceDecisionPolicyReceipt(
            str(event_id),
            decision,
            supersedes,
            "trusted-policy",
            "1.0.0",
            "1" * 64,
            service_decision_result_fingerprint(
                ServiceDecisionPolicyRequest(
                    str(event_id),
                    COURSE,
                    SESSION,
                    revision_id,
                    StudyArtifactKind.FLASHCARD,
                    supersedes,
                ),
                decision,
                supersedes,
            ),
        )
        if service_policy
        else None
    )
    return DomainEvent(
        event_id,
        COURSE,
        sequence,
        DECISION_RECORDED,
        ARTIFACT_SCHEMA_VERSION,
        Actor(
            PrincipalKind.SERVICE if service_policy else PrincipalKind.HUMAN,
            "principal-secret-must-not-export",
        ),
        NOW,
        CorrelationId(f"correlation-{key}"),
        decision_payload(revision_id, decision, supersedes, SESSION, key, receipt),
        SESSION,
    )


def _artifact_history(
    tmp_path: Path,
) -> tuple[FilesystemBlobStore, tuple[DomainEvent, ...]]:
    blobs, stored, _, _ = _stack(tmp_path)
    base = list(stored.read(COURSE))
    source = decode_source_revision_ingested(base[1].payload)
    chunk = source.chunks[0]
    commitment = SourceCommitment(
        chunk.source_id,
        chunk.revision_id,
        chunk.chunk_id,
        chunk.start_offset,
        min(chunk.start_offset + 8, chunk.end_offset),
    )
    interaction = InteractionId("interaction-human-export")
    base.append(
        DomainEvent(
            EventId("event-human-export"),
            COURSE,
            4,
            "session.interaction_recorded",
            1,
            Actor(PrincipalKind.HUMAN, "principal-secret-must-not-export"),
            NOW,
            CorrelationId("correlation-human-export"),
            interaction_recorded_payload(
                interaction, InteractionKind.HUMAN, "raw prompt text must not export"
            ),
            SESSION,
        )
    )

    first_run = RunId("run-generated-first")
    first_batch = artifact_batch_id_for(COURSE, SESSION, first_run, "generated-first")
    first_content = _content("Three cusps")
    first = _recorded(
        first_batch,
        0,
        first_content,
        _generated_provenance(first_content, commitment, first_run),
    )
    base.append(
        _proposal_event(
            5,
            "generated-first",
            first,
            run_id=first_run,
            origin=ArtifactProposalOrigin.GENERATED,
            interaction_id=interaction,
        )
    )
    base.append(_decision_event(6, "accept-first", first.revision_id, ArtifactDecision.ACCEPT))

    revision_content = _content("Three semilunar cusps")
    human_provenance = HumanAuthoredArtifactProvenance(
        PrincipalKind.HUMAN,
        interaction,
        (commitment,),
        (
            ArtifactReadDependency(
                "source_revision", str(commitment.source_id), str(commitment.revision_id)
            ),
            ArtifactReadDependency(
                "artifact_revision", str(first.revision_id), "1"
            ),
        ),
        first.revision_id,
    )
    human_batch = human_authored_artifact_batch_id_for(
        COURSE, SESSION, interaction, "human-revision"
    )
    human = _recorded(
        human_batch,
        0,
        revision_content,
        human_provenance,
        artifact_id=first.artifact_id,
        prior=first.revision_id,
    )
    base.append(
        _proposal_event(
            7,
            "human-revision",
            human,
            run_id=None,
            origin=ArtifactProposalOrigin.HUMAN_AUTHORED,
            interaction_id=interaction,
        )
    )
    base.append(
        _decision_event(
            8,
            "accept-revision",
            human.revision_id,
            ArtifactDecision.ACCEPT,
            first.revision_id,
        )
    )

    rejected_run = RunId("run-generated-rejected")
    rejected_batch = artifact_batch_id_for(
        COURSE, SESSION, rejected_run, "generated-rejected"
    )
    rejected_content = _content("Two cusps")
    rejected = _recorded(
        rejected_batch,
        0,
        rejected_content,
        _generated_provenance(rejected_content, commitment, rejected_run),
    )
    base.append(
        _proposal_event(
            9,
            "generated-rejected",
            rejected,
            run_id=rejected_run,
            origin=ArtifactProposalOrigin.GENERATED,
            interaction_id=interaction,
        )
    )
    base.append(
        _decision_event(
            10,
            "reject-generated",
            rejected.revision_id,
            ArtifactDecision.REJECT,
            service_policy=True,
        )
    )
    proposed_run = RunId("run-generated-proposed")
    proposed_batch = artifact_batch_id_for(
        COURSE, SESSION, proposed_run, "generated-proposed"
    )
    proposed_content = _content("Four cusps remain only a proposal")
    proposed = _recorded(
        proposed_batch,
        0,
        proposed_content,
        _generated_provenance(proposed_content, commitment, proposed_run),
    )
    base.append(
        _proposal_event(
            11,
            "generated-proposed",
            proposed,
            run_id=proposed_run,
            origin=ArtifactProposalOrigin.GENERATED,
            interaction_id=interaction,
        )
    )
    return blobs, tuple(base)


def _plain(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def test_pre_artifact_default_and_explicit_v1_remain_exactly_byte_identical(
    tmp_path: Path,
) -> None:
    blobs, events, _, _ = _stack(tmp_path)
    default = ExportService(events).assemble(COURSE)
    explicit = ExportService(events).assemble(COURSE, version=ExportVersion.V1)
    FilesystemExportWriter().write(default, tmp_path / "default")
    FilesystemExportWriter().write(explicit, tmp_path / "explicit")

    assert _files(tmp_path / "default") == _files(tmp_path / "explicit")
    assert set(_files(tmp_path / "default")) == {
        "answers.jsonl",
        "course.json",
        "events.jsonl",
        "manifest.json",
        "sessions.jsonl",
        "sources.json",
    }
    blobs.close()


def test_artifact_history_requires_v2_and_exports_deterministically_with_lineage(
    tmp_path: Path,
) -> None:
    blobs, history = _artifact_history(tmp_path)
    events = Events(history)
    with pytest.raises(ExportStateError, match=r"^artifact export requires v2$"):
        ExportService(events).assemble(COURSE)
    with pytest.raises(ExportStateError, match=r"^artifact export requires v2$"):
        ExportService(events).assemble(COURSE, version=ExportVersion.V1)

    first = ExportService(events).assemble(COURSE, version=ExportVersion.V2)
    second = ExportService(events).assemble(COURSE, version=ExportVersion.V2)
    assert isinstance(first, ExportBundleV2)
    assert isinstance(second, ExportBundleV2)
    assert first == second
    rows = cast(tuple[dict[str, Any], ...], first.artifacts)
    assert [row["ordinal"] for row in rows] == [0, 0, 0, 0]
    assert [row["status"] for row in rows] == [
        "superseded",
        "accepted",
        "rejected",
        "proposed",
    ]
    assert rows[1]["prior_revision_id"] == rows[0]["revision_id"]
    assert rows[1]["artifact_id"] == rows[0]["artifact_id"]
    assert rows[1]["decision"]["supersedes_revision_id"] == rows[0][
        "revision_id"
    ]
    generated = rows[0]
    assert generated["proposal_proof"] == {
        "verifier_id": "verified-run",
        "verifier_version": "1.0.0",
        "verifier_fingerprint": "f" * 64,
    }
    assert generated["provenance"]["profile_selection"]["profile"] == {
        "id": "hybrid-macro-detail",
        "version": 1,
    }
    assert generated["provenance"]["prompt"]["composition_fingerprint"] == "a" * 64
    assert generated["provenance"]["retrieval"]["read_set_fingerprint"] == "d" * 64
    assert generated["provenance"]["validators"][0]["result_fingerprint"] == "e" * 64
    assert generated["provenance"]["pins"]["skill"] == "hybrid-skill@1"
    assert generated["provenance"]["source_commitments"]
    policy = rows[2]["decision"]["policy"]
    assert policy["policy_id"] == "trusted-policy"
    assert policy["policy_version"] == "1.0.0"
    assert policy["policy_fingerprint"] == "1" * 64
    assert len(policy["result_fingerprint"]) == 64
    blobs.close()


def test_v1_artifact_guard_scans_past_earlier_v2_only_events(tmp_path: Path) -> None:
    blobs, history = _artifact_history(tmp_path)
    source = decode_source_revision_ingested(history[1].payload).source
    selected = DomainEvent(
        source_revision_selected_event_id_for(
            COURSE, source.source_id, source.revision_id, 5
        ),
        COURSE,
        5,
        SOURCE_REVISION_SELECTED,
        SOURCE_REVISION_SELECTED_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "principal-secret-must-not-export"),
        NOW,
        CorrelationId("correlation-selected-before-artifact"),
        source_revision_selected_payload(source.source_id, source.revision_id),
    )
    stream = (
        *history[:4],
        selected,
        *(
            replace(event, course_sequence=event.course_sequence + 1)
            for event in history[4:]
        ),
    )

    with pytest.raises(ExportStateError, match=r"^artifact export requires v2$"):
        ExportService(Events(stream)).assemble(COURSE, version=ExportVersion.V1)
    blobs.close()


def test_v1_artifact_guard_matches_only_exact_artifact_event_types(
    tmp_path: Path,
) -> None:
    blobs, stored, _, _ = _stack(tmp_path)
    stream = tuple(stored.read(COURSE))
    similarly_prefixed_unknown = DomainEvent(
        EventId("event-similarly-prefixed-unknown"),
        COURSE,
        4,
        f"{PROPOSAL_BATCH_RECORDED}.unknown",
        ARTIFACT_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "principal-secret-must-not-export"),
        NOW,
        CorrelationId("correlation-similarly-prefixed-unknown"),
        {},
    )

    with pytest.raises(
        ExportStateError,
        match=r"^event schema is not allowlisted for export: "
        r"study_artifact\.proposal_batch_recorded\.unknown@1$",
    ):
        ExportService(Events((*stream, similarly_prefixed_unknown))).assemble(
            COURSE, version=ExportVersion.V1
        )
    blobs.close()


def test_v2_export_is_positive_allowlist_redacted_and_adds_only_artifacts_file(
    tmp_path: Path,
) -> None:
    blobs, history = _artifact_history(tmp_path)
    bundle = ExportService(Events(history)).assemble(COURSE, version=ExportVersion.V2)
    assert isinstance(bundle, ExportBundleV2)
    FilesystemExportWriter().write(bundle, tmp_path / "first-v2")
    FilesystemExportWriter().write(bundle, tmp_path / "second-v2")
    assert _files(tmp_path / "first-v2") == _files(tmp_path / "second-v2")
    assert set(_files(tmp_path / "first-v2")) == {
        "answers.jsonl",
        "artifacts.jsonl",
        "course.json",
        "events.jsonl",
        "manifest.json",
        "sessions.jsonl",
        "sources.json",
    }
    combined = b"".join(_files(tmp_path / "first-v2").values())
    for forbidden in (
        b"principal-secret-must-not-export",
        b"raw prompt text must not export",
        b"adapter-secret-must-not-export",
        b"model-secret-must-not-export",
        b"response-secret-must-not-export",
        b"policy_request_id",
        b"idempotency",
        b"/Users/",
        b"medical-secret.md",
        b"Aortic valve content must not be exported verbatim.",
        b"source bytes",
        b"unverified_media",
    ):
        assert forbidden not in combined
    manifest = json.loads((tmp_path / "first-v2" / "manifest.json").read_bytes())
    assert manifest["schema_version"] == 2
    assert [item["name"] for item in manifest["files"]] == sorted(
        item["name"] for item in manifest["files"]
    )
    blobs.close()


@pytest.mark.parametrize(
    "mutation",
    ("unknown-schema", "corrupt-content", "orphan-session", "duplicate-decision"),
)
def test_v2_corrupt_or_ambiguous_artifact_history_fails_closed(
    tmp_path: Path, mutation: str
) -> None:
    blobs, valid = _artifact_history(tmp_path)
    values = list(valid)
    proposal_index = 4
    if mutation == "unknown-schema":
        values[proposal_index] = replace(values[proposal_index], schema_version=999)
    elif mutation == "corrupt-content":
        payload = dict(values[proposal_index].payload)
        proposals = [
            dict(item)
            for item in cast(tuple[JsonObject, ...], payload["proposals"])
        ]
        proposals[0]["content"] = "{}"
        payload["proposals"] = tuple(proposals)
        values[proposal_index] = replace(values[proposal_index], payload=payload)
    elif mutation == "orphan-session":
        values[proposal_index] = replace(
            values[proposal_index], session_id=type(SESSION)("session-orphan")
        )
    else:
        duplicate = replace(
            values[5],
            event_id=EventId("event-duplicate-decision"),
            course_sequence=len(values) + 1,
        )
        values.append(duplicate)
    with pytest.raises(ExportStateError):
        ExportService(Events(values)).assemble(COURSE, version=ExportVersion.V2)
    blobs.close()


def test_v2_export_rejects_artifact_commitment_to_absent_source_chunk(
    tmp_path: Path,
) -> None:
    blobs, valid = _artifact_history(tmp_path)
    source = decode_source_revision_ingested(valid[1].payload)
    chunk = source.chunks[0]
    commitment = SourceCommitment(
        chunk.source_id,
        chunk.revision_id,
        ChunkId("chunk-absent-from-export"),
        chunk.start_offset,
        min(chunk.start_offset + 8, chunk.end_offset),
    )
    run_id = RunId("run-broken-source-commitment")
    content = _content("Three cusps")
    proposal = _recorded(
        artifact_batch_id_for(COURSE, SESSION, run_id, "broken-source"),
        0,
        content,
        _generated_provenance(content, commitment, run_id),
    )
    history = (
        *valid[:4],
        _proposal_event(
            5,
            "broken-source",
            proposal,
            run_id=run_id,
            origin=ArtifactProposalOrigin.GENERATED,
            interaction_id=InteractionId("unused-broken-source"),
        ),
    )

    with pytest.raises(
        ExportStateError,
        match=r"^event stream cannot be replayed for export v2$",
    ):
        ExportService(Events(history)).assemble(COURSE, version=ExportVersion.V2)
    blobs.close()


def test_v2_export_rejects_acceptance_with_invalid_supersession(
    tmp_path: Path,
) -> None:
    blobs, valid = _artifact_history(tmp_path)
    values = list(valid[:7])
    revision_id = decode_proposal_batch_recorded(values[6]).proposals[0].revision_id
    values.append(
        _decision_event(
            8,
            "accept-revision-invalid-supersession",
            revision_id,
            ArtifactDecision.ACCEPT,
            ArtifactRevisionId("revision-not-currently-accepted"),
        )
    )

    with pytest.raises(ExportStateError):
        ExportService(Events(values)).assemble(COURSE, version=ExportVersion.V2)
    blobs.close()


def test_v2_export_preserves_only_verified_media_metadata(tmp_path: Path) -> None:
    blobs, valid = _artifact_history(tmp_path)
    source = decode_source_revision_ingested(valid[1].payload)
    chunk = source.chunks[0]
    commitment = SourceCommitment(
        chunk.source_id,
        chunk.revision_id,
        chunk.chunk_id,
        chunk.start_offset,
        min(chunk.start_offset + 8, chunk.end_offset),
    )
    digest = "2" * 64
    media = VerifiedMediaRef(
        BlobId(f"sha256:{digest}"),
        digest,
        0,
        "trusted_media_verifier",
        "1.0.0",
        "3" * 64,
        "Anterior view of the aortic valve",
    )
    base_content = _content("Three cusps")
    flashcard = cast(HybridFlashcardContent, base_content.content)
    content = replace(base_content, content=replace(flashcard, media=(media,)))
    run_id = RunId("run-verified-media")
    proposal = _recorded(
        artifact_batch_id_for(COURSE, SESSION, run_id, "verified-media"),
        0,
        content,
        _generated_provenance(content, commitment, run_id),
    )
    history = (
        *valid[:4],
        _proposal_event(
            5,
            "verified-media",
            proposal,
            run_id=run_id,
            origin=ArtifactProposalOrigin.GENERATED,
            interaction_id=InteractionId("unused-verified-media"),
        ),
    )

    bundle = ExportService(Events(history)).assemble(COURSE, version=ExportVersion.V2)
    assert isinstance(bundle, ExportBundleV2)
    exported = cast(dict[str, Any], bundle.artifacts[0]["content"])
    exported_media = cast(JsonValue, exported["content"]["media"])
    assert _plain(exported_media) == [
        {
            "blob_id": f"sha256:{digest}",
            "sha256": digest,
            "source_commitment_index": 0,
            "verifier_id": "trusted_media_verifier",
            "verifier_version": "1.0.0",
            "verifier_fingerprint": "3" * 64,
            "alt_text": "Anterior view of the aortic valve",
        }
    ]
    blobs.close()
