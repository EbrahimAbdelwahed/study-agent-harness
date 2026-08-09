"""Curated, provider-neutral source and citation contracts.

The facade re-exports immutable value types and canonical citation codecs from
their domain owners.  It deliberately does not import ingestion adapters,
filesystem implementations, providers, or retrieval indexes: hosts supply
canonical bytes through their own composition boundary.
"""

from study_agent.domain.citation_v2 import (
    FIGURE_CITATION_VERSION,
    TEXT_CITATION_VERSION,
    Citation,
    CitationFailure,
    CitationFailureKind,
    DerivedRef,
    FigureCitationV1,
    TextCitationV2,
    citation_from_bytes,
    citation_from_json,
)
from study_agent.domain.source import BlobRef, SourceRevision, SourceRevisionRef, SubstrateRef

__all__ = (
    "FIGURE_CITATION_VERSION",
    "TEXT_CITATION_VERSION",
    "BlobRef",
    "Citation",
    "CitationFailure",
    "CitationFailureKind",
    "DerivedRef",
    "FigureCitationV1",
    "SourceRevision",
    "SourceRevisionRef",
    "SubstrateRef",
    "TextCitationV2",
    "citation_from_bytes",
    "citation_from_json",
)
