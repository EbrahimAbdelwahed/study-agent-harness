from __future__ import annotations

import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import textwrap
import traceback
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any, cast

import pytest

from study_agent.adapters.filesystem.repository_target import _RetainedDatabaseBinding
from study_agent.adapters.sqlite import SQLiteConnectionIdentityError
from study_agent.adapters.sqlite import _database as sqlite_database_module
from study_agent.adapters.sqlite._database import (
    _SQLiteAccess,
    _SQLiteAssurance,
    _SQLiteDatabase,
    _SQLiteStorageFailure,
    _use_retained_database_bindings,
)


def _tree_snapshot(
    entries: tuple[Path, ...],
) -> dict[Path, tuple[bool, bytes | None, int | None, tuple[int, int] | None]]:
    snapshot: dict[Path, tuple[bool, bytes | None, int | None, tuple[int, int] | None]] = {}
    for entry in entries:
        try:
            metadata = entry.lstat()
        except FileNotFoundError:
            snapshot[entry] = (False, None, None, None)
            continue
        content = entry.read_bytes() if stat.S_ISREG(metadata.st_mode) else None
        snapshot[entry] = (
            True,
            content,
            stat.S_IMODE(metadata.st_mode),
            (metadata.st_dev, metadata.st_ino),
        )
    return snapshot


def _run_read_only_child(database: Path) -> subprocess.CompletedProcess[str]:
    script = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        from study_agent.adapters.sqlite._database import (
            _SQLiteAccess,
            _SQLiteDatabase,
            _SQLiteStorageFailure,
        )
        from study_agent.adapters.sqlite import SQLiteConnectionIdentityError

        owner = _SQLiteDatabase.for_path(
            Path(sys.argv[1]),
            access=_SQLiteAccess.READ_ONLY,
            busy_timeout_ms=5_000,
            isolation_level=None,
        )
        try:
            with owner.connect() as connection:
                connection.execute("PRAGMA schema_version").fetchone()
        except (_SQLiteStorageFailure, SQLiteConnectionIdentityError) as error:
            print(type(error).__name__)
        else:
            print("opened")
        """
    )
    repository = Path(__file__).parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository / "src")
    return subprocess.run(
        [sys.executable, "-c", script, str(database)],
        cwd=repository,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_exact_assurance_fails_closed_before_sqlite_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "events.sqlite3"
    sqlite_opened = False
    real_connect = sqlite3.connect

    def observe_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        nonlocal sqlite_opened
        sqlite_opened = True
        return cast(sqlite3.Connection, real_connect(*args, **kwargs))

    monkeypatch.setattr(sqlite3, "connect", observe_connect)
    owner = _SQLiteDatabase.for_path(
        database,
        access=_SQLiteAccess.READ_WRITE_EXISTING,
        assurance=_SQLiteAssurance.EXACT_MAIN_FILE,
        busy_timeout_ms=5_000,
        isolation_level=None,
    )

    with pytest.raises(SQLiteConnectionIdentityError, match="exact SQLite binding"):
        owner.connect()
    assert not sqlite_opened
    assert not database.exists()


def test_persistent_database_replacement_is_rejected_without_path_leak(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    owner = _SQLiteDatabase.for_path(
        database,
        access=_SQLiteAccess.READ_WRITE_EXISTING,
        busy_timeout_ms=5_000,
        isolation_level=None,
    )
    with closing(owner.connect()) as connection:
        connection.execute("CREATE TABLE marker(value TEXT NOT NULL)")

    replacement = tmp_path / "replacement.sqlite3"
    database.replace(replacement)
    with pytest.raises(SQLiteConnectionIdentityError) as error:
        owner.connect()
    assert str(database) not in str(error.value)
    assert str(replacement) not in str(error.value)


def test_read_only_wal_uses_the_real_path_and_reads_uncheckpointed_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('wal-row')")
        assert (tmp_path / "events.sqlite3-wal").exists()

        calls: list[str] = []
        real_connect = sqlite3.connect

        def observe_connect(
            database_argument: str, *args: Any, **kwargs: Any
        ) -> sqlite3.Connection:
            calls.append(database_argument)
            return cast(
                sqlite3.Connection,
                real_connect(database_argument, *args, **kwargs),
            )

        monkeypatch.setattr(sqlite3, "connect", observe_connect)
        owner = _SQLiteDatabase.for_path(
            database,
            access=_SQLiteAccess.READ_ONLY,
            busy_timeout_ms=5_000,
            isolation_level=None,
        )
        with closing(owner.connect()) as reader:
            assert reader.execute("PRAGMA query_only").fetchone() == (1,)
            with pytest.raises(sqlite3.OperationalError, match="too many attached"):
                reader.execute("ATTACH DATABASE ? AS forbidden", (str(tmp_path / "other.sqlite3"),))
            assert reader.execute("SELECT value FROM marker").fetchone() == ("wal-row",)

    assert calls
    assert all("/dev/fd/" not in value for value in calls)
    assert all("/proc/self/fd/" not in value for value in calls)
    assert all("immutable" not in value for value in calls)
    assert calls[-1].endswith("/events.sqlite3?mode=ro&nofollow=1")


@pytest.mark.parametrize("suffix", ("-journal", "-wal", "-shm"))
def test_preexisting_sidecar_hardlink_is_rejected_before_sqlite(
    tmp_path: Path, suffix: str
) -> None:
    database = tmp_path / "events.sqlite3"
    database.write_bytes(b"not a database")
    sidecar = Path(f"{database}{suffix}")
    victim = tmp_path / f"victim{suffix}"
    victim.write_bytes(b"victim-bytes")
    sidecar.hardlink_to(victim)
    before = _tree_snapshot((sidecar, victim))

    owner = _SQLiteDatabase.for_path(
        database,
        access=_SQLiteAccess.READ_WRITE_EXISTING,
        busy_timeout_ms=5_000,
        isolation_level=None,
    )
    with pytest.raises(SQLiteConnectionIdentityError):
        owner.connect()
    assert _tree_snapshot((sidecar, victim)) == before


def test_read_only_hot_journal_fails_closed_without_recovery(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('stable')")
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE marker SET value = 'uncommitted'")
        journal = Path(f"{database}-journal")
        assert journal.exists()
        entries = (database, journal)
        before = _tree_snapshot(entries)
        owner = _SQLiteDatabase.for_path(
            database,
            access=_SQLiteAccess.READ_ONLY,
            busy_timeout_ms=5_000,
            isolation_level=None,
        )
        with pytest.raises(_SQLiteStorageFailure, match="SQLite storage is unavailable"):
            owner.connect()
        assert _tree_snapshot(entries) == before
        writer.rollback()


def test_read_only_wal_snapshot_preserves_source_sidecars(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('wal-row')")
        entries = tuple(
            Path(f"{database}{suffix}")
            for suffix in ("", "-wal", "-shm")
        )
        before = _tree_snapshot(entries)
        owner = _SQLiteDatabase.for_path(
            database,
            access=_SQLiteAccess.READ_ONLY,
            busy_timeout_ms=5_000,
            isolation_level=None,
        )
        with owner.connect() as reader:
            assert reader.execute("SELECT value FROM marker").fetchone() == ("wal-row",)
        assert _tree_snapshot(entries) == before


def test_read_only_missing_wal_shm_fails_before_sqlite(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('wal-row')")
        shm = Path(f"{database}-shm")
        assert shm.exists()
        shm.unlink()
        entries = (database, Path(f"{database}-wal"), shm)
        before = _tree_snapshot(entries)
        owner = _SQLiteDatabase.for_path(
            database,
            access=_SQLiteAccess.READ_ONLY,
            busy_timeout_ms=5_000,
            isolation_level=None,
        )
        with pytest.raises(_SQLiteStorageFailure, match="SQLite storage is unavailable"):
            owner.connect()
        assert _tree_snapshot(entries) == before


def _database_fd_targets(root: Path) -> tuple[str, ...]:
    fd_root = Path("/dev/fd")
    if not fd_root.exists():
        pytest.skip("descriptor inspection is unavailable")
    targets: list[str] = []
    for descriptor in fd_root.iterdir():
        try:
            target = os.readlink(descriptor)
        except OSError:
            continue
        if str(root) in target:
            targets.append(target)
    return tuple(sorted(targets))


def _temporary_snapshot_factory(directory: Path) -> Callable[..., str]:
    def make_snapshot(**_: object) -> str:
        directory.mkdir()
        return str(directory)

    return make_snapshot


def _retained_binding(database: Path) -> tuple[_RetainedDatabaseBinding, int, int]:
    state_descriptor = os.open(database.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    database_descriptor = os.open(database, os.O_RDONLY)
    state_metadata = os.fstat(state_descriptor)
    database_metadata = os.fstat(database_descriptor)
    binding = _RetainedDatabaseBinding(
        database,
        state_descriptor,
        database_descriptor,
        (state_metadata.st_dev, state_metadata.st_ino),
        (database_metadata.st_dev, database_metadata.st_ino),
        lambda: None,
    )
    return binding, state_descriptor, database_descriptor


def test_repeated_hot_journal_failures_do_not_retain_descriptors(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('stable')")
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE marker SET value = 'uncommitted'")
        assert Path(f"{database}-journal").exists()
        owner = _SQLiteDatabase.for_path(
            database,
            access=_SQLiteAccess.READ_ONLY,
            busy_timeout_ms=5_000,
            isolation_level=None,
        )
        before = _database_fd_targets(tmp_path)
        for _ in range(32):
            with pytest.raises(_SQLiteStorageFailure):
                owner.connect()
        assert _database_fd_targets(tmp_path) == before
        writer.rollback()


def test_repeated_missing_shm_failures_do_not_retain_descriptors(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('wal-row')")
        shm = Path(f"{database}-shm")
        assert shm.exists()
        shm.unlink()
        owner = _SQLiteDatabase.for_path(
            database,
            access=_SQLiteAccess.READ_ONLY,
            busy_timeout_ms=5_000,
            isolation_level=None,
        )
        before = _database_fd_targets(tmp_path)
        for _ in range(32):
            with pytest.raises(_SQLiteStorageFailure):
                owner.connect()
        assert _database_fd_targets(tmp_path) == before


@pytest.mark.parametrize("journal_mode", ("hot-journal", "missing-shm"))
def test_repeated_retained_binding_failures_preserve_typed_error_and_fds(
    tmp_path: Path, journal_mode: str
) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('stable')")
        if journal_mode == "hot-journal":
            writer.execute("BEGIN IMMEDIATE")
            writer.execute("UPDATE marker SET value = 'uncommitted'")
            assert Path(f"{database}-journal").exists()
        else:
            writer.execute("PRAGMA journal_mode = WAL")
            writer.execute("PRAGMA wal_autocheckpoint = 0")
            writer.execute("INSERT INTO marker(value) VALUES ('wal-row')")
            shm = Path(f"{database}-shm")
            assert shm.exists()
            shm.unlink()

        binding, state_descriptor, database_descriptor = _retained_binding(database)
        try:
            with _use_retained_database_bindings({"events": binding}):
                owner = _SQLiteDatabase.for_path(
                    database,
                    access=_SQLiteAccess.READ_ONLY,
                    busy_timeout_ms=5_000,
                    isolation_level=None,
                )
                before = _database_fd_targets(tmp_path)
                for _ in range(32):
                    with pytest.raises(_SQLiteStorageFailure):
                        owner.connect()
                assert _database_fd_targets(tmp_path) == before
        finally:
            os.close(database_descriptor)
            os.close(state_descriptor)
            if journal_mode == "hot-journal":
                writer.rollback()


@pytest.mark.parametrize("interruption", (KeyboardInterrupt, SystemExit))
def test_snapshot_stream_interruption_cleans_snapshot_and_rethrows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interruption: type[BaseException],
) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database) as writer:
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('stable')")

    snapshot_directory = tmp_path / "private-snapshot"
    monkeypatch.setattr(tempfile, "mkdtemp", _temporary_snapshot_factory(snapshot_directory))

    def interrupt_stream(*args: Any, **kwargs: Any) -> bytes:
        raise interruption("cancelled")

    monkeypatch.setattr(sqlite_database_module, "_stream_descriptor", interrupt_stream)
    owner = _SQLiteDatabase.for_path(
        database,
        access=_SQLiteAccess.READ_ONLY,
        busy_timeout_ms=5_000,
        isolation_level=None,
    )
    before = _database_fd_targets(tmp_path)
    with pytest.raises(interruption, match="cancelled"):
        owner.connect()
    assert not snapshot_directory.exists()
    assert _database_fd_targets(tmp_path) == before


def test_sqlite_open_interruption_closes_anchor_and_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database) as writer:
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")

    snapshot_directory = tmp_path / "private-snapshot"
    monkeypatch.setattr(tempfile, "mkdtemp", _temporary_snapshot_factory(snapshot_directory))

    def interrupt_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        raise KeyboardInterrupt("cancelled")

    monkeypatch.setattr(sqlite3, "connect", interrupt_connect)
    owner = _SQLiteDatabase.for_path(
        database,
        access=_SQLiteAccess.READ_ONLY,
        busy_timeout_ms=5_000,
        isolation_level=None,
    )
    before = _database_fd_targets(tmp_path)
    with pytest.raises(KeyboardInterrupt, match="cancelled"):
        owner.connect()
    assert not snapshot_directory.exists()
    assert _database_fd_targets(tmp_path) == before


def test_configure_interruption_closes_connection_anchor_and_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database) as writer:
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")

    snapshot_directory = tmp_path / "private-snapshot"
    monkeypatch.setattr(tempfile, "mkdtemp", _temporary_snapshot_factory(snapshot_directory))

    def interrupt_configure(
        self: _SQLiteDatabase, connection: sqlite3.Connection
    ) -> None:
        raise SystemExit("cancelled")

    monkeypatch.setattr(_SQLiteDatabase, "_configure", interrupt_configure)
    owner = _SQLiteDatabase.for_path(
        database,
        access=_SQLiteAccess.READ_ONLY,
        busy_timeout_ms=5_000,
        isolation_level=None,
    )
    before = _database_fd_targets(tmp_path)
    with pytest.raises(SystemExit, match="cancelled"):
        owner.connect()
    assert not snapshot_directory.exists()
    assert _database_fd_targets(tmp_path) == before


def test_retained_verification_interruption_closes_duplicated_anchor_descriptors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database) as writer:
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")

    binding, state_descriptor, database_descriptor = _retained_binding(database)
    try:
        with _use_retained_database_bindings({"events": binding}):
            owner = _SQLiteDatabase.for_path(
                database,
                access=_SQLiteAccess.READ_WRITE_EXISTING,
                busy_timeout_ms=5_000,
                isolation_level=None,
            )
            before = _database_fd_targets(tmp_path)

            def interrupt_inspect(
                path: Path, parent_descriptor: int, access: _SQLiteAccess
            ) -> tuple[Any, ...]:
                del path, access
                assert parent_descriptor != binding.state_descriptor
                assert os.fstat(parent_descriptor).st_ino == binding.state_identity[1]
                raise KeyboardInterrupt("cancelled")

            monkeypatch.setattr(sqlite_database_module, "_inspect_sidecars", interrupt_inspect)
            with pytest.raises(KeyboardInterrupt, match="cancelled"):
                owner.connect()
            assert _database_fd_targets(tmp_path) == before
    finally:
        os.close(database_descriptor)
        os.close(state_descriptor)


def test_read_only_missing_shm_is_unchanged_across_process(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('wal-row')")
        shm = Path(f"{database}-shm")
        assert shm.exists()
        shm.unlink()
        entries = (database, Path(f"{database}-wal"), shm)
        before = _tree_snapshot(entries)
        result = _run_read_only_child(database)
        assert result.stdout.strip() == "_SQLiteStorageFailure"
        assert _tree_snapshot(entries) == before


def test_read_only_wal_shm_is_unchanged_across_process(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('wal-row')")
        entries = tuple(Path(f"{database}{suffix}") for suffix in ("", "-wal", "-shm"))
        before = _tree_snapshot(entries)
        result = _run_read_only_child(database)
        assert result.stdout.strip() == "opened"
        assert _tree_snapshot(entries) == before


def test_read_only_hardlinked_shm_is_unchanged_across_process(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    victim = tmp_path / "victim-shm"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        writer.execute("INSERT INTO marker(value) VALUES ('wal-row')")
        shm = Path(f"{database}-shm")
        assert shm.exists()
        shm.unlink()
        victim.write_bytes(b"external-shm-victim")
        shm.hardlink_to(victim)
        entries = (database, Path(f"{database}-wal"), shm, victim)
        before = _tree_snapshot(entries)
        result = _run_read_only_child(database)
        assert result.stdout.strip() == "SQLiteConnectionIdentityError"
        assert _tree_snapshot(entries) == before


@pytest.mark.parametrize("fault", ("sqlite", "os"))
def test_snapshot_backend_failure_redacts_path_and_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    database = tmp_path / "events.sqlite3"
    database.write_bytes(b"not a database")
    owner = _SQLiteDatabase.for_path(
        database,
        access=_SQLiteAccess.READ_ONLY,
        busy_timeout_ms=5_000,
        isolation_level=None,
    )
    secret = f"repository={database} temp={tmp_path / 'private-temp'}"

    if fault == "sqlite":
        def fail_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
            raise sqlite3.OperationalError(secret)

        monkeypatch.setattr(sqlite3, "connect", fail_connect)
    else:
        def fail_read(*args: Any, **kwargs: Any) -> bytes:
            raise OSError(secret)

        monkeypatch.setattr(os, "pread", fail_read)
    with pytest.raises(_SQLiteStorageFailure) as caught:
        owner.connect()
    error = caught.value
    assert str(error) == "SQLite storage is unavailable"
    assert error.__cause__ is None
    rendered = "".join(traceback.format_exception(error))
    assert str(database) not in rendered
    assert str(tmp_path / "private-temp") not in rendered
    assert secret not in rendered


def test_context_exit_preserves_sql_failure_over_binding_revalidation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "events.sqlite3"
    owner = _SQLiteDatabase.for_path(
        database,
        access=_SQLiteAccess.READ_WRITE_EXISTING,
        busy_timeout_ms=5_000,
        isolation_level=None,
    )
    with owner.connect() as connection:
        connection.execute("CREATE TABLE marker(value TEXT NOT NULL)")
    replacement = tmp_path / "replacement.sqlite3"
    with pytest.raises(sqlite3.OperationalError, match="near"), owner.connect() as connection:
        database.rename(replacement)
        database.write_bytes(b"replacement")
        connection.execute("THIS IS NOT SQL")
