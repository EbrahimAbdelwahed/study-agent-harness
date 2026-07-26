"""Immutable, provider-neutral contracts for canonical text substrates.

The substrate is the only citable text byte sequence in the knowledge-base
spine.  Page mappings are structural metadata over Unicode code-point spans;
they never alter substrate identity.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from ._validation import JsonObject, require_aware, require_text
from .identifiers import (
    SourceId,
    SubstrateId,
    SubstrateProductionId,
    substrate_production_id_for,
)
from .source import BlobRef


@dataclass(frozen=True, slots=True)
class PageMapEntry:
    """The page beginning at a normalized-text Unicode code-point offset."""

    offset: int
    page: int

    def __post_init__(self) -> None:
        if type(self.offset) is not int or self.offset < 0:
            raise ValueError("page-map offset must be a non-negative integer")
        if type(self.page) is not int or self.page < 1:
            raise ValueError("page-map page must be a positive integer")

    @property
    def char_offset(self) -> int:
        """Alias used by geometric connector profiles."""
        return self.offset

    @property
    def page_number(self) -> int:
        return self.page

    def to_json(self) -> JsonObject:
        return {"offset": self.offset, "page": self.page}


def validate_page_map(
    page_count: int | None,
    page_map: Sequence[PageMapEntry],
    character_length: int,
) -> tuple[PageMapEntry, ...]:
    """Validate the exact absent/present pagination contract."""
    if type(character_length) is not int or character_length < 1:
        raise ValueError("substrate character length must be positive")
    entries = tuple(page_map)
    if page_count is None:
        if entries:
            raise ValueError("page_map must be empty when page_count is absent")
        return entries
    if type(page_count) is not int or page_count < 1:
        raise ValueError("page_count must be positive when page_map is present")
    if not entries:
        raise ValueError("page_map cannot be empty when page_count is present")
    previous_offset = -1
    previous_page = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, PageMapEntry):
            raise TypeError("page_map entries must be PageMapEntry values")
        if index == 0 and entry.offset != 0:
            raise ValueError("page_map must begin at offset zero")
        if entry.offset <= previous_offset:
            raise ValueError("page_map offsets must be strictly increasing")
        if entry.offset >= character_length:
            raise ValueError("page_map offsets must be within substrate bounds")
        if entry.page <= previous_page:
            raise ValueError("page_map pages must be strictly increasing")
        if entry.page > page_count:
            raise ValueError("page_map page exceeds page_count")
        previous_offset = entry.offset
        previous_page = entry.page
    return entries


@dataclass(frozen=True, slots=True)
class Substrate:
    """A frozen normalized-text artifact addressed by content hash."""

    substrate_id: SubstrateId
    blob: BlobRef
    normalized_character_length: int
    normalization_version: str
    page_count: int | None = None
    page_map: tuple[PageMapEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.substrate_id, SubstrateId):
            raise TypeError("substrate_id must be SubstrateId")
        if not isinstance(self.blob, BlobRef):
            raise TypeError("substrate blob must be BlobRef")
        if str(self.blob.id) != f"sha256:{self.blob.checksum_sha256}":
            raise ValueError("substrate blob id must match its SHA-256 checksum")
        expected_blob_id = f"sha256:{self.substrate_id.value.removeprefix('substrate:sha256:')}"
        if str(self.blob.id) != expected_blob_id:
            raise ValueError("substrate blob must contain the exact substrate bytes")
        if (
            type(self.normalized_character_length) is not int
            or self.normalized_character_length < 1
        ):
            raise ValueError("normalized_character_length must be positive")
        require_text(self.normalization_version, "normalization_version")
        object.__setattr__(
            self,
            "page_map",
            validate_page_map(
                self.page_count, self.page_map, self.normalized_character_length
            ),
        )

    @property
    def id(self) -> SubstrateId:
        return self.substrate_id

    @property
    def character_length(self) -> int:
        return self.normalized_character_length

    def to_json(self) -> JsonObject:
        return {
            "blob": {
                "byte_length": self.blob.byte_length,
                "checksum_sha256": self.blob.checksum_sha256,
                "id": str(self.blob.id),
            },
            "normalization_version": self.normalization_version,
            "normalized_character_length": self.normalized_character_length,
            "page_count": self.page_count,
            "page_map": tuple(entry.to_json() for entry in self.page_map),
            "substrate_id": str(self.substrate_id),
        }


@dataclass(frozen=True, slots=True)
class SubstrateProduction:
    """Immutable provenance for one converter/admission production."""

    substrate_production_id: SubstrateProductionId
    source_id: SourceId
    original_blob: BlobRef
    substrate: Substrate
    converter_name: str
    converter_version: str
    normalization_version: str
    admission_policy_version: str
    page_map_policy_version: str
    produced_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.substrate_production_id, SubstrateProductionId):
            raise TypeError("substrate_production_id must be SubstrateProductionId")
        if not isinstance(self.source_id, SourceId):
            raise TypeError("source_id must be SourceId")
        if not isinstance(self.original_blob, BlobRef):
            raise TypeError("original_blob must be BlobRef")
        if str(self.original_blob.id) != f"sha256:{self.original_blob.checksum_sha256}":
            raise ValueError("original_blob id must match its SHA-256 checksum")
        if not isinstance(self.substrate, Substrate):
            raise TypeError("substrate must be Substrate")
        if self.substrate.normalization_version != self.normalization_version:
            raise ValueError("production and substrate normalization versions differ")
        for value, field_name in (
            (self.converter_name, "converter_name"),
            (self.converter_version, "converter_version"),
            (self.normalization_version, "normalization_version"),
            (self.admission_policy_version, "admission_policy_version"),
            (self.page_map_policy_version, "page_map_policy_version"),
        ):
            require_text(value, field_name)
        require_aware(self.produced_at, "produced_at")
        normalized_at = self.produced_at.astimezone(UTC)
        object.__setattr__(self, "produced_at", normalized_at)
        expected = substrate_production_id_for(
            source_id=self.source_id,
            original_blob_id=str(self.original_blob.id),
            original_blob_sha256=self.original_blob.checksum_sha256,
            original_blob_byte_length=self.original_blob.byte_length,
            substrate_id=self.substrate.substrate_id,
            converter_name=self.converter_name,
            converter_version=self.converter_version,
            normalization_version=self.normalization_version,
            page_map_policy_version=self.page_map_policy_version,
            page_count=self.substrate.page_count,
            page_map=tuple(entry.to_json() for entry in self.substrate.page_map),
            admission_policy_version=self.admission_policy_version,
            character_length=self.substrate.normalized_character_length,
        )
        if self.substrate_production_id != expected:
            raise ValueError("substrate production id does not match immutable receipt fields")

    @property
    def production_id(self) -> SubstrateProductionId:
        return self.substrate_production_id

    @property
    def original_blob_ref(self) -> BlobRef:
        return self.original_blob

    def to_json(self) -> JsonObject:
        return {
            "admission_policy_version": self.admission_policy_version,
            "converter_name": self.converter_name,
            "converter_version": self.converter_version,
            "original_blob": {
                "byte_length": self.original_blob.byte_length,
                "checksum_sha256": self.original_blob.checksum_sha256,
                "id": str(self.original_blob.id),
            },
            "page_map_policy_version": self.page_map_policy_version,
            "produced_at": self.produced_at.astimezone(UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z"),
            "source_id": str(self.source_id),
            "substrate": self.substrate.to_json(),
            "substrate_production_id": str(self.substrate_production_id),
        }


# Descriptive aliases keep callers independent of the event naming choice.
SubstrateProductionReceipt = SubstrateProduction
NormalizedTextSubstrate = Substrate

__all__ = [
    "NormalizedTextSubstrate",
    "PageMapEntry",
    "Substrate",
    "SubstrateProduction",
    "SubstrateProductionReceipt",
    "validate_page_map",
]
