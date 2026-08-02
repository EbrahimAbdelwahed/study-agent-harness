"""Deterministic typed-fragment extraction and promotion.

This module is deliberately a pure projection.  It accepts only the admitted
tree context owned by KB-08, never tokenizes text, and never calls a model or
creates a unit identity. Materialization is delegated to
:func:`unitize_drafts`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil, isfinite

from study_agent.domain.fragments import (
    FragmentDraft,
    FragmentKind,
    FragmentPromotionDecision,
    FragmentSignals,
    SignalContribution,
)
from study_agent.domain.identifiers import NodeId, RevisionId, SourceId
from study_agent.domain.tree import DocumentTree, RegionKind
from study_agent.domain.units import RetrievableUnit, UnitKind, UnitMeta

from .tree import AdmittedDocumentTree
from .unitizer import UnitDraft, UnitizerPolicy, draft_units, unitize_drafts
from .units import RevisionBinding

MAX_CANONICAL_TEXT = 8_000_000
MAX_FRAGMENTS = 4_096
MAX_SCORE_VALUES = 4_096

_REGION_TO_FRAGMENT: dict[str, FragmentKind] = {
    RegionKind.EMPHASIS.value: FragmentKind.EMPHASIS,
    RegionKind.SUMMARY.value: FragmentKind.SUMMARY,
    RegionKind.TABLE.value: FragmentKind.TABLE,
    RegionKind.ITEM.value: FragmentKind.ITEM,
    # KB-07 is forward-compatible with the definition region added by a
    # connector profile without making older trees depend on that enum value.
    "definition": FragmentKind.DEFINITION,
}
_FRAGMENT_TO_UNIT: dict[FragmentKind, UnitKind] = {
    FragmentKind.EMPHASIS: UnitKind.EMPHASIS,
    FragmentKind.SUMMARY: UnitKind.SUMMARY,
    FragmentKind.DEFINITION: UnitKind.DEFINITION,
    FragmentKind.TABLE: UnitKind.TABLE,
    FragmentKind.ITEM: UnitKind.ITEM,
}


def _bounded_text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("fragment extraction requires canonical text")
    if not value or len(value) > MAX_CANONICAL_TEXT:
        raise ValueError("canonical fragment text is empty or exceeds the bound")
    return value


def _tree_context(context: AdmittedDocumentTree) -> tuple[DocumentTree, str]:
    """Resolve the sole trusted tree/text context."""
    if not isinstance(context, AdmittedDocumentTree):
        raise TypeError("fragment extraction requires an admitted document tree")
    return context.tree, _bounded_text(context.text)


def _ancestor_flags(tree: DocumentTree) -> dict[object, frozenset[str]]:
    by_id = {node.node_id: node for node in tree.nodes}
    result: dict[object, frozenset[str]] = {}
    for node in tree.nodes:
        flags = set(node.flags)
        parent = node.parent_id
        seen: set[object] = set()
        while parent is not None:
            if parent in seen:
                raise ValueError("tree ancestor chain is cyclic")
            seen.add(parent)
            ancestor = by_id.get(parent)
            if ancestor is None:
                raise ValueError("tree node references an unknown ancestor")
            flags.update(ancestor.flags)
            parent = ancestor.parent_id
        result[node.node_id] = frozenset(flags)
    return result


def draft_fragments(
    context: AdmittedDocumentTree,
    *,
    source_id: SourceId,
    revision_id: RevisionId,
    max_fragments: int = MAX_FRAGMENTS,
) -> tuple[FragmentDraft, ...]:
    """Extract exact typed regions from an admitted canonical tree context."""
    if not isinstance(source_id, SourceId):
        raise TypeError("source_id must be SourceId")
    if not isinstance(revision_id, RevisionId):
        raise TypeError("revision_id must be RevisionId")
    if type(max_fragments) is not int or not 1 <= max_fragments <= MAX_FRAGMENTS:
        raise ValueError(f"max_fragments must be between 1 and {MAX_FRAGMENTS}")
    tree, canonical_text = _tree_context(context)
    flags_by_node = _ancestor_flags(tree)
    fragments: list[FragmentDraft] = []
    for node in tree.nodes:
        kind = _REGION_TO_FRAGMENT.get(node.region_kind.value)
        if kind is None:
            continue
        start, end = node.span
        if start < 0 or end > len(canonical_text) or end <= start:
            raise ValueError("tree fragment span escapes canonical text")
        if not canonical_text[start:end]:
            raise ValueError("tree fragment span has no canonical content")
        fragments.append(
            FragmentDraft(
                kind,
                tree.substrate_id,
                source_id,
                revision_id,
                node.node_id,
                node.parent_id,
                node.path,
                node.span,
                flags_by_node[node.node_id],
            )
        )
        if len(fragments) > max_fragments:
            raise ValueError("tree contains more fragments than the configured bound")
    return tuple(fragments)


def _raw_scores(values: Sequence[float], name: str) -> tuple[float, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence of finite real numbers")
    entries = tuple(values)
    if len(entries) > MAX_SCORE_VALUES:
        raise ValueError(f"{name} is too large")
    result: list[float] = []
    for value in entries:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must contain real numbers")
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must contain finite non-negative values")
        result.append(normalized)
    return tuple(result)


def _quantile(values: tuple[float, ...], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = tuple(sorted(values))
    index = max(0, min(len(ordered) - 1, ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def _reference(value: bool | float) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if not isinstance(value, (int, float)) or not isfinite(float(value)):
        raise ValueError("reference_signal must be a finite boolean or number")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError("reference_signal must be between 0 and 1")
    return normalized


@dataclass(frozen=True, slots=True)
class FragmentPromotionPolicy:
    """Immutable, bounded, per-scope model-free promotion policy."""

    version: str = "fragment-policy-v1"
    minimum_length: int = 24
    idf_percentile: float = 0.90
    length_weight: float = 0.25
    structural_weight: float = 0.25
    rarity_weight: float = 0.25
    reference_weight: float = 0.25
    threshold: float = 0.50
    structural_weights: tuple[tuple[FragmentKind, float], ...] = (
        (FragmentKind.EMPHASIS, 1.0),
        (FragmentKind.SUMMARY, 0.90),
        (FragmentKind.DEFINITION, 1.0),
        (FragmentKind.TABLE, 0.85),
        (FragmentKind.ITEM, 0.70),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("policy version must be non-empty text")
        if type(self.minimum_length) is not int or not 1 <= self.minimum_length <= 32_768:
            raise ValueError("minimum_length is outside its bound")
        for value, name in (
            (self.idf_percentile, "idf_percentile"),
            (self.length_weight, "length_weight"),
            (self.structural_weight, "structural_weight"),
            (self.rarity_weight, "rarity_weight"),
            (self.reference_weight, "reference_weight"),
            (self.threshold, "threshold"),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            if not isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be finite and between 0 and 1")
        weights = (
            float(self.length_weight),
            float(self.structural_weight),
            float(self.rarity_weight),
            float(self.reference_weight),
        )
        if sum(weights) <= 0.0:
            raise ValueError("at least one promotion weight must be positive")
        total = sum(weights)
        object.__setattr__(self, "length_weight", weights[0] / total)
        object.__setattr__(self, "structural_weight", weights[1] / total)
        object.__setattr__(self, "rarity_weight", weights[2] / total)
        object.__setattr__(self, "reference_weight", weights[3] / total)
        entries = tuple(self.structural_weights)
        if len(entries) != len(FragmentKind) or len({kind for kind, _ in entries}) != len(entries):
            raise ValueError("structural_weights must contain one entry per fragment kind")
        mapped: dict[FragmentKind, float] = {}
        for kind, value in entries:
            if not isinstance(kind, FragmentKind):
                raise TypeError("structural weight kind must be FragmentKind")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError("structural weight must be a real number")
            if not isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError("structural weight must be finite and between 0 and 1")
            mapped[kind] = float(value)
        if set(mapped) != set(FragmentKind):
            raise ValueError("structural_weights must cover every fragment kind")
        object.__setattr__(
            self,
            "structural_weights",
            tuple((kind, mapped[kind]) for kind in FragmentKind),
        )

    def decide(
        self,
        fragment: FragmentDraft,
        *,
        idf_scores: Sequence[float] = (),
        corpus_idf_scores: Sequence[float] = (),
        reference_signal: bool | float = False,
    ) -> FragmentPromotionDecision:
        """Evaluate one occurrence with a deterministic exact-threshold gate."""
        if not isinstance(fragment, FragmentDraft):
            raise TypeError("promotion requires a FragmentDraft")
        term_scores = _raw_scores(idf_scores, "idf_scores")
        corpus_scores = _raw_scores(corpus_idf_scores, "corpus_idf_scores")
        population = corpus_scores or term_scores
        cutoff = _quantile(population, float(self.idf_percentile))
        maximum = max(term_scores, default=0.0)
        if not population or cutoff <= 0.0:
            rarity = 0.0
        elif maximum >= cutoff:
            rarity = 1.0
        else:
            rarity = min(1.0, maximum / cutoff)
        signals = FragmentSignals(
            1.0 if fragment.length >= self.minimum_length else 0.0,
            dict(self.structural_weights)[fragment.kind],
            rarity,
            _reference(reference_signal),
        )
        weighted = (
            ("minimum_length", signals.minimum_length, self.length_weight),
            ("structural_weight", signals.structural_weight, self.structural_weight),
            ("corpus_rarity", signals.corpus_rarity, self.rarity_weight),
            ("reference_signal", signals.reference_signal, self.reference_weight),
        )
        contributions = tuple(
            SignalContribution(name, signal, weight, round(signal * weight, 12))
            for name, signal, weight in weighted
        )
        score = round(sum(entry.contribution for entry in contributions), 12)
        promoted = score >= float(self.threshold)
        reason = "threshold_met" if promoted else "below_threshold"
        return FragmentPromotionDecision(
            fragment,
            signals,
            contributions,
            score,
            float(self.threshold),
            promoted,
            reason,
        )


def promoted_unit_drafts(
    decisions: Sequence[FragmentPromotionDecision],
) -> tuple[UnitDraft, ...]:
    """Translate promoted fragments into identity-free KB-06 draft values."""
    entries = tuple(decisions)
    if len(entries) > MAX_FRAGMENTS:
        raise ValueError("promotion decision collection is too large")
    drafts: list[UnitDraft] = []
    seen: set[tuple[NodeId, FragmentKind, tuple[int, int]]] = set()
    for decision in entries:
        if not isinstance(decision, FragmentPromotionDecision):
            raise TypeError("promotion decisions must be typed values")
        if not decision.promoted:
            continue
        fragment = decision.fragment
        key = (fragment.node_id, fragment.kind, fragment.span)
        if key in seen:
            raise ValueError("promotion decisions must not repeat a fragment occurrence")
        seen.add(key)
        drafts.append(
            UnitDraft(
                _FRAGMENT_TO_UNIT[fragment.kind],
                4,
                fragment.structural_path,
                fragment.span,
                fragment.flags,
                None
                if fragment.parent_node_id is None
                else fragment.structural_path[:-1],
                fragment.node_id,
            )
        )
    return tuple(drafts)


def materialize_promoted_fragments(
    context: AdmittedDocumentTree,
    decisions: Sequence[FragmentPromotionDecision],
    *,
    revision_id: RevisionId,
    binding: RevisionBinding,
    policy: UnitizerPolicy,
    meta: UnitMeta | None = None,
) -> tuple[RetrievableUnit, ...]:
    """Materialize promoted drafts through the existing KB-06 owner."""
    tree, text = _tree_context(context)
    if not isinstance(revision_id, RevisionId):
        raise TypeError("revision_id must be RevisionId")
    if not isinstance(binding, RevisionBinding):
        raise TypeError("binding must be RevisionBinding")
    for decision in decisions:
        if not isinstance(decision, FragmentPromotionDecision):
            raise TypeError("promotion decisions must be typed values")
        fragment = decision.fragment
        if (
            fragment.substrate_id != binding.substrate_id
            or fragment.source_id != binding.source_id
            or fragment.revision_id != revision_id
        ):
            raise ValueError("fragment decision does not match its canonical revision binding")
        node = tree.node(fragment.node_id)
        if node.span != fragment.span or node.path != fragment.structural_path:
            raise ValueError("fragment decision does not match its canonical tree node")
    drafts = (*draft_units(text, tree, policy=policy), *promoted_unit_drafts(decisions))
    return unitize_drafts(
        text,
        tree,
        drafts,
        revision_id=revision_id,
        binding=binding,
        policy=policy,
        meta=meta,
    )


__all__ = [
    "MAX_CANONICAL_TEXT",
    "MAX_FRAGMENTS",
    "FragmentPromotionPolicy",
    "draft_fragments",
    "materialize_promoted_fragments",
    "promoted_unit_drafts",
]
