from __future__ import annotations

from datetime import date

import pytest

from study_agent.domain import StudyStatementInput, StudyStatementKind


@pytest.mark.parametrize(
    ("kind", "supplied", "canonical"),
    (
        (StudyStatementKind.OBJECTIVE, "  pass anatomy  ", "pass anatomy"),
        (StudyStatementKind.ASSESSMENT_FORMAT, "oral", "oral"),
        (StudyStatementKind.TESTING_PREFERENCE, "free recall", "free recall"),
        (StudyStatementKind.DEADLINE, date(2026, 9, 8), date(2026, 9, 8)),
        (StudyStatementKind.WEEKLY_TIME_BUDGET, 420, 420),
    ),
)
def test_statement_values_are_canonicalized_by_closed_kind(
    kind: StudyStatementKind,
    supplied: str | date | int,
    canonical: str | date | int,
) -> None:
    assert StudyStatementInput(kind, supplied).value == canonical


@pytest.mark.parametrize(
    ("kind", "value"),
    (
        (StudyStatementKind.OBJECTIVE, "  "),
        (StudyStatementKind.OBJECTIVE, 3),
        (StudyStatementKind.DEADLINE, "2026-09-08"),
        (StudyStatementKind.WEEKLY_TIME_BUDGET, True),
        (StudyStatementKind.WEEKLY_TIME_BUDGET, 0),
        (StudyStatementKind.WEEKLY_TIME_BUDGET, 10_081),
    ),
)
def test_statement_values_reject_wrong_or_out_of_range_values(
    kind: StudyStatementKind, value: object
) -> None:
    with pytest.raises((TypeError, ValueError)):
        StudyStatementInput(kind, value)  # type: ignore[arg-type]


def test_only_deadline_and_weekly_budget_are_scalar() -> None:
    scalar = {kind for kind in StudyStatementKind if kind.is_scalar}

    assert scalar == {
        StudyStatementKind.DEADLINE,
        StudyStatementKind.WEEKLY_TIME_BUDGET,
    }
