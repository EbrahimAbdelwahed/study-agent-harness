"""SHA-256 content-addressed storage anchored by filesystem descriptors."""

from __future__ import annotations

import errno
import hashlib
import os
import secrets
import stat
import weakref
from contextlib import suppress
from pathlib import Path

from study_agent.domain.identifiers import BlobId
from study_agent.domain.source import BlobRef


class BlobNotFoundError(LookupError):
    """The referenced immutable content object does not exist."""


class BlobIntegrityError(OSError):
    """Stored bytes do not match their immutable content reference."""


class UnsafeBlobPathError(ValueError):
    """A reference, platform, or filesystem entry violates safe-storage rules."""


_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_FILE_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def _require_descriptor_platform() -> None:
    required_dir_fd = (os.open, os.mkdir, os.link, os.unlink)
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise UnsafeBlobPathError("filesystem blob storage requires O_DIRECTORY and O_NOFOLLOW")
    if any(operation not in os.supports_dir_fd for operation in required_dir_fd):
        raise UnsafeBlobPathError("filesystem blob storage requires descriptor-relative operations")


class FilesystemBlobStore:
    """Immutable SHA-256 storage anchored to retained root and object-directory fds."""

    def __init__(self, root: str | Path) -> None:
        _require_descriptor_platform()
        configured_root = Path(root).expanduser()
        if configured_root.is_symlink():
            raise UnsafeBlobPathError("blob-store root cannot be a symlink")
        configured_root.mkdir(parents=True, exist_ok=True)
        try:
            root_fd = os.open(configured_root, _DIRECTORY_FLAGS)
        except OSError as error:
            raise UnsafeBlobPathError("blob-store root must be a real directory") from error

        objects_fd: int | None = None
        try:
            with suppress(FileExistsError):
                os.mkdir("objects", 0o755, dir_fd=root_fd)
            objects_fd = self._open_directory(root_fd, "objects", missing_is_blob=False)
        except BaseException:
            os.close(root_fd)
            raise

        self._root_fd = root_fd
        self._objects_fd = objects_fd
        self._root_finalizer = weakref.finalize(self, os.close, root_fd)
        self._objects_finalizer = weakref.finalize(self, os.close, objects_fd)

    @staticmethod
    def _open_directory(parent_fd: int, name: str, *, missing_is_blob: bool) -> int:
        try:
            return os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
        except FileNotFoundError as error:
            if missing_is_blob:
                raise BlobNotFoundError("blob does not exist") from error
            raise
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise UnsafeBlobPathError(f"unsafe blob-store directory: {name}") from error
            raise

    def close(self) -> None:
        """Release retained directory descriptors; subsequent operations are invalid."""
        self._objects_finalizer()
        self._root_finalizer()

    def __enter__(self) -> FilesystemBlobStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _digest(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _validate_ref(ref: BlobRef) -> str:
        digest = ref.checksum_sha256
        if str(ref.id) != f"sha256:{digest}":
            raise UnsafeBlobPathError("blob id must exactly match its SHA-256 checksum")
        return digest

    def _open_shard(self, digest: str, *, create: bool) -> int:
        first_name, second_name = digest[:2], digest[2:4]
        if create:
            with suppress(FileExistsError):
                os.mkdir(first_name, 0o755, dir_fd=self._objects_fd)
        first_fd = self._open_directory(
            self._objects_fd, first_name, missing_is_blob=not create
        )
        try:
            if create:
                with suppress(FileExistsError):
                    os.mkdir(second_name, 0o755, dir_fd=first_fd)
            return self._open_directory(first_fd, second_name, missing_is_blob=not create)
        finally:
            os.close(first_fd)

    @staticmethod
    def _read_file(shard_fd: int, name: str) -> bytes:
        try:
            descriptor = os.open(name, _FILE_READ_FLAGS, dir_fd=shard_fd)
        except FileNotFoundError as error:
            raise BlobNotFoundError(f"blob {name} does not exist") from error
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise UnsafeBlobPathError("blob object cannot be a symlink") from error
            raise
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise BlobIntegrityError("blob object is not a regular file")
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(descriptor)

    @classmethod
    def _verified_content(cls, shard_fd: int, name: str, ref: BlobRef) -> bytes:
        content = cls._read_file(shard_fd, name)
        if len(content) != ref.byte_length:
            raise BlobIntegrityError(
                f"blob length mismatch: expected {ref.byte_length}, got {len(content)}"
            )
        actual_digest = cls._digest(content)
        if actual_digest != ref.checksum_sha256:
            raise BlobIntegrityError(
                f"blob checksum mismatch: expected {ref.checksum_sha256}, got {actual_digest}"
            )
        return content

    @staticmethod
    def _create_temporary(shard_fd: int) -> tuple[int, str]:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        for _ in range(100):
            name = f".publish-{secrets.token_hex(16)}"
            try:
                return os.open(name, flags, 0o600, dir_fd=shard_fd), name
            except FileExistsError:
                continue
        raise OSError("could not allocate a unique temporary blob name")

    @staticmethod
    def _write_all(descriptor: int, content: bytes) -> None:
        view = memoryview(content)
        written = 0
        while written < len(view):
            written += os.write(descriptor, view[written:])

    def put(self, content: bytes) -> BlobRef:
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")
        digest = self._digest(content)
        ref = BlobRef(BlobId(f"sha256:{digest}"), digest, len(content))
        shard_fd = self._open_shard(digest, create=True)
        try:
            descriptor, temporary_name = self._create_temporary(shard_fd)
            try:
                try:
                    self._write_all(descriptor, content)
                    os.fsync(descriptor)
                    os.fchmod(descriptor, 0o444)
                finally:
                    os.close(descriptor)
                try:
                    os.link(
                        temporary_name,
                        digest,
                        src_dir_fd=shard_fd,
                        dst_dir_fd=shard_fd,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    self._verified_content(shard_fd, digest, ref)
                else:
                    os.fsync(shard_fd)
                return ref
            finally:
                with suppress(FileNotFoundError):
                    os.unlink(temporary_name, dir_fd=shard_fd)
        finally:
            os.close(shard_fd)

    def get(self, ref: BlobRef) -> bytes:
        digest = self._validate_ref(ref)
        shard_fd = self._open_shard(digest, create=False)
        try:
            return self._verified_content(shard_fd, digest, ref)
        finally:
            os.close(shard_fd)
