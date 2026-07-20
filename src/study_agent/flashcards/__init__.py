"""Provider-neutral private contracts for grounded flashcard generation."""

from .scope import (
    MAX_FLASHCARD_SCOPE_ENTRIES,
    MAX_FLASHCARD_SCOPE_EVIDENCE_ITEMS,
    FlashcardScopeIndexEntry,
    PreparedFlashcardScope,
    VerifiedMediaEvidence,
)

__all__ = [
    "MAX_FLASHCARD_SCOPE_ENTRIES",
    "MAX_FLASHCARD_SCOPE_EVIDENCE_ITEMS",
    "FlashcardScopeIndexEntry",
    "PreparedFlashcardScope",
    "VerifiedMediaEvidence",
]
