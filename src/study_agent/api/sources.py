"""Curated, provider-neutral source and citation contracts.

The domain citation codec keeps its detailed failure reasons private.  This
facade translates those reasons into the closed PF-02 failure taxonomy and
never exposes the implementation exception or parser/adapter text.
"""

from __future__ import annotations

from collections.abc import Callable as _Callable
from typing import cast as _cast

import study_agent.domain.citation_v2 as _citation_domain
from study_agent.domain._validation import JsonObject as _JsonObject
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
from study_agent.domain.identifiers import CorrelationId as _CorrelationId
from study_agent.domain.source import (
    BlobRef,
    SourceRevision,
    SourceRevisionRef,
    SubstrateRef,
)

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
    error: _CitationFailure, *, correlation_id: _CorrelationId | None = None
) -> _ValidationFailure:
    reason = _CITATION_REASONS[error.kind]
    return _ValidationFailure(
        "citation failed validation",
        correlation_id=correlation_id,
        details={"reason_kind": reason},
    )


def _invoke[T](operation: _Callable[[], T], *, correlation_id: _CorrelationId | None = None) -> T:
    try:
        return operation()
    except _CitationFailure as error:
        raise _citation_failure_to_harness_error(error, correlation_id=correlation_id) from error
    except _HarnessError:
        raise
    except Exception as error:
        internal = _CitationFailure(_CitationFailureKind.CORRUPT, "citation operation failed")
        raise _citation_failure_to_harness_error(internal, correlation_id=correlation_id) from error


def citation_from_bytes(data: object, *, correlation_id: _CorrelationId | None = None) -> Citation:
    """Decode bounded canonical citation bytes through the public failure seam."""

    return _invoke(
        lambda: _citation_domain.citation_from_bytes(_cast(bytes, data)),
        correlation_id=correlation_id,
    )


def citation_from_json(value: object, *, correlation_id: _CorrelationId | None = None) -> Citation:
    """Decode bounded citation JSON through the public failure seam."""

    return _invoke(
        lambda: _citation_domain.citation_from_json(_cast(_JsonObject, value)),
        correlation_id=correlation_id,
    )


__all__ = (
    "FIGURE_CITATION_VERSION",
    "TEXT_CITATION_VERSION",
    "BlobRef",
    "Citation",
    "DerivedRef",
    "FigureCitationV1",
    "SourceRevision",
    "SourceRevisionRef",
    "SubstrateRef",
    "TextCitationV2",
    "citation_from_bytes",
    "citation_from_json",
)


def __dir__() -> list[str]:
    return sorted(__all__)
