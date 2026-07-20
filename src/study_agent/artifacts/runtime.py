"""Composition of verified generated-batch recovery over caller-owned stores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from study_agent.workers import VerifiedChildProofOwner

if TYPE_CHECKING:
    from study_agent.ports.exam import ExamSampleScopePreparationPort
    from study_agent.ports.generated_owner import GeneratedBatchOwnerStore
    from study_agent.ports.lesson_worker import (
        HistoricalPlannedBundleWorkerRouter,
        LessonWorkerStore,
    )
    from study_agent.ports.storage import SourceContentPort
    from study_agent.ports.worker import VerifiedChildProofStore

from .generated_owner import GeneratedBatchOwnerRegistry
from .verified_batch import (
    VerifiedExamOwnerWriterAdapter,
    VerifiedGeneratedBatchAdapter,
    VerifiedGeneratedOwnerResolverAdapter,
    VerifiedLessonOwnerWriterAdapter,
)


@dataclass(frozen=True, slots=True)
class VerifiedGeneratedBatchRuntime:
    """One shared proof/owner graph for publication and later recovery."""

    owners: GeneratedBatchOwnerRegistry
    proofs: VerifiedChildProofOwner
    lesson_owner_writer: VerifiedLessonOwnerWriterAdapter
    exam_owner_writer: VerifiedExamOwnerWriterAdapter
    resolver: VerifiedGeneratedOwnerResolverAdapter
    batches: VerifiedGeneratedBatchAdapter


def compose_verified_generated_batch_runtime(
    *,
    owner_store: GeneratedBatchOwnerStore,
    proof_store: VerifiedChildProofStore,
    lesson_store: LessonWorkerStore,
    lesson_workers: HistoricalPlannedBundleWorkerRouter,
    exam_scope: ExamSampleScopePreparationPort,
    source_content: SourceContentPort,
) -> VerifiedGeneratedBatchRuntime:
    """Wire writers and recovery to the same durable owner and proof stores."""

    owners = GeneratedBatchOwnerRegistry(owner_store)
    proofs = VerifiedChildProofOwner(proof_store)
    resolver = VerifiedGeneratedOwnerResolverAdapter(
        lesson_store=lesson_store,
        lesson_worker=lesson_workers,
        exam_scope=exam_scope,
        source_content=source_content,
    )
    return VerifiedGeneratedBatchRuntime(
        owners=owners,
        proofs=proofs,
        lesson_owner_writer=VerifiedLessonOwnerWriterAdapter(proofs, owners),
        exam_owner_writer=VerifiedExamOwnerWriterAdapter(owners),
        resolver=resolver,
        batches=VerifiedGeneratedBatchAdapter(
            owners=owners,
            resolver=resolver,
            proofs=proofs,
        ),
    )


__all__ = [
    "VerifiedGeneratedBatchRuntime",
    "compose_verified_generated_batch_runtime",
]
