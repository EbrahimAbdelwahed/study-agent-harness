"""Bounded host and authorized review views for lesson workers."""

from __future__ import annotations

from dataclasses import dataclass

from study_agent.artifacts.candidates import FlashcardCandidateBatch
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


@dataclass(frozen=True, slots=True)
class LessonWorkerBatchReviewView:
    """One exact-decoded verified batch in canonical lesson-plan order."""

    page_position: int
    bundle_id: str
    bundle_kind: PlannedBundleKind
    active_topic_keys: tuple[str, ...]
    wrapper_fingerprint: str
    scope_fingerprint: str
    read_set_fingerprint: str
    batch: FlashcardCandidateBatch


@dataclass(frozen=True, slots=True)
class LessonWorkerOverviewAssociation:
    """One optional overview candidate associated to later canonical pages."""

    page_position: int
    candidate_key: str
    associated_page_positions: tuple[int, ...]
    associated_bundle_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LessonWorkerCompletedReviewView:
    """Authorized typed review of a fully successful lesson run."""

    run_id: RunId
    plan_fingerprint: str
    profile_fingerprint: str
    revision_commitments_fingerprint: str
    pages: tuple[LessonWorkerBatchReviewView, ...]
    overview_associations: tuple[LessonWorkerOverviewAssociation, ...]


__all__ = [
    "LessonWorkerBatchReviewView",
    "LessonWorkerCompactView",
    "LessonWorkerCompletedReviewView",
    "LessonWorkerOverviewAssociation",
    "LessonWorkerPageReviewView",
]
