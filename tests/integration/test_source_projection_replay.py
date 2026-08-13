from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from study_agent.adapters.filesystem import FilesystemBlobStore
from study_agent.adapters.sqlite import SQLiteEventStore
from study_agent.application.export import ExportService, ExportVersion
from study_agent.courses import register_course_events
from study_agent.domain import (
    Actor,
    BlobRef,
    CorrelationId,
    CourseId,
    DomainEvent,
    PrincipalKind,
    RevisionId,
    SourceDocument,
    SourceId,
    SourceKind,
    StructureOrigin,
    substrate_id_for,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.errors import ValidationFailure
from study_agent.domain.source import SourceRevision
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
    normalize_utf8,
    register_source_revision_events,
    source_revision_payload,
    source_revision_selected_event_id_for,
    source_revision_selected_payload,
)
from study_agent.ingestion.identity import source_revision_ingested_event_id_for
from study_agent.ingestion.legacy import _historical_source_event_id_for, _legacy_revision_id_for
from study_agent.ingestion.projection import source_revision_payload_v1
from study_agent.state import (
    EventRegistry,
    PayloadValidationError,
    canonical_json_bytes,
    event_to_bytes,
)
from tests.course_fixtures import create_canonical_course


def make_event(
    blobs: FilesystemBlobStore,
    original: bytes,
    sequence: int,
    *,
    max_characters: int = CHUNK_MAX_CHARACTERS,
) -> DomainEvent:
    normalized = normalize_utf8(original)
    original_blob = blobs.put(original)
    normalized_blob = blobs.put(normalized.content)
    source_id = SourceId("source-1")
    occurred_at = datetime(2026, 7, 11, 9, sequence, tzinfo=UTC)
    revision_id = SourceRevision.create(
        source_id=source_id,
        content=original,
        media_type="text/plain",
        created_at=occurred_at,
        normalization_version=NORMALIZATION_POLICY_VERSION,
        substrate_id=substrate_id_for(normalized.content),
        metadata={
            "kind": SourceKind.TEXT.value,
            "source_role": "primary",
            "title": "Physiology notes",
            "trust_level": 80,
        },
    ).revision_id
    document = SourceDocument(
        source_id,
        revision_id,
        SourceKind.TEXT,
        "Physiology notes",
        "text/plain",
        original_blob.checksum_sha256,
        original_blob.byte_length,
        occurred_at,
        80,
        "primary",
        original_blob,
        normalized_blob,
        NORMALIZATION_POLICY_VERSION,
        len(normalized.text),
        StructureOrigin.MECHANICALLY_EXTRACTED,
        "utf8-text-v1",
    )
    chunks = chunk_text(
        normalized.text,
        source_id=source_id,
        revision_id=revision_id,
        kind=SourceKind.TEXT,
        config=ChunkingConfig(
            max_characters=max_characters,
            version=CHUNKER_POLICY_VERSION,
        ),
    )
    course_id = CourseId("course-1")
    return DomainEvent(
        source_revision_ingested_event_id_for(course_id, revision_id, occurred_at),
        course_id,
        sequence,
        SOURCE_REVISION_INGESTED,
        SOURCE_REVISION_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "ingestion"),
        occurred_at,
        CorrelationId("correlation-1"),
        source_revision_payload(
            document,
            chunks,
            max_characters=max_characters,
        ),
    )


def select_event(revision_event: DomainEvent, sequence: int) -> DomainEvent:
    source = revision_event.payload["source"]
    assert isinstance(source, Mapping)
    source_id = SourceId(str(source["source_id"]))
    raw_revision_id = source["revision_id"]
    assert isinstance(raw_revision_id, str)
    revision_id = RevisionId(raw_revision_id)
    return DomainEvent(
        source_revision_selected_event_id_for(
            revision_event.course_id, source_id, revision_id, sequence
        ),
        revision_event.course_id,
        sequence,
        SOURCE_REVISION_SELECTED,
        SOURCE_REVISION_SELECTED_SCHEMA_VERSION,
        revision_event.actor,
        datetime(2026, 7, 11, 10, sequence, tzinfo=UTC),
        revision_event.correlation_id,
        source_revision_selected_payload(source_id, revision_id),
    )


def historical_event_from_current(event: DomainEvent, blobs: FilesystemBlobStore) -> DomainEvent:
    decoded = decode_source_revision_event(event, blobs.get)
    revision_id = _legacy_revision_id_for(
        original_sha256=decoded.source.checksum_sha256,
        source_id=decoded.source.source_id,
        kind=decoded.source.kind,
        normalization_version=decoded.source.normalization_version,
        chunker_version=decoded.chunking.version,
        max_characters=decoded.chunking.max_characters,
    )
    source = replace(decoded.source, revision_id=revision_id)
    normalized = blobs.get(source.normalized_blob).decode("utf-8")
    chunks = chunk_text(
        normalized,
        source_id=source.source_id,
        revision_id=source.revision_id,
        kind=source.kind,
        config=ChunkingConfig(
            max_characters=decoded.chunking.max_characters,
            version=decoded.chunking.version,
        ),
    )
    return DomainEvent(
        _historical_source_event_id_for(event.course_id, revision_id),
        event.course_id,
        event.course_sequence,
        SOURCE_REVISION_INGESTED,
        1,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        source_revision_payload_v1(
            source,
            chunks,
            chunker_version=decoded.chunking.version,
            max_characters=decoded.chunking.max_characters,
        ),
    )


def test_sqlite_replay_reloads_content_and_preserves_byte_identical_revisions(
    tmp_path: Path,
) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    store = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    course_id = CourseId("course-1")
    events = (
        make_event(blobs, "Cafe\u0301 🫀".encode(), 1),
        make_event(blobs, "Changed 🫀".encode(), 2),
    )
    store.append(course_id, 0, events)
    original = store.projection_bytes(course_id)

    assert store.verify_projection(course_id)
    assert store.rebuild_projection(course_id) == original
    assert store.projection_bytes(course_id) == original
    sources = store.projection(course_id).state["sources"]
    assert isinstance(sources, Mapping)
    source_state = sources["source-1"]
    assert isinstance(source_state, Mapping)
    revision_ids = source_state["revision_ids"]
    assert isinstance(revision_ids, tuple) and len(revision_ids) == 2
    blobs.close()


def test_persisted_mixed_v1_v2_history_rebuilds_and_exports_without_rewriting_bytes(
    tmp_path: Path,
) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    register_course_events(registry)
    register_source_revision_events(registry, blobs.get)
    database = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(database, registry)
    course_id = CourseId("course-1")
    create_canonical_course(store, course_id)

    current = make_event(blobs, b"Retained v1 text", 2)
    historical = historical_event_from_current(current, blobs)
    successor = make_event(blobs, b"Current v2 text", 3)
    retained = (historical, successor)
    with sqlite3.connect(database) as connection:
        for event in retained:
            connection.execute(
                """
                INSERT INTO events (
                    course_id, course_sequence, event_id, event_type,
                    schema_version, envelope
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.course_id),
                    event.course_sequence,
                    str(event.event_id),
                    event.event_type,
                    event.schema_version,
                    event_to_bytes(event),
                ),
            )

    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT envelope FROM events WHERE course_sequence > 1 ORDER BY course_sequence"
        ).fetchall()
    assert [bytes(row[0]) for row in rows] == [event_to_bytes(event) for event in retained]

    rebuilt = store.rebuild_projection(course_id)
    assert store.verify_projection(course_id)
    assert rebuilt == store.projection_bytes(course_id)
    exported = ExportService(store).assemble(course_id, version=ExportVersion.V2)
    historical_source = historical.payload["source"]
    successor_source = successor.payload["source"]
    assert isinstance(historical_source, Mapping)
    assert isinstance(successor_source, Mapping)
    historical_revision_id = str(historical_source["revision_id"])
    successor_revision_id = str(successor_source["revision_id"])
    assert {row["revision_id"] for row in exported.sources} == {
        historical_revision_id,
        successor_revision_id,
    }
    historical_export = next(
        row for row in exported.sources if row["revision_id"] == historical_revision_id
    )
    assert historical_export["title"] == "Legacy source"
    tail = make_event(blobs, b"Post-rebuild v2 text", 4)
    assert store.append(course_id, 3, (tail,)) == 4
    assert store.verify_projection(course_id)
    blobs.close()


def test_coordinated_historical_timestamp_shift_converges_in_replay_and_export(
    tmp_path: Path,
) -> None:
    def build_store(
        root: Path,
    ) -> tuple[SQLiteEventStore, FilesystemBlobStore, Path]:
        blobs = FilesystemBlobStore(root / "blobs")
        registry = EventRegistry()
        register_course_events(registry)
        register_source_revision_events(registry, blobs.get)
        database = root / "events.sqlite3"
        store = SQLiteEventStore(database, registry)
        create_canonical_course(store, CourseId("course-1"))
        return store, blobs, database

    first_store, first_blobs, first_database = build_store(tmp_path / "first")
    second_store, second_blobs, second_database = build_store(tmp_path / "second")
    first = make_event(first_blobs, b"Historical timestamp", 2)
    second_blobs.put(b"Historical timestamp")
    historical = historical_event_from_current(first, first_blobs)
    source = historical.payload["source"]
    assert isinstance(source, Mapping)
    shifted = historical.occurred_at + timedelta(days=30)
    shifted_historical = DomainEvent(
        historical.event_id,
        historical.course_id,
        historical.course_sequence,
        historical.event_type,
        historical.schema_version,
        historical.actor,
        shifted,
        historical.correlation_id,
        {**historical.payload, "source": {**source, "created_at": shifted.isoformat()}},
    )

    def retain(database: Path, event: DomainEvent) -> None:
        with sqlite3.connect(database) as connection:
            connection.execute(
                """
                INSERT INTO events (
                    course_id, course_sequence, event_id, event_type,
                    schema_version, envelope
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.course_id),
                    event.course_sequence,
                    str(event.event_id),
                    event.event_type,
                    event.schema_version,
                    event_to_bytes(event),
                ),
            )

    retain(first_database, historical)
    retain(second_database, shifted_historical)
    assert first_store.rebuild_projection(CourseId("course-1")) == (
        second_store.rebuild_projection(CourseId("course-1"))
    )
    assert first_store.projection_bytes(CourseId("course-1")) == second_store.projection_bytes(
        CourseId("course-1")
    )
    first_export = ExportService(first_store).assemble(
        CourseId("course-1"), version=ExportVersion.V2
    )
    second_export = ExportService(second_store).assemble(
        CourseId("course-1"), version=ExportVersion.V2
    )
    assert first_export.sources == second_export.sources

    stale_state = cast(
        dict[str, JsonValue], dict(first_store.projection(CourseId("course-1")).state)
    )
    stale_sources = dict(cast(Mapping[str, JsonValue], stale_state["sources"]))
    stale_source = dict(cast(Mapping[str, JsonValue], stale_sources["source-1"]))
    stale_revisions = dict(cast(Mapping[str, JsonValue], stale_source["revisions"]))
    historical_key = str(source["revision_id"])
    stale_revision = dict(cast(Mapping[str, JsonValue], stale_revisions[historical_key]))
    stale_manifest = dict(cast(Mapping[str, JsonValue], stale_revision["source"]))
    stale_manifest["created_at"] = historical.occurred_at.isoformat()
    stale_revision["source"] = stale_manifest
    stale_revisions[historical_key] = stale_revision
    stale_source["revisions"] = stale_revisions
    stale_sources["source-1"] = stale_source
    stale_state["sources"] = stale_sources
    with sqlite3.connect(first_database) as connection:
        connection.execute(
            "UPDATE projections SET state = ? WHERE course_id = ?",
            (canonical_json_bytes(cast(JsonObject, stale_state)), "course-1"),
        )
    migrated = first_store.projection(CourseId("course-1"))
    migrated_sources = cast(Mapping[str, object], migrated.state["sources"])
    migrated_source = cast(Mapping[str, object], migrated_sources["source-1"])
    migrated_revisions = cast(Mapping[str, object], migrated_source["revisions"])
    migrated_revision = cast(Mapping[str, object], migrated_revisions[historical_key])
    migrated_manifest = cast(Mapping[str, object], migrated_revision["source"])
    assert migrated_manifest["created_at"] == "1970-01-01T00:00:00.000000Z"
    assert first_store.verify_projection(CourseId("course-1"))

    first_blobs.close()
    second_blobs.close()


def test_selection_replay_tracks_current_without_reordering_immutable_history(
    tmp_path: Path,
) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    store = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    course_id = CourseId("course-1")
    first = make_event(blobs, b"Revision A", 1)
    second = make_event(blobs, b"Revision B", 2)
    selected = select_event(first, 3)

    store.append(course_id, 0, (first, second, selected))
    before = store.projection_bytes(course_id)
    sources = store.projection(course_id).state["sources"]
    assert isinstance(sources, Mapping)
    source_state = sources["source-1"]
    assert isinstance(source_state, Mapping)
    source = first.payload["source"]
    assert isinstance(source, Mapping)
    assert source_state["current_revision_id"] == source["revision_id"]
    revision_ids = source_state["revision_ids"]
    assert isinstance(revision_ids, tuple)
    assert len(revision_ids) == 2
    assert store.rebuild_projection(course_id) == before
    assert store.verify_projection(course_id)
    blobs.close()


def test_positive_max_characters_is_derived_policy_not_revision_identity(
    tmp_path: Path,
) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    store = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    course_id = CourseId("course-1")
    original = b"alpha beta gamma   \n"
    first = make_event(blobs, original, 1, max_characters=5)
    second = make_event(blobs, original, 2, max_characters=9)

    assert first.payload["source"] == second.payload["source"]
    assert first.payload["chunking"] != second.payload["chunking"]
    with pytest.raises((PayloadValidationError, ValueError)):
        store.append(course_id, 0, (first, second))
    assert store.read(course_id) == ()
    blobs.close()


def test_canonical_rechunking_rejects_omitted_shortened_reordered_and_forged_chunks(
    tmp_path: Path,
) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    store = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    valid = make_event(blobs, b"alpha beta gamma delta", 1, max_characters=6)
    chunks = valid.payload["chunks"]
    assert isinstance(chunks, tuple) and len(chunks) > 2
    first = chunks[0]
    assert isinstance(first, Mapping)
    shortened = dict(first)
    original_end = shortened["end_offset"]
    assert isinstance(original_end, int)
    shortened["end_offset"] = original_end - 1
    forged_section = dict(first)
    forged_section["section_path"] = ("Forged",)
    variants = (
        chunks[:-1],
        (shortened, *chunks[1:]),
        tuple(reversed(chunks)),
        (forged_section, *chunks[1:]),
    )

    for variant in variants:
        tampered = DomainEvent(
            valid.event_id,
            valid.course_id,
            valid.course_sequence,
            valid.event_type,
            valid.schema_version,
            valid.actor,
            valid.occurred_at,
            valid.correlation_id,
            {**valid.payload, "chunks": variant},
        )
        with pytest.raises(PayloadValidationError):
            store.append(valid.course_id, 0, (tampered,))
        assert store.read(valid.course_id) == ()
    blobs.close()


def test_tampering_fails_before_insert_and_corrupt_content_fails_replay(
    tmp_path: Path,
) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    content_overrides: dict[str, bytes] = {}

    def load(ref: BlobRef) -> bytes:
        key = str(ref.id)
        return content_overrides[key] if key in content_overrides else blobs.get(ref)

    register_source_revision_events(registry, load)
    store = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    valid = make_event(blobs, "Cafe\u0301 🫀".encode(), 1)
    malformed = DomainEvent(
        valid.event_id,
        valid.course_id,
        valid.course_sequence,
        valid.event_type,
        valid.schema_version,
        valid.actor,
        valid.occurred_at,
        valid.correlation_id,
        {**valid.payload, "normalized_character_length": 999},
    )
    with pytest.raises(PayloadValidationError, match="character_length"):
        store.append(valid.course_id, 0, (malformed,))
    assert store.read(valid.course_id) == ()

    source = valid.payload["source"]
    assert isinstance(source, Mapping)
    forged_source = {**source, "title": "Forged title"}
    forged = DomainEvent(
        valid.event_id,
        valid.course_id,
        valid.course_sequence,
        valid.event_type,
        valid.schema_version,
        valid.actor,
        valid.occurred_at,
        valid.correlation_id,
        {**valid.payload, "source": forged_source},
    )
    with pytest.raises(PayloadValidationError, match="revision_id"):
        store.append(valid.course_id, 0, (forged,))
    assert store.read(valid.course_id) == ()

    store.append(valid.course_id, 0, (valid,))
    before = store.projection_bytes(valid.course_id)
    source = valid.payload["source"]
    assert isinstance(source, Mapping)
    normalized_blob = source["normalized_blob"]
    assert isinstance(normalized_blob, Mapping)
    normalized_id = normalized_blob["id"]
    normalized_length = normalized_blob["byte_length"]
    assert isinstance(normalized_id, str)
    assert isinstance(normalized_length, int)
    content_overrides[normalized_id] = b"x" * normalized_length
    with pytest.raises(PayloadValidationError, match="checksum does not match loaded"):
        store.rebuild_projection(valid.course_id)
    assert store.projection_bytes(valid.course_id) == before
    blobs.close()


@pytest.mark.parametrize(
    "malformed",
    ["mismatched-key", "non-mapping", "unknown-ownership", "closed-shape"],
)
def test_projection_rejects_malformed_persisted_chunk_without_rewriting_bytes(
    tmp_path: Path, malformed: str
) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    database = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(database, registry)
    course_id = CourseId("course-1")
    event = make_event(blobs, b"persisted chunk", 1)
    store.append(course_id, 0, (event,))
    state = dict(store.projection(course_id).state)
    chunks = state["chunks"]
    assert isinstance(chunks, Mapping) and len(chunks) == 1
    chunk_id, chunk_value = next(iter(chunks.items()))
    assert isinstance(chunk_id, str) and isinstance(chunk_value, Mapping)
    rewritten_chunks = dict(chunks)
    if malformed == "mismatched-key":
        rewritten_chunks["chunk-forged"] = rewritten_chunks.pop(chunk_id)
    elif malformed == "non-mapping":
        rewritten_chunks[chunk_id] = "not-a-chunk"
    elif malformed == "unknown-ownership":
        rewritten_chunks[chunk_id] = {**chunk_value, "source_id": "source-forged"}
    else:
        rewritten_chunks[chunk_id] = {**chunk_value, "unexpected": True}
    state["chunks"] = rewritten_chunks
    tampered_bytes = canonical_json_bytes(state)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE projections SET state = ? WHERE course_id = ?",
            (tampered_bytes, str(course_id)),
        )

    with pytest.raises(ValueError, match="chunk"):
        store.projection(course_id)
    with sqlite3.connect(database) as connection:
        persisted = connection.execute(
            "SELECT state FROM projections WHERE course_id = ?", (str(course_id),)
        ).fetchone()
    assert persisted is not None and bytes(persisted[0]) == tampered_bytes
    blobs.close()


def test_projection_rejects_duplicate_serialized_chunks_key_without_rewriting_bytes(
    tmp_path: Path,
) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    database = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(database, registry)
    course_id = CourseId("course-1")
    event = make_event(blobs, b"duplicate chunk key", 1)
    store.append(course_id, 0, (event,))
    state = dict(store.projection(course_id).state)
    chunks = state["chunks"]
    assert isinstance(chunks, Mapping)

    def encoded_value(value: JsonValue) -> bytes:
        return canonical_json_bytes({"_": value})[5:-1]

    entries: list[bytes] = []
    for key in sorted(state):
        value = state[key]
        if key == "chunks":
            entries.append(b'"chunks":"hidden malformed value"')
            entries.append(b'"chunks":' + encoded_value(value))
        else:
            # The single-key object has the form {"key":<value>}.
            entries.append(canonical_json_bytes({key: value})[1:-1])
    tampered_bytes = b"{" + b",".join(entries) + b"}"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE projections SET state = ? WHERE course_id = ?",
            (tampered_bytes, str(course_id)),
        )

    with pytest.raises(ValidationFailure, match="projection state"):
        store.projection(course_id)
    with sqlite3.connect(database) as connection:
        persisted = connection.execute(
            "SELECT state FROM projections WHERE course_id = ?", (str(course_id),)
        ).fetchone()
    assert persisted is not None and bytes(persisted[0]) == tampered_bytes
    blobs.close()
