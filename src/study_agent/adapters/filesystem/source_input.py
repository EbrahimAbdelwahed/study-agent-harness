"""Read-only, descriptor-anchored capture of local source files."""

from __future__ import annotations

import os
import stat
from collections.abc import Sequence
from contextlib import suppress
from hashlib import sha256
from pathlib import Path

from study_agent.ports.source_input import (
    MAX_SOURCE_BYTES,
    MAX_TOTAL_SOURCE_BYTES,
    MAX_TOTAL_SOURCES,
    SourceSnapshot,
)

_DIRECTORY_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NONBLOCK", 0)
)
_SOURCE_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NONBLOCK", 0)
)
_EMPTY_SHA256 = sha256(b"").hexdigest()

_DirectoryIdentity = tuple[int, int]
_FileIdentity = tuple[int, int, int, int, int, int, int]


class SourceInputError(ValueError):
    """A source declaration could not be captured safely and exactly."""


class FilesystemSourceInput:
    """Capture immutable source bytes beneath one trusted local root."""

    def __init__(self, trusted_root: str | Path) -> None:
        raw = os.fspath(trusted_root)
        if not isinstance(raw, str) or not raw:
            raise SourceInputError("trusted source root must be a local path")
        self._trusted_root = Path(os.path.abspath(os.path.expanduser(raw)))

    @property
    def trusted_root(self) -> Path:
        """Return the normalized lexical root without resolving symlinks."""

        return self._trusted_root

    def snapshot(self, relative_path: str) -> SourceSnapshot:
        """Capture one stable, strict UTF-8 source by portable relative path."""

        _validate_snapshot_path(relative_path)
        parts = tuple(relative_path.split("/"))
        descriptors: list[int] = []
        try:
            root_descriptor = os.open(self._trusted_root, _DIRECTORY_OPEN_FLAGS)
            descriptors.append(root_descriptor)
            root_identity = _directory_identity(root_descriptor)

            directory_identities: list[_DirectoryIdentity] = []
            parent_descriptor = root_descriptor
            for component in parts[:-1]:
                descriptor = os.open(
                    component,
                    _DIRECTORY_OPEN_FLAGS,
                    dir_fd=parent_descriptor,
                )
                descriptors.append(descriptor)
                directory_identities.append(_directory_identity(descriptor))
                parent_descriptor = descriptor

            source_descriptor = os.open(
                parts[-1],
                _SOURCE_OPEN_FLAGS,
                dir_fd=parent_descriptor,
            )
            descriptors.append(source_descriptor)
            before = os.fstat(source_descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise SourceInputError("source path must identify a regular file")
            if before.st_size > MAX_SOURCE_BYTES:
                raise SourceInputError(
                    f"source file exceeds the {MAX_SOURCE_BYTES}-byte limit"
                )

            content = _read_bounded(source_descriptor)
            after = os.fstat(source_descriptor)
            if (
                _file_identity(after) != _file_identity(before)
                or after.st_size != len(content)
            ):
                raise SourceInputError("source file changed while it was being read")
            if len(content) > MAX_SOURCE_BYTES:
                raise SourceInputError(
                    f"source file exceeds the {MAX_SOURCE_BYTES}-byte limit"
                )
            try:
                content.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise SourceInputError("source file must contain strict UTF-8 text") from None

            _verify_path_binding(
                self._trusted_root,
                parts,
                root_identity,
                tuple(directory_identities),
                _file_identity(after),
            )
        except SourceInputError:
            raise
        except OSError:
            raise SourceInputError(
                "source path must contain only real directories and a regular file"
            ) from None
        finally:
            for descriptor in reversed(descriptors):
                with suppress(OSError):
                    os.close(descriptor)

        return SourceSnapshot(
            relative_path=relative_path,
            content=content,
            checksum_sha256=sha256(content).hexdigest(),
            byte_size=len(content),
        )

    def snapshots(self, relative_paths: Sequence[str]) -> tuple[SourceSnapshot, ...]:
        """Capture a bounded sequence in its declared order."""

        if isinstance(relative_paths, (str, bytes)):
            raise SourceInputError("source paths must be a sequence of paths")
        if len(relative_paths) > MAX_TOTAL_SOURCES:
            raise SourceInputError(
                f"source count exceeds the {MAX_TOTAL_SOURCES}-file limit"
            )
        declared = tuple(relative_paths)
        for relative_path in declared:
            _validate_snapshot_path(relative_path)

        captured: list[SourceSnapshot] = []
        total_bytes = 0
        for relative_path in declared:
            snapshot = self.snapshot(relative_path)
            total_bytes += snapshot.byte_size
            if total_bytes > MAX_TOTAL_SOURCE_BYTES:
                raise SourceInputError(
                    "source bytes exceed the "
                    f"{MAX_TOTAL_SOURCE_BYTES}-byte aggregate limit"
                )
            captured.append(snapshot)
        return tuple(captured)

    def snapshot_explicit(self, path: str | Path) -> SourceSnapshot:
        """Capture a trusted-host path that is lexically inside this root."""

        raw = os.fspath(path)
        if not isinstance(raw, str) or not raw:
            raise SourceInputError("source path must be a local path")
        expanded = os.path.expanduser(raw)
        _, lexical_tail = os.path.splitdrive(expanded)
        lexical_parts = lexical_tail.split(os.sep)
        if os.path.isabs(expanded):
            lexical_parts = lexical_parts[1:]
        if any(component in {"", ".", ".."} for component in lexical_parts):
            raise SourceInputError(
                "source path must not contain empty, dot, or traversing components"
            )
        candidate = (
            os.path.abspath(expanded)
            if os.path.isabs(expanded)
            else os.path.abspath(os.path.join(self._trusted_root, expanded))
        )
        try:
            relative = os.path.relpath(candidate, self._trusted_root)
        except ValueError:
            raise SourceInputError(
                "source path must be lexically inside the trusted root"
            ) from None
        if relative == os.pardir or relative.startswith(os.pardir + os.sep):
            raise SourceInputError(
                "source path must be lexically inside the trusted root"
            )
        return self.snapshot(relative.replace(os.sep, "/"))


def _validate_snapshot_path(relative_path: object) -> None:
    """Apply the value object's exact portable-path contract before any I/O."""

    if not isinstance(relative_path, str):
        raise SourceInputError(
            "source snapshot relative_path must be a portable relative path"
        )
    try:
        SourceSnapshot(
            relative_path=relative_path,
            content=b"",
            checksum_sha256=_EMPTY_SHA256,
            byte_size=0,
        )
    except ValueError as error:
        raise SourceInputError(str(error)) from None


def _read_bounded(descriptor: int) -> bytes:
    remaining = MAX_SOURCE_BYTES + 1
    chunks: list[bytes] = []
    while remaining:
        chunk = os.read(descriptor, min(1024 * 1024, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _verify_path_binding(
    trusted_root: Path,
    parts: tuple[str, ...],
    expected_root: _DirectoryIdentity,
    expected_directories: tuple[_DirectoryIdentity, ...],
    expected_source: _FileIdentity,
) -> None:
    descriptors: list[int] = []
    try:
        root_descriptor = os.open(trusted_root, _DIRECTORY_OPEN_FLAGS)
        descriptors.append(root_descriptor)
        if _directory_identity(root_descriptor) != expected_root:
            raise SourceInputError("source path changed while it was being read")

        parent_descriptor = root_descriptor
        for component, expected in zip(
            parts[:-1], expected_directories, strict=True
        ):
            descriptor = os.open(
                component,
                _DIRECTORY_OPEN_FLAGS,
                dir_fd=parent_descriptor,
            )
            descriptors.append(descriptor)
            if _directory_identity(descriptor) != expected:
                raise SourceInputError("source path changed while it was being read")
            parent_descriptor = descriptor

        source_descriptor = os.open(
            parts[-1],
            _SOURCE_OPEN_FLAGS,
            dir_fd=parent_descriptor,
        )
        descriptors.append(source_descriptor)
        rebound = os.fstat(source_descriptor)
        if not stat.S_ISREG(rebound.st_mode) or _file_identity(rebound) != expected_source:
            raise SourceInputError("source path changed while it was being read")
        bound = os.stat(parts[-1], dir_fd=parent_descriptor, follow_symlinks=False)
        if _file_identity(bound) != expected_source:
            raise SourceInputError("source path changed while it was being read")
    except SourceInputError:
        raise
    except OSError:
        raise SourceInputError("source path changed while it was being read") from None
    finally:
        for descriptor in reversed(descriptors):
            with suppress(OSError):
                os.close(descriptor)


def _directory_identity(descriptor: int) -> _DirectoryIdentity:
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        raise SourceInputError("source path contains a non-directory component")
    return metadata.st_dev, metadata.st_ino


def _file_identity(metadata: os.stat_result) -> _FileIdentity:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


__all__ = ["FilesystemSourceInput", "SourceInputError"]
