"""Explicit source succession: codec, reducer, and lineage read contracts.

Succession is structural and explicit.  It never migrates a citation, never
changes which revision is current, and never consults a timestamp or a recency
prior.  Selection remains reversible and is owned by the existing
``source.revision_selected@1`` event.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.events import DomainEvent, PrincipalKind
from study_agent.domain.identifiers import (
    BlobId,
    RevisionId,
    SourceId,
    SubstrateId,
    SubstrateProductionId,
)
from study_agent.domain.lineage import (
    RevisionLineage,
    RevisionManifest,
    RevisionRef,
    SelectionStatus,
    SourceLineage,
    SourceSuccession,
)
from study_agent.domain.source import BlobRef, SourceKind

from .identity import source_superseded_by_event_id_for

SOURCE_SUPERSEDED_BY = "source.superseded_by"
SOURCE_SUPERSEDED_BY_SCHEMA_VERSION = 1

_TOP_LEVEL_KEYS = frozenset({"predecessor", "reason", "successor"})
_ENDPOINT_KEYS = frozenset({"revision_id", "source_id"})


# --- codec ----------------------------------------------------------------


def source_superseded_by_payload(succession: SourceSuccession) -> JsonObject:
    if not isinstance(succession, SourceSuccession):
        raise TypeError("succession payload requires SourceSuccession")
    return succession.to_json()


def decode_source_superseded_by(payload: JsonObject) -> SourceSuccession:
    top = _object(payload, "payload", _TOP_LEVEL_KEYS)
    return SourceSuccession(
        _endpoint(top.get("predecessor"), "predecessor"),
        _endpoint(top.get("successor"), "successor"),
        _text(top.get("reason"), "reason"),
    )


def decode_source_superseded_by_event(event: DomainEvent) -> SourceSuccession:
    if (
        event.event_type != SOURCE_SUPERSEDED_BY
        or event.schema_version != SOURCE_SUPERSEDED_BY_SCHEMA_VERSION
    ):
        raise ValueError("event envelope does not match source.superseded_by@1")
    decoded = decode_source_superseded_by(event.payload)
    expected_id = source_superseded_by_event_id_for(
        event.course_id,
        decoded.predecessor.source_id,
        decoded.predecessor.revision_id,
        decoded.successor.source_id,
        decoded.successor.revision_id,
        event.course_sequence,
    )
    if event.event_id != expected_id:
        raise ValueError("event_id does not match succession identity")
    if event.actor.kind is not PrincipalKind.SERVICE:
        raise ValueError("succession events require a service actor")
    return decoded


# --- reducer --------------------------------------------------------------


def reduce_source_superseded_by(
    state: JsonObject, _: DomainEvent, payload: SourceSuccession
) -> Mapping[str, JsonValue]:
    """Record one succession edge after rejecting every invalid shape."""
    sources = _mapping(state.get("sources", {}), "sources")
    _require_endpoint(sources, payload.predecessor)
    _require_endpoint(sources, payload.successor)

    successions = _edges(state)
    index = _index(successions)
    encoded = payload.to_json()
    existing = index.get(_key(payload.predecessor))
    if existing is not None:
        if existing != payload.successor:
            raise ValueError("revision already has a different declared successor")
        return state
    if _reaches(index, payload.successor, payload.predecessor):
        raise ValueError("succession would create a cycle")
    return {**state, "successions": (*successions, encoded)}


def _key(ref: RevisionRef) -> tuple[str, str]:
    """An in-memory lookup key; never persisted, so it needs no separator."""
    return str(ref.source_id), str(ref.revision_id)


def _index(successions: tuple[JsonObject, ...]) -> dict[tuple[str, str], RevisionRef]:
    """Build the predecessor lookup once per call.

    The persisted shape stays an append-ordered array — a composite string key
    would need a separator that no identifier is guaranteed to exclude — but
    rebuilding this index once keeps a single append linear instead of
    quadratic in the number of accumulated edges.
    """
    index: dict[tuple[str, str], RevisionRef] = {}
    for edge in successions:
        predecessor = _endpoint(edge.get("predecessor"), "predecessor")
        index[_key(predecessor)] = _endpoint(edge.get("successor"), "successor")
    return index


def _edges(state: JsonObject) -> tuple[JsonObject, ...]:
    """Return the append-ordered succession edges held in projection state."""
    value = state.get("successions", ())
    if not isinstance(value, tuple):
        raise ValueError("projection field successions must be an array")
    return tuple(_mapping(edge, "successions entry") for edge in value)


def _reaches(
    index: Mapping[tuple[str, str], RevisionRef],
    start: RevisionRef,
    target: RevisionRef,
) -> bool:
    """Whether ``target`` is reachable by following successor edges."""
    current = start
    seen: set[tuple[str, str]] = set()
    while True:
        if current == target:
            return True
        key = _key(current)
        if key in seen:
            return False
        seen.add(key)
        following = index.get(key)
        if following is None:
            return False
        current = following


# --- read contracts -------------------------------------------------------


def revision_selection_status(
    state: JsonObject, source_id: SourceId, revision_id: RevisionId
) -> SelectionStatus:
    """Report whether one existing revision is current or inactive."""
    source = _require_source(_mapping(state.get("sources", {}), "sources"), source_id)
    revisions = _mapping(source.get("revisions", {}), "revisions")
    if str(revision_id) not in revisions:
        raise KeyError(f"unknown revision: {revision_id}")
    if source.get("current_revision_id") == str(revision_id):
        return SelectionStatus.CURRENT
    return SelectionStatus.INACTIVE


def successor_of(
    state: JsonObject, source_id: SourceId, revision_id: RevisionId
) -> RevisionRef | None:
    """Return the explicitly declared successor of one revision, if any."""
    return _index(_edges(state)).get(_key(RevisionRef(source_id, revision_id)))


def revision_manifest(
    state: JsonObject, source_id: SourceId, revision_id: RevisionId
) -> RevisionManifest:
    """Rebuild the v0.2 manifest of one revision from projection state."""
    source = _require_source(_mapping(state.get("sources", {}), "sources"), source_id)
    revisions = _mapping(source.get("revisions", {}), "revisions")
    revision = revisions.get(str(revision_id))
    if revision is None:
        raise KeyError(f"unknown revision: {revision_id}")
    manifest = _mapping(_mapping(revision, "revision").get("source"), "revision.source")
    normalized = _mapping(manifest.get("normalized_blob"), "normalized_blob")
    checksum = _text(normalized.get("checksum_sha256"), "normalized_blob.checksum_sha256")
    substrate_id = SubstrateId(f"substrate:sha256:{checksum}")
    return RevisionManifest(
        source_id,
        revision_id,
        substrate_id,
        _blob(manifest.get("blob"), "blob"),
        _text(manifest.get("normalization_version"), "normalization_version"),
        SourceKind(_text(manifest.get("kind"), "kind")),
        _text(manifest.get("title"), "title"),
        _text(manifest.get("source_role"), "source_role"),
        _integer(manifest.get("trust_level"), "trust_level"),
        _production_for(state, substrate_id, source_id),
    )


def source_lineage(state: JsonObject, source_id: SourceId) -> SourceLineage:
    """Return every revision of one source with selection and succession."""
    source = _require_source(_mapping(state.get("sources", {}), "sources"), source_id)
    revision_ids = source.get("revision_ids", ())
    if not isinstance(revision_ids, tuple) or any(
        not isinstance(item, str) for item in revision_ids
    ):
        raise ValueError("source revision_ids projection field is invalid")
    ordered = cast(tuple[str, ...], revision_ids)
    return SourceLineage(
        source_id,
        tuple(
            RevisionLineage(
                revision_manifest(state, source_id, RevisionId(value)),
                revision_selection_status(state, source_id, RevisionId(value)),
                successor_of(state, source_id, RevisionId(value)),
            )
            for value in ordered
        ),
    )


def eligible_revision_ids(state: JsonObject, source_id: SourceId) -> tuple[RevisionId, ...]:
    """Default retrieval eligibility: the current revision only.

    Historical revisions stay fully readable through :func:`source_lineage` and
    :func:`revision_manifest`; they are merely not default retrieval targets.
    """
    current = source_lineage(state, source_id).current
    return () if current is None else (current.manifest.revision_id,)


def _production_for(
    state: JsonObject, substrate_id: SubstrateId, source_id: SourceId
) -> SubstrateProductionId | None:
    """Find the substrate production receipt bound to this source, if any."""
    productions = _mapping(state.get("substrate_productions", {}), "substrate_productions")
    index = _mapping(
        state.get("substrate_productions_by_source", {}), "substrate_productions_by_source"
    )
    candidates = index.get(str(source_id), ())
    if not isinstance(candidates, tuple):
        raise ValueError("substrate production source index is invalid")
    for candidate in candidates:
        if not isinstance(candidate, str):
            raise ValueError("substrate production source index is invalid")
        receipt = productions.get(candidate)
        if not isinstance(receipt, Mapping):
            raise ValueError("substrate production receipt is invalid")
        substrate = receipt.get("substrate")
        if (
            isinstance(substrate, Mapping)
            and substrate.get("substrate_id") == str(substrate_id)
        ):
            return SubstrateProductionId(candidate)
    return None


# --- helpers --------------------------------------------------------------


def _require_source(sources: Mapping[str, JsonValue], source_id: SourceId) -> JsonObject:
    source = sources.get(str(source_id))
    if source is None:
        raise KeyError(f"unknown source: {source_id}")
    return _mapping(source, f"sources.{source_id}")


def _require_endpoint(sources: Mapping[str, JsonValue], ref: RevisionRef) -> None:
    source = sources.get(str(ref.source_id))
    if source is None:
        raise ValueError("succession endpoint source does not exist")
    revisions = _mapping(source, "source").get("revisions", {})
    if str(ref.revision_id) not in _mapping(revisions, "revisions"):
        raise ValueError("succession endpoint revision does not exist")


def _object(value: JsonValue | None, name: str, keys: frozenset[str]) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    actual = frozenset(value)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise ValueError(f"{name} fields mismatch; missing={missing}, extra={extra}")
    return value


def _endpoint(value: JsonValue | None, name: str) -> RevisionRef:
    payload = _object(value, name, _ENDPOINT_KEYS)
    return RevisionRef(
        SourceId(_text(payload.get("source_id"), f"{name}.source_id")),
        RevisionId(_text(payload.get("revision_id"), f"{name}.revision_id")),
    )


def _blob(value: JsonValue | None, name: str) -> BlobRef:
    payload = _mapping(value, name)
    checksum = _text(payload.get("checksum_sha256"), f"{name}.checksum_sha256")
    blob_id = _text(payload.get("id"), f"{name}.id")
    if blob_id != f"sha256:{checksum}":
        raise ValueError(f"{name}.id must match its SHA-256 checksum")
    return BlobRef(BlobId(blob_id), checksum, _integer(payload.get("byte_length"), name))


def _mapping(value: JsonValue | None, name: str) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ValueError(f"projection field {name} must be an object")
    return value


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


def _integer(value: JsonValue | None, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


__all__ = [
    "SOURCE_SUPERSEDED_BY",
    "SOURCE_SUPERSEDED_BY_SCHEMA_VERSION",
    "decode_source_superseded_by",
    "decode_source_superseded_by_event",
    "eligible_revision_ids",
    "reduce_source_superseded_by",
    "revision_manifest",
    "revision_selection_status",
    "source_lineage",
    "source_superseded_by_payload",
    "successor_of",
]
