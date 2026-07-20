from __future__ import annotations

from dataclasses import replace
from typing import NoReturn

import pytest

from study_agent.domain import ExecutionContext, PrincipalKind, RevisionId
from study_agent.flashcards.lesson_worker_contracts import LessonWorkerRequest
from study_agent.flashcards.planning import PreparedPlannedFlashcardScope
from study_agent.flashcards.worker_router import (
    ClosedHistoricalPlannedBundleWorkerRouter,
)
from study_agent.pedagogy import (
    HYBRID_MACRO_DETAIL_V1,
    MORPHOLOGY_FIRST_ANATOMY_V1,
    ProfileSelectionBasis,
    ProfileSelectionMode,
    ProfileSelectionReceipt,
    ProfileSelectorKind,
)
from study_agent.workers import GenerationWorkerTask
from study_agent.workers.view import WorkerCompactView
from tests.unit.flashcards.test_lesson_worker_contracts import _request


class _Worker:
    def __init__(self, expectation: object, label: str) -> None:
        self.expectation = expectation
        self.label = label

    async def start(
        self,
        task: GenerationWorkerTask,
        prepared_scope: PreparedPlannedFlashcardScope,
        context: ExecutionContext,
    ) -> WorkerCompactView:
        raise AssertionError("routing test does not execute workers")

    def detail(
        self,
        task_id: str,
        prepared_scope_fingerprint: str,
        context: ExecutionContext,
    ) -> NoReturn:
        raise AssertionError("routing test does not inspect worker details")


def _morphology_request() -> LessonWorkerRequest:
    request = _request()
    receipt = ProfileSelectionReceipt(
        MORPHOLOGY_FIRST_ANATOMY_V1,
        ProfileSelectionMode.TRUSTED_METADATA,
        ProfileSelectorKind.TRUSTED_MATERIAL,
        PrincipalKind.SERVICE,
        ProfileSelectionBasis(source_revision_id=RevisionId("rev-a")),
    )
    return replace(
        request,
        profile_expectation=replace(
            request.profile_expectation,
            profile_selection_receipt=receipt,
        ),
    )


def test_router_rebuilds_hybrid_and_morphology_workers_from_persisted_request() -> None:
    calls: list[tuple[str, object]] = []

    def hybrid(request: LessonWorkerRequest) -> _Worker:
        calls.append(("hybrid", request))
        return _Worker(request.profile_expectation, "hybrid")

    def morphology(request: LessonWorkerRequest) -> _Worker:
        calls.append(("morphology", request))
        return _Worker(request.profile_expectation, "morphology")

    router = ClosedHistoricalPlannedBundleWorkerRouter(
        {
            HYBRID_MACRO_DETAIL_V1: hybrid,
            MORPHOLOGY_FIRST_ANATOMY_V1: morphology,
        }
    )
    hybrid_request = _request()
    morphology_request = _morphology_request()

    assert router.for_request(hybrid_request).label == "hybrid"  # type: ignore[attr-defined]
    assert router.for_request(morphology_request).label == "morphology"  # type: ignore[attr-defined]
    assert calls == [
        ("hybrid", hybrid_request),
        ("morphology", morphology_request),
    ]


def test_router_fails_closed_for_unconfigured_historical_profile() -> None:
    router = ClosedHistoricalPlannedBundleWorkerRouter(
        {
            HYBRID_MACRO_DETAIL_V1: lambda request: _Worker(
                request.profile_expectation, "hybrid"
            )
        }
    )

    with pytest.raises(LookupError, match="morphology-first-anatomy@1"):
        router.for_request(_morphology_request())
