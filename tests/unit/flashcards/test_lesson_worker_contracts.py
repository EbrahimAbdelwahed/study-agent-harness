from __future__ import annotations

import base64
import json
from dataclasses import replace
from hashlib import sha256

import pytest

from study_agent.capabilities import TutorCapabilityId
from study_agent.domain import (
    ChunkId,
    Citation,
    RevisionId,
    RunId,
    SourceChunk,
    SourceId,
)
from study_agent.domain._validation import JsonObject
from study_agent.flashcards import FlashcardScopeIndexEntry, PreparedFlashcardScope
from study_agent.flashcards.lesson_worker_contracts import (
    MAX_PREPARED_WRAPPER_BYTES,
    LessonWorkerCheckpoint,
    LessonWorkerPageCheckpoint,
    LessonWorkerPageStatus,
    LessonWorkerRequest,
    ProfileTaskExpectation,
    ResolvedPlannedBundleEvidence,
    RevisionContentCommitment,
    child_task_id,
    lesson_run_id,
)
from study_agent.flashcards.planning import (
    CanonicalSourceSpan,
    FlashcardLessonPlan,
    LessonGenerationUnit,
    LessonParagraph,
    LessonTopic,
    PreparedPlannedFlashcardScope,
    plan_flashcard_lesson,
)
from study_agent.grounding import EvidenceEnvelope
from study_agent.playbooks import ToolBehaviorPin, VersionPins
from study_agent.ports import (
    EvidenceStatus,
    RetrievalEvidence,
    RetrievalEvidenceSet,
    retrieval_read_set_fingerprint,
)
from study_agent.skills import ArtifactReference, SemanticVersion
from study_agent.workers import (
    ValidationExpectation,
    ValidationReceiptSource,
    fingerprint_output_schema,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
V1 = SemanticVersion.parse("1.0.0")
SCHEMA: JsonObject = {
    "type": "object",
    "properties": {
        "candidates": {"type": "array", "items": {"type": "string"}},
    },
    "required": ("candidates",),
    "additionalProperties": False,
}


def _span(source: str, revision: str, start: int, end: int) -> CanonicalSourceSpan:
    return CanonicalSourceSpan(
        SourceId(source),
        RevisionId(revision),
        start,
        end,
        f"Lesson [{start}:{end}]",
    )


def _plan() -> FlashcardLessonPlan:
    paragraphs = (
        LessonParagraph("p-a", "topic-a", 0, _span("source-a", "rev-a", 0, 10), 10),
        LessonParagraph("p-b", "topic-b", 1, _span("source-b", "rev-b", 0, 12), 12),
    )
    topics = (
        LessonTopic(
            "topic-a", "Topic A", 1, None, 0, _span("source-a", "rev-a", 0, 10), ("p-a",)
        ),
        LessonTopic(
            "topic-b", "Topic B", 1, None, 1, _span("source-b", "rev-b", 0, 12), ("p-b",)
        ),
    )
    return plan_flashcard_lesson(LessonGenerationUnit("lesson", "Lesson", topics, paragraphs))


def _multi_plan() -> FlashcardLessonPlan:
    size = 6_001
    paragraphs = (
        LessonParagraph("p-a", "topic-a", 0, _span("source-a", "rev-a", 0, size), size),
        LessonParagraph("p-b", "topic-b", 1, _span("source-b", "rev-b", 0, size), size),
    )
    topics = (
        LessonTopic(
            "topic-a", "Topic A", 1, None, 0, _span("source-a", "rev-a", 0, size), ("p-a",)
        ),
        LessonTopic(
            "topic-b", "Topic B", 1, None, 1, _span("source-b", "rev-b", 0, size), ("p-b",)
        ),
    )
    return plan_flashcard_lesson(
        LessonGenerationUnit("multi-lesson", "Multi lesson", topics, paragraphs)
    )


def _no_work_plan() -> FlashcardLessonPlan:
    topic = LessonTopic(
        "context-only",
        "Context only",
        1,
        None,
        0,
        _span("source-a", "rev-a", 0, 10),
    )
    return plan_flashcard_lesson(
        LessonGenerationUnit("empty-lesson", "Empty lesson", (topic,), ())
    )


def _pins() -> VersionPins:
    return VersionPins(
        ArtifactReference("hybrid_flashcards", V1),
        ArtifactReference("hybrid_flashcards_flow", V1),
        ArtifactReference("hybrid_flashcards.v1", V1),
        (ToolBehaviorPin("source.prepare_planned_flashcard_scope", V1),),
        ArtifactReference("model-adapter", V1),
        ArtifactReference("event-state", V1),
    )


def _profile(**changes: object) -> ProfileTaskExpectation:
    values: dict[str, object] = {
        "profile_fingerprint": SHA_A,
        "capability_id": TutorCapabilityId.PROPOSE_FLASHCARDS,
        "capability_version": V1,
        "manifest_fingerprint": SHA_B,
        "required_authority": ("source.read",),
        "pins": _pins(),
        "definition_fingerprint": SHA_C,
        "output_schema": SCHEMA,
        "output_schema_fingerprint": fingerprint_output_schema(SCHEMA),
        "validations": (
            ValidationExpectation(
                "integrity",
                ValidationReceiptSource.VALIDATE_STEP,
                "hybrid_flashcard_integrity",
                "1.0.0",
            ),
        ),
    }
    values.update(changes)
    return ProfileTaskExpectation(**values)  # type: ignore[arg-type]


def _request(**changes: object) -> LessonWorkerRequest:
    values: dict[str, object] = {
        "plan": _plan(),
        "query": "Generate grounded cards",
        "scope": "the uploaded lesson",
        "language": "it",
        "candidate_ceiling": 12,
        "continuation_summary": {"known": ("valves",), "score": 2},
        "profile_expectation": _profile(),
        "concurrency": 2,
        "revision_commitments": (
            RevisionContentCommitment(RevisionId("rev-a"), SHA_A),
            RevisionContentCommitment(RevisionId("rev-b"), SHA_B),
        ),
    }
    values.update(changes)
    return LessonWorkerRequest(**values)  # type: ignore[arg-type]


def _wrapper(
    request: LessonWorkerRequest, bundle_position: int = 0
) -> PreparedPlannedFlashcardScope:
    bundle = request.plan.bundles[bundle_position]
    evidence: list[RetrievalEvidence] = []
    for position, slot in enumerate(bundle.slots):
        text = "x" * slot.visible_character_count
        chunk = SourceChunk(
            ChunkId(f"chunk-{position}"),
            slot.span.source_id,
            slot.span.revision_id,
            slot.span.start_offset,
            slot.span.end_offset,
            (),
            position,
            sha256(text.encode()).hexdigest(),
            "fixture-chunker-v1",
        )
        evidence.append(
            RetrievalEvidence(
                chunk,
                Citation(
                    slot.span.source_id,
                    slot.span.revision_id,
                    chunk.chunk_id,
                    slot.span.start_offset,
                    slot.span.end_offset,
                    slot.span.locator,
                    text,
                ),
                text,
                1.0,
            )
        )
    ordered = tuple(evidence)
    envelope = EvidenceEnvelope.from_retrieval(
        RetrievalEvidenceSet(
            EvidenceStatus.SUFFICIENT,
            ordered,
            SHA_C,
            "fixture_lexical",
            "1.0.0",
            "fixture-index-v1",
            retrieval_read_set_fingerprint(ordered),
        )
    )
    handles_by_topic = {
        slot.topic_key: (envelope.items[position].handle,)
        for position, slot in enumerate(bundle.slots)
    }
    index = tuple(
        FlashcardScopeIndexEntry(
            item.topic_key,
            item.title,
            item.span.locator,
            item.relative_position,
            max(1, item.subtree_visible_character_count),
            handles_by_topic.get(item.topic_key, ()),
        )
        for item in request.plan.index
    )
    prepared = PreparedFlashcardScope.prepare(index, envelope)
    return PreparedPlannedFlashcardScope.prepare(prepared, request.plan, bundle.bundle_id)


def test_request_round_trips_exactly_and_has_one_public_payload_transformation() -> None:
    request = _request()

    assert LessonWorkerRequest.from_bytes(request.to_bytes()) == request
    assert request.to_public_inputs() == {
        "query": "Generate grounded cards",
        "scope": "the uploaded lesson",
        "language": "it",
        "candidate_ceiling": 12,
        "continuation_summary_json": '{"known":["valves"],"score":2}',
    }
    assert not ({"profile", "preferences", "authority"} & set(request.to_public_inputs()))


def test_request_decoder_rejects_unknown_fields_and_noncanonical_bytes() -> None:
    request = _request()
    decoded = json.loads(request.to_bytes())
    decoded["extra"] = True
    with pytest.raises(ValueError):
        LessonWorkerRequest.from_bytes(
            json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
        )
    with pytest.raises(ValueError, match="canonical"):
        LessonWorkerRequest.from_bytes(
            json.dumps(json.loads(request.to_bytes()), indent=2, sort_keys=True).encode()
        )


@pytest.mark.parametrize(
    "commitments",
    (
        (RevisionContentCommitment(RevisionId("rev-a"), SHA_A),),
        (
            RevisionContentCommitment(RevisionId("rev-a"), SHA_A),
            RevisionContentCommitment(RevisionId("rev-b"), SHA_B),
            RevisionContentCommitment(RevisionId("rev-extra"), SHA_C),
        ),
        (
            RevisionContentCommitment(RevisionId("rev-b"), SHA_B),
            RevisionContentCommitment(RevisionId("rev-a"), SHA_A),
        ),
        (
            RevisionContentCommitment(RevisionId("rev-a"), SHA_A),
            RevisionContentCommitment(RevisionId("rev-a"), SHA_B),
        ),
    ),
)
def test_request_requires_complete_sorted_unique_revision_commitments(
    commitments: tuple[RevisionContentCommitment, ...],
) -> None:
    with pytest.raises(ValueError):
        _request(revision_commitments=commitments)


def test_content_fingerprints_bind_request_and_authority_binds_run_identity() -> None:
    request = _request()
    changed = _request(
        revision_commitments=(
            RevisionContentCommitment(RevisionId("rev-a"), SHA_C),
            RevisionContentCommitment(RevisionId("rev-b"), SHA_B),
        )
    )

    assert request.fingerprint != changed.fingerprint
    assert lesson_run_id(request, SHA_A) == lesson_run_id(request, SHA_A)
    assert lesson_run_id(request, SHA_A) != lesson_run_id(request, SHA_B)


def test_profile_expectation_fingerprint_commits_every_returned_task_contract() -> None:
    expected = _profile()
    changed_schema: JsonObject = {
        "type": "object",
        "properties": {},
        "required": (),
        "additionalProperties": False,
    }
    mutations = (
        replace(expected, profile_fingerprint=SHA_B),
        replace(expected, manifest_fingerprint=SHA_C),
        replace(expected, required_authority=("source.read", "study:read")),
        replace(expected, definition_fingerprint=SHA_A),
        replace(
            expected,
            output_schema=changed_schema,
            output_schema_fingerprint=fingerprint_output_schema(changed_schema),
        ),
        replace(
            expected,
            validations=(
                ValidationExpectation(
                    "changed",
                    ValidationReceiptSource.VALIDATE_STEP,
                    "hybrid_flashcard_integrity",
                    "1.0.0",
                ),
            ),
        ),
    )
    assert all(item.fingerprint != expected.fingerprint for item in mutations)


def test_profile_expectation_rejects_schema_fingerprint_mismatch() -> None:
    with pytest.raises(ValueError, match="output schema fingerprint"):
        _profile(output_schema_fingerprint=SHA_A)


def test_resolved_evidence_is_exactly_one_ordered_item_per_planned_slot() -> None:
    request = _request()
    bundle = request.plan.bundles[0]
    envelope = _wrapper(request).prepared_scope.evidence
    resolved = ResolvedPlannedBundleEvidence(
        envelope,
        request.revision_commitments,
        request.plan.plan_fingerprint,
        bundle.bundle_id,
    )

    resolved.validate(request.plan, bundle, request.revision_commitments)

    reversed_items = tuple(reversed(envelope.items))
    reordered = EvidenceEnvelope(
        envelope.status,
        reversed_items,
        envelope.query_fingerprint,
        envelope.strategy_id,
        envelope.strategy_version,
        envelope.index_version,
        retrieval_read_set_fingerprint(tuple(item.evidence for item in reversed_items)),
    )
    with pytest.raises(ValueError, match="planned slot"):
        replace(resolved, envelope=reordered).validate(
            request.plan, bundle, request.revision_commitments
        )


def test_resolved_evidence_rejects_changed_plan_bundle_or_revision_content() -> None:
    request = _request()
    bundle = request.plan.bundles[0]
    resolved = ResolvedPlannedBundleEvidence(
        _wrapper(request).prepared_scope.evidence,
        request.revision_commitments,
        request.plan.plan_fingerprint,
        bundle.bundle_id,
    )
    changed = (
        RevisionContentCommitment(RevisionId("rev-a"), SHA_C),
        RevisionContentCommitment(RevisionId("rev-b"), SHA_B),
    )

    with pytest.raises(ValueError, match="commitments changed"):
        resolved.validate(request.plan, bundle, changed)
    with pytest.raises(ValueError, match="plan or bundle changed"):
        replace(resolved, bundle_id="changed").validate(
            request.plan, bundle, request.revision_commitments
        )


def test_257_pages_fail_explicitly_without_truncating_the_plan() -> None:
    plan = _plan()
    object.__setattr__(plan, "bundles", (plan.bundles[0],) * 257)

    with pytest.raises(ValueError, match="lesson_worker_page_limit_exceeded"):
        _request(plan=plan)


def test_prepared_wrapper_bound_fails_before_decoding_oversized_bytes() -> None:
    with pytest.raises(ValueError, match="exceeds 512 KiB"):
        LessonWorkerPageCheckpoint(
            position=0,
            bundle_id="bundle",
            status=LessonWorkerPageStatus.PREPARED,
            child_task_id="child",
            resolution_fingerprint=SHA_A,
            wrapper_bytes=b"x" * (MAX_PREPARED_WRAPPER_BYTES + 1),
        )


@pytest.mark.parametrize("mutation", ("index_metadata", "active_handle_links"))
def test_checkpoint_decode_rejects_self_consistent_prepared_scope_tampering(
    mutation: str,
) -> None:
    request = _request()
    bundle = request.plan.bundles[0]
    wrapper = _wrapper(request)
    run_id = lesson_run_id(request, SHA_A)
    resolved = ResolvedPlannedBundleEvidence(
        wrapper.prepared_scope.evidence,
        request.revision_commitments,
        request.plan.plan_fingerprint,
        bundle.bundle_id,
    )
    page = LessonWorkerPageCheckpoint(
        position=0,
        bundle_id=bundle.bundle_id,
        status=LessonWorkerPageStatus.PREPARED,
        child_task_id=child_task_id(run_id, request, bundle, wrapper),
        resolution_fingerprint=resolved.fingerprint,
        wrapper_bytes=wrapper.to_bytes(),
    )
    checkpoint = LessonWorkerCheckpoint(
        request.to_bytes(), request.fingerprint, SHA_A, run_id, (page,)
    )

    index = list(wrapper.prepared_scope.index)
    index[0] = (
        replace(index[0], heading="Self-consistent forged heading")
        if mutation == "index_metadata"
        else replace(index[0], evidence_handles=())
    )
    forged_scope = PreparedFlashcardScope.prepare(
        tuple(index), wrapper.prepared_scope.evidence
    )
    forged_wrapper = PreparedPlannedFlashcardScope.prepare(
        forged_scope, request.plan, bundle.bundle_id
    )
    decoded = json.loads(checkpoint.to_bytes())
    decoded["pages"][0]["wrapper_bytes"] = base64.b64encode(
        forged_wrapper.to_bytes()
    ).decode("ascii")
    decoded["pages"][0]["child_task_id"] = child_task_id(
        run_id, request, bundle, forged_wrapper
    )

    with pytest.raises(ValueError, match="prepared scope differs from lesson plan"):
        LessonWorkerCheckpoint.from_bytes(
            json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
        )


def test_checkpoint_decode_rejects_forged_run_id_even_when_canonical() -> None:
    request = _request()
    run_id = lesson_run_id(request, SHA_A)
    checkpoint = LessonWorkerCheckpoint(
        request.to_bytes(),
        request.fingerprint,
        SHA_A,
        run_id,
        (
            LessonWorkerPageCheckpoint(
                position=0,
                bundle_id=request.plan.bundles[0].bundle_id,
                status=LessonWorkerPageStatus.PENDING,
                child_task_id=child_task_id(
                    run_id, request, request.plan.bundles[0], None
                ),
            ),
        ),
    )
    decoded = json.loads(checkpoint.to_bytes())
    decoded["run_id"] = str(RunId("forged-lesson-run"))

    with pytest.raises(ValueError, match="lesson run identity is invalid"):
        LessonWorkerCheckpoint.from_bytes(
            json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
        )
