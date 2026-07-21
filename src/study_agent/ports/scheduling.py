"""The inward, provider-neutral scheduling seam."""

from __future__ import annotations

from typing import Protocol

from study_agent.recall.contracts import SchedulingRequest, SchedulingResult


class SchedulingPolicyPort(Protocol):
    def decide(self, request: SchedulingRequest) -> SchedulingResult: ...


__all__ = ["SchedulingPolicyPort"]
