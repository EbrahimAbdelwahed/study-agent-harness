from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from study_agent.domain import (
    DialectProfile,
    IndexProjection,
    ProjectionRef,
    RetrievableUnit,
    RevisionId,
    SourceId,
    SubstrateId,
    TextSpan,
    UnitKind,
    UnitMeta,
    node_id_for,
    unit_id_for,
)
from study_agent.domain._validation import JsonObject
from study_agent.domain.identifiers import substrate_id_for
from study_agent.domain.tree import HeadingSyntax, RegionKind, TreeNode
from study_agent.knowledge.projections import (
    StructuralProjector,
    delete_projections,
    project_structural,
    projection_input_fingerprint,
    reduce_projections,
)
from study_agent.knowledge.tree import admit_tree, build_document_tree

SOURCE = SourceId("source")
REVISION = RevisionId("revision")
SUBSTRATE = SubstrateId("substrate:sha256:" + "b" * 64)


def make_unit(path: tuple[str, ...] = ("document", "muscles")) -> RetrievableUnit:
    ref = TextSpan(SUBSTRATE, 0, 10)
    return RetrievableUnit(
        unit_id_for(
            revision_id=REVISION,
            structural_path=path,
            unit_kind=UnitKind.PASSAGE.value,
            granularity=3,
            canonical_ref=ref.to_json(),
            unitizer_version="unitizer-v1",
        ),
        SOURCE,
        REVISION,
        UnitKind.PASSAGE,
        3,
        path,
        ref,
        UnitMeta("notes", "primary", 80),
    )


def ancestors(*, leaf_heading: str = "Muscoli") -> tuple[TreeNode, ...]:
    root = TreeNode(
        node_id_for(
            substrate_id=SUBSTRATE,
            tree_format_version="document-tree-v1",
            profile_name="markdown",
            profile_version="v1",
            path=(),
        ),
        None,
        (),
        "",
        RegionKind.BODY,
        (0, 100),
    )
    document = TreeNode(
        node_id_for(
            substrate_id=SUBSTRATE,
            tree_format_version="document-tree-v1",
            profile_name="markdown",
            profile_version="v1",
            path=("document",),
        ),
        root.node_id,
        ("document",),
        "document",
        RegionKind.BODY,
        (0, 100),
    )
    leaf = TreeNode(
        node_id_for(
            substrate_id=SUBSTRATE,
            tree_format_version="document-tree-v1",
            profile_name="markdown",
            profile_version="v1",
            path=("document", "muscles"),
        ),
        document.node_id,
        ("document", "muscles"),
        leaf_heading,
        RegionKind.BODY,
        (0, 100),
    )
    return root, document, leaf


def test_structural_projection_is_deterministic_and_round_trips() -> None:
    unit = make_unit()
    first = project_structural(unit, ancestors())
    second = project_structural(unit, ancestors())
    assert first == second
    assert first.handle == "passage: Muscoli"
    assert first.structural_context == "document > Muscoli"
    assert IndexProjection.from_bytes(first.to_bytes()) == first
    assert ProjectionRef.from_bytes(first.ref.to_bytes()) == first.ref


def test_weak_headings_have_a_safe_nonempty_fallback() -> None:
    projection = StructuralProjector().project(make_unit(), ancestors(leaf_heading="section"))
    assert projection.handle == "passage unit in document > section"
    assert projection.summary is None
    assert projection.key_terms == projection.aliases == projection.covers == ()


def test_projection_identity_binds_every_provenance_component() -> None:
    unit = make_unit()
    base = project_structural(unit, ancestors())
    assert base.projection_id != replace(base, projector_version="structural-v2").projection_id
    assert (
        base.projection_id
        != replace(
            base,
            input_fingerprint=projection_input_fingerprint(unit, ancestors(leaf_heading="Other")),
        ).projection_id
    )
    forged = {**base.to_json(), "output_sha256": "a" * 64}
    with pytest.raises(ValueError, match="output_sha256"):
        IndexProjection.from_json(forged)


def test_projection_bounds_and_unknown_fields_fail_closed() -> None:
    unit = make_unit()
    projection = project_structural(unit, ancestors())
    with pytest.raises(ValueError, match="at most"):
        replace(projection, handle="x" * 513)
    with pytest.raises(ValueError, match="fields mismatch"):
        IndexProjection.from_json({**projection.to_json(), "forged": True})


def test_delete_and_rebuild_touch_only_derived_state() -> None:
    unit = make_unit()
    projection = project_structural(unit, ancestors())
    state: JsonObject = {
        "units": {str(unit.unit_id): unit.to_json()},
        "events": ("canonical",),
    }
    projected = reduce_projections(state, (projection,))
    deleted = delete_projections(projected, projector_name="structural")
    assert deleted["units"] == state["units"]
    assert deleted["events"] == state["events"]
    assert deleted["projections"] == {}
    rebuilt = reduce_projections(deleted, (projection,))
    assert rebuilt["projections"] == projected["projections"]


def test_projection_rejects_unknown_units_and_unbounded_policy_values() -> None:
    unit = make_unit()
    projection = project_structural(unit, ancestors())
    with pytest.raises(ValueError, match="unknown canonical unit"):
        reduce_projections(cast(JsonObject, {"units": {}}), (projection,))
    with pytest.raises(ValueError, match="finite"):
        project_structural(unit, ancestors(), scope_policy=(float("nan"),))


def test_projection_rejects_non_ancestor_or_version_only_invalidation() -> None:
    unit = make_unit()
    with pytest.raises(TypeError, match="TreeNode"):
        project_structural(unit, ("forged",))  # type: ignore[arg-type]
    wrong = replace(ancestors()[-1], path=("wrong",), parent_id=ancestors()[0].node_id)
    with pytest.raises(ValueError, match="prefix"):
        project_structural(unit, (ancestors()[0], wrong))
    projection = project_structural(unit, ancestors())
    state = reduce_projections({"units": {str(unit.unit_id): unit.to_json()}}, (projection,))
    with pytest.raises(ValueError, match="requires"):
        delete_projections(state, projector_version=projection.projector_version)


def test_long_admitted_heading_is_truncated_deterministically() -> None:
    unit = make_unit()
    projection = project_structural(unit, ancestors(leaf_heading="A" * 2_000))
    assert len(projection.handle) <= 512
    assert len(projection.structural_context) <= 1_024
    assert projection == project_structural(unit, ancestors(leaf_heading="A" * 2_000))


def test_tree_admission_rejects_tampered_spans() -> None:
    text = "# Topic\n\ncanonical\n"
    profile = DialectProfile("markdown", "v1", heading_syntax=HeadingSyntax.ATX)
    tree = build_document_tree(text, profile, substrate_id=substrate_id_for(text.encode()))
    assert admit_tree(tree, text, profile) == tree
    tampered = replace(tree.nodes[1], span=(tree.nodes[1].span[0], tree.nodes[1].span[1] - 1))
    with pytest.raises(ValueError, match="admission"):
        admit_tree(replace(tree, nodes=(tree.nodes[0], tampered)), text, profile)
