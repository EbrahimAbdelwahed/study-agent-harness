"""Authority-safe application service for canonical artifact lifecycle writes."""

from __future__ import annotations

from study_agent.domain import (
    Actor,
    ArtifactBatchId,
    ArtifactDecision,
    ArtifactId,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    DomainEvent,
    EventId,
    ExecutionContext,
    InteractionKind,
    PrincipalKind,
    RunId,
    SessionId,
    artifact_event_id_for,
)
from study_agent.domain._validation import JsonObject
from study_agent.ports import (
    ArtifactViewPort,
    ClockPort,
    EventSequenceConflictError,
    EventStore,
    ServiceDecisionPolicyPort,
    SessionViewPort,
    SourceCommitmentLookupPort,
    VerifiedGeneratedBatchPort,
)

from .content import HybridFlashcardContent, MorphologyFlashcardContent, StudyArtifactEnvelope
from .contracts import (
    ArtifactProposal,
    ArtifactProposalOrigin,
    ArtifactRevisionRecord,
    ArtifactSnapshot,
    ServiceDecisionPolicyReceipt,
    ServiceDecisionPolicyRequest,
    service_decision_result_fingerprint,
)
from .events import (
    ARTIFACT_SCHEMA_VERSION,
    DECISION_RECORDED,
    PROPOSAL_BATCH_RECORDED,
    RecordedArtifactProposal,
    decision_command_fingerprint,
    decision_payload,
    proposal_batch_payload,
    proposal_command_fingerprint,
    service_decision_command_fingerprint,
)
from .identity import (
    HumanAuthoredArtifactProvenance,
    artifact_batch_id_for,
    artifact_id_for,
    artifact_provenance_to_bytes,
    artifact_revision_id_for,
    human_authored_artifact_batch_id_for,
)


class ArtifactCommandError(ValueError):
    """An artifact command violates authority, ownership, or lifecycle rules."""


class ArtifactConflictError(ArtifactCommandError):
    """A retry identity or lifecycle target conflicts with canonical state."""


class RetryableArtifactConflictError(RuntimeError):
    """The stream raced and the exact artifact command did not commit."""


class ArtifactService:
    def __init__(
        self,
        events: EventStore,
        clock: ClockPort,
        view: ArtifactViewPort,
        sessions: SessionViewPort,
        generated_batches: VerifiedGeneratedBatchPort,
        source_commitments: SourceCommitmentLookupPort,
        decision_policy: ServiceDecisionPolicyPort,
    ) -> None:
        self._events = events
        self._clock = clock
        self._view = view
        self._sessions = sessions
        self._generated_batches = generated_batches
        self._source_commitments = source_commitments
        self._decision_policy = decision_policy

    def record_generated(
        self, run_id: RunId, context: ExecutionContext, expected_sequence: int
    ) -> ArtifactSnapshot:
        session_id, key = _context(context, PrincipalKind.SERVICE)
        _expected(expected_sequence)
        if not isinstance(run_id, RunId):
            raise TypeError("run_id must be RunId")
        event_id = artifact_event_id_for(context.course_id, session_id, key, "proposal")
        fingerprint = proposal_command_fingerprint(ArtifactProposalOrigin.GENERATED, run_id, ())
        existing = self._existing(context, event_id, fingerprint)
        if existing is not None:
            return existing
        self._expect_sequence(context, expected_sequence)
        verified = self._generated_batches.recover(run_id)
        if (
            verified.run_id != run_id
            or verified.course_id != context.course_id
            or verified.session_id != session_id
        ):
            raise ArtifactCommandError(
                "verified generated batch belongs to another run, course, or session"
            )
        batch_id = artifact_batch_id_for(context.course_id, session_id, run_id, key)
        snapshot = self._view.get(context.course_id)
        proposals = self._prepare(batch_id, verified.proposals, snapshot)
        payload = proposal_batch_payload(
            batch_id,
            ArtifactProposalOrigin.GENERATED,
            proposals,
            session_id,
            key,
            run_id=run_id,
            proof=verified.proof,
        )
        event = self._event(
            context, event_id, PROPOSAL_BATCH_RECORDED, expected_sequence + 1, payload
        )
        return self._append(context, expected_sequence, event, fingerprint)

    def record_human_revision(
        self,
        content: StudyArtifactEnvelope,
        provenance: HumanAuthoredArtifactProvenance,
        target_artifact_id: ArtifactId | None,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> ArtifactSnapshot:
        session_id, key = _context(context, PrincipalKind.HUMAN)
        _expected(expected_sequence)
        if not isinstance(content, StudyArtifactEnvelope):
            raise TypeError("content must be StudyArtifactEnvelope")
        if not isinstance(provenance, HumanAuthoredArtifactProvenance):
            raise TypeError("provenance must be HumanAuthoredArtifactProvenance")
        if target_artifact_id is not None and not isinstance(target_artifact_id, ArtifactId):
            raise TypeError("target_artifact_id must be ArtifactId or absent")
        if provenance.authority is not PrincipalKind.HUMAN:
            raise ArtifactCommandError("direct artifact authoring requires HUMAN provenance")
        batch_id = human_authored_artifact_batch_id_for(
            context.course_id, session_id, provenance.interaction_id, key
        )
        proposal = ArtifactProposal(0, content, provenance, target_artifact_id)
        event_id = artifact_event_id_for(context.course_id, session_id, key, "proposal")
        provisional = RecordedArtifactProposal(
            0,
            target_artifact_id or artifact_id_for(batch_id, 0),
            ArtifactRevisionId("uncommitted"),
            content.kind,
            content.to_bytes(),
            artifact_provenance_to_bytes(provenance),
            provenance.prior_revision_id,
            None,
        )
        fingerprint = proposal_command_fingerprint(
            ArtifactProposalOrigin.HUMAN_AUTHORED,
            None,
            (
                {
                    "ordinal": provisional.ordinal,
                    "artifact_id": str(provisional.artifact_id),
                    "revision_id": str(provisional.revision_id),
                    "kind": provisional.kind.value,
                    "content": provisional.content_bytes.decode(),
                    "provenance": provisional.provenance_bytes.decode(),
                    "prior_revision_id": str(provisional.prior_revision_id)
                    if provisional.prior_revision_id
                    else None,
                    "parent_artifact_id": None,
                },
            ),
        )
        existing = self._existing(context, event_id, fingerprint)
        if existing is not None:
            return existing
        snapshot = self._view.get(context.course_id)
        prepared = self._prepare(batch_id, (proposal,), snapshot)
        manifest = proposal_batch_payload(
            batch_id,
            ArtifactProposalOrigin.HUMAN_AUTHORED,
            prepared,
            session_id,
            key,
            run_id=None,
            proof=None,
        )
        if manifest["command_fingerprint"] != fingerprint:
            raise ArtifactCommandError("human proposal command identity is unstable")
        self._expect_sequence(context, expected_sequence)
        interaction = next(
            (
                item
                for item in self._sessions.interactions(context.course_id, session_id)
                if item.id == provenance.interaction_id
            ),
            None,
        )
        if interaction is None or interaction.kind is not InteractionKind.HUMAN:
            raise ArtifactCommandError(
                "human-authored artifact requires an existing human interaction in the session"
            )
        if any(
            not self._source_commitments.contains(context.course_id, item)
            for item in provenance.source_commitments
        ):
            raise ArtifactCommandError("human-authored artifact source commitment is not canonical")
        event = self._event(
            context, event_id, PROPOSAL_BATCH_RECORDED, expected_sequence + 1, manifest
        )
        return self._append(context, expected_sequence, event, fingerprint)

    def record_human_decision(
        self,
        revision_id: ArtifactRevisionId,
        decision: ArtifactDecision,
        supersedes_revision_id: ArtifactRevisionId | None,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> ArtifactSnapshot:
        return self._record_decision(
            revision_id,
            decision,
            supersedes_revision_id,
            context,
            expected_sequence,
            required=PrincipalKind.HUMAN,
            receipt=None,
        )

    def apply_service_decision(
        self,
        revision_id: ArtifactRevisionId,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> ArtifactSnapshot:
        session_id, key = _context(context, PrincipalKind.SERVICE)
        _expected(expected_sequence)
        if not isinstance(revision_id, ArtifactRevisionId):
            raise TypeError("revision_id must be ArtifactRevisionId")
        event_id = artifact_event_id_for(context.course_id, session_id, key, "decision")
        # Decision outcome is intentionally absent from the public command and
        # from its stable request fingerprint.
        fingerprint = service_decision_command_fingerprint(revision_id)
        existing_fingerprint = self._view.command_fingerprint(context.course_id, event_id)
        if existing_fingerprint is not None:
            if existing_fingerprint == fingerprint:
                return self._view.get(context.course_id)
            raise ArtifactConflictError("decision retry identity names another result")
        self._expect_sequence(context, expected_sequence)
        snapshot = self._view.get(context.course_id)
        target = _proposed(snapshot, revision_id)
        _require_decision_session(snapshot, target, session_id)
        current = _current_accepted(snapshot, target.artifact_id)
        request_id = str(event_id)
        request = ServiceDecisionPolicyRequest(
            request_id,
            context.course_id,
            session_id,
            revision_id,
            target.kind,
            current.id if current else None,
        )
        receipt = self._decision_policy.decide(request)
        _validate_policy_result(request, receipt)
        # This fingerprint includes the outcome but the policy is never called
        # for an already committed event. A post-race retry must return exactly
        # the same bound deterministic result.
        return self._record_decision(
            revision_id,
            receipt.decision,
            receipt.supersedes_revision_id,
            context,
            expected_sequence,
            required=PrincipalKind.SERVICE,
            receipt=receipt,
            skip_sequence_check=True,
        )

    def _record_decision(
        self,
        revision_id: ArtifactRevisionId,
        decision: ArtifactDecision,
        supersedes_revision_id: ArtifactRevisionId | None,
        context: ExecutionContext,
        expected_sequence: int,
        *,
        required: PrincipalKind,
        receipt: ServiceDecisionPolicyReceipt | None,
        skip_sequence_check: bool = False,
    ) -> ArtifactSnapshot:
        session_id, key = _context(context, required)
        _expected(expected_sequence)
        if not isinstance(revision_id, ArtifactRevisionId):
            raise TypeError("revision_id must be ArtifactRevisionId")
        if not isinstance(decision, ArtifactDecision):
            raise TypeError("decision must be ArtifactDecision")
        if supersedes_revision_id is not None and not isinstance(
            supersedes_revision_id, ArtifactRevisionId
        ):
            raise TypeError("supersedes_revision_id must be ArtifactRevisionId or absent")
        event_id = artifact_event_id_for(context.course_id, session_id, key, "decision")
        fingerprint = (
            service_decision_command_fingerprint(revision_id)
            if receipt is not None
            else decision_command_fingerprint(revision_id, decision, supersedes_revision_id, None)
        )
        existing = self._existing(context, event_id, fingerprint)
        if existing is not None:
            return existing
        if not skip_sequence_check:
            self._expect_sequence(context, expected_sequence)
        snapshot = self._view.get(context.course_id)
        target = _proposed(snapshot, revision_id)
        _require_decision_session(snapshot, target, session_id)
        current = _current_accepted(snapshot, target.artifact_id)
        if decision is ArtifactDecision.REJECT:
            if supersedes_revision_id is not None:
                raise ArtifactCommandError("reject never supersedes")
        elif supersedes_revision_id != (current.id if current else None):
            raise ArtifactConflictError("accept must name the exact current accepted predecessor")
        payload = decision_payload(
            revision_id,
            decision,
            supersedes_revision_id,
            session_id,
            key,
            receipt,
        )
        event = self._event(context, event_id, DECISION_RECORDED, expected_sequence + 1, payload)
        return self._append(context, expected_sequence, event, fingerprint)

    def _prepare(
        self,
        batch_id: ArtifactBatchId,
        proposals: tuple[ArtifactProposal, ...],
        snapshot: ArtifactSnapshot,
    ) -> tuple[RecordedArtifactProposal, ...]:
        if not 1 <= len(proposals) <= 24 or tuple(item.ordinal for item in proposals) != tuple(
            range(len(proposals))
        ):
            raise ArtifactCommandError("artifact batch requires 1..24 contiguous proposals")
        prepared: list[RecordedArtifactProposal] = []
        seen: set[ArtifactId] = set()
        resolved: dict[int, ArtifactId] = {}
        for item in proposals:
            target = None
            if item.target_artifact_id is not None:
                history = snapshot.history(item.target_artifact_id)
                if not history:
                    raise ArtifactCommandError("artifact revision target was not found")
                try:
                    target = snapshot.current_head(item.target_artifact_id)
                except ValueError as error:
                    raise ArtifactConflictError(
                        "artifact revision target has an invalid canonical lineage"
                    ) from error
                if target.kind is not item.content.kind:
                    raise ArtifactCommandError("artifact revision cannot change kind")
                artifact_id = target.artifact_id
                prior = target.id
                parent_id = target.parent_artifact_id
                proposed_parent = _parent_ordinal(item.content)
                if proposed_parent is not None and resolved.get(proposed_parent) != parent_id:
                    raise ArtifactCommandError("artifact revision cannot change its durable parent")
            else:
                artifact_id = artifact_id_for(batch_id, item.ordinal)
                prior = None
                parent_ordinal = _parent_ordinal(item.content)
                if parent_ordinal is not None:
                    if parent_ordinal >= item.ordinal or parent_ordinal not in resolved:
                        raise ArtifactCommandError(
                            "parent ordinal must resolve to a lower proposal"
                        )
                    parent_id = resolved[parent_ordinal]
                else:
                    parent_id = None
            if artifact_id in seen:
                raise ArtifactCommandError("batch cannot revise one artifact twice")
            if item.provenance.prior_revision_id != prior:
                raise ArtifactCommandError("proposal provenance does not name current lineage head")
            content_bytes = item.content.to_bytes()
            provenance_bytes = artifact_provenance_to_bytes(item.provenance)
            revision_id = artifact_revision_id_for(
                artifact_id, item.content.kind, content_bytes, provenance_bytes, prior
            )
            prepared.append(
                RecordedArtifactProposal(
                    item.ordinal,
                    artifact_id,
                    revision_id,
                    item.content.kind,
                    content_bytes,
                    provenance_bytes,
                    prior,
                    parent_id,
                )
            )
            seen.add(artifact_id)
            resolved[item.ordinal] = artifact_id
        return tuple(prepared)

    def _existing(
        self, context: ExecutionContext, event_id: EventId, fingerprint: str
    ) -> ArtifactSnapshot | None:
        existing = self._view.command_fingerprint(context.course_id, event_id)
        if existing is None:
            return None
        if existing != fingerprint:
            raise ArtifactConflictError("artifact retry identity has different command fingerprint")
        return self._view.get(context.course_id)

    def _expect_sequence(self, context: ExecutionContext, expected: int) -> None:
        actual = len(self._events.read(context.course_id))
        if actual != expected:
            raise RetryableArtifactConflictError(
                f"course stream advanced: expected {expected}, actual {actual}"
            )

    def _append(
        self, context: ExecutionContext, expected: int, event: DomainEvent, fingerprint: str
    ) -> ArtifactSnapshot:
        try:
            self._events.append(context.course_id, expected, (event,))
        except EventSequenceConflictError as error:
            existing = self._view.command_fingerprint(context.course_id, event.event_id)
            if existing is not None:
                if existing == fingerprint:
                    return self._view.get(context.course_id)
                raise ArtifactConflictError(
                    "artifact retry identity committed different content"
                ) from error
            raise RetryableArtifactConflictError(
                "course stream raced before artifact command committed"
            ) from error
        return self._view.get(context.course_id)

    def _event(
        self,
        context: ExecutionContext,
        event_id: EventId,
        event_type: str,
        sequence: int,
        payload: JsonObject,
    ) -> DomainEvent:
        return DomainEvent(
            event_id,
            context.course_id,
            sequence,
            event_type,
            ARTIFACT_SCHEMA_VERSION,
            Actor(context.principal_kind, context.principal_id),
            self._clock.now(),
            context.correlation_id,
            payload,
            context.session_id,
        )


def _context(context: ExecutionContext, required: PrincipalKind) -> tuple[SessionId, str]:
    if context.principal_kind is not required:
        raise ArtifactCommandError(f"artifact command requires {required.value.upper()} authority")
    if context.session_id is None:
        raise ArtifactCommandError("artifact command requires a session")
    if context.idempotency_key is None:
        raise ArtifactCommandError("artifact command requires an idempotency key")
    return context.session_id, context.idempotency_key


def _expected(value: int) -> None:
    if type(value) is not int or value < 1:
        raise ValueError("expected_sequence must be a positive integer")


def _proposed(
    snapshot: ArtifactSnapshot, revision_id: ArtifactRevisionId
) -> ArtifactRevisionRecord:
    try:
        target = snapshot.revision(revision_id)
    except LookupError as error:
        raise ArtifactCommandError("artifact decision target was not found") from error
    if target.status is not ArtifactRevisionStatus.PROPOSED:
        raise ArtifactConflictError("artifact decisions are terminal")
    return target


def _current_accepted(
    snapshot: ArtifactSnapshot, artifact_id: ArtifactId
) -> ArtifactRevisionRecord | None:
    accepted = tuple(
        item
        for item in snapshot.history(artifact_id)
        if item.status is ArtifactRevisionStatus.ACCEPTED
    )
    if len(accepted) > 1:
        raise ArtifactConflictError("artifact has multiple accepted revisions")
    return accepted[0] if accepted else None


def _require_decision_session(
    snapshot: ArtifactSnapshot,
    target: ArtifactRevisionRecord,
    session_id: SessionId,
) -> None:
    batch = next((item for item in snapshot.batches if item.id == target.batch_id), None)
    if batch is None or batch.session_id != session_id:
        raise ArtifactCommandError("artifact decision target belongs to another session")


def _parent_ordinal(content: StudyArtifactEnvelope) -> int | None:
    if isinstance(content.content, (HybridFlashcardContent, MorphologyFlashcardContent)):
        return content.content.parent_ordinal
    return None


def _validate_policy_result(
    request: ServiceDecisionPolicyRequest, receipt: ServiceDecisionPolicyReceipt
) -> None:
    if not isinstance(receipt, ServiceDecisionPolicyReceipt):
        raise ArtifactCommandError("decision policy returned an invalid receipt")
    if receipt.request_id != request.request_id:
        raise ArtifactCommandError("decision policy receipt belongs to another request")
    if receipt.decision is ArtifactDecision.ACCEPT:
        if receipt.supersedes_revision_id != request.current_accepted_revision_id:
            raise ArtifactCommandError("decision policy did not bind the accepted predecessor")
    elif receipt.supersedes_revision_id is not None:
        raise ArtifactCommandError("reject policy result cannot supersede")
    expected = service_decision_result_fingerprint(
        request, receipt.decision, receipt.supersedes_revision_id
    )
    if receipt.result_fingerprint != expected:
        raise ArtifactCommandError("decision policy result fingerprint mismatch")


__all__ = [
    "ArtifactCommandError",
    "ArtifactConflictError",
    "ArtifactService",
    "RetryableArtifactConflictError",
    "service_decision_result_fingerprint",
]
