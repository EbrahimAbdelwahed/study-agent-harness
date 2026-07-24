from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from study_agent.adapters.sqlite.capability_gap_store import SQLiteCapabilityGapStore
from study_agent.feedback import (
    CapabilityGapAggregate,
    CapabilityGapObservation,
    CapabilityGapService,
    CapabilityGapWriteContext,
    GapCategory,
    GapExportState,
    GapOutboxBundle,
    GapOutboxCorruptionError,
    GapOutboxExportService,
    GapOutboxPublicationError,
    GapOutboxRecord,
    ImpactKind,
    RequestedOperationKind,
    SafeTargetKind,
)
from study_agent.state import canonical_json_bytes

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


class _Publisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.payloads: list[bytes] = []

    def publish(self, payload: bytes) -> None:
        if self.fail:
            raise OSError("publisher unavailable")
        self.payloads.append(payload)


class _DurableThenFails(_Publisher):
    def publish(self, payload: bytes) -> None:
        self.payloads.append(payload)
        raise OSError("ack lost after durable write")


def _record(tmp_path: Path) -> tuple[SQLiteCapabilityGapStore, GapOutboxRecord]:
    store = SQLiteCapabilityGapStore(tmp_path / "gaps.sqlite3")
    service = CapabilityGapService(store)
    observation = CapabilityGapObservation(
        GapCategory.INPUT_FORMAT,
        RequestedOperationKind.EXTRACT_TEXT,
        SafeTargetKind.PDF,
        ImpactKind.BLOCKED,
    )
    service.record(
        observation,
        CapabilityGapWriteContext("harness@1", "corr@1", "a" * 64, NOW),
    )
    report = service.record(
        observation,
        CapabilityGapWriteContext("harness@1", "corr@1", "a" * 64, NOW),
    )
    aggregate = CapabilityGapAggregate.from_bytes(store.load(report.gap_key.value))
    return store, GapOutboxRecord.from_aggregate(aggregate)


def test_record_and_bundle_are_canonical_and_roundtrip(tmp_path: Path) -> None:
    _store, record = _record(tmp_path)
    bundle = GapOutboxBundle("harness@1", (record,))
    assert GapOutboxRecord.from_bytes(record.to_bytes()) == record
    assert GapOutboxBundle.from_bytes(bundle.to_bytes()) == bundle
    assert bundle.to_bytes() == (
        b'{"harness_version":"harness@1","records":[{"dimensions":'
        b'{"category":"input_format","contract_major":1,"limitation_code":'
        b'"missing_capability","relevant_contract_identity":"unverified-request@1",'
        b'"requested_operation_kind":"extract_text","safe_target_kind":"pdf",'
        b'"schema_version":1},"export_state":"local","first_seen":'
        b'"2026-07-24T12:00:00.000000Z","gap_key":"08d93ea459d23bc6ba78d484747392bc3045a937f7147d943fad2e1b4a767485",'
        b'"impact_kind":"blocked","last_seen":"2026-07-24T12:00:00.000000Z",'
        b'"occurrence_count":1,"resolution":"unresolved",'
        b'"resolution_authority_fingerprint":null,"resolved_at":null,"schema_version":1,'
        b'"verification_kind":"unverified_request"}],"schema_version":1}'
    )
    assert bundle.bundle_fingerprint == GapOutboxBundle.from_bytes(
        bundle.to_bytes()
    ).bundle_fingerprint


def test_unknown_fields_tamper_and_key_mismatch_fail_closed(tmp_path: Path) -> None:
    _store, record = _record(tmp_path)
    raw = record.to_json()
    raw["learner_text"] = "secret"
    with pytest.raises(GapOutboxCorruptionError):
        GapOutboxRecord.from_bytes(canonical_json_bytes(raw))
    tampered = record.to_json()
    tampered["gap_key"] = "b" * 64
    with pytest.raises(RuntimeError):
        GapOutboxRecord.from_bytes(canonical_json_bytes(tampered))
    with pytest.raises(GapOutboxCorruptionError):
        GapOutboxRecord.from_bytes(record.to_bytes().replace(b",", b", ", 1))


def test_export_is_explicit_byte_stable_and_retains_source(tmp_path: Path) -> None:
    store, record = _record(tmp_path)
    publisher = _Publisher()
    export = GapOutboxExportService(store, publisher, harness_version="harness@1")
    first = export.export_pending()
    assert first.payload == publisher.payloads[0]
    assert first.bundle.records[0].gap_key == record.gap_key
    assert store.load(record.gap_key.value)
    assert store.list_aggregates(states={GapExportState.EXPORTED})
    assert export.snapshot().records == ()
    exported_record = CapabilityGapAggregate.from_bytes(store.load(record.gap_key.value))
    assert export.snapshot(include_exported=True).to_bytes() == GapOutboxBundle(
        "harness@1", (GapOutboxRecord.from_aggregate(exported_record),)
    ).to_bytes()


def test_publish_failure_never_claims_exported(tmp_path: Path) -> None:
    store, _record_value = _record(tmp_path)
    export = GapOutboxExportService(
        store, _Publisher(fail=True), harness_version="harness@1"
    )
    with pytest.raises(GapOutboxPublicationError):
        export.export_pending()
    assert store.list_aggregates(states={GapExportState.FAILED})
    assert not store.list_aggregates(states={GapExportState.EXPORTED})


def test_retry_after_lost_ack_reuses_exact_snapshot(tmp_path: Path) -> None:
    store, _record_value = _record(tmp_path)
    first_publisher = _DurableThenFails()
    first_export = GapOutboxExportService(
        store, first_publisher, harness_version="harness@1"
    )
    with pytest.raises(GapOutboxPublicationError):
        first_export.export_pending()
    second_publisher = _Publisher()
    second_export = GapOutboxExportService(
        SQLiteCapabilityGapStore(tmp_path / "gaps.sqlite3"),
        second_publisher,
        harness_version="harness@1",
    )
    second_export.export_pending()
    assert second_publisher.payloads == first_publisher.payloads
