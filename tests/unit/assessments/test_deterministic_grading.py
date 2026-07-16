from __future__ import annotations

import ast
from pathlib import Path

import pytest

from study_agent.artifacts import AssessmentItemContent
from study_agent.assessments import (
    FreeResponse,
    MultipleChoiceResponse,
    RationalScore,
    SingleChoiceResponse,
)
from study_agent.assessments.grading import (
    EXACT_CLOSED_POLICY_FINGERPRINT,
    EXACT_CLOSED_POLICY_ID,
    EXACT_CLOSED_POLICY_VERSION,
    ExactClosedGradingPolicy,
)
from study_agent.domain import AssessmentFormat, CriterionStatus


def _item(
    format: AssessmentFormat,
    *,
    expected: str,
    criteria: tuple[str, ...] = ("answer",),
) -> AssessmentItemContent:
    options = () if format is AssessmentFormat.FREE_RESPONSE else ("Alpha", "Beta", "Gamma")
    return AssessmentItemContent(format, "Which answer?", options, expected, criteria)


def test_single_choice_is_strict_and_carries_versioned_rubric_score() -> None:
    policy = ExactClosedGradingPolicy()
    item = _item(
        AssessmentFormat.SINGLE_CHOICE,
        expected="Alpha",
        criteria=("selection", "exactness"),
    )

    correct = policy.grade(item, SingleChoiceResponse("Alpha"))
    incorrect = policy.grade(item, SingleChoiceResponse("alpha"))

    assert correct.score == RationalScore(1, 1)
    assert tuple(result.status for result in correct.criterion_results) == (
        CriterionStatus.MET,
        CriterionStatus.MET,
    )
    assert incorrect.score == RationalScore(0, 1)
    assert tuple(result.status for result in incorrect.criterion_results) == (
        CriterionStatus.NOT_MET,
        CriterionStatus.NOT_MET,
    )
    assert (
        correct.policy_id,
        correct.policy_version,
        correct.policy_fingerprint,
    ) == (
        EXACT_CLOSED_POLICY_ID,
        EXACT_CLOSED_POLICY_VERSION,
        EXACT_CLOSED_POLICY_FINGERPRINT,
    )


def test_multiple_choice_pins_exact_partial_and_false_positive_semantics() -> None:
    policy = ExactClosedGradingPolicy()
    item = _item(
        AssessmentFormat.MULTIPLE_CHOICE,
        expected='["Alpha","Gamma"]',
        criteria=("closed answer", "all required options"),
    )

    exact = policy.grade(item, MultipleChoiceResponse(("Alpha", "Gamma")))
    partial = policy.grade(item, MultipleChoiceResponse(("Alpha",)))
    false_positive = policy.grade(item, MultipleChoiceResponse(("Alpha", "Beta")))
    zero_overlap = policy.grade(item, MultipleChoiceResponse(("Beta",)))

    assert exact.score == RationalScore(1, 1)
    assert all(result.status is CriterionStatus.MET for result in exact.criterion_results)
    assert partial.score == RationalScore(1, 2)
    assert all(result.status is CriterionStatus.UNCERTAIN for result in partial.criterion_results)
    for result in (false_positive, zero_overlap):
        assert result.score == RationalScore(0, 2)
        assert all(
            criterion.status is CriterionStatus.NOT_MET
            for criterion in result.criterion_results
        )


@pytest.mark.parametrize(
    ("item", "response"),
    (
        (
            _item(AssessmentFormat.FREE_RESPONSE, expected="Explanation"),
            FreeResponse("Explanation"),
        ),
        (
            _item(AssessmentFormat.SINGLE_CHOICE, expected="Alpha"),
            MultipleChoiceResponse(("Alpha",)),
        ),
        (
            _item(AssessmentFormat.MULTIPLE_CHOICE, expected='["Alpha","Gamma"]'),
            SingleChoiceResponse("Alpha"),
        ),
    ),
)
def test_closed_policy_rejects_free_text_and_cross_format_responses(
    item: AssessmentItemContent,
    response: FreeResponse | SingleChoiceResponse | MultipleChoiceResponse,
) -> None:
    with pytest.raises(ValueError, match=r"free responses|requires"):
        ExactClosedGradingPolicy().grade(item, response)


def test_closed_policy_has_no_model_provider_or_gateway_dependency() -> None:
    path = Path(__file__).parents[3] / "src" / "study_agent" / "assessments" / "grading.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    forbidden = (
        "study_agent.adapters",
        "study_agent.capabilities",
        "study_agent.gateway",
        "study_agent.models",
        "openai",
        "anthropic",
        "deepseek",
    )
    assert {
        imported
        for imported in imports
        if any(imported == prefix or imported.startswith(prefix + ".") for prefix in forbidden)
    } == set()
