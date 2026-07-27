from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from hashlib import sha256

import pytest

from study_agent.domain.identifiers import ScopeId, UnitId
from study_agent.domain.projections import ProjectionId
from study_agent.ports.knowledge import (
    LexicalCandidate,
    LexicalCandidateList,
    LexicalIndexReceipt,
    LexicalProjectionBinding,
    LexicalSurface,
)
from study_agent.ports.retrievers import (
    RetrieverCandidate,
    RetrieverCandidateList,
    RetrieverCost,
    RetrieverFilter,
    RetrieverHostAuthority,
    RetrieverManifest,
    RetrieverNetwork,
    RetrieverQuery,
    RetrieverSkipReason,
)
from study_agent.retrieval.lexical import LexicalRetriever
from study_agent.retrieval.registry import RetrieverRegistry, RetrieverRegistryError


def _digest(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _unit(label: str) -> UnitId:
    return UnitId(f"unit:sha256:{_digest(label)}")


def _projection(unit: UnitId, label: str) -> ProjectionId:
    return ProjectionId(unit, _digest(label + "-input"), "projector", "v1", None, _digest(label))


@dataclass
class FakeLexicalIndex:
    called: int = 0

    def index(self, bindings: Sequence[LexicalProjectionBinding]) -> LexicalIndexReceipt:
        return LexicalIndexReceipt(len(bindings), "index-v1", _digest("catalog"))

    def rebuild(self, bindings: Sequence[LexicalProjectionBinding]) -> LexicalIndexReceipt:
        return self.index(bindings)

    def search(self, query: object) -> LexicalCandidateList:
        self.called += 1
        assert isinstance(query, object)
        from study_agent.ports.knowledge import LexicalQuery

        assert isinstance(query, LexicalQuery)
        first = _unit("first")
        second = _unit("second")
        candidates = (
            LexicalCandidate(
                first, _projection(first, "first"), 1, 1.0, query.fingerprint, "index-v1"
            ),
            LexicalCandidate(
                second, _projection(second, "second"), 2, 0.5, query.fingerprint, "index-v1"
            ),
        )
        return LexicalCandidateList(
            query.surface, query.fingerprint, "index-v1", candidates
        )


class OptionalRetriever:
    def __init__(self, manifest: RetrieverManifest) -> None:
        self._manifest = manifest
        self.called = 0

    @property
    def manifest(self) -> RetrieverManifest:
        return self._manifest

    def search(self, query: RetrieverQuery) -> RetrieverCandidateList:
        self.called += 1
        return RetrieverCandidateList(
            query.fingerprint,
            self._manifest.identity,
            self._manifest.fingerprint,
            self._manifest.surface,
            "optional-v1",
            (),
            query.limit,
        )


def _query(*, filters: tuple[RetrieverFilter, ...] = ()) -> RetrieverQuery:
    return RetrieverQuery(ScopeId("exam"), "heart valve", 5, filters)


def test_lexical_baseline_runs_and_keeps_only_portable_candidate_data() -> None:
    index = FakeLexicalIndex()
    baseline = LexicalRetriever(index, LexicalSurface.PROJECTION)
    batch = RetrieverRegistry((baseline,), RetrieverHostAuthority()).search(_query())
    assert index.called == 1
    assert [item.retriever_identity for item in batch.results] == ["lex_projection@1"]
    assert batch.skips == ()
    candidate = batch.results[0].candidates[0]
    assert candidate.unit_id == _unit("first")
    assert candidate.projection_id is not None
    assert not hasattr(candidate, "text")


def test_optional_retriever_is_skipped_without_invocation() -> None:
    optional = OptionalRetriever(
        RetrieverManifest(
            "semantic",
            "v1",
            "semantic",
            cost=RetrieverCost.LOCAL_COMPUTE,
            required_capability="embedding",
        )
    )
    batch = RetrieverRegistry(
        (LexicalRetriever(FakeLexicalIndex(), LexicalSurface.PROJECTION), optional),
        RetrieverHostAuthority(),
    ).search(_query())
    assert optional.called == 0
    assert batch.skips[0].reason is RetrieverSkipReason.MISSING_CAPABILITY


def test_filters_are_literal_data_and_skip_unsupported_ports() -> None:
    optional = OptionalRetriever(RetrieverManifest("optional", "v1", "optional"))
    query = _query(filters=(RetrieverFilter("source", ("a OR 1=1",)),))
    batch = RetrieverRegistry(
        (LexicalRetriever(FakeLexicalIndex(), LexicalSurface.PROJECTION), optional),
        RetrieverHostAuthority(),
    ).search(query)
    assert optional.called == 0
    assert len(batch.skips) == 2
    assert all(item.reason is RetrieverSkipReason.UNSUPPORTED_FILTER for item in batch.skips)


def test_duplicate_active_name_or_surface_and_missing_baseline_are_rejected() -> None:
    with pytest.raises(RetrieverRegistryError):
        RetrieverRegistry(
            (
                LexicalRetriever(FakeLexicalIndex(), LexicalSurface.PROJECTION),
                LexicalRetriever(FakeLexicalIndex(), LexicalSurface.PROJECTION),
            ),
            RetrieverHostAuthority(),
        )
    with pytest.raises(RetrieverRegistryError):
        RetrieverRegistry(
            (OptionalRetriever(RetrieverManifest("optional", "v1", "optional")),),
            RetrieverHostAuthority(),
        )


def test_candidate_ties_use_unit_then_projection_identity() -> None:
    first = _unit("tie-a")
    second = _unit("tie-b")
    query_fingerprint = _digest("query")
    manifest_fingerprint = _digest("manifest")
    first_candidate = RetrieverCandidate(
        first,
        None,
        1,
        1.0,
        query_fingerprint,
        "lex_projection@1",
        manifest_fingerprint,
        "lex_projection",
        "index-v1",
    )
    second_candidate = RetrieverCandidate(
        second,
        None,
        2,
        1.0,
        query_fingerprint,
        "lex_projection@1",
        manifest_fingerprint,
        "lex_projection",
        "index-v1",
    )
    ordered = sorted((first_candidate, second_candidate), key=lambda item: str(item.unit_id))
    result = RetrieverCandidateList(
        query_fingerprint,
        "lex_projection@1",
        manifest_fingerprint,
        "lex_projection",
        "index-v1",
        tuple(ordered),
        2,
    )
    assert result.candidates == tuple(ordered)
    with pytest.raises(ValueError, match="equal-score"):
        RetrieverCandidateList(
            query_fingerprint,
            "lex_projection@1",
            manifest_fingerprint,
            "lex_projection",
            "index-v1",
            (replace(ordered[1], rank=1), replace(ordered[0], rank=2)),
            2,
        )


def test_manifest_gating_constraints_and_registry_immutability() -> None:
    with pytest.raises(ValueError, match="capability gate"):
        RetrieverManifest(
            "remote",
            "v1",
            "remote",
            network=RetrieverNetwork.REQUIRED,
        )
    registry = RetrieverRegistry(
        (LexicalRetriever(FakeLexicalIndex(), LexicalSurface.PROJECTION),),
        RetrieverHostAuthority(),
    )
    with pytest.raises(AttributeError):
        registry._registrations = ()
