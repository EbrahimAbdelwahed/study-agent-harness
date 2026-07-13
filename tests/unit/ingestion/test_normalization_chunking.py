from __future__ import annotations

from hashlib import sha256

import pytest

from study_agent.domain import RevisionId, SourceId, SourceKind
from study_agent.ingestion import (
    CHUNKER_VERSION,
    NORMALIZATION_VERSION,
    ChunkingConfig,
    InvalidUtf8Error,
    chunk_text,
    normalize_utf8,
    revision_id_for,
)


def test_normalization_is_strict_versioned_and_canonicalizes_newlines_and_nfc() -> None:
    result = normalize_utf8("Cafe\u0301\r\nLine two\rLine three".encode())

    assert result.text == "Café\nLine two\nLine three"
    assert result.content == result.text.encode("utf-8")
    assert result.version == NORMALIZATION_VERSION


def test_normalization_rejects_invalid_utf8() -> None:
    with pytest.raises(InvalidUtf8Error, match="valid UTF-8"):
        normalize_utf8(b"\xff")


def test_markdown_chunking_tracks_small_heading_and_paragraph_structure() -> None:
    text = "# Heart\n\nFirst paragraph.\nSecond line.\n\n## Valves\nMitral valve."
    chunks = chunk_text(
        text,
        source_id=SourceId("source-1"),
        revision_id=RevisionId("revision-1"),
        kind=SourceKind.MARKDOWN,
    )

    assert [text[item.start_offset : item.end_offset] for item in chunks] == [
        "# Heart",
        "First paragraph.\nSecond line.",
        "## Valves",
        "Mitral valve.",
    ]
    assert [item.section_path for item in chunks] == [
        ("Heart",),
        ("Heart",),
        ("Heart", "Valves"),
        ("Heart", "Valves"),
    ]
    assert [item.metadata["block_kind"] for item in chunks] == [
        "heading",
        "paragraph",
        "heading",
        "paragraph",
    ]
    assert all(item.chunker_version == CHUNKER_VERSION for item in chunks)


def test_chunks_are_stable_ordered_non_overlapping_and_checksum_exact_spans() -> None:
    text = "alpha beta gamma delta"
    arguments = {
        "source_id": SourceId("source-1"),
        "revision_id": RevisionId("revision-1"),
        "kind": SourceKind.TEXT,
        "config": ChunkingConfig(max_characters=10),
    }
    first = chunk_text(text, **arguments)  # type: ignore[arg-type]
    second = chunk_text(text, **arguments)  # type: ignore[arg-type]

    assert first == second
    assert len(first) > 1
    previous_end = 0
    for ordinal, chunk in enumerate(first):
        resolved = text[chunk.start_offset : chunk.end_offset]
        assert resolved
        assert chunk.ordinal == ordinal
        assert chunk.start_offset >= previous_end
        assert chunk.checksum_sha256 == sha256(resolved.encode()).hexdigest()
        previous_end = chunk.end_offset


def test_chunk_identity_changes_with_revision_or_chunker_configuration() -> None:
    common = {"text": "one paragraph", "source_id": SourceId("source-1"), "kind": SourceKind.TEXT}
    first = chunk_text(
        revision_id=RevisionId("revision-1"),
        config=ChunkingConfig(version="chunker-a"),
        **common,  # type: ignore[arg-type]
    )
    changed_revision = chunk_text(
        revision_id=RevisionId("revision-2"),
        config=ChunkingConfig(version="chunker-a"),
        **common,  # type: ignore[arg-type]
    )
    changed_chunker = chunk_text(
        revision_id=RevisionId("revision-1"),
        config=ChunkingConfig(version="chunker-b"),
        **common,  # type: ignore[arg-type]
    )

    assert first[0].chunk_id != changed_revision[0].chunk_id
    assert first[0].chunk_id != changed_chunker[0].chunk_id


def test_whitespace_only_text_cannot_produce_an_empty_revision() -> None:
    with pytest.raises(ValueError, match="non-whitespace"):
        chunk_text(
            " \n\t",
            source_id=SourceId("source-1"),
            revision_id=RevisionId("revision-1"),
            kind=SourceKind.TEXT,
        )


@pytest.mark.parametrize("marker", ["```", "~~~~"])
def test_markdown_headings_inside_fences_do_not_change_section_path(marker: str) -> None:
    text = f"# Outside ###\n{marker}python\n## Not a heading\n{marker}\n### Jumped ###\nBody"
    chunks = chunk_text(
        text,
        source_id=SourceId("source-1"),
        revision_id=RevisionId("revision-1"),
        kind=SourceKind.MARKDOWN,
    )

    assert [item.metadata["block_kind"] for item in chunks] == [
        "heading",
        "code_fence",
        "heading",
        "paragraph",
    ]
    assert chunks[0].section_path == ("Outside",)
    assert chunks[1].section_path == ("Outside",)
    assert chunks[2].section_path == ("Outside", "Jumped")
    assert chunks[3].section_path == ("Outside", "Jumped")
    assert "Not a heading" in text[chunks[1].start_offset : chunks[1].end_offset]


def test_revision_identity_excludes_descriptive_metadata_but_includes_algorithms() -> None:
    common = {
        "original_sha256": "a" * 64,
        "source_id": SourceId("source-1"),
        "kind": SourceKind.TEXT,
        "normalization_version": "normalizer-v1",
        "chunker_version": "chunker-v1",
        "max_characters": 100,
    }
    first = revision_id_for(
        title="First title", trust_level=10, source_role="primary", **common  # type: ignore[arg-type]
    )
    metadata_changed = revision_id_for(
        title="Changed", trust_level=99, source_role="supplement", **common  # type: ignore[arg-type]
    )
    chunking_changed = revision_id_for(
        title="First title",
        trust_level=10,
        source_role="primary",
        **{**common, "max_characters": 101},  # type: ignore[arg-type]
    )

    assert first == metadata_changed
    assert first != chunking_changed
