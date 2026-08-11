from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256

import pytest

from study_agent.api.sources import (
    DerivedRef,
    FigureCitationV1,
    TextCitationV2,
)
from study_agent.domain import Citation as LegacyCitation
from study_agent.domain import (
    RetrievableUnit,
    RevisionId,
    SelectionStatus,
    SourceId,
    TextSpan,
    UnitKind,
    UnitMeta,
    substrate_id_for,
    unit_id_for,
)
from study_agent.domain.citation_v2 import (
    CitationFailure,
    CitationFailureKind,
    citation_from_bytes,
    citation_from_json,
)
from study_agent.domain.identifiers import ChunkId
from study_agent.domain.lineage import RevisionRef
from study_agent.knowledge.citation import (
    text_citation_for,
    verify_figure_citation,
    verify_text_citation,
)
from study_agent.knowledge.units import UNITIZER_VERSION

TEXT = "La cuffia dei rotatori comprende quattro muscoli distinti.\n"
BYTES = TEXT.encode("utf-8")
SUBSTRATE = substrate_id_for(BYTES)
SOURCE = SourceId("dispensa")
REVISION = RevisionId("revision-sha256:" + "a" * 64)
META = UnitMeta("lecture-notes", "primary", 80)
CURRENT = SelectionStatus.CURRENT


def unit(start: int = 0, end: int = len(TEXT), path: tuple[str, ...] = ("doc",)) -> RetrievableUnit:
    span = TextSpan(SUBSTRATE, start, end)
    return RetrievableUnit(
        unit_id_for(
            revision_id=REVISION,
            structural_path=path,
            unit_kind=UnitKind.PASSAGE.value,
            granularity=3,
            canonical_ref=dict(span.to_json()),
            unitizer_version=UNITIZER_VERSION,
        ),
        SOURCE,
        REVISION,
        UnitKind.PASSAGE,
        3,
        path,
        span,
        META,
    )


def cite(start: int = 3, end: int = 20) -> TextCitationV2:
    return text_citation_for(unit(), substrate_bytes=BYTES, start=start, end=end)


def kind_of(error: pytest.ExceptionInfo[CitationFailure]) -> CitationFailureKind:
    return error.value.kind


# --- text verification ----------------------------------------------------


def test_a_valid_citation_resolves_to_the_exact_canonical_text() -> None:
    citation = cite()
    resolved = verify_text_citation(
        citation,
        substrate_bytes=BYTES,
        unit=unit(),
        selection_status=CURRENT,
    )
    assert resolved.text == TEXT[3:20]
    assert resolved.is_current
    assert resolved.successor is None


def test_verification_checks_the_substrate_hash() -> None:
    citation = cite()
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(
            citation,
            substrate_bytes=b"altro testo",
            unit=unit(),
            selection_status=CURRENT,
        )
    assert kind_of(error) is CitationFailureKind.CORRUPT


def test_verification_checks_the_quoted_checksum() -> None:
    good = cite()
    tampered = TextCitationV2(
        good.source_id,
        good.revision_id,
        good.unit_id,
        good.substrate_id,
        good.start,
        good.end,
        sha256(b"testo inventato").hexdigest(),
    )
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(tampered, substrate_bytes=BYTES, unit=unit(), selection_status=CURRENT)
    assert kind_of(error) is CitationFailureKind.MISMATCHED_CHECKSUM


def test_a_span_escaping_its_unit_is_rejected() -> None:
    narrow = unit(0, 10)
    citation = TextCitationV2(
        SOURCE, REVISION, narrow.unit_id, SUBSTRATE, 0, 30,
        sha256(TEXT[0:30].encode()).hexdigest(),
    )
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(citation, substrate_bytes=BYTES, unit=narrow, selection_status=CURRENT)
    assert kind_of(error) is CitationFailureKind.OUT_OF_UNIT


def test_a_span_beyond_the_substrate_is_rejected() -> None:
    wide = unit(0, len(TEXT))
    citation = TextCitationV2(
        SOURCE, REVISION, wide.unit_id, SUBSTRATE, 0, len(TEXT),
        sha256(TEXT.encode()).hexdigest(),
    )
    shorter = b"corto\n"
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(citation, substrate_bytes=shorter, unit=wide, selection_status=CURRENT)
    assert kind_of(error) is CitationFailureKind.CORRUPT


@pytest.mark.parametrize("field", ["unit", "source", "revision"])
def test_a_cross_reference_mismatch_fails_closed(field: str) -> None:
    citation = cite()
    other = unit(path=("altro",)) if field == "unit" else unit()
    if field == "source":
        other = RetrievableUnit(
            other.unit_id, SourceId("altra"), REVISION, other.unit_kind,
            other.granularity, other.structural_path, other.canonical_ref, META,
        )
    if field == "revision":
        other = RetrievableUnit(
            other.unit_id, SOURCE, RevisionId("revision-sha256:" + "b" * 64),
            other.unit_kind, other.granularity, other.structural_path,
            other.canonical_ref, META,
        )
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(citation, substrate_bytes=BYTES, unit=other, selection_status=CURRENT)
    assert kind_of(error) is CitationFailureKind.REFERENCE_MISMATCH


def test_missing_substrate_bytes_fail_closed() -> None:
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(cite(), substrate_bytes=b"", unit=unit(), selection_status=CURRENT)
    assert kind_of(error) is CitationFailureKind.MISSING


# --- superseded revisions -------------------------------------------------


def test_an_inactive_citation_still_resolves_and_reports_its_successor() -> None:
    successor = RevisionRef(SourceId("edizione-2027"), RevisionId("revision-sha256:" + "c" * 64))
    resolved = verify_text_citation(
        cite(),
        substrate_bytes=BYTES,
        unit=unit(),
        selection_status=SelectionStatus.INACTIVE,
        successor=successor,
    )
    assert resolved.text == TEXT[3:20]
    assert not resolved.is_current
    assert resolved.is_superseded
    assert resolved.successor == successor


# --- figures --------------------------------------------------------------


def test_a_figure_citation_verifies_the_image_bytes() -> None:
    image = b"\x89PNG fake bytes"
    citation = FigureCitationV1(sha256(image).hexdigest(), len(image), page_hint=12)
    resolved = verify_figure_citation(citation, image_bytes=image, selection_status=CURRENT)
    assert resolved.text is None
    assert resolved.citation == citation


def test_a_figure_with_tampered_bytes_fails_closed() -> None:
    image = b"\x89PNG fake bytes"
    citation = FigureCitationV1(sha256(image).hexdigest(), len(image))
    with pytest.raises(CitationFailure) as error:
        verify_figure_citation(
            citation,
            image_bytes=b"\x89PNG altre bytes",
            selection_status=CURRENT,
        )
    assert kind_of(error) in {
        CitationFailureKind.MISMATCHED_CHECKSUM,
        CitationFailureKind.CORRUPT,
    }


def test_page_and_anchor_are_hints_and_do_not_change_figure_identity() -> None:
    image = b"\x89PNG fake bytes"
    digest = sha256(image).hexdigest()
    bare = FigureCitationV1(digest, len(image))
    hinted = FigureCitationV1(digest, len(image), anchor_unit_id=unit().unit_id, page_hint=7)
    assert bare.figure_sha256 == hinted.figure_sha256
    resolved = verify_figure_citation(hinted, image_bytes=image, selection_status=CURRENT)
    assert resolved.citation == hinted


# --- derived text is never evidence ---------------------------------------


def test_derived_text_is_labelled_and_names_its_subject() -> None:
    derived = DerivedRef("model-projector", "v1", "riassunto generato", cite())
    assert derived.is_canonical is False
    assert derived.to_json()["derived"] is True
    assert derived.to_json()["subject"] == cite().to_json()


def test_derived_text_cannot_be_created_without_a_canonical_subject() -> None:
    with pytest.raises(TypeError):
        DerivedRef("model", "v1", "testo", "non-una-citazione")  # type: ignore[arg-type]


def test_derived_text_is_rejected_by_the_verifier() -> None:
    derived = DerivedRef("model", "v1", "testo", cite())
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(derived, substrate_bytes=BYTES, unit=unit(), selection_status=CURRENT)
    assert kind_of(error) is CitationFailureKind.NOT_A_CITATION


def test_an_index_snippet_cannot_stand_in_for_canonical_bytes() -> None:
    # A caller that supplies index text instead of substrate bytes must fail,
    # never silently resolve against the snippet.
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(
            cite(), substrate_bytes=b"snippet dall'indice", unit=unit(),
        selection_status=CURRENT,
    )
    assert kind_of(error) is CitationFailureKind.CORRUPT


# --- minting --------------------------------------------------------------


def test_minting_derives_the_checksum_from_canonical_bytes() -> None:
    citation = text_citation_for(unit(), substrate_bytes=BYTES, start=0, end=6)
    assert citation.quoted_sha256 == sha256(TEXT[0:6].encode()).hexdigest()
    resolved = verify_text_citation(
        citation, substrate_bytes=BYTES, unit=unit(), selection_status=CURRENT
    )
    assert resolved.text == TEXT[0:6]


def test_minting_rejects_a_span_outside_the_substrate() -> None:
    with pytest.raises(CitationFailure) as error:
        text_citation_for(unit(), substrate_bytes=BYTES, start=0, end=9999)
    assert kind_of(error) is CitationFailureKind.MALFORMED_SPAN


def test_locator_and_page_are_hints_not_identity() -> None:
    plain = text_citation_for(unit(), substrate_bytes=BYTES, start=0, end=6)
    hinted = text_citation_for(
        unit(), substrate_bytes=BYTES, start=0, end=6, locator="p. 12", page_hint=12
    )
    assert plain.quoted_sha256 == hinted.quoted_sha256
    assert plain.start == hinted.start and plain.end == hinted.end


# --- v0.1 compatibility ---------------------------------------------------


def legacy(quoted: str | None) -> LegacyCitation:
    return LegacyCitation(
        SOURCE, REVISION, ChunkId("chunk-sha256:" + "d" * 64), 3, 20, "p. 1", quoted
    )


def test_the_v01_contract_itself_is_untouched() -> None:
    original = legacy(TEXT[3:20])
    assert original.chunk_id == ChunkId("chunk-sha256:" + "d" * 64)
    assert original.quoted_snippet == TEXT[3:20]


# --- hostile encodings and bounds -----------------------------------------


def test_invalid_utf8_substrate_bytes_fail_closed_with_a_typed_reason() -> None:
    with pytest.raises(CitationFailure) as error:
        verify_text_citation(
            cite(),
            substrate_bytes=b"\xff\xfe not utf-8",
            unit=unit(),
            selection_status=CURRENT,
        )
    assert kind_of(error) is CitationFailureKind.CORRUPT


def test_minting_from_invalid_utf8_fails_closed_with_a_typed_reason() -> None:
    with pytest.raises(CitationFailure) as error:
        text_citation_for(unit(), substrate_bytes=b"\xff\xfe", start=0, end=1)
    assert kind_of(error) is CitationFailureKind.CORRUPT


def test_selection_status_must_be_stated_explicitly() -> None:
    with pytest.raises(TypeError):
        verify_text_citation(cite(), substrate_bytes=BYTES, unit=unit())  # type: ignore[call-arg]


def test_a_locator_cannot_carry_a_paragraph() -> None:
    with pytest.raises(ValueError, match="at most"):
        TextCitationV2(
            SOURCE, REVISION, unit().unit_id, SUBSTRATE, 0, 6,
            sha256(TEXT[0:6].encode()).hexdigest(), "x" * 5000,
        )


# --- canonical citation bytes --------------------------------------------


def test_malformed_unicode_citation_bytes_fail_as_corrupt() -> None:
    malformed = cite().to_bytes().replace(b'"dispensa"', b'"\\ud800"')

    with pytest.raises(CitationFailure) as error:
        TextCitationV2.from_bytes(malformed)

    assert kind_of(error) is CitationFailureKind.CORRUPT


def test_noncanonical_citation_bytes_fail_as_corrupt() -> None:
    noncanonical = cite().to_bytes().replace(b",", b", ", 1)

    with pytest.raises(CitationFailure) as error:
        citation_from_bytes(noncanonical)

    assert kind_of(error) is CitationFailureKind.CORRUPT


def test_text_codec_maps_unknown_versions_to_a_typed_failure() -> None:
    payload = dict(cite().to_json())
    payload["version"] = 99

    with pytest.raises(CitationFailure) as json_error:
        TextCitationV2.from_json(payload)
    assert type(json_error.value) is CitationFailure
    assert kind_of(json_error) is CitationFailureKind.UNSUPPORTED_VERSION

    with pytest.raises(CitationFailure) as bytes_error:
        citation_from_bytes(cite().to_bytes().replace(b'"version":2', b'"version":99'))
    assert type(bytes_error.value) is CitationFailure
    assert kind_of(bytes_error) is CitationFailureKind.UNSUPPORTED_VERSION


def test_figure_codec_maps_unknown_versions_to_a_typed_failure() -> None:
    image = b"figure"
    figure = FigureCitationV1(sha256(image).hexdigest(), len(image))
    payload = dict(figure.to_json())
    payload["version"] = 99

    with pytest.raises(CitationFailure) as json_error:
        FigureCitationV1.from_json(payload)
    assert type(json_error.value) is CitationFailure
    assert kind_of(json_error) is CitationFailureKind.UNSUPPORTED_VERSION

    with pytest.raises(CitationFailure) as bytes_error:
        FigureCitationV1.from_bytes(figure.to_bytes().replace(b'"version":1', b'"version":99'))
    assert type(bytes_error.value) is CitationFailure
    assert kind_of(bytes_error) is CitationFailureKind.UNSUPPORTED_VERSION


def test_public_dispatch_maps_unknown_versions_to_a_typed_failure() -> None:
    payload = {"version": 99}

    with pytest.raises(CitationFailure) as error:
        citation_from_json(payload)

    assert type(error.value) is CitationFailure
    assert kind_of(error) is CitationFailureKind.UNSUPPORTED_VERSION


@pytest.mark.parametrize(
    "decoder",
    [
        TextCitationV2.from_bytes,
        FigureCitationV1.from_bytes,
        DerivedRef.from_bytes,
        citation_from_bytes,
    ],
)
def test_public_codecs_map_malformed_bytes_to_a_typed_failure(
    decoder: Callable[[bytes], object],
) -> None:
    with pytest.raises(CitationFailure) as error:
        decoder(b"not-json")

    assert type(error.value) is CitationFailure
    assert kind_of(error) is CitationFailureKind.CORRUPT
