from __future__ import annotations

from hashlib import sha256

import pytest

from study_agent.domain import (
    ChunkId,
    FigureBlob,
    LinkKind,
    RetrievableUnit,
    ReviewStatus,
    RevisionId,
    SourceChunk,
    SourceId,
    SubstrateId,
    TextSpan,
    UnitId,
    UnitKind,
    UnitLink,
    UnitMeta,
    UnitSignal,
    unit_id_for,
)
from study_agent.domain._validation import JsonObject
from study_agent.knowledge.units import (
    UNITIZER_VERSION,
    RevisionBinding,
    admit,
    decode_unit,
    derive_unit_id,
    reduce_units,
    unit_from_legacy_chunk,
)

SOURCE = SourceId("dispensa")
REVISION = RevisionId("revision-sha256:" + "a" * 64)
SUBSTRATE = SubstrateId("substrate:sha256:" + "b" * 64)
META = UnitMeta("lecture-notes", "primary", 80)
BINDINGS = {str(REVISION): RevisionBinding(SOURCE, SUBSTRATE, 4000)}


def span(start: int = 0, end: int = 40) -> TextSpan:
    return TextSpan(SUBSTRATE, start, end)


def unit(
    kind: UnitKind = UnitKind.PASSAGE,
    granularity: int = 3,
    path: tuple[str, ...] = ("doc", "sez"),
    ref: TextSpan | FigureBlob | None = None,
    meta: UnitMeta = META,
    links: tuple[UnitLink, ...] = (),
) -> RetrievableUnit:
    reference = ref if ref is not None else span()
    return RetrievableUnit(
        unit_id_for(
            revision_id=REVISION,
            structural_path=path,
            unit_kind=kind.value,
            granularity=granularity,
            canonical_ref=dict(reference.to_json()),
            unitizer_version=UNITIZER_VERSION,
        ),
        SOURCE,
        REVISION,
        kind,
        granularity,
        path,
        reference,
        meta,
        links,
    )


def project(
    state: JsonObject,
    units: list[RetrievableUnit],
    bindings: dict[str, RevisionBinding] | None = None,
) -> JsonObject:
    return dict(
        reduce_units(state, units, bindings=BINDINGS if bindings is None else bindings)
    )


def figure(checksum: str = "c" * 64) -> FigureBlob:
    return FigureBlob(checksum, 2048)


# --- one row shape --------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "granularity"),
    [
        (UnitKind.DOCUMENT_CARD, 0),
        (UnitKind.SECTION, 1),
        (UnitKind.SECTION, 2),
        (UnitKind.PASSAGE, 3),
        (UnitKind.DEFINITION, 4),
        (UnitKind.EMPHASIS, 4),
        (UnitKind.TABLE, 4),
        (UnitKind.EXAM_ITEM, 4),
    ],
)
def test_every_text_kind_uses_the_same_row_shape(kind: UnitKind, granularity: int) -> None:
    row = unit(kind, granularity).to_json()
    assert frozenset(row) == {
        "canonical_ref",
        "granularity",
        "links",
        "meta",
        "revision_id",
        "source_id",
        "structural_path",
        "unit_id",
        "unit_kind",
    }


def test_a_figure_uses_the_same_row_shape_as_text() -> None:
    text_row = unit().to_json()
    figure_row = unit(UnitKind.FIGURE, 4, ref=figure()).to_json()
    assert frozenset(text_row) == frozenset(figure_row)


@pytest.mark.parametrize(
    ("kind", "granularity"),
    [
        (UnitKind.DOCUMENT_CARD, 3),
        (UnitKind.SECTION, 0),
        (UnitKind.SECTION, 3),
        (UnitKind.PASSAGE, 4),
        (UnitKind.TABLE, 3),
        (UnitKind.FIGURE, 0),
    ],
)
def test_an_invalid_kind_granularity_pair_is_rejected(
    kind: UnitKind, granularity: int
) -> None:
    with pytest.raises(ValueError, match="granularity"):
        unit(kind, granularity, ref=figure() if kind is UnitKind.FIGURE else None)


# --- canonical references -------------------------------------------------


def test_text_units_reference_substrate_spans_and_never_carry_the_text() -> None:
    row = unit().to_json()
    assert row["canonical_ref"] == {
        "end": 40,
        "kind": "text_span",
        "start": 0,
        "substrate_id": str(SUBSTRATE),
    }
    assert "canonical_text" not in row
    assert "text" not in row


def test_figures_reference_the_image_blob_and_never_carry_the_bytes() -> None:
    row = unit(UnitKind.FIGURE, 4, ref=figure()).to_json()
    assert row["canonical_ref"] == {
        "byte_length": 2048,
        "checksum_sha256": "c" * 64,
        "kind": "figure_blob",
    }


def test_a_text_kind_cannot_reference_a_blob_and_a_figure_cannot_reference_a_span() -> None:
    with pytest.raises(TypeError, match="substrate span"):
        unit(UnitKind.PASSAGE, 3, ref=figure())
    with pytest.raises(TypeError, match="image blob"):
        unit(UnitKind.FIGURE, 4, ref=span())


def test_a_backward_or_empty_span_is_rejected() -> None:
    for start, end in ((5, 5), (9, 2), (-1, 4)):
        with pytest.raises(ValueError):
            TextSpan(SUBSTRATE, start, end)


# --- links ----------------------------------------------------------------


def test_links_accept_a_known_unit_or_an_explicit_provisional_target() -> None:
    known = UnitLink(LinkKind.PARENT, unit(UnitKind.SECTION, 2, ("doc",)).unit_id)
    provisional = UnitLink(LinkKind.REFERENCES, None, "figura-3-non-ancora-indicizzata")
    row = unit(links=(known, provisional))
    assert len(row.links) == 2
    assert provisional.is_provisional


def test_a_link_must_declare_exactly_one_target() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        UnitLink(LinkKind.PARENT, None, None)
    with pytest.raises(ValueError, match="exactly one"):
        UnitLink(LinkKind.PARENT, unit().unit_id, "anche-provvisorio")


def test_a_unit_cannot_link_to_itself() -> None:
    target = unit()
    with pytest.raises(ValueError, match="link to itself"):
        RetrievableUnit(
            target.unit_id,
            SOURCE,
            REVISION,
            UnitKind.PASSAGE,
            3,
            ("doc", "sez"),
            span(),
            META,
            (UnitLink(LinkKind.DERIVED_FROM, target.unit_id),),
        )


def test_links_are_bounded_deduplicated_and_single_parent() -> None:
    parent = unit(UnitKind.SECTION, 2, ("doc",)).unit_id
    other = unit(UnitKind.SECTION, 1, ("altro",)).unit_id
    with pytest.raises(ValueError, match="at most one parent"):
        unit(links=(UnitLink(LinkKind.PARENT, parent), UnitLink(LinkKind.PARENT, other)))
    with pytest.raises(ValueError, match="unique"):
        unit(links=(UnitLink(LinkKind.REFERENCES, parent),) * 2)
    with pytest.raises(ValueError, match="at most"):
        unit(links=tuple(UnitLink(LinkKind.REFERENCES, None, f"p{i}") for i in range(65)))


# --- identity -------------------------------------------------------------


def test_identity_commits_to_placement_kind_granularity_and_unitizer() -> None:
    base = unit()
    assert base.unit_id == derive_unit_id(base)
    assert unit(path=("doc", "altra")).unit_id != base.unit_id
    assert unit(ref=span(10, 40)).unit_id != base.unit_id
    assert unit(UnitKind.DEFINITION, 4).unit_id != base.unit_id


def test_duplicate_passages_at_different_placements_stay_distinct() -> None:
    first = unit(path=("doc", "a"), ref=span(0, 40))
    second = unit(path=("doc", "b"), ref=span(40, 80))
    assert first.unit_id != second.unit_id


def test_a_forged_identity_is_rejected_before_projection() -> None:
    good = unit()
    forged = RetrievableUnit(
        UnitId("unit:sha256:" + "0" * 64),
        good.source_id,
        good.revision_id,
        good.unit_kind,
        good.granularity,
        good.structural_path,
        good.canonical_ref,
        good.meta,
    )
    with pytest.raises(ValueError, match="does not match its immutable placement"):
        admit(forged)


def test_changing_the_unitizer_version_changes_identity() -> None:
    other = unit_id_for(
        revision_id=REVISION,
        structural_path=("doc", "sez"),
        unit_kind=UnitKind.PASSAGE.value,
        granularity=3,
        canonical_ref=dict(span().to_json()),
        unitizer_version="unitizer-v2",
    )
    assert other != unit().unit_id


# --- projection and replay ------------------------------------------------


def test_projection_is_idempotent_and_indexes_by_revision() -> None:
    rows = [unit(), unit(UnitKind.SECTION, 2, ("doc",))]
    once = project({}, rows)
    twice = project(once, rows)
    assert once == twice
    units = once["units"]
    assert isinstance(units, dict) and len(units) == 2
    index = once["units_by_revision"]
    assert isinstance(index, dict)
    assert len(index[str(REVISION)]) == 2


def test_meta_survives_replay_unchanged() -> None:
    meta = UnitMeta(
        "lecture-notes",
        "primary",
        70,
        ReviewStatus.REVIEWED,
        frozenset({"[VERIFICARE]"}),
        4,
        12,
        "it",
    )
    row = unit(meta=meta).to_json()
    assert row["meta"] == {
        "flags": ("[VERIFICARE]",),
        "language": "it",
        "ordinal": 4,
        "page_hint": 12,
        "review_status": "reviewed",
        "role": "primary",
        "source_class": "lecture-notes",
        "trust_level": 70,
    }
    assert decode_unit(row).meta == meta


def test_a_conflicting_row_for_the_same_identity_is_rejected() -> None:
    original = unit()
    state = project({}, [original])
    tampered: JsonObject = {
        **state,
        "units": {
            str(original.unit_id): {
                **original.to_json(),
                "meta": {**original.meta.to_json(), "trust_level": 100},
            }
        },
    }
    with pytest.raises(ValueError, match="different immutable metadata"):
        project(tampered, [original])


# --- hostile payloads -----------------------------------------------------


def test_the_codec_round_trips_every_kind() -> None:
    for candidate in (unit(), unit(UnitKind.FIGURE, 4, ref=figure()), unit(UnitKind.SECTION, 2)):
        assert decode_unit(candidate.to_json()) == candidate


@pytest.mark.parametrize(
    "mutate",
    [
        lambda row: {**row, "extra": 1},
        lambda row: {k: v for k, v in row.items() if k != "meta"},
        lambda row: {**row, "unit_kind": "sconosciuto"},
        lambda row: {**row, "granularity": "3"},
        lambda row: {**row, "structural_path": "doc"},
        lambda row: {**row, "canonical_ref": {"kind": "vector", "id": "x"}},
        lambda row: {**row, "links": [{"kind": "parent"}]},
        lambda row: {**row, "unit_id": "unit:sha256:" + "0" * 64},
    ],
)
def test_hostile_payloads_fail_closed(mutate: object) -> None:
    row = unit().to_json()
    with pytest.raises((ValueError, TypeError)):
        decode_unit(mutate(row))  # type: ignore[operator]


def test_an_index_snippet_cannot_be_smuggled_into_a_unit_row() -> None:
    row = {**unit().to_json(), "canonical_text": "testo falsificato"}
    with pytest.raises(ValueError, match="fields mismatch"):
        decode_unit(row)


# --- v0.1 migration seam --------------------------------------------------


def test_a_v01_chunk_maps_onto_exactly_one_passage_unit() -> None:
    chunk = SourceChunk(
        ChunkId(f"chunk-sha256:{sha256(b'x').hexdigest()}"),
        SOURCE,
        REVISION,
        0,
        1200,
        ("Dispensa", "Sezione"),
        0,
        sha256(b"x").hexdigest(),
        "heading-paragraph-v1",
    )
    migrated = unit_from_legacy_chunk(chunk, substrate_id=SUBSTRATE, meta=META)
    assert migrated.unit_kind is UnitKind.PASSAGE
    assert migrated.granularity == 3
    assert migrated.canonical_ref == TextSpan(SUBSTRATE, 0, 1200)
    assert migrated.structural_path == ("Dispensa", "Sezione")
    assert admit(migrated) is migrated


def test_signals_are_separate_from_the_unit_row() -> None:
    signal = UnitSignal("high_idf_terms", 3.0)
    assert signal.to_json() == {"name": "high_idf_terms", "value": 3.0}
    assert "signal" not in unit().to_json()
    with pytest.raises(ValueError):
        UnitSignal("bad", float("inf"))


# --- link integrity and revision coherence --------------------------------


def test_a_link_to_an_unknown_unit_is_rejected_by_the_projection() -> None:
    orphan = UnitId("unit:sha256:" + "e" * 64)
    child = unit(links=(UnitLink(LinkKind.PARENT, orphan),))
    with pytest.raises(ValueError, match="known unit"):
        project({}, [child])


def test_a_link_resolves_against_a_unit_admitted_in_the_same_batch() -> None:
    parent = unit(UnitKind.SECTION, 2, ("doc",))
    child = unit(links=(UnitLink(LinkKind.PARENT, parent.unit_id),))
    state = project({}, [parent, child])
    assert len(state["units"]) == 2  # type: ignore[arg-type]


def test_a_link_resolves_against_a_unit_already_in_the_projection() -> None:
    parent = unit(UnitKind.SECTION, 2, ("doc",))
    state = project({}, [parent])
    child = unit(links=(UnitLink(LinkKind.PARENT, parent.unit_id),))
    assert len(project(state, [child])["units"]) == 2  # type: ignore[arg-type]


def test_a_provisional_target_needs_no_known_unit() -> None:
    child = unit(links=(UnitLink(LinkKind.REFERENCES, None, "figura-non-ancora-estratta"),))
    assert len(project({}, [child])["units"]) == 1  # type: ignore[arg-type]


def test_a_parent_cycle_across_two_units_is_rejected() -> None:
    a = unit(UnitKind.SECTION, 2, ("doc",))
    b = unit(UnitKind.SECTION, 1, ("altro",))
    linked_a = unit(
        UnitKind.SECTION, 2, ("doc",), links=(UnitLink(LinkKind.PARENT, b.unit_id),)
    )
    linked_b = unit(
        UnitKind.SECTION, 1, ("altro",), links=(UnitLink(LinkKind.PARENT, a.unit_id),)
    )
    with pytest.raises(ValueError, match="cycle"):
        project({}, [linked_a, linked_b])


def test_a_batch_is_rejected_whole_and_never_half_applied() -> None:
    good = unit(UnitKind.SECTION, 2, ("doc",))
    bad = unit(links=(UnitLink(LinkKind.PARENT, UnitId("unit:sha256:" + "f" * 64)),))
    with pytest.raises(ValueError):
        project({}, [good, bad])
    assert project({}, [good])["units"] != {}


def test_a_revision_cannot_belong_to_two_sources() -> None:
    first = unit()
    second = RetrievableUnit(
        unit(path=("doc", "b"), ref=span(40, 80)).unit_id,
        SourceId("altra-dispensa"),
        REVISION,
        UnitKind.PASSAGE,
        3,
        ("doc", "b"),
        span(40, 80),
        META,
    )
    # admit() passes: unit_id deliberately excludes source_id, so only the
    # projection owner's revision-coherence check can catch this.
    assert admit(second) is second
    with pytest.raises(ValueError, match="does not own its revision"):
        project({}, [first, second])


def test_a_revision_cannot_bind_two_text_substrates() -> None:
    other = TextSpan(SubstrateId("substrate:sha256:" + "d" * 64), 0, 40)
    with pytest.raises(ValueError, match="not bound to its revision"):
        project({}, [unit(), unit(path=("doc", "b"), ref=other)])


def test_a_figure_unit_does_not_constrain_the_revision_substrate() -> None:
    state = project({}, [unit(), unit(UnitKind.FIGURE, 4, ("doc", "f"), figure())])
    assert len(state["units"]) == 2  # type: ignore[arg-type]


def test_a_unit_naming_an_uningested_revision_is_rejected() -> None:
    with pytest.raises(ValueError, match="not ingested"):
        project({}, [unit()], bindings={})


def test_a_span_beyond_the_real_substrate_length_is_rejected() -> None:
    short = {str(REVISION): RevisionBinding(SOURCE, SUBSTRATE, 20)}
    with pytest.raises(ValueError, match="exceeds the substrate character length"):
        project({}, [unit()], bindings=short)


def test_free_text_unit_fields_cannot_carry_a_paragraph_of_canonical_text() -> None:
    smuggled = "x" * 5000
    with pytest.raises(ValueError, match="at most"):
        UnitLink(LinkKind.REFERENCES, None, smuggled)
    with pytest.raises(ValueError, match="at most"):
        UnitMeta("lecture-notes", "primary", 80, flags=frozenset({smuggled}))
    with pytest.raises(ValueError, match="at most"):
        UnitMeta(smuggled, "primary", 80)
