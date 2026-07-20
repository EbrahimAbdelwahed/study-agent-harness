from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from study_agent.adapters.filesystem import FilesystemBlobStore
from study_agent.adapters.sqlite import SQLiteEventStore
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
)
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
    normalize_utf8,
    register_source_revision_events,
    revision_id_for,
    source_event_id_for,
    source_revision_payload,
    source_revision_selected_event_id_for,
    source_revision_selected_payload,
)
from study_agent.state import EventRegistry, PayloadValidationError


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
    revision_id = revision_id_for(
        original_sha256=original_blob.checksum_sha256,
        source_id=source_id,
        kind=SourceKind.TEXT,
        title="Physiology notes",
        trust_level=80,
        source_role="primary",
        normalization_version=NORMALIZATION_POLICY_VERSION,
        chunker_version=CHUNKER_POLICY_VERSION,
        max_characters=max_characters,
    )
    occurred_at = datetime(2026, 7, 11, 9, sequence, tzinfo=UTC)
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
        source_event_id_for(course_id, revision_id),
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


def test_positive_max_characters_changes_revision_and_trailing_length_is_exact(
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

    assert first.payload["source"] != second.payload["source"]
    store.append(course_id, 0, (first, second))
    assert store.verify_projection(course_id)
    sources = store.projection(course_id).state["sources"]
    assert isinstance(sources, Mapping)
    source_state = sources["source-1"]
    assert isinstance(source_state, Mapping)
    revisions = source_state["revisions"]
    assert isinstance(revisions, Mapping)
    assert len(revisions) == 2
    for manifest in revisions.values():
        assert isinstance(manifest, Mapping)
        assert manifest["normalized_character_length"] == len("alpha beta gamma   \n")
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
