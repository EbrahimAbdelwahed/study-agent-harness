from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from study_agent.api.sources import SourceRevision
from study_agent.domain import (
    Actor,
    BlobId,
    BlobRef,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
    RevisionId,
    SourceDocument,
    SourceId,
    SourceKind,
    StructureOrigin,
    SubstrateId,
    substrate_id_for,
)
from study_agent.domain.errors import ValidationFailure
from study_agent.ingestion import (
    CHUNK_MAX_CHARACTERS,
    CHUNKER_POLICY_VERSION,
    NORMALIZATION_POLICY_VERSION,
    SOURCE_REVISION_INGESTED,
    SOURCE_REVISION_SCHEMA_VERSION,
    SOURCE_REVISION_SELECTED,
    SOURCE_REVISION_SELECTED_SCHEMA_VERSION,
    ChunkingConfig,
    chunk_text,
    decode_source_revision_event,
    decode_source_revision_selected_event,
    normalize_utf8,
    register_source_revision_events,
    source_revision_payload,
    source_revision_selected_event_id_for,
    source_revision_selected_payload,
)
from study_agent.ingestion.events import (
    prepare_for_append,
    prepare_for_replay,
    upcast_source_revision_ingested_v1,
)
from study_agent.ingestion.identity import source_revision_ingested_event_id_for
from study_agent.ingestion.legacy import (
    HistoricalIdentityVariant,
    historical_ingestion_v2_revision_id,
    historical_public_manifest_revision_id,
    historical_source_event_id_for,
    legacy_revision_id_for,
)
from study_agent.ingestion.projection import source_revision_payload_v1
from study_agent.state import EventRegistry, PayloadValidationError, Projection, apply_event

type BlobLoader = Callable[[BlobRef], bytes]


def _blob(content: bytes) -> BlobRef:
    digest = sha256(content).hexdigest()
    return BlobRef(BlobId(f"sha256:{digest}"), digest, len(content))


def make_event(
    *,
    sequence: int = 1,
    original: bytes = "Cafe\u0301 🫀 valve".encode(),
    legacy_identity: bool = False,
) -> tuple[DomainEvent, BlobLoader]:
    normalized_text = normalize_utf8(original).text
    normalized = normalized_text.encode()
    original_blob = _blob(original)
    normalized_blob = _blob(normalized)
    source_id = SourceId("source-1")
    occurred_at = datetime(2026, 7, 11, 8, sequence, tzinfo=UTC)
    if legacy_identity:
        revision_id = legacy_revision_id_for(
            original_sha256=original_blob.checksum_sha256,
            source_id=source_id,
            kind=SourceKind.TEXT,
            normalization_version=NORMALIZATION_POLICY_VERSION,
            chunker_version=CHUNKER_POLICY_VERSION,
            max_characters=CHUNK_MAX_CHARACTERS,
        )
    else:
        revision_id = SourceRevision.create(
            source_id=source_id,
            content=original,
            media_type="text/plain",
            created_at=occurred_at,
            normalization_version=NORMALIZATION_POLICY_VERSION,
            substrate_id=substrate_id_for(normalized),
            metadata={
                "kind": SourceKind.TEXT.value,
                "source_role": "primary",
                "title": "Cardiac anatomy",
                "trust_level": 90,
            },
        ).revision_id
    source = SourceDocument(
        source_id,
        revision_id,
        SourceKind.TEXT,
        "Cardiac anatomy",
        "text/plain",
        original_blob.checksum_sha256,
        original_blob.byte_length,
        occurred_at,
        90,
        "primary",
        original_blob,
        normalized_blob,
        NORMALIZATION_POLICY_VERSION,
        len(normalized_text),
        StructureOrigin.MECHANICALLY_EXTRACTED,
        "utf8-text-v1",
    )
    chunks = chunk_text(
        normalized_text,
        source_id=source_id,
        revision_id=revision_id,
        kind=SourceKind.TEXT,
        config=ChunkingConfig(
            max_characters=CHUNK_MAX_CHARACTERS,
            version=CHUNKER_POLICY_VERSION,
        ),
    )
    event = DomainEvent(
        (
            historical_source_event_id_for(CourseId("course-1"), revision_id)
            if legacy_identity
            else source_revision_ingested_event_id_for(
                CourseId("course-1"), revision_id, occurred_at
            )
        ),
        CourseId("course-1"),
        sequence,
        SOURCE_REVISION_INGESTED,
        1 if legacy_identity else SOURCE_REVISION_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "ingestion"),
        occurred_at,
        CorrelationId("correlation-1"),
        (
            source_revision_payload_v1(source, chunks)
            if legacy_identity
            else source_revision_payload(source, chunks)
        ),
    )
    contents = {str(original_blob.id): original, str(normalized_blob.id): normalized}
    return event, lambda ref: contents[str(ref.id)]


def _replace_source(event: DomainEvent, **updates: object) -> DomainEvent:
    source = dict(event.payload["source"])  # type: ignore[arg-type]
    source.update(updates)  # type: ignore[arg-type]
    return DomainEvent(
        event.event_id,
        event.course_id,
        event.course_sequence,
        event.event_type,
        event.schema_version,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        {**event.payload, "source": source},
    )


def test_full_event_decoder_verifies_utf8_nfc_content_spans_and_identities() -> None:
    event, load_blob = make_event()
    decoded = decode_source_revision_event(event, load_blob)

    assert decoded.normalized_character_length == len("Café 🫀 valve")
    assert decoded.source.created_at == event.occurred_at
    assert len(decoded.chunks) == 1


def test_full_event_decoder_preserves_legacy_revision_identity() -> None:
    event, load_blob = make_event(legacy_identity=True)
    decoded = decode_source_revision_event(event, load_blob)
    registry = EventRegistry()
    register_source_revision_events(registry, load_blob)
    source = event.payload.get("source")
    assert isinstance(source, Mapping)
    raw_revision_id = source.get("revision_id")
    assert isinstance(raw_revision_id, str)

    assert str(decoded.source.revision_id) == raw_revision_id
    with pytest.raises(ValidationFailure, match="upcast path is incomplete"):
        registry.decode(event)


def test_schema_one_is_replay_only_and_schema_two_is_the_append_contract() -> None:
    legacy_event, legacy_loader = make_event(legacy_identity=True)
    with pytest.raises(ValueError, match="schema 2"):
        prepare_for_append(legacy_event, legacy_loader)
    replayed = prepare_for_replay(legacy_event, legacy_loader)
    assert replayed.source.revision_id == RevisionId(
        str(legacy_event.payload["source"]["revision_id"])  # type: ignore[index]
    )

    current_event, current_loader = make_event()
    assert prepare_for_append(current_event, current_loader) == decode_source_revision_event(
        current_event, current_loader
    )


@pytest.mark.parametrize("variant", tuple(HistoricalIdentityVariant))
def test_all_historical_identity_variants_replay_through_the_v1_upcaster(
    variant: HistoricalIdentityVariant,
) -> None:
    current_event, loader = make_event()
    current = decode_source_revision_event(current_event, loader)
    if variant is HistoricalIdentityVariant.PUBLIC_MANIFEST:
        revision_id = historical_public_manifest_revision_id(
            source=current.source,
            chunker_version=current.chunking.version,
            max_characters=current.chunking.max_characters,
        )
    elif variant is HistoricalIdentityVariant.INGESTION_V2:
        revision_id = historical_ingestion_v2_revision_id(
            original_sha256=current.source.checksum_sha256,
            source_id=current.source.source_id,
            kind=current.source.kind,
            title=current.source.title,
            trust_level=current.source.trust_level,
            source_role=current.source.source_role,
            normalization_version=current.source.normalization_version,
            chunker_version=current.chunking.version,
            max_characters=current.chunking.max_characters,
        )
    else:
        revision_id = legacy_revision_id_for(
            original_sha256=current.source.checksum_sha256,
            source_id=current.source.source_id,
            kind=current.source.kind,
            normalization_version=current.source.normalization_version,
            chunker_version=current.chunking.version,
            max_characters=current.chunking.max_characters,
        )
    source = replace(current.source, revision_id=revision_id)
    original = loader(source.blob)
    normalized_text = normalize_utf8(original).text
    chunks = chunk_text(
        normalized_text,
        source_id=source.source_id,
        revision_id=revision_id,
        kind=source.kind,
        config=ChunkingConfig(
            max_characters=current.chunking.max_characters,
            version=current.chunking.version,
        ),
    )
    event = DomainEvent(
        historical_source_event_id_for(current_event.course_id, revision_id),
        current_event.course_id,
        current_event.course_sequence,
        SOURCE_REVISION_INGESTED,
        1,
        current_event.actor,
        current_event.occurred_at,
        current_event.correlation_id,
        source_revision_payload_v1(
            source,
            chunks,
            chunker_version=current.chunking.version,
            max_characters=current.chunking.max_characters,
        ),
    )

    replayed = prepare_for_replay(event, loader)
    assert replayed.source.revision_id == revision_id
    if variant is HistoricalIdentityVariant.WEAK_V01:
        assert replayed.source.title == "Legacy source"
        assert replayed.source.trust_level == 0
        assert replayed.source.source_role == "legacy-unverified"
    else:
        assert replayed.source.title == current.source.title
        assert replayed.source.trust_level == current.source.trust_level
        assert replayed.source.source_role == current.source.source_role


def test_facade_revision_identity_decodes_through_ingestion_and_replays() -> None:
    event, load_blob = make_event()
    original = "Cafe\u0301 🫀 valve".encode()
    normalized_text = normalize_utf8(original).text
    normalized = normalized_text.encode()
    source_id = SourceId("source-1")
    metadata = {
        "kind": SourceKind.TEXT.value,
        "source_role": "primary",
        "title": "Cardiac anatomy",
        "trust_level": 90,
    }
    facade_revision = SourceRevision.create(
        source_id=source_id,
        content=original,
        media_type="text/plain",
        created_at=event.occurred_at,
        normalization_version=NORMALIZATION_POLICY_VERSION,
        substrate_id=SubstrateId(
            f"substrate:sha256:{sha256(normalized).hexdigest()}"
        ),
        metadata=metadata,
    )
    source = SourceDocument(
        source_id,
        facade_revision.revision_id,
        SourceKind.TEXT,
        "Cardiac anatomy",
        "text/plain",
        sha256(original).hexdigest(),
        len(original),
        event.occurred_at,
        90,
        "primary",
        _blob(original),
        _blob(normalized),
        NORMALIZATION_POLICY_VERSION,
        len(normalized_text),
        StructureOrigin.MECHANICALLY_EXTRACTED,
        "utf8-text-v1",
    )
    chunks = chunk_text(
        normalized_text,
        source_id=source_id,
        revision_id=facade_revision.revision_id,
        kind=SourceKind.TEXT,
        config=ChunkingConfig(
            max_characters=CHUNK_MAX_CHARACTERS,
            version=CHUNKER_POLICY_VERSION,
        ),
    )
    public_event = DomainEvent(
        source_revision_ingested_event_id_for(
            event.course_id, facade_revision.revision_id, event.occurred_at
        ),
        event.course_id,
        event.course_sequence,
        event.event_type,
        SOURCE_REVISION_SCHEMA_VERSION,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        source_revision_payload(source, chunks),
    )

    decoded = decode_source_revision_event(public_event, load_blob)
    registry = EventRegistry()
    register_source_revision_events(registry, load_blob)
    first = apply_event(Projection(event.course_id), public_event, registry)
    replayed = apply_event(Projection(event.course_id), public_event, registry)

    assert decoded.source.revision_id == facade_revision.revision_id
    assert first.state == replayed.state


def test_legacy_identity_is_a_historical_envelope_for_unencoded_metadata() -> None:
    event, load_blob = make_event(legacy_identity=True)
    source = event.payload["source"]
    assert isinstance(source, Mapping)
    legacy_revision_id = source["revision_id"]
    assert isinstance(legacy_revision_id, str)
    historical = _replace_source(
        event,
        title="Historical title",
        trust_level=10,
        source_role="secondary",
    )

    decoded = upcast_source_revision_ingested_v1(historical, load_blob)

    assert str(decoded.source.revision_id) == legacy_revision_id
    assert decoded.source.title == "Legacy source"
    assert decoded.source.trust_level == 0
    assert decoded.source.source_role == "legacy-unverified"


@pytest.mark.parametrize(
    "updates",
    [
        {"kind": SourceKind.MARKDOWN.value},
        {"normalization_version": "future-normalization-v2"},
        {"revision_id": "revision-sha256:" + "0" * 64},
    ],
)
def test_legacy_decoder_rejects_mutation_of_legacy_identity_inputs(
    updates: dict[str, object],
) -> None:
    event, _ = make_event(legacy_identity=True)

    with pytest.raises(ValueError):
        upcast_source_revision_ingested_v1(_replace_source(event, **updates), lambda _: b"")


def test_payload_decoder_rejects_a_forged_revision_manifest() -> None:
    event, _ = make_event()
    forged = _replace_source(event, title="Forged title")

    with pytest.raises(ValueError, match="revision_id"):
        decode_source_revision_event(forged, lambda _: b"")


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        (lambda event: _replace_source(event, revision_id="revision-arbitrary"), "belong"),
        (
            lambda event: DomainEvent(
                EventId("event-arbitrary"),
                event.course_id,
                event.course_sequence,
                event.event_type,
                event.schema_version,
                event.actor,
                event.occurred_at,
                event.correlation_id,
                event.payload,
            ),
            "event_id",
        ),
        (
            lambda event: DomainEvent(
                event.event_id,
                event.course_id,
                event.course_sequence,
                event.event_type,
                event.schema_version,
                event.actor,
                event.occurred_at,
                event.correlation_id,
                {
                    **event.payload,
                    "chunking": {"version": "arbitrary", "max_characters": 1200},
                },
            ),
            "version",
        ),
        (
            lambda event: _replace_source(
                event,
                created_at=(event.occurred_at + timedelta(seconds=1)).isoformat(),
            ),
            "created_at",
        ),
    ],
)
def test_envelope_decoder_rejects_arbitrary_ids_versions_and_timestamps(
    tamper: Callable[[DomainEvent], DomainEvent], message: str
) -> None:
    event, load_blob = make_event()
    registry = EventRegistry()
    register_source_revision_events(registry, load_blob)

    with pytest.raises(PayloadValidationError, match=message):
        registry.decode(tamper(event))


def test_decoder_rejects_corrupt_normalized_blob_and_chunk_checksum() -> None:
    event, load_blob = make_event()
    decoded = decode_source_revision_event(event, load_blob)

    with pytest.raises(ValueError, match="checksum does not match loaded"):
        decode_source_revision_event(
            event,
            lambda ref: b"x" * ref.byte_length
            if ref == decoded.source.normalized_blob
            else load_blob(ref),
        )

    chunks = list(event.payload["chunks"])  # type: ignore[arg-type]
    first = dict(chunks[0])  # type: ignore[arg-type]
    first["checksum_sha256"] = "0" * 64
    chunks[0] = first
    tampered = DomainEvent(
        event.event_id,
        event.course_id,
        event.course_sequence,
        event.event_type,
        event.schema_version,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        {**event.payload, "chunks": tuple(chunks)},
    )
    with pytest.raises(ValueError, match="checksum"):
        decode_source_revision_event(tampered, load_blob)

    first["checksum_sha256"] = decoded.chunks[0].checksum_sha256
    first["chunk_id"] = "chunk-arbitrary"
    chunks[0] = first
    arbitrary_chunk_id = DomainEvent(
        event.event_id,
        event.course_id,
        event.course_sequence,
        event.event_type,
        event.schema_version,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        {**event.payload, "chunks": tuple(chunks)},
    )
    with pytest.raises(ValueError, match="chunk_id"):
        decode_source_revision_event(arbitrary_chunk_id, load_blob)


def test_reducer_preserves_prior_revisions_and_persisted_configuration() -> None:
    first, first_loader = make_event()
    second, second_loader = make_event(sequence=2, original="Changed 🫀 valve".encode())
    registry = EventRegistry()
    loaders: tuple[BlobLoader, ...] = (first_loader, second_loader)

    def load(ref: BlobRef) -> bytes:
        for loader in loaders:
            try:
                return loader(ref)
            except KeyError:
                continue
        raise KeyError(str(ref.id))

    register_source_revision_events(registry, load)
    projection = Projection(CourseId("course-1"), state={"unrelated": "preserved"})
    projection = apply_event(projection, first, registry)
    projection = apply_event(projection, second, registry)

    sources = projection.state["sources"]
    assert isinstance(sources, Mapping)
    source_state = sources["source-1"]
    assert isinstance(source_state, Mapping)
    revision_ids = source_state["revision_ids"]
    assert isinstance(revision_ids, tuple) and len(revision_ids) == 2
    first_revision_id = revision_ids[0]
    assert isinstance(first_revision_id, str)
    revisions = source_state["revisions"]
    assert isinstance(revisions, Mapping)
    first_manifest = revisions[first_revision_id]
    assert isinstance(first_manifest, Mapping)
    assert first_manifest["normalized_character_length"] == len("Café 🫀 valve")
    assert first_manifest["chunking"] == {
        "version": CHUNKER_POLICY_VERSION,
        "max_characters": CHUNK_MAX_CHARACTERS,
    }
    assert projection.state["unrelated"] == "preserved"


def test_selection_decoder_and_legacy_projection_append_are_strict_and_compatible() -> None:
    first, load_blob = make_event()
    registry = EventRegistry()
    register_source_revision_events(registry, load_blob)
    projection = apply_event(Projection(first.course_id), first, registry)
    sources = projection.state["sources"]
    assert isinstance(sources, Mapping)
    source_state = sources["source-1"]
    assert isinstance(source_state, Mapping)
    legacy_source_state = dict(source_state)
    legacy_source_state.pop("current_revision_id")
    legacy_projection = Projection(
        first.course_id,
        sequence=projection.sequence,
        state={**projection.state, "sources": {"source-1": legacy_source_state}},
    )
    source = first.payload["source"]
    assert isinstance(source, Mapping)
    revision_id = RevisionId(str(source["revision_id"]))
    selection = DomainEvent(
        source_revision_selected_event_id_for(
            first.course_id, SourceId("source-1"), revision_id, 2
        ),
        first.course_id,
        2,
        SOURCE_REVISION_SELECTED,
        SOURCE_REVISION_SELECTED_SCHEMA_VERSION,
        first.actor,
        first.occurred_at + timedelta(seconds=1),
        first.correlation_id,
        source_revision_selected_payload(SourceId("source-1"), revision_id),
    )

    decoded = decode_source_revision_selected_event(selection)
    selected_projection = apply_event(legacy_projection, selection, registry)
    selected_sources = selected_projection.state["sources"]
    assert isinstance(selected_sources, Mapping)
    selected_source = selected_sources["source-1"]
    assert isinstance(selected_source, Mapping)
    assert decoded.revision_id == revision_id
    assert selected_source["current_revision_id"] == str(revision_id)
    assert selected_source["revision_ids"] == legacy_source_state["revision_ids"]

    forged = DomainEvent(
        EventId("event-arbitrary"),
        selection.course_id,
        selection.course_sequence,
        selection.event_type,
        selection.schema_version,
        selection.actor,
        selection.occurred_at,
        selection.correlation_id,
        selection.payload,
    )
    with pytest.raises(ValueError, match="event_id"):
        decode_source_revision_selected_event(forged)
