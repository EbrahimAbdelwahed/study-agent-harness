"""Provider-neutral contracts for typed canonical fragment promotion.

Fragments are authored structural regions, not model output.  They retain the
same substrate, revision, source, node, span, and uncertainty flags as the
tree region from which they came.  Promotion is intentionally represented as
an inspectable decision separate from canonical unit identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from ._validation import JsonObject, require_text
from .identifiers import NodeId, RevisionId, SourceId, SubstrateId

_MAX_PATH_SEGMENTS = 32
_MAX_FLAGS = 32
_MAX_FLAG_LENGTH = 128


class FragmentKind(StrEnum):
    """Closed set of generic, connector-independent fragment kinds."""

    EMPHASIS = "emphasis"
    SUMMARY = "summary"
    DEFINITION = "definition"
    TABLE = "table"
    ITEM = "item"


@dataclass(frozen=True, slots=True)
class FragmentDraft:
    """One identity-free fragment occurrence derived from a tree region."""

    kind: FragmentKind
    substrate_id: SubstrateId
    source_id: SourceId
    revision_id: RevisionId
    node_id: NodeId
    parent_node_id: NodeId | None
    structural_path: tuple[str, ...]
    span: tuple[int, int]
    flags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, FragmentKind):
            raise TypeError("fragment kind must be FragmentKind")
        for value, name, expected in (
            (self.substrate_id, "substrate_id", SubstrateId),
            (self.source_id, "source_id", SourceId),
            (self.revision_id, "revision_id", RevisionId),
            (self.node_id, "node_id", NodeId),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"fragment {name} must be {expected.__name__}")
        if self.parent_node_id is not None and not isinstance(self.parent_node_id, NodeId):
            raise TypeError("fragment parent_node_id must be NodeId or None")
        if self.parent_node_id == self.node_id:
            raise ValueError("fragment cannot be its own parent")
        path = tuple(self.structural_path)
        if not path or len(path) > _MAX_PATH_SEGMENTS:
            raise ValueError("fragment structural_path has an invalid bounded length")
        for segment in path:
            if not isinstance(segment, str):
                raise TypeError("fragment path segments must be strings")
            require_text(segment, "fragment path segment")
        object.__setattr__(self, "structural_path", path)
        span = tuple(self.span)
        if len(span) != 2 or any(type(value) is not int for value in span):
            raise ValueError("fragment span must be a pair of integers")
        start, end = span
        if start < 0 or end <= start:
            raise ValueError("fragment span must be a non-empty forward range")
        object.__setattr__(self, "span", (start, end))
        flags = frozenset(self.flags)
        if len(flags) > _MAX_FLAGS:
            raise ValueError(f"fragment flags must contain at most {_MAX_FLAGS} entries")
        for flag in flags:
            if not isinstance(flag, str):
                raise TypeError("fragment flags must be strings")
            if not flag or len(flag) > _MAX_FLAG_LENGTH or flag != flag.strip():
                raise ValueError("fragment flags must be bounded non-empty text")
        object.__setattr__(self, "flags", flags)

    @property
    def length(self) -> int:
        return self.span[1] - self.span[0]

    def to_json(self) -> JsonObject:
        return {
            "flags": tuple(sorted(self.flags)),
            "kind": self.kind.value,
            "node_id": str(self.node_id),
            "parent_node_id": None if self.parent_node_id is None else str(self.parent_node_id),
            "revision_id": str(self.revision_id),
            "source_id": str(self.source_id),
            "span": (self.span[0], self.span[1]),
            "structural_path": self.structural_path,
            "substrate_id": str(self.substrate_id),
        }


def _signal(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    normalized = float(value)
    if not isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return normalized


@dataclass(frozen=True, slots=True)
class FragmentSignals:
    """The four independently observable, normalized promotion signals."""

    minimum_length: float
    structural_weight: float
    corpus_rarity: float
    reference_signal: float

    def __post_init__(self) -> None:
        for value, name in (
            (self.minimum_length, "minimum_length"),
            (self.structural_weight, "structural_weight"),
            (self.corpus_rarity, "corpus_rarity"),
            (self.reference_signal, "reference_signal"),
        ):
            object.__setattr__(self, name, _signal(value, name))

    def to_json(self) -> JsonObject:
        return {
            "corpus_rarity": self.corpus_rarity,
            "minimum_length": self.minimum_length,
            "reference_signal": self.reference_signal,
            "structural_weight": self.structural_weight,
        }


@dataclass(frozen=True, slots=True)
class SignalContribution:
    """One normalized signal and its policy-weighted contribution."""

    name: str
    signal: float
    weight: float
    contribution: float

    def __post_init__(self) -> None:
        require_text(self.name, "signal name")
        object.__setattr__(self, "signal", _signal(self.signal, "signal"))
        object.__setattr__(self, "weight", _signal(self.weight, "weight"))
        value = float(self.contribution)
        if not isfinite(value) or value < 0.0 or value > 1.0:
            raise ValueError("signal contribution must be finite and between 0 and 1")
        object.__setattr__(self, "contribution", value)

    def to_json(self) -> JsonObject:
        return {
            "contribution": self.contribution,
            "name": self.name,
            "signal": self.signal,
            "weight": self.weight,
        }


@dataclass(frozen=True, slots=True)
class FragmentPromotionDecision:
    """Deterministic, explainable outcome for one fragment occurrence."""

    fragment: FragmentDraft
    signals: FragmentSignals
    contributions: tuple[SignalContribution, ...]
    total_score: float
    threshold: float
    promoted: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.fragment, FragmentDraft):
            raise TypeError("decision fragment must be FragmentDraft")
        if not isinstance(self.signals, FragmentSignals):
            raise TypeError("decision signals must be FragmentSignals")
        contributions = tuple(self.contributions)
        if len(contributions) != 4:
            raise ValueError("a promotion decision must expose four contributions")
        if len({entry.name for entry in contributions}) != 4:
            raise ValueError("promotion contribution names must be unique")
        object.__setattr__(self, "contributions", contributions)
        for value, name in ((self.total_score, "total_score"), (self.threshold, "threshold")):
            object.__setattr__(self, name, _signal(value, name))
        if not isinstance(self.promoted, bool):
            raise TypeError("promoted must be boolean")
        require_text(self.reason, "promotion reason")

    def to_json(self) -> JsonObject:
        return {
            "contributions": tuple(entry.to_json() for entry in self.contributions),
            "fragment": self.fragment.to_json(),
            "promoted": self.promoted,
            "reason": self.reason,
            "signals": self.signals.to_json(),
            "threshold": self.threshold,
            "total_score": self.total_score,
        }


__all__ = [
    "FragmentDraft",
    "FragmentKind",
    "FragmentPromotionDecision",
    "FragmentSignals",
    "SignalContribution",
]
