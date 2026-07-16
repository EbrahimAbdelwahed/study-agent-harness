"""Bounded host and authorized review views for lesson workers."""

from __future__ import annotations

from dataclasses import dataclass

from study_agent.domain import RunId
from study_agent.flashcards.lesson_worker_contracts import LessonWorkerStatus
from study_agent.flashcards.planning import PlannedBundleKind
from study_agent.workers.view import WorkerDetailView


@dataclass(frozen=True, slots=True)
class LessonWorkerCompactView:
    run_id: RunId
    plan_fingerprint: str
    profile_fingerprint: str
    status: LessonWorkerStatus
    completed_positions: tuple[int, ...]
    failed_positions: tuple[int, ...]
    pending_positions: tuple[int, ...]
    candidate_count: int
    omission_count: int
    failure_codes: tuple[str, ...]
    in_progress: bool
    advance_required: bool


@dataclass(frozen=True, slots=True)
class LessonWorkerPageReviewView:
    run_id: RunId
    plan_fingerprint: str
    profile_fingerprint: str
    page_position: int
    bundle_id: str
    bundle_kind: PlannedBundleKind
    active_topic_keys: tuple[str, ...]
    wrapper_fingerprint: str
    scope_fingerprint: str
    read_set_fingerprint: str
    revision_commitments_fingerprint: str
    detail: WorkerDetailView


__all__ = ["LessonWorkerCompactView", "LessonWorkerPageReviewView"]
