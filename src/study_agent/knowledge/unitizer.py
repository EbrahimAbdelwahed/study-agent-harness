"""Deterministic structural unitization over the canonical document tree.

The unitizer is the only owner of final ``UnitId`` creation.  It consumes the
already-admitted revision binding and the KB-04 tree; connector and model
claims are deliberately absent from this module.  The output is pure and
replayable for the same UTF-8 substrate, tree, and policy.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from re import finditer

from study_agent.domain.citation_v2 import TextCitationV2
from study_agent.domain.identifiers import NodeId, RevisionId, UnitId, substrate_id_for
from study_agent.domain.tree import DocumentTree, RegionKind, TreeNode
from study_agent.domain.units import (
    LinkKind,
    RetrievableUnit,
    TextSpan,
    UnitKind,
    UnitLink,
    UnitMeta,
)

from .units import UNITIZER_VERSION, RevisionBinding

V01_WINDOW_CHARACTERS = 1_200
"""The frozen v0.1 structure-poor window size."""


@dataclass(frozen=True, slots=True)
class UnitizerPolicy:
    """Versioned, corpus-agnostic boundary policy."""

    version: str = UNITIZER_VERSION
    max_characters: int = V01_WINDOW_CHARACTERS
    fallback_window_characters: int = V01_WINDOW_CHARACTERS

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("unitizer policy version must be non-empty text")
        for value, name in (
            (self.max_characters, "max_characters"),
            (self.fallback_window_characters, "fallback_window_characters"),
        ):
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.fallback_window_characters != V01_WINDOW_CHARACTERS:
            raise ValueError("the structure-poor fallback is frozen at 1,200 characters")


DEFAULT_POLICY = UnitizerPolicy()


@dataclass(frozen=True, slots=True)
class UnitDraft:
    """A bounded, identity-free draft produced before final unit admission."""

    unit_kind: UnitKind
    granularity: int
    structural_path: tuple[str, ...]
    span: tuple[int, int]
    flags: frozenset[str] = frozenset()
    parent_path: tuple[str, ...] | None = None
    node_id: NodeId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.unit_kind, UnitKind):
            raise TypeError("unit draft kind must be UnitKind")
        if type(self.granularity) is not int:
            raise TypeError("unit draft granularity must be an integer")
        path = tuple(self.structural_path)
        if any(not isinstance(segment, str) or not segment.strip() for segment in path):
            raise ValueError("unit draft path segments must be non-empty text")
        object.__setattr__(self, "structural_path", path)
        start, end = tuple(self.span)
        if type(start) is not int or type(end) is not int or start < 0 or end <= start:
            raise ValueError("unit draft span must be a non-empty forward range")
        object.__setattr__(self, "span", (start, end))
        flags = frozenset(self.flags)
        if any(not isinstance(flag, str) or not flag.strip() for flag in flags):
            raise ValueError("unit draft flags must be non-empty text")
        object.__setattr__(self, "flags", flags)
        if self.parent_path is not None:
            parent = tuple(self.parent_path)
            if any(not isinstance(segment, str) or not segment.strip() for segment in parent):
                raise ValueError("unit draft parent_path segments must be non-empty text")
            object.__setattr__(self, "parent_path", parent)
        if self.node_id is not None and not isinstance(self.node_id, NodeId):
            raise TypeError("unit draft node_id must be NodeId or None")


@dataclass(frozen=True, slots=True)
class CitationRemap:
    """One conservative citation migration result."""

    citation: TextCitationV2
    replacement: TextCitationV2 | None
    reason: str

    @property
    def matched(self) -> bool:
        return self.replacement is not None


@dataclass(frozen=True, slots=True)
class RemapReport:
    """Complete report for a unitizer-version migration."""

    old_version: str
    new_version: str
    entries: tuple[CitationRemap, ...]

    @property
    def matched(self) -> tuple[CitationRemap, ...]:
        return tuple(entry for entry in self.entries if entry.matched)

    @property
    def unmatched(self) -> tuple[CitationRemap, ...]:
        return tuple(entry for entry in self.entries if not entry.matched)


def draft_units(
    text: str,
    tree: DocumentTree,
    *,
    policy: UnitizerPolicy = DEFAULT_POLICY,
) -> tuple[UnitDraft, ...]:
    """Produce identity-free document/section/passage drafts.

    ``text`` is used only to verify spans and to locate paragraph boundaries;
    the returned drafts carry spans, never canonical text.
    """

    _validate_tree_text(text, tree)
    if not isinstance(policy, UnitizerPolicy):
        raise TypeError("policy must be a UnitizerPolicy")
    root = tree.root
    drafts: list[UnitDraft] = [
        UnitDraft(
            UnitKind.DOCUMENT_CARD,
            0,
            ("document",),
            root.span,
            root.flags,
            None,
        )
    ]

    sections = tuple(
        node for node in tree.nodes if node.region_kind is RegionKind.BODY and node.path
    )
    for node in sections:
        parent_path = _section_parent_path(node.path, sections)
        drafts.append(
            UnitDraft(
                UnitKind.SECTION,
                min(2, max(1, len(node.path))),
                node.path,
                node.span,
                node.flags,
                parent_path,
            )
        )

    root_regions = tuple(
        node
        for node in tree.children(root.node_id)
        if node.region_kind is not RegionKind.BODY
    )
    # A root with headings owns only its preamble/gaps.  A genuinely
    # structure-poor root owns the full document and therefore gets the exact
    # v0.1 fallback.  Typed regions are structure, even without headings, so
    # they still receive the atomic-region treatment below.
    if not sections and not root_regions:
        passage_spans = _fallback_windows(len(text), policy.fallback_window_characters)
        for start, end in passage_spans:
            drafts.append(
                UnitDraft(
                    UnitKind.PASSAGE,
                    3,
                    ("document",),
                    (start, end),
                    root.flags,
                    None,
                )
            )
    elif sections:
        for node in sections:
            for start, end, path, flags in _passage_spans_for_node(text, tree, node, policy):
                drafts.append(
                    UnitDraft(
                        UnitKind.PASSAGE,
                        3,
                        path,
                        (start, end),
                        flags,
                        _nearest_section_path(path, sections),
                    )
                )
        for start, end in _owned_ranges(root, tree):
            if end > start and text[start:end].strip():
                for span in _split_range(
                    text, start, end, (), root.flags, policy.max_characters
                ):
                    drafts.append(
                        UnitDraft(
                            UnitKind.PASSAGE,
                            3,
                            ("document",),
                            span,
                            root.flags,
                            None,
                        )
                    )
    else:
        for start, end, _, flags in _passage_spans_for_node(text, tree, root, policy):
            drafts.append(
                UnitDraft(
                    UnitKind.PASSAGE,
                    3,
                    ("document",),
                    (start, end),
                    flags,
                    None,
                )
            )

    return tuple(drafts)


def unitize(
    text: str,
    tree: DocumentTree,
    *,
    revision_id: RevisionId,
    binding: RevisionBinding,
    policy: UnitizerPolicy = DEFAULT_POLICY,
    meta: UnitMeta | None = None,
) -> tuple[RetrievableUnit, ...]:
    """Materialize final units from canonical bytes and a real revision binding."""

    if not isinstance(revision_id, RevisionId):
        raise TypeError("revision_id must be RevisionId")
    if not isinstance(binding, RevisionBinding):
        raise TypeError("binding must be RevisionBinding")
    _validate_tree_text(text, tree)
    if len(text) != binding.character_length:
        raise ValueError("canonical text length does not match the revision binding")
    if substrate_id_for(text.encode("utf-8")) != binding.substrate_id:
        raise ValueError("canonical text does not match the bound substrate")
    base_meta = meta if meta is not None else UnitMeta("unknown", "primary", 0)
    if not isinstance(base_meta, UnitMeta):
        raise TypeError("meta must be UnitMeta")

    return unitize_drafts(
        text,
        tree,
        draft_units(text, tree, policy=policy),
        revision_id=revision_id,
        binding=binding,
        policy=policy,
        meta=meta,
    )


def unitize_drafts(
    text: str,
    tree: DocumentTree,
    drafts: Sequence[UnitDraft],
    *,
    revision_id: RevisionId,
    binding: RevisionBinding,
    policy: UnitizerPolicy = DEFAULT_POLICY,
    meta: UnitMeta | None = None,
) -> tuple[RetrievableUnit, ...]:
    """Materialize canonical drafts through the one KB-06 identity owner.

    ``drafts`` remain identity-free.  A caller may provide typed structural
    drafts, but every span and optional node binding is checked against the
    already-admitted tree before the existing ``_unit_id`` function runs.
    """
    if not isinstance(revision_id, RevisionId):
        raise TypeError("revision_id must be RevisionId")
    if not isinstance(binding, RevisionBinding):
        raise TypeError("binding must be RevisionBinding")
    _validate_tree_text(text, tree)
    if len(text) != binding.character_length:
        raise ValueError("canonical text length does not match the revision binding")
    if substrate_id_for(text.encode("utf-8")) != binding.substrate_id:
        raise ValueError("canonical text does not match the bound substrate")
    if not isinstance(policy, UnitizerPolicy):
        raise TypeError("policy must be a UnitizerPolicy")
    base_meta = meta if meta is not None else UnitMeta("unknown", "primary", 0)
    if not isinstance(base_meta, UnitMeta):
        raise TypeError("meta must be UnitMeta")
    materialized_drafts = tuple(drafts)
    if len(materialized_drafts) > 4096:
        raise ValueError("unit draft collection is too large")
    for draft in materialized_drafts:
        if not isinstance(draft, UnitDraft):
            raise TypeError("drafts must contain UnitDraft values")
        _validate_draft_context(draft, tree, len(text))
    units: list[RetrievableUnit] = []
    for ordinal, draft in enumerate(materialized_drafts, start=base_meta.ordinal):
        span = TextSpan(binding.substrate_id, *draft.span)
        unit_meta = replace(base_meta, flags=base_meta.flags | draft.flags, ordinal=ordinal)
        units.append(
            RetrievableUnit(
                _unit_id(revision_id, draft, span, policy),
                binding.source_id,
                revision_id,
                draft.unit_kind,
                draft.granularity,
                draft.structural_path,
                span,
                unit_meta,
            )
        )

    # Links are added after all IDs exist; links are not identity-bearing.
    by_key = {
        (
            unit.unit_kind,
            unit.structural_path,
            unit.canonical_ref.start,
            unit.canonical_ref.end,
        ): unit
        for unit in units
        if isinstance(unit.canonical_ref, TextSpan)
    }
    document = next(unit for unit in units if unit.unit_kind is UnitKind.DOCUMENT_CARD)
    finalized: list[RetrievableUnit] = []
    for unit in units:
        if unit.unit_kind is UnitKind.DOCUMENT_CARD:
            finalized.append(unit)
            continue
        parent = _parent_unit(unit, by_key, document)
        finalized.append(replace(unit, links=(UnitLink(LinkKind.PARENT, parent.unit_id),)))
    return tuple(finalized)


def _validate_draft_context(draft: UnitDraft, tree: DocumentTree, text_length: int) -> None:
    """Reject spans and structural claims not backed by the admitted tree."""
    start, end = draft.span
    if end > text_length or start < 0:
        raise ValueError("unit draft span escapes canonical text")
    if draft.node_id is None:
        return
    node = tree.node(draft.node_id)
    if node.path != draft.structural_path:
        raise ValueError("unit draft path does not match its tree node")
    if node.region_kind is RegionKind.BODY:
        raise ValueError("typed unit draft must reference a typed tree region")
    expected_kind = {
        RegionKind.EMPHASIS: UnitKind.EMPHASIS,
        RegionKind.SUMMARY: UnitKind.SUMMARY,
        RegionKind.DEFINITION: UnitKind.DEFINITION,
        RegionKind.TABLE: UnitKind.TABLE,
        RegionKind.ITEM: UnitKind.ITEM,
    }.get(node.region_kind)
    if expected_kind is None or draft.unit_kind is not expected_kind:
        raise ValueError("typed unit draft kind does not match its tree region")
    if not node.start_offset <= start < end <= node.end_offset:
        raise ValueError("unit draft span escapes its tree node")


def remap_citations(
    citations: Sequence[TextCitationV2],
    *,
    old_units: Sequence[RetrievableUnit],
    new_units: Sequence[RetrievableUnit],
    old_version: str,
    new_version: str,
) -> RemapReport:
    """Remap only exact, unambiguous unit placements; never guess."""

    old_by_id = {unit.unit_id: unit for unit in old_units}
    new_text = tuple(unit for unit in new_units if isinstance(unit.canonical_ref, TextSpan))
    entries: list[CitationRemap] = []
    for citation in citations:
        old = old_by_id.get(citation.unit_id)
        if old is None or not isinstance(old.canonical_ref, TextSpan):
            entries.append(CitationRemap(citation, None, "old unit is unavailable"))
            continue
        candidates = tuple(
            unit
            for unit in new_text
            if isinstance(unit.canonical_ref, TextSpan)
            and unit.source_id == old.source_id
            and unit.revision_id == old.revision_id
            and unit.unit_kind == old.unit_kind
            and unit.granularity == old.granularity
            and unit.structural_path == old.structural_path
            and unit.canonical_ref == old.canonical_ref
        )
        if len(candidates) != 1:
            reason = "no exact replacement" if not candidates else "ambiguous exact replacements"
            entries.append(CitationRemap(citation, None, reason))
            continue
        replacement = replace(citation, unit_id=candidates[0].unit_id)
        entries.append(CitationRemap(citation, replacement, "exact canonical placement"))
    return RemapReport(old_version, new_version, tuple(entries))


def _unit_id(
    revision_id: RevisionId,
    draft: UnitDraft,
    span: TextSpan,
    policy: UnitizerPolicy,
) -> UnitId:
    from study_agent.domain.identifiers import unit_id_for

    return unit_id_for(
        revision_id=revision_id,
        structural_path=draft.structural_path,
        unit_kind=draft.unit_kind.value,
        granularity=draft.granularity,
        canonical_ref=dict(span.to_json()),
        unitizer_version=policy.version,
    )


def _validate_tree_text(text: str, tree: DocumentTree) -> None:
    if not isinstance(text, str):
        raise TypeError("unitizer requires canonical UTF-8 text decoded as str")
    if not text:
        raise ValueError("unitizer requires non-empty canonical text")
    if not isinstance(tree, DocumentTree):
        raise TypeError("unitizer requires a DocumentTree")
    if tree.root.span != (0, len(text)):
        raise ValueError("tree root span must cover the canonical text")
    for node in tree.nodes:
        if node.start_offset < 0 or node.end_offset > len(text):
            raise ValueError("tree node span escapes the canonical text")


def _fallback_windows(length: int, cap: int) -> tuple[tuple[int, int], ...]:
    return tuple((start, min(start + cap, length)) for start in range(0, length, cap))


def _section_parent_path(
    path: tuple[str, ...], sections: Sequence[TreeNode]
) -> tuple[str, ...] | None:
    candidates = [
        candidate.path
        for candidate in sections
        if candidate.path
        and len(candidate.path) < len(path)
        and path[: len(candidate.path)] == candidate.path
    ]
    return max(candidates, key=len) if candidates else None


def _nearest_section_path(
    path: tuple[str, ...], sections: Sequence[TreeNode]
) -> tuple[str, ...] | None:
    candidates = [
        candidate.path
        for candidate in sections
        if path[: len(candidate.path)] == candidate.path
    ]
    return max(candidates, key=len) if candidates else None


def _owned_ranges(node: TreeNode, tree: DocumentTree) -> tuple[tuple[int, int], ...]:
    children = sorted(tree.children(node.node_id), key=lambda item: item.span)
    cursor = node.start_offset
    ranges: list[tuple[int, int]] = []
    for child in children:
        if child.start_offset > cursor:
            ranges.append((cursor, child.start_offset))
        cursor = max(cursor, child.end_offset)
    if cursor < node.end_offset:
        ranges.append((cursor, node.end_offset))
    return tuple(ranges)


def _passage_spans_for_node(
    text: str,
    tree: DocumentTree,
    node: TreeNode,
    policy: UnitizerPolicy,
) -> Iterable[tuple[int, int, tuple[str, ...], frozenset[str]]]:
    if node.end_offset - node.start_offset <= policy.max_characters:
        yield node.start_offset, node.end_offset, node.path, node.flags
        return
    children = sorted(tree.children(node.node_id), key=lambda item: item.span)
    for start, end in _owned_ranges(node, tree):
        if text[start:end].strip():
            for span in _split_range(text, start, end, (), node.flags, policy.max_characters):
                yield span[0], span[1], node.path, node.flags
    for child in children:
        if child.region_kind is RegionKind.BODY:
            continue
        # Typed regions are atomic.  They may exceed the ordinary cap.
        yield child.start_offset, child.end_offset, child.path, node.flags | child.flags


def _split_range(
    text: str,
    start: int,
    end: int,
    _: tuple[str, ...],
    __: frozenset[str],
    cap: int,
) -> tuple[tuple[int, int], ...]:
    """Pack paragraphs under ``cap`` while preserving oversized paragraphs."""

    if end - start <= cap:
        return ((start, end),)
    boundaries = [start]
    for match in finditer(r"\n\s*\n", text[start:end]):
        boundary = start + match.end()
        if boundary > boundaries[-1]:
            boundaries.append(boundary)
    if boundaries[-1] != end:
        boundaries.append(end)
    paragraphs = tuple(pairwise(boundaries))
    output: list[tuple[int, int]] = []
    current_start: int | None = None
    current_end: int | None = None
    for paragraph_start, paragraph_end in paragraphs:
        if paragraph_end <= paragraph_start:
            continue
        if paragraph_end - paragraph_start > cap:
            if current_start is not None:
                output.append((current_start, current_end or current_start))
                current_start = current_end = None
            output.append((paragraph_start, paragraph_end))
            continue
        if current_start is None:
            current_start, current_end = paragraph_start, paragraph_end
        elif paragraph_end - current_start <= cap:
            current_end = paragraph_end
        else:
            output.append((current_start, current_end or current_start))
            current_start, current_end = paragraph_start, paragraph_end
    if current_start is not None and current_end is not None:
        output.append((current_start, current_end))
    return tuple(output)


def _parent_unit(
    unit: RetrievableUnit,
    by_key: dict[tuple[UnitKind, tuple[str, ...], int, int], RetrievableUnit],
    document: RetrievableUnit,
) -> RetrievableUnit:
    path = unit.structural_path
    if unit.unit_kind is UnitKind.SECTION:
        candidates = [
            candidate
            for (kind, candidate_path, _, _), candidate in by_key.items()
            if kind is UnitKind.SECTION
            and len(candidate_path) < len(path)
            and path[: len(candidate_path)] == candidate_path
        ]
        if candidates:
            return max(candidates, key=lambda item: len(item.structural_path))
        return document
    for length in range(len(path), 0, -1):
        candidates = [
            candidate
            for (kind, candidate_path, _, _), candidate in by_key.items()
            if kind is UnitKind.SECTION and candidate_path == path[:length]
        ]
        if candidates:
            return candidates[0]
    return document


__all__ = [
    "DEFAULT_POLICY",
    "V01_WINDOW_CHARACTERS",
    "CitationRemap",
    "RemapReport",
    "UnitDraft",
    "UnitizerPolicy",
    "draft_units",
    "remap_citations",
    "unitize",
    "unitize_drafts",
]
