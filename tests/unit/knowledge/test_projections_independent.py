from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import cast

import pytest

from study_agent.domain import (
    DialectProfile,
    IndexProjection,
    ProjectionId,
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
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.identifiers import substrate_id_for
from study_agent.domain.tree import HeadingSyntax
from study_agent.knowledge.projections import (
    MAX_POLICY_DEPTH,
    MAX_POLICY_ITEMS,
    StructuralProjector,
    delete_projections,
    project_structural,
    reduce_projections,
)
from study_agent.knowledge.tree import AdmittedDocumentTree, admit_tree, build_document_tree

SOURCE = SourceId("source")
REVISION = RevisionId("revision")
PROFILE = DialectProfile("markdown", "v1", heading_syntax=HeadingSyntax.ATX)
TEXT = "# Document\n## Muscoli {#muscles}\ncanonical text\n"
SUBSTRATE = substrate_id_for(TEXT.encode("utf-8"))


def make_unit(
    *,
    unitizer_version: str = "unitizer-v1",
    substrate: SubstrateId = SUBSTRATE,
    path: tuple[str, ...] = ("document", "muscles"),
) -> RetrievableUnit:
    ref = TextSpan(substrate, 0, 10)
    return RetrievableUnit(
        unit_id_for(
            revision_id=REVISION,
            structural_path=path,
            unit_kind=UnitKind.PASSAGE.value,
            granularity=3,
            canonical_ref=ref.to_json(),
            unitizer_version=unitizer_version,
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


def state_for(unit: RetrievableUnit) -> JsonObject:
    return {
        "units": {str(unit.unit_id): unit.to_json()},
        "events": ("canonical-event",),
        "metadata": {"owner": "canonical"},
    }


def test_unknown_canonical_unit_is_rejected_without_writing_derived_rows() -> None:
    unit = make_unit()
    projection = project_structural(unit, admitted_tree())
    state = cast(JsonObject, {"units": {}, "events": ("canonical-event",)})

    with pytest.raises(ValueError, match="unknown canonical unit"):
        reduce_projections(state, (projection,))

    assert state == {"units": {}, "events": ("canonical-event",)}


def test_fabricated_and_out_of_order_ancestor_nodes_are_rejected() -> None:
    unit = make_unit()
    context = admitted_tree()
    with pytest.raises(TypeError, match="AdmittedDocumentTree"):
        project_structural(unit, context.tree)
    with pytest.raises(TypeError, match="AdmittedDocumentTree"):
        project_structural(unit, (context.root, context.nodes[-1]))


def test_policy_depth_size_and_nonfinite_values_are_bounded() -> None:
    unit = make_unit()
    too_deep: tuple[JsonValue, ...] = ("x",)
    for _ in range(MAX_POLICY_DEPTH + 1):
        too_deep = (too_deep,)

    with pytest.raises(ValueError, match="depth bound"):
        project_structural(unit, admitted_tree(), scope_policy=too_deep)
    with pytest.raises(ValueError, match="item bound"):
        project_structural(
            unit,
            admitted_tree(),
            producer_policy=tuple("x" for _ in range(MAX_POLICY_ITEMS + 1)),
        )
    with pytest.raises(ValueError, match="finite"):
        project_structural(unit, admitted_tree(), scope_policy=(float("nan"),))


def test_exact_projector_name_and_version_invalidation_is_isolated() -> None:
    unit = make_unit()
    first = project_structural(unit, admitted_tree())
    upgraded = replace(first, projector_version="structural-v2")
    state = reduce_projections(state_for(unit), (first, upgraded))

    deleted = delete_projections(
        state,
        projector_name=first.projector_name,
        projector_version=first.projector_version,
    )
    rows = deleted.get("projections")
    assert isinstance(rows, Mapping)

    assert str(first.projection_id) not in rows
    assert str(upgraded.projection_id) in rows
    assert deleted["units"] == state["units"]
    assert deleted["events"] == state["events"]


def test_delete_and_rebuild_preserve_canonical_unit_and_event_state() -> None:
    unit = make_unit()
    projection = project_structural(unit, admitted_tree())
    canonical = state_for(unit)
    projected = reduce_projections(canonical, (projection,))
    deleted = delete_projections(
        projected,
        projector_name=projection.projector_name,
        projector_version=projection.projector_version,
    )
    rebuilt = reduce_projections(deleted, (projection,))

    assert deleted["units"] == canonical["units"]
    assert deleted["events"] == canonical["events"]
    assert deleted["metadata"] == canonical["metadata"]
    assert rebuilt["units"] == canonical["units"]
    assert rebuilt["events"] == canonical["events"]
    assert rebuilt["projections"] == projected["projections"]


def test_projection_codecs_reject_noncanonical_bytes_and_provenance_forgery() -> None:
    projection = project_structural(make_unit(), admitted_tree())
    codec_pairs: tuple[tuple[Callable[[bytes], object], bytes], ...] = (
        (IndexProjection.from_bytes, projection.to_bytes()),
        (ProjectionId.from_bytes, projection.projection_id.to_bytes()),
        (ProjectionRef.from_bytes, projection.ref.to_bytes()),
    )
    for decode, encoded in codec_pairs:
        with pytest.raises(ValueError, match="canonical"):
            decode(encoded + b" ")

    output_forgery = {**projection.to_json(), "output_sha256": "a" * 64}
    with pytest.raises(ValueError, match="output_sha256"):
        IndexProjection.from_json(output_forgery)

    input_forgery = {
        **projection.to_json(),
        "input_fingerprint": "c" * 64,
    }
    forged = IndexProjection.from_json(input_forgery)
    assert forged.projection_id != projection.projection_id
    assert forged.ref != projection.ref


def test_long_headings_have_bounded_projection_fallbacks() -> None:
    context = admitted_tree(leaf_heading="A" * 2_000, path_segment="long-heading")
    projection = StructuralProjector().project(
        make_unit(path=("document", "long-heading"), substrate=context.substrate_id), context
    )
    assert len(projection.handle) <= 512
    assert len(projection.structural_context) <= 1_024


def test_explicit_unitizer_version_requires_matching_projection_context() -> None:
    unit = make_unit(unitizer_version="unitizer-v2")
    projection = project_structural(unit, admitted_tree())
    state = state_for(unit)

    with pytest.raises(ValueError):
        reduce_projections(state, (projection,))
    reduce_with_context = cast(
        Callable[..., Mapping[str, JsonValue]],
        reduce_projections,
    )
    with pytest.raises(ValueError):
        reduce_with_context(state, (projection,), unitizer_version="unitizer-v1")
    accepted = reduce_with_context(
        state,
        (projection,),
        unitizer_version="unitizer-v2",
    )
    rows = accepted.get("projections")
    assert isinstance(rows, Mapping)
    assert str(projection.projection_id) in rows
