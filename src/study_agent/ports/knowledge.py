"""Portable contracts for scope-local lexical knowledge indexes.

The contracts in this module deliberately carry identities and scores only.
Canonical text remains owned by the knowledge/citation layer and is loaded by
an adapter solely while validating an index row.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from typing import Protocol, cast

from study_agent.domain._validation import JsonObject, require_text
from study_agent.domain.identifiers import RevisionId, ScopeId, SourceId, SubstrateId, UnitId
from study_agent.domain.lineage import SelectionStatus
from study_agent.domain.projections import IndexProjection, ProjectionId
from study_agent.domain.units import RetrievableUnit, TextSpan
from study_agent.state.serialization import canonical_json_bytes


class LexicalSurface(StrEnum):
    """The three independently ranked lexical text surfaces."""

    PROJECTION = "projection"
    TERMS = "terms"
    CANONICAL = "canonical"


@dataclass(frozen=True, slots=True)
class LexicalProjectionBinding:
    """One canonical unit and its admitted projection in an explicit scope."""

    scope_id: ScopeId
    projection: IndexProjection
    unit: RetrievableUnit
    substrate_bytes: bytes
    selection_status: SelectionStatus = SelectionStatus.CURRENT
    scope_member: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.scope_id, ScopeId):
            raise TypeError("scope_id must be ScopeId")
        if not isinstance(self.projection, IndexProjection):
            raise TypeError("projection must be IndexProjection")
        if not isinstance(self.unit, RetrievableUnit):
            raise TypeError("unit must be RetrievableUnit")
        if self.projection.unit_id != self.unit.unit_id:
            raise ValueError("projection and unit must identify the same unit")
        if not isinstance(self.substrate_bytes, bytes) or not self.substrate_bytes:
            raise ValueError("substrate_bytes must be non-empty bytes")
        if not isinstance(self.selection_status, SelectionStatus):
            raise TypeError("selection_status must be SelectionStatus")
        if type(self.scope_member) is not bool:
            raise TypeError("scope_member must be a boolean")

    @property
    def projection_id(self) -> ProjectionId:
        """Re-derive the projection identity; never trust an opaque row id."""

        return self.projection.projection_id

    @property
    def unit_id(self) -> UnitId:
        return self.unit.unit_id

    @property
    def source_id(self) -> SourceId:
        return self.unit.source_id

    @property
    def revision_id(self) -> RevisionId:
        return self.unit.revision_id

    @property
    def substrate_id(self) -> SubstrateId:
        reference = self.unit.canonical_ref
        if not isinstance(reference, TextSpan):
            raise ValueError("lexical binding requires a text unit")
        return reference.substrate_id

    @property
    def fingerprint(self) -> str:
        payload = cast(JsonObject, {
            "projection": self.projection.to_json(),
            "scope_id": str(self.scope_id),
            "scope_member": self.scope_member,
            "selection_status": self.selection_status.value,
            "substrate_id": str(self.substrate_id),
            "substrate_sha256": sha256(self.substrate_bytes).hexdigest(),
            "unit": self.unit.to_json(),
        })
        return sha256(
            b"study-agent/lexical-binding/v1\0" + canonical_json_bytes(payload)
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class LexicalQuery:
    """Literal-only search request for one explicit scope and surface."""

    scope_id: ScopeId
    text: str
    surface: LexicalSurface = LexicalSurface.PROJECTION
    limit: int = 8

    def __post_init__(self) -> None:
        if not isinstance(self.scope_id, ScopeId):
            raise TypeError("scope_id must be ScopeId")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("text must be non-empty")
        if "\x00" in self.text:
            raise ValueError("text contains a NUL character")
        if not isinstance(self.surface, LexicalSurface):
            raise TypeError("surface must be LexicalSurface")
        if type(self.limit) is not int or not 1 <= self.limit <= 10_000:
            raise ValueError("limit must be between 1 and 10000")

    @property
    def fingerprint(self) -> str:
        payload = cast(JsonObject, {
            "limit": self.limit,
            "scope_id": str(self.scope_id),
            "surface": self.surface.value,
            "text": self.text,
        })
        return sha256(
            b"study-agent/lexical-query/v1\0" + canonical_json_bytes(payload)
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class LexicalCandidate:
    """A portable lexical hit; it intentionally contains no indexed text."""

    unit_id: UnitId
    projection_id: ProjectionId
    rank: int
    score: float
    query_fingerprint: str = ""
    index_version: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.unit_id, UnitId):
            raise TypeError("unit_id must be UnitId")
        if not isinstance(self.projection_id, ProjectionId):
            raise TypeError("projection_id must be ProjectionId")
        if self.projection_id.unit_id != self.unit_id:
            raise ValueError("projection_id must belong to unit_id")
        if type(self.rank) is not int or self.rank < 1:
            raise ValueError("rank must be a positive integer")
        if isinstance(self.score, bool) or not isinstance(self.score, (float, int)):
            raise TypeError("score must be a real number")
        value = float(self.score)
        if not isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("score must be finite and between zero and one")
        object.__setattr__(self, "score", value)
        if self.query_fingerprint and (
            len(self.query_fingerprint) != 64
            or any(char not in "0123456789abcdef" for char in self.query_fingerprint)
        ):
            raise ValueError("query_fingerprint must be a lowercase SHA-256 digest")
        if self.index_version:
            require_text(self.index_version, "index_version")


@dataclass(frozen=True, slots=True)
class LexicalCandidateList:
    """Deterministic ranked candidates for one query and one surface."""

    surface: LexicalSurface
    query_fingerprint: str
    index_version: str
    candidates: tuple[LexicalCandidate, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.surface, LexicalSurface):
            raise TypeError("surface must be LexicalSurface")
        for value, name in (
            (self.query_fingerprint, "query_fingerprint"),
            (self.index_version, "index_version"),
        ):
            require_text(value, name)
        if len(self.query_fingerprint) != 64 or any(
            char not in "0123456789abcdef" for char in self.query_fingerprint
        ):
            raise ValueError("query_fingerprint must be a lowercase SHA-256 digest")
        values = tuple(self.candidates)
        if len({item.unit_id for item in values}) != len(values):
            raise ValueError("candidates must not repeat unit ids")
        if tuple(item.rank for item in values) != tuple(range(1, len(values) + 1)):
            raise ValueError("candidate ranks must be contiguous and one-based")
        for item in values:
            if item.query_fingerprint and item.query_fingerprint != self.query_fingerprint:
                raise ValueError("candidate query fingerprint does not match the result")
            if item.index_version and item.index_version != self.index_version:
                raise ValueError("candidate index version does not match the result")
        object.__setattr__(self, "candidates", values)


@dataclass(frozen=True, slots=True)
class LexicalIndexReceipt:
    """Portable receipt for a complete derived lexical generation."""

    indexed_bindings: int
    index_version: str
    catalog_fingerprint: str

    def __post_init__(self) -> None:
        if type(self.indexed_bindings) is not int or self.indexed_bindings < 0:
            raise ValueError("indexed_bindings must be non-negative")
        require_text(self.index_version, "index_version")
        if len(self.catalog_fingerprint) != 64 or any(
            char not in "0123456789abcdef" for char in self.catalog_fingerprint
        ):
            raise ValueError("catalog_fingerprint must be a lowercase SHA-256 digest")


class LexicalCatalogPort(Protocol):
    """Canonical source of complete, active scope bindings."""

    def bindings(self, scope_id: ScopeId) -> Sequence[LexicalProjectionBinding]: ...


class LexicalIndexPort(Protocol):
    def index(
        self, bindings: Sequence[LexicalProjectionBinding]
    ) -> LexicalIndexReceipt: ...

    def rebuild(
        self, bindings: Sequence[LexicalProjectionBinding]
    ) -> LexicalIndexReceipt: ...

    def search(self, query: LexicalQuery) -> LexicalCandidateList: ...


__all__ = [
    "LexicalCandidate",
    "LexicalCandidateList",
    "LexicalCatalogPort",
    "LexicalIndexPort",
    "LexicalIndexReceipt",
    "LexicalProjectionBinding",
    "LexicalQuery",
    "LexicalSurface",
]
