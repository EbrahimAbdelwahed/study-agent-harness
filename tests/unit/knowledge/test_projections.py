from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from study_agent.domain import (
    FigureBlob,
    IndexProjection,
    ProjectionRef,
    RetrievableUnit,
    RevisionId,
    SourceId,
    SubstrateId,
    TextSpan,
    UnitKind,
    UnitMeta,
    unit_id_for,
)
from study_agent.domain._validation import JsonObject
from study_agent.domain.identifiers import substrate_id_for
from study_agent.domain.tree import DialectProfile, HeadingSyntax
from study_agent.knowledge.projections import (
    StructuralProjector,
    delete_projections,
    project_structural,
    projection_input_fingerprint,
    reduce_projections,
)
from study_agent.knowledge.tree import AdmittedDocumentTree, admit_tree, build_document_tree

SOURCE = SourceId("source")
REVISION = RevisionId("revision")
PROFILE = DialectProfile("markdown", "v1", heading_syntax=HeadingSyntax.ATX)
TEXT = "# Document\n## Muscoli {#muscles}\ncanonical text\n"
SUBSTRATE = substrate_id_for(TEXT.encode("utf-8"))


def make_unit(
    path: tuple[str, ...] = ("document", "muscles"),
    *,
    substrate: SubstrateId = SUBSTRATE,
) -> RetrievableUnit:
    ref = TextSpan(substrate, 0, 10)
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


def admitted_tree(
    *, leaf_heading: str = "Muscoli", path_segment: str = "muscles"
) -> AdmittedDocumentTree:
    text = f"# Document\n## {leaf_heading} {{#{path_segment}}}\ncanonical text\n"
    tree = build_document_tree(text, PROFILE, substrate_id=substrate_id_for(text.encode()))
    return admit_tree(tree, text, PROFILE)


def test_structural_projection_is_deterministic_and_round_trips() -> None:
    unit = make_unit()
    first = project_structural(unit, admitted_tree())
    second = project_structural(unit, admitted_tree())
    assert first == second
    assert first.handle == "passage: Muscoli"
    assert first.structural_context == "Document > Muscoli"
    assert IndexProjection.from_bytes(first.to_bytes()) == first
    assert ProjectionRef.from_bytes(first.ref.to_bytes()) == first.ref


def test_real_document_heading_is_not_aliased_to_synthetic_root() -> None:
    context = admitted_tree()
    projection = project_structural(
        make_unit(("document",), substrate=context.substrate_id), context
    )
    assert projection.structural_context == "Document"
    assert projection.handle == "passage unit in Document"


def test_weak_headings_have_a_safe_nonempty_fallback() -> None:
    context = admitted_tree(leaf_heading="section", path_segment="section")
    projection = StructuralProjector().project(
        make_unit(("document", "section"), substrate=context.substrate_id), context
    )
    assert projection.handle == "passage unit in Document > section"
    assert projection.summary is None
    assert projection.key_terms == projection.aliases == projection.covers == ()


def test_projection_identity_binds_every_provenance_component() -> None:
    unit = make_unit()
    base = project_structural(unit, admitted_tree())
    other_context = admitted_tree(leaf_heading="Other")
    other_unit = make_unit(substrate=other_context.substrate_id)
    assert base.projection_id != replace(base, projector_version="structural-v2").projection_id
    assert (
        base.projection_id
        != replace(
            base,
            input_fingerprint=projection_input_fingerprint(other_unit, other_context),
        ).projection_id
    )
    forged = {**base.to_json(), "output_sha256": "a" * 64}
    with pytest.raises(ValueError, match="output_sha256"):
        IndexProjection.from_json(forged)


def test_projection_bounds_and_unknown_fields_fail_closed() -> None:
    unit = make_unit()
    projection = project_structural(unit, admitted_tree())
    with pytest.raises(ValueError, match="at most"):
        replace(projection, handle="x" * 513)
    with pytest.raises(ValueError, match="fields mismatch"):
        IndexProjection.from_json({**projection.to_json(), "forged": True})


def test_delete_and_rebuild_touch_only_derived_state() -> None:
    unit = make_unit()
    projection = project_structural(unit, admitted_tree())
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
    projection = project_structural(unit, admitted_tree())
    with pytest.raises(ValueError, match="unknown canonical unit"):
        reduce_projections(cast(JsonObject, {"units": {}}), (projection,))
    with pytest.raises(ValueError, match="finite"):
        project_structural(unit, admitted_tree(), scope_policy=(float("nan"),))


def test_projection_rejects_raw_tree_context_or_version_only_invalidation() -> None:
    unit = make_unit()
    context = admitted_tree()
    with pytest.raises(TypeError, match="AdmittedDocumentTree"):
        project_structural(unit, context.tree)
    with pytest.raises(TypeError, match="AdmittedDocumentTree"):
        project_structural(unit, (context.root,))
    with pytest.raises(TypeError, match="admit_tree"):
        AdmittedDocumentTree()
    projection = project_structural(unit, context)
    state = reduce_projections({"units": {str(unit.unit_id): unit.to_json()}}, (projection,))
    with pytest.raises(ValueError, match="requires"):
        delete_projections(state, projector_version=projection.projector_version)


def test_projection_requires_matching_text_substrate_and_resolves_figures_by_path() -> None:
    context = admitted_tree()
    wrong = make_unit(substrate=SubstrateId("substrate:sha256:" + "a" * 64))
    with pytest.raises(ValueError, match="substrate"):
        project_structural(wrong, context)

    figure_ref = FigureBlob("c" * 64, 1)
    path = ("document", "muscles")
    figure = RetrievableUnit(
        unit_id_for(
            revision_id=REVISION,
            structural_path=path,
            unit_kind=UnitKind.FIGURE.value,
            granularity=4,
            canonical_ref=figure_ref.to_json(),
            unitizer_version="unitizer-v1",
        ),
        SOURCE,
        REVISION,
        UnitKind.FIGURE,
        4,
        path,
        figure_ref,
        UnitMeta("notes", "figure", 80),
    )
    projection = project_structural(figure, context)
    assert projection.handle == "figure: Muscoli"


def test_long_admitted_heading_is_truncated_deterministically() -> None:
    context = admitted_tree(leaf_heading="A" * 2_000, path_segment="long-heading")
    projection = project_structural(
        make_unit(("document", "long-heading"), substrate=context.substrate_id), context
    )
    assert len(projection.handle) <= 512
    assert len(projection.structural_context) <= 1_024
    assert projection == project_structural(
        make_unit(("document", "long-heading"), substrate=context.substrate_id), context
    )


def test_tree_admission_rejects_tampered_spans() -> None:
    text = "# Topic\n\ncanonical\n"
    profile = DialectProfile("markdown", "v1", heading_syntax=HeadingSyntax.ATX)
    tree = build_document_tree(text, profile, substrate_id=substrate_id_for(text.encode()))
    admitted = admit_tree(tree, text, profile)
    assert admitted.tree == tree
    tampered = replace(tree.nodes[1], span=(tree.nodes[1].span[0], tree.nodes[1].span[1] - 1))
    with pytest.raises(ValueError, match="admission"):
        admit_tree(replace(tree, nodes=(tree.nodes[0], tampered)), text, profile)
