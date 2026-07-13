from __future__ import annotations

import os
import signal
from pathlib import Path

import pytest

from study_agent.cli.commands import _DeferredSigint, _read_source


def test_source_read_rejects_symlink_leaf_and_ancestor(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    real = root / "real"
    real.mkdir()
    source = real / "source.md"
    source.write_text("content")
    leaf = root / "leaf.md"
    leaf.symlink_to(source)
    ancestor = root / "linked"
    ancestor.symlink_to(real, target_is_directory=True)

    with pytest.raises(ValueError, match="real repository directories"):
        _read_source(root, str(leaf))
    with pytest.raises(ValueError, match="real repository directories"):
        _read_source(root, str(ancestor / "source.md"))


def test_source_read_rejects_resolved_escape(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("content")
    with pytest.raises(ValueError, match="inside the repository"):
        _read_source(root, str(outside))


def test_relative_source_is_anchored_to_repository_not_process_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    (root / "source.md").write_bytes(b"repository content")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "source.md").write_bytes(b"wrong cwd content")
    monkeypatch.chdir(elsewhere)
    path, content = _read_source(root, "source.md")
    assert path == root / "source.md"
    assert content == b"repository content"


def test_descriptor_walk_cannot_escape_when_opened_ancestor_is_swapped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (nested / "source.md").write_bytes(b"safe original")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "source.md").write_bytes(b"escaped content")
    actual_open = os.open
    swapped = False

    def swapping_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        descriptor = actual_open(path, flags, mode, dir_fd=dir_fd)
        if path == "nested" and dir_fd is not None and not swapped:
            nested.rename(root / "nested-original")
            nested.symlink_to(outside, target_is_directory=True)
            swapped = True
        return descriptor

    monkeypatch.setattr(os, "open", swapping_open)
    _, content = _read_source(root, "nested/source.md")
    assert swapped is True
    assert content == b"safe original"


def test_source_read_rejects_sparse_oversized_file_without_reading_it(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    oversized = root / "oversized.md"
    with oversized.open("wb") as stream:
        stream.truncate(16 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="byte limit"):
        _read_source(root, str(oversized))


def test_source_read_rejects_growth_detected_after_bounded_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    source = root / "source.md"
    source.write_bytes(b"stable")
    actual_fstat = os.fstat
    calls = 0

    def growing_fstat(descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        result = actual_fstat(descriptor)
        if calls == 2:
            values = list(result)
            values[6] = result.st_size + 1
            return os.stat_result(values)
        return result

    monkeypatch.setattr(os, "fstat", growing_fstat)
    with pytest.raises(ValueError, match="changed while"):
        _read_source(root, str(source))


def test_automatic_ask_region_defers_injected_sigint_until_atomic_operation_finishes() -> None:
    mutations: list[str] = []
    deferred = _DeferredSigint(enabled=True)
    with deferred:
        mutations.append("session-started")
        os.kill(os.getpid(), signal.SIGINT)
        mutations.extend(("run-created", "answer-committed"))
    assert mutations == ["session-started", "run-created", "answer-committed"]
    assert deferred.pending is True
