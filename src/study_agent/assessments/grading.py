"""Versioned deterministic policy for exact closed-answer grading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from study_agent.artifacts.content import AssessmentItemContent
from study_agent.domain import AssessmentFormat, CriterionStatus
from study_agent.state import canonical_json_bytes

from .contracts import (
    CanonicalResponse,
    CriterionResult,
    MultipleChoiceResponse,
    RationalScore,
    SingleChoiceResponse,
    canonical_multiple_choice,
)

EXACT_CLOSED_POLICY_ID = "exact-closed-answer"
EXACT_CLOSED_POLICY_VERSION = "1.0.0"
_POLICY_MANIFEST = {
    "policy_id": EXACT_CLOSED_POLICY_ID,
    "policy_version": EXACT_CLOSED_POLICY_VERSION,
    "single_choice": "strict_option_text_equality",
    "multiple_choice": "strict_canonical_artifact_order_equality",
    "criterion_rule": "exact_met_proper_subset_uncertain_otherwise_not_met",
    "score_rule": "exact_one_over_one_subset_overlap_over_expected_else_zero",
}
EXACT_CLOSED_POLICY_FINGERPRINT = sha256(canonical_json_bytes(_POLICY_MANIFEST)).hexdigest()


@dataclass(frozen=True, slots=True)
class DeterministicGradeDecision:
    criterion_results: tuple[CriterionResult, ...]
    score: RationalScore
    policy_id: str
    policy_version: str
    policy_fingerprint: str


class ExactClosedGradingPolicy:
    """Compare immutable option values without normalization or inference."""

    def grade(
        self, content: AssessmentItemContent, response: CanonicalResponse
    ) -> DeterministicGradeDecision:
        if content.format is AssessmentFormat.SINGLE_CHOICE:
            if not isinstance(response, SingleChoiceResponse):
                raise ValueError("single-choice grading requires a single-choice response")
            matched = response.selected_option == content.expected_response
            status = CriterionStatus.MET if matched else CriterionStatus.NOT_MET
            score = RationalScore(1 if matched else 0, 1)
        elif content.format is AssessmentFormat.MULTIPLE_CHOICE:
            if not isinstance(response, MultipleChoiceResponse):
                raise ValueError("multiple-choice grading requires a multiple-choice response")
            try:
                expected = json.loads(content.expected_response)
            except json.JSONDecodeError as error:
                raise ValueError(
                    "immutable multiple-choice answer is not canonical JSON"
                ) from error
            if (
                not isinstance(expected, list)
                or not expected
                or any(not isinstance(item, str) for item in expected)
                or len(expected) != len(set(expected))
            ):
                raise ValueError("immutable multiple-choice answer is not a text array")
            expected_options = tuple(expected)
            selected = set(response.selected_options)
            expected_set = set(expected_options)
            overlap = len(selected & expected_set)
            false_positive = bool(selected - expected_set)
            matched = (
                canonical_multiple_choice(response.selected_options)
                == content.expected_response
            )
            if matched:
                status = CriterionStatus.MET
                score = RationalScore(1, 1)
            elif overlap and not false_positive:
                status = CriterionStatus.UNCERTAIN
                score = RationalScore(overlap, len(expected_options))
            else:
                status = CriterionStatus.NOT_MET
                score = RationalScore(0, len(expected_options))
        else:
            raise ValueError("free responses require verified capability grading")

        rationale = {
            CriterionStatus.MET: "Exact response matched the immutable expected answer.",
            CriterionStatus.UNCERTAIN: (
                "Response selected only expected options but omitted at least one expected option."
            ),
            CriterionStatus.NOT_MET: (
                "Response had no expected overlap or selected at least one unexpected option."
            ),
        }[status]
        results = tuple(
            CriterionResult(item, status, rationale)
            for item in content.evaluation_criteria
        )
        return DeterministicGradeDecision(
            results,
            score,
            EXACT_CLOSED_POLICY_ID,
            EXACT_CLOSED_POLICY_VERSION,
            EXACT_CLOSED_POLICY_FINGERPRINT,
        )


__all__ = [
    "EXACT_CLOSED_POLICY_FINGERPRINT",
    "EXACT_CLOSED_POLICY_ID",
    "EXACT_CLOSED_POLICY_VERSION",
    "DeterministicGradeDecision",
    "ExactClosedGradingPolicy",
]
