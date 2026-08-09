"""Provider- and framework-neutral public protocols."""

# Public re-exports intentionally define the small package-level API.

from typing import TYPE_CHECKING, Any

from .artifact import (
    ArtifactViewPort,
    ServiceDecisionPolicyPort,
    SourceCommitmentLookupPort,
    VerifiedGeneratedBatchPort,
)
from .assessment import (
    AssessmentViewPort,
    DeterministicClosedGradingPolicyPort,
    LearnerEvidenceViewPort,
    VerifiedGradeOwnerStore,
    VerifiedGradePort,
)
from .clock import ClockPort
from .course import CourseCatalogPort, CourseNotFoundError, CourseViewPort
from .host_file import (
    HostFileIdentityPort,
    HostFileIngestionPort,
    HostFileSnapshotStore,
)
from .knowledge import (
    LexicalCandidate,
    LexicalCandidateList,
    LexicalCatalogPort,
    LexicalIndexPort,
    LexicalIndexReceipt,
    LexicalProjectionBinding,
    LexicalQuery,
    LexicalSurface,
)
from .model import (
    CancellationToken,
    MessageRole,
    ModelCapabilities,
    ModelError,
    ModelErrorCode,
    ModelFinishReason,
    ModelInvocation,
    ModelMessage,
    ModelPort,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventKind,
    ModelUsage,
    StructuredOutputConstraint,
    ToolCall,
)
from .retrieval import (
    EvidenceStatus,
    IndexReceipt,
    RetrievalEvidence,
    RetrievalEvidenceSet,
    RetrievalPort,
    RetrievalQuery,
    retrieval_read_set_fingerprint,
)
from .retrievers import (
    RetrieverCandidate,
    RetrieverCandidateList,
    RetrieverCost,
    RetrieverFilter,
    RetrieverHostAuthority,
    RetrieverManifest,
    RetrieverNetwork,
    RetrieverPort,
    RetrieverQuery,
    RetrieverSearchBatch,
    RetrieverSkipCode,
    RetrieverSkipReason,
    RetrieverSkipReceipt,
)
from .session import (
    AnswerNotFoundError,
    AssistantTurnViewPort,
    SessionNotFoundError,
    SessionViewPort,
)
from .source_input import (
    MAX_SOURCE_BYTES,
    MAX_TOTAL_SOURCE_BYTES,
    MAX_TOTAL_SOURCES,
    SourceInputPort,
    SourceSnapshot,
)
from .storage import (
    BlobStore,
    EventSequenceConflictError,
    EventStore,
    RunStore,
    SourceContentPort,
)
from .study_context import StudyContextViewPort
from .tools import StudyTool
from .tutor_host import (
    RetryableTutorDecisionError,
    TutorDecisionPort,
    TutorInterruptionToken,
)
from .tutor_runner import (
    TutorCapabilityGatewayPort,
    TutorContinuationStore,
    TutorHostActionIdentityPort,
    TutorHostAuthorityPort,
)
from .tutor_snapshot import TutorSnapshotPort

if TYPE_CHECKING:
    from .recall import RecallCommandPort, RecallViewPort
    from .scheduling import SchedulingPolicyPort
    from .workaround import WorkaroundApprovalAuthority, WorkaroundExecutor


def __getattr__(name: str) -> Any:
    """Load optional public protocols without activating their feature packages."""

    if name in {"RecallCommandPort", "RecallViewPort"}:
        from . import recall

        return getattr(recall, name)
    if name == "SchedulingPolicyPort":
        from .scheduling import SchedulingPolicyPort

        return SchedulingPolicyPort
    if name in {"WorkaroundApprovalAuthority", "WorkaroundExecutor"}:
        from . import workaround

        return getattr(workaround, name)
    raise AttributeError(name)

__all__ = [
    "MAX_SOURCE_BYTES",
    "MAX_TOTAL_SOURCES",
    "MAX_TOTAL_SOURCE_BYTES",
    "AnswerNotFoundError",
    "ArtifactViewPort",
    "AssessmentViewPort",
    "AssistantTurnViewPort",
    "BlobStore",
    "CancellationToken",
    "ClockPort",
    "CourseCatalogPort",
    "CourseNotFoundError",
    "CourseViewPort",
    "DeterministicClosedGradingPolicyPort",
    "EventSequenceConflictError",
    "EventStore",
    "EvidenceStatus",
    "HostFileIdentityPort",
    "HostFileIngestionPort",
    "HostFileSnapshotStore",
    "IndexReceipt",
    "LearnerEvidenceViewPort",
    "LexicalCandidate",
    "LexicalCandidateList",
    "LexicalCatalogPort",
    "LexicalIndexPort",
    "LexicalIndexReceipt",
    "LexicalProjectionBinding",
    "LexicalQuery",
    "LexicalSurface",
    "MessageRole",
    "ModelCapabilities",
    "ModelError",
    "ModelErrorCode",
    "ModelFinishReason",
    "ModelInvocation",
    "ModelMessage",
    "ModelPort",
    "ModelRequest",
    "ModelResponse",
    "ModelStreamEvent",
    "ModelStreamEventKind",
    "ModelUsage",
    "RecallCommandPort",
    "RecallViewPort",
    "RetrievalEvidence",
    "RetrievalEvidenceSet",
    "RetrievalPort",
    "RetrievalQuery",
    "RetrieverCandidate",
    "RetrieverCandidateList",
    "RetrieverCost",
    "RetrieverFilter",
    "RetrieverHostAuthority",
    "RetrieverManifest",
    "RetrieverNetwork",
    "RetrieverPort",
    "RetrieverQuery",
    "RetrieverSearchBatch",
    "RetrieverSkipCode",
    "RetrieverSkipReason",
    "RetrieverSkipReceipt",
    "RetryableTutorDecisionError",
    "RunStore",
    "SchedulingPolicyPort",
    "ServiceDecisionPolicyPort",
    "SessionNotFoundError",
    "SessionViewPort",
    "SourceCommitmentLookupPort",
    "SourceContentPort",
    "SourceInputPort",
    "SourceSnapshot",
    "StructuredOutputConstraint",
    "StudyContextViewPort",
    "StudyTool",
    "ToolCall",
    "TutorCapabilityGatewayPort",
    "TutorContinuationStore",
    "TutorDecisionPort",
    "TutorHostActionIdentityPort",
    "TutorHostAuthorityPort",
    "TutorInterruptionToken",
    "TutorSnapshotPort",
    "VerifiedGeneratedBatchPort",
    "VerifiedGradeOwnerStore",
    "VerifiedGradePort",
    "WorkaroundApprovalAuthority",
    "WorkaroundExecutor",
    "retrieval_read_set_fingerprint",
]
