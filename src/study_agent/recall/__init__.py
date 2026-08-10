"""Canonical provider-neutral recall ledger."""

from .contracts import (
    AppliedSchedule,
    RecallRating,
    RecallSnapshot,
    RecallViewRow,
    ReviewHistoryEntry,
    ReviewRecord,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    effective_policy_fingerprint,
    history_fingerprint,
    result_fingerprint,
)
from .due import DueRecallView
from .events import (
    RECALL_EVENT_TYPES,
    RECALL_SCHEMA_VERSION,
    REVIEW_RECORDED,
    SCHEDULE_APPLIED,
    ReviewRecorded,
    ScheduleApplied,
    decode_review_recorded,
    decode_schedule_applied,
    encode_review_recorded,
    encode_schedule_applied,
)
from .projection import reduce_review_recorded, reduce_schedule_applied, register_recall_events
from .service import (
    RecallCommandError,
    RecallConflictError,
    RecallService,
    RetryableRecallConflictError,
)
from .view import ProjectionRecallView

__all__ = [
    "RECALL_EVENT_TYPES",
    "RECALL_SCHEMA_VERSION",
    "REVIEW_RECORDED",
    "SCHEDULE_APPLIED",
    "AppliedSchedule",
    "DueRecallView",
    "ProjectionRecallView",
    "RecallAvailability",
    "RecallAvailabilityCode",
    "RecallCommandError",
    "RecallComposition",
    "RecallConflictError",
    "RecallRating",
    "RecallService",
    "RecallSnapshot",
    "RecallViewRow",
    "RetryableRecallConflictError",
    "ReviewHistoryEntry",
    "ReviewRecord",
    "ReviewRecorded",
    "ScheduleApplied",
    "SchedulingPolicyConfigV1",
    "SchedulingRequest",
    "SchedulingResult",
    "compose_recall",
    "decode_review_recorded",
    "decode_schedule_applied",
    "effective_policy_fingerprint",
    "encode_review_recorded",
    "encode_schedule_applied",
    "history_fingerprint",
    "reduce_review_recorded",
    "reduce_schedule_applied",
    "register_recall_events",
    "result_fingerprint",
]


def __getattr__(name: str) -> object:
    """Load application-layer B consumers without importing artifact adapters."""
    if name in {
        "RecallAvailability",
        "RecallAvailabilityCode",
        "RecallComposition",
        "compose_recall",
    }:
        from .composition import (
            RecallAvailability,
            RecallAvailabilityCode,
            RecallComposition,
            compose_recall,
        )

        return {
            "RecallAvailability": RecallAvailability,
            "RecallAvailabilityCode": RecallAvailabilityCode,
            "RecallComposition": RecallComposition,
            "compose_recall": compose_recall,
        }[name]
    if name == "DueRecallView":
        from .due import DueRecallView

        return DueRecallView
    if name in {
        "RecallCommandError",
        "RecallConflictError",
        "RecallService",
        "RetryableRecallConflictError",
    }:
        from .service import (
            RecallCommandError,
            RecallConflictError,
            RecallService,
            RetryableRecallConflictError,
        )

        return {
            "RecallCommandError": RecallCommandError,
            "RecallConflictError": RecallConflictError,
            "RecallService": RecallService,
            "RetryableRecallConflictError": RetryableRecallConflictError,
        }[name]
    raise AttributeError(name)
