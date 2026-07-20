from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from study_agent.adapters.sqlite.capability_gap_store import SQLiteCapabilityGapStore
from study_agent.feedback import (
    CapabilityGapObservation,
    CapabilityGapService,
    CapabilityGapWriteContext,
    GapCategory,
    GapDisposition,
    ImpactKind,
    RequestedOperationKind,
    SafeTargetKind,
)


def _observation(operation: RequestedOperationKind) -> CapabilityGapObservation:
    return CapabilityGapObservation(
        GapCategory.INPUT_FORMAT,
        operation,
        SafeTargetKind.PDF,
        ImpactKind.BLOCKED,
    )


def _context(fingerprint: str, at: datetime) -> CapabilityGapWriteContext:
    return CapabilityGapWriteContext("harness@1", "corr@1", fingerprint, at)


def test_service_returns_current_report_and_deduplicates_exact_retry(tmp_path: Path) -> None:
    service = CapabilityGapService(SQLiteCapabilityGapStore(tmp_path / "gaps.sqlite3"))
    at = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    observation = _observation(RequestedOperationKind.EXTRACT_TEXT)
    context = _context("a" * 64, at)
    first = service.record(observation, context)
    retry = service.record(observation, context)
    second = service.record(
        observation,
        _context("b" * 64, at + timedelta(seconds=1)),
    )
    assert first.disposition is GapDisposition.RECORDED
    assert retry.disposition is GapDisposition.DEDUPLICATED
    assert second.disposition is GapDisposition.RECORDED
    assert retry.report_id == first.report_id
    assert second.report_id != first.report_id
    assert first.occurrence_count == retry.occurrence_count == 1
    assert second.occurrence_count == 2
    detail = service.get(first.gap_key)
    assert detail.local_only is True
    assert detail.occurrence_count == 2
    assert detail.first_seen == at
    assert detail.last_seen == at + timedelta(seconds=1)


def test_distinct_operations_do_not_collapse(tmp_path: Path) -> None:
    service = CapabilityGapService(SQLiteCapabilityGapStore(tmp_path / "gaps.sqlite3"))
    at = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    extract = service.record(
        _observation(RequestedOperationKind.EXTRACT_TEXT), _context("a" * 64, at)
    )
    tables = service.record(
        _observation(RequestedOperationKind.PRESERVE_TABLES), _context("b" * 64, at)
    )
    assert extract.gap_key != tables.gap_key
    assert service.get(extract.gap_key).occurrence_count == 1
    assert service.get(tables.gap_key).occurrence_count == 1
