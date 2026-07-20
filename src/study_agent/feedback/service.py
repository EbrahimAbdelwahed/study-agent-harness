"""Application service for recording and querying sanitized capability gaps."""

from __future__ import annotations

from study_agent.ports.capability_gap import CapabilityGapStore

from .contracts import (
    CapabilityGapAggregate,
    CapabilityGapObservation,
    CapabilityGapValidationError,
    CapabilityGapWriteContext,
    GapDisposition,
    GapKeyV1,
    proposal_for,
    report_id_for,
)
from .view import CapabilityGapCompactView, CapabilityGapDetailView


class CapabilityGapService:
    """Record one closed observation in a host-owned operational store."""

    def __init__(self, store: CapabilityGapStore) -> None:
        self._store = store

    def record(
        self,
        observation: CapabilityGapObservation,
        context: CapabilityGapWriteContext,
    ) -> CapabilityGapCompactView:
        if not isinstance(observation, CapabilityGapObservation) or not isinstance(
            context, CapabilityGapWriteContext
        ):
            raise CapabilityGapValidationError("invalid_gap_context")
        proposed = proposal_for(observation, context)
        report_id = report_id_for(proposed.gap_key, context.idempotency_fingerprint)
        payload, created = self._store.create_or_increment(
            proposed.gap_key.value, report_id, proposed.to_bytes()
        )
        try:
            aggregate = CapabilityGapAggregate.from_bytes(payload)
        except Exception as error:
            # Do not leak storage/JSON implementation details across the API.
            from .contracts import CapabilityGapCorruptionError

            if isinstance(error, CapabilityGapCorruptionError):
                raise
            raise CapabilityGapCorruptionError("gap_payload_invalid") from None
        if (
            aggregate.gap_key != proposed.gap_key
            or aggregate.dimensions != proposed.dimensions
            or aggregate.verification_kind != proposed.verification_kind
            or aggregate.impact_kind != proposed.impact_kind
        ):
            from .contracts import CapabilityGapCollisionError

            raise CapabilityGapCollisionError("gap_key_collision")
        return CapabilityGapCompactView(
            report_id=report_id,
            gap_key=aggregate.gap_key,
            occurrence_count=aggregate.occurrence_count,
            disposition=(GapDisposition.RECORDED if created else GapDisposition.DEDUPLICATED),
        )

    def get(self, gap_key: GapKeyV1 | str) -> CapabilityGapDetailView:
        key = gap_key if isinstance(gap_key, GapKeyV1) else GapKeyV1(gap_key)
        payload = self._store.load(key.value)
        aggregate = CapabilityGapAggregate.from_bytes(payload)
        if aggregate.gap_key != key:
            from .contracts import CapabilityGapCollisionError

            raise CapabilityGapCollisionError("gap_key_collision")
        return CapabilityGapDetailView.from_aggregate(aggregate)


__all__ = ["CapabilityGapService"]
