"""Atomic deterministic directory writer for public export v1."""

from __future__ import annotations

import ctypes
import errno
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from study_agent.application.export import (
    EXPORT_SCHEMA_VERSION,
    EXPORT_V2_SCHEMA_VERSION,
    ExportBundle,
    ExportBundleV2,
)
from study_agent.domain._validation import JsonObject
from study_agent.state.serialization import canonical_json_bytes


class ExportDestinationExistsError(FileExistsError):
    """The requested immutable export destination already exists."""


class ExportWriteError(OSError):
    """The export could not be published atomically."""


@dataclass(frozen=True, slots=True)
class ExportReceipt:
    destination: Path
    manifest_sha256: str
    high_water_sequence: int


class FilesystemExportWriter:
    """Write one immutable export through a sibling staging directory."""

    def write(self, bundle: ExportBundle | ExportBundleV2, destination: Path) -> ExportReceipt:
        target = destination.expanduser().absolute()
        parent = target.parent
        if target.exists() or target.is_symlink():
            raise ExportDestinationExistsError(str(target))
        if not parent.is_dir():
            raise ExportWriteError(f"export parent directory does not exist: {parent}")

        staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=parent))
        try:
            files = _export_files(bundle)
            for name, content in files.items():
                _write_file(staging / name, content)
            _sync_directory(staging)
            try:
                _rename_no_replace(staging, target)
            except FileExistsError as error:
                raise ExportDestinationExistsError(str(target)) from error
            except OSError as error:
                raise ExportWriteError(f"could not publish export: {target}") from error
            _sync_directory(parent)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        manifest = files["manifest.json"]
        return ExportReceipt(
            target,
            sha256(manifest).hexdigest(),
            bundle.high_water_sequence,
        )


def _export_files(bundle: ExportBundle | ExportBundleV2) -> Mapping[str, bytes]:
    if isinstance(bundle, ExportBundleV2):
        return _export_files_v2(bundle)
    data_files = {
        "course.json": _json_file(bundle.course),
        "sources.json": _json_file(
            {"schema_version": EXPORT_SCHEMA_VERSION, "sources": bundle.sources}
        ),
        "sessions.jsonl": _json_lines(bundle.sessions),
        "answers.jsonl": _json_lines(bundle.answers),
        "events.jsonl": _json_lines(bundle.events),
    }
    manifest: JsonObject = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "course_id": str(bundle.course_id),
        "high_water_sequence": bundle.high_water_sequence,
        "files": tuple(
            {
                "name": name,
                "sha256": sha256(content).hexdigest(),
                "byte_size": len(content),
            }
            for name, content in sorted(data_files.items())
        ),
    }
    return {"manifest.json": _json_file(manifest), **data_files}


def _export_files_v2(bundle: ExportBundleV2) -> Mapping[str, bytes]:
    data_files = {
        "course.json": _json_file(bundle.course),
        "sources.json": _json_file(
            {"schema_version": EXPORT_V2_SCHEMA_VERSION, "sources": bundle.sources}
        ),
        "sessions.jsonl": _json_lines(bundle.sessions),
        "answers.jsonl": _json_lines(bundle.answers),
        "events.jsonl": _json_lines(bundle.events),
        "artifacts.jsonl": _json_lines(bundle.artifacts),
    }
    manifest: JsonObject = {
        "schema_version": EXPORT_V2_SCHEMA_VERSION,
        "course_id": str(bundle.course_id),
        "high_water_sequence": bundle.high_water_sequence,
        "files": tuple(
            {
                "name": name,
                "sha256": sha256(content).hexdigest(),
                "byte_size": len(content),
            }
            for name, content in sorted(data_files.items())
        ),
    }
    return {"manifest.json": _json_file(manifest), **data_files}


def _json_file(value: JsonObject) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _json_lines(values: Sequence[JsonObject]) -> bytes:
    return b"".join(canonical_json_bytes(value) + b"\n" for value in values)


def _write_file(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rename_no_replace(source: Path, destination: Path) -> None:
    """Atomically publish without replacing a destination created by a racer."""
    library = ctypes.CDLL(None, use_errno=True)
    old = os.fsencode(source)
    new = os.fsencode(destination)
    if sys.platform == "darwin":
        rename = library.renameatx_np
        rename.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename.restype = ctypes.c_int
        result = rename(-2, old, -2, new, 0x00000004)  # AT_FDCWD, RENAME_EXCL
    elif sys.platform.startswith("linux"):
        try:
            rename = library.renameat2
        except AttributeError as error:
            raise ExportWriteError("atomic no-replace publication is unavailable") from error
        rename.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename.restype = ctypes.c_int
        result = rename(-100, old, -100, new, 1)  # AT_FDCWD, RENAME_NOREPLACE
    else:
        raise ExportWriteError(
            f"atomic no-replace publication is unsupported on {sys.platform}"
        )
    if result == 0:
        return
    code = ctypes.get_errno()
    if code in (errno.EEXIST, errno.ENOTEMPTY):
        raise ExportDestinationExistsError(str(destination))
    raise OSError(code, os.strerror(code), str(destination))
