"""The single current source-revision identity contract."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import TYPE_CHECKING

from ._validation import JsonObject, JsonValue
from .bounded_json import MAX_METADATA_BYTES, canonical_json_bytes, validate_json_object
from .identifiers import RevisionId, SourceId, SubstrateId

if TYPE_CHECKING:
    from .source import BlobRef


SOURCE_REVISION_ID_NAMESPACE = b"study-agent/source-revision/v3\0"
SOURCE_REVISION_ID_PREFIX = "revision-sha256:"
_MANIFEST_KEYS = frozenset(
    {
        "blob",
        "media_type",
        "metadata",
        "normalization_version",
        "source_id",
        "substrate_id",
    }
)
_BLOB_KEYS = frozenset({"byte_length", "checksum_sha256", "id"})


def _trimmed(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


def source_revision_manifest(
    *,
    source_id: SourceId,
    blob: BlobRef,
    media_type: str,
    normalization_version: str,
    substrate_id: SubstrateId,
    metadata: Mapping[str, JsonValue],
) -> JsonObject:
    """Build the closed v3 manifest used by every current source path."""

    if not isinstance(source_id, SourceId):
        raise TypeError("source_id must be SourceId")
    from .source import BlobRef as BlobRefType

    if not isinstance(blob, BlobRefType):
        raise TypeError("blob must be BlobRef")
    if not blob.is_content_addressed:
        raise ValueError("blob id must match its SHA-256 checksum")
    if not isinstance(substrate_id, SubstrateId):
        raise TypeError("substrate_id must be SubstrateId")
    _trimmed(media_type, "media_type")
    _trimmed(normalization_version, "normalization_version")
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a JSON object")
    canonical_metadata = validate_json_object(metadata, max_bytes=MAX_METADATA_BYTES)
    manifest: JsonObject = {
        "blob": blob.to_json(),
        "media_type": media_type,
        "metadata": canonical_metadata,
        "normalization_version": normalization_version,
        "source_id": str(source_id),
        "substrate_id": str(substrate_id),
    }
    return _validate_manifest(manifest)


def _validate_manifest(value: object) -> JsonObject:
    """Validate the exact six-field manifest before identity derivation."""

    manifest = validate_json_object(value)
    if frozenset(manifest) != _MANIFEST_KEYS:
        raise ValueError("source revision manifest fields mismatch")

    for field in ("source_id", "media_type", "normalization_version", "substrate_id"):
        _trimmed(manifest.get(field), f"manifest.{field}")

    blob = manifest.get("blob")
    if not isinstance(blob, Mapping) or frozenset(blob) != _BLOB_KEYS:
        raise ValueError("source revision manifest blob fields mismatch")
    checksum = blob.get("checksum_sha256")
    blob_id = blob.get("id")
    byte_length = blob.get("byte_length")
    if (
        not isinstance(checksum, str)
        or len(checksum) != 64
        or any(character not in "0123456789abcdef" for character in checksum)
    ):
        raise ValueError("source revision manifest blob checksum is invalid")
    if blob_id != f"sha256:{checksum}":
        raise ValueError("source revision manifest blob id does not match checksum")
    if type(byte_length) is not int or byte_length < 0:
        raise ValueError("source revision manifest blob length is invalid")
    validate_json_object(manifest.get("metadata"), max_bytes=MAX_METADATA_BYTES)
    return manifest


def source_revision_id_for(manifest: JsonObject) -> RevisionId:
    """Derive the v3 revision identity from exactly one canonical manifest."""

    canonical = canonical_json_bytes(_validate_manifest(manifest))
    digest = sha256(SOURCE_REVISION_ID_NAMESPACE + canonical).hexdigest()
    return RevisionId(f"{SOURCE_REVISION_ID_PREFIX}{digest}")


def verify_source_revision_id(revision_id: RevisionId, manifest: JsonObject) -> None:
    """Reject a revision whose declared ID does not authenticate its manifest."""

    expected = source_revision_id_for(manifest)
    if revision_id != expected:
        raise ValueError("revision_id does not match the canonical source manifest")


# This name remains as a source-compatible import for old callers.  It is not
# used by current ingestion; historical identity derivations live in
# ``study_agent.ingestion.legacy`` and are replay-only.
INGESTION_REVISION_ID_NAMESPACE = SOURCE_REVISION_ID_NAMESPACE


__all__ = [
    "INGESTION_REVISION_ID_NAMESPACE",
    "SOURCE_REVISION_ID_NAMESPACE",
    "SOURCE_REVISION_ID_PREFIX",
    "source_revision_id_for",
    "source_revision_manifest",
    "verify_source_revision_id",
]
