"""Neutral, deterministic identity helpers for immutable source revisions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256

from ._validation import JsonObject, JsonValue
from .identifiers import RevisionId

# Public facade and ingestion revisions share one identity domain.  The
# ingestion module keeps its old constant as an alias below so persisted
# callers do not grow a second hash namespace while migrating to the facade.
SOURCE_REVISION_ID_NAMESPACE = "study-agent-source-revision-v2"
SOURCE_REVISION_ID_PREFIX = "revision-sha256:"
INGESTION_REVISION_ID_NAMESPACE = SOURCE_REVISION_ID_NAMESPACE


def _jsonable(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _canonical_json_bytes(value: JsonObject) -> bytes:
    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def source_revision_id_for(
    manifest: JsonObject,
    *,
    namespace: str = SOURCE_REVISION_ID_NAMESPACE,
    identifier_prefix: str = SOURCE_REVISION_ID_PREFIX,
) -> RevisionId:
    """Derive an immutable revision ID from one canonical manifest.

    Callers own the manifest schema. This module owns the canonical JSON
    encoding and hash domain so source values and ingestion events cannot drift
    into separate identity algorithms.
    """

    if not isinstance(manifest, Mapping):
        raise TypeError("source revision identity manifest must be an object")
    if not namespace or namespace != namespace.strip():
        raise ValueError("source revision identity namespace must be non-empty text")
    if not identifier_prefix or identifier_prefix != identifier_prefix.strip():
        raise ValueError("source revision identifier prefix must be non-empty text")
    payload = namespace.encode("utf-8") + b"\0" + _canonical_json_bytes(manifest)
    return RevisionId(f"{identifier_prefix}{sha256(payload).hexdigest()}")


def verify_source_revision_id(
    revision_id: RevisionId,
    manifest: JsonObject,
    *,
    namespace: str = SOURCE_REVISION_ID_NAMESPACE,
    identifier_prefix: str = SOURCE_REVISION_ID_PREFIX,
) -> None:
    """Reject a revision manifest whose declared identity has been forged."""

    expected = source_revision_id_for(
        manifest,
        namespace=namespace,
        identifier_prefix=identifier_prefix,
    )
    if revision_id != expected:
        raise ValueError("revision_id does not match the canonical source manifest")


__all__ = (
    "INGESTION_REVISION_ID_NAMESPACE",
    "SOURCE_REVISION_ID_NAMESPACE",
    "SOURCE_REVISION_ID_PREFIX",
    "source_revision_id_for",
    "verify_source_revision_id",
)
