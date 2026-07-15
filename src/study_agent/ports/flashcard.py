"""Trusted preparation protocols for grounded flashcard generation."""

from __future__ import annotations

from typing import Protocol

from study_agent.domain import ExecutionContext
from study_agent.flashcards import PreparedFlashcardScope, VerifiedMediaEvidence


class FlashcardScopePreparationPort(Protocol):
    """Prepare one whole-scope index and bounded evidence bundle.

    Implementations, rather than this value protocol, own the semantic guarantee
    that the structural index enumerates the complete trusted request scope.
    """

    def prepare(
        self, context: ExecutionContext, query: str, scope: str | None
    ) -> PreparedFlashcardScope: ...


class VerifiedMediaEvidencePort(Protocol):
    def resolve(self, handle: str) -> VerifiedMediaEvidence: ...


__all__ = ["FlashcardScopePreparationPort", "VerifiedMediaEvidencePort"]
