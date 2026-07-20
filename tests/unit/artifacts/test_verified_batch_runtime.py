from __future__ import annotations

from study_agent.artifacts.runtime import compose_verified_generated_batch_runtime
from study_agent.artifacts.verified_batch import (
    VerifiedExamOwnerWriterAdapter,
    VerifiedGeneratedBatchAdapter,
    VerifiedGeneratedOwnerResolverAdapter,
    VerifiedLessonOwnerWriterAdapter,
)
from study_agent.workers import VerifiedChildProofOwner


class _Unused:
    pass


def test_runtime_composes_one_shared_owner_and_proof_graph() -> None:
    store = _Unused()
    runtime = compose_verified_generated_batch_runtime(
        owner_store=store,  # type: ignore[arg-type]
        proof_store=store,  # type: ignore[arg-type]
        lesson_store=store,  # type: ignore[arg-type]
        lesson_workers=store,  # type: ignore[arg-type]
        exam_scope=store,  # type: ignore[arg-type]
        source_content=store,  # type: ignore[arg-type]
    )

    assert isinstance(runtime.proofs, VerifiedChildProofOwner)
    assert isinstance(runtime.lesson_owner_writer, VerifiedLessonOwnerWriterAdapter)
    assert isinstance(runtime.exam_owner_writer, VerifiedExamOwnerWriterAdapter)
    assert isinstance(runtime.resolver, VerifiedGeneratedOwnerResolverAdapter)
    assert isinstance(runtime.batches, VerifiedGeneratedBatchAdapter)
    assert runtime.lesson_owner_writer._proofs is runtime.proofs
    assert runtime.lesson_owner_writer._owners is runtime.owners
    assert runtime.exam_owner_writer._owners is runtime.owners
    assert runtime.batches._proofs is runtime.proofs
    assert runtime.batches._owners is runtime.owners
    assert runtime.batches._resolver is runtime.resolver
