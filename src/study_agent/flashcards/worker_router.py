"""Closed historical routing for request-scoped flashcard workers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType

from study_agent.flashcards.lesson_worker_contracts import LessonWorkerRequest
from study_agent.pedagogy import PedagogicalProfileRef
from study_agent.ports.lesson_worker import PlannedBundleWorker

type PlannedBundleWorkerFactory = Callable[[LessonWorkerRequest], PlannedBundleWorker]


class ClosedHistoricalPlannedBundleWorkerRouter:
    """Select a trusted worker factory from the profile persisted in a request."""

    def __init__(
        self,
        factories: Mapping[PedagogicalProfileRef, PlannedBundleWorkerFactory],
    ) -> None:
        copied = dict(factories)
        if not copied:
            raise ValueError("historical worker router requires profile factories")
        if not all(isinstance(profile, PedagogicalProfileRef) for profile in copied):
            raise TypeError("historical worker route keys must be pedagogical profiles")
        if not all(callable(factory) for factory in copied.values()):
            raise TypeError("historical worker routes must be callable factories")
        self._factories = MappingProxyType(copied)

    def for_request(self, request: LessonWorkerRequest) -> PlannedBundleWorker:
        if not isinstance(request, LessonWorkerRequest):
            raise TypeError("historical worker routing requires LessonWorkerRequest")
        profile = request.profile_expectation.profile_selection_receipt.profile
        try:
            factory = self._factories[profile]
        except KeyError as error:
            raise LookupError(
                f"no trusted historical worker for profile {profile.identity}"
            ) from error
        return factory(request)


__all__ = [
    "ClosedHistoricalPlannedBundleWorkerRouter",
    "PlannedBundleWorkerFactory",
]
