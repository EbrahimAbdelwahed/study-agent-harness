"""Deterministic local-source ingestion state contracts."""

from .chunking import CHUNKER_VERSION, ChunkingConfig, chunk_text
from .events import (
    SOURCE_REVISION_INGESTED,
    SOURCE_REVISION_SCHEMA_VERSION,
    BlobLoader,
    PersistedChunkingConfig,
    SourceRevisionIngested,
    decode_source_revision_event,
    decode_source_revision_ingested,
)
from .identity import (
    CHUNK_MAX_CHARACTERS,
    CHUNKER_POLICY_VERSION,
    NORMALIZATION_POLICY_VERSION,
    chunk_id_for,
    revision_id_for,
    source_event_id_for,
    source_kind_contract,
)
from .normalization import (
    NORMALIZATION_VERSION,
    InvalidUtf8Error,
    NormalizedText,
    normalize_utf8,
)
from .projection import (
    chunk_manifest,
    reduce_source_revision,
    register_source_revision_events,
    source_manifest,
    source_revision_payload,
)
from .service import (
    IngestionErrorCode,
    IngestionStatus,
    TextIngestionError,
    TextIngestionResult,
    TextIngestionService,
)

__all__ = [
    "CHUNKER_POLICY_VERSION",
    "CHUNKER_VERSION",
    "CHUNK_MAX_CHARACTERS",
    "NORMALIZATION_POLICY_VERSION",
    "NORMALIZATION_VERSION",
    "SOURCE_REVISION_INGESTED",
    "SOURCE_REVISION_SCHEMA_VERSION",
    "BlobLoader",
    "ChunkingConfig",
    "IngestionErrorCode",
    "IngestionStatus",
    "InvalidUtf8Error",
    "NormalizedText",
    "PersistedChunkingConfig",
    "SourceRevisionIngested",
    "TextIngestionError",
    "TextIngestionResult",
    "TextIngestionService",
    "chunk_id_for",
    "chunk_manifest",
    "chunk_text",
    "decode_source_revision_event",
    "decode_source_revision_ingested",
    "normalize_utf8",
    "reduce_source_revision",
    "register_source_revision_events",
    "revision_id_for",
    "source_event_id_for",
    "source_kind_contract",
    "source_manifest",
    "source_revision_payload",
]
