"""Immutable contracts for revision selection, succession, and lineage.

Selection is reversible and structural: a revision is ``current`` or
``inactive`` because of explicit events, never because of a timestamp or a
recency prior.  Succession is a separate, explicit cross-source relation and
never rewrites or migrates a historical citation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ._validation import JsonObject, require_text
from .identifiers import RevisionId, SourceId, SubstrateId, SubstrateProductionId
from .source import BlobRef, SourceKind


class SelectionStatus(StrEnum):
    """Whether a revision is the source's selected current revision."""

    CURRENT = "current"
    INACTIVE = "inactive"


@dataclass(frozen=True, slots=True)
class RevisionRef:
    """A strict source-bound revision endpoint."""

    source_id: SourceId
    revision_id: RevisionId

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise TypeError("source_id must be SourceId")
        if not isinstance(self.revision_id, RevisionId):
            raise TypeError("revision_id must be RevisionId")

    def to_json(self) -> JsonObject:
        return {"revision_id": str(self.revision_id), "source_id": str(self.source_id)}


@dataclass(frozen=True, slots=True)
class RevisionManifest:
    """The exact v0.2 view of one immutable source revision.

    ``revision_id`` keeps its v0.1 derivation: ADR-0014 adds versioned
    successors rather than mutating persisted contracts, so an existing
    revision identity is never recomputed.  The manifest adds the substrate
    binding that v0.2 needs and states whether that binding came from a
    ``source.substrate_produced@1`` receipt or from the deterministic legacy
    mapping of a v0.1 normalized blob.
    """

    source_id: SourceId
    revision_id: RevisionId
    substrate_id: SubstrateId
    original_blob: BlobRef
    normalization_version: str
    kind: SourceKind
    title: str
    source_role: str
    trust_level: int
    substrate_production_id: SubstrateProductionId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise TypeError("source_id must be SourceId")
        if not isinstance(self.revision_id, RevisionId):
            raise TypeError("revision_id must be RevisionId")
        if not isinstance(self.substrate_id, SubstrateId):
            raise TypeError("substrate_id must be SubstrateId")
        if not isinstance(self.original_blob, BlobRef):
            raise TypeError("original_blob must be BlobRef")
        if str(self.original_blob.id) != f"sha256:{self.original_blob.checksum_sha256}":
            raise ValueError("original_blob id must match its SHA-256 checksum")
        if not isinstance(self.kind, SourceKind):
            raise TypeError("kind must be SourceKind")
        for value, name in (
            (self.normalization_version, "normalization_version"),
            (self.title, "title"),
            (self.source_role, "source_role"),
        ):
            require_text(value, name)
        if type(self.trust_level) is not int or not 0 <= self.trust_level <= 100:
            raise ValueError("trust_level must be an integer between 0 and 100")
        if self.substrate_production_id is not None and not isinstance(
            self.substrate_production_id, SubstrateProductionId
        ):
            raise TypeError("substrate_production_id must be SubstrateProductionId or None")

    @property
    def is_legacy_substrate(self) -> bool:
        """True when the substrate binding came from a v0.1 normalized blob."""
        return self.substrate_production_id is None

    @property
    def ref(self) -> RevisionRef:
        return RevisionRef(self.source_id, self.revision_id)

    def to_json(self) -> JsonObject:
        return {
            "kind": self.kind.value,
            "normalization_version": self.normalization_version,
            "original_blob": {
                "byte_length": self.original_blob.byte_length,
                "checksum_sha256": self.original_blob.checksum_sha256,
                "id": str(self.original_blob.id),
            },
            "revision_id": str(self.revision_id),
            "source_id": str(self.source_id),
            "source_role": self.source_role,
            "substrate_id": str(self.substrate_id),
            "substrate_production_id": (
                None
                if self.substrate_production_id is None
                else str(self.substrate_production_id)
            ),
            "title": self.title,
            "trust_level": self.trust_level,
        }


@dataclass(frozen=True, slots=True)
class SourceSuccession:
    """One explicit, structural succession between two revision endpoints."""

    predecessor: RevisionRef
    successor: RevisionRef
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.predecessor, RevisionRef) or not isinstance(
            self.successor, RevisionRef
        ):
            raise TypeError("succession endpoints must be RevisionRef values")
        require_text(self.reason, "reason")
        if self.predecessor == self.successor:
            raise ValueError("a revision cannot supersede itself")

    def to_json(self) -> JsonObject:
        return {
            "predecessor": self.predecessor.to_json(),
            "reason": self.reason,
            "successor": self.successor.to_json(),
        }


@dataclass(frozen=True, slots=True)
class RevisionLineage:
    """The replayable read view of one revision."""

    manifest: RevisionManifest
    selection_status: SelectionStatus
    successor: RevisionRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, RevisionManifest):
            raise TypeError("manifest must be RevisionManifest")
        if not isinstance(self.selection_status, SelectionStatus):
            raise TypeError("selection_status must be SelectionStatus")
        if self.successor is not None and not isinstance(self.successor, RevisionRef):
            raise TypeError("successor must be RevisionRef or None")

    @property
    def is_current(self) -> bool:
        return self.selection_status is SelectionStatus.CURRENT

    def to_json(self) -> JsonObject:
        return {
            "manifest": self.manifest.to_json(),
            "selection_status": self.selection_status.value,
            "successor": None if self.successor is None else self.successor.to_json(),
        }


@dataclass(frozen=True, slots=True)
class SourceLineage:
    """Every revision of one source in immutable ingestion order."""

    source_id: SourceId
    revisions: tuple[RevisionLineage, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise TypeError("source_id must be SourceId")
        revisions = tuple(self.revisions)
        for revision in revisions:
            if not isinstance(revision, RevisionLineage):
                raise TypeError("revisions must be RevisionLineage values")
            if revision.manifest.source_id != self.source_id:
                raise ValueError("every revision must belong to the lineage source")
        if sum(1 for revision in revisions if revision.is_current) > 1:
            raise ValueError("a source cannot have two current revisions")
        object.__setattr__(self, "revisions", revisions)

    @property
    def current(self) -> RevisionLineage | None:
        for revision in self.revisions:
            if revision.is_current:
                return revision
        return None

    def to_json(self) -> JsonObject:
        return {
            "revisions": tuple(revision.to_json() for revision in self.revisions),
            "source_id": str(self.source_id),
        }


__all__ = [
    "RevisionLineage",
    "RevisionManifest",
    "RevisionRef",
    "SelectionStatus",
    "SourceLineage",
    "SourceSuccession",
]
