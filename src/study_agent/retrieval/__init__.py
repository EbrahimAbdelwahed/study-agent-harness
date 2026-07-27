"""Source retrieval services and reference implementations."""

from study_agent.ports.retrieval import (
    RetrievalDocument,
    retrieval_read_set_fingerprint,
)

from .content import CourseSourceContent, SourceRevisionRecord
from .errors import SourceContentError, SourceContentErrorCode
from .fusion import (
    AdmittedUnitCatalog,
    FusedEvidenceGroup,
    FusionContextAttachment,
    FusionError,
    FusionPolicy,
    FusionPriorReceipt,
    FusionResult,
    FusionResultStatus,
    FusionStatus,
    fuse_candidates,
)
from .lexical import LexicalRetriever
from .registry import RetrieverRegistry, RetrieverRegistryError

__all__ = [
    "AdmittedUnitCatalog",
    "CourseSourceContent",
    "FusedEvidenceGroup",
    "FusionContextAttachment",
    "FusionError",
    "FusionPolicy",
    "FusionPriorReceipt",
    "FusionResult",
    "FusionResultStatus",
    "FusionStatus",
    "LexicalRetriever",
    "RetrievalDocument",
    "RetrieverRegistry",
    "RetrieverRegistryError",
    "SourceContentError",
    "SourceContentErrorCode",
    "SourceRevisionRecord",
    "fuse_candidates",
    "retrieval_read_set_fingerprint",
]
