"""Provider-neutral contracts for immutable, bounded source snapshots."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_SOURCES = 4096
MAX_TOTAL_SOURCE_BYTES = 512 * 1024 * 1024

_MAX_RELATIVE_PATH_LENGTH = 256
_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    """Exact immutable bytes captured from one portable relative source path."""

    relative_path: str
    content: bytes
    checksum_sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        _validate_relative_source_path(self.relative_path)
        if type(self.content) is not bytes:
            raise ValueError("source snapshot content must be bytes")
        if type(self.byte_size) is not int or not 0 <= self.byte_size <= MAX_SOURCE_BYTES:
            raise ValueError(
                f"source snapshot byte_size must be between 0 and {MAX_SOURCE_BYTES}"
            )
        if self.byte_size != len(self.content):
            raise ValueError("source snapshot byte_size must match its captured content")
        try:
            self.content.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise ValueError(
                "source snapshot content must contain strict UTF-8 text"
            ) from None
        if (
            not isinstance(self.checksum_sha256, str)
            or _LOWERCASE_SHA256.fullmatch(self.checksum_sha256) is None
            or self.checksum_sha256 != sha256(self.content).hexdigest()
        ):
            raise ValueError(
                "source snapshot checksum_sha256 must be the lowercase SHA-256 of its content"
            )

    @property
    def filename(self) -> str:
        return self.relative_path.rsplit("/", 1)[-1]


class SourceInputPort(Protocol):
    """Capture exact source bytes beneath an adapter-owned trusted root."""

    def snapshot(self, relative_path: str) -> SourceSnapshot: ...

    def snapshots(self, relative_paths: Sequence[str]) -> tuple[SourceSnapshot, ...]: ...


def _validate_relative_source_path(value: object) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > _MAX_RELATIVE_PATH_LENGTH
        or value.startswith(("/", "\\"))
        or "\\" in value
        or ":" in value
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        raise ValueError("source snapshot relative_path must be a portable relative path")
    parts = value.split("/")
    if any(
        not part
        or part in {".", ".."}
        or part.endswith((" ", "."))
        or part.split(".", 1)[0].upper() in _WINDOWS_DEVICE_NAMES
        for part in parts
    ):
        raise ValueError("source snapshot relative_path must use portable path components")
    if not value.endswith((".txt", ".md")):
        raise ValueError("source snapshot relative_path must identify a .txt or .md file")


__all__ = [
    "MAX_SOURCE_BYTES",
    "MAX_TOTAL_SOURCES",
    "MAX_TOTAL_SOURCE_BYTES",
    "SourceInputPort",
    "SourceSnapshot",
]
