"""Agent-neutral evidence contracts backed by canonical citations only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .citation_v2 import TextCitationV2
from .identifiers import ScopeId, UnitId
from .lineage import RevisionRef, SelectionStatus
from .projections import ProjectionId

MAX_EVIDENCE_ROWS = 256
MAX_EVIDENCE_EXPANSIONS = 32
MAX_EVIDENCE_TEXT = 200_000


class EvidencePacketStatus(StrEnum):
    READY = "ready"
    INSUFFICIENT = "insufficient"


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or not value.strip() or "\x00" in value:
        raise ValueError(f"{field} must be non-empty text without NUL")
    if len(value) > MAX_EVIDENCE_TEXT:
        raise ValueError(f"{field} exceeds the evidence text bound")
    return value


@dataclass(frozen=True, slots=True)
class EvidenceExpansion:
    """A separately cited context attachment; never a replacement for primary evidence."""

    relation: str
    citation: TextCitationV2
    canonical_text: str
    selection_status: SelectionStatus
    successor: RevisionRef | None = None

    def __post_init__(self) -> None:
        if self.relation not in {"parent", "sibling", "window"}:
            raise ValueError("evidence expansion relation is unsupported")
        if not isinstance(self.citation, TextCitationV2):
            raise TypeError("evidence expansion requires TextCitationV2")
        _text(self.canonical_text, "canonical_text")
        if not isinstance(self.selection_status, SelectionStatus):
            raise TypeError("selection_status must be SelectionStatus")
        if self.successor is not None and not isinstance(self.successor, RevisionRef):
            raise TypeError("successor must be RevisionRef or None")


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    """One narrow, verified source span with discovery provenance."""

    unit_id: UnitId
    projection_id: ProjectionId
    citation: TextCitationV2
    canonical_text: str
    selection_status: SelectionStatus
    score: float
    retriever_provenance: tuple[str, ...]
    projector_name: str
    projector_version: str
    expansions: tuple[EvidenceExpansion, ...] = ()
    successor: RevisionRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.unit_id, UnitId) or not isinstance(self.projection_id, ProjectionId):
            raise TypeError("evidence row requires typed unit and projection identities")
        if self.projection_id.unit_id != self.unit_id or self.citation.unit_id != self.unit_id:
            raise ValueError("evidence identities must belong to the primary unit")
        if not isinstance(self.citation, TextCitationV2):
            raise TypeError("evidence rows require TextCitationV2")
        _text(self.canonical_text, "canonical_text")
        if not isinstance(self.selection_status, SelectionStatus):
            raise TypeError("selection_status must be SelectionStatus")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise TypeError("score must be a real number")
        if not isfinite(float(self.score)):
            raise ValueError("score must be finite")
        object.__setattr__(self, "score", float(self.score))
        provenance = tuple(self.retriever_provenance)
        if not provenance or len(provenance) != len(set(provenance)):
            raise ValueError("retriever_provenance must be non-empty and unique")
        if any(not isinstance(item, str) or not item for item in provenance):
            raise TypeError("retriever_provenance must contain non-empty text")
        object.__setattr__(self, "retriever_provenance", tuple(sorted(provenance)))
        _text(self.projector_name, "projector_name")
        _text(self.projector_version, "projector_version")
        expansions = tuple(self.expansions)
        if len(expansions) > MAX_EVIDENCE_EXPANSIONS or any(
            not isinstance(item, EvidenceExpansion) for item in expansions
        ):
            raise ValueError("evidence expansions are invalid or exceed the bound")
        object.__setattr__(self, "expansions", expansions)
        if self.successor is not None and not isinstance(self.successor, RevisionRef):
            raise TypeError("successor must be RevisionRef or None")


@dataclass(frozen=True, slots=True)
class EvidencePacket:
    """A bounded retrieval response, intentionally without generated claims."""

    scope_id: ScopeId
    query: str
    status: EvidencePacketStatus
    registry_fingerprint: str
    rows: tuple[EvidenceRow, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope_id, ScopeId):
            raise TypeError("scope_id must be ScopeId")
        _text(self.query, "query")
        if not isinstance(self.status, EvidencePacketStatus):
            raise TypeError("status must be EvidencePacketStatus")
        if len(self.registry_fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in self.registry_fingerprint
        ):
            raise ValueError("registry_fingerprint must be a SHA-256 digest")
        rows = tuple(self.rows)
        if len(rows) > MAX_EVIDENCE_ROWS or any(not isinstance(item, EvidenceRow) for item in rows):
            raise ValueError("rows are invalid or exceed the evidence bound")
        # Packet order is relevance order, so duplicate identities are the only
        # ordering-related invariant at this boundary.
        if len({row.unit_id for row in rows}) != len(rows):
            raise ValueError("evidence rows must have unique unit identities")
        object.__setattr__(self, "rows", rows)
        if self.status is EvidencePacketStatus.READY and not rows:
            raise ValueError("ready evidence packets require rows")
        if self.status is EvidencePacketStatus.INSUFFICIENT and rows:
            raise ValueError("insufficient evidence packets cannot contain rows")
        if self.reason is not None:
            _text(self.reason, "reason")


__all__ = [
    "MAX_EVIDENCE_EXPANSIONS",
    "MAX_EVIDENCE_ROWS",
    "EvidenceExpansion",
    "EvidencePacket",
    "EvidencePacketStatus",
    "EvidenceRow",
]
