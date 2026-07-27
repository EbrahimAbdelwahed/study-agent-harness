from __future__ import annotations

import random
from itertools import pairwise

import pytest

from study_agent.domain.identifiers import NodeId, SubstrateId, node_id_for, substrate_id_for
from study_agent.domain.tree import (
    MALFORMED_FLAG,
    DialectProfile,
    DocumentTree,
    HeadingSyntax,
    RegionKind,
    TreeNode,
)
from study_agent.knowledge.tree import TREE_FORMAT_VERSION, build_document_tree

MARKDOWN = DialectProfile(
    "markdown-notes",
    "v1",
    heading_syntax=HeadingSyntax.ATX,
    fenced_code=True,
    pipe_tables=True,
    list_items=True,
    figure_reference_markers=("![[",),
    emphasis_markers=("> [!warning]",),
    summary_markers=("> [!summary]",),
    uncertainty_markers=("[VERIFICARE]", "[AUDIO INAUDIBILE]"),
)
PLAIN = DialectProfile("plain-text", "v1")


def substrate_of(text: str) -> SubstrateId:
    return substrate_id_for(text.encode("utf-8"))


def build(text: str, profile: DialectProfile = MARKDOWN) -> DocumentTree:
    return build_document_tree(text, profile, substrate_id=substrate_of(text))


def paths(tree: DocumentTree) -> list[tuple[str, ...]]:
    return [node.path for node in tree.nodes]


# --- structure ------------------------------------------------------------


def test_structure_poor_text_yields_one_valid_root_for_the_v01_window_fallback() -> None:
    text = "una riga di appunti\nsenza alcuna struttura\n"
    tree = build(text, PLAIN)
    assert len(tree.nodes) == 1
    root = tree.root
    assert root.parent_id is None
    assert root.path == ()
    assert root.region_kind is RegionKind.BODY
    assert root.span == (0, len(text))


def test_markdown_without_headings_still_yields_a_spanning_root() -> None:
    text = "solo paragrafi\n\ne nient'altro\n"
    tree = build(text)
    assert tree.root.span == (0, len(text))


def test_nested_headings_are_parent_linked_and_span_bounded() -> None:
    text = "# Uno\n\ntesto\n\n## Due\n\naltro\n\n### Tre\n\nfondo\n"
    tree = build(text)
    assert paths(tree) == [(), ("uno",), ("uno", "due"), ("uno", "due", "tre")]
    for node in tree.nodes[1:]:
        assert node.parent_id is not None
        parent = tree.node(node.parent_id)
        assert parent.contains(node)
        assert node.path[:-1] == parent.path


def test_a_sibling_heading_closes_the_previous_section_span() -> None:
    text = "# Uno\n\nprimo\n\n# Due\n\nsecondo\n"
    tree = build(text)
    first, second = tree.nodes[1], tree.nodes[2]
    assert first.parent_id == second.parent_id == tree.root.node_id
    assert first.span[1] == second.span[0]
    assert second.span[1] == len(text)


def test_duplicate_headings_receive_deterministic_distinct_paths() -> None:
    text = "## Muscoli\n\nprimo\n\n## Muscoli\n\nsecondo\n\n## Muscoli\n\nterzo\n"
    tree = build(text)
    assert paths(tree) == [(), ("muscoli",), ("muscoli-2",), ("muscoli-3",)]
    assert len({node.node_id for node in tree.nodes}) == len(tree.nodes)


def test_authored_anchor_wins_over_the_derived_slug() -> None:
    text = "## Cuffia dei rotatori {#rotator-cuff}\n\ntesto\n"
    tree = build(text)
    assert tree.nodes[1].path == ("rotator-cuff",)
    assert tree.nodes[1].heading_text == "Cuffia dei rotatori"


def test_a_region_segment_cannot_collide_with_a_heading_slug() -> None:
    text = "# Doc\n\n| a | b |\n\n## Table 1\n\ntesto\n"
    tree = build(text)
    segments = [node.path[-1] for node in tree.nodes[2:]]
    assert len(set(segments)) == len(segments)


# --- typed regions --------------------------------------------------------


def test_generic_region_kinds_are_detected_without_source_specific_enums() -> None:
    text = (
        "# Doc\n\n"
        "> [!warning] Enfasi docente\n> continua qui\n\n"
        "> [!summary] Ripasso\n\n"
        "| a | b |\n| c | d |\n\n"
        "- primo\n\n"
        "![[figura.svg]]\n\n"
        "```\ncodice\n```\n"
    )
    tree = build(text)
    kinds = [node.region_kind for node in tree.nodes if node.region_kind is not RegionKind.BODY]
    assert set(kinds) == {
        RegionKind.EMPHASIS,
        RegionKind.SUMMARY,
        RegionKind.TABLE,
        RegionKind.ITEM,
        RegionKind.FIGURE_REF,
        RegionKind.CODE,
    }


def test_a_callout_region_absorbs_its_continuation_lines() -> None:
    text = "# Doc\n\n> [!warning] Titolo\n> corpo del callout\n\ndopo\n"
    tree = build(text)
    emphasis = next(n for n in tree.nodes if n.region_kind is RegionKind.EMPHASIS)
    assert text[emphasis.span[0] : emphasis.span[1]].strip().endswith("corpo del callout")


def test_a_table_is_one_atomic_region() -> None:
    text = "# Doc\n\n| a | b |\n| - | - |\n| c | d |\n\nfine\n"
    tree = build(text)
    tables = [n for n in tree.nodes if n.region_kind is RegionKind.TABLE]
    assert len(tables) == 1
    assert text[tables[0].span[0] : tables[0].span[1]] == "| a | b |\n| - | - |\n| c | d |\n"


def test_headings_inside_a_code_fence_are_not_structural() -> None:
    text = "# Doc\n\n```\n# non un titolo\n```\n\ntesto\n"
    tree = build(text)
    assert paths(tree) == [(), ("doc",), ("doc", "code-1")]


def test_profile_flags_disable_region_detection() -> None:
    text = "# Doc\n\n| a | b |\n\n- primo\n"
    minimal = DialectProfile("minimal", "v1", heading_syntax=HeadingSyntax.ATX)
    tree = build_document_tree(text, minimal, substrate_id=substrate_of(text))
    assert all(node.region_kind is RegionKind.BODY for node in tree.nodes)


# --- flags ----------------------------------------------------------------


def test_uncertainty_flags_propagate_from_a_region_to_every_containing_node() -> None:
    text = "# Doc\n\n## Sezione\n\n| a | [VERIFICARE] |\n"
    tree = build(text)
    table = next(n for n in tree.nodes if n.region_kind is RegionKind.TABLE)
    assert "[VERIFICARE]" in table.flags
    for node in tree.nodes:
        assert "[VERIFICARE]" in node.flags


def test_an_unclosed_fence_is_flagged_rather_than_dropped() -> None:
    text = "# Doc\n\n```\ncodice mai chiuso\n"
    tree = build(text)
    code = next(n for n in tree.nodes if n.region_kind is RegionKind.CODE)
    assert MALFORMED_FLAG in code.flags
    assert code.span[1] == len(text)
    assert MALFORMED_FLAG in tree.root.flags


def test_a_flag_does_not_leak_into_an_unrelated_sibling() -> None:
    text = "# Doc\n\n## Uno\n\n| a | [VERIFICARE] |\n\n## Due\n\npulito\n"
    tree = build(text)
    clean = next(n for n in tree.nodes if n.path == ("doc", "due"))
    assert clean.flags == frozenset()


def test_only_markers_declared_by_the_profile_become_flags() -> None:
    text = "# Doc\n\n| a | [SCONOSCIUTO] |\n"
    tree = build(text)
    assert all(node.flags == frozenset() for node in tree.nodes)


# --- determinism and identity --------------------------------------------


def test_same_substrate_profile_and_version_yield_a_byte_identical_projection() -> None:
    text = "# Uno\n\n> [!warning] x\n\n## Due\n\n| a | b |\n"
    assert build(text).to_json() == build(text).to_json()


def test_node_identity_commits_to_substrate_profile_version_and_path() -> None:
    text = "# Uno\n\ntesto\n"
    tree = build(text)
    assert tree.nodes[1].node_id == node_id_for(
        substrate_id=substrate_of(text),
        tree_format_version=TREE_FORMAT_VERSION,
        profile_name=MARKDOWN.profile_name,
        profile_version=MARKDOWN.profile_version,
        path=("uno",),
    )


def test_a_different_profile_version_changes_every_node_identity() -> None:
    text = "# Uno\n\ntesto\n"
    other = DialectProfile(
        MARKDOWN.profile_name,
        "v2",
        heading_syntax=HeadingSyntax.ATX,
        fenced_code=True,
        pipe_tables=True,
        list_items=True,
        figure_reference_markers=MARKDOWN.figure_reference_markers,
        emphasis_markers=MARKDOWN.emphasis_markers,
        summary_markers=MARKDOWN.summary_markers,
        uncertainty_markers=MARKDOWN.uncertainty_markers,
    )
    first = build(text)
    second = build_document_tree(text, other, substrate_id=substrate_of(text))
    assert {n.node_id for n in first.nodes}.isdisjoint({n.node_id for n in second.nodes})


def test_identical_text_under_a_different_substrate_yields_different_node_ids() -> None:
    text = "# Uno\n\ntesto\n"
    other = build_document_tree(text, MARKDOWN, substrate_id=substrate_of(text + "\n"))
    assert build(text).root.node_id != other.root.node_id


# --- rejected input -------------------------------------------------------


@pytest.mark.parametrize("text", ["", None, 3])
def test_the_builder_rejects_non_text_substrates(text: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        build_document_tree(text, MARKDOWN, substrate_id=substrate_of("x"))  # type: ignore[arg-type]


def test_the_builder_requires_a_dialect_profile() -> None:
    with pytest.raises(TypeError):
        build_document_tree("testo\n", "markdown", substrate_id=substrate_of("x"))  # type: ignore[arg-type]


def test_the_builder_requires_a_typed_substrate_id() -> None:
    with pytest.raises(TypeError):
        build_document_tree("testo\n", MARKDOWN, substrate_id="substrate:sha256:00")  # type: ignore[arg-type]


# --- contract invariants --------------------------------------------------


def test_document_tree_rejects_a_second_root() -> None:
    root = TreeNode(_node("a"), None, (), "", RegionKind.BODY, (0, 4))
    stray = TreeNode(_node("b"), None, (), "", RegionKind.BODY, (0, 4))
    with pytest.raises(ValueError, match="exactly one root"):
        DocumentTree(substrate_of("x"), TREE_FORMAT_VERSION, "p", "v1", (root, stray))


def test_document_tree_rejects_a_child_escaping_its_parent_span() -> None:
    root = TreeNode(_node("a"), None, (), "", RegionKind.BODY, (0, 4))
    child = TreeNode(_node("b"), root.node_id, ("x",), "", RegionKind.BODY, (2, 9))
    with pytest.raises(ValueError, match="inside"):
        DocumentTree(substrate_of("x"), TREE_FORMAT_VERSION, "p", "v1", (root, child))


def test_document_tree_rejects_a_forward_parent_reference() -> None:
    root = TreeNode(_node("a"), None, (), "", RegionKind.BODY, (0, 9))
    child = TreeNode(_node("b"), _node("c"), ("x",), "", RegionKind.BODY, (0, 4))
    with pytest.raises(ValueError, match="preceding"):
        DocumentTree(substrate_of("x"), TREE_FORMAT_VERSION, "p", "v1", (root, child))


def test_document_tree_rejects_overlapping_siblings() -> None:
    root = TreeNode(_node("a"), None, (), "", RegionKind.BODY, (0, 9))
    first = TreeNode(_node("b"), root.node_id, ("x",), "", RegionKind.BODY, (0, 6))
    second = TreeNode(_node("c"), root.node_id, ("y",), "", RegionKind.BODY, (3, 9))
    with pytest.raises(ValueError, match="non-overlapping"):
        DocumentTree(substrate_of("x"), TREE_FORMAT_VERSION, "p", "v1", (root, first, second))


def test_tree_node_rejects_an_empty_or_backward_span() -> None:
    for span in ((4, 4), (5, 2), (-1, 3)):
        with pytest.raises(ValueError):
            TreeNode(_node("a"), None, (), "", RegionKind.BODY, span)


def test_tree_node_requires_root_and_path_to_agree() -> None:
    with pytest.raises(ValueError, match="root"):
        TreeNode(_node("a"), None, ("x",), "", RegionKind.BODY, (0, 4))
    with pytest.raises(ValueError, match="root"):
        TreeNode(_node("a"), _node("b"), (), "", RegionKind.BODY, (0, 4))


def test_dialect_profile_rejects_repeated_or_blank_markers() -> None:
    with pytest.raises(ValueError):
        DialectProfile("p", "v1", uncertainty_markers=("[X]", "[X]"))
    with pytest.raises(ValueError):
        DialectProfile("p", "v1", uncertainty_markers=(" ",))


def _node(seed: str) -> NodeId:
    return node_id_for(
        substrate_id=substrate_of(seed),
        tree_format_version=TREE_FORMAT_VERSION,
        profile_name="p",
        profile_version="v1",
        path=(seed,),
    )


# --- property tests -------------------------------------------------------


def random_document(rng: random.Random) -> str:
    blocks = [
        "# Titolo\n",
        "## Sotto\n",
        "### Terzo\n",
        "paragrafo di testo\n",
        "| a | b |\n| c | d |\n",
        "- elemento\n",
        "> [!warning] enfasi\n> continua\n",
        "> [!summary] ripasso\n",
        "![[figura.png]]\n",
        "```\ncodice\n```\n",
        "```\nfence aperta\n",
        "testo con [VERIFICARE] dentro\n",
        "\n",
    ]
    return "".join(rng.choice(blocks) for _ in range(rng.randint(1, 24))) or "x\n"


@pytest.mark.parametrize("seed", range(60))
def test_every_generated_tree_is_acyclic_ordered_and_contained(seed: int) -> None:
    rng = random.Random(seed)
    text = random_document(rng)
    tree = build(text)

    seen: set[NodeId] = set()
    for index, node in enumerate(tree.nodes):
        assert node.node_id not in seen
        seen.add(node.node_id)
        assert 0 <= node.span[0] < node.span[1] <= len(text)
        if index == 0:
            assert node.parent_id is None
            assert node.span == (0, len(text))
            continue
        assert node.parent_id in seen  # parents always precede children
        parent = tree.node(node.parent_id) if node.parent_id else None
        assert parent is not None
        assert parent.contains(node)
        assert node.path[:-1] == parent.path

    by_parent: dict[NodeId | None, list[TreeNode]] = {}
    for node in tree.nodes:
        by_parent.setdefault(node.parent_id, []).append(node)
    for siblings in by_parent.values():
        for left, right in pairwise(siblings):
            assert left.span[1] <= right.span[0]
            assert left.path != right.path


@pytest.mark.parametrize("seed", range(40))
def test_every_generated_tree_rebuilds_byte_identically(seed: int) -> None:
    text = random_document(random.Random(seed))
    assert build(text).to_json() == build(text).to_json()


@pytest.mark.parametrize("seed", range(40))
def test_flags_of_a_node_always_include_every_descendant_flag(seed: int) -> None:
    text = random_document(random.Random(seed))
    tree = build(text)
    for node in tree.nodes:
        for child in tree.children(node.node_id):
            assert child.flags <= node.flags
