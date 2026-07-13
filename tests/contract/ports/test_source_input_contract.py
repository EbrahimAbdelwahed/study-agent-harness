from __future__ import annotations

import inspect
from collections.abc import Sequence
from dataclasses import FrozenInstanceError, fields
from hashlib import sha256
from typing import get_type_hints

import pytest

from study_agent.ports import (
    MAX_SOURCE_BYTES,
    MAX_TOTAL_SOURCE_BYTES,
    MAX_TOTAL_SOURCES,
    SourceInputPort,
    SourceSnapshot,
)


def _snapshot(relative_path: str, content: bytes) -> SourceSnapshot:
    return SourceSnapshot(
        relative_path=relative_path,
        content=content,
        checksum_sha256=sha256(content).hexdigest(),
        byte_size=len(content),
    )


def test_public_source_bounds_are_pinned() -> None:
    assert MAX_SOURCE_BYTES == 16 * 1024 * 1024
    assert MAX_TOTAL_SOURCES == 4096
    assert MAX_TOTAL_SOURCE_BYTES == 512 * 1024 * 1024


def test_source_input_port_has_only_single_and_batch_snapshot_operations() -> None:
    public_callables = {
        name: member
        for name, member in inspect.getmembers(SourceInputPort, inspect.isfunction)
        if not name.startswith("_")
    }

    assert set(public_callables) == {"snapshot", "snapshots"}
    assert tuple(inspect.signature(public_callables["snapshot"]).parameters) == (
        "self",
        "relative_path",
    )
    assert tuple(inspect.signature(public_callables["snapshots"]).parameters) == (
        "self",
        "relative_paths",
    )
    assert get_type_hints(public_callables["snapshot"]) == {
        "relative_path": str,
        "return": SourceSnapshot,
    }
    assert get_type_hints(public_callables["snapshots"]) == {
        "relative_paths": Sequence[str],
        "return": tuple[SourceSnapshot, ...],
    }


def test_source_snapshot_is_frozen_slotted_and_exposes_exact_captured_values() -> None:
    content = b"# Heart\n\nMitral valve."
    snapshot = _snapshot("cardiology/valves/mitral.md", content)

    assert tuple(field.name for field in fields(SourceSnapshot)) == (
        "relative_path",
        "content",
        "checksum_sha256",
        "byte_size",
    )
    assert snapshot.relative_path == "cardiology/valves/mitral.md"
    assert snapshot.filename == "mitral.md"
    assert snapshot.content is content
    assert snapshot.byte_size == len(content)
    assert snapshot.checksum_sha256 == sha256(content).hexdigest()
    assert not hasattr(snapshot, "__dict__")
    with pytest.raises(FrozenInstanceError):
        snapshot.byte_size = 0  # type: ignore[misc]


@pytest.mark.parametrize(
    "relative_path",
    [
        "notes.txt",
        "anatomy/cardiac-cycle.md",
        "year_2/semester-2/lesson 01/café.md",
        "x" * 253 + ".md",
    ],
)
def test_portable_nested_txt_and_md_paths_are_accepted(relative_path: str) -> None:
    assert _snapshot(relative_path, b"content").relative_path == relative_path


def test_empty_and_exact_per_file_limit_are_inclusive() -> None:
    empty = _snapshot("empty.txt", b"")
    content_at_limit = b"x" * MAX_SOURCE_BYTES
    at_limit = _snapshot("limit.md", content_at_limit)

    assert empty.byte_size == 0
    assert empty.checksum_sha256 == sha256(b"").hexdigest()
    assert at_limit.byte_size == MAX_SOURCE_BYTES
    assert at_limit.content is content_at_limit


def test_content_over_per_file_limit_is_rejected() -> None:
    content = b"x" * (MAX_SOURCE_BYTES + 1)

    with pytest.raises(ValueError, match="byte_size"):
        _snapshot("too-large.md", content)


@pytest.mark.parametrize("byte_size", [-1, 4, True, 1.0, "3"])
def test_forged_or_invalid_byte_size_is_rejected(byte_size: object) -> None:
    content = b"abc"

    with pytest.raises(ValueError, match="byte_size"):
        SourceSnapshot(
            "notes.md",
            content,
            sha256(content).hexdigest(),
            byte_size,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "content",
    [bytearray(b"abc"), memoryview(b"abc"), "abc", None],
)
def test_content_must_be_exactly_bytes(content: object) -> None:
    with pytest.raises(ValueError, match="content must be bytes"):
        SourceSnapshot(
            "notes.md",
            content,  # type: ignore[arg-type]
            sha256(b"abc").hexdigest(),
            3,
        )


def test_content_must_be_strict_utf8() -> None:
    content = b"\xff"
    with pytest.raises(ValueError, match="strict UTF-8"):
        SourceSnapshot(
            "notes.md",
            content,
            sha256(content).hexdigest(),
            len(content),
        )


@pytest.mark.parametrize(
    "checksum",
    [
        sha256(b"different").hexdigest(),
        sha256(b"abc").hexdigest().upper(),
        "g" * 64,
        "a" * 63,
        "a" * 65,
        " sha256",
        b"a" * 64,
        None,
    ],
)
def test_checksum_must_be_exact_lowercase_sha256_of_content(checksum: object) -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        SourceSnapshot(
            "notes.md",
            b"abc",
            checksum,  # type: ignore[arg-type]
            3,
        )


@pytest.mark.parametrize(
    "relative_path",
    [
        "",
        "/absolute.md",
        "\\absolute.md",
        ".",
        "..",
        "./notes.md",
        "notes/./item.md",
        "notes/../item.md",
        "notes\\item.md",
        "C:notes.md",
        "notes:item.md",
        "notes\x00.md",
        "notes\nitem.md",
        "notes/zero\u200bwidth.md",
        " notes.md",
        "notes.md ",
        "notes//item.md",
        "notes/.hidden./item.md",
        "notes/trailing /item.md",
        "CON.md",
        "con.txt",
        "aux/notes.md",
        "LPT9.txt",
        "com1.anything.md",
        "notes.pdf",
        "notes.MD",
        "notes.Txt",
        "x" * 254 + ".md",
    ],
)
def test_non_portable_or_unsupported_source_paths_are_rejected(relative_path: str) -> None:
    with pytest.raises(ValueError, match="relative_path"):
        _snapshot(relative_path, b"content")


@pytest.mark.parametrize("relative_path", [None, b"notes.md", 1, True])
def test_relative_path_must_be_text(relative_path: object) -> None:
    with pytest.raises(ValueError, match="relative_path"):
        SourceSnapshot(
            relative_path,  # type: ignore[arg-type]
            b"content",
            sha256(b"content").hexdigest(),
            7,
        )
