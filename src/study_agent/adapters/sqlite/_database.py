"""Private owner for safe, pathname-continuous SQLite connections.

The standard-library SQLite adapter cannot prove that its native ``main``
handle is the same file object as a separately retained descriptor.  This
module therefore implements the weaker, explicit contract: retain the
repository owner and database entry, open the real authorized pathname once,
and revalidate the retained binding around the connection lifetime.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import stat
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast

from study_agent.domain.errors import InternalFailure, UnavailableDependencyFailure


class _SQLiteAccess(StrEnum):
    READ_ONLY = "read_only"
    READ_WRITE_EXISTING = "read_write_existing"


class _SQLiteAssurance(StrEnum):
    PATH_CONTINUITY = "repository_pathname_continuity"
    EXACT_MAIN_FILE = "exact_main_file"


class SQLiteConnectionIdentityError(InternalFailure):
    """The retained repository pathname binding could not be preserved."""


class _SQLiteStorageFailure(UnavailableDependencyFailure):
    """SQLite or its sidecars were unavailable without leaking backend detail."""


class _RetainedDatabaseBinding(Protocol):
    """Private filesystem seam consumed by the SQLite owner."""

    database_path: Path
    state_descriptor: int
    database_descriptor: int
    state_identity: tuple[int, int]
    database_identity: tuple[int, int]

    def verify(self) -> None: ...


_RETAINED_BINDINGS: ContextVar[Mapping[str, object] | None] = ContextVar(
    "study_agent_sqlite_retained_bindings", default=None
)


@contextmanager
def _use_retained_database_bindings(bindings: Mapping[str, object]) -> Iterator[None]:
    """Make observation bindings available only while adapters are composed."""

    token = _RETAINED_BINDINGS.set(dict(bindings))
    try:
        yield
    finally:
        _RETAINED_BINDINGS.reset(token)


@dataclass(frozen=True, slots=True)
class _SidecarBinding:
    suffix: str
    identity: tuple[int, int]
    mode: int
    size: int


@dataclass(frozen=True, slots=True)
class _Anchor:
    parent_descriptor: int
    database_descriptor: int
    parent_identity: tuple[int, int]
    database_identity: tuple[int, int]
    sidecars: tuple[_SidecarBinding, ...]
    read_only: bool


class _OwnedSQLiteConnection:
    """A small proxy that keeps pathname anchors alive through SQLite close."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        database_path: Path,
        anchor: _Anchor,
        binding: _RetainedDatabaseBinding | None,
        cleanup: Callable[[], None] | None = None,
        source_digests: Mapping[str, bytes] | None = None,
    ) -> None:
        object.__setattr__(self, "_connection", connection)
        object.__setattr__(self, "_database_path", database_path)
        object.__setattr__(self, "_anchor", anchor)
        object.__setattr__(self, "_binding", binding)
        object.__setattr__(self, "_cleanup", cleanup)
        object.__setattr__(self, "_source_digests", source_digests)
        object.__setattr__(self, "_closed", False)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def __setattr__(self, name: str, value: object) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._connection, name, value)

    def __enter__(self) -> _OwnedSQLiteConnection:
        try:
            self._connection.__enter__()
        except BaseException as error:
            with suppress(BaseException):
                self.close()
            raise error
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool | None:
        result: bool | None = None
        primary: BaseException | None = exc if isinstance(exc, BaseException) else None
        try:
            result = cast(bool | None, self._connection.__exit__(exc_type, exc, traceback))
        except BaseException as error:
            if primary is None:
                primary = error
        try:
            self.close()
        except BaseException as error:
            if primary is None:
                primary = error
        if primary is not None:
            raise primary
        return result

    def close(self) -> None:
        if self._closed:
            return
        object.__setattr__(self, "_closed", True)
        primary: BaseException | None = None
        try:
            self._connection.close()
        except Exception:
            primary = _SQLiteStorageFailure("SQLite storage is unavailable")
        except BaseException as error:
            primary = error
        try:
            _verify_anchor(
                self._database_path,
                self._anchor,
                self._binding,
                self._source_digests,
            )
        except BaseException as error:
            if primary is None:
                primary = error
        finally:
            cleanup = self._cleanup
            if cleanup is not None:
                with suppress(BaseException):
                    cleanup()
            for descriptor in (
                self._anchor.database_descriptor,
                self._anchor.parent_descriptor,
            ):
                with suppress(OSError):
                    os.close(descriptor)
        if primary is not None:
            raise primary


class _SQLiteDatabase:
    """Deep private SQLite module with one-open, real-path semantics."""

    def __init__(
        self,
        database_path: Path,
        *,
        access: _SQLiteAccess,
        assurance: _SQLiteAssurance,
        busy_timeout_ms: int,
        isolation_level: str | None,
        binding: _RetainedDatabaseBinding | None,
    ) -> None:
        self._database_path = database_path
        if not isinstance(access, _SQLiteAccess) or not isinstance(assurance, _SQLiteAssurance):
            raise ValueError("unsupported SQLite connection policy")
        self._access = access
        self._assurance = assurance
        self._busy_timeout_ms = busy_timeout_ms
        self._isolation_level = isolation_level
        self._binding = binding
        self._expected_parent_identity: tuple[int, int] | None = None
        self._expected_database_identity: tuple[int, int] | None = None

    @classmethod
    def for_path(
        cls,
        path: str | Path,
        *,
        access: _SQLiteAccess,
        assurance: _SQLiteAssurance = _SQLiteAssurance.PATH_CONTINUITY,
        busy_timeout_ms: int,
        isolation_level: str | None,
    ) -> _SQLiteDatabase:
        database_path = _path_from_value(path)
        binding = _binding_for_path(database_path)
        return cls(
            database_path,
            access=access,
            assurance=assurance,
            busy_timeout_ms=busy_timeout_ms,
            isolation_level=isolation_level,
            binding=binding,
        )

    @classmethod
    def for_retained_binding(
        cls,
        binding: _RetainedDatabaseBinding,
        *,
        access: _SQLiteAccess,
        assurance: _SQLiteAssurance = _SQLiteAssurance.PATH_CONTINUITY,
        busy_timeout_ms: int,
        isolation_level: str | None,
    ) -> _SQLiteDatabase:
        if not isinstance(binding.database_path, Path):
            raise TypeError("database binding path must be a Path")
        return cls(
            binding.database_path,
            access=access,
            assurance=assurance,
            busy_timeout_ms=busy_timeout_ms,
            isolation_level=isolation_level,
            binding=binding,
        )

    def connect(self) -> _OwnedSQLiteConnection:
        if self._assurance is _SQLiteAssurance.EXACT_MAIN_FILE:
            raise SQLiteConnectionIdentityError("exact SQLite binding is unavailable")
        if self._access not in {
            _SQLiteAccess.READ_ONLY,
            _SQLiteAccess.READ_WRITE_EXISTING,
        }:
            raise ValueError("unsupported SQLite access mode")
        if type(self._busy_timeout_ms) is not int or self._busy_timeout_ms < 0:
            raise ValueError("busy timeout must be a non-negative integer")

        anchor: _Anchor | None = None
        connection: sqlite3.Connection | None = None
        cleanup: Callable[[], None] | None = None
        source_digests: Mapping[str, bytes] | None = None
        try:
            anchor = _open_anchor(
                self._database_path,
                self._access,
                self._binding,
                expected_parent_identity=self._expected_parent_identity,
                expected_database_identity=self._expected_database_identity,
            )
            if self._binding is None and self._expected_database_identity is None:
                self._expected_parent_identity = anchor.parent_identity
                self._expected_database_identity = anchor.database_identity
            database_path = self._database_path
            if self._access is _SQLiteAccess.READ_ONLY:
                database_path, cleanup, source_digests = _create_read_only_snapshot(
                    self._database_path, anchor
                )
                _verify_anchor(
                    self._database_path,
                    anchor,
                    self._binding,
                    source_digests,
                )
            uri = _sqlite_uri(database_path, self._access)
            connection = sqlite3.connect(
                uri,
                isolation_level=cast(Any, self._isolation_level),
                timeout=self._busy_timeout_ms / 1000,
                uri=True,
            )
            self._configure(connection)
            _verify_anchor(
                self._database_path,
                anchor,
                self._binding,
                source_digests,
            )
            return _OwnedSQLiteConnection(
                connection,
                database_path=self._database_path,
                anchor=anchor,
                binding=self._binding,
                cleanup=cleanup,
                source_digests=source_digests,
            )
        except SQLiteConnectionIdentityError:
            _close_failed_connection(connection, anchor)
            if cleanup is not None:
                with suppress(BaseException):
                    cleanup()
            raise
        except _SQLiteStorageFailure:
            _close_failed_connection(connection, anchor)
            if cleanup is not None:
                with suppress(BaseException):
                    cleanup()
            raise
        except (OSError, sqlite3.Error):
            _close_failed_connection(connection, anchor)
            if cleanup is not None:
                with suppress(BaseException):
                    cleanup()
            raise _SQLiteStorageFailure("SQLite storage is unavailable") from None
        except Exception:
            _close_failed_connection(connection, anchor)
            if cleanup is not None:
                with suppress(BaseException):
                    cleanup()
            raise _SQLiteStorageFailure("SQLite storage is unavailable") from None
        except BaseException:
            _close_failed_connection(connection, anchor)
            if cleanup is not None:
                with suppress(BaseException):
                    cleanup()
            raise

    def _configure(self, connection: sqlite3.Connection) -> None:
        connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
        set_limit = getattr(connection, "setlimit", None)
        limit = getattr(sqlite3, "SQLITE_LIMIT_ATTACHED", None)
        if not callable(set_limit) or not isinstance(limit, int):
            raise _SQLiteStorageFailure("SQLite attachment policy is unavailable")
        set_limit(limit, 0)
        if self._access is _SQLiteAccess.READ_ONLY:
            connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA schema_version").fetchone()
        rows = connection.execute("PRAGMA database_list").fetchall()
        main_rows = tuple(
            row
            for row in rows
            if type(row) is tuple and len(row) == 3 and row[1] == "main"
        )
        if len(main_rows) != 1 or not isinstance(main_rows[0][2], str) or not main_rows[0][2]:
            raise SQLiteConnectionIdentityError("SQLite database binding is unavailable")


def _path_from_value(value: str | Path) -> Path:
    raw = os.fspath(value)
    if not isinstance(raw, str) or not raw.strip() or raw.startswith("file:"):
        raise ValueError("SQLite database must be a path")
    path = Path(raw)
    if path.name in {"", ".", ".."} or path.name != path.name.strip():
        raise ValueError("SQLite database path is invalid")
    return path.absolute()


def _binding_for_path(path: Path) -> _RetainedDatabaseBinding | None:
    key = path.name.removesuffix(".sqlite3")
    bindings = _RETAINED_BINDINGS.get()
    candidate = None if bindings is None else bindings.get(key)
    if candidate is None:
        return None
    # Protocols are not runtime-checkable; the explicit attribute check is
    # intentionally narrow so an arbitrary composition object is rejected.
    required = (
        "database_path",
        "state_descriptor",
        "database_descriptor",
        "state_identity",
        "database_identity",
        "verify",
    )
    if not all(hasattr(candidate, name) for name in required):
        raise TypeError("invalid retained SQLite database binding")
    return cast(_RetainedDatabaseBinding, candidate)


def _sqlite_uri(path: Path, access: _SQLiteAccess) -> str:
    mode = "ro" if access is _SQLiteAccess.READ_ONLY else "rw"
    return f"{path.as_uri()}?mode={mode}&nofollow=1"


_SIDECAR_SUFFIXES = ("-journal", "-wal", "-shm")
# Read-only snapshots are intentionally bounded to keep an untrusted SQLite
# entry from turning observation into an unbounded memory or disk sink.
_MAX_READ_ONLY_SNAPSHOT_BYTES = 64 * 1024 * 1024
_SNAPSHOT_CHUNK_BYTES = 1024 * 1024


def _stream_descriptor(
    descriptor: int,
    size: int,
    destination: Any | None = None,
) -> bytes:
    if size < 0:
        raise OSError("negative SQLite sidecar size")
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        chunk = os.pread(descriptor, min(_SNAPSHOT_CHUNK_BYTES, size - offset), offset)
        if not chunk:
            raise OSError("SQLite sidecar changed while it was inspected")
        digest.update(chunk)
        if destination is not None:
            destination.write(chunk)
        offset += len(chunk)
    if offset != size:
        raise OSError("SQLite sidecar changed while it was inspected")
    return digest.digest()


def _inspect_sidecars(
    path: Path, parent_descriptor: int, access: _SQLiteAccess
) -> tuple[_SidecarBinding, ...]:
    """Inspect native sidecars without following or creating any entry."""

    bindings: list[_SidecarBinding] = []
    for suffix in _SIDECAR_SUFFIXES:
        name = f"{path.name}{suffix}"
        try:
            metadata = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError:
            raise SQLiteConnectionIdentityError(
                "SQLite sidecar binding is unavailable"
            ) from None
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise SQLiteConnectionIdentityError("SQLite sidecar binding is unavailable")
        descriptor: int | None = None
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NONBLOCK", 0),
                dir_fd=parent_descriptor,
            )
            opened = os.fstat(descriptor)
            identity = (metadata.st_dev, metadata.st_ino)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != identity
            ):
                raise SQLiteConnectionIdentityError("SQLite sidecar binding changed")
            bindings.append(
                _SidecarBinding(
                    suffix,
                    identity,
                    stat.S_IMODE(opened.st_mode),
                    opened.st_size,
                )
            )
        except SQLiteConnectionIdentityError:
            raise
        except OSError:
            raise SQLiteConnectionIdentityError(
                "SQLite sidecar binding is unavailable"
            ) from None
        finally:
            if descriptor is not None:
                with suppress(OSError):
                    os.close(descriptor)
    if access is _SQLiteAccess.READ_ONLY:
        suffixes = {binding.suffix for binding in bindings}
        if "-journal" in suffixes:
            raise _SQLiteStorageFailure("SQLite storage is unavailable")
        if "-wal" in suffixes and "-shm" not in suffixes:
            raise _SQLiteStorageFailure("SQLite storage is unavailable")
    return tuple(bindings)


def _create_read_only_snapshot(
    path: Path, anchor: _Anchor
) -> tuple[Path, Callable[[], None], Mapping[str, bytes]]:
    """Read a sidecar-bearing database from a private immutable source copy.

    SQLite may update WAL shared-memory locks even for ``mode=ro`` readers.  A
    private copy preserves the source tree byte-for-byte while retaining the
    native basename SQLite uses to discover its WAL and SHM files.
    """

    directory = Path(tempfile.mkdtemp(prefix="study-agent-sqlite-"))
    snapshot = directory / path.name
    try:
        main_metadata = os.fstat(anchor.database_descriptor)
        total_size = main_metadata.st_size + sum(sidecar.size for sidecar in anchor.sidecars)
        if (
            total_size > _MAX_READ_ONLY_SNAPSHOT_BYTES
            or total_size > shutil.disk_usage(directory).free
        ):
            raise _SQLiteStorageFailure("SQLite storage is unavailable")
        digests: dict[str, bytes] = {}
        with open(snapshot, "xb") as stream:
            digests[""] = _stream_descriptor(
                anchor.database_descriptor, main_metadata.st_size, stream
            )
        os.chmod(snapshot, 0o600)
        for sidecar in anchor.sidecars:
            descriptor: int | None = None
            try:
                descriptor = os.open(
                    f"{path.name}{sidecar.suffix}",
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0)
                    | getattr(os, "O_NONBLOCK", 0),
                    dir_fd=anchor.parent_descriptor,
                )
                metadata = os.fstat(descriptor)
                if (
                    (metadata.st_dev, metadata.st_ino) != sidecar.identity
                    or not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_nlink != 1
                    or metadata.st_size != sidecar.size
                    or stat.S_IMODE(metadata.st_mode) != sidecar.mode
                ):
                    raise SQLiteConnectionIdentityError("SQLite sidecar binding changed")
                destination = Path(f"{snapshot}{sidecar.suffix}")
                with open(destination, "xb") as stream:
                    digests[sidecar.suffix] = _stream_descriptor(
                        descriptor, metadata.st_size, stream
                    )
                os.chmod(destination, 0o600)
            finally:
                if descriptor is not None:
                    with suppress(OSError):
                        os.close(descriptor)
    except BaseException:
        _remove_snapshot(directory)
        raise
    return snapshot, lambda: _remove_snapshot(directory), digests


def _remove_snapshot(directory: Path) -> None:
    """Best-effort cleanup that cannot replace the operation's primary error."""

    with suppress(BaseException):
        shutil.rmtree(directory, ignore_errors=True)


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )


def _file_flags(access: _SQLiteAccess) -> int:
    return (
        (os.O_RDONLY if access is _SQLiteAccess.READ_ONLY else os.O_RDWR)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )


def _open_anchor(
    path: Path,
    access: _SQLiteAccess,
    binding: _RetainedDatabaseBinding | None,
    *,
    expected_parent_identity: tuple[int, int] | None,
    expected_database_identity: tuple[int, int] | None,
) -> _Anchor:
    if not hasattr(os, "O_NOFOLLOW"):
        raise SQLiteConnectionIdentityError("SQLite pathname continuity is unavailable")
    if binding is not None:
        bound_parent_descriptor: int | None = None
        bound_database_descriptor: int | None = None
        try:
            binding.verify()
            bound_parent_descriptor = os.dup(binding.state_descriptor)
            bound_database_descriptor = os.dup(binding.database_descriptor)
            parent_identity = (binding.state_identity[0], binding.state_identity[1])
            database_identity = (binding.database_identity[0], binding.database_identity[1])
            sidecars = _inspect_sidecars(path, bound_parent_descriptor, access)
            anchor = _Anchor(
                bound_parent_descriptor,
                bound_database_descriptor,
                parent_identity,
                database_identity,
                sidecars,
                access is _SQLiteAccess.READ_ONLY,
            )
            _verify_anchor(path, anchor, binding)
            return anchor
        except SQLiteConnectionIdentityError:
            _close_descriptors(bound_parent_descriptor, bound_database_descriptor)
            raise
        except _SQLiteStorageFailure:
            _close_descriptors(bound_parent_descriptor, bound_database_descriptor)
            raise
        except (OSError, RuntimeError, ValueError):
            _close_descriptors(bound_parent_descriptor, bound_database_descriptor)
            raise SQLiteConnectionIdentityError("SQLite database binding changed") from None
        except BaseException:
            _close_descriptors(bound_parent_descriptor, bound_database_descriptor)
            raise

    parent_descriptor: int | None = None
    database_descriptor: int | None = None
    try:
        parent_descriptor = os.open(path.parent, _directory_flags())
        flags = _file_flags(access)
        try:
            database_descriptor = os.open(path.name, flags, dir_fd=parent_descriptor)
        except FileNotFoundError:
            if access is _SQLiteAccess.READ_ONLY:
                raise _SQLiteStorageFailure("SQLite storage is unavailable") from None
            try:
                database_descriptor = os.open(
                    path.name,
                    flags | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=parent_descriptor,
                )
            except FileExistsError:
                database_descriptor = os.open(path.name, flags, dir_fd=parent_descriptor)
        parent_metadata = os.fstat(parent_descriptor)
        database_metadata = os.fstat(database_descriptor)
        if not stat.S_ISDIR(parent_metadata.st_mode) or not stat.S_ISREG(database_metadata.st_mode):
            raise SQLiteConnectionIdentityError("SQLite database binding is unavailable")
        if database_metadata.st_nlink != 1:
            raise SQLiteConnectionIdentityError("SQLite database binding is unavailable")
        sidecars = _inspect_sidecars(path, parent_descriptor, access)
        anchor = _Anchor(
            parent_descriptor,
            database_descriptor,
            (parent_metadata.st_dev, parent_metadata.st_ino),
            (database_metadata.st_dev, database_metadata.st_ino),
            sidecars,
            access is _SQLiteAccess.READ_ONLY,
        )
        if (
            expected_parent_identity is not None
            and anchor.parent_identity != expected_parent_identity
        ):
            raise SQLiteConnectionIdentityError("SQLite database binding changed")
        if (
            expected_database_identity is not None
            and anchor.database_identity != expected_database_identity
        ):
            raise SQLiteConnectionIdentityError("SQLite database binding changed")
        _verify_anchor(path, anchor, None)
        return anchor
    except SQLiteConnectionIdentityError:
        _close_descriptors(parent_descriptor, database_descriptor)
        raise
    except _SQLiteStorageFailure:
        _close_descriptors(parent_descriptor, database_descriptor)
        raise
    except OSError:
        _close_descriptors(parent_descriptor, database_descriptor)
        raise SQLiteConnectionIdentityError(
            "SQLite database binding is unavailable"
        ) from None
    except BaseException:
        _close_descriptors(parent_descriptor, database_descriptor)
        raise


def _verify_anchor(
    path: Path,
    anchor: _Anchor,
    binding: _RetainedDatabaseBinding | None,
    source_digests: Mapping[str, bytes] | None = None,
) -> None:
    try:
        if binding is not None:
            binding.verify()
            _verify_descriptor(anchor.parent_descriptor, anchor.parent_identity, directory=True)
            _verify_descriptor(
                anchor.database_descriptor, anchor.database_identity, directory=False
            )
            metadata = os.stat(
                path.name,
                dir_fd=anchor.parent_descriptor,
                follow_symlinks=False,
            )
        else:
            current_parent = os.open(path.parent, _directory_flags())
            try:
                _verify_descriptor(current_parent, anchor.parent_identity, directory=True)
            finally:
                os.close(current_parent)
            _verify_descriptor(anchor.parent_descriptor, anchor.parent_identity, directory=True)
            _verify_descriptor(
                anchor.database_descriptor, anchor.database_identity, directory=False
            )
            metadata = os.stat(path.name, dir_fd=anchor.parent_descriptor, follow_symlinks=False)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino) != anchor.database_identity
            or metadata.st_nlink != 1
        ):
            raise SQLiteConnectionIdentityError("SQLite database binding changed")
        if (
            anchor.read_only
            and source_digests is not None
            and _stream_descriptor(anchor.database_descriptor, metadata.st_size)
            != source_digests.get("")
        ):
            raise SQLiteConnectionIdentityError("SQLite database binding changed")
        expected_sidecars = {binding.suffix: binding for binding in anchor.sidecars}
        for suffix in _SIDECAR_SUFFIXES:
            name = f"{path.name}{suffix}"
            expected = expected_sidecars.get(suffix)
            try:
                sidecar_metadata = os.stat(
                    name,
                    dir_fd=anchor.parent_descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                if anchor.read_only and expected is not None:
                    raise SQLiteConnectionIdentityError(
                        "SQLite sidecar binding changed"
                    ) from None
                continue
            if not stat.S_ISREG(sidecar_metadata.st_mode) or sidecar_metadata.st_nlink != 1:
                raise SQLiteConnectionIdentityError("SQLite sidecar binding changed")
            if expected is None:
                if anchor.read_only:
                    raise SQLiteConnectionIdentityError("SQLite sidecar binding changed")
                continue
            if (sidecar_metadata.st_dev, sidecar_metadata.st_ino) != expected.identity:
                raise SQLiteConnectionIdentityError("SQLite sidecar binding changed")
            if anchor.read_only and source_digests is not None:
                if stat.S_IMODE(sidecar_metadata.st_mode) != expected.mode:
                    raise SQLiteConnectionIdentityError("SQLite sidecar binding changed")
                if sidecar_metadata.st_size != expected.size:
                    raise SQLiteConnectionIdentityError("SQLite sidecar binding changed")
                descriptor: int | None = None
                try:
                    descriptor = os.open(
                        name,
                        os.O_RDONLY
                        | getattr(os, "O_NOFOLLOW", 0)
                        | getattr(os, "O_CLOEXEC", 0)
                        | getattr(os, "O_NONBLOCK", 0),
                        dir_fd=anchor.parent_descriptor,
                    )
                    opened = os.fstat(descriptor)
                    if (opened.st_dev, opened.st_ino) != expected.identity:
                        raise SQLiteConnectionIdentityError("SQLite sidecar binding changed")
                    digest = _stream_descriptor(descriptor, opened.st_size)
                    if digest != source_digests.get(suffix):
                        raise SQLiteConnectionIdentityError("SQLite sidecar binding changed")
                except SQLiteConnectionIdentityError:
                    raise
                except OSError:
                    raise SQLiteConnectionIdentityError(
                        "SQLite sidecar binding changed"
                    ) from None
                finally:
                    if descriptor is not None:
                        with suppress(OSError):
                            os.close(descriptor)
    except SQLiteConnectionIdentityError:
        raise
    except (OSError, RuntimeError, ValueError):
        raise SQLiteConnectionIdentityError("SQLite database binding changed") from None


def _verify_descriptor(descriptor: int, identity: tuple[int, int], *, directory: bool) -> None:
    metadata = os.fstat(descriptor)
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(metadata.st_mode) or (metadata.st_dev, metadata.st_ino) != identity:
        raise SQLiteConnectionIdentityError("SQLite database binding changed")


def _close_failed_connection(
    connection: sqlite3.Connection | None,
    anchor: _Anchor | None,
) -> None:
    if connection is not None:
        with suppress(BaseException):
            connection.close()
    if anchor is not None:
        _close_descriptors(anchor.parent_descriptor, anchor.database_descriptor)


def _close_descriptors(parent_descriptor: int | None, database_descriptor: int | None) -> None:
    for descriptor in (database_descriptor, parent_descriptor):
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)


__all__ = [
    "SQLiteConnectionIdentityError",
    "_SQLiteAccess",
    "_SQLiteAssurance",
    "_SQLiteDatabase",
    "_SQLiteStorageFailure",
    "_use_retained_database_bindings",
]
