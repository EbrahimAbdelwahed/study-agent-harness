"""Inward ports for grounded exam-sample analysis."""

from typing import Protocol

from study_agent.domain import ExecutionContext, RunId
from study_agent.exams.contracts import ExamAnalysisRequest, PreparedExamSampleScope
from study_agent.workers import (
    GenerationWorkerReceipt,
    GenerationWorkerTask,
    VerifiedChildExecutionProofView,
)


class ExamSampleScopePreparationPort(Protocol):
    def prepare(
        self, request: ExamAnalysisRequest, context: ExecutionContext
    ) -> PreparedExamSampleScope: ...


class ExamVerifiedChildProofReader(Protocol):
    def load(
        self,
        task: GenerationWorkerTask,
        run_id: RunId,
        receipt: GenerationWorkerReceipt,
        context: ExecutionContext,
    ) -> VerifiedChildExecutionProofView: ...


__all__ = ["ExamSampleScopePreparationPort", "ExamVerifiedChildProofReader"]
