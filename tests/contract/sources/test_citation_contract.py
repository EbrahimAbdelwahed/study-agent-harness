from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256

import pytest

from study_agent.api.sources import (
    FIGURE_CITATION_VERSION,
    TEXT_CITATION_VERSION,
    DerivedRef,
    FigureCitationV1,
    TextCitationV2,
    citation_from_bytes,
    citation_from_json,
)
from study_agent.domain import (
    RevisionId,
    RevisionRef,
    SelectionStatus,
    SourceId,
    SubstrateId,
    TextSpan,
)
from study_agent.domain.citation_v2 import CitationFailure, CitationFailureKind
from study_agent.domain.errors import ValidationFailure
from study_agent.knowledge.citation import text_citation_for, verify_text_citation
from study_agent.state import canonical_json_bytes
from tests.support.pf05 import BYTES, TEXT, make_text_citation, make_unit


def failure_kind(error: pytest.ExceptionInfo[CitationFailure]) -> CitationFailureKind:
    return error.value.kind


def test_versioned_citation_values_are_public_and_stable() -> None:
    citation = make_text_citation(start=1, end=12)
    figure_bytes = b"figure"
    figure = FigureCitationV1(sha256(figure_bytes).hexdigest(), len(figure_bytes))

    assert TEXT_CITATION_VERSION == 2
    assert FIGURE_CITATION_VERSION == 1
    assert citation.version == TEXT_CITATION_VERSION
    assert citation.to_json() == citation.to_json()
    assert TextCitationV2.from_bytes(citation.to_bytes()) == citation
    assert FigureCitationV1.from_bytes(figure.to_bytes()) == figure


def test_current_and_superseded_citations_resolve_without_rewriting_history() -> None:
    citation = make_text_citation(start=1, end=12)
    successor = RevisionRef(
        SourceId("source-pf05"), RevisionId("revision-sha256:" + "2" * 64)
    )

    current = verify_text_citation(
        citation,
        substrate_bytes=BYTES,
        unit=make_unit(),
        selection_status=SelectionStatus.CURRENT,
    )
    historical = verify_text_citation(
        citation,
        substrate_bytes=BYTES,
        unit=make_unit(),
        selection_status=SelectionStatus.INACTIVE,
        successor=successor,
    )

    assert current.text == TEXT[1:12]
    assert current.is_current
    assert not current.is_superseded
    assert historical.text == current.text
    assert not historical.is_current
    assert historical.is_superseded
    assert historical.successor == successor
    assert citation.to_json() == current.citation.to_json()


@pytest.mark.parametrize(
    ("tampered", "expected"),
    [
        (b"not the canonical substrate", CitationFailureKind.CORRUPT),
        (b"", CitationFailureKind.MISSING),
    ],
)
def test_citation_resolution_rejects_missing_or_corrupt_canonical_bytes(
    tampered: bytes, expected: CitationFailureKind
) -> None:
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(
            make_text_citation(),
            substrate_bytes=tampered,
            unit=make_unit(),
            selection_status=SelectionStatus.CURRENT,
        )

    assert failure_kind(error) is expected


def test_citation_resolution_rejects_quote_hash_and_out_of_unit_tampering() -> None:
    citation = make_text_citation(start=1, end=12)
    mismatched_quote = replace(
        citation, quoted_sha256=sha256(b"forged quote").hexdigest()
    )
    with pytest.raises(CitationFailure) as quote_error:
        verify_text_citation(
            mismatched_quote,
            substrate_bytes=BYTES,
            unit=make_unit(),
            selection_status=SelectionStatus.CURRENT,
        )
    assert failure_kind(quote_error) is CitationFailureKind.MISMATCHED_CHECKSUM

    narrow_unit = make_unit(start=0, end=8)
    escaping = TextCitationV2(
        citation.source_id,
        citation.revision_id,
        narrow_unit.unit_id,
        citation.substrate_id,
        1,
        12,
        sha256(TEXT[1:12].encode("utf-8")).hexdigest(),
    )
    with pytest.raises(CitationFailure) as bounds_error:
        verify_text_citation(
            escaping,
            substrate_bytes=BYTES,
            unit=narrow_unit,
            selection_status=SelectionStatus.CURRENT,
        )
    assert failure_kind(bounds_error) is CitationFailureKind.OUT_OF_UNIT


@pytest.mark.parametrize(
    "field",
    ["source_id", "revision_id", "unit_id"],
)
def test_citation_resolution_rejects_cross_reference_mismatches(field: str) -> None:
    citation = make_text_citation()
    if field == "source_id":
        tampered = replace(citation, source_id=SourceId("foreign-source"))
    elif field == "revision_id":
        tampered = replace(
            citation, revision_id=RevisionId("revision-sha256:" + "3" * 64)
        )
    else:
        tampered = replace(
            citation, unit_id=make_unit(start=1, end=len(TEXT)).unit_id
        )

    with pytest.raises(CitationFailure) as error:
        verify_text_citation(
            tampered,
            substrate_bytes=BYTES,
            unit=make_unit(),
            selection_status=SelectionStatus.CURRENT,
        )

    assert failure_kind(error) is CitationFailureKind.REFERENCE_MISMATCH


def test_citation_resolution_rejects_a_unit_bound_to_another_substrate() -> None:
    citation = make_text_citation()
    foreign_substrate = SubstrateId("substrate:sha256:" + "4" * 64)
    foreign_unit = replace(
        make_unit(),
        canonical_ref=TextSpan(foreign_substrate, 0, len(TEXT)),
    )

    with pytest.raises(CitationFailure) as error:
        verify_text_citation(
            citation,
            substrate_bytes=BYTES,
            unit=foreign_unit,
            selection_status=SelectionStatus.CURRENT,
        )

    assert failure_kind(error) is CitationFailureKind.REFERENCE_MISMATCH


def test_derived_text_preserves_lineage_but_is_not_primary_evidence() -> None:
    citation = make_text_citation(start=0, end=12)
    derived = DerivedRef("summary", "summary-v1", "model text", citation)

    assert not derived.is_canonical
    assert derived.to_json()["subject"] == citation.to_json()
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(
            derived,
            substrate_bytes=BYTES,
            unit=make_unit(),
            selection_status=SelectionStatus.CURRENT,
        )
    assert failure_kind(error) is CitationFailureKind.NOT_A_CITATION


def test_unsupported_versions_and_invalid_spans_fail_closed() -> None:
    image = b"figure"
    figure = FigureCitationV1(sha256(image).hexdigest(), len(image))
    with pytest.raises(CitationFailure) as version_error:
        verify_text_citation(
            figure,
            substrate_bytes=BYTES,
            unit=make_unit(),
            selection_status=SelectionStatus.CURRENT,
        )
    assert failure_kind(version_error) is CitationFailureKind.UNSUPPORTED_VERSION

    with pytest.raises(CitationFailure) as span_error:
        text_citation_for(
            make_unit(), substrate_bytes=BYTES, start=0, end=len(TEXT) + 1
        )
    assert failure_kind(span_error) is CitationFailureKind.MALFORMED_SPAN


def test_citation_and_derived_export_bytes_are_deterministic() -> None:
    citation = make_text_citation(start=2, end=22)
    derived = DerivedRef("summary", "summary-v1", "model text", citation)

    assert canonical_json_bytes(citation.to_json()) == canonical_json_bytes(
        citation.to_json()
    )
    assert canonical_json_bytes(derived.to_json()) == canonical_json_bytes(
        derived.to_json()
    )
    assert TextCitationV2.from_bytes(citation.to_bytes()) == citation
    assert DerivedRef.from_bytes(derived.to_bytes()) == derived


def test_public_citation_codecs_never_leak_raw_value_error_for_bad_versions() -> None:
    payload = dict(make_text_citation().to_json())
    payload["version"] = 99

    with pytest.raises(ValidationFailure) as json_error:
        citation_from_json(payload)
    assert type(json_error.value) is ValidationFailure
    assert json_error.value.message == "citation failed validation"
    assert isinstance(json_error.value.details, Mapping)
    assert json_error.value.details["reason_kind"] == "unsupported_version"

    malformed = b'{"version":2}'
    with pytest.raises(ValidationFailure) as bytes_error:
        citation_from_bytes(malformed)
    assert type(bytes_error.value) is ValidationFailure
    assert isinstance(bytes_error.value.details, Mapping)
    assert bytes_error.value.details["reason_kind"] == "corrupt"
