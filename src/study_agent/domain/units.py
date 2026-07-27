"""One strict, provider-neutral shape for every retrievable unit.

Every indexable text, figure, table, fragment, and exam item shares this row.
``unit_kind`` and ``granularity`` drive ranking priors, expansion, and filters
— never a separate code path, and never a source-specific branch.

Canonical text is deliberately absent: a unit references substrate spans or
image blobs and the bytes are loaded and checksum-verified on demand, which is
what keeps every index discardable and stops a tampered index from producing an
unsupported citation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ._validation import JsonObject, require_text
from .identifiers import RevisionId, SourceId, SubstrateId, UnitId


class UnitKind(StrEnum):
    """The closed set of retrievable unit kinds."""

    DOCUMENT_CARD = "document_card"
    SECTION = "section"
    PASSAGE = "passage"
    DEFINITION = "definition"
    EMPHASIS = "emphasis"
    SUMMARY = "summary"
    TABLE = "table"
    ITEM = "item"
    FIGURE = "figure"
    EXAM_ITEM = "exam_item"


class ReviewStatus(StrEnum):
    """Whether a human has reviewed the unit's structural derivation."""

    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"
    REJECTED = "rejected"


class LinkKind(StrEnum):
    """Typed, bounded relations between units."""

    PARENT = "parent"
    ANCHORED_IN = "anchored_in"
    DERIVED_FROM = "derived_from"
    REFERENCES = "references"


#: Granularity bands allowed for each kind (§5.1).
_ALLOWED_GRANULARITY: dict[UnitKind, frozenset[int]] = {
    UnitKind.DOCUMENT_CARD: frozenset({0}),
    UnitKind.SECTION: frozenset({1, 2}),
    UnitKind.PASSAGE: frozenset({3}),
    UnitKind.DEFINITION: frozenset({4}),
    UnitKind.EMPHASIS: frozenset({4}),
    UnitKind.SUMMARY: frozenset({4}),
    UnitKind.TABLE: frozenset({4}),
    UnitKind.ITEM: frozenset({4}),
    UnitKind.FIGURE: frozenset({4}),
    UnitKind.EXAM_ITEM: frozenset({4}),
}

#: The only kind whose canonical reference is an image blob rather than text.
_BLOB_KINDS = frozenset({UnitKind.FIGURE})

_MAX_LINKS = 64

#: Free-text unit fields are labels, never a second channel for canonical text.
_MAX_LABEL = 128


def _require_label(value: str, field_name: str) -> None:
    require_text(value, field_name)
    if len(value) > _MAX_LABEL:
        raise ValueError(f"{field_name} must be at most {_MAX_LABEL} characters")


@dataclass(frozen=True, slots=True)
class TextSpan:
    """A half-open Unicode code-point span over one frozen substrate."""

    substrate_id: SubstrateId
    start: int
    end: int

    def __post_init__(self) -> None:
        if not isinstance(self.substrate_id, SubstrateId):
            raise TypeError("substrate_id must be SubstrateId")
        if type(self.start) is not int or type(self.end) is not int:
            raise ValueError("span offsets must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("span must be a non-empty forward code-point range")

    def to_json(self) -> JsonObject:
        return {
            "end": self.end,
            "kind": "text_span",
            "start": self.start,
            "substrate_id": str(self.substrate_id),
        }


@dataclass(frozen=True, slots=True)
class FigureBlob:
    """Content identity of one image: the hash of the image bytes themselves."""

    checksum_sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if len(self.checksum_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.checksum_sha256
        ):
            raise ValueError("figure checksum must be a lowercase SHA-256 hex digest")
        if type(self.byte_length) is not int or self.byte_length < 1:
            raise ValueError("figure byte_length must be positive")

    def to_json(self) -> JsonObject:
        return {
            "byte_length": self.byte_length,
            "checksum_sha256": self.checksum_sha256,
            "kind": "figure_blob",
        }


type CanonicalRef = TextSpan | FigureBlob


@dataclass(frozen=True, slots=True)
class UnitMeta:
    """Provenance and presentation hints that must survive replay."""

    source_class: str
    role: str
    trust_level: int
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    flags: frozenset[str] = field(default_factory=frozenset)
    ordinal: int = 0
    page_hint: int | None = None
    language: str | None = None

    def __post_init__(self) -> None:
        _require_label(self.source_class, "source_class")
        _require_label(self.role, "role")
        if type(self.trust_level) is not int or not 0 <= self.trust_level <= 100:
            raise ValueError("trust_level must be an integer between 0 and 100")
        if not isinstance(self.review_status, ReviewStatus):
            raise TypeError("review_status must be ReviewStatus")
        flags = frozenset(self.flags)
        for flag in flags:
            if not isinstance(flag, str):
                raise TypeError("flags must be strings")
            _require_label(flag, "flag")
        object.__setattr__(self, "flags", flags)
        if type(self.ordinal) is not int or self.ordinal < 0:
            raise ValueError("ordinal must be a non-negative integer")
        if self.page_hint is not None and (
            type(self.page_hint) is not int or self.page_hint < 1
        ):
            raise ValueError("page_hint must be a positive integer when present")
        if self.language is not None:
            _require_label(self.language, "language")

    def to_json(self) -> JsonObject:
        return {
            "flags": tuple(sorted(self.flags)),
            "language": self.language,
            "ordinal": self.ordinal,
            "page_hint": self.page_hint,
            "review_status": self.review_status.value,
            "role": self.role,
            "source_class": self.source_class,
            "trust_level": self.trust_level,
        }


@dataclass(frozen=True, slots=True)
class UnitLink:
    """One typed relation to a known unit or an explicit provisional target."""

    kind: LinkKind
    target: UnitId | None
    provisional_target: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, LinkKind):
            raise TypeError("link kind must be LinkKind")
        if (self.target is None) == (self.provisional_target is None):
            raise ValueError(
                "a link must reference exactly one known unit or one provisional target"
            )
        if self.target is not None and not isinstance(self.target, UnitId):
            raise TypeError("link target must be UnitId")
        if self.provisional_target is not None:
            _require_label(self.provisional_target, "provisional_target")

    @property
    def is_provisional(self) -> bool:
        return self.target is None

    def to_json(self) -> JsonObject:
        return {
            "kind": self.kind.value,
            "provisional_target": self.provisional_target,
            "target": None if self.target is None else str(self.target),
        }


@dataclass(frozen=True, slots=True)
class UnitSignal:
    """Operational, discardable signal about one unit.

    Signals never participate in unit identity and are not required to
    reconstruct a canonical unit occurrence.
    """

    name: str
    value: float

    def __post_init__(self) -> None:
        require_text(self.name, "signal name")
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise TypeError("signal value must be a real number")
        value = float(self.value)
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("signal value must be finite")
        object.__setattr__(self, "value", value)

    def to_json(self) -> JsonObject:
        return {"name": self.name, "value": self.value}


@dataclass(frozen=True, slots=True)
class RetrievableUnit:
    """One revision-local retrievable occurrence."""

    unit_id: UnitId
    source_id: SourceId
    revision_id: RevisionId
    unit_kind: UnitKind
    granularity: int
    structural_path: tuple[str, ...]
    canonical_ref: CanonicalRef
    meta: UnitMeta
    links: tuple[UnitLink, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.unit_id, UnitId):
            raise TypeError("unit_id must be UnitId")
        if not isinstance(self.source_id, SourceId):
            raise TypeError("source_id must be SourceId")
        if not isinstance(self.revision_id, RevisionId):
            raise TypeError("revision_id must be RevisionId")
        if not isinstance(self.unit_kind, UnitKind):
            raise TypeError("unit_kind must be UnitKind")
        if type(self.granularity) is not int:
            raise ValueError("granularity must be an integer")
        allowed = _ALLOWED_GRANULARITY[self.unit_kind]
        if self.granularity not in allowed:
            raise ValueError(
                f"{self.unit_kind.value} requires granularity in {sorted(allowed)}"
            )
        path = tuple(self.structural_path)
        for segment in path:
            if not isinstance(segment, str):
                raise TypeError("structural_path segments must be strings")
            _require_label(segment, "structural_path segment")
        object.__setattr__(self, "structural_path", path)
        if self.unit_kind in _BLOB_KINDS:
            if not isinstance(self.canonical_ref, FigureBlob):
                raise TypeError("figure units must reference an image blob")
        elif not isinstance(self.canonical_ref, TextSpan):
            raise TypeError("text units must reference a substrate span")
        if not isinstance(self.meta, UnitMeta):
            raise TypeError("meta must be UnitMeta")
        links = tuple(self.links)
        if len(links) > _MAX_LINKS:
            raise ValueError(f"a unit may declare at most {_MAX_LINKS} links")
        seen: set[tuple[str, str | None, str | None]] = set()
        for link in links:
            if not isinstance(link, UnitLink):
                raise TypeError("links must be UnitLink values")
            if link.target == self.unit_id:
                raise ValueError("a unit cannot link to itself")
            key = (
                link.kind.value,
                None if link.target is None else str(link.target),
                link.provisional_target,
            )
            if key in seen:
                raise ValueError("links must be unique per kind and target")
            seen.add(key)
        if sum(1 for link in links if link.kind is LinkKind.PARENT) > 1:
            raise ValueError("a unit may declare at most one parent link")
        object.__setattr__(self, "links", links)

    @property
    def is_figure(self) -> bool:
        return self.unit_kind in _BLOB_KINDS

    @property
    def substrate_id(self) -> SubstrateId | None:
        ref = self.canonical_ref
        return ref.substrate_id if isinstance(ref, TextSpan) else None

    def to_json(self) -> JsonObject:
        return {
            "canonical_ref": self.canonical_ref.to_json(),
            "granularity": self.granularity,
            "links": tuple(link.to_json() for link in self.links),
            "meta": self.meta.to_json(),
            "revision_id": str(self.revision_id),
            "source_id": str(self.source_id),
            "structural_path": self.structural_path,
            "unit_id": str(self.unit_id),
            "unit_kind": self.unit_kind.value,
        }


def decode_canonical_ref(value: JsonObject) -> CanonicalRef:
    """Decode a strict canonical reference; unknown kinds fail closed."""
    kind = value.get("kind")
    if kind == "text_span":
        if frozenset(value) != {"end", "kind", "start", "substrate_id"}:
            raise ValueError("text_span fields mismatch")
        substrate = value.get("substrate_id")
        start = value.get("start")
        end = value.get("end")
        if not isinstance(substrate, str) or type(start) is not int or type(end) is not int:
            raise ValueError("text_span field types are invalid")
        return TextSpan(SubstrateId(substrate), start, end)
    if kind == "figure_blob":
        if frozenset(value) != {"byte_length", "checksum_sha256", "kind"}:
            raise ValueError("figure_blob fields mismatch")
        checksum = value.get("checksum_sha256")
        byte_length = value.get("byte_length")
        if not isinstance(checksum, str) or type(byte_length) is not int:
            raise ValueError("figure_blob field types are invalid")
        return FigureBlob(checksum, byte_length)
    raise ValueError("unsupported canonical reference kind")


__all__ = [
    "CanonicalRef",
    "FigureBlob",
    "LinkKind",
    "RetrievableUnit",
    "ReviewStatus",
    "TextSpan",
    "UnitKind",
    "UnitLink",
    "UnitMeta",
    "UnitSignal",
    "decode_canonical_ref",
]
