"""Pure reducers for canonical study-artifact lifecycle state."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from study_agent.domain import (
    ArtifactDecision,
    ArtifactRevisionStatus,
    DomainEvent,
    InteractionKind,
    PrincipalKind,
    SessionId,
    StudyArtifactKind,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.pedagogy import ProfileSelectionMode
from study_agent.state import EventRegistry

from .content import HybridFlashcardContent, MorphologyFlashcardContent, StudyArtifactEnvelope
from .contracts import (
    ArtifactProposalOrigin,
    ServiceDecisionPolicyRequest,
    service_decision_result_fingerprint,
)
from .events import (
    ARTIFACT_SCHEMA_VERSION,
    DECISION_RECORDED,
    PROPOSAL_BATCH_RECORDED,
    DecisionRecorded,
    ProposalBatchRecorded,
    decode_decision_recorded,
    decode_proposal_batch_recorded,
)
from .identity import (
    GeneratedArtifactProvenance,
    HumanAuthoredArtifactProvenance,
    artifact_provenance_from_bytes,
    artifact_revision_id_for,
)


def reduce_proposal_batch_recorded(
    state: JsonObject, event: DomainEvent, payload: ProposalBatchRecorded
) -> Mapping[str, JsonValue]:
    _require_course_session(state, event)
    artifacts, revisions, batches, decisions, commands = _parts(state, event)
    command_id = str(event.event_id)
    if command_id in commands or str(payload.batch_id) in batches:
        raise ValueError("artifact proposal command already exists")
    if payload.origin is ArtifactProposalOrigin.GENERATED:
        if event.actor.kind is not PrincipalKind.SERVICE:
            raise ValueError("generated artifact replay requires SERVICE authority")
    else:
        if event.actor.kind is not PrincipalKind.HUMAN:
            raise ValueError("direct artifact replay requires HUMAN authority")

    updated_artifacts = dict(artifacts)
    updated_revisions = dict(revisions)
    resolved_in_batch: dict[int, str] = {}
    revision_ids: list[str] = []
    for proposal in payload.proposals:
        content = StudyArtifactEnvelope.from_bytes(proposal.content_bytes)
        provenance = artifact_provenance_from_bytes(proposal.provenance_bytes)
        if content.kind is not proposal.kind:
            raise ValueError("artifact proposal kind does not match content")
        _validate_commitments(state, provenance)
        if isinstance(provenance, GeneratedArtifactProvenance):
            if payload.run_id is None or provenance.run_id != payload.run_id:
                raise ValueError("generated provenance does not match batch run")
            _validate_generated_selection(state, event, provenance)
        elif isinstance(provenance, HumanAuthoredArtifactProvenance):
            _validate_human_origin(state, event, provenance)
        else:  # pragma: no cover - closed union guard
            raise ValueError("unknown artifact provenance origin")

        artifact_id = str(proposal.artifact_id)
        existing = updated_artifacts.get(artifact_id)
        if existing is None:
            if proposal.prior_revision_id is not None:
                raise ValueError("new artifact cannot name a prior revision")
            prior = None
            revision_history: tuple[str, ...] = ()
            parent_id = _resolve_new_parent(content, proposal.ordinal, resolved_in_batch)
            if proposal.parent_artifact_id != (
                None if parent_id is None else type(proposal.artifact_id)(parent_id)
            ):
                raise ValueError("persisted parent artifact does not match batch scaffolding")
        else:
            existing_map = _mapping(existing, "artifact")
            if existing_map.get("kind") != proposal.kind.value:
                raise ValueError("artifact revision cannot change kind")
            prior_text = _text(existing_map.get("current_revision_id"), "current_revision_id")
            prior = type(proposal.revision_id)(prior_text)
            if proposal.prior_revision_id != prior or provenance.prior_revision_id != prior:
                raise ValueError("artifact revision must name the current lineage head")
            raw_history = existing_map.get("revision_ids")
            if not isinstance(raw_history, tuple) or any(
                not isinstance(item, str) for item in raw_history
            ):
                raise ValueError("artifact revision history is corrupt")
            revision_history = tuple(item for item in raw_history if isinstance(item, str))
            raw_parent_id = existing_map.get("parent_artifact_id")
            if raw_parent_id is not None and not isinstance(raw_parent_id, str):
                raise ValueError("artifact parent identity is corrupt")
            parent_id = raw_parent_id if isinstance(raw_parent_id, str) else None
            proposed_parent = _parent_ordinal(content)
            if proposed_parent is not None:
                resolved = resolved_in_batch.get(proposed_parent)
                if resolved != parent_id or str(proposal.parent_artifact_id) != parent_id:
                    raise ValueError("revision cannot change its durable parent artifact")
            elif proposal.parent_artifact_id != (
                None if parent_id is None else type(proposal.artifact_id)(parent_id)
            ):
                raise ValueError("revision cannot clear or change its durable parent artifact")

        expected_revision = artifact_revision_id_for(
            proposal.artifact_id,
            proposal.kind,
            proposal.content_bytes,
            proposal.provenance_bytes,
            prior,
        )
        if proposal.revision_id != expected_revision or str(expected_revision) in updated_revisions:
            raise ValueError("artifact revision identity is invalid or duplicated")
        revision_id = str(expected_revision)
        updated_revisions[revision_id] = {
            "revision_id": revision_id,
            "artifact_id": artifact_id,
            "batch_id": str(payload.batch_id),
            "ordinal": proposal.ordinal,
            "kind": proposal.kind.value,
            "status": ArtifactRevisionStatus.PROPOSED.value,
            "content": proposal.content_bytes.decode(),
            "provenance": proposal.provenance_bytes.decode(),
            "prior_revision_id": str(prior) if prior else None,
            "parent_artifact_id": parent_id,
            "proposed_at": _timestamp(event.occurred_at),
            "decided_at": None,
        }
        updated_artifacts[artifact_id] = {
            "artifact_id": artifact_id,
            "kind": proposal.kind.value,
            "parent_artifact_id": parent_id,
            "revision_ids": (*revision_history, revision_id),
            "current_revision_id": revision_id,
        }
        resolved_in_batch[proposal.ordinal] = artifact_id
        revision_ids.append(revision_id)

    updated_batches = {
        **batches,
        str(payload.batch_id): {
            "batch_id": str(payload.batch_id),
            "course_id": str(event.course_id),
            "session_id": str(event.session_id),
            "origin": payload.origin.value,
            "revision_ids": tuple(revision_ids),
            "run_id": str(payload.run_id) if payload.run_id else None,
            "recorded_at": _timestamp(event.occurred_at),
        },
    }
    return _replace(
        state,
        updated_artifacts,
        updated_revisions,
        updated_batches,
        decisions,
        {
            **commands,
            command_id: {
                "command_fingerprint": payload.command_fingerprint,
                "result_id": str(payload.batch_id),
            },
        },
    )


def reduce_decision_recorded(
    state: JsonObject, event: DomainEvent, payload: DecisionRecorded
) -> Mapping[str, JsonValue]:
    _require_course_session(state, event)
    artifacts, revisions, batches, decisions, commands = _parts(state, event)
    command_id = str(event.event_id)
    if command_id in commands:
        raise ValueError("artifact decision command already exists")
    revision_id = str(payload.revision_id)
    raw = revisions.get(revision_id)
    revision = dict(_mapping(raw, "decision target"))
    if revision.get("status") != ArtifactRevisionStatus.PROPOSED.value:
        raise ValueError("artifact decisions are terminal")
    batch = _mapping(batches.get(_text(revision.get("batch_id"), "batch_id")), "batch")
    if batch.get("session_id") != str(event.session_id):
        raise ValueError("artifact decision target belongs to another session")
    if event.actor.kind is PrincipalKind.HUMAN:
        if payload.policy_receipt is not None:
            raise ValueError("human decision cannot carry service policy proof")
    elif event.actor.kind is PrincipalKind.SERVICE:
        if payload.policy_receipt is None:
            raise ValueError("service decision requires policy proof")
    else:
        raise ValueError("MODEL cannot decide artifacts")

    updated_revisions = dict(revisions)
    artifact_id = _text(revision.get("artifact_id"), "artifact_id")
    current_accepted = _current_accepted(artifacts, revisions, artifact_id)
    if payload.policy_receipt is not None:
        request = ServiceDecisionPolicyRequest(
            str(event.event_id),
            event.course_id,
            SessionId(str(event.session_id)),
            payload.revision_id,
            StudyArtifactKind(_text(revision.get("kind"), "revision kind")),
            type(payload.revision_id)(current_accepted) if current_accepted else None,
        )
        receipt = payload.policy_receipt
        if (
            receipt.request_id != request.request_id
            or receipt.decision is not payload.decision
            or receipt.supersedes_revision_id != payload.supersedes_revision_id
            or receipt.result_fingerprint
            != service_decision_result_fingerprint(
                request, payload.decision, payload.supersedes_revision_id
            )
        ):
            raise ValueError("service decision policy receipt is not bound to canonical state")
    if payload.decision is ArtifactDecision.REJECT:
        if payload.supersedes_revision_id is not None:
            raise ValueError("reject never supersedes")
        status = ArtifactRevisionStatus.REJECTED
    else:
        expected = current_accepted
        actual = str(payload.supersedes_revision_id) if payload.supersedes_revision_id else None
        if actual != expected:
            raise ValueError("accept must name the exact current accepted predecessor")
        if expected is not None:
            predecessor = dict(_mapping(updated_revisions.get(expected), "accepted predecessor"))
            predecessor["status"] = ArtifactRevisionStatus.SUPERSEDED.value
            predecessor["decided_at"] = _timestamp(event.occurred_at)
            updated_revisions[expected] = predecessor
        status = ArtifactRevisionStatus.ACCEPTED
    revision["status"] = status.value
    revision["decided_at"] = _timestamp(event.occurred_at)
    updated_revisions[revision_id] = revision
    decision_record: JsonObject = {
        "revision_id": revision_id,
        "decision": payload.decision.value,
        "supersedes_revision_id": (
            str(payload.supersedes_revision_id) if payload.supersedes_revision_id else None
        ),
        "decided_at": _timestamp(event.occurred_at),
        "policy_receipt": _policy_manifest(payload),
    }
    return _replace(
        state,
        artifacts,
        updated_revisions,
        batches,
        (*decisions, decision_record),
        {
            **commands,
            command_id: {
                "command_fingerprint": payload.command_fingerprint,
                "result_id": revision_id,
            },
        },
    )


def register_artifact_events(registry: EventRegistry) -> None:
    registry.register_event(
        PROPOSAL_BATCH_RECORDED,
        ARTIFACT_SCHEMA_VERSION,
        decode_proposal_batch_recorded,
        reduce_proposal_batch_recorded,
    )
    registry.register_event(
        DECISION_RECORDED,
        ARTIFACT_SCHEMA_VERSION,
        decode_decision_recorded,
        reduce_decision_recorded,
    )


def _parts(
    state: JsonObject, event: DomainEvent
) -> tuple[
    Mapping[str, JsonValue],
    Mapping[str, JsonValue],
    Mapping[str, JsonValue],
    tuple[JsonValue, ...],
    Mapping[str, JsonValue],
]:
    raw = state.get("study_artifacts", {})
    if not isinstance(raw, Mapping) or (
        raw and set(raw) != {"artifacts", "revisions", "batches", "decisions", "commands"}
    ):
        raise ValueError("artifact projection fields are corrupt")
    artifacts = _mapping(raw.get("artifacts", {}), "artifacts")
    revisions = _mapping(raw.get("revisions", {}), "revisions")
    batches = _mapping(raw.get("batches", {}), "batches")
    raw_decisions = raw.get("decisions", ())
    commands = _mapping(raw.get("commands", {}), "commands")
    if not isinstance(raw_decisions, tuple):
        raise ValueError("artifact decision history is corrupt")
    _validate_existing(event, artifacts, revisions, batches, raw_decisions, commands)
    return artifacts, revisions, batches, raw_decisions, commands


def _replace(
    state: JsonObject,
    artifacts: Mapping[str, JsonValue],
    revisions: Mapping[str, JsonValue],
    batches: Mapping[str, JsonValue],
    decisions: tuple[JsonValue, ...],
    commands: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    return {
        **state,
        "study_artifacts": {
            "artifacts": artifacts,
            "revisions": revisions,
            "batches": batches,
            "decisions": decisions,
            "commands": commands,
        },
    }


def _require_course_session(state: JsonObject, event: DomainEvent) -> None:
    if "course" not in state:
        raise ValueError("artifacts require an existing course")
    sessions = _mapping(state.get("sessions"), "sessions")
    session = sessions.get(str(event.session_id))
    if not isinstance(session, Mapping) or session.get("course_id") != str(event.course_id):
        raise ValueError("artifact event session was not found in its course")


def _validate_human_origin(
    state: JsonObject, event: DomainEvent, provenance: HumanAuthoredArtifactProvenance
) -> None:
    interactions = _mapping(state.get("session_interactions"), "session_interactions")
    origin = interactions.get(str(provenance.interaction_id))
    if (
        not isinstance(origin, Mapping)
        or origin.get("session_id") != str(event.session_id)
        or origin.get("kind") != InteractionKind.HUMAN.value
    ):
        raise ValueError("human-authored artifact requires its exact human interaction")


def _validate_generated_selection(
    state: JsonObject,
    event: DomainEvent,
    provenance: GeneratedArtifactProvenance,
) -> None:
    selection = provenance.profile_selection
    if selection is None or selection.mode is ProfileSelectionMode.DEFAULT:
        return
    if selection.mode is ProfileSelectionMode.EXPLICIT_REQUEST:
        interactions = _mapping(state.get("session_interactions"), "session_interactions")
        interaction_id = selection.basis.interaction_id
        origin = interactions.get(str(interaction_id))
        if (
            interaction_id is None
            or not isinstance(origin, Mapping)
            or origin.get("session_id") != str(event.session_id)
            or origin.get("kind") != InteractionKind.HUMAN.value
        ):
            raise ValueError("explicit profile selection lacks its canonical human interaction")
        return
    sources = _mapping(state.get("sources"), "sources")
    revision_id = selection.basis.source_revision_id
    if revision_id is None or not any(
        isinstance(source, Mapping)
        and str(revision_id) in _mapping(source.get("revisions", {}), "source revisions")
        for source in sources.values()
    ):
        raise ValueError("trusted profile selection lacks its canonical source revision")


def _validate_commitments(
    state: JsonObject, provenance: GeneratedArtifactProvenance | HumanAuthoredArtifactProvenance
) -> None:
    sources = _mapping(state.get("sources"), "sources")
    chunks = _mapping(state.get("chunks"), "chunks")
    for commitment in provenance.source_commitments:
        source = _mapping(sources.get(str(commitment.source_id)), "source commitment source")
        revisions = _mapping(source.get("revisions"), "source revisions")
        if str(commitment.revision_id) not in revisions:
            raise ValueError("artifact source revision commitment is not canonical")
        chunk = _mapping(chunks.get(str(commitment.chunk_id)), "source commitment chunk")
        if chunk.get("source_id") != str(commitment.source_id) or chunk.get("revision_id") != str(
            commitment.revision_id
        ):
            raise ValueError("artifact source commitment chunk ownership mismatch")
        start = chunk.get("start_offset")
        end = chunk.get("end_offset")
        if (
            type(start) is not int
            or type(end) is not int
            or commitment.start_offset < start
            or commitment.end_offset > end
        ):
            raise ValueError("artifact source commitment span is outside its canonical chunk")


def _resolve_new_parent(
    content: StudyArtifactEnvelope, ordinal: int, resolved: Mapping[int, str]
) -> str | None:
    parent = _parent_ordinal(content)
    if parent is None:
        return None
    if parent >= ordinal or parent not in resolved:
        raise ValueError("flashcard parent ordinal must resolve to a lower batch ordinal")
    return resolved[parent]


def _parent_ordinal(content: StudyArtifactEnvelope) -> int | None:
    if isinstance(content.content, (HybridFlashcardContent, MorphologyFlashcardContent)):
        return content.content.parent_ordinal
    return None


def _current_accepted(
    artifacts: Mapping[str, JsonValue], revisions: Mapping[str, JsonValue], artifact_id: str
) -> str | None:
    artifact = _mapping(artifacts.get(artifact_id), "artifact")
    history = artifact.get("revision_ids")
    if not isinstance(history, tuple):
        raise ValueError("artifact revision history is corrupt")
    accepted = [
        item
        for item in history
        if isinstance(item, str)
        and _mapping(revisions.get(item), "revision").get("status")
        == ArtifactRevisionStatus.ACCEPTED.value
    ]
    if len(accepted) > 1:
        raise ValueError("artifact has multiple current accepted revisions")
    return accepted[0] if accepted else None


def _validate_existing(
    event: DomainEvent,
    artifacts: Mapping[str, JsonValue],
    revisions: Mapping[str, JsonValue],
    batches: Mapping[str, JsonValue],
    decisions: tuple[JsonValue, ...],
    commands: Mapping[str, JsonValue],
) -> None:
    # Validate the complete owned shape before every reduction so replay cannot
    # use a partially trusted read model as lifecycle authority.
    for artifact_id, raw in artifacts.items():
        item = _mapping(raw, "artifact")
        if (
            set(item)
            != {"artifact_id", "kind", "parent_artifact_id", "revision_ids", "current_revision_id"}
            or item.get("artifact_id") != artifact_id
        ):
            raise ValueError("artifact projection entry is corrupt")
    for revision_id, raw in revisions.items():
        item = _mapping(raw, "revision")
        if item.get("revision_id") != revision_id or item.get("kind") not in {
            kind.value for kind in StudyArtifactKind
        }:
            raise ValueError("artifact revision projection entry is corrupt")
        ArtifactRevisionStatus(_text(item.get("status"), "revision status"))
        StudyArtifactEnvelope.from_bytes(_text(item.get("content"), "revision content").encode())
        artifact_provenance_from_bytes(
            _text(item.get("provenance"), "revision provenance").encode()
        )
    for batch_id, raw in batches.items():
        if _mapping(raw, "batch").get("batch_id") != batch_id:
            raise ValueError("artifact batch projection entry is corrupt")
    for raw in decisions:
        if not isinstance(raw, Mapping) or set(raw) != {
            "revision_id",
            "decision",
            "supersedes_revision_id",
            "decided_at",
            "policy_receipt",
        }:
            raise ValueError("artifact decision projection entry is corrupt")
    for command_id, raw in commands.items():
        item = _mapping(raw, "command")
        fingerprint = item.get("command_fingerprint")
        if (
            set(item) != {"command_fingerprint", "result_id"}
            or not isinstance(command_id, str)
            or not isinstance(fingerprint, str)
            or len(fingerprint) != 64
        ):
            raise ValueError("artifact command projection entry is corrupt")


def _policy_manifest(payload: DecisionRecorded) -> JsonValue:
    receipt = payload.policy_receipt
    if receipt is None:
        return None
    return {
        "request_id": receipt.request_id,
        "decision": receipt.decision.value,
        "supersedes_revision_id": str(receipt.supersedes_revision_id)
        if receipt.supersedes_revision_id
        else None,
        "policy_id": receipt.policy_id,
        "policy_version": receipt.policy_version,
        "policy_fingerprint": receipt.policy_fingerprint,
        "result_fingerprint": receipt.result_fingerprint,
    }


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"artifact projection field {name} must be an object")
    return value


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"artifact projection field {name} must be text")
    return value


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = ["reduce_decision_recorded", "reduce_proposal_batch_recorded", "register_artifact_events"]
