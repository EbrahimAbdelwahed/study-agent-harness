from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Host-supplied wall clock; values must be aware UTC instants."""

    def now(self) -> datetime: ...


# Historical callers use ``ClockPort``.  Keep one protocol owner while the
# package foundation publishes the shorter ``Clock`` name.
ClockPort = Clock


def require_utc(value: datetime) -> datetime:
    """Validate a clock result without changing the host-owned instant."""

    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock.now() must return an aware UTC datetime")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("clock.now() must return a UTC datetime")
    return value


__all__ = ["Clock", "ClockPort", "require_utc"]
