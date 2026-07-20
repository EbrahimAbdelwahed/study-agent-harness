"""Collision-free operational byte stores over the existing durable run table."""

from __future__ import annotations

import re
from hashlib import sha256

from study_agent.domain import RunId

from .run_store import SQLiteRunStore

_NAMESPACE = re.compile(r"[a-z][a-z0-9-]{0,63}")
_KEY_DOMAIN = b"namespaced-operational-run-key@1\0"


class NamespacedSQLiteRunStore:
    """Adapt string/RunId operational keys to isolated SQLite run slots."""

    def __init__(self, store: SQLiteRunStore, namespace: str) -> None:
        if not isinstance(store, SQLiteRunStore):
            raise TypeError("namespaced run storage requires SQLiteRunStore")
        if not isinstance(namespace, str) or _NAMESPACE.fullmatch(namespace) is None:
            raise ValueError("run-store namespace must be portable lowercase text")
        self._store = store
        self._namespace = namespace

    def create(self, key: str | RunId, payload: bytes) -> bool:
        return self._store.create(self._slot(key), payload)

    def compare_and_set(
        self,
        key: str | RunId,
        expected: bytes,
        replacement: bytes,
    ) -> bool:
        return self._store.compare_and_set(self._slot(key), expected, replacement)

    def load(self, key: str | RunId) -> bytes:
        return self._store.load(self._slot(key))

    def _slot(self, key: str | RunId) -> RunId:
        if not isinstance(key, (str, RunId)):
            raise TypeError("operational run key must be str or RunId")
        value = str(key)
        if not value or value != value.strip():
            raise ValueError("operational run key must be non-empty trimmed text")
        digest = sha256(
            _KEY_DOMAIN
            + self._namespace.encode("ascii")
            + b"\0"
            + value.encode("utf-8")
        ).hexdigest()
        return RunId(f"{self._namespace}-sha256:{digest}")


__all__ = ["NamespacedSQLiteRunStore"]
