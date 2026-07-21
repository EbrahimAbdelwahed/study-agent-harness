"""Unsupported-source-format tracer bullet.

The tracer accepts typed host evidence only.  It never receives or inspects a
filename, path, MIME string, source body, or prompt text.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .contracts import (
    CapabilityGapObservation,
    CapabilityGapWriteContext,
    GapCategory,
    ImpactKind,
    RequestedOperationKind,
    SafeTargetKind,
    TrustedLimitationCode,
    TrustedLimitationReceipt,
)
from .service import CapabilityGapService


class SourceFormatDisposition(StrEnum):
    NOT_INGESTED = "not_ingested"
    SUPPORTED_DERIVATIVE_REQUESTED = "supported_derivative_requested"


@dataclass(frozen=True, slots=True)
class UnsupportedSourceEvidence:
    """Host-produced evidence for an unsupported source family."""

    target_kind: SafeTargetKind
    contract_identity: str
    contract_major: int
    failure_fingerprint: str

    def receipt(self) -> TrustedLimitationReceipt:
        return TrustedLimitationReceipt(
            self.contract_identity,
            self.contract_major,
            TrustedLimitationCode.UNSUPPORTED_FORMAT,
            self.failure_fingerprint,
        )


@dataclass(frozen=True, slots=True)
class SourceFormatTrace:
    disposition: SourceFormatDisposition
    learner_message: str
    report: object


def trace_unsupported_source_format(
    service: CapabilityGapService,
    evidence: UnsupportedSourceEvidence,
    context: CapabilityGapWriteContext,
) -> SourceFormatTrace:
    """Record one typed limitation and return an honest manual fallback."""

    if not isinstance(evidence, UnsupportedSourceEvidence):
        raise ValueError("invalid_source_evidence")
    if context.limitation_receipt is not None:
        # A mismatching receipt is never replaced by source-format evidence.
        if context.limitation_receipt != evidence.receipt():
            raise ValueError("limitation_receipt_context_mismatch")
        write_context = context
    else:
        write_context = CapabilityGapWriteContext(
            context.harness_version,
            context.correlation_id,
            context.idempotency_fingerprint,
            context.observed_at,
            evidence.receipt(),
        )
    observation = CapabilityGapObservation(
        GapCategory.INPUT_FORMAT,
        RequestedOperationKind.INGEST_SOURCE,
        evidence.target_kind,
        ImpactKind.WORKAROUND_AVAILABLE,
    )
    receipt = service.record(observation, write_context)
    return SourceFormatTrace(
        SourceFormatDisposition.SUPPORTED_DERIVATIVE_REQUESTED,
        (
            "I couldn't ingest this material format. Please provide a supported "
            ".txt or .md derivative; the original was not changed."
        ),
        receipt,
    )


__all__ = [
    "SourceFormatDisposition",
    "SourceFormatTrace",
    "UnsupportedSourceEvidence",
    "trace_unsupported_source_format",
]
