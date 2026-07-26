from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from pathlib import Path

from study_agent.adapters.filesystem import FilesystemBlobStore
from study_agent.adapters.sqlite import SQLiteEventStore
from study_agent.domain import BlobId, BlobRef, DomainEvent
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.ingestion import register_source_revision_events
from study_agent.ingestion.events import (
    SOURCE_REVISION_INGESTED,
    SOURCE_REVISION_SCHEMA_VERSION,
    SourceRevisionIngested,
    decode_source_revision_event,
)
from study_agent.ingestion.projection import reduce_source_revision
from study_agent.state import EventRegistry
from tests.unit.ingestion.test_source_revision_state import make_event as make_legacy_event
from tests.unit.knowledge.test_substrate_events import make_event


def payload_mapping(event: DomainEvent, key: str) -> dict[str, JsonValue]:
    value = event.payload[key]
    assert isinstance(value, Mapping)
    return dict(value)


def integer(value: JsonValue) -> int:
    assert type(value) is int
    return value


def legacy_reduce(
    state: JsonObject, event: DomainEvent, payload: SourceRevisionIngested
) -> Mapping[str, JsonValue]:
    projected = dict(reduce_source_revision(state, event, payload))
    projected.pop("substrates", None)
    return projected


def test_projection_delete_and_replay_reproduce_exact_canonical_bytes(tmp_path: Path) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    events = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    event, content = make_event()
    for ref, value in content.items():
        assert blobs.put(value).id.value == ref
    events.append(event.course_id, 0, (event,))
    before = events.projection_bytes(event.course_id)

    rebuilt = events.rebuild_projection(event.course_id)

    assert rebuilt == before
    assert events.verify_projection(event.course_id)
    blobs.close()


def test_v01_source_event_maps_to_legacy_substrate_without_new_event(tmp_path: Path) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    event, load_blob = make_legacy_event(legacy_identity=True)
    source = payload_mapping(event, "source")
    original_binding = source["blob"]
    normalized_binding = source["normalized_blob"]
    assert isinstance(original_binding, Mapping)
    assert isinstance(normalized_binding, Mapping)
    original_id = str(original_binding["id"])
    normalized_id = str(normalized_binding["id"])
    original_ref = BlobRef(
        BlobId(original_id),
        str(original_binding["checksum_sha256"]),
        integer(original_binding["byte_length"]),
    )
    normalized_ref = BlobRef(
        BlobId(normalized_id),
        str(normalized_binding["checksum_sha256"]),
        integer(normalized_binding["byte_length"]),
    )
    blobs.put(load_blob(original_ref))
    blobs.put(load_blob(normalized_ref))
    register_source_revision_events(registry, blobs.get)

    events = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    events.append(event.course_id, 0, (event,))

    stream = tuple(events.read(event.course_id))
    state = events.projection(event.course_id).state
    assert stream == (event,)
    legacy_substrate_id = str(normalized_binding["id"]).replace(
        "sha256:", "substrate:sha256:"
    )
    substrates = state["substrates"]
    assert isinstance(substrates, Mapping)
    assert tuple(substrates) == (legacy_substrate_id,)
    blobs.close()


def test_v01_projection_lazy_substrate_migration_is_one_shot_and_read_only_safe(
    tmp_path: Path,
) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    event, load_blob = make_legacy_event(legacy_identity=True)
    source = payload_mapping(event, "source")
    original_binding = source["blob"]
    normalized_binding = source["normalized_blob"]
    assert isinstance(original_binding, Mapping)
    assert isinstance(normalized_binding, Mapping)
    original_ref = BlobRef(
        BlobId(str(original_binding["id"])),
        str(original_binding["checksum_sha256"]),
        integer(original_binding["byte_length"]),
    )
    normalized_ref = BlobRef(
        BlobId(str(normalized_binding["id"])),
        str(normalized_binding["checksum_sha256"]),
        integer(normalized_binding["byte_length"]),
    )
    blobs.put(load_blob(original_ref))
    blobs.put(load_blob(normalized_ref))

    old_registry = EventRegistry()
    old_registry.register_event(
        SOURCE_REVISION_INGESTED,
        SOURCE_REVISION_SCHEMA_VERSION,
        lambda candidate: decode_source_revision_event(candidate, blobs.get),
        legacy_reduce,
    )
    database = tmp_path / "events.sqlite3"
    old_store = SQLiteEventStore(database, old_registry)
    old_store.append(event.course_id, 0, (event,))
    before_events = tuple(old_store.read(event.course_id))
    assert "substrates" not in old_store.projection(event.course_id).state

    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    read_only = SQLiteEventStore(database, registry, read_only=True)
    read_only_state = read_only.projection(event.course_id).state
    assert "substrates" in read_only_state
    with sqlite3.connect(database) as connection:
        raw_before_write = bytes(
            connection.execute(
                "SELECT state FROM projections WHERE course_id = ?",
                (str(event.course_id),),
            ).fetchone()[0]
        )
    assert b"substrates" not in raw_before_write

    writable = SQLiteEventStore(database, registry)
    migrated_bytes = writable.projection_bytes(event.course_id)
    assert migrated_bytes == writable.projection_bytes(event.course_id)
    with sqlite3.connect(database) as connection:
        raw_after_write = bytes(
            connection.execute(
                "SELECT state FROM projections WHERE course_id = ?",
                (str(event.course_id),),
            ).fetchone()[0]
        )
    assert b"substrates" in raw_after_write
    assert tuple(writable.read(event.course_id)) == before_events
    blobs.close()
