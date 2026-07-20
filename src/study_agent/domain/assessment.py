"""Closed provider-neutral assessment vocabulary."""

from enum import StrEnum


class GradeStatus(StrEnum):
    GRADED = "graded"
    NEEDS_REVIEW = "needs_review"
    UNGRADABLE = "ungradable"


class CriterionStatus(StrEnum):
    MET = "met"
    NOT_MET = "not_met"
    UNCERTAIN = "uncertain"


class GradeLifecycle(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


__all__ = ["CriterionStatus", "GradeLifecycle", "GradeStatus"]
