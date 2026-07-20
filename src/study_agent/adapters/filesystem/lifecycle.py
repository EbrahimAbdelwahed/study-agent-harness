"""Bounded no-follow reader for one explicitly selected lifecycle manifest."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from study_agent.lifecycle.contracts import MAX_MANIFEST_BYTES, LifecycleManifestV1


class ManifestReadError(OSError):
    """The selected manifest could not be read as one stable regular file."""


def load_lifecycle_manifest(path: Path) -> LifecycleManifestV1:
    """Read only ``path`` and parse it without resolving declared manifest paths."""
    if not isinstance(path, Path):
        raise ManifestReadError("manifest path is invalid")
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if no_follow == 0:  # pragma: no cover - supported release platforms provide it
        raise ManifestReadError("safe manifest reads are unavailable on this platform")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | no_follow
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ManifestReadError("manifest is unavailable or unsafe") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ManifestReadError("manifest must be a regular non-symlink file")
        if before.st_size <= 0 or before.st_size > MAX_MANIFEST_BYTES:
            raise ManifestReadError("manifest size is outside the allowed bound")
        chunks: list[bytes] = []
        total = 0
        while total <= MAX_MANIFEST_BYTES:
            chunk = os.read(descriptor, min(64 * 1024, MAX_MANIFEST_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total > MAX_MANIFEST_BYTES:
            raise ManifestReadError("manifest exceeds the 1 MiB bound")
        after = os.fstat(descriptor)
        if _identity(before) != _identity(after) or after.st_size != total:
            raise ManifestReadError("manifest changed while it was being read")
        current = os.stat(path, follow_symlinks=False)
        if not stat.S_ISREG(current.st_mode) or _identity(after) != _identity(current):
            raise ManifestReadError("manifest path changed while it was being read")
        payload = b"".join(chunks)
    except OSError as error:
        if isinstance(error, ManifestReadError):
            raise
        raise ManifestReadError("manifest could not be read safely") from error
    finally:
        os.close(descriptor)
    return LifecycleManifestV1.from_bytes(payload)


def _identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


__all__ = ["ManifestReadError", "load_lifecycle_manifest"]
