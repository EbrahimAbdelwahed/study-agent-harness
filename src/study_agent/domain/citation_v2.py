"""Versioned citation contracts that resolve only from canonical bytes.

``TextCitationV2`` and ``FigureCitationV1`` are versioned successors: v0.1
``Citation`` keeps its meaning and its codec permanently, per ADR-0014, so old
events and exports stay readable.

A citation commits to identity and to the hash of the exact quoted bytes.
Locators, page numbers, and anchors are hints or links and never participate in
identity, so no index, snippet, or derived artifact can stand in for canonical
evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ._validation import JsonObject, require_text
from .identifiers import RevisionId, SourceId, SubstrateId, UnitId

TEXT_CITATION_VERSION = 2
FIGURE_CITATION_VERSION = 1


class CitationFailureKind(StrEnum):
    """The exact vocabulary of citation verification failures."""

    MISSING = "missing"
    CORRUPT = "corrupt"
    OUT_OF_UNIT = "out_of_unit"
    MISMATCHED_CHECKSUM = "mismatched_checksum"
    UNSUPPORTED_VERSION = "unsupported_version"
    REFERENCE_MISMATCH = "reference_mismatch"
    MALFORMED_SPAN = "malformed_span"
    NOT_A_CITATION = "not_a_citation"


class CitationFailure(ValueError):
    """Raised when a citation cannot be verified. Always fails closed."""

    def __init__(self, kind: CitationFailureKind, message: str) -> None:
        super().__init__(f"{kind.value}: {message}")
        self.kind = kind


def _digest(value: str, field_name: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return value


@dataclass(frozen=True, slots=True)
class TextCitationV2:
    """A citation into one frozen substrate, bound to one unit occurrence."""

    source_id: SourceId
    revision_id: RevisionId
    unit_id: UnitId
    substrate_id: SubstrateId
    start: int
    end: int
    quoted_sha256: str
    locator: str | None = None
    page_hint: int | None = None

    def __post_init__(self) -> None:
        for value, expected, name in (
            (self.source_id, SourceId, "source_id"),
            (self.revision_id, RevisionId, "revision_id"),
            (self.unit_id, UnitId, "unit_id"),
            (self.substrate_id, SubstrateId, "substrate_id"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{name} must be {expected.__name__}")
        if type(self.start) is not int or type(self.end) is not int:
            raise ValueError("citation offsets must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("citation span must be a non-empty forward range")
        _digest(self.quoted_sha256, "quoted_sha256")
        if self.locator is not None:
            require_text(self.locator, "locator")
        if self.page_hint is not None and (
            type(self.page_hint) is not int or self.page_hint < 1
        ):
            raise ValueError("page_hint must be a positive integer when present")

    @property
    def version(self) -> int:
        return TEXT_CITATION_VERSION

    def to_json(self) -> JsonObject:
        return {
            "end": self.end,
            "locator": self.locator,
            "page_hint": self.page_hint,
            "quoted_sha256": self.quoted_sha256,
            "revision_id": str(self.revision_id),
            "source_id": str(self.source_id),
            "start": self.start,
            "substrate_id": str(self.substrate_id),
            "unit_id": str(self.unit_id),
            "version": TEXT_CITATION_VERSION,
        }


@dataclass(frozen=True, slots=True)
class FigureCitationV1:
    """A citation to an image. Identity is the image bytes themselves."""

    figure_sha256: str
    byte_length: int
    anchor_unit_id: UnitId | None = None
    page_hint: int | None = None

    def __post_init__(self) -> None:
        _digest(self.figure_sha256, "figure_sha256")
        if type(self.byte_length) is not int or self.byte_length < 1:
            raise ValueError("figure byte_length must be positive")
        if self.anchor_unit_id is not None and not isinstance(self.anchor_unit_id, UnitId):
            raise TypeError("anchor_unit_id must be UnitId or None")
        if self.page_hint is not None and (
            type(self.page_hint) is not int or self.page_hint < 1
        ):
            raise ValueError("page_hint must be a positive integer when present")

    @property
    def version(self) -> int:
        return FIGURE_CITATION_VERSION

    def to_json(self) -> JsonObject:
        return {
            "anchor_unit_id": (
                None if self.anchor_unit_id is None else str(self.anchor_unit_id)
            ),
            "byte_length": self.byte_length,
            "figure_sha256": self.figure_sha256,
            "page_hint": self.page_hint,
            "version": FIGURE_CITATION_VERSION,
        }


type Citation = TextCitationV2 | FigureCitationV1


@dataclass(frozen=True, slots=True)
class DerivedRef:
    """Model- or index-produced text. Never evidence, always labelled.

    A derived reference must name the canonical citation it is about, so a
    reader can always reach the real bytes behind a summary or a handle.
    """

    producer: str
    producer_version: str
    text: str
    subject: Citation

    def __post_init__(self) -> None:
        require_text(self.producer, "producer")
        require_text(self.producer_version, "producer_version")
        if not isinstance(self.text, str) or not self.text:
            raise ValueError("derived text must be non-empty")
        if not isinstance(self.subject, (TextCitationV2, FigureCitationV1)):
            raise TypeError("derived text must name a canonical subject citation")

    @property
    def is_canonical(self) -> bool:
        """Always false. Derived text can never be cited as evidence."""
        return False

    def to_json(self) -> JsonObject:
        return {
            "derived": True,
            "producer": self.producer,
            "producer_version": self.producer_version,
            "subject": self.subject.to_json(),
            "text": self.text,
        }


__all__ = [
    "FIGURE_CITATION_VERSION",
    "TEXT_CITATION_VERSION",
    "Citation",
    "CitationFailure",
    "CitationFailureKind",
    "DerivedRef",
    "FigureCitationV1",
    "TextCitationV2",
]
