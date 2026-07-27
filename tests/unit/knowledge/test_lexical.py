from __future__ import annotations

from dataclasses import replace

import pytest

from study_agent.domain import (
    DialectProfile,
    RetrievableUnit,
    RevisionId,
    SourceId,
    TextSpan,
    UnitKind,
    UnitMeta,
    unit_id_for,
)
from study_agent.domain.identifiers import substrate_id_for
from study_agent.knowledge.lexical import (
    DEFAULT_POLICY,
    LexicalCorpusItem,
    LexicalPolicy,
    LexicalProjector,
    project_lexical,
    tokenize,
)
from study_agent.knowledge.projections import project_structural
from study_agent.knowledge.tree import admit_tree, build_document_tree

SOURCE = SourceId("source")
REVISION = RevisionId("revision")
PROFILE = DialectProfile("markdown", "v1")
def _item(text: str, ordinal: int = 0) -> LexicalCorpusItem:
    substrate = substrate_id_for(text.encode("utf-8"))
    tree = build_document_tree(text, PROFILE, substrate_id=substrate)
    context = admit_tree(tree, text, PROFILE)
    end = len(text)
    unit = RetrievableUnit(
        unit_id_for(
            revision_id=REVISION,
            structural_path=(),
            unit_kind=UnitKind.PASSAGE.value,
            granularity=3,
            canonical_ref=TextSpan(substrate, 0, end).to_json(),
            unitizer_version="unitizer-v1",
        ),
        SOURCE,
        REVISION,
        UnitKind.PASSAGE,
        3,
        (),
        TextSpan(substrate, 0, end),
        UnitMeta("notes", "primary", 80, ordinal=ordinal),
    )
    return LexicalCorpusItem(unit, project_structural(unit, context), text, context)


def test_unicode_tokens_preserve_medical_distinctions_and_digits() -> None:
    assert tokenize("β₂-microglobulina IL-6 H₂O naïve") == (
        "β₂-microglobulina",
        "il-6",
        "h₂o",
        "naïve",
    )
    assert tokenize("OR AND \"NEAR\" ![[figura]]") == ("or", "and", "near", "figura")


def test_idf_order_is_stable_and_one_document_has_lexical_ties() -> None:
    first = _item("β₂-microglobulina IL-6 IL-6", 0)
    second = _item("β₂-microglobulina naïve", 1)
    projector = LexicalProjector((second, first), scope_id="exam", policy=DEFAULT_POLICY)
    projections = projector.project_all()
    assert [str(projection.unit_id) for projection in projections] == sorted(
        (str(first.unit.unit_id), str(second.unit.unit_id))
    )
    assert projections[0].key_terms
    assert project_lexical((first,), scope_id="one")[0].key_terms == (
        "il-6",
        "β₂-microglobulina",
    )


def test_aliases_are_literal_data_with_collision_and_empty_behavior() -> None:
    item = _item("Myocardial infarction OR thrombosis", 0)
    projection = LexicalProjector(
        (item,),
        scope_id="exam",
        aliases={"myocardial infarction": ("MI", "", '" OR 1=1')},
    ).project_all()[0]
    assert projection.aliases == ('" or 1=1', "mi")
    with pytest.raises(ValueError, match="collision"):
        LexicalProjector(
            (item,),
            scope_id="exam",
            aliases={"infarction": ("MI",), "thrombosis": ("mi",)},
        )


def test_empty_corpus_and_duplicate_unit_policy_are_explicit() -> None:
    assert LexicalProjector((), scope_id="empty").project_all() == ()
    item = _item("one", 0)
    projector = LexicalProjector((item, item), scope_id="dedupe")
    assert len(projector.entries) == 1
    with pytest.raises(ValueError, match="canonical_text"):
        replace(item, canonical_text="different")


def test_term_cap_stop_words_and_bounds_are_enforced() -> None:
    item = _item("a b c d e f g", 0)
    policy = LexicalPolicy(term_cap=3, stop_words=("a",))
    projection = LexicalProjector((item,), scope_id="cap", policy=policy).project_all()[0]
    assert projection.key_terms == ("b", "c", "d")
    with pytest.raises(ValueError, match="max_corpus_units"):
        LexicalProjector((item,), scope_id="cap", policy=replace(policy, max_corpus_units=0))
    with pytest.raises(ValueError, match="canonical_text"):
        LexicalCorpusItem(item.unit, item.structural_projection, "x\x00", item.admitted_tree)


def test_same_inputs_are_byte_identical_and_policy_changes_invalidate() -> None:
    item = _item("\N{GREEK SMALL LETTER ALPHA}-synuclein dopamine", 0)
    first = LexicalProjector((item,), scope_id="exam").project_all()[0]
    second = LexicalProjector((item,), scope_id="exam").project_all()[0]
    assert first.to_bytes() == second.to_bytes()
    changed = LexicalProjector(
        (item,), scope_id="exam", policy=replace(DEFAULT_POLICY, term_cap=1)
    ).project_all()[0]
    assert changed.input_fingerprint != first.input_fingerprint
    assert changed.projection_id != first.projection_id
    with pytest.raises(TypeError):
        projector = LexicalProjector((item,), scope_id="exam", aliases={"dopamine": ("DA",)})
        projector.aliases["dopamine"] = ("forged",)  # type: ignore[index]


def test_policy_codec_is_strict_and_canonical() -> None:
    encoded = DEFAULT_POLICY.to_bytes()
    assert LexicalPolicy.from_bytes(encoded) == DEFAULT_POLICY
    with pytest.raises(ValueError, match="canonical"):
        LexicalPolicy.from_bytes(encoded + b" ")
    with pytest.raises(ValueError, match="fields mismatch"):
        LexicalPolicy.from_json({**DEFAULT_POLICY.to_json(), "extra": True})


def test_forged_structural_projection_and_wrong_canonical_slice_are_rejected() -> None:
    item = _item("medical", 0)
    forged_handle = "forged"
    forged = replace(
        item.structural_projection,
        handle=forged_handle,
        output_sha256=item.structural_projection.derive_output_sha256(
            handle=forged_handle,
            summary=item.structural_projection.summary,
            key_terms=(),
            aliases=(),
            covers=(),
            structural_context=item.structural_projection.structural_context,
        ),
    )
    with pytest.raises(ValueError, match="re-derivation"):
        LexicalCorpusItem(item.unit, forged, item.canonical_text, item.admitted_tree)
    with pytest.raises(ValueError, match="canonical_text"):
        LexicalCorpusItem(item.unit, item.structural_projection, "not-the-span", item.admitted_tree)
