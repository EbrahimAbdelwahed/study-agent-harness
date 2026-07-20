"""Offline memory adapters."""

from .host_file import (
    MemoryHostFileIdentity,
    MemoryHostFileSnapshotStore,
)

__all__ = [
    "MemoryHostFileIdentity",
    "MemoryHostFileSnapshotStore",
]
