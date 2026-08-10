"""Curated, provider-neutral source and citation contracts.

The domain citation codec keeps its detailed failure reasons private.  This
facade translates those reasons into the closed PF-02 failure taxonomy and
never exposes the implementation exception or parser/adapter text.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Protocol, cast

import study_agent.domain.citation_v2 as _citation_domain
from study_agent.domain._validation import JsonObject
from study_agent.domain.citation_v2 import (
    FIGURE_CITATION_VERSION,
    TEXT_CITATION_VERSION,
    Citation,
    DerivedRef,
    FigureCitationV1,
    TextCitationV2,
)
from study_agent.domain.errors import HarnessError as _HarnessError
from study_agent.domain.errors import ValidationFailure as _ValidationFailure
from study_agent.domain.identifiers import (
    ChunkId as _ChunkId,
)
from study_agent.domain.identifiers import CorrelationId
from study_agent.domain.identifiers import (
    RevisionId as _RevisionId,
)
from study_agent.domain.identifiers import (
    SourceId as _SourceId,
)
from study_agent.domain.identifiers import (
    SubstrateId as _SubstrateId,
)
from study_agent.domain.lineage import RevisionRef as _RevisionRef
from study_agent.domain.lineage import SelectionStatus as _SelectionStatus
from study_agent.domain.source import (
    BlobRef,
    SourceRevision,
    SourceRevisionRef,
    SubstrateRef,
)
from study_agent.domain.source import (
    Citation as _LegacyCitation,
)
from study_agent.domain.source import (
    SourceChunk as _SourceChunk,
)
from study_agent.domain.units import RetrievableUnit as _RetrievableUnit
from study_agent.domain.units import TextSpan as _TextSpan

if TYPE_CHECKING:
    from study_agent.knowledge.citation import ResolvedCitation

_CitationFailure = _citation_domain.CitationFailure
_CitationFailureKind = _citation_domain.CitationFailureKind

_CITATION_REASONS: dict[object, str] = {
    _CitationFailureKind.MISSING: "missing",
    _CitationFailureKind.CORRUPT: "corrupt",
    _CitationFailureKind.OUT_OF_UNIT: "out_of_unit",
    _CitationFailureKind.MISMATCHED_CHECKSUM: "mismatched_checksum",
    _CitationFailureKind.UNSUPPORTED_VERSION: "unsupported_version",
    _CitationFailureKind.REFERENCE_MISMATCH: "reference_mismatch",
    _CitationFailureKind.MALFORMED_SPAN: "malformed_span",
    _CitationFailureKind.NOT_A_CITATION: "not_a_citation",
}
if set(_CITATION_REASONS) != set(_CitationFailureKind):  # pragma: no cover
    raise RuntimeError("citation failure mapping is incomplete")


def _citation_failure_to_harness_error(
    error: _CitationFailure, *, correlation_id: CorrelationId | None = None
) -> _ValidationFailure:
    reason = _CITATION_REASONS[error.kind]
    return _ValidationFailure(
        "citation failed validation",
        correlation_id=correlation_id,
        details={"reason_kind": reason},
    )


def _invoke[T](
    operation: Callable[[], T], *, correlation_id: CorrelationId | None = None
) -> T:
    try:
        return operation()
    except _CitationFailure as error:
        raise _citation_failure_to_harness_error(
            error, correlation_id=correlation_id
        ) from error
    except _HarnessError:
        raise
    except Exception as error:
        internal = _CitationFailure(
            _CitationFailureKind.CORRUPT, "citation operation failed"
        )
        raise _citation_failure_to_harness_error(
            internal, correlation_id=correlation_id
        ) from error


def citation_from_bytes(
    data: object, *, correlation_id: CorrelationId | None = None
) -> Citation:
    """Decode bounded canonical citation bytes through the public failure seam."""

    return _invoke(
        lambda: _citation_domain.citation_from_bytes(cast(bytes, data)),
        correlation_id=correlation_id,
    )


def citation_from_json(
    value: object, *, correlation_id: CorrelationId | None = None
) -> Citation:
    """Decode bounded citation JSON through the public failure seam."""

    return _invoke(
        lambda: _citation_domain.citation_from_json(cast(JsonObject, value)),
        correlation_id=correlation_id,
    )


def text_citation_for(
    unit: _RetrievableUnit,
    *,
    substrate_bytes: bytes,
    start: int,
    end: int,
    locator: str | None = None,
    page_hint: int | None = None,
    correlation_id: CorrelationId | None = None,
) -> TextCitationV2:
    """Mint a citation only from host-supplied canonical bytes."""

    def operation() -> TextCitationV2:
        from study_agent.knowledge.citation import text_citation_for as implementation

        return implementation(
            unit,
            substrate_bytes=substrate_bytes,
            start=start,
            end=end,
            locator=locator,
            page_hint=page_hint,
        )

    return _invoke(operation, correlation_id=correlation_id)


def verify_text_citation(
    citation: Citation | DerivedRef,
    *,
    substrate_bytes: bytes,
    unit: _RetrievableUnit,
    selection_status: _SelectionStatus,
    successor: _RevisionRef | None = None,
    correlation_id: CorrelationId | None = None,
) -> ResolvedCitation:
    """Resolve text evidence through the typed public failure seam."""

    def operation() -> ResolvedCitation:
        from study_agent.knowledge.citation import (
            verify_text_citation as implementation,
        )

        return implementation(
            citation,
            substrate_bytes=substrate_bytes,
            unit=unit,
            selection_status=selection_status,
            successor=successor,
        )

    return _invoke(operation, correlation_id=correlation_id)


def verify_figure_citation(
    citation: Citation | DerivedRef,
    *,
    image_bytes: bytes,
    selection_status: _SelectionStatus,
    successor: _RevisionRef | None = None,
    correlation_id: CorrelationId | None = None,
) -> ResolvedCitation:
    """Resolve figure evidence through the typed public failure seam."""

    def operation() -> ResolvedCitation:
        from study_agent.knowledge.citation import (
            verify_figure_citation as implementation,
        )

        return implementation(
            citation,
            image_bytes=image_bytes,
            selection_status=selection_status,
            successor=successor,
        )

    return _invoke(operation, correlation_id=correlation_id)


@dataclass(frozen=True, slots=True)
class LegacyCitationBinding:
    """One replay-derived binding for an exact v0.1 chunk key."""

    chunk: _SourceChunk
    unit: _RetrievableUnit
    substrate_bytes: bytes
    selection_status: _SelectionStatus
    successor: _RevisionRef | None = None


class LegacyCitationBindingPort(Protocol):
    """Resolve only the canonical chunk binding selected by replay."""

    def resolve(
        self, source_id: _SourceId, revision_id: _RevisionId, chunk_id: _ChunkId
    ) -> LegacyCitationBinding | None: ...


def _upgrade_legacy_impl(
    citation: _LegacyCitation, bindings: LegacyCitationBindingPort
) -> TextCitationV2:
    if not isinstance(citation, _LegacyCitation):
        raise _CitationFailure(_CitationFailureKind.UNSUPPORTED_VERSION, "legacy citation expected")
    try:
        binding = bindings.resolve(citation.source_id, citation.revision_id, citation.chunk_id)
    except Exception as error:
        raise _CitationFailure(
            _CitationFailureKind.CORRUPT, "legacy citation binding failed"
        ) from error
    if binding is None:
        raise _CitationFailure(_CitationFailureKind.MISSING, "legacy citation binding is missing")
    if not isinstance(binding, LegacyCitationBinding):
        raise _CitationFailure(_CitationFailureKind.CORRUPT, "legacy citation binding is invalid")
    chunk = binding.chunk
    unit = binding.unit
    if (
        chunk.source_id != citation.source_id
        or chunk.revision_id != citation.revision_id
        or chunk.chunk_id != citation.chunk_id
        or unit.source_id != citation.source_id
        or unit.revision_id != citation.revision_id
    ):
        raise _CitationFailure(
            _CitationFailureKind.REFERENCE_MISMATCH,
            "legacy citation binding does not match its key",
        )
    if type(binding.substrate_bytes) is not bytes or not binding.substrate_bytes:
        raise _CitationFailure(_CitationFailureKind.MISSING, "legacy substrate bytes are missing")
    try:
        text = binding.substrate_bytes.decode("utf-8", errors="strict")
    except UnicodeError as error:
        raise _CitationFailure(
            _CitationFailureKind.CORRUPT, "legacy substrate is not valid UTF-8"
        ) from error
    substrate_id = unit.substrate_id
    if not isinstance(substrate_id, _SubstrateId):
        raise _CitationFailure(
            _CitationFailureKind.REFERENCE_MISMATCH, "legacy unit is not text-bound"
        )
    from study_agent.ingestion.identity import chunk_id_for
    from study_agent.knowledge.units import unit_from_legacy_chunk

    expected_chunk_id = chunk_id_for(
        source_id=chunk.source_id,
        revision_id=chunk.revision_id,
        start_offset=chunk.start_offset,
        end_offset=chunk.end_offset,
        checksum_sha256=chunk.checksum_sha256,
        chunker_version=chunk.chunker_version,
    )
    if chunk.chunk_id != expected_chunk_id:
        raise _CitationFailure(
            _CitationFailureKind.REFERENCE_MISMATCH,
            "legacy chunk identity is invalid",
        )
    span = unit.canonical_ref
    if not isinstance(span, _TextSpan):
        raise _CitationFailure(_CitationFailureKind.REFERENCE_MISMATCH, "legacy unit is not a span")
    if (
        span.substrate_id != substrate_id
        or span.start != chunk.start_offset
        or span.end != chunk.end_offset
        or unit.unit_id
        != unit_from_legacy_chunk(
            chunk, substrate_id=substrate_id, meta=unit.meta
        ).unit_id
    ):
        raise _CitationFailure(
            _CitationFailureKind.REFERENCE_MISMATCH,
            "legacy unit is not the deterministic chunk mapping",
        )
    if (
        sha256(text[chunk.start_offset : chunk.end_offset].encode("utf-8")).hexdigest()
        != chunk.checksum_sha256
    ):
        raise _CitationFailure(
            _CitationFailureKind.MISMATCHED_CHECKSUM,
            "legacy chunk bytes do not match its checksum",
        )
    if (
        citation.start_offset < chunk.start_offset
        or citation.end_offset > chunk.end_offset
        or citation.start_offset < span.start
        or citation.end_offset > span.end
        or citation.end_offset > len(text)
    ):
        raise _CitationFailure(
            _CitationFailureKind.OUT_OF_UNIT, "legacy citation span is outside its binding"
        )
    quoted = text[citation.start_offset : citation.end_offset]
    if citation.quoted_snippet is not None and citation.quoted_snippet != quoted:
        raise _CitationFailure(
            _CitationFailureKind.MISMATCHED_CHECKSUM,
            "legacy citation snippet does not match canonical bytes",
        )
    return TextCitationV2(
        citation.source_id,
        citation.revision_id,
        unit.unit_id,
        substrate_id,
        citation.start_offset,
        citation.end_offset,
        sha256(quoted.encode("utf-8")).hexdigest(),
        citation.locator,
    )


def upgrade_legacy_citation(
    citation: _LegacyCitation,
    *,
    bindings: LegacyCitationBindingPort,
    correlation_id: CorrelationId | None = None,
) -> TextCitationV2:
    """Upgrade v0.1 citations only through an exact replay-derived binding."""

    return _invoke(
        lambda: _upgrade_legacy_impl(citation, bindings),
        correlation_id=correlation_id,
    )


__all__ = (
    "FIGURE_CITATION_VERSION",
    "TEXT_CITATION_VERSION",
    "BlobRef",
    "Citation",
    "DerivedRef",
    "FigureCitationV1",
    "LegacyCitationBinding",
    "LegacyCitationBindingPort",
    "SourceRevision",
    "SourceRevisionRef",
    "SubstrateRef",
    "TextCitationV2",
    "citation_from_bytes",
    "citation_from_json",
    "text_citation_for",
    "upgrade_legacy_citation",
    "verify_figure_citation",
    "verify_text_citation",
)
