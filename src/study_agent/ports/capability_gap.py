"""Inward port for the optional capability-gap operational plane."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from study_agent.feedback.contracts import CapabilityGapObservation, CapabilityGapWriteContext
    from study_agent.feedback.view import CapabilityGapCompactView


class CapabilityGapStore(Protocol):
    """Store canonical aggregate bytes without owning tutor/course state."""

    def create_or_increment(
        self, gap_key: str, report_id: str, payload: bytes
    ) -> tuple[bytes, bool]: ...

    def load(self, gap_key: str) -> bytes: ...


class FeatureGapSink(Protocol):
    """Trusted inward sink used by the separately discoverable host tool."""

    def record(
        self,
        observation: CapabilityGapObservation,
        write_context: CapabilityGapWriteContext,
    ) -> CapabilityGapCompactView: ...


__all__ = ["CapabilityGapStore", "FeatureGapSink"]
