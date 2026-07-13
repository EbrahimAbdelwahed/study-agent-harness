from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from study_agent.adapters.sqlite import (
    RunStoreCorruptionError,
    SQLiteRunStore,
    UnsupportedSQLiteRunDatabaseError,
)
from study_agent.domain import RunId
from study_agent.ports import RunStore


def _store(database: Path) -> RunStore:
    return SQLiteRunStore(database)


def test_create_load_duplicate_and_compare_and_set_are_atomic(tmp_path: Path) -> None:
    store = _store(tmp_path / "runs.sqlite3")
    run_id = RunId("run-1")

    assert store.create(run_id, b"running")
    assert not store.create(run_id, b"duplicate")
    assert store.load(run_id) == b"running"
    assert not store.compare_and_set(run_id, b"stale", b"wrong")
    assert store.compare_and_set(run_id, b"running", b"suspended")
    assert store.load(run_id) == b"suspended"


def test_state_survives_adapter_reopen(tmp_path: Path) -> None:
    database = tmp_path / "runs.sqlite3"
    run_id = RunId("run-reopen")
    assert SQLiteRunStore(database).create(run_id, b"checkpoint-1")

    reopened = SQLiteRunStore(database)
    assert reopened.load(run_id) == b"checkpoint-1"
    assert reopened.compare_and_set(run_id, b"checkpoint-1", b"checkpoint-2")
    assert SQLiteRunStore(database).load(run_id) == b"checkpoint-2"


def test_concurrent_creators_and_cas_writers_have_one_winner(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    run_id = RunId("contended")
    create_barrier = Barrier(8)

    def create(payload: bytes) -> bool:
        create_barrier.wait()
        return store.create(run_id, payload)

    with ThreadPoolExecutor(max_workers=8) as executor:
        create_results = tuple(executor.map(create, (bytes([index]) for index in range(8))))
    assert create_results.count(True) == 1

    expected = store.load(run_id)
    cas_barrier = Barrier(8)

    def replace(payload: bytes) -> bool:
        cas_barrier.wait()
        return store.compare_and_set(run_id, expected, payload)

    replacements = tuple(bytes([index + 10]) for index in range(8))
    with ThreadPoolExecutor(max_workers=8) as executor:
        cas_results = tuple(executor.map(replace, replacements))
    assert cas_results.count(True) == 1
    assert store.load(run_id) in replacements


def test_missing_load_and_cas_have_portable_semantics(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    missing = RunId("missing")

    assert not store.compare_and_set(missing, b"old", b"new")
    with pytest.raises(KeyError) as raised:
        store.load(missing)
    assert raised.value.args == (missing,)


@pytest.mark.parametrize("database", ["", ":memory:", "file:runs?mode=memory&cache=shared"])
def test_store_rejects_non_path_backed_databases(database: str) -> None:
    with pytest.raises(UnsupportedSQLiteRunDatabaseError):
        SQLiteRunStore(database)


def test_store_accepts_durable_filename_containing_memory_mode_text(tmp_path: Path) -> None:
    database = tmp_path / "archive-mode=memory.sqlite3"
    store = SQLiteRunStore(database)
    run_id = RunId("run-durable-name")

    assert store.create(run_id, b"payload")
    assert store.load(run_id) == b"payload"


def test_strict_schema_rejects_non_blob_payload_corruption(tmp_path: Path) -> None:
    database = tmp_path / "runs.sqlite3"
    SQLiteRunStore(database)

    with sqlite3.connect(database) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO playbook_runs (run_id, payload) VALUES (?, ?)",
            ("corrupt", "not-bytes"),
        )


def test_public_writes_require_exact_bytes(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    with pytest.raises(TypeError, match="payload must be bytes"):
        store.create(RunId("run"), bytearray(b"mutable"))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="expected must be bytes"):
        store.compare_and_set(RunId("run"), bytearray(b"old"), b"new")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "schema",
    [
        "CREATE TABLE playbook_runs (run_id TEXT PRIMARY KEY, payload BLOB NOT NULL)",
        "CREATE TABLE playbook_runs (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL) STRICT",
        "CREATE TABLE playbook_runs (run_id TEXT, payload BLOB NOT NULL) STRICT",
        "CREATE TABLE playbook_runs (run_id TEXT PRIMARY KEY, payload BLOB) STRICT",
        (
            "CREATE TABLE playbook_runs (run_id TEXT PRIMARY KEY, payload BLOB NOT NULL, "
            "extra TEXT) STRICT"
        ),
        (
            "CREATE TABLE playbook_runs (run_id TEXT PRIMARY KEY, payload BLOB NOT NULL) "
            "STRICT, WITHOUT ROWID"
        ),
        (
            "CREATE TABLE playbook_runs (run_id TEXT PRIMARY KEY, payload BLOB NOT NULL, "
            "hidden TEXT GENERATED ALWAYS AS (run_id)) STRICT"
        ),
    ],
)
def test_init_rejects_incompatible_preexisting_schema(tmp_path: Path, schema: str) -> None:
    database = tmp_path / "runs.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(schema)

    with pytest.raises(RunStoreCorruptionError, match="playbook_runs"):
        SQLiteRunStore(database)


def test_init_classifies_preexisting_view_as_schema_corruption(tmp_path: Path) -> None:
    database = tmp_path / "runs.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE VIEW playbook_runs AS SELECT 'run' AS run_id, X'00' AS payload")

    with pytest.raises(RunStoreCorruptionError, match="playbook_runs"):
        SQLiteRunStore(database)
