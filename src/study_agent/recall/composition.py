"""Optional recall composition without importing a scheduling implementation.

The canonical ledger and read views are useful for replay even when no
scheduler extra is installed.  Commands are exposed only when a host supplies
an explicit provider-neutral scheduler instance (or a lazy factory).  This
keeps FSRS and other package imports outside the core composition path.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from study_agent.artifacts.view import ProjectionArtifactView
from study_agent.domain import CourseId
from study_agent.ports.artifact import ArtifactViewPort
from study_agent.ports.clock import ClockPort
from study_agent.ports.scheduling import SchedulingPolicyPort
from study_agent.ports.storage import EventStore
from study_agent.state import Projection

from .due import DueRecallView
from .service import RecallService
from .view import ProjectionRecallView


class RecallAvailabilityCode(StrEnum):
    """Stable host-facing reasons for optional recall availability."""

    AVAILABLE = "available"
    NOT_CONFIGURED = "not_configured"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class RecallAvailability:
    """A safe, actionable result for optional recall composition."""

    code: RecallAvailabilityCode
    message: str

    @property
    def available(self) -> bool:
        return self.code is RecallAvailabilityCode.AVAILABLE

    def to_json(self) -> dict[str, str | bool]:
        return {"available": self.available, "code": self.code.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class RecallComposition:
    """Read views plus an optional command service for one repository."""

    availability: RecallAvailability
    view: ProjectionRecallView
    due: DueRecallView
    service: RecallService | None

    @property
    def commands(self) -> RecallService | None:
        """Alias used by hosts that treat commands as a separate boundary."""

        return self.service


def compose_recall(
    *,
    events: EventStore,
    load_projection: Callable[[CourseId], Projection],
    clock: ClockPort,
    scheduler: SchedulingPolicyPort | None = None,
    scheduler_factory: Callable[[], SchedulingPolicyPort] | None = None,
    artifacts: ArtifactViewPort | None = None,
) -> RecallComposition:
    """Compose optional recall around an explicit scheduler or lazy factory.

    A factory is intentionally host-owned: it may import an optional adapter,
    but the harness itself never imports that package.  Factory failures are
    converted to one redacted availability result and cannot reach canonical
    writes.  Supplying both a scheduler and factory is rejected to avoid
    ambiguous composition.
    """

    if scheduler is not None and scheduler_factory is not None:
        raise TypeError("scheduler and scheduler_factory are mutually exclusive")
    recall_view = ProjectionRecallView(_course_projection_loader(load_projection))
    due = DueRecallView(_course_projection_loader(load_projection), clock)
    if scheduler_factory is not None:
        try:
            scheduler = scheduler_factory()
        except Exception:
            return RecallComposition(
                RecallAvailability(
                    RecallAvailabilityCode.UNAVAILABLE,
                    "optional recall scheduler is unavailable; install and configure "
                    "the recall extra",
                ),
                recall_view,
                due,
                None,
            )
    if scheduler is None:
        return RecallComposition(
                RecallAvailability(
                    RecallAvailabilityCode.NOT_CONFIGURED,
                    "recall is optional; supply an explicit scheduling adapter "
                    "(for example the recall extra)",
            ),
            recall_view,
            due,
            None,
        )
    artifact_view = artifacts or ProjectionArtifactView(
        _course_projection_loader(load_projection)
    )
    return RecallComposition(
        RecallAvailability(
            RecallAvailabilityCode.AVAILABLE, "optional recall scheduler configured"
        ),
        recall_view,
        due,
        RecallService(events, clock, artifact_view, scheduler, recall_view),
    )


def _course_projection_loader(
    load_projection: Callable[[CourseId], Projection],
) -> Callable[[CourseId], Projection]:
    def load(course_id: CourseId) -> Projection:
        return load_projection(course_id)

    return load


__all__ = [
    "RecallAvailability",
    "RecallAvailabilityCode",
    "RecallComposition",
    "compose_recall",
]
