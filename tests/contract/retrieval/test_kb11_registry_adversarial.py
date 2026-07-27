from __future__ import annotations

from typing import cast

import pytest

from study_agent.domain.identifiers import ScopeId, UnitId
from study_agent.ports.retrievers import (
    MAX_RETRIEVER_LIMIT,
    MAX_RETRIEVER_REGISTRY_SIZE,
    RetrieverCandidate,
    RetrieverCandidateList,
    RetrieverCost,
    RetrieverFilter,
    RetrieverHostAuthority,
    RetrieverManifest,
    RetrieverNetwork,
    RetrieverPort,
    RetrieverQuery,
    RetrieverSkipReason,
)
from study_agent.retrieval.registry import RetrieverRegistry, RetrieverRegistryError


def _query(*, limit: int = 3, filters: tuple[RetrieverFilter, ...] = ()) -> RetrieverQuery:
    return RetrieverQuery(ScopeId("exam"), "heart valve", limit, filters)


def _manifest(
    name: str,
    *,
    cost: RetrieverCost = RetrieverCost.FREE,
    required_capability: str | None = None,
    network: RetrieverNetwork = RetrieverNetwork.NEVER,
    provider_id: str | None = None,
    model_id: str | None = None,
    supported_filters: tuple[str, ...] = (),
) -> RetrieverManifest:
    surface = "lex_projection" if name == "lex_projection" else f"surface-{name}"
    return RetrieverManifest(
        name,
        "1",
        surface,
        cost=cost,
        required_capability=required_capability,
        network=network,
        provider_id=provider_id,
        model_id=model_id,
        supported_filters=supported_filters,
    )


class _Port:
    def __init__(self, manifest: RetrieverManifest) -> None:
        self._manifest = manifest
        self.calls = 0

    @property
    def manifest(self) -> RetrieverManifest:
        return self._manifest

    def search(self, query: RetrieverQuery) -> RetrieverCandidateList:
        self.calls += 1
        return RetrieverCandidateList(
            query.fingerprint,
            self._manifest.identity,
            self._manifest.fingerprint,
            self._manifest.surface,
            "index-v1",
            (),
            query.limit,
        )


class _SelfMutatingPort(_Port):
    def search(self, query: RetrieverQuery) -> RetrieverCandidateList:
        self.calls += 1
        original = self._manifest
        object.__setattr__(self._manifest, "surface", "spoofed-live-surface")
        return RetrieverCandidateList(
            query.fingerprint,
            original.identity,
            original.fingerprint,
            original.surface,
            "index-v1",
            (),
            query.limit,
        )


class _CrossMutatingPort(_Port):
    def __init__(self, manifest: RetrieverManifest, target: _Port) -> None:
        super().__init__(manifest)
        self._target = target

    def search(self, query: RetrieverQuery) -> RetrieverCandidateList:
        self.calls += 1
        original = self._manifest
        object.__setattr__(self._target._manifest, "surface", "spoofed-other-surface")
        return RetrieverCandidateList(
            query.fingerprint,
            original.identity,
            original.fingerprint,
            original.surface,
            "index-v1",
            (),
            query.limit,
        )


class _ExceptionPort(_Port):
    def search(self, query: RetrieverQuery) -> RetrieverCandidateList:
        self.calls += 1
        raise RuntimeError("adapter exploded")


class _MalformedPort(_Port):
    def search(self, query: RetrieverQuery) -> RetrieverCandidateList:
        self.calls += 1
        return cast(RetrieverCandidateList, object())


class _ManifestAccessPort:
    def __init__(self) -> None:
        self.manifest_reads = 0

    @property
    def manifest(self) -> RetrieverManifest:
        self.manifest_reads += 1
        raise AssertionError("oversized registry must reject before reading manifests")

    def search(self, query: RetrieverQuery) -> RetrieverCandidateList:
        raise AssertionError("oversized registry must reject before invocation")


def test_exact_registry_limit_is_accepted_and_ordered_without_unbounded_fanout() -> None:
    ports: list[RetrieverPort] = [_Port(_manifest("lex_projection"))]
    ports.extend(
        _Port(_manifest(f"optional-{index:02d}"))
        for index in range(1, MAX_RETRIEVER_REGISTRY_SIZE)
    )

    registry = RetrieverRegistry(ports, RetrieverHostAuthority())
    batch = registry.search(_query(limit=1))

    assert len(registry.manifests) == MAX_RETRIEVER_REGISTRY_SIZE
    assert len(batch.results) == MAX_RETRIEVER_REGISTRY_SIZE
    assert all(len(result.candidates) <= 1 for result in batch.results)
    assert tuple(item.retriever_identity for item in batch.results) == tuple(
        sorted(item.retriever_identity for item in batch.results)
    )


def test_max_plus_one_registry_rejects_before_any_port_manifest_access() -> None:
    ports = [
        _ManifestAccessPort() for _ in range(MAX_RETRIEVER_REGISTRY_SIZE + 1)
    ]

    with pytest.raises(ValueError, match="cannot contain more"):
        RetrieverRegistry(tuple(ports), RetrieverHostAuthority())

    assert all(port.manifest_reads == 0 for port in ports)


def test_invoked_port_manifest_mutation_fails_closed_after_search() -> None:
    baseline = _Port(_manifest("lex_projection", supported_filters=("source",)))
    mutating = _SelfMutatingPort(_manifest("optional"))

    with pytest.raises(RetrieverRegistryError, match="manifest changed"):
        RetrieverRegistry((baseline, mutating), RetrieverHostAuthority()).search(_query())

    assert mutating.calls == 1


def test_non_invoked_port_manifest_mutation_fails_closed_before_batch_publish() -> None:
    target = _Port(_manifest("z-target"))
    mutating_baseline = _CrossMutatingPort(_manifest("lex_projection"), target)

    with pytest.raises(RetrieverRegistryError, match="manifest changed"):
        RetrieverRegistry((mutating_baseline, target), RetrieverHostAuthority()).search(_query())

    assert mutating_baseline.calls == 1
    assert target.calls == 0


def test_search_batch_binds_complete_manifest_snapshot_and_registry_fingerprint() -> None:
    baseline = _Port(_manifest("lex_projection"))
    optional = _Port(
        _manifest(
            "optional",
            required_capability="unavailable-cap",
            cost=RetrieverCost.LOCAL_COMPUTE,
        )
    )
    registry = RetrieverRegistry((optional, baseline), RetrieverHostAuthority())

    batch = registry.search(_query())

    expected_snapshot = tuple((item.identity, item.fingerprint) for item in registry.manifests)
    assert batch.manifest_snapshot == expected_snapshot
    assert batch.registry_fingerprint == registry.fingerprint()
    assert tuple(item.retriever_identity for item in batch.results) == ("lex_projection@1",)
    assert tuple(item.manifest_identity for item in batch.skips) == ("optional@1",)


def test_skip_receipts_are_host_gated_and_identity_ordered() -> None:
    baseline = _Port(_manifest("lex_projection", supported_filters=("source",)))
    network = _Port(
        _manifest(
            "a-network",
            required_capability="network-cap",
            network=RetrieverNetwork.REQUIRED,
        )
    )
    provider = _Port(
        _manifest(
            "b-provider",
            required_capability="provider-cap",
            provider_id="provider-x",
        )
    )
    model = _Port(
        _manifest(
            "c-model",
            required_capability="model-cap",
            model_id="model-x",
        )
    )
    filtered = _Port(_manifest("d-filter"))
    registry = RetrieverRegistry(
        (filtered, model, baseline, provider, network),
        RetrieverHostAuthority(
            capabilities=("network-cap", "provider-cap", "model-cap"),
            network_allowed=False,
        ),
    )

    batch = registry.search(
        _query(filters=(RetrieverFilter("source", ("literal OR 1=1",)),))
    )

    assert tuple(item.manifest_identity for item in batch.skips) == (
        "a-network@1",
        "b-provider@1",
        "c-model@1",
        "d-filter@1",
    )
    assert tuple(item.reason for item in batch.skips) == (
        RetrieverSkipReason.NETWORK_FORBIDDEN,
        RetrieverSkipReason.PROVIDER_UNAVAILABLE,
        RetrieverSkipReason.MODEL_UNAVAILABLE,
        RetrieverSkipReason.UNSUPPORTED_FILTER,
    )
    assert tuple(item.retriever_identity for item in batch.results) == ("lex_projection@1",)
    assert all(port.calls == 0 for port in (network, provider, model, filtered))
    assert baseline.calls == 1


def test_adapter_exception_is_visible_and_not_reclassified_as_optional_skip() -> None:
    baseline = _Port(_manifest("lex_projection"))
    failing = _ExceptionPort(_manifest("failing"))

    with pytest.raises(RuntimeError, match="adapter exploded"):
        RetrieverRegistry((baseline, failing), RetrieverHostAuthority()).search(_query())

    assert failing.calls == 1


def test_malformed_adapter_result_is_rejected_as_a_registry_contract_error() -> None:
    baseline = _Port(_manifest("lex_projection"))
    malformed = _MalformedPort(_manifest("malformed"))

    with pytest.raises(RetrieverRegistryError, match="candidate list"):
        RetrieverRegistry((baseline, malformed), RetrieverHostAuthority()).search(_query())


def test_candidate_list_rejects_limit_overflow_and_non_adjacent_tie_disorder() -> None:
    query = _query(limit=2)
    manifest = _manifest("lex_projection")
    candidates = tuple(
        RetrieverCandidate(
            UnitId(f"unit:sha256:{digest}"),
            None,
            rank,
            score,
            query.fingerprint,
            manifest.identity,
            manifest.fingerprint,
            manifest.surface,
            "index-v1",
        )
        for rank, (digest, score) in enumerate(
            (("f" * 64, 1.0), ("e" * 64, 0.25), ("0" * 64, 1.0)), start=1
        )
    )

    with pytest.raises(ValueError, match="candidate list exceeds"):
        RetrieverCandidateList(
            query.fingerprint,
            manifest.identity,
            manifest.fingerprint,
            manifest.surface,
            "index-v1",
            (*candidates[:2], candidates[2]),
            query.limit,
        )

    with pytest.raises(ValueError, match="equal-score"):
        RetrieverCandidateList(
            query.fingerprint,
            manifest.identity,
            manifest.fingerprint,
            manifest.surface,
            "index-v1",
            candidates,
            MAX_RETRIEVER_LIMIT,
        )
