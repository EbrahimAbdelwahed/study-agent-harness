"""Grounded-answer contracts, citation resolution, and validation."""

from .draft import (
    GROUNDED_ANSWER_DRAFT_SCHEMA,
    DraftSegment,
    GroundedAnswerDraft,
)
from .evidence import (
    EvidenceEnvelope,
    EvidenceItem,
    GroundingContractError,
    evidence_handle,
)
from .validators import (
    EvidenceSufficiencyValidator,
    GroundedAnswerIntegrityValidator,
)

__all__ = [
    "GROUNDED_ANSWER_DRAFT_SCHEMA",
    "DraftSegment",
    "EvidenceEnvelope",
    "EvidenceItem",
    "EvidenceSufficiencyValidator",
    "GroundedAnswerDraft",
    "GroundedAnswerIntegrityValidator",
    "GroundingContractError",
    "evidence_handle",
]
