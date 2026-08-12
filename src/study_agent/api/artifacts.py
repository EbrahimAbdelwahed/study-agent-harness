"""Curated, provider-neutral artifact lifecycle facade.

The domain package owns artifact mechanics.  This module is the supported
host seam and deliberately excludes services, event codecs, projections, and
storage compatibility helpers.
"""

from study_agent.api.sources import (
    BlobRef,
    Citation,
    DerivedRef,
    FigureCitationV1,
    SourceRevision,
    SourceRevisionRef,
    SubstrateRef,
    TextCitationV2,
)
from study_agent.artifacts.content import (
    AnswerBlock,
    ArtifactContent,
    AssessmentItemContent,
    EvidenceObservation,
    ExamBlueprintContent,
    FlashcardContent,
    HybridFlashcardContent,
    MorphologyFlashcardContent,
    StudyArtifactEnvelope,
    StudyBriefContent,
    StudyBriefSection,
)
from study_agent.artifacts.contracts import (
    ArtifactBatchRecord,
    ArtifactBulkDecisionReceipt,
    ArtifactDecisionRecord,
    ArtifactDecisionRequest,
    ArtifactDecisionResult,
    ArtifactProposal,
    ArtifactProposalOrigin,
    ArtifactRevisionRecord,
    ArtifactSnapshot,
    GeneratedBatchProofReceipt,
    ServiceDecisionPolicyReceipt,
    ServiceDecisionPolicyRequest,
    VerifiedGeneratedArtifactBatch,
)
from study_agent.artifacts.identity import (
    ArtifactProvenance,
    ArtifactProvenanceOrigin,
    GeneratedArtifactProvenance,
    HumanAuthoredArtifactProvenance,
)
from study_agent.domain import (
    ArtifactBatchId,
    ArtifactDecision,
    ArtifactId,
    ArtifactReadDependency,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    SourceCommitment,
)
from study_agent.ports.artifact import ArtifactCommandPort, ArtifactViewPort

__all__ = (
    "AnswerBlock",
    "ArtifactBatchId",
    "ArtifactBatchRecord",
    "ArtifactBulkDecisionReceipt",
    "ArtifactCommandPort",
    "ArtifactContent",
    "ArtifactDecision",
    "ArtifactDecisionRecord",
    "ArtifactDecisionRequest",
    "ArtifactDecisionResult",
    "ArtifactId",
    "ArtifactProposal",
    "ArtifactProposalOrigin",
    "ArtifactProvenance",
    "ArtifactProvenanceOrigin",
    "ArtifactReadDependency",
    "ArtifactRevisionId",
    "ArtifactRevisionRecord",
    "ArtifactRevisionStatus",
    "ArtifactSnapshot",
    "ArtifactViewPort",
    "AssessmentItemContent",
    "BlobRef",
    "Citation",
    "DerivedRef",
    "EvidenceObservation",
    "ExamBlueprintContent",
    "FigureCitationV1",
    "FlashcardContent",
    "GeneratedArtifactProvenance",
    "GeneratedBatchProofReceipt",
    "HumanAuthoredArtifactProvenance",
    "HybridFlashcardContent",
    "MorphologyFlashcardContent",
    "ServiceDecisionPolicyReceipt",
    "ServiceDecisionPolicyRequest",
    "SourceCommitment",
    "SourceRevision",
    "SourceRevisionRef",
    "StudyArtifactEnvelope",
    "StudyBriefContent",
    "StudyBriefSection",
    "SubstrateRef",
    "TextCitationV2",
    "VerifiedGeneratedArtifactBatch",
)


def __dir__() -> list[str]:
    return sorted(__all__)
