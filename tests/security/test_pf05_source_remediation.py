from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest

from study_agent.adapters.sqlite import SQLiteEventStore
from study_agent.domain import SourceId, substrate_id_for
from study_agent.domain.bounded_json import BoundedJsonError, validate_json
from study_agent.domain.errors import ValidationFailure
from study_agent.domain.events import EventEnvelope
from study_agent.domain.source import SourceRevision
from study_agent.domain.source_identity import source_revision_id_for, source_revision_manifest
from study_agent.ingestion import ChunkingConfig, decode_source_revision_event
from study_agent.ingestion.events import upcast_source_revision_ingested_v1
from study_agent.ingestion.projection import register_source_revision_events
from study_agent.ingestion.service import (
    _BoundedBlobLoader,
    _current_revision,
    _find_matching_revision,
)
from study_agent.state import EventRegistry, PayloadValidationError
from tests.unit.ingestion.test_source_revision_state import make_event


def test_mapping_proxy_around_custom_mapping_never_invokes_the_mapping() -> None:
    class EvilMapping(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            raise AssertionError(f"Bearer secret via {key}")

        def __iter__(self) -> Iterator[str]:
            raise AssertionError("Bearer secret via iteration")

        def __len__(self) -> int:
            raise AssertionError("Bearer secret via length")

    value = MappingProxyType(EvilMapping())
    with pytest.raises(BoundedJsonError, match="unsupported JSON value"):
        validate_json(value)
    with pytest.raises(ValueError, match="outside the bounded JSON profile"):
        SourceRevision.create(
            source_id=SourceId("source-security"),
            content=b"safe text",
            media_type="text/plain",
            created_at=datetime(2026, 8, 10, tzinfo=UTC),
            normalization_version="utf8-newlines-nfc-v1",
            substrate_id=substrate_id_for(b"safe text"),
            metadata=value,
        )


def test_revision_identity_rejects_open_or_mismatched_manifests() -> None:
    revision = SourceRevision.create(
        source_id=SourceId("source-security"),
        content=b"identity text",
        media_type="text/plain",
        created_at=datetime(2026, 8, 10, tzinfo=UTC),
        normalization_version="utf8-newlines-nfc-v1",
        substrate_id=substrate_id_for(b"identity text"),
        metadata={"kind": "text"},
    )
    manifest = source_revision_manifest(
        source_id=revision.source_id,
        blob=revision.blob,
        media_type=revision.media_type,
        normalization_version=revision.normalization_version,
        substrate_id=revision.substrate_id,
        metadata=revision.metadata,
    )
    assert source_revision_id_for(manifest)
    with pytest.raises(ValueError):
        source_revision_id_for({})
    forged = dict(manifest)
    blob = dict(forged["blob"])  # type: ignore[arg-type]
    blob["id"] = "host-provided-id"
    forged["blob"] = blob
    with pytest.raises(ValueError, match="blob id"):
        source_revision_id_for(forged)


@pytest.mark.parametrize("marker", [True, False, "legacy"])
def test_schema_two_legacy_marker_smuggling_fails_registry_and_sqlite(
    tmp_path, marker: object
) -> None:
    valid, load_blob = make_event()
    payload = {**valid.payload, "__legacy_v1_replay": marker}
    forged = EventEnvelope(
        valid.event_id,
        valid.event_type,
        valid.schema_version,
        valid.course_id,
        valid.course_sequence,
        valid.occurred_at,
        valid.correlation_id,
        valid.actor,
        payload,
    )
    registry = EventRegistry()
    register_source_revision_events(registry, load_blob)
    with pytest.raises(PayloadValidationError) as error:
        registry.decode(forged)
    assert "__legacy_v1_replay" not in str(error.value)

    store = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    with pytest.raises(PayloadValidationError):
        store.append(valid.course_id, 0, (forged,), "marker-smuggle")
    assert store.read(valid.course_id) == ()


def test_tampered_v1_timestamp_is_rejected_at_direct_registry_and_sqlite_boundaries(
    tmp_path,
) -> None:
    historical, load_blob = make_event(legacy_identity=True)
    source = historical.payload["source"]
    assert isinstance(source, Mapping)
    tampered_source = {
        **source,
        "created_at": (historical.occurred_at + timedelta(days=1)).isoformat(),
    }
    tampered = historical.__class__(
        historical.event_id,
        historical.course_id,
        historical.course_sequence,
        historical.event_type,
        historical.schema_version,
        historical.actor,
        historical.occurred_at,
        historical.correlation_id,
        {**historical.payload, "source": tampered_source},
    )
    with pytest.raises(ValueError, match="created_at"):
        upcast_source_revision_ingested_v1(tampered, load_blob)

    registry = EventRegistry()
    register_source_revision_events(registry, load_blob)
    with pytest.raises(ValidationFailure):
        registry.decode(tampered)
    store = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    with pytest.raises(ValidationFailure):
        store.append(historical.course_id, 0, (tampered,))
    assert store.read(historical.course_id) == ()


def test_blob_loader_failures_have_no_adapter_text_at_registry_or_storage_boundary(
    tmp_path,
) -> None:
    valid, _ = make_event()

    def loader(_ref) -> bytes:
        raise RuntimeError("Bearer token=/private/secret/path trace=secret")

    registry = EventRegistry()
    register_source_revision_events(registry, loader)
    with pytest.raises(PayloadValidationError) as error:
        registry.decode(valid)
    assert "Bearer" not in str(error.value)
    assert "/private/secret/path" not in str(error.value)

    store = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    with pytest.raises(PayloadValidationError) as error:
        store.append(valid.course_id, 0, (valid,))
    assert "Bearer" not in str(error.value)
    assert store.read(valid.course_id) == ()


def test_history_index_limits_blob_verification_to_current_or_matching_candidate() -> None:
    first, first_loader = make_event(original=b"first source", sequence=1)
    second, second_loader = make_event(original=b"second source", sequence=2)
    calls: list[str] = []

    def load(ref) -> bytes:
        calls.append(str(ref.id))
        try:
            return first_loader(ref)
        except KeyError:
            return second_loader(ref)

    bounded = _BoundedBlobLoader(load, max_reads=2)
    current = _current_revision((first, second), SourceId("source-1"), bounded)
    assert current is not None
    assert str(current.source.revision_id) == second.payload["source"]["revision_id"]  # type: ignore[index]
    assert len(calls) == 2

    calls.clear()
    requested = decode_source_revision_event(first, first_loader).source
    matched = _find_matching_revision(
        (first, second),
        SourceId("source-1"),
        requested,
        ChunkingConfig(),
        _BoundedBlobLoader(load, max_reads=2),
    )
    assert matched is not None
    assert matched.source.revision_id == requested.revision_id
    assert len(calls) == 2


def test_historical_identity_helpers_are_not_public_ingestion_exports() -> None:
    import study_agent.ingestion as ingestion

    assert "revision_id_for" not in ingestion.__all__
    assert "source_event_id_for" not in ingestion.__all__
    assert not hasattr(ingestion, "revision_id_for")
    assert not hasattr(ingestion, "source_event_id_for")
