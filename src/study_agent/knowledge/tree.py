"""Pure, deterministic document-tree construction over a frozen substrate.

The builder consumes normalized substrate text plus a connector-declared
:class:`~study_agent.domain.tree.DialectProfile`.  It performs no I/O, imports
no connector, calls no model, and produces a byte-identical tree for the same
substrate, profile, and format version.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from study_agent.domain.identifiers import NodeId, SubstrateId, node_id_for
from study_agent.domain.tree import (
    MALFORMED_FLAG,
    DialectProfile,
    DocumentTree,
    HeadingSyntax,
    RegionKind,
    TreeNode,
)

#: Bumping this version changes every derived ``node_id`` and forces a rebuild.
TREE_FORMAT_VERSION = "document-tree-v1"

_FENCE = "```"
_LIST_BULLETS = ("- ", "* ", "+ ")


@dataclass(frozen=True, slots=True)
class _Line:
    start: int
    end: int
    content: str


@dataclass(frozen=True, slots=True)
class _Heading:
    level: int
    start: int
    title: str
    anchor: str | None


@dataclass(frozen=True, slots=True)
class _Region:
    kind: RegionKind
    start: int
    end: int
    flags: frozenset[str]


@dataclass
class _Outline:
    """Mutable scaffold used only while nesting headings."""

    level: int
    title: str
    anchor: str | None
    start: int
    end: int
    children: list[_Outline] = field(default_factory=list)


def build_document_tree(
    text: str,
    profile: DialectProfile,
    *,
    substrate_id: SubstrateId,
) -> DocumentTree:
    """Project one frozen substrate into its bounded document tree."""
    if not isinstance(text, str):
        raise TypeError("document tree requires normalized substrate text")
    if not text:
        raise ValueError("document tree requires non-empty substrate text")
    if not isinstance(profile, DialectProfile):
        raise TypeError("document tree requires a DialectProfile")
    if not isinstance(substrate_id, SubstrateId):
        raise TypeError("document tree requires SubstrateId")

    lines = _scan_lines(text)
    code_spans = _code_spans(lines, profile)
    headings = _headings(lines, code_spans, profile)
    outline = _nest(headings, len(text))
    nodes: list[TreeNode] = []
    _emit(
        outline,
        parent_id=None,
        path=(),
        lines=lines,
        code_spans=code_spans,
        profile=profile,
        substrate_id=substrate_id,
        nodes=nodes,
    )
    return DocumentTree(
        substrate_id,
        TREE_FORMAT_VERSION,
        profile.profile_name,
        profile.profile_version,
        tuple(nodes),
    )


def _scan_lines(text: str) -> tuple[_Line, ...]:
    """Split into newline-inclusive lines so spans tile the document exactly."""
    lines: list[_Line] = []
    start = 0
    length = len(text)
    while start < length:
        break_index = text.find("\n", start)
        end = length if break_index == -1 else break_index + 1
        lines.append(_Line(start, end, text[start : end if break_index == -1 else break_index]))
        start = end
    return tuple(lines)


def _code_spans(
    lines: tuple[_Line, ...], profile: DialectProfile
) -> tuple[_Region, ...]:
    """Return fenced-code spans; an unterminated fence is flagged, not dropped."""
    if not profile.fenced_code:
        return ()
    spans: list[_Region] = []
    open_line: _Line | None = None
    for line in lines:
        if not line.content.lstrip().startswith(_FENCE):
            continue
        if open_line is None:
            open_line = line
        else:
            spans.append(_Region(RegionKind.CODE, open_line.start, line.end, frozenset()))
            open_line = None
    if open_line is not None:
        spans.append(
            _Region(
                RegionKind.CODE,
                open_line.start,
                lines[-1].end,
                frozenset({MALFORMED_FLAG}),
            )
        )
    return tuple(spans)


def _inside(offset: int, spans: tuple[_Region, ...]) -> bool:
    return any(span.start <= offset < span.end for span in spans)


def _headings(
    lines: tuple[_Line, ...],
    code_spans: tuple[_Region, ...],
    profile: DialectProfile,
) -> tuple[_Heading, ...]:
    if profile.heading_syntax is not HeadingSyntax.ATX:
        return ()
    headings: list[_Heading] = []
    for line in lines:
        if _inside(line.start, code_spans):
            continue
        stripped = line.content.lstrip()
        level = len(stripped) - len(stripped.lstrip("#"))
        if level < 1 or level > profile.max_heading_depth:
            continue
        remainder = stripped[level:]
        if not remainder.startswith(" "):
            continue
        title, anchor = _split_anchor(remainder.strip())
        if not title and anchor is None:
            continue
        headings.append(_Heading(level, line.start, title, anchor))
    return tuple(headings)


def _split_anchor(text: str) -> tuple[str, str | None]:
    """Extract a trailing authored ``{#anchor}`` declaration."""
    if not text.endswith("}"):
        return text, None
    opening = text.rfind("{#")
    if opening == -1:
        return text, None
    anchor = text[opening + 2 : -1].strip()
    if not anchor:
        return text, None
    return text[:opening].strip(), anchor


def _nest(headings: tuple[_Heading, ...], document_end: int) -> _Outline:
    root = _Outline(0, "", None, 0, document_end)
    stack: list[_Outline] = [root]
    for index, heading in enumerate(headings):
        end = document_end
        for candidate in headings[index + 1 :]:
            if candidate.level <= heading.level:
                end = candidate.start
                break
        node = _Outline(heading.level, heading.title, heading.anchor, heading.start, end)
        while stack[-1].level >= heading.level:
            stack.pop()
        stack[-1].children.append(node)
        stack.append(node)
    return root


def _emit(
    outline: _Outline,
    *,
    parent_id: NodeId | None,
    path: tuple[str, ...],
    lines: tuple[_Line, ...],
    code_spans: tuple[_Region, ...],
    profile: DialectProfile,
    substrate_id: SubstrateId,
    nodes: list[TreeNode],
) -> frozenset[str]:
    """Append one outline node and its children in document order.

    Returns the node's flags after propagation so that every containing node
    accumulates the uncertainty declared by its typed regions.
    """
    own_end = outline.children[0].start if outline.children else outline.end
    regions = _regions(outline.start, own_end, lines, code_spans, profile)
    children: list[tuple[int, RegionKind, _Region | _Outline]] = [
        (region.start, region.kind, region) for region in regions
    ]
    children.extend((child.start, RegionKind.BODY, child) for child in outline.children)
    children.sort(key=lambda entry: entry[0])
    segments = _unique_segments(children)

    node_id = node_id_for(
        substrate_id=substrate_id,
        tree_format_version=TREE_FORMAT_VERSION,
        profile_name=profile.profile_name,
        profile_version=profile.profile_version,
        path=path,
    )
    index = len(nodes)
    placeholder = TreeNode(
        node_id,
        parent_id,
        path,
        outline.title,
        RegionKind.BODY,
        (outline.start, outline.end),
        frozenset(),
    )
    nodes.append(placeholder)

    flags = _markers_in(outline.start, own_end, lines, profile)
    for segment, (_, _, child) in zip(segments, children, strict=True):
        child_path = (*path, segment)
        if isinstance(child, _Outline):
            flags |= _emit(
                child,
                parent_id=node_id,
                path=child_path,
                lines=lines,
                code_spans=code_spans,
                profile=profile,
                substrate_id=substrate_id,
                nodes=nodes,
            )
        else:
            flags |= _emit_region(
                child,
                parent_id=node_id,
                path=child_path,
                lines=lines,
                profile=profile,
                substrate_id=substrate_id,
                nodes=nodes,
            )
    nodes[index] = TreeNode(
        node_id,
        parent_id,
        path,
        outline.title,
        RegionKind.BODY,
        (outline.start, outline.end),
        flags,
    )
    return flags


def _emit_region(
    region: _Region,
    *,
    parent_id: NodeId,
    path: tuple[str, ...],
    lines: tuple[_Line, ...],
    profile: DialectProfile,
    substrate_id: SubstrateId,
    nodes: list[TreeNode],
) -> frozenset[str]:
    flags = region.flags | _markers_in(region.start, region.end, lines, profile)
    nodes.append(
        TreeNode(
            node_id_for(
                substrate_id=substrate_id,
                tree_format_version=TREE_FORMAT_VERSION,
                profile_name=profile.profile_name,
                profile_version=profile.profile_version,
                path=path,
            ),
            parent_id,
            path,
            "",
            region.kind,
            (region.start, region.end),
            flags,
        )
    )
    return flags


def _unique_segments(
    children: list[tuple[int, RegionKind, _Region | _Outline]],
) -> tuple[str, ...]:
    """Assign deterministic, collision-free path segments in document order."""
    counters: dict[RegionKind, int] = {}
    proposed: list[str] = []
    for _, kind, child in children:
        if isinstance(child, _Outline):
            proposed.append(child.anchor or _slugify(child.title))
        else:
            counters[kind] = counters.get(kind, 0) + 1
            proposed.append(f"{kind.value}-{counters[kind]}")
    used: dict[str, int] = {}
    segments: list[str] = []
    for segment in proposed:
        if segment in used:
            used[segment] += 1
            segments.append(f"{segment}-{used[segment]}")
        else:
            used[segment] = 1
            segments.append(segment)
    return tuple(segments)


def _slugify(title: str) -> str:
    characters: list[str] = []
    dashed = False
    for character in title.lower():
        if character.isalnum():
            characters.append(character)
            dashed = False
        elif not dashed:
            characters.append("-")
            dashed = True
    slug = "".join(characters).strip("-")
    return slug or "section"


def _regions(
    start: int,
    end: int,
    lines: tuple[_Line, ...],
    code_spans: tuple[_Region, ...],
    profile: DialectProfile,
) -> tuple[_Region, ...]:
    """Classify the node's own content into ordered, non-overlapping regions."""
    if end <= start:
        return ()
    regions: list[_Region] = []
    for span in code_spans:
        if start <= span.start and span.end <= end:
            regions.append(span)
    open_kind: RegionKind | None = None
    open_start = 0
    open_end = 0
    for line in lines:
        if line.start < start or line.end > end:
            continue
        if _inside(line.start, code_spans):
            # A fenced block is its own region; it must never be swallowed by
            # an open merged region that started before it.
            if open_kind is not None:
                regions.append(_Region(open_kind, open_start, open_end, frozenset()))
                open_kind = None
            continue
        kind = _classify(line.content, profile)
        if open_kind is not None:
            # A merged region continues through its own kind and through
            # unclassified continuation lines (for example the body lines of a
            # callout), and closes on a blank line or a different region.
            if kind is open_kind or (kind is None and line.content.strip()):
                open_end = line.end
                continue
            regions.append(_Region(open_kind, open_start, open_end, frozenset()))
            open_kind = None
        if kind is None:
            continue
        if kind in _MERGEABLE:
            open_kind, open_start, open_end = kind, line.start, line.end
        else:
            regions.append(_Region(kind, line.start, line.end, frozenset()))
    if open_kind is not None:
        regions.append(_Region(open_kind, open_start, open_end, frozenset()))
    regions.sort(key=lambda region: region.start)
    return tuple(regions)


_MERGEABLE = frozenset({RegionKind.TABLE, RegionKind.EMPHASIS, RegionKind.SUMMARY})


def _classify(content: str, profile: DialectProfile) -> RegionKind | None:
    stripped = content.strip()
    if not stripped:
        return None
    for marker in profile.emphasis_markers:
        if stripped.startswith(marker):
            return RegionKind.EMPHASIS
    for marker in profile.summary_markers:
        if stripped.startswith(marker):
            return RegionKind.SUMMARY
    if profile.pipe_tables and stripped.startswith("|"):
        return RegionKind.TABLE
    for marker in profile.figure_reference_markers:
        if marker in stripped:
            return RegionKind.FIGURE_REF
    if profile.list_items and _is_list_item(stripped):
        return RegionKind.ITEM
    return None


def _is_list_item(stripped: str) -> bool:
    if stripped.startswith(_LIST_BULLETS):
        return True
    head, separator, remainder = stripped.partition(". ")
    return bool(separator) and head.isdigit() and bool(remainder.strip())


def _markers_in(
    start: int,
    end: int,
    lines: tuple[_Line, ...],
    profile: DialectProfile,
) -> frozenset[str]:
    if end <= start or not profile.uncertainty_markers:
        return frozenset()
    content = "".join(
        line.content for line in lines if line.start >= start and line.end <= end
    )
    return frozenset(
        marker for marker in profile.uncertainty_markers if marker in content
    )


__all__ = ["TREE_FORMAT_VERSION", "build_document_tree"]
