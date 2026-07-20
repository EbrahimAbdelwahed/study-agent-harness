from __future__ import annotations

from pathlib import Path

import pytest

from study_agent.adapters.sqlite import NamespacedSQLiteRunStore, SQLiteRunStore
from study_agent.domain import RunId


def test_namespaces_survive_restart_without_owner_proof_or_worker_collisions(
    tmp_path: Path,
) -> None:
    database = tmp_path / "runs.sqlite3"
    first = SQLiteRunStore(database)
    owner = NamespacedSQLiteRunStore(first, "generated-owner")
    proof = NamespacedSQLiteRunStore(first, "verified-proof")
    worker = NamespacedSQLiteRunStore(first, "generation-worker")
    key = RunId("child-run-1")

    assert owner.create(key, b"owner")
    assert proof.create(key, b"proof")
    assert worker.create(str(key), b"worker")

    restarted = SQLiteRunStore(database)
    assert NamespacedSQLiteRunStore(restarted, "generated-owner").load(key) == b"owner"
    assert NamespacedSQLiteRunStore(restarted, "verified-proof").load(key) == b"proof"
    assert NamespacedSQLiteRunStore(restarted, "generation-worker").load(str(key)) == b"worker"


def test_namespaced_store_preserves_atomic_create_and_compare_and_set(tmp_path: Path) -> None:
    store = NamespacedSQLiteRunStore(SQLiteRunStore(tmp_path / "runs.sqlite3"), "lesson")

    assert store.create("lesson-1", b"v1")
    assert not store.create("lesson-1", b"other")
    assert not store.compare_and_set("lesson-1", b"wrong", b"v2")
    assert store.compare_and_set("lesson-1", b"v1", b"v2")
    assert store.load("lesson-1") == b"v2"


@pytest.mark.parametrize("namespace", ("", "UPPER", "contains_underscore", "x" * 65))
def test_namespaces_are_closed_portable_identifiers(tmp_path: Path, namespace: str) -> None:
    with pytest.raises(ValueError, match="namespace"):
        NamespacedSQLiteRunStore(SQLiteRunStore(tmp_path / "runs.sqlite3"), namespace)
