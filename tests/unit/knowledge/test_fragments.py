from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from study_agent.domain.fragments import FragmentDraft, FragmentKind
from study_agent.domain.identifiers import RevisionId, SourceId, substrate_id_for
from study_agent.domain.tree import DialectProfile, DocumentTree, HeadingSyntax
from study_agent.domain.units import TextSpan, UnitKind, UnitMeta
from study_agent.knowledge.fragments import (
    FragmentPromotionPolicy,
    draft_fragments,
    materialize_promoted_fragments,
    promoted_unit_drafts,
)
from study_agent.knowledge.tree import AdmittedDocumentTree, admit_tree, build_document_tree
from study_agent.knowledge.unitizer import UnitizerPolicy
from study_agent.knowledge.units import RevisionBinding, derive_unit_id

SOURCE = SourceId("lecture")
REVISION = RevisionId("revision-1")
PROFILE = DialectProfile(
    "markdown",
    "v1",
    heading_syntax=HeadingSyntax.ATX,
    emphasis_markers=("> [!warning]",),
    summary_markers=("Summary:",),
    definition_markers=("Definition:",),
    pipe_tables=True,
    list_items=True,
    uncertainty_markers=("uncertain",),
)


def make_context() -> tuple[str, AdmittedDocumentTree, tuple[FragmentDraft, ...]]:
    text = (
        "# Heart\n\n"
        "> [!warning] uncertain pressure threshold\n"
        "Summary: preload lowers afterload\n"
        "Definition: preload is end-diastolic stretch\n"
        "| pressure | flow |\n| --- | --- |\n"
        "- item one\n"
    )
    substrate = substrate_id_for(text.encode())
    tree = build_document_tree(text, PROFILE, substrate_id=substrate)
    admitted = admit_tree(tree, text, PROFILE)
    fragments = draft_fragments(
        admitted,
        source_id=SOURCE,
        revision_id=REVISION,
    )
    return text, admitted, fragments


def test_drafts_preserve_exact_binding_span_and_inherited_flags() -> None:
    text, context, fragments = make_context()
    tree = context.tree
    assert {fragment.kind for fragment in fragments} == set(FragmentKind)
    by_kind = {fragment.kind: fragment for fragment in fragments}
    for _kind, fragment in by_kind.items():
        node = tree.node(fragment.node_id)
        assert fragment.substrate_id == tree.substrate_id
        assert fragment.span == node.span
        assert fragment.structural_path == node.path
        assert fragment.parent_node_id == node.parent_id
        assert fragment.flags.issuperset(node.flags)
        assert text[fragment.span[0] : fragment.span[1]]
    assert "uncertain" in by_kind[FragmentKind.EMPHASIS].flags


@pytest.mark.parametrize(
    ("kind", "scores", "corpus", "reference", "expected"),
    [
        (FragmentKind.EMPHASIS, (0.1,), (0.1, 0.2, 0.3), False, True),
        (FragmentKind.SUMMARY, (), (), False, False),
        (FragmentKind.TABLE, (0.0,), (0.1, 0.2), False, False),
        (FragmentKind.ITEM, (0.2,), (0.1, 0.2), True, True),
    ],
)
def test_signals_are_independent_and_combined(
    kind: FragmentKind,
    scores: tuple[float, ...],
    corpus: tuple[float, ...],
    reference: bool,
    expected: bool,
) -> None:
    _, _, fragments = make_context()
    fragment = next(candidate for candidate in fragments if candidate.kind is kind)
    policy = FragmentPromotionPolicy(minimum_length=1, threshold=0.5)
    decision = policy.decide(
        fragment,
        idf_scores=scores,
        corpus_idf_scores=corpus,
        reference_signal=reference,
    )
    assert decision.promoted is expected
    assert len(decision.contributions) == 4
    assert decision.total_score == sum(entry.contribution for entry in decision.contributions)


def test_exact_threshold_tie_promotes_and_replay_is_byte_identical() -> None:
    _, _, fragments = make_context()
    policy = FragmentPromotionPolicy(
        minimum_length=1,
        length_weight=1.0,
        structural_weight=0.0,
        rarity_weight=0.0,
        reference_weight=0.0,
        threshold=1.0,
    )
    first = policy.decide(fragments[0])
    second = policy.decide(fragments[0])
    assert first.promoted
    assert first.to_json() == second.to_json()
    assert first.to_json()["total_score"] == 1.0


def test_policy_is_immutable_and_rejects_unbounded_values() -> None:
    with pytest.raises(ValueError, match="minimum_length"):
        FragmentPromotionPolicy(minimum_length=0)
    with pytest.raises(ValueError, match="finite"):
        FragmentPromotionPolicy(threshold=float("nan"))
    policy = FragmentPromotionPolicy()
    with pytest.raises(FrozenInstanceError):
        policy.minimum_length = 10  # type: ignore[misc]
    _, _, fragments = make_context()
    with pytest.raises(ValueError, match="too large"):
        policy.decide(fragments[0], corpus_idf_scores=(0.1,) * 4097)


def test_non_promoted_fragments_have_no_child_draft_and_parent_remains_accessible() -> None:
    _, context, fragments = make_context()
    tree = context.tree
    policy = FragmentPromotionPolicy(threshold=1.0, minimum_length=32_768)
    decisions = tuple(policy.decide(fragment) for fragment in fragments)
    assert not any(decision.promoted for decision in decisions)
    assert promoted_unit_drafts(decisions) == ()
    assert all(fragment.parent_node_id is not None for fragment in fragments)
    assert tree.root.span[0] == 0


def test_materialization_uses_kb06_identity_owner_and_custom_version() -> None:
    text, context, fragments = make_context()
    policy = FragmentPromotionPolicy(minimum_length=1, threshold=0.0)
    decisions = tuple(policy.decide(fragment) for fragment in fragments)
    unitizer = UnitizerPolicy(version="unitizer-v2")
    substrate = substrate_id_for(text.encode())
    binding = RevisionBinding(SOURCE, substrate, len(text))
    units = materialize_promoted_fragments(
        context,
        decisions,
        revision_id=REVISION,
        binding=binding,
        policy=unitizer,
        meta=UnitMeta("notes", "primary", 10),
    )
    fragment_units = [
        unit
        for unit in units
        if unit.unit_kind
        in {
            UnitKind.EMPHASIS,
            UnitKind.SUMMARY,
            UnitKind.DEFINITION,
            UnitKind.TABLE,
            UnitKind.ITEM,
        }
    ]
    assert len(fragment_units) == len(fragments)
    for unit in fragment_units:
        assert isinstance(unit.canonical_ref, TextSpan)
        assert unit.canonical_ref.substrate_id == substrate
    assert len({unit.unit_id for unit in fragment_units}) == len(fragment_units)
    assert all(
        "uncertain" in unit.meta.flags
        for unit in fragment_units
        if unit.unit_kind is UnitKind.EMPHASIS
    )
    assert all(
        unit.unit_id == derive_unit_id(unit, unitizer_version="unitizer-v2")
        for unit in fragment_units
    )


def test_plain_tree_context_fails_closed() -> None:
    _, context, _ = make_context()
    plain_tree: DocumentTree = context.tree
    with pytest.raises(TypeError, match="admitted"):
        draft_fragments(
            plain_tree,  # type: ignore[arg-type]
            source_id=SOURCE,
            revision_id=REVISION,
        )


def test_materialization_rejects_fragment_from_another_revision() -> None:
    text, context, fragments = make_context()
    policy = FragmentPromotionPolicy(minimum_length=1, threshold=0.0)
    decisions = tuple(policy.decide(fragment) for fragment in fragments)
    binding = RevisionBinding(SOURCE, substrate_id_for(text.encode()), len(text))
    with pytest.raises(ValueError, match="canonical revision binding"):
        materialize_promoted_fragments(
            context,
            tuple(
                replace(
                    decision,
                    fragment=replace(decision.fragment, revision_id=RevisionId("other")),
                )
                for decision in decisions
            ),
            revision_id=REVISION,
            binding=binding,
            policy=UnitizerPolicy(),
        )


def test_duplicate_promoted_occurrences_are_rejected() -> None:
    _, _, fragments = make_context()
    policy = FragmentPromotionPolicy(minimum_length=1, threshold=0.0)
    decision = policy.decide(fragments[0])
    with pytest.raises(ValueError, match="repeat"):
        promoted_unit_drafts((decision, decision))


def test_model_provider_import_firewall_and_no_duplicate_identity_scheme() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).parents[3] / "src" / "study_agent"
    for path in (root / "domain" / "fragments.py", root / "knowledge" / "fragments.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not any(
            value.startswith(
                ("study_agent.adapters", "study_agent.models", "study_agent.providers")
            )
            or value in {"openai", "anthropic", "deepseek", "httpx", "requests"}
            for value in imports
        )
    source = (root / "knowledge" / "fragments.py").read_text(encoding="utf-8")
    assert "unit_id_for" not in source
    assert "sha256" not in source
