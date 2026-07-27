from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from typing import cast

import pytest

from study_agent.domain.citation_v2 import TextCitationV2
from study_agent.domain.identifiers import RevisionId, SourceId, substrate_id_for
from study_agent.domain.tree import DialectProfile, DocumentTree, HeadingSyntax, RegionKind
from study_agent.domain.units import RetrievableUnit, TextSpan, UnitKind
from study_agent.knowledge.tree import build_document_tree
from study_agent.knowledge.unitizer import (
    V01_WINDOW_CHARACTERS,
    RemapReport,
    UnitDraft,
    UnitizerPolicy,
    draft_units,
    remap_citations,
    unitize,
)
from study_agent.knowledge.units import RevisionBinding, decode_unit, reduce_units

SOURCE = SourceId("notes")
REVISION = RevisionId("revision-1")
PLAIN = DialectProfile("plain", "v1")
MARKDOWN = DialectProfile(
    "markdown",
    "v1",
    heading_syntax=HeadingSyntax.ATX,
    fenced_code=True,
    pipe_tables=True,
    emphasis_markers=("> [!warning]",),
)


def make_units(
    text: str,
    profile: DialectProfile = MARKDOWN,
    *,
    cap: int = 1200,
) -> tuple[DocumentTree, RevisionBinding, tuple[RetrievableUnit, ...]]:
    substrate = substrate_id_for(text.encode("utf-8"))
    tree = build_document_tree(text, profile, substrate_id=substrate)
    binding = RevisionBinding(SOURCE, substrate, len(text))
    units = unitize(
        text,
        tree,
        revision_id=REVISION,
        binding=binding,
        policy=UnitizerPolicy(max_characters=cap),
    )
    return tree, binding, units


def spans(units: tuple[object, ...], kind: UnitKind) -> list[tuple[int, int]]:
    return [
        (unit.canonical_ref.start, unit.canonical_ref.end)  # type: ignore[attr-defined]
        for unit in units
        if unit.unit_kind is kind  # type: ignore[attr-defined]
    ]


def span_for(unit: RetrievableUnit) -> TextSpan:
    return cast(TextSpan, unit.canonical_ref)


def test_small_section_emits_document_section_and_one_passage() -> None:
    text = "# Doc\n\nUna breve spiegazione.\n"
    _, binding, units = make_units(text)
    assert [unit.unit_kind for unit in units] == [
        UnitKind.DOCUMENT_CARD,
        UnitKind.SECTION,
        UnitKind.PASSAGE,
    ]
    assert spans(units, UnitKind.PASSAGE) == [(0, len(text))]
    assert reduce_units({}, units, bindings={str(REVISION): binding})["units"]


def test_exact_cap_keeps_a_section_as_one_passage() -> None:
    text = "# Doc\n\nabc\n"
    _, _, units = make_units(text, cap=len(text))
    assert spans(units, UnitKind.PASSAGE) == [(0, len(text))]


def test_structure_poor_input_preserves_exact_v01_windows() -> None:
    text = "x" * (V01_WINDOW_CHARACTERS * 2 + 17)
    _, _, units = make_units(text, PLAIN)
    assert spans(units, UnitKind.PASSAGE) == [
        (0, 1200),
        (1200, 2400),
        (2400, len(text)),
    ]


def test_large_section_splits_at_paragraph_boundaries() -> None:
    text = "# Doc\n\n" + "a" * 700 + "\n\n" + "b" * 700 + "\n"
    tree, _, units = make_units(text, cap=900)
    passage_spans = spans(units, UnitKind.PASSAGE)
    assert len(passage_spans) == 2
    assert all(text[start:end].strip() for start, end in passage_spans)
    assert all(
        start >= tree.nodes[1].start_offset and end <= tree.nodes[1].end_offset
        for start, end in passage_spans
    )
    assert text[passage_spans[0][1] - 2 : passage_spans[0][1]] == "\n\n"


def test_oversized_paragraph_is_kept_whole() -> None:
    text = "# Doc\n\n" + "a" * 1400 + "\n"
    _, _, units = make_units(text, cap=1200)
    assert (7, len(text)) in spans(units, UnitKind.PASSAGE)


def test_atomic_regions_are_never_split() -> None:
    code = "```\n" + "x" * 1500 + "\n```\n"
    text = "# Doc\n\n" + "a" * 800 + "\n\n" + code + "\n"
    tree, _, units = make_units(text, cap=900)
    code_node = next(node for node in tree.nodes if node.region_kind is RegionKind.CODE)
    passage_spans = spans(units, UnitKind.PASSAGE)
    assert (code_node.start_offset, code_node.end_offset) in passage_spans
    assert not any(
        start < code_node.start_offset < end < code_node.end_offset
        or code_node.start_offset < start < code_node.end_offset < end
        for start, end in passage_spans
    )


def test_atomic_region_without_headings_is_not_treated_as_plain_fallback() -> None:
    code = "```\n" + "x" * 1500 + "\n```\n"
    tree, _, units = make_units(code, MARKDOWN, cap=900)
    code_node = next(node for node in tree.nodes if node.region_kind is RegionKind.CODE)
    assert (code_node.start_offset, code_node.end_offset) in spans(units, UnitKind.PASSAGE)


def test_unicode_offsets_are_code_point_offsets_and_ids_are_deterministic() -> None:
    text = "# Caffè 🫀\n\n\u03b1\u03b2\u03b3 — testo\n"
    first = make_units(text)[2]
    second = make_units(text)[2]
    assert [unit.to_json() for unit in first] == [unit.to_json() for unit in second]
    assert all(
        0 <= span_for(unit).start < span_for(unit).end <= len(text)
        for unit in first
    )


def test_nested_sections_keep_their_granularity_and_parent_links() -> None:
    text = "# A\n\n## B\n\ntext\n"
    _, _, units = make_units(text)
    sections = [unit for unit in units if unit.unit_kind is UnitKind.SECTION]
    assert [unit.structural_path for unit in sections] == [("a",), ("a", "b")]
    assert sections[0].granularity == 1
    assert sections[1].granularity == 2
    assert sections[1].links[0].target == sections[0].unit_id


def test_empty_draft_spans_fail_closed() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        UnitDraft(UnitKind.PASSAGE, 3, ("document",), (4, 4))


def test_binding_rejects_text_from_a_different_substrate() -> None:
    text = "# Doc\n\ncanonical\n"
    tree, binding, _ = make_units(text)
    with pytest.raises(ValueError, match="does not match the bound substrate"):
        unitize(
            text.replace("canonical", "canon1cal"),
            tree,
            revision_id=REVISION,
            binding=binding,
        )


def test_policy_rejects_a_changed_structure_poor_fallback_cap() -> None:
    with pytest.raises(ValueError, match="frozen at 1,200"):
        UnitizerPolicy(fallback_window_characters=1000)


def test_versioned_unit_ids_and_complete_no_guess_remap_report() -> None:
    text = "# Doc\n\n" + ("a" * 700 + "\n\n") * 2
    tree, binding, old_units = make_units(text, cap=1000)
    new_units = unitize(
        text,
        tree,
        revision_id=REVISION,
        binding=binding,
        policy=UnitizerPolicy(version="unitizer-v2", max_characters=600),
    )
    old_passage = next(unit for unit in old_units if unit.unit_kind is UnitKind.PASSAGE)
    old_span = span_for(old_passage)
    assert old_passage.unit_id not in {unit.unit_id for unit in new_units}
    citation = TextCitationV2(
        SOURCE,
        REVISION,
        old_passage.unit_id,
        binding.substrate_id,
        old_span.start,
        old_span.end,
        sha256(
            text[old_span.start : old_span.end].encode()
        ).hexdigest(),
    )
    report = remap_citations(
        (citation,),
        old_units=old_units,
        new_units=new_units,
        old_version="unitizer-v1",
        new_version="unitizer-v2",
    )
    assert isinstance(report, RemapReport)
    assert len(report.entries) == 1
    assert report.unmatched[0].replacement is None
    assert report.unmatched[0].reason == "no exact replacement"


def test_explicit_unitizer_version_context_admits_and_decodes_matching_rows() -> None:
    text = "# Doc\n\nshort\n"
    tree, binding, _ = make_units(text)
    policy = UnitizerPolicy(version="unitizer-v2")
    units = unitize(text, tree, revision_id=REVISION, binding=binding, policy=policy)
    bindings = {str(REVISION): binding}
    with pytest.raises(ValueError, match="does not match"):
        reduce_units({}, units, bindings=bindings)
    with pytest.raises(ValueError, match="does not match"):
        reduce_units({}, units, bindings=bindings, unitizer_version="unitizer-v3")
    projected = reduce_units(
        {}, units, bindings=bindings, unitizer_version="unitizer-v2"
    )
    assert len(projected["units"]) == len(units)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="does not match"):
        decode_unit(units[0].to_json())
    assert decode_unit(
        units[0].to_json(), unitizer_version="unitizer-v2"
    ) == units[0]


def test_exact_remap_changes_only_the_unit_id() -> None:
    text = "# Doc\n\nshort\n"
    tree, binding, old_units = make_units(text)
    new_units = unitize(
        text,
        tree,
        revision_id=REVISION,
        binding=binding,
        policy=UnitizerPolicy(version="unitizer-v2"),
    )
    old_passage = next(unit for unit in old_units if unit.unit_kind is UnitKind.PASSAGE)
    citation = TextCitationV2(
        SOURCE,
        REVISION,
        old_passage.unit_id,
        binding.substrate_id,
        2,
        7,
        sha256(text[2:7].encode()).hexdigest(),
    )
    report = remap_citations(
        (citation,),
        old_units=old_units,
        new_units=new_units,
        old_version="unitizer-v1",
        new_version="unitizer-v2",
    )
    assert report.matched[0].replacement is not None
    assert report.matched[0].replacement.unit_id != citation.unit_id
    assert replace(report.matched[0].replacement, unit_id=citation.unit_id) == citation


def test_drafts_are_identity_free_and_tree_bounded() -> None:
    text = "# Doc\n\nparagraph\n"
    tree, _, _ = make_units(text)
    drafts = draft_units(text, tree)
    assert all(not hasattr(draft, "unit_id") for draft in drafts)
    assert all(0 <= start < end <= len(text) for draft in drafts for start, end in (draft.span,))
