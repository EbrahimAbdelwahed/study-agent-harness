from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import cast

import pytest

from study_agent.domain import (
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
    node_id_for,
    unit_id_for,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.identifiers import NodeId
from study_agent.domain.tree import RegionKind, TreeNode
from study_agent.knowledge.projections import (
    MAX_POLICY_DEPTH,
    MAX_POLICY_ITEMS,
    StructuralProjector,
    delete_projections,
    project_structural,
    reduce_projections,
)

SOURCE = SourceId("source")
REVISION = RevisionId("revision")
SUBSTRATE = SubstrateId("substrate:sha256:" + "b" * 64)


def make_unit(*, unitizer_version: str = "unitizer-v1") -> RetrievableUnit:
    path = ("document", "muscles")
    ref = TextSpan(SUBSTRATE, 0, 10)
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


def state_for(unit: RetrievableUnit) -> JsonObject:
    return {
        "units": {str(unit.unit_id): unit.to_json()},
        "events": ("canonical-event",),
        "metadata": {"owner": "canonical"},
    }


def test_unknown_canonical_unit_is_rejected_without_writing_derived_rows() -> None:
    unit = make_unit()
    projection = project_structural(unit, ancestors())
    state = cast(JsonObject, {"units": {}, "events": ("canonical-event",)})

    with pytest.raises(ValueError, match="unknown canonical unit"):
        reduce_projections(state, (projection,))

    assert state == {"units": {}, "events": ("canonical-event",)}


def test_fabricated_and_out_of_order_ancestor_nodes_are_rejected() -> None:
    unit = make_unit()
    root, document, leaf = ancestors()
    fabricated = replace(
        leaf,
        node_id=NodeId("node:sha256:" + "c" * 64),
    )

    with pytest.raises(ValueError, match=r"canonical|identity|admission"):
        project_structural(unit, (root, document, fabricated))
    with pytest.raises(ValueError, match="ordered"):
        project_structural(unit, (root, leaf, document))


def test_policy_depth_size_and_nonfinite_values_are_bounded() -> None:
    unit = make_unit()
    too_deep: tuple[JsonValue, ...] = ("x",)
    for _ in range(MAX_POLICY_DEPTH + 1):
        too_deep = (too_deep,)

    with pytest.raises(ValueError, match="depth bound"):
        project_structural(unit, ancestors(), scope_policy=too_deep)
    with pytest.raises(ValueError, match="item bound"):
        project_structural(
            unit,
            ancestors(),
            producer_policy=tuple("x" for _ in range(MAX_POLICY_ITEMS + 1)),
        )
    with pytest.raises(ValueError, match="finite"):
        project_structural(unit, ancestors(), scope_policy=(float("nan"),))


def test_exact_projector_name_and_version_invalidation_is_isolated() -> None:
    unit = make_unit()
    first = project_structural(unit, ancestors())
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
    projection = project_structural(unit, ancestors())
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
    projection = project_structural(make_unit(), ancestors())
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
    projection = StructuralProjector().project(
        make_unit(), ancestors(leaf_heading="A" * 2_000)
    )
    assert len(projection.handle) <= 512
    assert len(projection.structural_context) <= 1_024


def test_explicit_unitizer_version_requires_matching_projection_context() -> None:
    unit = make_unit(unitizer_version="unitizer-v2")
    projection = project_structural(unit, ancestors())
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
