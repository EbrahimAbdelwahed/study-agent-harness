"""Curated, provider-neutral assessment lifecycle facade."""

from study_agent.assessments.contracts import (
    AssessmentSnapshot,
    AttemptRecord,
    CanonicalResponse,
    CriterionResult,
    DeterministicGradeProvenance,
    FreeResponse,
    GradeContestRecord,
    GradeProvenance,
    GradeRecord,
    LearnerPresentationView,
    MultipleChoiceResponse,
    PresentationRecord,
    RationalScore,
    SingleChoiceResponse,
    ValidatorReceipt,
    VerifiedCapabilityGradeProvenance,
    canonical_multiple_choice,
    response_fingerprint,
)
from study_agent.assessments.evidence import (
    EvidenceDimension,
    EvidenceDisposition,
    LearnerEvidenceEstimate,
    LearnerEvidenceReference,
)
from study_agent.assessments.evidence import LearnerEvidenceSnapshot as LearningEvidence
from study_agent.ports.assessment import (
    AssessmentCommandPort,
    AssessmentViewPort,
    DeterministicClosedGradingPolicyPort,
    LearnerEvidenceViewPort,
    VerifiedGradePort,
)

__all__ = (
    "AssessmentCommandPort",
    "AssessmentSnapshot",
    "AssessmentViewPort",
    "AttemptRecord",
    "CanonicalResponse",
    "CriterionResult",
    "DeterministicClosedGradingPolicyPort",
    "DeterministicGradeProvenance",
    "EvidenceDimension",
    "EvidenceDisposition",
    "FreeResponse",
    "GradeContestRecord",
    "GradeProvenance",
    "GradeRecord",
    "LearnerEvidenceEstimate",
    "LearnerEvidenceReference",
    "LearnerEvidenceViewPort",
    "LearnerPresentationView",
    "LearningEvidence",
    "MultipleChoiceResponse",
    "PresentationRecord",
    "RationalScore",
    "SingleChoiceResponse",
    "ValidatorReceipt",
    "VerifiedCapabilityGradeProvenance",
    "VerifiedGradePort",
    "canonical_multiple_choice",
    "response_fingerprint",
)


def __dir__() -> list[str]:
    return sorted(__all__)
