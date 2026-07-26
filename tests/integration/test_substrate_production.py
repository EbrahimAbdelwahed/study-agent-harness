from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from study_agent.adapters.filesystem import FilesystemBlobStore
from study_agent.adapters.sqlite import SQLiteEventStore
from study_agent.domain import (
    BlobId,
    BlobRef,
    CorrelationId,
    CourseId,
    DomainEvent,
    ExecutionContext,
    PrincipalKind,
    SourceId,
)
from study_agent.domain.substrate import PageMapEntry
from study_agent.ingestion import register_source_revision_events
from study_agent.ingestion.substrate import (
    ConverterReceipt,
    SubstrateProductionError,
    SubstrateProductionService,
    SubstrateProductionStatus,
    TrustedBlobReceipt,
)
from study_agent.ports.storage import EventSequenceConflictError
from study_agent.state import EventRegistry

ORIGINAL = b"source PDF bytes"
NORMALIZED = "Café\nheart valves".encode()
SOURCE_ID = SourceId("source-cardiac")
COURSE_ID = CourseId("course-kb-01")


class FixedClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 26, 20, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.value


def context() -> ExecutionContext:
    return ExecutionContext(
        PrincipalKind.SERVICE,
        "substrate-test",
        COURSE_ID,
        CorrelationId("correlation-kb-01"),
    )


def converter(
    original_blob: BlobRef,
    content: bytes = NORMALIZED,
    *,
    version: str = "pdf-to-md-1",
    policy: str = "admission-1",
    page_policy: str = "page-map-1",
    page_count: int | None = None,
    page_map: tuple[PageMapEntry, ...] = (),
    blob: BlobRef | None = None,
) -> ConverterReceipt:
    return ConverterReceipt(
        content=content,
        converter_name="pdf-to-markdown",
        converter_version=version,
        normalization_version="utf8-newlines-nfc-v1",
        admission_policy_version=policy,
        page_map_policy_version=page_policy,
        source_id=SOURCE_ID,
        original_blob=original_blob,
        page_count=page_count,
        page_map=page_map,
        blob=blob,
    )


def trusted(original: BlobRef, *, source_id: SourceId = SOURCE_ID) -> TrustedBlobReceipt:
    return TrustedBlobReceipt(original, source_id)


def make_service(tmp_path: Path) -> tuple[
    SubstrateProductionService, FilesystemBlobStore, SQLiteEventStore, FixedClock
]:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    events = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    clock = FixedClock()
    return SubstrateProductionService(blobs=blobs, events=events, clock=clock), blobs, events, clock


def test_production_is_idempotent_and_retains_first_timestamp(tmp_path: Path) -> None:
    service, blobs, events, clock = make_service(tmp_path)
    original = blobs.put(ORIGINAL)

    first = service.produce(
        source_id=SOURCE_ID,
        original_blob=trusted(original),
        converter=converter(original),
        context=context(),
    )
    clock.value = datetime(2026, 7, 26, 21, 0, tzinfo=UTC)
    retry = service.produce(
        source_id=SOURCE_ID,
        original_blob=trusted(original),
        converter=converter(original),
        context=context(),
    )

    assert first.status is SubstrateProductionStatus.EMITTED
    assert retry.status is SubstrateProductionStatus.IDEMPOTENT
    assert retry.receipt == first.receipt
    assert retry.receipt.produced_at == datetime(2026, 7, 26, 20, 0, tzinfo=UTC)
    assert len(events.read(COURSE_ID)) == 1
    assert events.verify_projection(COURSE_ID)
    blobs.close()


def test_production_requires_service_context_and_bound_trusted_receipts(
    tmp_path: Path,
) -> None:
    service, blobs, events, _ = make_service(tmp_path)
    original = blobs.put(ORIGINAL)
    for principal_kind in (PrincipalKind.HUMAN, PrincipalKind.MODEL):
        non_service = ExecutionContext(
            principal_kind,
            "untrusted",
            COURSE_ID,
            CorrelationId("correlation-kb-01"),
        )
        with pytest.raises(SubstrateProductionError, match="service context"):
            service.produce(
                source_id=SOURCE_ID,
                original_blob=trusted(original),
                converter=converter(original),
                context=non_service,
            )
    raw_original: Any = original
    with pytest.raises(TypeError, match="TrustedBlobReceipt"):
        service.produce(
            source_id=SOURCE_ID,
            original_blob=raw_original,
            converter=converter(original),
            context=context(),
        )
    with pytest.raises(SubstrateProductionError, match="another source"):
        service.produce(
            source_id=SOURCE_ID,
            original_blob=trusted(original, source_id=SourceId("other-source")),
            converter=converter(original),
            context=context(),
        )
    assert events.read(COURSE_ID) == ()
    blobs.close()


def test_stale_expected_sequence_rejects_idempotent_and_changed_retries(
    tmp_path: Path,
) -> None:
    service, blobs, events, _ = make_service(tmp_path)
    original = blobs.put(ORIGINAL)
    service.produce(
        source_id=SOURCE_ID,
        original_blob=trusted(original),
        converter=converter(original),
        context=context(),
    )
    for changed in (converter(original), converter(original, policy="admission-2")):
        with pytest.raises(SubstrateProductionError, match="expected sequence"):
            service.produce(
                source_id=SOURCE_ID,
                original_blob=trusted(original),
                converter=changed,
                context=context(),
                expected_sequence=0,
            )
    assert len(events.read(COURSE_ID)) == 1
    blobs.close()


@pytest.mark.parametrize("expected", [True, 1.5, -1])
def test_expected_sequence_rejects_bool_float_and_negative_before_append(
    tmp_path: Path, expected: Any
) -> None:
    service, blobs, events, _ = make_service(tmp_path)
    original = blobs.put(ORIGINAL)
    with pytest.raises(ValueError, match="expected_sequence"):
        service.produce(
            source_id=SOURCE_ID,
            original_blob=trusted(original),
            converter=converter(original),
            context=context(),
            expected_sequence=expected,
        )
    assert events.read(COURSE_ID) == ()
    blobs.close()


class CountingBlobStore:
    def __init__(self, inner: FilesystemBlobStore) -> None:
        self.inner = inner
        self.get_counts: dict[str, int] = {}

    def put(self, content: bytes) -> BlobRef:
        return self.inner.put(content)

    def get(self, ref: BlobRef) -> bytes:
        key = str(ref.id)
        self.get_counts[key] = self.get_counts.get(key, 0) + 1
        return self.inner.get(ref)


def test_converter_blob_is_verified_once_before_reuse_of_canonical_bytes(
    tmp_path: Path,
) -> None:
    inner = FilesystemBlobStore(tmp_path / "blobs")
    blobs = CountingBlobStore(inner)
    original = blobs.put(ORIGINAL)
    converter_blob = blobs.put(NORMALIZED)
    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    events = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    service = SubstrateProductionService(blobs=blobs, events=events, clock=FixedClock())

    service.produce(
        source_id=SOURCE_ID,
        original_blob=trusted(original),
        converter=converter(original, blob=converter_blob),
        context=context(),
    )

    # The converter verification is one read; the other two are the substrate
    # integrity check and the event-envelope decode during append.
    assert blobs.get_counts[str(converter_blob.id)] == 3
    inner.close()


def test_policy_page_map_and_bytes_changes_create_new_receipts(tmp_path: Path) -> None:
    service, blobs, events, _ = make_service(tmp_path)
    original = blobs.put(ORIGINAL)
    first = service.produce(
        source_id=SOURCE_ID,
        original_blob=trusted(original),
        converter=converter(original),
        context=context(),
    )
    policy_changed = service.produce(
        source_id=SOURCE_ID,
        original_blob=trusted(original),
        converter=converter(original, policy="admission-2"),
        context=context(),
    )
    page_changed = service.produce(
        source_id=SOURCE_ID,
        original_blob=trusted(original),
        converter=converter(
            original,
            page_count=2,
            page_map=(PageMapEntry(0, 1), PageMapEntry(5, 2)),
        ),
        context=context(),
    )
    bytes_changed = service.produce(
        source_id=SOURCE_ID,
        original_blob=trusted(original),
        converter=converter(original, "Café\nchanged".encode()),
        context=context(),
    )

    assert policy_changed.receipt.substrate.substrate_id == first.receipt.substrate.substrate_id
    assert policy_changed.receipt.substrate_production_id != first.receipt.substrate_production_id
    assert (
        page_changed.receipt.substrate_production_id
        != policy_changed.receipt.substrate_production_id
    )
    assert bytes_changed.receipt.substrate.substrate_id != first.receipt.substrate.substrate_id
    assert len(events.read(COURSE_ID)) == 4
    blobs.close()


@pytest.mark.parametrize(
    "action",
    [
        lambda service, original: service.produce(
            source_id=SOURCE_ID,
            original_blob=trusted(original),
            converter=converter(original, b"\xff"),
            context=context(),
        ),
        lambda service, original: service.produce(
            source_id=SOURCE_ID,
            original_blob=trusted(original),
            converter=converter(original, page_count=2, page_map=()),
            context=context(),
        ),
    ],
)
def test_invalid_converter_receipts_fail_before_append(
    tmp_path: Path,
    action: Callable[[SubstrateProductionService, BlobRef], object],
) -> None:
    service, blobs, events, _ = make_service(tmp_path)
    original = blobs.put(ORIGINAL)
    with pytest.raises(SubstrateProductionError):
        action(service, original)
    assert events.read(COURSE_ID) == ()
    blobs.close()


def test_orphan_original_blob_fails_closed(tmp_path: Path) -> None:
    service, blobs, events, _ = make_service(tmp_path)
    digest = sha256(ORIGINAL).hexdigest()
    orphan = BlobRef(BlobId(f"sha256:{digest}"), digest, len(ORIGINAL))
    with pytest.raises(SubstrateProductionError, match="original_blob"):
        service.produce(
            source_id=SOURCE_ID,
            original_blob=trusted(orphan),
            converter=converter(orphan),
            context=context(),
        )
    assert events.read(COURSE_ID) == ()
    blobs.close()


class ConflictStore:
    def __init__(self, blobs: FilesystemBlobStore) -> None:
        self.blobs = blobs

    def put(self, content: bytes) -> BlobRef:
        return self.blobs.put(content)

    def get(self, ref: BlobRef) -> bytes:
        return self.blobs.get(ref)

    def read(
        self, _course_id: CourseId, after_sequence: int = 0
    ) -> Sequence[DomainEvent]:
        del after_sequence
        return ()

    def append(
        self,
        course_id: CourseId,
        expected_sequence: int,
        events: Sequence[DomainEvent],
    ) -> int:
        raise EventSequenceConflictError(course_id, expected_sequence, expected_sequence + 1)


def test_append_conflict_fails_closed_when_no_concurrent_matching_receipt(tmp_path: Path) -> None:
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    original = blobs.put(ORIGINAL)
    service = SubstrateProductionService(
        blobs=blobs,
        events=ConflictStore(blobs),
        clock=FixedClock(),
    )
    with pytest.raises(SubstrateProductionError, match="sequence changed"):
        service.produce(
            source_id=SOURCE_ID,
            original_blob=trusted(original),
            converter=converter(original),
            context=context(),
        )
    blobs.close()
