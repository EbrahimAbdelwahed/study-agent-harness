from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import date
from typing import Any, cast

from study_agent.domain import (
    CorrelationId,
    CourseId,
    CourseProfile,
    ExecutionContext,
    PrincipalKind,
)
from study_agent.ports import CourseViewPort
from study_agent.tools import StudyToolRegistry, ToolErrorCode


class FakeCourses:
    def __init__(self, profile: CourseProfile) -> None:
        self.profile = profile
        self.calls = 0

    def get(self, course_id: CourseId) -> CourseProfile:
        self.calls += 1
        assert course_id == self.profile.id
        return self.profile


def _registry(courses: CourseViewPort) -> StudyToolRegistry:
    unavailable = cast(Any, object())
    return StudyToolRegistry(
        courses=courses,
        catalog=unavailable,
        retrieval=unavailable,
        content=unavailable,
        sessions=unavailable,
        grounding=unavailable,
    )


def _context(*capabilities: str) -> ExecutionContext:
    return ExecutionContext(
        PrincipalKind.HUMAN,
        "learner",
        CourseId("course-1"),
        CorrelationId("correlation-1"),
        frozenset(capabilities),
    )


def _model_context(*capabilities: str) -> ExecutionContext:
    return ExecutionContext(
        PrincipalKind.MODEL,
        "external-model",
        CourseId("course-1"),
        CorrelationId("correlation-model"),
        frozenset(capabilities),
    )


def test_registry_is_exactly_the_seven_versioned_tools_in_canonical_order() -> None:
    courses = FakeCourses(
        CourseProfile(
            CourseId("course-1"), "Medicine", "it", date(2027, 1, 1), learning_goals=("Pass",)
        )
    )
    manifests = _registry(courses).manifests
    assert tuple(item.name for item in manifests) == (
        "citation.resolve",
        "course.get",
        "grounding.ask",
        "session.get_context",
        "session.record_note",
        "source.list",
        "source.search",
    )
    assert {item.version for item in manifests} == {"1.0.0"}
    assert len({item.fingerprint for item in manifests}) == 7


def test_registry_rejects_unknown_fields_and_missing_capability_before_effect() -> None:
    courses = FakeCourses(
        CourseProfile(CourseId("course-1"), "Medicine", "it", learning_goals=("Pass",))
    )
    registry = _registry(courses)
    forged = asyncio.run(
        registry.invoke("course.get", {"course_id": "course-other"}, _context("study:read"))
    )
    denied = asyncio.run(registry.invoke("course.get", {}, _context()))
    unknown = asyncio.run(registry.invoke("source.injected", {}, _context("study:read")))
    assert forged.error is not None and forged.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert denied.error is not None and denied.error.code is ToolErrorCode.UNAUTHORIZED
    assert unknown.error is not None and unknown.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert courses.calls == 0


def test_course_get_is_thin_authorized_and_json_only() -> None:
    courses = FakeCourses(
        CourseProfile(CourseId("course-1"), "Medicine", "it", learning_goals=("Pass",))
    )
    result = asyncio.run(_registry(courses).invoke("course.get", {}, _context("study:read")))
    assert result.error is None
    assert result.value is not None
    profile = cast(Mapping[str, object], result.value["profile"])
    assert profile["id"] == "course-1"
    assert courses.calls == 1


def test_model_principals_receive_no_implicit_capabilities() -> None:
    courses = FakeCourses(
        CourseProfile(CourseId("course-1"), "Medicine", "it", learning_goals=("Pass",))
    )
    registry = _registry(courses)
    denied = asyncio.run(registry.invoke("course.get", {}, _model_context()))
    granted = asyncio.run(registry.invoke("course.get", {}, _model_context("study:read")))
    assert denied.error is not None and denied.error.code is ToolErrorCode.UNAUTHORIZED
    assert granted.error is None
    assert courses.calls == 1
