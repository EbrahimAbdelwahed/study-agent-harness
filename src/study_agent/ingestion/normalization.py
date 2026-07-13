"""Strict, deterministic canonicalization for local UTF-8 study text."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

NORMALIZATION_VERSION = "utf8-newlines-nfc-v1"


class InvalidUtf8Error(ValueError):
    """Input bytes are not strict UTF-8."""


@dataclass(frozen=True, slots=True)
class NormalizedText:
    text: str
    content: bytes
    version: str = NORMALIZATION_VERSION


def normalize_utf8(content: bytes) -> NormalizedText:
    """Decode strict UTF-8, canonicalize newlines, then normalize Unicode to NFC."""

    if not isinstance(content, bytes):
        raise TypeError("content must be bytes")
    try:
        decoded = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise InvalidUtf8Error("content must be valid UTF-8") from error
    normalized = unicodedata.normalize("NFC", decoded.replace("\r\n", "\n").replace("\r", "\n"))
    return NormalizedText(normalized, normalized.encode("utf-8"))
