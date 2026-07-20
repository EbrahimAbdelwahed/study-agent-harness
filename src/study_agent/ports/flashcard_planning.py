"""Provider-neutral ports for trusted lesson flashcard planning."""

from __future__ import annotations

from typing import Protocol

from study_agent.flashcards.planning import (
    FlashcardPlanningPolicyReceipt,
    LessonGenerationUnit,
)


class FlashcardPlanningPolicy(Protocol):
    """Classify trusted structural topics without model-authored authority."""

    policy_id: str
    policy_version: str
    policy_fingerprint: str

    def classify(self, unit: LessonGenerationUnit) -> FlashcardPlanningPolicyReceipt: ...


__all__ = ["FlashcardPlanningPolicy"]
