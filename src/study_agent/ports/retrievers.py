"""Provider-neutral contracts for bounded knowledge-base retrievers.

The contracts in this module are deliberately narrower than the older source
retrieval API.  A retriever returns identities and adapter-local scores only;
canonical text, citations, and evidence remain owned by later layers.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from itertools import pairwise
from math import isfinite
from typing import Protocol

from study_agent.domain._validation import JsonObject, require_text
from study_agent.domain.identifiers import ScopeId, UnitId
from study_agent.domain.projections import ProjectionId
from study_agent.state.serialization import canonical_json_bytes

MAX_RETRIEVER_IDENTITY_LENGTH = 128
MAX_RETRIEVER_SURFACE_LENGTH = 128
MAX_RETRIEVER_CAPABILITY_LENGTH = 128
MAX_RETRIEVER_PROVIDER_LENGTH = 128
MAX_RETRIEVER_MODEL_LENGTH = 128
MAX_RETRIEVER_FILTER_NAME_LENGTH = 128
MAX_RETRIEVER_FILTER_VALUE_LENGTH = 256
MAX_RETRIEVER_FILTERS = 32
MAX_RETRIEVER_FILTER_VALUES = 64
MAX_RETRIEVER_QUERY_LENGTH = 16_384
MAX_RETRIEVER_LIMIT = 1_000
MAX_RETRIEVER_CANDIDATES = 1_000

_IDENTITY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]*$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class RetrieverCost(StrEnum):
    FREE = "free"
    LOCAL_COMPUTE = "local_compute"
    METERED = "metered"


class RetrieverNetwork(StrEnum):
    NEVER = "never"
    REQUIRED = "required"


class RetrieverSkipReason(StrEnum):
    MISSING_CAPABILITY = "missing_capability"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MODEL_UNAVAILABLE = "model_unavailable"
    NETWORK_FORBIDDEN = "network_forbidden"
    UNSUPPORTED_FILTER = "unsupported_filter"


# ``RetrieverSkipCode`` is a readable compatibility alias for callers that
# prefer the word used in the registry's structured receipt.
RetrieverSkipCode = RetrieverSkipReason


def _text(value: str, name: str, limit: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    require_text(value, name)
    if len(value) > limit or "\x00" in value:
        raise ValueError(f"{name} must be at most {limit} characters and contain no NUL")
    return value


def _identity(value: str, name: str, *, version: bool = False) -> str:
    value = _text(value, name, MAX_RETRIEVER_IDENTITY_LENGTH)
    if (_VERSION if version else _IDENTITY).fullmatch(value) is None:
        raise ValueError(f"{name} is not a portable identity")
    return value


def _digest(value: str, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 fingerprint")


def _retriever_identity(value: str, name: str = "retriever_identity") -> str:
    value = _text(value, name, MAX_RETRIEVER_IDENTITY_LENGTH)
    parts = value.split("@")
    if len(parts) != 2:
        raise ValueError(f"{name} must be name@version")
    _identity(parts[0], f"{name} name")
    _identity(parts[1], f"{name} version", version=True)
    return value


def _canonical_unique(
    values: Sequence[str], name: str, limit: int, value_limit: int
) -> tuple[str, ...]:
    normalized = tuple(_text(value, f"{name} item", value_limit) for value in values)
    if len(normalized) > limit or len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must contain at most {limit} unique values")
    return tuple(sorted(normalized))


@dataclass(frozen=True, slots=True)
class RetrieverManifest:
    """Immutable declaration of one registered retriever surface."""

    name: str
    version: str
    surface: str
    cost: RetrieverCost = RetrieverCost.FREE
    required_capability: str | None = None
    default_weight: float = 1.0
    network: RetrieverNetwork = RetrieverNetwork.NEVER
    provider_id: str | None = None
    model_id: str | None = None
    supported_filters: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identity(self.name, "name")
        _identity(self.version, "version", version=True)
        _text(self.surface, "surface", MAX_RETRIEVER_SURFACE_LENGTH)
        if not isinstance(self.cost, RetrieverCost):
            raise TypeError("cost must be RetrieverCost")
        if self.required_capability is not None:
            _text(self.required_capability, "required_capability", MAX_RETRIEVER_CAPABILITY_LENGTH)
        if isinstance(self.default_weight, bool) or not isinstance(
            self.default_weight, (int, float)
        ):
            raise TypeError("default_weight must be a finite number")
        weight = float(self.default_weight)
        if not isfinite(weight) or not 0.0 < weight <= 100.0:
            raise ValueError("default_weight must be finite and between 0 and 100")
        object.__setattr__(self, "default_weight", weight)
        if not isinstance(self.network, RetrieverNetwork):
            raise TypeError("network must be RetrieverNetwork")
        if self.provider_id is not None:
            _text(self.provider_id, "provider_id", MAX_RETRIEVER_PROVIDER_LENGTH)
        if self.model_id is not None:
            _text(self.model_id, "model_id", MAX_RETRIEVER_MODEL_LENGTH)
        filters = _canonical_unique(
            self.supported_filters,
            "supported_filters",
            MAX_RETRIEVER_FILTERS,
            MAX_RETRIEVER_FILTER_NAME_LENGTH,
        )
        object.__setattr__(self, "supported_filters", filters)
        requires_gate = (
            self.cost is RetrieverCost.METERED
            or self.network is RetrieverNetwork.REQUIRED
            or self.provider_id is not None
            or self.model_id is not None
        )
        if requires_gate and self.required_capability is None:
            raise ValueError(
                "metered, network, provider, or model retrievers require a capability gate"
            )

    @property
    def identity(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def manifest_identity(self) -> str:
        return self.identity

    @property
    def network_requirement(self) -> RetrieverNetwork:
        return self.network

    def to_json(self) -> JsonObject:
        return {
            "cost": self.cost.value,
            "default_weight": self.default_weight,
            "model_id": self.model_id,
            "name": self.name,
            "network": self.network.value,
            "provider_id": self.provider_id,
            "required_capability": self.required_capability,
            "supported_filters": self.supported_filters,
            "surface": self.surface,
            "version": self.version,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @property
    def fingerprint(self) -> str:
        return sha256(b"study-agent/retriever-manifest/v1\0" + self.to_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class RetrieverHostAuthority:
    """Trusted host capabilities used to decide which ports may run."""

    capabilities: tuple[str, ...] = ()
    provider_ids: tuple[str, ...] = ()
    model_ids: tuple[str, ...] = ()
    network_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "capabilities",
            _canonical_unique(
                self.capabilities,
                "capabilities",
                MAX_RETRIEVER_FILTERS,
                MAX_RETRIEVER_CAPABILITY_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "provider_ids",
            _canonical_unique(
                self.provider_ids,
                "provider_ids",
                MAX_RETRIEVER_FILTERS,
                MAX_RETRIEVER_PROVIDER_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "model_ids",
            _canonical_unique(
                self.model_ids, "model_ids", MAX_RETRIEVER_FILTERS, MAX_RETRIEVER_MODEL_LENGTH
            ),
        )
        if type(self.network_allowed) is not bool:
            raise TypeError("network_allowed must be a boolean")

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return self.capabilities

    def to_json(self) -> JsonObject:
        return {
            "capabilities": self.capabilities,
            "model_ids": self.model_ids,
            "network_allowed": self.network_allowed,
            "provider_ids": self.provider_ids,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @property
    def fingerprint(self) -> str:
        return sha256(b"study-agent/retriever-host-authority/v1\0" + self.to_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class RetrieverFilter:
    name: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        _identity(self.name, "filter name")
        values = _canonical_unique(
            self.values,
            "filter values",
            MAX_RETRIEVER_FILTER_VALUES,
            MAX_RETRIEVER_FILTER_VALUE_LENGTH,
        )
        if not values:
            raise ValueError("filter values must be non-empty")
        object.__setattr__(self, "values", values)

    def to_json(self) -> JsonObject:
        return {"name": self.name, "values": self.values}


@dataclass(frozen=True, slots=True)
class RetrieverQuery:
    scope_id: ScopeId
    text: str
    limit: int = 8
    filters: tuple[RetrieverFilter, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scope_id, ScopeId):
            raise TypeError("scope_id must be ScopeId")
        self_text = _text(self.text, "query text", MAX_RETRIEVER_QUERY_LENGTH)
        if not self_text.strip():
            raise ValueError("query text must be non-empty")
        if type(self.limit) is not int or not 1 <= self.limit <= MAX_RETRIEVER_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_RETRIEVER_LIMIT}")
        filters = tuple(self.filters)
        if any(not isinstance(item, RetrieverFilter) for item in filters):
            raise TypeError("filters must contain RetrieverFilter values")
        if len(filters) > MAX_RETRIEVER_FILTERS or len({item.name for item in filters}) != len(
            filters
        ):
            raise ValueError("filters must contain unique bounded names")
        object.__setattr__(self, "filters", tuple(sorted(filters, key=lambda item: item.name)))

    @property
    def fingerprint(self) -> str:
        payload: JsonObject = {
            "filters": tuple(item.to_json() for item in self.filters),
            "limit": self.limit,
            "scope_id": str(self.scope_id),
            "text": self.text,
        }
        return sha256(
            b"study-agent/retriever-query/v1\0" + canonical_json_bytes(payload)
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class RetrieverCandidate:
    unit_id: UnitId
    projection_id: ProjectionId | None
    rank: int
    score: float
    query_fingerprint: str
    retriever_identity: str
    manifest_fingerprint: str
    surface: str
    index_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.unit_id, UnitId):
            raise TypeError("unit_id must be UnitId")
        if self.projection_id is not None:
            if not isinstance(self.projection_id, ProjectionId):
                raise TypeError("projection_id must be ProjectionId or None")
            if self.projection_id.unit_id != self.unit_id:
                raise ValueError("projection_id must belong to unit_id")
        if type(self.rank) is not int or self.rank < 1:
            raise ValueError("rank must be a positive integer")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise TypeError("score must be a real number")
        score = float(self.score)
        if not isfinite(score):
            raise ValueError("score must be finite")
        object.__setattr__(self, "score", score)
        _digest(self.query_fingerprint, "query_fingerprint")
        _retriever_identity(self.retriever_identity)
        _digest(self.manifest_fingerprint, "manifest_fingerprint")
        _text(self.surface, "surface", MAX_RETRIEVER_SURFACE_LENGTH)
        _text(self.index_version, "index_version", MAX_RETRIEVER_IDENTITY_LENGTH)

    @property
    def retriever_id(self) -> str:
        return self.retriever_identity


@dataclass(frozen=True, slots=True)
class RetrieverCandidateList:
    query_fingerprint: str
    retriever_identity: str
    manifest_fingerprint: str
    surface: str
    index_version: str
    candidates: tuple[RetrieverCandidate, ...] = ()
    limit: int = MAX_RETRIEVER_LIMIT

    def __post_init__(self) -> None:
        _digest(self.query_fingerprint, "query_fingerprint")
        _retriever_identity(self.retriever_identity)
        _digest(self.manifest_fingerprint, "manifest_fingerprint")
        _text(self.surface, "surface", MAX_RETRIEVER_SURFACE_LENGTH)
        _text(self.index_version, "index_version", MAX_RETRIEVER_IDENTITY_LENGTH)
        if type(self.limit) is not int or not 1 <= self.limit <= MAX_RETRIEVER_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_RETRIEVER_LIMIT}")
        values = tuple(self.candidates)
        if len(values) > self.limit or len(values) > MAX_RETRIEVER_CANDIDATES:
            raise ValueError("candidate list exceeds the query limit")
        if len({item.unit_id for item in values}) != len(values):
            raise ValueError("candidate units must be unique")
        if tuple(item.rank for item in values) != tuple(range(1, len(values) + 1)):
            raise ValueError("candidate ranks must be contiguous and one-based")
        for item in values:
            if (
                item.query_fingerprint != self.query_fingerprint
                or item.retriever_identity != self.retriever_identity
                or item.manifest_fingerprint != self.manifest_fingerprint
                or item.surface != self.surface
                or item.index_version != self.index_version
            ):
                raise ValueError("candidate provenance does not match the candidate list")
        for left, right in pairwise(values):
            if left.score == right.score and _candidate_key(left) > _candidate_key(right):
                raise ValueError("equal-score candidates must use canonical identity ordering")
        object.__setattr__(self, "candidates", values)

    @property
    def retriever_id(self) -> str:
        return self.retriever_identity


def _candidate_key(candidate: RetrieverCandidate) -> tuple[str, str]:
    return (str(candidate.unit_id), str(candidate.projection_id) if candidate.projection_id else "")


class RetrieverPort(Protocol):
    @property
    def manifest(self) -> RetrieverManifest: ...

    def search(self, query: RetrieverQuery) -> RetrieverCandidateList: ...


@dataclass(frozen=True, slots=True)
class RetrieverSkipReceipt:
    manifest_identity: str
    manifest_fingerprint: str
    reason: RetrieverSkipReason

    def __post_init__(self) -> None:
        _retriever_identity(self.manifest_identity, "manifest_identity")
        _digest(self.manifest_fingerprint, "manifest_fingerprint")
        if not isinstance(self.reason, RetrieverSkipReason):
            raise TypeError("reason must be RetrieverSkipReason")

    @property
    def retriever_identity(self) -> str:
        return self.manifest_identity


@dataclass(frozen=True, slots=True)
class RetrieverSearchBatch:
    query: RetrieverQuery
    host_fingerprint: str
    results: tuple[RetrieverCandidateList, ...] = ()
    skips: tuple[RetrieverSkipReceipt, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.query, RetrieverQuery):
            raise TypeError("query must be RetrieverQuery")
        _digest(self.host_fingerprint, "host_fingerprint")
        results = tuple(self.results)
        skips = tuple(self.skips)
        if any(not isinstance(item, RetrieverCandidateList) for item in results):
            raise TypeError("results must contain RetrieverCandidateList values")
        if any(not isinstance(item, RetrieverSkipReceipt) for item in skips):
            raise TypeError("skips must contain RetrieverSkipReceipt values")
        result_ids = tuple(item.retriever_identity for item in results)
        skip_ids = tuple(item.manifest_identity for item in skips)
        if len(set(result_ids)) != len(result_ids) or len(set(skip_ids)) != len(skip_ids):
            raise ValueError("retriever results and skips must be unique")
        if set(result_ids) & set(skip_ids):
            raise ValueError("a retriever cannot both run and be skipped")
        if result_ids != tuple(sorted(result_ids)) or skip_ids != tuple(sorted(skip_ids)):
            raise ValueError("results and skips must be in manifest identity order")
        if any(item.query_fingerprint != self.query.fingerprint for item in results):
            raise ValueError("result query provenance does not match the batch query")
        object.__setattr__(self, "results", results)
        object.__setattr__(self, "skips", skips)

    @property
    def candidate_lists(self) -> tuple[RetrieverCandidateList, ...]:
        return self.results

    @property
    def skipped(self) -> tuple[RetrieverSkipReceipt, ...]:
        return self.skips


__all__ = [
    "MAX_RETRIEVER_CANDIDATES",
    "MAX_RETRIEVER_LIMIT",
    "MAX_RETRIEVER_QUERY_LENGTH",
    "RetrieverCandidate",
    "RetrieverCandidateList",
    "RetrieverCost",
    "RetrieverFilter",
    "RetrieverHostAuthority",
    "RetrieverManifest",
    "RetrieverNetwork",
    "RetrieverPort",
    "RetrieverQuery",
    "RetrieverSearchBatch",
    "RetrieverSkipCode",
    "RetrieverSkipReason",
    "RetrieverSkipReceipt",
]
