"""Private v0.1/v2 identity compatibility used only during replay."""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256

from study_agent.domain.bounded_json import canonical_json_bytes
from study_agent.domain.identifiers import RevisionId, SourceId
from study_agent.domain.source import SourceDocument, SourceKind


class HistoricalIdentityVariant(StrEnum):
    PUBLIC_MANIFEST = "public-manifest"
    INGESTION_V2 = "ingestion-v2"
    WEAK_V01 = "weak-v0.1"


_HISTORICAL_NAMESPACE = b"study-agent-source-revision-v2\0"


def _historical_json_revision_id(manifest: dict[str, object]) -> RevisionId:
    return RevisionId(
        "revision-sha256:"
        + sha256(_HISTORICAL_NAMESPACE + canonical_json_bytes(manifest)).hexdigest()
    )


def historical_public_manifest_revision_id(
    *,
    source: SourceDocument,
    chunker_version: str,
    max_characters: int,
) -> RevisionId:
    """Recompute the historical facade manifest identity exactly."""

    return _historical_json_revision_id(
        {
            "blob": source.blob.to_json(),
            "media_type": source.media_type,
            "metadata": {
                "chunker_version": chunker_version,
                "kind": source.kind.value,
                "max_characters": max_characters,
                "source_role": source.source_role,
                "title": source.title,
                "trust_level": source.trust_level,
            },
            "normalization_version": source.normalization_version,
            "source_id": str(source.source_id),
            "substrate_id": str(source.substrate_id),
        }
    )


def historical_ingestion_v2_revision_id(
    *,
    original_sha256: str,
    source_id: SourceId,
    kind: SourceKind,
    title: str,
    trust_level: int,
    source_role: str,
    normalization_version: str,
    chunker_version: str,
    max_characters: int,
) -> RevisionId:
    """Recompute the metadata-bearing ingestion identity used by old events."""

    return _historical_json_revision_id(
        {
            "chunker_version": chunker_version,
            "kind": kind.value,
            "max_characters": max_characters,
            "normalization_version": normalization_version,
            "original_sha256": original_sha256,
            "source_id": str(source_id),
            "source_role": source_role,
            "title": title,
            "trust_level": trust_level,
        }
    )


def legacy_revision_id_for(
    *,
    original_sha256: str,
    source_id: SourceId,
    kind: SourceKind,
    normalization_version: str,
    chunker_version: str,
    max_characters: int,
) -> RevisionId:
    """Reconstruct the weak v0.1 identity with its original byte recipe."""

    identity = (
        f"{source_id}\0{original_sha256}\0{kind.value}\0{normalization_version}\0"
        f"{chunker_version}\0{max_characters}"
    ).encode()
    return RevisionId(f"revision-sha256:{sha256(identity).hexdigest()}")


def classify_historical_identity(
    *,
    source: SourceDocument,
    chunker_version: str,
    max_characters: int,
) -> HistoricalIdentityVariant:
    """Require exactly one known historical identity to authenticate."""

    candidates: list[HistoricalIdentityVariant] = []
    if source.revision_id == historical_public_manifest_revision_id(
        source=source,
        chunker_version=chunker_version,
        max_characters=max_characters,
    ):
        candidates.append(HistoricalIdentityVariant.PUBLIC_MANIFEST)
    if source.revision_id == historical_ingestion_v2_revision_id(
        original_sha256=source.checksum_sha256,
        source_id=source.source_id,
        kind=source.kind,
        title=source.title,
        trust_level=source.trust_level,
        source_role=source.source_role,
        normalization_version=source.normalization_version,
        chunker_version=chunker_version,
        max_characters=max_characters,
    ):
        candidates.append(HistoricalIdentityVariant.INGESTION_V2)
    if source.revision_id == legacy_revision_id_for(
        original_sha256=source.checksum_sha256,
        source_id=source.source_id,
        kind=source.kind,
        normalization_version=source.normalization_version,
        chunker_version=chunker_version,
        max_characters=max_characters,
    ):
        candidates.append(HistoricalIdentityVariant.WEAK_V01)
    if len(candidates) != 1:
        raise ValueError("historical source revision identity is ambiguous or unknown")
    return candidates[0]


__all__ = [
    "HistoricalIdentityVariant",
    "classify_historical_identity",
    "historical_ingestion_v2_revision_id",
    "historical_public_manifest_revision_id",
    "legacy_revision_id_for",
]
