"""Provider-neutral source-content lookup and integrity errors."""

from __future__ import annotations

from enum import StrEnum


class SourceContentErrorCode(StrEnum):
    NOT_FOUND = "not_found"
    INTEGRITY_ERROR = "integrity_error"
    OWNERSHIP_MISMATCH = "ownership_mismatch"
    OUT_OF_BOUNDS = "out_of_bounds"
    QUOTE_MISMATCH = "quote_mismatch"


class SourceContentError(Exception):
    def __init__(self, code: SourceContentErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
