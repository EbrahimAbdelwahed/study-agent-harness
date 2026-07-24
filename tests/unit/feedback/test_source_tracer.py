from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from study_agent.adapters.sqlite.capability_gap_store import SQLiteCapabilityGapStore
from study_agent.feedback import (
    CapabilityGapService,
    CapabilityGapWriteContext,
    SafeTargetKind,
    SourceFormatMetadata,
    UnsupportedSourceEvidence,
    trace_unsupported_source_format,
)


def test_source_tracer_uses_metadata_only_and_preserves_original(tmp_path: Path) -> None:
    service = CapabilityGapService(SQLiteCapabilityGapStore(tmp_path / "gap.sqlite3"))
    evidence = UnsupportedSourceEvidence(
        SafeTargetKind.PDF, "reader@1", 1, "a" * 64, ".pdf", "application/pdf"
    )
    trace = trace_unsupported_source_format(
        service,
        evidence,
        CapabilityGapWriteContext(
            "harness@1", "corr@1", "b" * 64, datetime(2026, 7, 24, tzinfo=UTC)
        ),
        SourceFormatMetadata(".pdf", "application/pdf"),
    )
    assert trace.original_immutable is True
    assert "txt" in trace.learner_message and "md" in trace.learner_message
    assert trace.report is not None


@pytest.mark.parametrize("metadata", [SourceFormatMetadata(".pdf", "application/pdf", None)])
def test_source_metadata_rejects_hostile_filename_without_body_access(
    metadata: SourceFormatMetadata,
) -> None:
    with pytest.raises(ValueError):
        SourceFormatMetadata(".pdf", "application/pdf", "../prompt injection")
