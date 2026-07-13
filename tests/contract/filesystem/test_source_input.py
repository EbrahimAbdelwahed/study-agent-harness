from __future__ import annotations

import os
import socket
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

import pytest

import study_agent.adapters.filesystem.source_input as source_input_module
from study_agent.adapters.filesystem import FilesystemSourceInput, SourceInputError
from study_agent.ports import MAX_SOURCE_BYTES, MAX_TOTAL_SOURCES


def _write(root: Path, relative_path: str, content: bytes = b"content") -> Path:
    path = root.joinpath(*relative_path.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _mutate_after_first_read(
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[], None],
) -> None:
    real_read = os.read
    mutated = False

    def read_then_mutate(descriptor: int, count: int) -> bytes:
        nonlocal mutated
        chunk = real_read(descriptor, count)
        if chunk and not mutated:
            mutated = True
            mutation()
        return chunk

    monkeypatch.setattr("study_agent.adapters.filesystem.source_input.os.read", read_then_mutate)


def test_nested_snapshot_captures_exact_strict_utf8_bytes_and_checksum(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sources"
    content = "# Cuore\n\nValvola mitrale: caffè.\n".encode()
    _write(root, "anatomy/cardiac/mitral.md", content)

    snapshot = FilesystemSourceInput(root).snapshot("anatomy/cardiac/mitral.md")

    assert snapshot.relative_path == "anatomy/cardiac/mitral.md"
    assert snapshot.filename == "mitral.md"
    assert snapshot.content == content
    assert snapshot.byte_size == len(content)
    assert snapshot.checksum_sha256 == sha256(content).hexdigest()


def test_snapshot_is_read_only_and_uses_only_read_open_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    source = _write(root, "nested/notes.txt", b"immutable")
    before = {
        path.relative_to(root): (
            path.lstat().st_dev,
            path.lstat().st_ino,
            path.lstat().st_mode,
            path.lstat().st_size,
            path.lstat().st_mtime_ns,
        )
        for path in (root, *root.rglob("*"))
    }
    real_open = os.open
    observed_flags: list[int] = []

    def recording_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        observed_flags.append(flags)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr("study_agent.adapters.filesystem.source_input.os.open", recording_open)

    def forbidden_socket(*args: object, **kwargs: object) -> None:
        pytest.fail("source snapshot attempted a network operation")

    monkeypatch.setattr(socket, "socket", forbidden_socket)

    snapshot = FilesystemSourceInput(root).snapshot("nested/notes.txt")

    after = {
        path.relative_to(root): (
            path.lstat().st_dev,
            path.lstat().st_ino,
            path.lstat().st_mode,
            path.lstat().st_size,
            path.lstat().st_mtime_ns,
        )
        for path in (root, *root.rglob("*"))
    }
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
    assert snapshot.content == source.read_bytes()
    assert observed_flags
    assert all(flags & write_flags == 0 for flags in observed_flags)
    assert before == after


def test_relative_and_absolute_explicit_paths_are_anchored_inside_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sources"
    source = _write(root, "nested/notes.md", b"inside")
    adapter = FilesystemSourceInput(root)

    relative = adapter.snapshot_explicit("nested/notes.md")
    absolute = adapter.snapshot_explicit(source)

    assert relative == absolute
    assert relative.relative_path == "nested/notes.md"
    assert relative.content == b"inside"


@pytest.mark.parametrize(
    "declared",
    ("./notes.md", "nested/../notes.md", "nested//notes.md"),
)
def test_explicit_path_rejects_dot_traversal_and_empty_components(
    tmp_path: Path, declared: str
) -> None:
    root = tmp_path / "sources"
    _write(root, "notes.md", b"inside")

    with pytest.raises(SourceInputError, match="dot, or traversing"):
        FilesystemSourceInput(root).snapshot_explicit(declared)


@pytest.mark.parametrize("outside_form", ("../outside.md", "absolute"))
def test_explicit_path_lexically_outside_root_is_rejected(
    tmp_path: Path, outside_form: str
) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_bytes(b"outside")
    declared: str | Path = outside if outside_form == "absolute" else "../outside.md"

    with pytest.raises(SourceInputError, match=r"lexically inside|traversing"):
        FilesystemSourceInput(root).snapshot_explicit(declared)


def test_symlinked_trusted_root_is_rejected(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    _write(real_root, "notes.md")
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(SourceInputError, match="real directories"):
        FilesystemSourceInput(linked_root).snapshot("notes.md")


@pytest.mark.parametrize("position", ("intermediate", "leaf"))
def test_symlink_components_are_rejected(tmp_path: Path, position: str) -> None:
    root = tmp_path / "sources"
    real = root / "real"
    source = _write(real, "notes.md")
    if position == "intermediate":
        (root / "linked").symlink_to(real, target_is_directory=True)
        declared = "linked/notes.md"
    else:
        (root / "linked.md").symlink_to(source)
        declared = "linked.md"

    with pytest.raises(SourceInputError, match="real directories and a regular file"):
        FilesystemSourceInput(root).snapshot(declared)


def test_file_used_as_parent_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _write(root, "parent", b"not a directory")

    with pytest.raises(SourceInputError, match="real directories and a regular file"):
        FilesystemSourceInput(root).snapshot("parent/notes.md")


@pytest.mark.parametrize("leaf_kind", ("fifo", "socket"))
def test_nonregular_stream_leaf_is_rejected_without_blocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, leaf_kind: str
) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    leaf = root / "stream.md"
    listening_socket: socket.socket | None = None
    if leaf_kind == "fifo":
        os.mkfifo(leaf)
    else:
        listening_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        monkeypatch.chdir(root)
        try:
            listening_socket.bind(leaf.name)
        except PermissionError:
            listening_socket.close()
            pytest.skip("sandbox forbids binding a filesystem Unix socket")
    try:
        with pytest.raises(SourceInputError, match="regular file"):
            FilesystemSourceInput(root).snapshot("stream.md")
    finally:
        if listening_socket is not None:
            listening_socket.close()


@pytest.mark.parametrize(
    ("relative_path", "message"),
    (("missing.md", "real directories"), ("notes.pdf", "relative_path")),
)
def test_missing_and_unsupported_sources_are_rejected(
    tmp_path: Path, relative_path: str, message: str
) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    if relative_path.endswith(".pdf"):
        _write(root, relative_path)

    with pytest.raises(SourceInputError, match=message):
        FilesystemSourceInput(root).snapshot(relative_path)


def test_invalid_utf8_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _write(root, "notes.md", b"valid prefix\xffinvalid")

    with pytest.raises(SourceInputError, match="strict UTF-8"):
        FilesystemSourceInput(root).snapshot("notes.md")


def test_exact_per_file_limit_is_inclusive(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    content = b"x" * MAX_SOURCE_BYTES
    _write(root, "limit.md", content)

    snapshot = FilesystemSourceInput(root).snapshot("limit.md")

    assert snapshot.byte_size == MAX_SOURCE_BYTES
    assert snapshot.checksum_sha256 == sha256(content).hexdigest()


def test_one_byte_over_per_file_limit_is_rejected_before_capture(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    oversized = _write(root, "oversized.md", b"")
    with oversized.open("wb") as stream:
        stream.truncate(MAX_SOURCE_BYTES + 1)

    with pytest.raises(SourceInputError, match="byte limit"):
        FilesystemSourceInput(root).snapshot("oversized.md")


@pytest.mark.parametrize("change", ("grow", "truncate", "overwrite", "nlink"))
def test_in_place_change_during_read_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    root = tmp_path / "sources"
    source = _write(root, "notes.md", b"original bytes")

    def mutate() -> None:
        if change == "grow":
            with source.open("ab") as stream:
                stream.write(b"!")
        elif change == "truncate":
            source.write_bytes(b"")
        elif change == "overwrite":
            source.write_bytes(b"changed! bytes")
        else:
            os.link(source, root / "alias.md")

    _mutate_after_first_read(monkeypatch, mutate)

    with pytest.raises(SourceInputError, match="changed while"):
        FilesystemSourceInput(root).snapshot("notes.md")


def test_leaf_rename_replacement_during_read_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    source = _write(root, "notes.md", b"original")
    replacement = _write(root, "replacement.md", b"replacement")

    def replace_leaf() -> None:
        source.rename(root / "displaced.md")
        replacement.rename(source)

    _mutate_after_first_read(monkeypatch, replace_leaf)

    with pytest.raises(SourceInputError, match="changed while"):
        FilesystemSourceInput(root).snapshot("notes.md")


@pytest.mark.parametrize("component", ("ancestor", "root"))
def test_directory_replacement_during_read_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, component: str
) -> None:
    root = tmp_path / "sources"
    nested = root / "nested"
    _write(root, "nested/notes.md", b"original")

    def replace_directory() -> None:
        if component == "ancestor":
            nested.rename(root / "displaced")
            nested.mkdir()
            (nested / "notes.md").write_bytes(b"replacement")
        else:
            root.rename(tmp_path / "displaced-root")
            root.mkdir()
            _write(root, "nested/notes.md", b"replacement")

    _mutate_after_first_read(monkeypatch, replace_directory)

    with pytest.raises(SourceInputError, match="changed while"):
        FilesystemSourceInput(root).snapshot("nested/notes.md")


@pytest.mark.parametrize("component", ("ancestor", "root"))
def test_full_path_rebinding_rejects_component_swapped_after_it_is_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, component: str
) -> None:
    root = tmp_path / "sources"
    nested = root / "nested"
    _write(root, "nested/notes.md", b"safe original")
    real_open = os.open
    swapped = False

    def swapping_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        should_swap = (component == "ancestor" and path == "nested" and dir_fd is not None) or (
            component == "root" and path == root and dir_fd is None
        )
        if should_swap and not swapped:
            swapped = True
            if component == "ancestor":
                nested.rename(root / "displaced")
                nested.mkdir()
                (nested / "notes.md").write_bytes(b"replacement")
            else:
                root.rename(tmp_path / "displaced-root")
                root.mkdir()
                _write(root, "nested/notes.md", b"replacement")
        return descriptor

    monkeypatch.setattr("study_agent.adapters.filesystem.source_input.os.open", swapping_open)

    with pytest.raises(SourceInputError, match="changed while"):
        FilesystemSourceInput(root).snapshot("nested/notes.md")
    assert swapped is True


def test_open_flags_are_nofollow_directory_aware_and_nonblocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    _write(root, "nested/notes.md")
    real_open = os.open
    calls: list[
        tuple[
            str | bytes | os.PathLike[str] | os.PathLike[bytes],
            int,
            int | None,
        ]
    ] = []

    def recording_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        calls.append((path, flags, dir_fd))
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr("study_agent.adapters.filesystem.source_input.os.open", recording_open)

    FilesystemSourceInput(root).snapshot("nested/notes.md")

    root_calls = [call for call in calls if call[0] == root]
    directory_calls = [call for call in calls if call[0] == "nested"]
    leaf_calls = [call for call in calls if call[0] == "notes.md"]
    assert len(root_calls) == 2
    assert len(directory_calls) == 2
    assert len(leaf_calls) == 2
    assert all(flags & os.O_NOFOLLOW for _, flags, _ in calls)
    assert all(flags & os.O_NONBLOCK for _, flags, _ in calls)
    assert all(flags & os.O_DIRECTORY for _, flags, _ in root_calls + directory_calls)
    assert all(flags & os.O_DIRECTORY == 0 for _, flags, _ in leaf_calls)
    assert all(dir_fd is not None for _, _, dir_fd in directory_calls + leaf_calls)


def test_batch_preserves_declared_order(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _write(root, "third.md", b"3")
    _write(root, "first.md", b"1")
    _write(root, "second.md", b"2")

    snapshots = FilesystemSourceInput(root).snapshots(("third.md", "first.md", "second.md"))

    assert tuple(snapshot.relative_path for snapshot in snapshots) == (
        "third.md",
        "first.md",
        "second.md",
    )
    assert tuple(snapshot.content for snapshot in snapshots) == (b"3", b"1", b"2")


def test_batch_count_limit_is_checked_before_any_source_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    adapter = FilesystemSourceInput(root)

    def forbidden_snapshot(relative_path: str) -> None:
        pytest.fail(f"snapshot I/O attempted for {relative_path}")

    monkeypatch.setattr(adapter, "snapshot", forbidden_snapshot)

    with pytest.raises(SourceInputError, match="source count"):
        adapter.snapshots(("notes.md",) * (MAX_TOTAL_SOURCES + 1))


def test_batch_aggregate_limit_is_inclusive_and_one_byte_over_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    _write(root, "first.md", b"abc")
    _write(root, "second.md", b"def")
    _write(root, "over.md", b"defg")
    monkeypatch.setattr(source_input_module, "MAX_TOTAL_SOURCE_BYTES", 6)
    adapter = FilesystemSourceInput(root)

    inclusive = adapter.snapshots(("first.md", "second.md"))

    assert sum(snapshot.byte_size for snapshot in inclusive) == 6
    with pytest.raises(SourceInputError, match="aggregate limit"):
        adapter.snapshots(("first.md", "over.md"))
