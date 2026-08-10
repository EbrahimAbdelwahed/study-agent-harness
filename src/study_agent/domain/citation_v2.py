"""Versioned citation contracts that resolve only from canonical bytes.

``TextCitationV2`` and ``FigureCitationV1`` are versioned successors: v0.1
``Citation`` keeps its meaning and its codec permanently, per ADR-0014, so old
events and exports stay readable.

A citation commits to identity and to the hash of the exact quoted bytes.
Locators, page numbers, and anchors are hints or links and never participate in
identity, so no index, snippet, or derived artifact can stand in for canonical
evidence.

Spans are code-point exact by design (ADR-0014). A span may therefore split a
grapheme cluster; the quoted hash stays consistent, but the rendered fragment
may not read the way a human would expect. This is accepted deliberately
rather than silently widened, because widening a span would change what was
cited.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from ._validation import JsonObject, require_text
from .identifiers import RevisionId, SourceId, SubstrateId, UnitId

TEXT_CITATION_VERSION = 2
FIGURE_CITATION_VERSION = 1

#: A locator is a short human hint, never a second channel for text.
MAX_LOCATOR_LENGTH = 128


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
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return value


def _object(value: object, name: str, fields: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or frozenset(value) != fields:
        raise ValueError(f"{name} fields mismatch")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    require_text(value, name)
    return value


def _integer(value: object, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def _optional_text(value: object, name: str) -> str | None:
    if value is not None:
        return _text(value, name)
    return None


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _jsonable(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(child) for child in value]
    return value


def _canonical_bytes(value: JsonObject) -> bytes:
    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _decode_bytes(data: bytes, name: str) -> JsonObject:
    if not isinstance(data, bytes):
        raise CitationFailure(CitationFailureKind.CORRUPT, f"{name} bytes must be bytes")
    try:
        decoded: Any = json.loads(data)
        if not isinstance(decoded, dict):
            raise ValueError(f"{name} must be a JSON object")
        value = cast(JsonObject, decoded)
        canonical = _canonical_bytes(value)
    except (TypeError, UnicodeError, ValueError) as error:
        raise CitationFailure(
            CitationFailureKind.CORRUPT,
            f"{name} bytes are not valid canonical JSON",
        ) from error
    if canonical != data:
        raise CitationFailure(
            CitationFailureKind.CORRUPT,
            f"{name} bytes are not canonical",
        )
    return value


def _require_codec_version(
    payload: Mapping[str, Any], expected: int, name: str
) -> None:
    version = payload.get("version")
    if type(version) is not int:
        raise CitationFailure(
            CitationFailureKind.CORRUPT,
            f"{name} version must be an integer",
        )
    if version != expected:
        raise CitationFailure(
            CitationFailureKind.UNSUPPORTED_VERSION,
            f"unsupported {name} version: {version}",
        )


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
            if not isinstance(self.locator, str):
                raise TypeError("locator must be text or None")
            require_text(self.locator, "locator")
            if len(self.locator) > MAX_LOCATOR_LENGTH:
                raise ValueError(
                    f"locator must be at most {MAX_LOCATOR_LENGTH} characters"
                )
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

    @classmethod
    def from_json(cls, value: JsonObject) -> TextCitationV2:
        try:
            if not isinstance(value, Mapping):
                raise ValueError("text citation must be an object")
            _require_codec_version(value, TEXT_CITATION_VERSION, "text citation")
            payload = _object(
                value,
                "text citation",
                frozenset(
                    {
                        "end",
                        "locator",
                        "page_hint",
                        "quoted_sha256",
                        "revision_id",
                        "source_id",
                        "start",
                        "substrate_id",
                        "unit_id",
                        "version",
                    }
                ),
            )
            page_hint = payload.get("page_hint")
            if page_hint is not None:
                page_hint = _integer(page_hint, "page_hint")
            locator = _optional_text(payload.get("locator"), "locator")
            return cls(
                SourceId(_text(payload.get("source_id"), "source_id")),
                RevisionId(_text(payload.get("revision_id"), "revision_id")),
                UnitId(_text(payload.get("unit_id"), "unit_id")),
                SubstrateId(_text(payload.get("substrate_id"), "substrate_id")),
                _integer(payload.get("start"), "start"),
                _integer(payload.get("end"), "end"),
                _text(payload.get("quoted_sha256"), "quoted_sha256"),
                locator,
                page_hint,
            )
        except CitationFailure:
            raise
        except (TypeError, UnicodeError, ValueError) as error:
            raise CitationFailure(
                CitationFailureKind.CORRUPT,
                "text citation payload is malformed",
            ) from error

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> TextCitationV2:
        return cls.from_json(_decode_bytes(data, "text citation"))


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

    @classmethod
    def from_json(cls, value: JsonObject) -> FigureCitationV1:
        try:
            if not isinstance(value, Mapping):
                raise ValueError("figure citation must be an object")
            _require_codec_version(value, FIGURE_CITATION_VERSION, "figure citation")
            payload = _object(
                value,
                "figure citation",
                frozenset(
                    {
                        "anchor_unit_id",
                        "byte_length",
                        "figure_sha256",
                        "page_hint",
                        "version",
                    }
                ),
            )
            anchor = payload.get("anchor_unit_id")
            if anchor is not None:
                anchor = UnitId(_text(anchor, "anchor_unit_id"))
            page_hint = payload.get("page_hint")
            if page_hint is not None:
                page_hint = _integer(page_hint, "page_hint")
            return cls(
                _text(payload.get("figure_sha256"), "figure_sha256"),
                _integer(payload.get("byte_length"), "byte_length"),
                anchor,
                page_hint,
            )
        except CitationFailure:
            raise
        except (TypeError, UnicodeError, ValueError) as error:
            raise CitationFailure(
                CitationFailureKind.CORRUPT,
                "figure citation payload is malformed",
            ) from error

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> FigureCitationV1:
        return cls.from_json(_decode_bytes(data, "figure citation"))


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
        if not isinstance(self.producer, str) or not isinstance(self.producer_version, str):
            raise TypeError("derived producer fields must be text")
        require_text(self.producer, "producer")
        require_text(self.producer_version, "producer_version")
        if not isinstance(self.text, str):
            raise TypeError("derived text must be text")
        require_text(self.text, "derived text")
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

    @classmethod
    def from_json(cls, value: JsonObject) -> DerivedRef:
        try:
            payload = _object(
                value,
                "derived reference",
                frozenset(
                    {"derived", "producer", "producer_version", "subject", "text"}
                ),
            )
            if payload.get("derived") is not True:
                raise ValueError("derived reference marker must be true")
            subject = payload.get("subject")
            if not isinstance(subject, Mapping):
                raise ValueError("derived reference subject must be an object")
            return cls(
                _text(payload.get("producer"), "producer"),
                _text(payload.get("producer_version"), "producer_version"),
                _text(payload.get("text"), "text"),
                citation_from_json(cast(JsonObject, subject)),
            )
        except CitationFailure:
            raise
        except (TypeError, UnicodeError, ValueError) as error:
            raise CitationFailure(
                CitationFailureKind.CORRUPT,
                "derived reference payload is malformed",
            ) from error

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> DerivedRef:
        return cls.from_json(_decode_bytes(data, "derived reference"))


def citation_from_json(value: JsonObject) -> Citation:
    """Decode one canonical citation without accepting derived text as evidence."""
    if not isinstance(value, Mapping):
        raise CitationFailure(CitationFailureKind.CORRUPT, "citation must be an object")
    version = value.get("version")
    if type(version) is not int:
        raise CitationFailure(
            CitationFailureKind.CORRUPT, "citation version must be an integer"
        )
    if version == TEXT_CITATION_VERSION:
        return TextCitationV2.from_json(value)
    if version == FIGURE_CITATION_VERSION:
        return FigureCitationV1.from_json(value)
    raise CitationFailure(
        CitationFailureKind.UNSUPPORTED_VERSION,
        f"unsupported citation version: {version}",
    )


def citation_from_bytes(data: bytes) -> Citation:
    """Decode one canonical citation from its stable UTF-8 JSON bytes."""
    return citation_from_json(_decode_bytes(data, "citation"))


__all__ = [
    "FIGURE_CITATION_VERSION",
    "TEXT_CITATION_VERSION",
    "Citation",
    "CitationFailure",
    "CitationFailureKind",
    "DerivedRef",
    "FigureCitationV1",
    "TextCitationV2",
    "citation_from_bytes",
    "citation_from_json",
]
