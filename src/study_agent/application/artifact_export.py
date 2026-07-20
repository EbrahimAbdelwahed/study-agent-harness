"""Typed, positive-allowlist rendering for public artifact export v2."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from study_agent.artifacts import (
    DECISION_RECORDED,
    PROPOSAL_BATCH_RECORDED,
    ArtifactDecisionRecord,
    ArtifactProposalOrigin,
    ArtifactRevisionRecord,
    ArtifactSnapshot,
    GeneratedArtifactProvenance,
    HumanAuthoredArtifactProvenance,
    artifact_provenance_to_bytes,
    decode_decision_recorded,
    decode_proposal_batch_recorded,
)
from study_agent.artifacts.events import (
    DecisionRecorded,
    ProposalBatchRecorded,
    RecordedArtifactProposal,
)
from study_agent.domain import (
    ArtifactReadDependency,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    DomainEvent,
    PrincipalKind,
    SourceCommitment,
)
from study_agent.domain._validation import JsonObject
from study_agent.domain.source import SourceChunk
from study_agent.ingestion import SourceRevisionIngested


class ArtifactExportError(ValueError):
    """Canonical artifact state cannot be rendered without ambiguity."""


def artifact_rows(
    stream: Sequence[DomainEvent],
    snapshot: ArtifactSnapshot,
    sources: Sequence[SourceRevisionIngested],
) -> tuple[JsonObject, ...]:
    """Render revisions in proposal course-sequence/ordinal order."""
    revisions = {item.id: item for item in snapshot.revisions}
    batches = {item.id: item for item in snapshot.batches}
    decisions = {item.revision_id: item for item in snapshot.decisions}
    if len(decisions) != len(snapshot.decisions):
        raise ArtifactExportError("artifact decisions contain duplicate revisions")

    replayed_decisions: dict[ArtifactRevisionId, tuple[DecisionRecorded, PrincipalKind]] = {}
    proposal_order: list[tuple[int, ProposalBatchRecorded, RecordedArtifactProposal]] = []
    for event in stream:
        if event.event_type == PROPOSAL_BATCH_RECORDED:
            proposal_batch = decode_proposal_batch_recorded(event)
            batch = batches.get(proposal_batch.batch_id)
            if batch is None or batch.origin is not proposal_batch.origin:
                raise ArtifactExportError("artifact proposal batch does not match replayed state")
            if batch.session_id != event.session_id or batch.run_id != proposal_batch.run_id:
                raise ArtifactExportError("artifact proposal linkage does not match replayed state")
            if batch.revision_ids != tuple(item.revision_id for item in proposal_batch.proposals):
                raise ArtifactExportError("artifact batch revisions do not match replayed state")
            for proposal in proposal_batch.proposals:
                proposal_order.append((event.course_sequence, proposal_batch, proposal))
        elif event.event_type == DECISION_RECORDED:
            decoded_decision = decode_decision_recorded(event)
            if decoded_decision.revision_id in replayed_decisions:
                raise ArtifactExportError("artifact revision has duplicate terminal decisions")
            replayed_decisions[decoded_decision.revision_id] = (
                decoded_decision,
                event.actor.kind,
            )

    if len(proposal_order) != len(revisions):
        raise ArtifactExportError("artifact revisions do not match proposal replay")
    if set(replayed_decisions) != set(decisions):
        raise ArtifactExportError("artifact decisions do not match decision replay")
    for revision_id, decision in decisions.items():
        decoded, _ = replayed_decisions[revision_id]
        if (
            decision.decision is not decoded.decision
            or decision.supersedes_revision_id != decoded.supersedes_revision_id
            or decision.policy_receipt != decoded.policy_receipt
        ):
            raise ArtifactExportError("artifact decision does not match typed snapshot")
    _validate_supersession(decisions, revisions)

    chunks = _source_chunks(sources)
    source_revisions = {
        (str(item.source.source_id), str(item.source.revision_id)) for item in sources
    }
    rows: list[JsonObject] = []
    seen: set[object] = set()
    for _, decoded_batch, proposal in sorted(
        proposal_order, key=lambda item: (item[0], item[2].ordinal)
    ):
        revision = revisions.get(proposal.revision_id)
        if revision is None or revision.id in seen:
            raise ArtifactExportError("artifact proposal revision replay is inconsistent")
        seen.add(revision.id)
        if (
            revision.artifact_id != proposal.artifact_id
            or revision.batch_id != decoded_batch.batch_id
            or revision.ordinal != proposal.ordinal
            or revision.kind is not proposal.kind
            or revision.content.to_bytes() != proposal.content_bytes
            or artifact_provenance_to_bytes(revision.provenance) != proposal.provenance_bytes
            or revision.prior_revision_id != proposal.prior_revision_id
            or revision.parent_artifact_id != proposal.parent_artifact_id
        ):
            raise ArtifactExportError("artifact proposal does not match typed snapshot")
        _validate_provenance_links(revision.provenance, chunks, source_revisions, revisions)
        revision_decision = decisions.get(revision.id)
        _validate_terminal_state(revision.status, revision_decision)
        rows.append(
            {
                "schema_version": 2,
                "artifact_id": str(revision.artifact_id),
                "revision_id": str(revision.id),
                "batch_id": str(revision.batch_id),
                "session_id": str(batches[revision.batch_id].session_id),
                "ordinal": revision.ordinal,
                "kind": revision.kind.value,
                "proposal_origin": decoded_batch.origin.value,
                "status": revision.status.value,
                "prior_revision_id": (
                    str(revision.prior_revision_id) if revision.prior_revision_id else None
                ),
                "parent_artifact_id": (
                    str(revision.parent_artifact_id) if revision.parent_artifact_id else None
                ),
                "content": revision.content.to_json(),
                "proposal_proof": (
                    _proof(decoded_batch.proof)
                    if decoded_batch.origin is ArtifactProposalOrigin.GENERATED
                    else None
                ),
                "decision": (
                    None
                    if revision_decision is None
                    else _decision(revision_decision, replayed_decisions[revision.id][1])
                ),
                "provenance": _provenance(revision.provenance),
            }
        )
    return tuple(rows)


def _proof(value: object) -> JsonObject:
    from study_agent.artifacts import GeneratedBatchProofReceipt

    if not isinstance(value, GeneratedBatchProofReceipt):
        raise ArtifactExportError("generated artifact batch lacks typed proposal proof")
    return {
        "verifier_id": value.verifier_id,
        "verifier_version": value.verifier_version,
        "verifier_fingerprint": value.verifier_fingerprint,
    }


def _decision(value: object, authority: PrincipalKind) -> JsonObject:
    from study_agent.artifacts import ArtifactDecisionRecord

    if not isinstance(value, ArtifactDecisionRecord):
        raise ArtifactExportError("artifact decision is not typed")
    if authority not in (PrincipalKind.HUMAN, PrincipalKind.SERVICE):
        raise ArtifactExportError("artifact decision authority is invalid")
    receipt = value.policy_receipt
    if (authority is PrincipalKind.SERVICE) != (receipt is not None):
        raise ArtifactExportError("artifact decision authority does not match policy receipt")
    return {
        "authority": "human" if authority is PrincipalKind.HUMAN else "service_policy",
        "decision": value.decision.value,
        "supersedes_revision_id": (
            str(value.supersedes_revision_id) if value.supersedes_revision_id else None
        ),
        "policy": (
            None
            if receipt is None
            else {
                "policy_id": receipt.policy_id,
                "policy_version": receipt.policy_version,
                "policy_fingerprint": receipt.policy_fingerprint,
                "result_fingerprint": receipt.result_fingerprint,
            }
        ),
    }


def _provenance(value: object) -> JsonObject:
    common: JsonObject
    if isinstance(value, HumanAuthoredArtifactProvenance):
        common = {
            "origin": value.origin.value,
            "interaction_id": str(value.interaction_id),
            "source_commitments": _commitments(value.source_commitments),
            "read_dependencies": _dependencies(value.read_dependencies),
            "prior_revision_id": (
                str(value.prior_revision_id) if value.prior_revision_id else None
            ),
        }
        return common
    if not isinstance(value, GeneratedArtifactProvenance):
        raise ArtifactExportError("artifact provenance is not typed")
    return {
        "origin": value.origin.value,
        "run_id": str(value.run_id),
        "source_commitments": _commitments(value.source_commitments),
        "read_dependencies": _dependencies(value.read_dependencies),
        "prompt": {
            "prompt_id": value.prompt.prompt_id,
            "version": value.prompt.version,
            "composition_fingerprint": value.prompt.composition_fingerprint,
            "layer_fingerprints": value.prompt.layer_fingerprints,
        },
        "retrieval": {
            "strategy_id": value.retrieval.strategy_id,
            "strategy_version": value.retrieval.strategy_version,
            "query_fingerprint": value.retrieval.query_fingerprint,
            "index_version": value.retrieval.index_version,
            "read_set_fingerprint": value.retrieval.read_set_fingerprint,
        },
        "validators": tuple(
            {
                "validator_id": item.validator_id,
                "version": item.version,
                "passed": item.passed,
                "disposition": item.disposition,
                "result_fingerprint": item.result_fingerprint,
            }
            for item in value.validators
        ),
        "pins": {
            "skill": value.pins.skill,
            "playbook": value.pins.playbook,
            "prompt": value.pins.prompt,
            "state_contract": value.pins.state_contract,
            "tool_behavior": value.pins.tool_behavior,
        },
        "profile_selection": (
            value.profile_selection.to_json() if value.profile_selection else None
        ),
        "output_fingerprint": value.output_fingerprint,
        "prior_revision_id": str(value.prior_revision_id) if value.prior_revision_id else None,
    }


def _commitments(values: Sequence[SourceCommitment]) -> tuple[JsonObject, ...]:
    return tuple(
        {
            "source_id": str(item.source_id),
            "revision_id": str(item.revision_id),
            "chunk_id": str(item.chunk_id),
            "start_offset": item.start_offset,
            "end_offset": item.end_offset,
        }
        for item in values
    )


def _dependencies(values: Sequence[ArtifactReadDependency]) -> tuple[JsonObject, ...]:
    return tuple({"kind": item.kind, "id": item.id, "version": item.version} for item in values)


def _source_chunks(
    sources: Sequence[SourceRevisionIngested],
) -> dict[tuple[str, str, str], SourceChunk]:
    result: dict[tuple[str, str, str], SourceChunk] = {}
    for source in sources:
        for chunk in source.chunks:
            key = (str(chunk.source_id), str(chunk.revision_id), str(chunk.chunk_id))
            if key in result:
                raise ArtifactExportError("artifact export source chunks are duplicated")
            result[key] = chunk
    return result


def _validate_provenance_links(
    provenance: object,
    chunks: Mapping[tuple[str, str, str], SourceChunk],
    source_revisions: set[tuple[str, str]],
    revisions: Mapping[ArtifactRevisionId, ArtifactRevisionRecord],
) -> None:
    if not isinstance(provenance, (GeneratedArtifactProvenance, HumanAuthoredArtifactProvenance)):
        raise ArtifactExportError("artifact provenance is not typed")
    for commitment in provenance.source_commitments:
        key = (str(commitment.source_id), str(commitment.revision_id), str(commitment.chunk_id))
        chunk = chunks.get(key)
        if chunk is None:
            raise ArtifactExportError("artifact references a source chunk absent from export")
        if commitment.start_offset < chunk.start_offset or commitment.end_offset > chunk.end_offset:
            raise ArtifactExportError("artifact source span exceeds its exported chunk")
    for dependency in provenance.read_dependencies:
        if (
            dependency.kind == "source_revision"
            and (dependency.id, dependency.version) not in source_revisions
        ):
            raise ArtifactExportError("artifact references a source revision absent from export")
        if dependency.kind == "artifact_revision" and dependency.id not in {
            str(key) for key in revisions
        }:
            raise ArtifactExportError("artifact references an artifact revision absent from export")


def _validate_terminal_state(status: ArtifactRevisionStatus, decision: object | None) -> None:
    if status is ArtifactRevisionStatus.PROPOSED:
        if decision is not None:
            raise ArtifactExportError("proposed artifact unexpectedly has a terminal decision")
        return
    if decision is None:
        raise ArtifactExportError("terminal artifact is missing its decision")
    from study_agent.artifacts import ArtifactDecisionRecord
    from study_agent.domain import ArtifactDecision

    if not isinstance(decision, ArtifactDecisionRecord):
        raise ArtifactExportError("artifact decision is not typed")
    if (
        status is ArtifactRevisionStatus.REJECTED
        and decision.decision is not ArtifactDecision.REJECT
    ):
        raise ArtifactExportError("rejected artifact decision is inconsistent")
    if (
        status in (ArtifactRevisionStatus.ACCEPTED, ArtifactRevisionStatus.SUPERSEDED)
        and decision.decision is not ArtifactDecision.ACCEPT
    ):
        raise ArtifactExportError("accepted artifact decision is inconsistent")


def _validate_supersession(
    decisions: Mapping[ArtifactRevisionId, ArtifactDecisionRecord],
    revisions: Mapping[ArtifactRevisionId, ArtifactRevisionRecord],
) -> None:
    superseded = {
        item.supersedes_revision_id
        for item in decisions.values()
        if item.supersedes_revision_id is not None
    }
    expected = {
        item.id for item in revisions.values() if item.status is ArtifactRevisionStatus.SUPERSEDED
    }
    if superseded != expected:
        raise ArtifactExportError("artifact supersession does not match typed snapshot")


__all__ = ["ArtifactExportError", "artifact_rows"]
