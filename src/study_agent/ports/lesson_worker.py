"""Inward ports for the lesson-scoped flashcard coordinator."""

from __future__ import annotations

from typing import Protocol

from study_agent.domain import ExecutionContext
from study_agent.domain._validation import JsonObject
from study_agent.flashcards.lesson_worker_contracts import (
    ProfileTaskExpectation,
    ResolvedPlannedBundleEvidence,
    RevisionContentCommitment,
    VerifiedFlashcardPageResult,
)
from study_agent.flashcards.planning import (
    FlashcardLessonPlan,
    PlannedFlashcardBundle,
    PreparedPlannedFlashcardScope,
)
from study_agent.workers.contracts import GenerationWorkerTask
from study_agent.workers.view import WorkerCompactView


class PlannedBundleEvidenceResolver(Protocol):
    def resolve(
        self,
        plan: FlashcardLessonPlan,
        bundle: PlannedFlashcardBundle,
        revision_commitments: tuple[RevisionContentCommitment, ...],
        context: ExecutionContext,
    ) -> ResolvedPlannedBundleEvidence: ...


class FlashcardProfileTaskBinding(Protocol):
    @property
    def expectation(self) -> ProfileTaskExpectation: ...

    def build(
        self,
        task_id: str,
        public_inputs: JsonObject,
        prepared_scope: PreparedPlannedFlashcardScope,
        context: ExecutionContext,
    ) -> GenerationWorkerTask: ...


class PlannedBundleWorker(Protocol):
    async def start(
        self,
        task: GenerationWorkerTask,
        prepared_scope: PreparedPlannedFlashcardScope,
        context: ExecutionContext,
    ) -> WorkerCompactView: ...

    def detail(
        self,
        task_id: str,
        prepared_scope_fingerprint: str,
        context: ExecutionContext,
    ) -> VerifiedFlashcardPageResult: ...


class LessonWorkerStore(Protocol):
    def create(self, key: str, payload: bytes) -> bool: ...

    def compare_and_set(self, key: str, expected: bytes, replacement: bytes) -> bool: ...

    def load(self, key: str) -> bytes: ...


__all__ = [
    "FlashcardProfileTaskBinding",
    "LessonWorkerStore",
    "PlannedBundleEvidenceResolver",
    "PlannedBundleWorker",
]
