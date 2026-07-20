from __future__ import annotations

import inspect

import pytest

from study_agent.flashcards.lesson_worker_contracts import LessonWorkerCheckpoint
from study_agent.flashcards.lesson_worker_service import LessonWorkerService
from study_agent.ports.lesson_worker import LessonWorkerStore


def test_oversized_checkpoint_fails_explicitly_before_decode() -> None:
    with pytest.raises(ValueError, match="lesson_worker_checkpoint_limit_exceeded"):
        LessonWorkerCheckpoint.from_bytes(b"x" * (8 * 1024 * 1024 + 1))


def test_public_recovery_surface_and_atomic_store_calls_remain_exact() -> None:
    assert tuple(inspect.signature(LessonWorkerService.start).parameters) == (
        "self",
        "request",
        "parent",
    )
    assert tuple(inspect.signature(LessonWorkerService.advance).parameters) == (
        "self",
        "run_id",
        "request",
        "parent",
    )
    assert tuple(inspect.signature(LessonWorkerService.review_page).parameters) == (
        "self",
        "run_id",
        "request",
        "page_position",
        "parent",
    )
    assert tuple(inspect.signature(LessonWorkerStore.create).parameters) == (
        "self",
        "key",
        "payload",
    )
    assert tuple(inspect.signature(LessonWorkerStore.compare_and_set).parameters) == (
        "self",
        "key",
        "expected",
        "replacement",
    )
    assert tuple(inspect.signature(LessonWorkerStore.load).parameters) == (
        "self",
        "key",
    )
