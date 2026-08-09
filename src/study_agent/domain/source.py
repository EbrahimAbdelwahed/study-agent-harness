from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256

from ._validation import JsonObject, freeze_object, require_aware, require_text
from .identifiers import BlobId, ChunkId, RevisionId, SourceId, SubstrateId
from .provenance import ContentOrigin, StructureOrigin

_SHA256_HEX_LENGTH = 64


def _require_sha256(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _SHA256_HEX_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return value


def _canonical_metadata(value: Mapping[str, object]) -> object:
    """Return metadata in a JSON-safe form for deterministic revision codecs."""
    if not isinstance(value, Mapping):
        raise ValueError("source metadata must be a JSON object")

    def jsonable(item: object) -> object:
        if isinstance(item, Mapping):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("source metadata object keys must be strings")
            return {key: jsonable(nested) for key, nested in item.items()}
        if isinstance(item, (tuple, list)):
            return [jsonable(nested) for nested in item]
        if item is None or isinstance(item, (str, int, bool)):
            return item
        if isinstance(item, float) and item == item and item not in (
            float("inf"),
            float("-inf"),
        ):
            return item
        raise ValueError("source metadata must contain only JSON values")

    try:
        return json.loads(
            json.dumps(
                jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        )
    except (TypeError, ValueError) as error:
        raise ValueError("source metadata must contain only JSON values") from error


def _encode_metadata(value: Mapping[str, object]) -> JsonObject:
    encoded = _canonical_metadata(value)
    if not isinstance(encoded, Mapping):  # pragma: no cover - checked by the caller
        raise TypeError("source metadata must be a JSON object")
    return encoded  # type: ignore[return-value]


class SourceKind(StrEnum):
    TEXT = "text"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class BlobRef:
    id: BlobId
    checksum_sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if not isinstance(self.id, BlobId):
            raise TypeError("blob id must be BlobId")
        _require_sha256(self.checksum_sha256, "checksum_sha256")
        if type(self.byte_length) is not int or self.byte_length < 0:
            raise ValueError("byte_length must be non-negative")

    @classmethod
    def from_bytes(cls, content: bytes) -> BlobRef:
        """Create the canonical reference for exact bytes without retaining them."""
        if type(content) is not bytes:
            raise TypeError("blob content must be bytes")
        checksum = sha256(content).hexdigest()
        return cls(BlobId(f"sha256:{checksum}"), checksum, len(content))

    @property
    def is_content_addressed(self) -> bool:
        """Whether the legacy reference carries its canonical SHA-256 id."""
        return str(self.id) == f"sha256:{self.checksum_sha256}"

    def to_json(self) -> JsonObject:
        return {
            "byte_length": self.byte_length,
            "checksum_sha256": self.checksum_sha256,
            "id": str(self.id),
        }


@dataclass(frozen=True, slots=True)
class SourceRevisionRef:
    """The logical-source and immutable-revision pair used by host contracts."""

    source_id: SourceId
    revision_id: RevisionId

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise TypeError("source_id must be SourceId")
        if not isinstance(self.revision_id, RevisionId):
            raise TypeError("revision_id must be RevisionId")

    def to_json(self) -> JsonObject:
        return {"revision_id": str(self.revision_id), "source_id": str(self.source_id)}


@dataclass(frozen=True, slots=True)
class SubstrateRef:
    """A frozen normalized-text substrate reference, separate from its source blob."""

    substrate_id: SubstrateId
    blob: BlobRef
    normalized_character_length: int
    normalization_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.substrate_id, SubstrateId):
            raise TypeError("substrate_id must be SubstrateId")
        if not isinstance(self.blob, BlobRef):
            raise TypeError("substrate blob must be BlobRef")
        if not self.blob.is_content_addressed:
            raise ValueError("substrate blob must be content-addressed")
        expected = f"substrate:sha256:{self.blob.checksum_sha256}"
        if str(self.substrate_id) != expected:
            raise ValueError("substrate_id must match its immutable blob")
        if type(self.normalized_character_length) is not int or (
            self.normalized_character_length < 1
        ):
            raise ValueError("normalized_character_length must be positive")
        require_text(self.normalization_version, "normalization_version")

    @property
    def id(self) -> SubstrateId:
        return self.substrate_id

    def to_json(self) -> JsonObject:
        return {
            "blob": self.blob.to_json(),
            "normalization_version": self.normalization_version,
            "normalized_character_length": self.normalized_character_length,
            "substrate_id": str(self.substrate_id),
        }


@dataclass(frozen=True, slots=True)
class SourceRevision:
    """The minimal immutable source revision contract.

    ``SourceRevision`` intentionally carries references, not source bytes. The
    host-owned blob port supplies bytes when needed, while ``metadata`` remains
    opaque to the harness and cannot participate in citation resolution.
    """

    source_id: SourceId
    revision_id: RevisionId
    blob: BlobRef
    media_type: str
    created_at: datetime
    normalization_version: str
    substrate_id: SubstrateId
    metadata: JsonObject = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        source_id: SourceId,
        content: bytes,
        media_type: str,
        created_at: datetime,
        normalization_version: str,
        substrate_id: SubstrateId,
        metadata: Mapping[str, object] | None = None,
    ) -> SourceRevision:
        """Create a revision with an identity derived from its exact manifest.

        The timestamp is provenance, not identity. Retrying an identical
        capture therefore returns the same revision ID, while changed raw
        bytes, substrate, or manifest metadata produce a different ID.
        """
        blob = BlobRef.from_bytes(content)
        manifest = {
            "blob": blob.to_json(),
            "media_type": media_type,
            "metadata": _canonical_metadata(metadata or {}),
            "normalization_version": normalization_version,
            "source_id": str(source_id),
            "substrate_id": str(substrate_id),
        }
        identity_bytes = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        digest = sha256(b"study-agent/source-revision/v1\0" + identity_bytes).hexdigest()
        revision_id = RevisionId(f"revision:sha256:{digest}")
        return cls(
            source_id,
            revision_id,
            blob,
            media_type,
            created_at,
            normalization_version,
            substrate_id,
            {} if metadata is None else metadata,  # type: ignore[arg-type]
        )

    @classmethod
    def from_content(cls, **kwargs: object) -> SourceRevision:
        """Compatibility spelling for hosts that model ingestion as capture."""
        return cls.create(**kwargs)  # type: ignore[arg-type]

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise TypeError("source_id must be SourceId")
        if not isinstance(self.revision_id, RevisionId):
            raise TypeError("revision_id must be RevisionId")
        if not isinstance(self.blob, BlobRef):
            raise TypeError("blob must be BlobRef")
        if not self.blob.is_content_addressed:
            raise ValueError("source revision blob must be content-addressed")
        if not isinstance(self.substrate_id, SubstrateId):
            raise TypeError("substrate_id must be SubstrateId")
        require_text(self.media_type, "media_type")
        require_text(self.normalization_version, "normalization_version")
        require_aware(self.created_at, "created_at")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "metadata", freeze_object(_encode_metadata(self.metadata)))

    @property
    def ref(self) -> SourceRevisionRef:
        return SourceRevisionRef(self.source_id, self.revision_id)

    @property
    def content_blob(self) -> BlobRef:
        return self.blob

    @property
    def normalized_substrate_id(self) -> SubstrateId:
        return self.substrate_id

    def to_json(self) -> JsonObject:
        return {
            "blob": self.blob.to_json(),
            "created_at": self.created_at.isoformat(timespec="microseconds"),
            "media_type": self.media_type,
            "metadata": _encode_metadata(self.metadata),
            "normalization_version": self.normalization_version,
            "revision_id": str(self.revision_id),
            "source_id": str(self.source_id),
            "substrate_id": str(self.substrate_id),
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, object]) -> SourceRevision:
        """Decode exactly one revision manifest without accepting extra fields."""
        if not isinstance(payload, Mapping):
            raise ValueError("source revision payload must be an object")
        expected = {
            "blob",
            "created_at",
            "media_type",
            "metadata",
            "normalization_version",
            "revision_id",
            "source_id",
            "substrate_id",
        }
        if set(payload) != expected:
            raise ValueError("source revision fields mismatch")
        blob_payload = payload["blob"]
        if not isinstance(blob_payload, Mapping) or set(blob_payload) != {
            "byte_length",
            "checksum_sha256",
            "id",
        }:
            raise ValueError("source revision blob fields mismatch")
        byte_length = blob_payload["byte_length"]
        checksum = blob_payload["checksum_sha256"]
        blob_id = blob_payload["id"]
        if type(byte_length) is not int or not isinstance(checksum, str) or not isinstance(
            blob_id, str
        ):
            raise ValueError("source revision blob fields have invalid types")
        metadata = payload["metadata"]
        if not isinstance(metadata, Mapping):
            raise ValueError("source revision metadata must be an object")
        created_at = payload["created_at"]
        media_type = payload["media_type"]
        normalization_version = payload["normalization_version"]
        revision_id = payload["revision_id"]
        source_id = payload["source_id"]
        substrate_id = payload["substrate_id"]
        if not all(
            isinstance(value, str)
            for value in (
                created_at,
                media_type,
                normalization_version,
                revision_id,
                source_id,
                substrate_id,
            )
        ):
            raise ValueError("source revision scalar fields have invalid types")
        try:
            timestamp = datetime.fromisoformat(created_at)
        except ValueError as error:
            raise ValueError("source revision created_at must be ISO-8601") from error
        return cls(
            SourceId(source_id),
            RevisionId(revision_id),
            BlobRef(BlobId(blob_id), checksum, byte_length),
            media_type,
            timestamp,
            normalization_version,
            SubstrateId(substrate_id),
            metadata,  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class SourceDocument:
    source_id: SourceId
    revision_id: RevisionId
    kind: SourceKind
    title: str
    media_type: str
    checksum_sha256: str
    byte_length: int
    created_at: datetime
    trust_level: int
    source_role: str
    blob: BlobRef
    normalized_blob: BlobRef
    normalization_version: str
    normalized_character_length: int
    structure_origin: StructureOrigin
    ingestion_method: str
    content_origin: ContentOrigin = ContentOrigin.ORIGINAL

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise TypeError("source_id must be SourceId")
        if not isinstance(self.revision_id, RevisionId):
            raise TypeError("revision_id must be RevisionId")
        if not isinstance(self.kind, SourceKind):
            raise TypeError("kind must be SourceKind")
        if not isinstance(self.blob, BlobRef) or not isinstance(self.normalized_blob, BlobRef):
            raise TypeError("source blobs must be BlobRef values")
        if not isinstance(self.structure_origin, StructureOrigin):
            raise TypeError("structure_origin must be StructureOrigin")
        if not isinstance(self.content_origin, ContentOrigin):
            raise TypeError("content_origin must be ContentOrigin")
        require_text(self.title, "title")
        require_text(self.media_type, "media_type")
        require_text(self.source_role, "source_role")
        require_text(self.ingestion_method, "ingestion_method")
        require_text(self.normalization_version, "normalization_version")
        _require_sha256(self.checksum_sha256, "checksum_sha256")
        if type(self.byte_length) is not int or self.byte_length < 0:
            raise ValueError("byte_length must be non-negative")
        if type(self.normalized_character_length) is not int or (
            self.normalized_character_length < 1
        ):
            raise ValueError("normalized_character_length must be positive")
        require_aware(self.created_at, "created_at")
        if self.checksum_sha256 != self.blob.checksum_sha256:
            raise ValueError("source checksum must match its immutable blob")
        if self.byte_length != self.blob.byte_length:
            raise ValueError("source byte_length must match its immutable blob")
        if str(self.blob.id) != f"sha256:{self.blob.checksum_sha256}":
            raise ValueError("source blob id must match its SHA-256 checksum")
        if str(self.normalized_blob.id) != f"sha256:{self.normalized_blob.checksum_sha256}":
            raise ValueError("normalized blob id must match its SHA-256 checksum")
        if type(self.trust_level) is not int or not 0 <= self.trust_level <= 100:
            raise ValueError("trust_level must be between 0 and 100")

    @property
    def substrate_id(self) -> SubstrateId:
        """The normalized substrate identity derived from its immutable bytes."""
        return SubstrateId(f"substrate:sha256:{self.normalized_blob.checksum_sha256}")

    @property
    def revision_ref(self) -> SourceRevisionRef:
        return SourceRevisionRef(self.source_id, self.revision_id)


@dataclass(frozen=True, slots=True)
class SourceChunk:
    chunk_id: ChunkId
    source_id: SourceId
    revision_id: RevisionId
    start_offset: int
    end_offset: int
    section_path: tuple[str, ...]
    ordinal: int
    checksum_sha256: str
    chunker_version: str
    metadata: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "section_path", tuple(self.section_path))
        if self.start_offset < 0 or self.end_offset <= self.start_offset:
            raise ValueError("chunk offsets must describe a non-empty forward span")
        if self.ordinal < 0:
            raise ValueError("ordinal must be non-negative")
        _require_sha256(self.checksum_sha256, "checksum_sha256")
        require_text(self.chunker_version, "chunker_version")
        for section in self.section_path:
            require_text(section, "section_path item")
        object.__setattr__(self, "metadata", freeze_object(self.metadata))


@dataclass(frozen=True, slots=True)
class Citation:
    source_id: SourceId
    revision_id: RevisionId
    chunk_id: ChunkId
    start_offset: int
    end_offset: int
    locator: str
    quoted_snippet: str | None = None

    def __post_init__(self) -> None:
        if self.start_offset < 0 or self.end_offset <= self.start_offset:
            raise ValueError("citation offsets must describe a non-empty forward span")
        require_text(self.locator, "locator")
        if self.quoted_snippet is not None and not self.quoted_snippet:
            raise ValueError("quoted_snippet must be non-empty when supplied")


@dataclass(frozen=True, slots=True)
class ResolvedCitation:
    citation: Citation
    text: str

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("resolved citation text must be non-empty")
        if self.citation.quoted_snippet is not None and self.citation.quoted_snippet != self.text:
            raise ValueError("resolved text must match the citation's quoted snippet")


__all__ = [
    "BlobRef",
    "Citation",
    "ResolvedCitation",
    "SourceChunk",
    "SourceDocument",
    "SourceKind",
    "SourceRevision",
    "SourceRevisionRef",
    "SubstrateRef",
]
