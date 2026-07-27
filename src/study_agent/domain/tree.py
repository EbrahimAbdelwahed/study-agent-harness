"""Immutable, provider-neutral contracts for deterministic document trees.

A document tree is one bounded structural projection of a frozen substrate.
It is rebuildable from the substrate bytes, the declared dialect profile, and
the tree format version alone; it never carries model output, connector
implementations, or source-specific domain vocabulary.

Spans are half-open Unicode code-point ranges over the normalized substrate
text, matching the citation span contract frozen by ADR-0014.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from ._validation import JsonObject, JsonValue, require_text
from .identifiers import NodeId, SubstrateId


class RegionKind(StrEnum):
    """Generic structural region kinds shared by every source dialect."""

    BODY = "body"
    EMPHASIS = "emphasis"
    SUMMARY = "summary"
    DEFINITION = "definition"
    TABLE = "table"
    CODE = "code"
    FIGURE_REF = "figure_ref"
    ITEM = "item"


class HeadingSyntax(StrEnum):
    """Generic heading conventions a connector profile may declare."""

    NONE = "none"
    ATX = "atx"


#: Flag raised on a region whose declared delimiters never close.
MALFORMED_FLAG = "malformed"


@dataclass(frozen=True, slots=True)
class DialectProfile:
    """A connector-declared description of one source dialect.

    The profile is data, not behavior: the tree builder consumes it without
    importing any connector.  Markers are declared as literal strings so that a
    profile cannot smuggle source-specific enums or executable rules into the
    structural trunk.
    """

    profile_name: str
    profile_version: str
    heading_syntax: HeadingSyntax = HeadingSyntax.NONE
    max_heading_depth: int = 6
    fenced_code: bool = False
    pipe_tables: bool = False
    list_items: bool = False
    figure_reference_markers: tuple[str, ...] = ()
    emphasis_markers: tuple[str, ...] = ()
    summary_markers: tuple[str, ...] = ()
    uncertainty_markers: tuple[str, ...] = ()
    definition_markers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.profile_name, "profile_name")
        require_text(self.profile_version, "profile_version")
        if not isinstance(self.heading_syntax, HeadingSyntax):
            raise TypeError("heading_syntax must be a HeadingSyntax value")
        if type(self.max_heading_depth) is not int or not 1 <= self.max_heading_depth <= 6:
            raise ValueError("max_heading_depth must be between 1 and 6")
        for flag, name in (
            (self.fenced_code, "fenced_code"),
            (self.pipe_tables, "pipe_tables"),
            (self.list_items, "list_items"),
        ):
            if type(flag) is not bool:
                raise TypeError(f"{name} must be a boolean")
        for markers, name in (
            (self.figure_reference_markers, "figure_reference_markers"),
            (self.emphasis_markers, "emphasis_markers"),
            (self.summary_markers, "summary_markers"),
            (self.definition_markers, "definition_markers"),
            (self.uncertainty_markers, "uncertainty_markers"),
        ):
            object.__setattr__(self, name, _marker_tuple(markers, name))

    def to_json(self) -> JsonObject:
        payload: dict[str, JsonValue] = {
            "emphasis_markers": self.emphasis_markers,
            "fenced_code": self.fenced_code,
            "figure_reference_markers": self.figure_reference_markers,
            "heading_syntax": self.heading_syntax.value,
            "list_items": self.list_items,
            "max_heading_depth": self.max_heading_depth,
            "pipe_tables": self.pipe_tables,
            "profile_name": self.profile_name,
            "profile_version": self.profile_version,
            "summary_markers": self.summary_markers,
            "uncertainty_markers": self.uncertainty_markers,
        }
        if self.definition_markers:
            payload["definition_markers"] = self.definition_markers
        return payload


def _marker_tuple(markers: Sequence[str], name: str) -> tuple[str, ...]:
    if isinstance(markers, (str, bytes, bytearray)) or not isinstance(markers, Sequence):
        raise TypeError(f"{name} must be a sequence of literal marker strings")
    entries = tuple(markers)
    for marker in entries:
        if not isinstance(marker, str):
            raise TypeError(f"{name} entries must be strings")
        require_text(marker, f"{name} entry")
    if len(set(entries)) != len(entries):
        raise ValueError(f"{name} must not repeat a marker")
    return entries


@dataclass(frozen=True, slots=True)
class TreeNode:
    """One ordered, span-bounded region of a document tree."""

    node_id: NodeId
    parent_id: NodeId | None
    path: tuple[str, ...]
    heading_text: str
    region_kind: RegionKind
    span: tuple[int, int]
    flags: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, NodeId):
            raise TypeError("node_id must be NodeId")
        if self.parent_id is not None and not isinstance(self.parent_id, NodeId):
            raise TypeError("parent_id must be NodeId or None")
        if self.parent_id == self.node_id:
            raise ValueError("a node cannot be its own parent")
        path = tuple(self.path)
        for segment in path:
            if not isinstance(segment, str):
                raise TypeError("path segments must be strings")
            require_text(segment, "path segment")
        object.__setattr__(self, "path", path)
        if not isinstance(self.heading_text, str):
            raise TypeError("heading_text must be a string")
        if not isinstance(self.region_kind, RegionKind):
            raise TypeError("region_kind must be a RegionKind value")
        span = tuple(self.span)
        if len(span) != 2 or any(type(value) is not int for value in span):
            raise ValueError("span must be a pair of integers")
        start, end = span
        if start < 0 or end <= start:
            raise ValueError("span must be a non-empty forward code-point range")
        object.__setattr__(self, "span", (start, end))
        flags = frozenset(self.flags)
        for flag in flags:
            if not isinstance(flag, str):
                raise TypeError("flags must be strings")
            require_text(flag, "flag")
        object.__setattr__(self, "flags", flags)
        if (self.parent_id is None) != (not path):
            raise ValueError("exactly the root node has an empty path and no parent")

    @property
    def depth(self) -> int:
        return len(self.path)

    @property
    def start_offset(self) -> int:
        return self.span[0]

    @property
    def end_offset(self) -> int:
        return self.span[1]

    def contains(self, other: TreeNode) -> bool:
        return self.span[0] <= other.span[0] and other.span[1] <= self.span[1]

    def to_json(self) -> JsonObject:
        return {
            "flags": tuple(sorted(self.flags)),
            "heading_text": self.heading_text,
            "node_id": str(self.node_id),
            "parent_id": None if self.parent_id is None else str(self.parent_id),
            "path": self.path,
            "region_kind": self.region_kind.value,
            "span": (self.span[0], self.span[1]),
        }


@dataclass(frozen=True, slots=True)
class DocumentTree:
    """One bounded, acyclic, deterministically ordered structural projection."""

    substrate_id: SubstrateId
    tree_format_version: str
    profile_name: str
    profile_version: str
    nodes: tuple[TreeNode, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.substrate_id, SubstrateId):
            raise TypeError("substrate_id must be SubstrateId")
        require_text(self.tree_format_version, "tree_format_version")
        require_text(self.profile_name, "profile_name")
        require_text(self.profile_version, "profile_version")
        nodes = tuple(self.nodes)
        if not nodes:
            raise ValueError("a document tree must contain at least a root node")
        for node in nodes:
            if not isinstance(node, TreeNode):
                raise TypeError("nodes must be TreeNode values")
        object.__setattr__(self, "nodes", nodes)
        _validate_structure(nodes)

    @property
    def root(self) -> TreeNode:
        return self.nodes[0]

    def node(self, node_id: NodeId) -> TreeNode:
        for candidate in self.nodes:
            if candidate.node_id == node_id:
                return candidate
        raise KeyError(f"unknown node: {node_id}")

    def children(self, node_id: NodeId) -> tuple[TreeNode, ...]:
        return tuple(node for node in self.nodes if node.parent_id == node_id)

    def to_json(self) -> JsonObject:
        return {
            "nodes": tuple(node.to_json() for node in self.nodes),
            "profile_name": self.profile_name,
            "profile_version": self.profile_version,
            "substrate_id": str(self.substrate_id),
            "tree_format_version": self.tree_format_version,
        }


def _validate_structure(nodes: tuple[TreeNode, ...]) -> None:
    """Enforce single-root, acyclic, ordered, and contained node structure."""
    root = nodes[0]
    if root.parent_id is not None:
        raise ValueError("the first node must be the root")
    seen: dict[NodeId, TreeNode] = {}
    for index, node in enumerate(nodes):
        if node.node_id in seen:
            raise ValueError("node ids must be unique within a document tree")
        if index > 0:
            if node.parent_id is None:
                raise ValueError("a document tree must have exactly one root")
            # Parents always precede children, which makes cycles unreachable.
            parent = seen.get(node.parent_id)
            if parent is None:
                raise ValueError("parent_id must reference a preceding node")
            if not parent.contains(node):
                raise ValueError("child spans must stay inside their parent span")
            if len(node.path) != len(parent.path) + 1:
                raise ValueError("child path must extend its parent path by one segment")
            if node.path[: len(parent.path)] != parent.path:
                raise ValueError("child path must extend its parent path")
        seen[node.node_id] = node
    _validate_sibling_order(nodes)


def _validate_sibling_order(nodes: tuple[TreeNode, ...]) -> None:
    by_parent: dict[NodeId | None, list[TreeNode]] = {}
    for node in nodes:
        by_parent.setdefault(node.parent_id, []).append(node)
    for siblings in by_parent.values():
        previous_end = -1
        previous_path: tuple[str, ...] | None = None
        for sibling in siblings:
            if sibling.span[0] < previous_end:
                raise ValueError("sibling spans must be ordered and non-overlapping")
            if previous_path is not None and sibling.path == previous_path:
                raise ValueError("sibling paths must be unique")
            previous_end = sibling.span[1]
            previous_path = sibling.path


__all__ = [
    "MALFORMED_FLAG",
    "DialectProfile",
    "DocumentTree",
    "HeadingSyntax",
    "RegionKind",
    "TreeNode",
]
