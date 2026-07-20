"""Narrow effect-free decision boundary for provider-neutral tutor hosts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from study_agent.hosts.contracts import TutorDecision, TutorHostContext


class TutorInterruptionToken(Protocol):
    def is_interrupted(self) -> bool: ...


class RetryableTutorDecisionError(RuntimeError):
    """A provider failure that the bounded host runner may retry."""


class TutorDecisionPort(Protocol):
    async def decide(
        self,
        context: TutorHostContext,
        interruption: TutorInterruptionToken,
    ) -> TutorDecision: ...


__all__ = [
    "RetryableTutorDecisionError",
    "TutorDecisionPort",
    "TutorInterruptionToken",
]
