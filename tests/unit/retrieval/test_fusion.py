from __future__ import annotations

from hashlib import sha256

import pytest

from study_agent.domain.identifiers import RevisionId, ScopeId, SourceId, SubstrateId, UnitId
from study_agent.domain.units import (
    LinkKind,
    RetrievableUnit,
    ReviewStatus,
    TextSpan,
    UnitKind,
    UnitLink,
    UnitMeta,
)
from study_agent.ports.retrievers import (
    RetrieverCandidate,
    RetrieverCandidateList,
    RetrieverQuery,
    RetrieverSearchBatch,
    RetrieverSkipReason,
    RetrieverSkipReceipt,
    _registry_fingerprint,
)
from study_agent.retrieval.fusion import (
    FusionError,
    FusionPolicy,
    FusionResultStatus,
    fuse_candidates,
)


def _digest(seed: str) -> str:
    return sha256(seed.encode()).hexdigest()


def _unit(
    name: str,
    *,
    source: str = "source-a",
    revision: str = "revision-a",
    kind: UnitKind = UnitKind.PASSAGE,
    granularity: int = 3,
    parent: RetrievableUnit | None = None,
    ordinal: int = 0,
    flags: frozenset[str] = frozenset(),
    source_class: str = "reference",
    review: ReviewStatus = ReviewStatus.REVIEWED,
) -> RetrievableUnit:
    unit_id = UnitId(f"unit:sha256:{_digest(name)}")
    substrate_id = SubstrateId(f"substrate:sha256:{_digest(revision)}")
    links = () if parent is None else (UnitLink(LinkKind.PARENT, parent.unit_id),)
    return RetrievableUnit(
        unit_id,
        SourceId(source),
        RevisionId(revision),
        kind,
        granularity,
        ("section-a", name),
        TextSpan(substrate_id, 0, max(1, len(name))),
        UnitMeta(source_class, "lecture", 90, review, flags, ordinal),
        links,
    )


def _query() -> RetrieverQuery:
    return RetrieverQuery(ScopeId("exam"), "heart valve", 10)


def _batch(
    lists: tuple[RetrieverCandidateList, ...],
    *,
    identities: tuple[str, ...] = ("lex_projection@1",),
    skips: tuple[RetrieverSkipReceipt, ...] = (),
) -> RetrieverSearchBatch:
    query = _query()
    snapshots = tuple((identity, _digest(f"manifest:{identity}")) for identity in identities)
    return RetrieverSearchBatch(
        query,
        _digest("host"),
        _registry_fingerprint(snapshots),
        snapshots,
        lists,
        skips,
    )


def _list(
    units: tuple[RetrievableUnit, ...],
    *,
    identity: str = "lex_projection@1",
    ranks: tuple[int, ...] | None = None,
) -> RetrieverCandidateList:
    query = _query()
    manifest = _digest(f"manifest:{identity}")
    ordered = tuple(sorted(units, key=lambda item: str(item.unit_id)))
    values = tuple(
        RetrieverCandidate(
            unit.unit_id,
            None,
            rank,
            1.0,
            query.fingerprint,
            identity,
            manifest,
            "lex_projection",
            "index-v1",
        )
        for rank, unit in zip(ranks or tuple(range(1, len(ordered) + 1)), ordered, strict=True)
    )
    return RetrieverCandidateList(
        query.fingerprint,
        identity,
        manifest,
        "lex_projection",
        "index-v1",
        values,
        10,
    )


def test_weighted_rrf_consensus_and_ties_are_deterministic() -> None:
    first = _unit("a")
    second = _unit("b")
    one = _list((first, second))
    two = _list((second, first), identity="semantic@1", ranks=(1, 2))
    policy = FusionPolicy(
        retriever_weights=(("lex_projection@1", 1.0), ("semantic@1", 1.0)),
        max_parent_attachments=0,
        max_sibling_attachments=0,
        max_window_attachments=0,
    )
    result = fuse_candidates(
        _batch((one, two), identities=("lex_projection@1", "semantic@1")),
        {first.unit_id: first, second.unit_id: second},
        policy,
    )
    assert result.status is FusionResultStatus.READY
    assert [str(group.unit_id) for group in result.groups] == sorted(
        (str(first.unit_id), str(second.unit_id))
    )
    assert result.groups[0].consensus == 2
    assert result.groups[0].rrf_score == pytest.approx(2 / 61)


def test_weight_changes_order_and_one_retriever_contributes_once() -> None:
    first = _unit("first")
    second = _unit("second")
    batch = _batch((_list((first, second)),))
    result = fuse_candidates(
        batch,
        (first, second),
        FusionPolicy(
            retriever_weights=(("lex_projection@1", 2.0),),
            max_parent_attachments=0,
            max_sibling_attachments=0,
            max_window_attachments=0,
        ),
    )
    assert result.groups[0].rrf_score == pytest.approx(2 / 61)
    assert result.groups[0].consensus == 1


def test_empty_or_skipped_batch_is_explicitly_insufficient() -> None:
    result = fuse_candidates(
        _batch((RetrieverCandidateList(
            _query().fingerprint,
            "lex_projection@1",
            _digest("manifest:lex_projection@1"),
            "lex_projection",
            "index-v1",
            (),
            10,
        ),)),
        (),
        FusionPolicy(retriever_weights=(("lex_projection@1", 1.0),)),
    )
    assert result.status is FusionResultStatus.INSUFFICIENT
    assert result.reason == "no_candidates"


def test_parent_child_ladder_collapses_and_keeps_narrow_primary_ref() -> None:
    parent = _unit("section", kind=UnitKind.SECTION, granularity=1)
    child = _unit("child", parent=parent, kind=UnitKind.PASSAGE, granularity=3)
    result = fuse_candidates(
        _batch((_list((parent, child)),)),
        (parent, child),
        FusionPolicy(
            retriever_weights=(("lex_projection@1", 1.0),),
            max_parent_attachments=0,
            max_sibling_attachments=0,
            max_window_attachments=0,
        ),
    )
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.primary_unit == child
    assert group.canonical_ref == child.canonical_ref
    assert group.members == tuple(sorted((parent.unit_id, child.unit_id), key=str))


def test_priors_and_uncertainty_are_receipted_without_recency() -> None:
    uncertain = _unit(
        "uncertain",
        flags=frozenset({"uncertain"}),
        source_class="notes",
        review=ReviewStatus.UNREVIEWED,
    )
    certain = _unit("certain", source_class="reference")
    result = fuse_candidates(
        _batch((_list((uncertain, certain)),)),
        (uncertain, certain),
        FusionPolicy(
            retriever_weights=(("lex_projection@1", 1.0),),
            source_class_priors=(("reference", 0.2), ("notes", 0.0)),
            review_priors=(("reviewed", 0.1),),
            uncertainty_penalty=0.05,
            max_parent_attachments=0,
            max_sibling_attachments=0,
            max_window_attachments=0,
        ),
    )
    assert result.groups[0].unit_id == certain.unit_id
    receipt = next(
        group.prior_receipt
        for group in result.groups
        if group.unit_id == uncertain.unit_id
    )
    assert receipt.uncertainty is True
    assert receipt.uncertainty_penalty == pytest.approx(0.05)


def test_diversity_caps_and_context_expansion_are_bounded() -> None:
    parent = _unit("section", kind=UnitKind.SECTION, granularity=1)
    first = _unit("first", parent=parent, ordinal=1)
    sibling = _unit("sibling", parent=parent, ordinal=2)
    other = _unit("other", source="source-b")
    result = fuse_candidates(
        _batch((_list((first, sibling, other)),)),
        (parent, first, sibling, other),
        FusionPolicy(
            retriever_weights=(("lex_projection@1", 1.0),),
            max_units_per_source=1,
            max_units_per_section=1,
            max_parent_attachments=1,
            max_sibling_attachments=1,
            max_window_attachments=1,
            max_attachments_per_group=2,
        ),
    )
    assert len(result.groups) == 2
    assert all(len(group.attachments) <= 2 for group in result.groups)
    assert any(group.primary_unit.canonical_ref == first.canonical_ref for group in result.groups)


def test_hostile_catalog_and_weight_provenance_fail_closed() -> None:
    parent = _unit("parent")
    child = _unit("child", parent=parent)
    with pytest.raises(FusionError, match="catalog key"):
        fuse_candidates(
            _batch((_list((child,)),)),
            {parent.unit_id: child},
            FusionPolicy(retriever_weights=(("lex_projection@1", 1.0),)),
        )
    foreign = _unit("foreign", revision="revision-b")
    foreign_child = _unit("foreign-child", parent=parent, revision="revision-b")
    with pytest.raises(FusionError, match="cross-source or cross-revision"):
        fuse_candidates(
            _batch((_list((foreign_child,)),)),
            (parent, foreign_child),
            FusionPolicy(retriever_weights=(("lex_projection@1", 1.0),)),
        )
    del foreign
    skipped = fuse_candidates(
        _batch(
            (_list((child,)),),
            identities=("lex_projection@1", "semantic@1"),
            skips=(
                RetrieverSkipReceipt(
                    "semantic@1",
                    _digest("manifest:semantic@1"),
                    RetrieverSkipReason.MISSING_CAPABILITY,
                ),
            ),
        ),
        (parent, child),
        FusionPolicy(retriever_weights=(("lex_projection@1", 1.0),)),
    )
    assert skipped.status is FusionResultStatus.READY
    with pytest.raises(FusionError, match="unknown manifest"):
        fuse_candidates(
            _batch((_list((child,)),)),
            (parent, child),
            FusionPolicy(
                retriever_weights=(
                    ("lex_projection@1", 1.0),
                    ("unknown@1", 1.0),
                )
            ),
        )
    with pytest.raises(FusionError, match="required"):
        fuse_candidates(_batch((_list((child,)),)), (parent, child), FusionPolicy())


def test_catalog_permutation_does_not_change_result() -> None:
    parent = _unit("parent", kind=UnitKind.SECTION, granularity=1)
    first = _unit("first", parent=parent)
    second = _unit("second", parent=parent)
    policy = FusionPolicy(
        retriever_weights=(("lex_projection@1", 1.0),),
        max_parent_attachments=1,
        max_sibling_attachments=1,
        max_window_attachments=1,
    )
    batch = _batch((_list((first, second)),))
    left = fuse_candidates(batch, (parent, first, second), policy)
    right = fuse_candidates(batch, (second, parent, first), policy)
    assert left == right
