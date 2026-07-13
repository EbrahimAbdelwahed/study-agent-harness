from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
from typing import cast

from study_agent.domain import (
    ChunkId,
    Citation,
    ResolvedCitation,
    RevisionId,
    SourceChunk,
    SourceId,
)
from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.grounding import (
    EvidenceEnvelope,
    EvidenceSufficiencyValidator,
    GroundedAnswerIntegrityValidator,
)
from study_agent.playbooks import ValidatorDisposition
from study_agent.ports import (
    EvidenceStatus,
    RetrievalEvidence,
    RetrievalEvidenceSet,
    retrieval_read_set_fingerprint,
)


class Content:
    def __init__(self, citation: Citation, text: str) -> None:
        self.citation = citation
        self.text = text

    def get_text(self, revision_id: RevisionId) -> str:
        return self.text

    def resolve(self, citation: Citation) -> ResolvedCitation:
        if citation != self.citation:
            raise ValueError("citation differs from canonical content")
        return ResolvedCitation(self.citation, self.text)


def evidence_set(status: EvidenceStatus = EvidenceStatus.SUFFICIENT) -> RetrievalEvidenceSet:
    if status is EvidenceStatus.INSUFFICIENT:
        items: tuple[RetrievalEvidence, ...] = ()
        return RetrievalEvidenceSet(
            status,
            items,
            "a" * 64,
            "fixture_lexical",
            "1.0.0",
            "fixture-index-v1",
            retrieval_read_set_fingerprint(items),
        )
    text = "La valvola aortica ha tre cuspidi."
    source_id = SourceId("source-1")
    revision_id = RevisionId("revision-1")
    chunk = SourceChunk(
        ChunkId("chunk-1"),
        source_id,
        revision_id,
        0,
        len(text),
        (),
        0,
        sha256(text.encode()).hexdigest(),
        "chunker-v1",
    )
    citation = Citation(
        source_id,
        revision_id,
        chunk.chunk_id,
        0,
        len(text),
        "Fixture > chunk 1",
        text,
    )
    items = (RetrievalEvidence(chunk, citation, text, 0.8),)
    return RetrievalEvidenceSet(
        status,
        items,
        "a" * 64,
        "fixture_lexical",
        "1.0.0",
        "fixture-index-v1",
        retrieval_read_set_fingerprint(items),
    )


def answer(handle: str, *, status: str = "answered") -> JsonObject:
    return freeze_object(
        {
            "status": status,
            "segments": (
                {
                    "kind": "supported_claim",
                    "text": "La valvola aortica ha tre cuspidi.",
                    "evidence_ids": (handle,),
                },
            ),
            "unsupported_information_note": (
                "Le fonti sono in conflitto." if status == "conflicting_evidence" else None
            ),
        }
    )


def test_evidence_envelope_has_stable_opaque_handles_and_strict_fields() -> None:
    retrieval = evidence_set()
    first = EvidenceEnvelope.from_retrieval(retrieval)
    second = EvidenceEnvelope.from_retrieval(retrieval)

    assert first == second
    assert first.items[0].handle.startswith("ev_")
    assert "chunk-1" not in first.items[0].handle
    assert EvidenceEnvelope.from_json(first.to_json()).to_json() == first.to_json()

    forged = dict(first.to_json())
    forged["provider"] = "not allowed"
    outcome = asyncio.run(EvidenceSufficiencyValidator().validate({"evidence": forged}))
    assert not outcome.passed
    assert outcome.disposition is ValidatorDisposition.TERMINATE

    forged_receipt = dict(first.to_json())
    forged_receipt["read_set_fingerprint"] = "f" * 64
    receipt_outcome = asyncio.run(
        EvidenceSufficiencyValidator().validate({"evidence": forged_receipt})
    )
    assert not receipt_outcome.passed
    assert receipt_outcome.disposition is ValidatorDisposition.TERMINATE


def test_insufficient_evidence_terminates_with_deterministic_result() -> None:
    envelope = EvidenceEnvelope.from_retrieval(evidence_set(EvidenceStatus.INSUFFICIENT))

    outcome = asyncio.run(
        EvidenceSufficiencyValidator().validate({"evidence": envelope.to_json()})
    )

    assert outcome.passed
    assert outcome.disposition is ValidatorDisposition.TERMINATE
    assert outcome.result["status"] == "insufficient_evidence"
    assert outcome.result["segments"] == ()


def test_fallback_schema_validator_accepts_only_the_parsed_draft_contract() -> None:
    retrieval = evidence_set()
    handle = EvidenceEnvelope.from_retrieval(retrieval).items[0].handle
    canonical = retrieval.evidence[0]
    validator = GroundedAnswerIntegrityValidator(
        Content(canonical.citation, canonical.text)
    )

    accepted = asyncio.run(validator.validate({"output": answer(handle)}))
    rejected = asyncio.run(
        validator.validate(
            {"output": freeze_object({**answer(handle), "provider": "forged"})}
        )
    )

    assert accepted.passed
    assert accepted.result == {"schema_valid": True}
    assert not rejected.passed
    assert rejected.disposition is ValidatorDisposition.TERMINATE


def test_integrity_validator_reconstructs_and_reresolves_trusted_citation() -> None:
    retrieval = evidence_set()
    envelope = EvidenceEnvelope.from_retrieval(retrieval)
    handle = envelope.items[0].handle
    canonical = retrieval.evidence[0]
    validator = GroundedAnswerIntegrityValidator(
        Content(canonical.citation, canonical.text)
    )

    outcome = asyncio.run(
        validator.validate({"answer": answer(handle), "evidence": envelope.to_json()})
    )

    assert outcome.passed
    segments = cast(tuple[JsonValue, ...], outcome.result["segments"])
    segment = cast(Mapping[str, JsonValue], segments[0])
    citations = cast(tuple[JsonValue, ...], segment["citations"])
    citation = cast(Mapping[str, JsonValue], citations[0])
    assert citation["revision_id"] == "revision-1"
    assert citation["quoted_snippet"] == canonical.text


def test_unknown_duplicate_extra_and_stale_evidence_fail_closed() -> None:
    retrieval = evidence_set()
    envelope = EvidenceEnvelope.from_retrieval(retrieval)
    canonical = retrieval.evidence[0]
    validator = GroundedAnswerIntegrityValidator(
        Content(canonical.citation, canonical.text)
    )
    handle = envelope.items[0].handle
    cases: tuple[JsonObject, ...] = (
        answer("ev_unknown"),
        freeze_object(
            {
                **answer(handle),
                "segments": (
                    {
                        "kind": "supported_claim",
                        "text": "Claim",
                        "evidence_ids": (handle, handle),
                    },
                ),
            }
        ),
        freeze_object({**answer(handle), "citation": {"revision_id": "forged"}}),
    )

    stale_content = Content(replace(canonical.citation, locator="changed"), canonical.text)
    stale_validator = GroundedAnswerIntegrityValidator(stale_content)
    stale = asyncio.run(
        stale_validator.validate(
            {"answer": answer(handle), "evidence": envelope.to_json()}
        )
    )
    outcomes = [
        asyncio.run(validator.validate({"answer": case, "evidence": envelope.to_json()}))
        for case in cases
    ] + [stale]

    assert all(not outcome.passed for outcome in outcomes)
    assert all(
        outcome.disposition is ValidatorDisposition.TERMINATE for outcome in outcomes
    )


def test_conflicting_evidence_cannot_collapse_to_answered() -> None:
    retrieval = evidence_set(EvidenceStatus.CONFLICTING)
    envelope = EvidenceEnvelope.from_retrieval(retrieval)
    canonical = retrieval.evidence[0]
    validator = GroundedAnswerIntegrityValidator(
        Content(canonical.citation, canonical.text)
    )
    handle = envelope.items[0].handle

    collapsed = asyncio.run(
        validator.validate({"answer": answer(handle), "evidence": envelope.to_json()})
    )
    surfaced = asyncio.run(
        validator.validate(
            {
                "answer": answer(handle, status="conflicting_evidence"),
                "evidence": envelope.to_json(),
            }
        )
    )

    assert not collapsed.passed
    assert surfaced.passed
