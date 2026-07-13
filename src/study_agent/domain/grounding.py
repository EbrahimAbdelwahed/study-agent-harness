from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ._validation import require_text
from .provenance import AnswerProvenance, ClaimOrigin
from .source import Citation


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    FAILED = "failed"


class SegmentKind(StrEnum):
    SUPPORTED_CLAIM = "supported_claim"
    SYNTHESIS = "synthesis"
    UNCERTAINTY = "uncertainty"
    STUDY_GUIDANCE = "study_guidance"


@dataclass(frozen=True, slots=True)
class AnswerSegment:
    kind: SegmentKind
    text: str
    citations: tuple[Citation, ...] = ()
    claim_origin: ClaimOrigin = ClaimOrigin.INFERRED

    def __post_init__(self) -> None:
        object.__setattr__(self, "citations", tuple(self.citations))
        require_text(self.text, "text")
        if self.kind in (SegmentKind.SUPPORTED_CLAIM, SegmentKind.SYNTHESIS) and not self.citations:
            raise ValueError(f"{self.kind.value} segments require citations")
        if self.kind is SegmentKind.STUDY_GUIDANCE and self.citations:
            raise ValueError("study_guidance cannot introduce cited domain claims")


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    status: AnswerStatus
    segments: tuple[AnswerSegment, ...]
    unsupported_information_note: str | None
    provenance: AnswerProvenance

    def __post_init__(self) -> None:
        object.__setattr__(self, "segments", tuple(self.segments))
        claim_kinds = {SegmentKind.SUPPORTED_CLAIM, SegmentKind.SYNTHESIS}
        has_claims = any(segment.kind in claim_kinds for segment in self.segments)
        if self.status is AnswerStatus.ANSWERED and not has_claims:
            raise ValueError("answered output must contain a supported claim or synthesis")
        if self.status in (AnswerStatus.INSUFFICIENT_EVIDENCE, AnswerStatus.FAILED) and has_claims:
            raise ValueError(f"{self.status.value} output cannot contain supported claims")
        if self.status is not AnswerStatus.ANSWERED:
            if self.unsupported_information_note is None:
                raise ValueError("non-answered output requires an unsupported-information note")
            require_text(self.unsupported_information_note, "unsupported_information_note")
        if self.status is AnswerStatus.FAILED:
            raise ValueError("failed outputs cannot be persisted as grounded answers")
        has_citations = any(segment.citations for segment in self.segments)
        citation_commitments = tuple(
            (
                citation.source_id,
                citation.revision_id,
                citation.chunk_id,
                citation.start_offset,
                citation.end_offset,
            )
            for segment in self.segments
            for citation in segment.citations
        )
        unique_citation_commitments = tuple(dict.fromkeys(citation_commitments))
        provenance_commitments = tuple(
            (
                item.source_id,
                item.revision_id,
                item.chunk_id,
                item.start_offset,
                item.end_offset,
            )
            for item in self.provenance.source_commitments
        )
        if provenance_commitments != unique_citation_commitments:
            raise ValueError("source commitments must exactly match ordered canonical citations")
        if self.status is AnswerStatus.INSUFFICIENT_EVIDENCE:
            if self.provenance.model is not None:
                raise ValueError("insufficient evidence must not fabricate model provenance")
            if self.provenance.source_commitments or has_citations:
                raise ValueError("insufficient evidence cannot contain source commitments")
            sufficiency_receipts = tuple(
                item
                for item in self.provenance.validators
                if item.validator_id == "evidence_sufficiency"
            )
            if len(sufficiency_receipts) != 1:
                raise ValueError(
                    "insufficient evidence requires exactly one evidence_sufficiency validator"
                )
            sufficiency = sufficiency_receipts[0]
            if not sufficiency.passed or sufficiency.disposition != "terminate":
                raise ValueError(
                    "insufficient evidence requires a successful terminating "
                    "evidence_sufficiency validator"
                )
        elif self.status in (AnswerStatus.ANSWERED, AnswerStatus.CONFLICTING_EVIDENCE):
            if self.provenance.model is None:
                raise ValueError(f"{self.status.value} requires model provenance")
            if self.status is AnswerStatus.CONFLICTING_EVIDENCE and not has_citations:
                raise ValueError("conflicting evidence requires canonical citations")
            if not any(
                item.validator_id == "grounded_answer_integrity" and item.passed
                for item in self.provenance.validators
            ):
                raise ValueError(
                    f"{self.status.value} requires a passed grounded_answer_integrity validator"
                )
