from datetime import UTC, datetime

from study_agent.adapters.system import SystemClock
from study_agent.ports import ClockPort


def test_system_clock_returns_current_timezone_aware_utc_time() -> None:
    clock: ClockPort = SystemClock()
    before = datetime.now(UTC)
    observed = clock.now()
    after = datetime.now(UTC)

    assert before <= observed <= after
    assert observed.tzinfo is UTC
    assert observed.utcoffset() is not None
