"""Small deterministic heading/paragraph chunker over normalized character spans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

from study_agent.domain.identifiers import RevisionId, SourceId
from study_agent.domain.source import SourceChunk, SourceKind

from .identity import CHUNKER_POLICY_VERSION, chunk_id_for

CHUNKER_VERSION = CHUNKER_POLICY_VERSION
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_FENCE_OPEN = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})[^\n]*$")


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    max_characters: int = 1200
    version: str = CHUNKER_VERSION

    def __post_init__(self) -> None:
        if self.max_characters < 1:
            raise ValueError("max_characters must be positive")
        if not self.version or self.version != self.version.strip():
            raise ValueError("chunker version must be non-empty trimmed text")


DEFAULT_CHUNKING_CONFIG = ChunkingConfig()


@dataclass(frozen=True, slots=True)
class _Block:
    start: int
    end: int
    section_path: tuple[str, ...]
    kind: str


def chunk_text(
    text: str,
    *,
    source_id: SourceId,
    revision_id: RevisionId,
    kind: SourceKind,
    config: ChunkingConfig = DEFAULT_CHUNKING_CONFIG,
) -> tuple[SourceChunk, ...]:
    """Return stable non-overlapping chunks whose offsets address ``text`` exactly."""

    blocks = _blocks(text, kind)
    chunks: list[SourceChunk] = []
    for block in blocks:
        for start, end in _split_span(text, block.start, block.end, config.max_characters):
            chunk_content = text[start:end]
            digest = sha256(chunk_content.encode("utf-8")).hexdigest()
            chunks.append(
                SourceChunk(
                    chunk_id_for(
                        source_id=source_id,
                        revision_id=revision_id,
                        start_offset=start,
                        end_offset=end,
                        checksum_sha256=digest,
                        chunker_version=config.version,
                    ),
                    source_id,
                    revision_id,
                    start,
                    end,
                    block.section_path,
                    len(chunks),
                    digest,
                    config.version,
                    {"block_kind": block.kind},
                )
            )
    if not chunks:
        raise ValueError("normalized text must contain non-whitespace content")
    return tuple(chunks)


def _blocks(text: str, kind: SourceKind) -> tuple[_Block, ...]:
    lines = tuple(re.finditer(r".*(?:\n|$)", text))
    blocks: list[_Block] = []
    headings: list[str] = []
    paragraph_start: int | None = None
    paragraph_end = 0
    fence_start: int | None = None
    fence_character = ""
    fence_length = 0

    def finish_paragraph() -> None:
        nonlocal paragraph_start
        if paragraph_start is not None:
            start, end = _trim_span(text, paragraph_start, paragraph_end)
            if start < end:
                blocks.append(_Block(start, end, tuple(headings), "paragraph"))
            paragraph_start = None

    for match in lines:
        raw_start, raw_end = match.span()
        line_end = raw_end - 1 if match.group().endswith("\n") else raw_end
        line = text[raw_start:line_end]
        if fence_start is not None:
            if _is_fence_close(line, fence_character, fence_length):
                blocks.append(
                    _Block(fence_start, line_end, tuple(headings), "code_fence")
                )
                fence_start = None
            if raw_start == raw_end:
                break
            continue
        fence = _FENCE_OPEN.fullmatch(line) if kind is SourceKind.MARKDOWN else None
        if fence is not None:
            finish_paragraph()
            marker = fence.group(1)
            fence_start = raw_start
            fence_character = marker[0]
            fence_length = len(marker)
            continue
        heading = _HEADING.fullmatch(line) if kind is SourceKind.MARKDOWN else None
        if heading is not None:
            finish_paragraph()
            level = len(heading.group(1))
            title = re.sub(r"[ \t]+#+[ \t]*$", "", heading.group(2)).strip()
            headings[level - 1 :] = [title]
            start, end = _trim_span(text, raw_start, line_end)
            if start < end:
                blocks.append(_Block(start, end, tuple(headings), "heading"))
        elif not line.strip():
            finish_paragraph()
        else:
            if paragraph_start is None:
                paragraph_start = raw_start
            paragraph_end = line_end
        if raw_start == raw_end:
            break
    finish_paragraph()
    if fence_start is not None:
        start, end = _trim_span(text, fence_start, len(text))
        if start < end:
            blocks.append(_Block(start, end, tuple(headings), "code_fence"))
    return tuple(blocks)


def _is_fence_close(line: str, character: str, minimum_length: int) -> bool:
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return False
    marker = stripped.rstrip(" \t")
    return len(marker) >= minimum_length and set(marker) == {character}


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _split_span(
    text: str, start: int, end: int, max_characters: int
) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        limit = min(cursor + max_characters, end)
        split = limit
        if limit < end:
            whitespace = max(
                text.rfind(" ", cursor, limit + 1),
                text.rfind("\n", cursor, limit + 1),
            )
            if whitespace > cursor:
                split = whitespace
        chunk_start, chunk_end = _trim_span(text, cursor, split)
        if chunk_start < chunk_end:
            spans.append((chunk_start, chunk_end))
        cursor = split
        while cursor < end and text[cursor].isspace():
            cursor += 1
    return tuple(spans)
