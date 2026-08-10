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
    # Validate the complete closed object before it can be hashed.  This also
    # rejects a future caller accidentally adding an unsupported value.
    return validate_json_object(manifest)


def source_revision_id_for(manifest: JsonObject) -> RevisionId:
    """Derive the v3 revision identity from exactly one canonical manifest."""

    canonical = canonical_json_bytes(validate_json_object(manifest))
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
