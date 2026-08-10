"""Deterministic optional adapter for the exact ``fsrs==6.3.1`` package.

Only this module knows about FSRS package objects.  The public method accepts
and returns the provider-neutral recall DTOs, and a fresh package card is
reconstructed from the complete canonical history for every decision.
"""

from __future__ import annotations

import importlib
import importlib.metadata
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import ModuleType
from typing import Any, cast

from study_agent.domain._validation import JsonObject
from study_agent.recall.contracts import (
    RecallRating,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    effective_policy_fingerprint,
    result_fingerprint,
)
from study_agent.state import canonical_json_bytes

FSRS_IMPLEMENTATION_ID = "py-fsrs"
FSRS_IMPLEMENTATION_VERSION = "6.3.1"
FSRS_ADAPTER_POLICY_ID = "fsrs"
_ADAPTER_POLICY_SCHEMA_VERSION = 1

# These are the published 6.3.1 defaults, copied into the adapter so package
# defaults cannot silently change scheduling.  They are passed explicitly to
# every Scheduler construction and are included in the adapter fingerprint.
_FSRS_PARAMETERS: tuple[float, ...] = (
    0.212,
    1.2931,
    2.3065,
    8.2956,
    6.4133,
    0.8334,
    3.0194,
    0.001,
    1.8722,
    0.1666,
    0.796,
    1.4835,
    0.0614,
    0.2629,
    1.6483,
    0.6014,
    1.8729,
    0.5425,
    0.0912,
    0.0658,
    0.1542,
)

_ADAPTER_POLICY_DESCRIPTOR: JsonObject = {
    "schema_version": _ADAPTER_POLICY_SCHEMA_VERSION,
    "implementation_id": FSRS_IMPLEMENTATION_ID,
    "implementation_version": FSRS_IMPLEMENTATION_VERSION,
    "parameters": _FSRS_PARAMETERS,
    "enable_fuzzing": False,
}
FSRS_CONFIGURATION_FINGERPRINT = sha256(
    b"study-agent.fsrs-policy@1\0" + canonical_json_bytes(_ADAPTER_POLICY_DESCRIPTOR)
).hexdigest()
FSRS_ADAPTER_POLICY_VERSION = (
    f"{FSRS_IMPLEMENTATION_VERSION}.policy-{FSRS_CONFIGURATION_FINGERPRINT}"
)


class FsrsAdapterError(RuntimeError):
    """The optional scheduler cannot produce a safe provider-neutral result."""


class FsrsUnavailableError(FsrsAdapterError):
    """The exact optional FSRS distribution or its supported API is unavailable."""


class PyFsrsSchedulingPolicy:
    """Implement :class:`SchedulingPolicyPort` with deterministic FSRS calls."""

    def __init__(self) -> None:
        # Composition fails before a host can issue a command.  Decisions also
        # revalidate the distribution because an embedding process can mutate
        # its environment after construction.
        _load_fsrs()

    @property
    def configuration_fingerprint(self) -> str:
        """Fingerprint of every fixed effective FSRS parameter."""

        return FSRS_CONFIGURATION_FINGERPRINT

    def configuration_fingerprint_for(self, policy: SchedulingPolicyConfigV1) -> str:
        """Bind fixed adapter settings and all request policy parameters."""

        if not isinstance(policy, SchedulingPolicyConfigV1):
            raise TypeError("policy must be SchedulingPolicyConfigV1")
        return effective_policy_fingerprint(
            policy,
            FSRS_ADAPTER_POLICY_ID,
            FSRS_ADAPTER_POLICY_VERSION,
            FSRS_IMPLEMENTATION_ID,
            FSRS_IMPLEMENTATION_VERSION,
        )

    def decide(self, request: SchedulingRequest) -> SchedulingResult:
        """Schedule one request without exposing FSRS package state."""

        if not isinstance(request, SchedulingRequest):
            raise TypeError("request must be SchedulingRequest")
        fsrs = _load_fsrs()
        _validate_history_order(request)
        scheduler = _new_scheduler(fsrs, request.policy)
        card = _new_card(fsrs, request)
        for history in request.history:
            try:
                rating = _rating(fsrs, history.rating)
                reviewed = scheduler.review_card(
                    card,
                    rating,
                    review_datetime=_utc(history.occurred_at),
                    review_duration=history.latency_ms,
                )
                card = reviewed[0]
            except FsrsAdapterError:
                raise
            except Exception as error:
                raise FsrsAdapterError(
                    "FSRS could not apply the canonical review history"
                ) from error

        due_at = _utc(getattr(card, "due", None))
        if due_at < request.enrollment_at:
            raise FsrsAdapterError("FSRS returned a due time before enrollment")
        if request.history and due_at < request.history[-1].occurred_at:
            raise FsrsAdapterError("FSRS returned a due time before the latest review")
        partial = SchedulingResult(
            due_at,
            FSRS_ADAPTER_POLICY_ID,
            FSRS_ADAPTER_POLICY_VERSION,
            effective_policy_fingerprint(
                request.policy,
                FSRS_ADAPTER_POLICY_ID,
                FSRS_ADAPTER_POLICY_VERSION,
                FSRS_IMPLEMENTATION_ID,
                FSRS_IMPLEMENTATION_VERSION,
            ),
            FSRS_IMPLEMENTATION_ID,
            FSRS_IMPLEMENTATION_VERSION,
            request.history_fingerprint,
            "0" * 64,
        )
        return _with_result_fingerprint(request, partial)


def _load_fsrs() -> ModuleType:
    try:
        installed = importlib.metadata.version("fsrs")
    except importlib.metadata.PackageNotFoundError as error:
        raise FsrsUnavailableError(
            "FSRS is unavailable; install the optional dependency with "
            "study-agent-harness[recall] (requires fsrs==6.3.1)"
        ) from error
    except Exception as error:
        raise FsrsUnavailableError("FSRS version metadata could not be read") from error
    if installed != FSRS_IMPLEMENTATION_VERSION:
        raise FsrsUnavailableError(
            f"unsupported fsrs version {installed!r}; install exactly "
            f"fsrs=={FSRS_IMPLEMENTATION_VERSION}"
        )
    try:
        module = importlib.import_module("fsrs")
    except Exception as error:
        raise FsrsUnavailableError(
            "FSRS is installed but cannot be imported; reinstall the recall extra"
        ) from error
    if not all(hasattr(module, name) for name in ("Card", "Rating", "Scheduler", "State")):
        raise FsrsUnavailableError("installed fsrs package does not expose the supported API")
    return module


def _new_scheduler(fsrs: ModuleType, policy: SchedulingPolicyConfigV1) -> Any:
    scheduler_type = cast(Any, fsrs).Scheduler
    try:
        return scheduler_type(
            parameters=_FSRS_PARAMETERS,
            desired_retention=policy.target_retention_bps / 10000,
            learning_steps=tuple(timedelta(minutes=item) for item in policy.learning_steps_minutes),
            relearning_steps=tuple(
                timedelta(minutes=item) for item in policy.relearning_steps_minutes
            ),
            maximum_interval=policy.maximum_interval_days,
            enable_fuzzing=False,
        )
    except Exception as error:
        raise FsrsAdapterError("FSRS scheduler configuration is invalid") from error


def _new_card(fsrs: ModuleType, request: SchedulingRequest) -> Any:
    fsrs_module = cast(Any, fsrs)
    card_type = fsrs_module.Card
    state_type = fsrs_module.State
    try:
        return card_type(
            card_id=_card_id(str(request.revision_id)),
            state=state_type.Learning,
            step=0,
            due=_utc(request.enrollment_at),
            last_review=None,
        )
    except Exception as error:
        raise FsrsAdapterError("FSRS card initialization failed") from error


def _rating(fsrs: ModuleType, value: RecallRating) -> Any:
    rating_type = cast(Any, fsrs).Rating
    if value is RecallRating.AGAIN:
        return rating_type.Again
    if value is RecallRating.HARD:
        return rating_type.Hard
    if value is RecallRating.GOOD:
        return rating_type.Good
    if value is RecallRating.EASY:
        return rating_type.Easy
    raise FsrsAdapterError("unsupported recall rating")


def _validate_history_order(request: SchedulingRequest) -> None:
    previous: datetime | None = None
    for item in request.history:
        occurred_at = _utc(item.occurred_at)
        if previous is not None and occurred_at < previous:
            raise FsrsAdapterError("canonical review history is not in deterministic time order")
        previous = occurred_at


def _with_result_fingerprint(
    request: SchedulingRequest, result: SchedulingResult
) -> SchedulingResult:
    return SchedulingResult(
        result.due_at,
        result.policy_id,
        result.policy_version,
        result.policy_fingerprint,
        result.implementation_id,
        result.implementation_version,
        result.history_fingerprint,
        result_fingerprint(request, result),
    )


def _card_id(revision_id: str) -> int:
    # The package uses this only as an internal identifier; it never crosses
    # the provider-neutral seam or enters canonical event payloads.
    return int.from_bytes(
        sha256(f"study-agent.fsrs-card@1\0{revision_id}".encode()).digest()[:8],
        "big",
    )


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise FsrsAdapterError("FSRS datetimes must be timezone-aware")
    return value.astimezone(UTC)


__all__ = [
    "FSRS_ADAPTER_POLICY_ID",
    "FSRS_ADAPTER_POLICY_VERSION",
    "FSRS_CONFIGURATION_FINGERPRINT",
    "FSRS_IMPLEMENTATION_ID",
    "FSRS_IMPLEMENTATION_VERSION",
    "FsrsAdapterError",
    "FsrsUnavailableError",
    "PyFsrsSchedulingPolicy",
]
