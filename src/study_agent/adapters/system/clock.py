"""Wall-clock adapter for host application composition."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """Return timezone-aware UTC wall-clock timestamps."""

    def now(self) -> datetime:
        return datetime.now(UTC)
