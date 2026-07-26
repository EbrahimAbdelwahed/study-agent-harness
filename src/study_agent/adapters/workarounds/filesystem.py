"""Descriptor-anchored local PDF input and no-clobber Markdown output."""

from __future__ import annotations

import os
import secrets
import stat
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from hashlib import sha256
from pathlib import Path
from typing import NamedTuple

MAX_PDF_BYTES = 16 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
_MAX_PATH_LENGTH = 256
_MAX_COMPONENT_UTF8_BYTES = 255
_FORBIDDEN_PORTABLE_CHARS = frozenset('?*<>"|')
_WINDOWS_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)

_DIRECTORY_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NONBLOCK", 0)
)
_READ_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NONBLOCK", 0)
)
_OUTPUT_OPEN_FLAGS = (
    os.O_WRONLY
    | os.O_CREAT
    | os.O_EXCL
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
)

_DirectoryIdentity = tuple[int, int]
_StableIdentity = tuple[int, int]
_Identity = tuple[int, int, int, int, int, int, int]


class PdfMarkdownFilesystemError(ValueError):
    """A trusted local binding could not be read or safely published."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CapturedPdf(NamedTuple):
    """Bytes and descriptor identity captured in one binding operation."""

    content: bytes
    identity: _StableIdentity


class _StagingState(NamedTuple):
    content: bytes
    metadata: os.stat_result


class _ExistingOutput(NamedTuple):
    content: bytes
    identity: _Identity

    @property
    def stable_identity(self) -> _StableIdentity:
        return self.identity[0], self.identity[1]


def validate_portable_path(path: str, *, suffix: str) -> tuple[str, ...]:
    """Validate one relative path before any filesystem operation."""

    if (
        not isinstance(path, str)
        or not path
        or path != path.strip()
        or len(path) > _MAX_PATH_LENGTH
        or path.startswith(("/", "\\"))
        or "\\" in path
        or ":" in path
        or any(character in _FORBIDDEN_PORTABLE_CHARS for character in path)
        or any(unicodedata.category(character).startswith("C") for character in path)
    ):
        raise PdfMarkdownFilesystemError("invalid_portable_path")
    parts = tuple(path.split("/"))
    if any(
        not part
        or part in {".", ".."}
        or part.endswith((" ", "."))
        or part.split(".", 1)[0].upper() in _WINDOWS_DEVICE_NAMES
        for part in parts
    ):
        raise PdfMarkdownFilesystemError("invalid_portable_path")
    if any(len(part.encode("utf-8")) > _MAX_COMPONENT_UTF8_BYTES for part in parts):
        raise PdfMarkdownFilesystemError("invalid_portable_path")
    if parts[-1].lower() != parts[-1] or not parts[-1].endswith(suffix):
        raise PdfMarkdownFilesystemError("invalid_portable_path")
    return parts


def _directory_identity(metadata: os.stat_result) -> _DirectoryIdentity:
    if not stat.S_ISDIR(metadata.st_mode):
        raise PdfMarkdownFilesystemError("trusted_root_not_directory")
    return metadata.st_dev, metadata.st_ino


def _file_identity(metadata: os.stat_result) -> _Identity:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _open_root(root: Path, expected: _DirectoryIdentity) -> int:
    try:
        descriptor = os.open(root, _DIRECTORY_OPEN_FLAGS)
        if _directory_identity(os.fstat(descriptor)) != expected:
            os.close(descriptor)
            raise PdfMarkdownFilesystemError("trusted_root_rebound")
        return descriptor
    except PdfMarkdownFilesystemError:
        raise
    except OSError:
        raise PdfMarkdownFilesystemError("trusted_root_unavailable") from None


@contextmanager
def _open_parent(
    root: Path, expected: _DirectoryIdentity, parts: tuple[str, ...]
) -> Iterator[tuple[int, tuple[_DirectoryIdentity, ...]]]:
    descriptors: list[int] = []
    identities: list[_DirectoryIdentity] = [expected]
    try:
        root_descriptor = _open_root(root, expected)
        descriptors.append(root_descriptor)
        parent = root_descriptor
        for component in parts[:-1]:
            try:
                child = os.open(component, _DIRECTORY_OPEN_FLAGS, dir_fd=parent)
                metadata = os.fstat(child)
                _directory_identity(metadata)
            except PdfMarkdownFilesystemError:
                raise
            except OSError:
                raise PdfMarkdownFilesystemError("path_component_not_directory") from None
            descriptors.append(child)
            parent = child
            identities.append(_directory_identity(metadata))
        yield parent, tuple(identities)
    finally:
        for descriptor in reversed(descriptors):
            with suppress(OSError):
                os.close(descriptor)


def _read_bounded(descriptor: int, limit: int) -> bytes:
    remaining = limit + 1
    chunks: list[bytes] = []
    while remaining:
        try:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
        except OSError:
            raise PdfMarkdownFilesystemError("input_read_failed") from None
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    content = b"".join(chunks)
    if len(content) > limit:
        raise PdfMarkdownFilesystemError("input_size_limit_exceeded")
    return content


def capture_pdf(
    root: Path, root_identity: _DirectoryIdentity, relative_path: str
) -> CapturedPdf:
    """Capture an exact regular PDF by descriptor and verify its name binding."""

    parts = validate_portable_path(relative_path, suffix=".pdf")
    descriptors: list[int] = []
    try:
        root_descriptor = _open_root(root, root_identity)
        descriptors.append(root_descriptor)
        parent = root_descriptor
        expected_directories: list[_DirectoryIdentity] = []
        for component in parts[:-1]:
            try:
                descriptor = os.open(component, _DIRECTORY_OPEN_FLAGS, dir_fd=parent)
                metadata = os.fstat(descriptor)
                _directory_identity(metadata)
            except PdfMarkdownFilesystemError:
                raise
            except OSError:
                raise PdfMarkdownFilesystemError("path_component_not_directory") from None
            descriptors.append(descriptor)
            expected_directories.append(_directory_identity(metadata))
            parent = descriptor
        try:
            descriptor = os.open(parts[-1], _READ_OPEN_FLAGS, dir_fd=parent)
            descriptors.append(descriptor)
            before = os.fstat(descriptor)
        except OSError:
            raise PdfMarkdownFilesystemError("input_not_regular_file") from None
        if not stat.S_ISREG(before.st_mode):
            raise PdfMarkdownFilesystemError("input_not_regular_file")
        if before.st_size > MAX_PDF_BYTES:
            raise PdfMarkdownFilesystemError("input_size_limit_exceeded")
        content = _read_bounded(descriptor, MAX_PDF_BYTES)
        after = os.fstat(descriptor)
        if _file_identity(before) != _file_identity(after) or after.st_size != len(content):
            raise PdfMarkdownFilesystemError("input_changed_while_reading")
        if not content.startswith(PDF_MAGIC):
            raise PdfMarkdownFilesystemError("input_not_pdf")
        # Re-open every component and compare identities.  This closes the
        # lexical name-to-descriptor gap after the bounded read.
        _verify_input_binding(
            root, root_identity, parts, tuple(expected_directories), _file_identity(after)
        )
        return CapturedPdf(content, _stable_identity(after))
    except PdfMarkdownFilesystemError:
        raise
    except OSError:
        raise PdfMarkdownFilesystemError("input_unavailable") from None
    finally:
        for descriptor in reversed(descriptors):
            with suppress(OSError):
                os.close(descriptor)


def _verify_input_binding(
    root: Path,
    expected_root: _DirectoryIdentity,
    parts: tuple[str, ...],
    expected_directories: tuple[_DirectoryIdentity, ...],
    expected_file: _Identity,
) -> None:
    descriptors: list[int] = []
    try:
        root_descriptor = _open_root(root, expected_root)
        descriptors.append(root_descriptor)
        parent = root_descriptor
        for component, expected in zip(parts[:-1], expected_directories, strict=True):
            descriptor = os.open(component, _DIRECTORY_OPEN_FLAGS, dir_fd=parent)
            descriptors.append(descriptor)
            if _directory_identity(os.fstat(descriptor)) != expected:
                raise PdfMarkdownFilesystemError("input_path_rebound")
            parent = descriptor
        descriptor = os.open(parts[-1], _READ_OPEN_FLAGS, dir_fd=parent)
        descriptors.append(descriptor)
        rebound = os.fstat(descriptor)
        bound = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        if (
            not stat.S_ISREG(rebound.st_mode)
            or _file_identity(rebound) != expected_file
            or _file_identity(bound) != expected_file
        ):
            raise PdfMarkdownFilesystemError("input_path_rebound")
    except PdfMarkdownFilesystemError:
        raise
    except OSError:
        raise PdfMarkdownFilesystemError("input_path_rebound") from None
    finally:
        for descriptor in reversed(descriptors):
            with suppress(OSError):
                os.close(descriptor)


def _verify_parent_binding(
    root: Path,
    expected_root: _DirectoryIdentity,
    parts: tuple[str, ...],
    expected_chain: tuple[_DirectoryIdentity, ...],
) -> None:
    """Re-walk the lexical parent chain and reject any directory rebound."""

    if len(expected_chain) != len(parts) or expected_chain[0] != expected_root:
        raise PdfMarkdownFilesystemError("output_path_rebound")
    descriptors: list[int] = []
    try:
        root_descriptor = _open_root(root, expected_root)
        descriptors.append(root_descriptor)
        parent = root_descriptor
        for component, expected in zip(parts[:-1], expected_chain[1:], strict=True):
            descriptor = os.open(component, _DIRECTORY_OPEN_FLAGS, dir_fd=parent)
            descriptors.append(descriptor)
            if _directory_identity(os.fstat(descriptor)) != expected:
                raise PdfMarkdownFilesystemError("output_path_rebound")
            parent = descriptor
    except PdfMarkdownFilesystemError:
        raise
    except OSError:
        raise PdfMarkdownFilesystemError("output_path_rebound") from None
    finally:
        for descriptor in reversed(descriptors):
            with suppress(OSError):
                os.close(descriptor)


def _stable_identity(metadata: os.stat_result) -> _StableIdentity:
    return metadata.st_dev, metadata.st_ino


def _staging_name(destination: str, output: bytes) -> str:
    """Derive a bounded, destination- and content-specific staging name."""

    destination_digest = sha256(destination.encode("utf-8")).hexdigest()
    output_digest = sha256(output).hexdigest()
    return f".{destination_digest}.{output_digest}.tmp"


def _read_staging(
    parent: int, name: str, limit: int
) -> _StagingState | None:
    """Read a deterministic staging link without following symlinks."""

    try:
        bound = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        raise PdfMarkdownFilesystemError("output_unavailable") from None
    if not stat.S_ISREG(bound.st_mode) or bound.st_nlink not in (1, 2):
        raise PdfMarkdownFilesystemError("output_collision")
    try:
        descriptor = os.open(name, _READ_OPEN_FLAGS, dir_fd=parent)
    except OSError:
        raise PdfMarkdownFilesystemError("output_collision") from None
    try:
        metadata = os.fstat(descriptor)
        if _file_identity(metadata) != _file_identity(bound):
            raise PdfMarkdownFilesystemError("output_rebound")
        content = _read_bounded(descriptor, limit)
        if _file_identity(os.fstat(descriptor)) != _file_identity(bound):
            raise PdfMarkdownFilesystemError("output_rebound")
        try:
            final = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except OSError:
            raise PdfMarkdownFilesystemError("output_rebound") from None
        if (
            not stat.S_ISREG(final.st_mode)
            or final.st_nlink not in (1, 2)
            or _file_identity(final) != _file_identity(bound)
        ):
            raise PdfMarkdownFilesystemError("output_rebound")
        return _StagingState(content, final)
    finally:
        with suppress(OSError):
            os.close(descriptor)


def _unlink_staging(parent: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=parent)
        os.fsync(parent)
    except OSError:
        raise PdfMarkdownFilesystemError("output_publish_failed") from None


def _cleanup_private_temp(
    parent: int, name: str | None, identity: _StableIdentity | None
) -> None:
    """Remove only the private inode created by this publication attempt."""

    if name is None or identity is None:
        return
    try:
        metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except OSError:
        return
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink not in (1, 2)
        or _stable_identity(metadata) != identity
    ):
        return
    try:
        os.unlink(name, dir_fd=parent)
        os.fsync(parent)
    except OSError:
        return


def _find_reserved_private(
    parent: int, staging_name: str, identity: _StableIdentity
) -> str | None:
    """Find the sole private link reserved for a deterministic stage inode."""

    prefix = f"{staging_name}."
    suffix = ".private"
    try:
        entries = os.listdir(parent)
    except OSError:
        raise PdfMarkdownFilesystemError("output_unavailable") from None
    matches: list[str] = []
    for entry in entries:
        if not entry.startswith(prefix) or not entry.endswith(suffix):
            continue
        token = entry[len(prefix) : -len(suffix)]
        if len(token) != 24 or any(character not in "0123456789abcdef" for character in token):
            continue
        try:
            metadata = os.stat(entry, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError:
            raise PdfMarkdownFilesystemError("output_unavailable") from None
        if (
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_nlink == 2
            and _stable_identity(metadata) == identity
        ):
            matches.append(entry)
    if len(matches) > 1:
        raise PdfMarkdownFilesystemError("output_collision")
    return matches[0] if matches else None


def _read_existing_output(
    parent: int, name: str, limit: int
) -> _ExistingOutput | None:
    try:
        bound = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        raise PdfMarkdownFilesystemError("output_unavailable") from None
    if not stat.S_ISREG(bound.st_mode):
        raise PdfMarkdownFilesystemError("output_collision")
    if bound.st_nlink != 1:
        raise PdfMarkdownFilesystemError("output_collision")
    try:
        descriptor = os.open(name, _READ_OPEN_FLAGS, dir_fd=parent)
    except OSError:
        raise PdfMarkdownFilesystemError("output_collision") from None
    try:
        metadata = os.fstat(descriptor)
        if _file_identity(metadata) != _file_identity(bound):
            raise PdfMarkdownFilesystemError("output_rebound")
        content = _read_bounded(descriptor, limit)
        if _file_identity(os.fstat(descriptor)) != _file_identity(bound):
            raise PdfMarkdownFilesystemError("output_rebound")
        try:
            final = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except OSError:
            raise PdfMarkdownFilesystemError("output_rebound") from None
        if (
            not stat.S_ISREG(final.st_mode)
            or final.st_nlink != 1
            or _file_identity(final) != _file_identity(bound)
        ):
            raise PdfMarkdownFilesystemError("output_rebound")
        return _ExistingOutput(content, _file_identity(bound))
    finally:
        with suppress(OSError):
            os.close(descriptor)


def publish_markdown(
    root: Path,
    root_identity: _DirectoryIdentity,
    relative_path: str,
    output: bytes,
    *,
    output_limit: int,
    input_identity: _StableIdentity | None = None,
) -> bytes:
    """Publish output privately and atomically without replacing a destination."""

    if len(output) > output_limit:
        raise PdfMarkdownFilesystemError("output_size_limit_exceeded")
    parts = validate_portable_path(relative_path, suffix=".md")
    with _open_parent(root, root_identity, parts) as (parent, directory_chain):
        _verify_parent_binding(root, root_identity, parts, directory_chain)
        destination_name = parts[-1]
        staging_name = _staging_name(destination_name, output)
        staging = _read_staging(parent, staging_name, output_limit)
        staging_identity: _StableIdentity | None = None
        if staging is not None:
            if staging.content != output:
                raise PdfMarkdownFilesystemError("output_collision")
            staging_identity = _stable_identity(staging.metadata)
            if staging.metadata.st_nlink == 2:
                try:
                    destination = os.stat(
                        destination_name, dir_fd=parent, follow_symlinks=False
                    )
                except FileNotFoundError:
                    private = _find_reserved_private(
                        parent, staging_name, staging_identity
                    )
                    if private is None:
                        raise PdfMarkdownFilesystemError("output_collision") from None
                    _cleanup_private_temp(parent, private, staging_identity)
                    staging = _read_staging(parent, staging_name, output_limit)
                    if (
                        staging is None
                        or staging.content != output
                        or staging.metadata.st_nlink != 1
                        or _stable_identity(staging.metadata) != staging_identity
                    ):
                        raise PdfMarkdownFilesystemError("output_rebound") from None
                except OSError:
                    raise PdfMarkdownFilesystemError("output_unavailable") from None
                else:
                    if (
                        not stat.S_ISREG(destination.st_mode)
                        or destination.st_nlink != 2
                        or _stable_identity(destination) != staging_identity
                    ):
                        raise PdfMarkdownFilesystemError("output_collision")
                    _unlink_staging(parent, staging_name)
                    recovered = _read_existing_output(
                        parent, destination_name, output_limit
                    )
                    if (
                        recovered is None
                        or recovered.stable_identity != staging_identity
                        or recovered.content != output
                    ):
                        raise PdfMarkdownFilesystemError("output_publish_failed")
                    if (
                        input_identity is not None
                        and recovered.stable_identity == input_identity
                    ):
                        raise PdfMarkdownFilesystemError("input_output_alias")
                    _verify_parent_binding(root, root_identity, parts, directory_chain)
                    final = _read_existing_output(parent, destination_name, output_limit)
                    if (
                        final is None
                        or final.identity != recovered.identity
                        or final.content != output
                    ):
                        raise PdfMarkdownFilesystemError("output_rebound")
                    return final.content
            existing = _read_existing_output(parent, destination_name, output_limit)
            if existing is not None:
                if (
                    input_identity is not None
                    and existing.stable_identity == input_identity
                ):
                    raise PdfMarkdownFilesystemError("input_output_alias")
                if existing.content != output:
                    raise PdfMarkdownFilesystemError("output_collision")
                _unlink_staging(parent, staging_name)
                _verify_parent_binding(root, root_identity, parts, directory_chain)
                final = _read_existing_output(parent, destination_name, output_limit)
                if (
                    final is None
                    or final.identity != existing.identity
                    or final.content != output
                ):
                    raise PdfMarkdownFilesystemError("output_rebound")
                return final.content
        else:
            existing = _read_existing_output(parent, destination_name, output_limit)
            if existing is not None:
                existing_bytes = existing.content
                if (
                    input_identity is not None
                    and existing.stable_identity == input_identity
                ):
                    raise PdfMarkdownFilesystemError("input_output_alias")
                if existing_bytes == output:
                    _verify_parent_binding(root, root_identity, parts, directory_chain)
                    final = _read_existing_output(parent, destination_name, output_limit)
                    if (
                        final is None
                        or final.identity != existing.identity
                        or final.content != output
                    ):
                        raise PdfMarkdownFilesystemError("output_rebound")
                    return final.content
                raise PdfMarkdownFilesystemError("output_collision")

        descriptor: int | None = None
        private_name: str | None = None
        private_identity: _StableIdentity | None = None
        try:
            if staging is None:
                private_name = f"{staging_name}.{secrets.token_hex(12)}.private"
                try:
                    descriptor = os.open(
                        private_name, _OUTPUT_OPEN_FLAGS, 0o600, dir_fd=parent
                    )
                except FileExistsError:
                    raise PdfMarkdownFilesystemError("output_publish_failed") from None
                written = 0
                while written < len(output):
                    try:
                        count = os.write(descriptor, output[written:])
                    except OSError:
                        raise PdfMarkdownFilesystemError("output_write_failed") from None
                    if count <= 0:
                        raise PdfMarkdownFilesystemError("output_write_failed")
                    written += count
                os.fsync(descriptor)
                os.close(descriptor)
                descriptor = None
                private_state = _read_staging(parent, private_name, output_limit)
                if (
                    private_state is None
                    or private_state.content != output
                    or private_state.metadata.st_nlink != 1
                ):
                    raise PdfMarkdownFilesystemError("output_rebound")
                private_identity = _stable_identity(private_state.metadata)
                try:
                    os.link(
                        private_name,
                        staging_name,
                        src_dir_fd=parent,
                        dst_dir_fd=parent,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    staging = _read_staging(parent, staging_name, output_limit)
                    if (
                        staging is None
                        or staging.content != output
                        or staging.metadata.st_nlink != 1
                    ):
                        raise PdfMarkdownFilesystemError("output_collision") from None
                    staging_identity = _stable_identity(staging.metadata)
                else:
                    staging = _read_staging(parent, staging_name, output_limit)
                    if (
                        staging is None
                        or staging.content != output
                        or staging.metadata.st_nlink != 2
                        or _stable_identity(staging.metadata) != private_identity
                    ):
                        raise PdfMarkdownFilesystemError("output_rebound")
                    staging_identity = private_identity
                _cleanup_private_temp(parent, private_name, private_identity)
            if staging_identity is None:
                raise PdfMarkdownFilesystemError("output_publish_failed")
            try:
                _verify_parent_binding(root, root_identity, parts, directory_chain)
                os.link(
                    staging_name,
                    destination_name,
                    src_dir_fd=parent,
                    dst_dir_fd=parent,
                    follow_symlinks=False,
                )
            except FileExistsError:
                raced = _read_existing_output(parent, destination_name, output_limit)
                if raced is not None:
                    if (
                        input_identity is not None
                        and raced.stable_identity == input_identity
                    ):
                        raise PdfMarkdownFilesystemError("input_output_alias") from None
                    if raced.content == output:
                        _unlink_staging(parent, staging_name)
                        _verify_parent_binding(root, root_identity, parts, directory_chain)
                        final = _read_existing_output(
                            parent, destination_name, output_limit
                        )
                        if (
                            final is None
                            or final.identity != raced.identity
                            or final.content != output
                        ):
                            raise PdfMarkdownFilesystemError("output_rebound") from None
                        return final.content
                raise PdfMarkdownFilesystemError("output_collision") from None
            except OSError:
                raise PdfMarkdownFilesystemError("output_publish_failed") from None
            try:
                _unlink_staging(parent, staging_name)
            except OSError:
                raise PdfMarkdownFilesystemError("output_publish_failed") from None
            _verify_parent_binding(root, root_identity, parts, directory_chain)
            published = _read_existing_output(parent, destination_name, output_limit)
            if published is None or published.stable_identity != staging_identity:
                raise PdfMarkdownFilesystemError("output_rebound")
            if (
                input_identity is not None
                and published.stable_identity == input_identity
            ):
                raise PdfMarkdownFilesystemError("input_output_alias")
            if published.content != output:
                raise PdfMarkdownFilesystemError("output_publish_failed")
            return published.content
        finally:
            if descriptor is not None:
                with suppress(OSError):
                    os.close(descriptor)
            _cleanup_private_temp(parent, private_name, private_identity)


def capture_root_identity(root: str | Path) -> tuple[Path, _DirectoryIdentity]:
    """Normalize a trusted root lexically and capture its descriptor identity."""

    raw = os.fspath(root)
    if not isinstance(raw, str) or not raw or not os.path.isabs(raw):
        raise PdfMarkdownFilesystemError("trusted_root_must_be_absolute")
    normalized = Path(os.path.abspath(raw))
    try:
        descriptor = os.open(normalized, _DIRECTORY_OPEN_FLAGS)
        try:
            return normalized, _directory_identity(os.fstat(descriptor))
        finally:
            os.close(descriptor)
    except PdfMarkdownFilesystemError:
        raise
    except OSError:
        raise PdfMarkdownFilesystemError("trusted_root_unavailable") from None


__all__ = [
    "MAX_PDF_BYTES",
    "PDF_MAGIC",
    "CapturedPdf",
    "PdfMarkdownFilesystemError",
    "capture_pdf",
    "capture_root_identity",
    "publish_markdown",
    "validate_portable_path",
]
