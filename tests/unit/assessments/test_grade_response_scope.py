from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace

import pytest

from study_agent.assessments import FreeResponse, response_fingerprint
from study_agent.assessments.grade_scope import (
    GradeEvidence,
    GradeResponseIntegrityValidator,
    GradeResponseReadinessValidator,
    PreparedGradeScope,
    evidence_handle,
    rubric_fingerprint,
    source_commitments_fingerprint,
)
from study_agent.domain import (
    ArtifactRevisionId,
    AttemptId,
    ChunkId,
    Citation,
    CourseId,
    PresentationId,
    ResolvedCitation,
    RevisionId,
    SessionId,
    SourceId,
)
from study_agent.domain._validation import JsonObject, freeze_object
from study_agent.playbooks import ValidationOutcome


class Content:
    def __init__(self, evidence: tuple[GradeEvidence, ...]) -> None:
        self._values = {item.citation: item.text for item in evidence}

    def get_text(self, revision_id: RevisionId) -> str:
        del revision_id
        raise NotImplementedError

    def resolve(self, citation: Citation) -> ResolvedCitation:
        return ResolvedCitation(citation, self._values[citation])


def _scope(rubric: tuple[str, ...] = ("anatomy", "function")) -> PreparedGradeScope:
    texts = ("The valve has three cusps.", "It prevents diastolic backflow.")
    evidence = tuple(
        GradeEvidence(
            evidence_handle(citation),
            citation,
            text,
        )
        for index, text in enumerate(texts)
        for citation in (
            Citation(
                SourceId("source"),
                RevisionId("revision"),
                ChunkId(f"chunk-{index}"),
                0,
                len(text),
                f"section-{index}",
                text,
            ),
        )
    )
    response = "It has three cusps and prevents backflow."
    return PreparedGradeScope(
        CourseId("course"),
        SessionId("session"),
        AttemptId("attempt"),
        PresentationId("presentation"),
        ArtifactRevisionId("artifact-revision"),
        response,
        response_fingerprint(FreeResponse(response)),
        "Three cusps prevent diastolic backflow.",
        rubric,
        rubric_fingerprint(rubric),
        "a" * 64,
        source_commitments_fingerprint(evidence),
        evidence,
        "Italian",
    )


def _criterion(
    criterion: str,
    status: str,
    evidence_id: str | None,
    *,
    insufficient: bool = False,
) -> JsonObject:
    return freeze_object(
        {
            "criterion": criterion,
            "status": status,
            "rationale": "The immutable source supports this judgement.",
            "evidence_ids": () if evidence_id is None else (evidence_id,),
            "confidence": 0.8,
            "evidence_insufficient": insufficient,
        }
    )


def _integrity(scope: PreparedGradeScope, criteria: tuple[JsonObject, ...]) -> ValidationOutcome:
    return asyncio.run(
        GradeResponseIntegrityValidator(Content(scope.evidence)).validate(
            {
                "prepared_grade": {
                    "prepared_scope": scope.to_json(),
                    "prompt_projection": scope.prompt_projection,
                },
                "prepared_scope": scope.to_json(),
                "draft": {"criteria": criteria},
            }
        )
    )


def test_prepared_scope_binds_exact_authority_projection_and_rejects_stale_pins() -> None:
    scope = _scope()

    restored = PreparedGradeScope.from_json(scope.to_json())

    assert restored == scope
    assert set(scope.prompt_projection) == {
        "language",
        "response",
        "expected_response",
        "rubric",
        "evidence",
    }
    assert not {
        "course_id",
        "session_id",
        "attempt_id",
        "presentation_id",
        "revision_id",
        "scope_fingerprint",
    }.intersection(scope.prompt_projection)
    with pytest.raises(ValueError, match="rubric fingerprint is stale"):
        replace(scope, rubric_fingerprint="b" * 64)
    with pytest.raises(ValueError, match="response fingerprint is stale"):
        replace(scope, response_fingerprint="b" * 64)
    with pytest.raises(ValueError, match="source commitments fingerprint is stale"):
        replace(scope, source_commitments_fingerprint="b" * 64)


def test_readiness_rejects_cross_wired_scope_or_projection() -> None:
    scope = _scope()
    wrapper = {
        "prepared_scope": scope.to_json(),
        "prompt_projection": scope.prompt_projection,
    }
    validator = GradeResponseReadinessValidator()
    accepted = asyncio.run(
        validator.validate(
            {
                "prepared_grade": wrapper,
                "prepared_scope": scope.to_json(),
                "prompt_projection": scope.prompt_projection,
            }
        )
    )
    rejected = asyncio.run(
        validator.validate(
            {
                "prepared_grade": wrapper,
                "prepared_scope": scope.to_json(),
                "prompt_projection": {**scope.prompt_projection, "language": "English"},
            }
        )
    )

    assert accepted.passed is True
    assert rejected.passed is False
    assert rejected.reason is not None


def test_integrity_derives_unreduced_score_and_closed_status_union() -> None:
    scope = _scope(("a", "b", "c", "d"))
    first, second = (item.handle for item in scope.evidence)
    graded = _integrity(
        scope,
        (
            _criterion("a", "met", first),
            _criterion("b", "not_met", second),
            _criterion("c", "met", first),
            _criterion("d", "not_met", second),
        ),
    )
    review = _integrity(
        _scope(),
        (
            _criterion("anatomy", "met", first),
            _criterion("function", "uncertain", second),
        ),
    )
    ungradable = _integrity(
        _scope(),
        (
            _criterion("anatomy", "uncertain", None, insufficient=True),
            _criterion("function", "uncertain", None, insufficient=True),
        ),
    )

    assert graded.passed is True
    assert graded.result["status"] == "graded"
    assert graded.result["score"] == {"numerator": 2, "denominator": 4}
    assert review.result["status"] == "needs_review"
    assert ungradable.result["status"] == "ungradable"


@pytest.mark.parametrize(
    "mutate",
    (
        lambda values, _scope: ({**values[0], "criterion": "function"}, values[1]),
        lambda values, _scope: (values[1], values[0]),
        lambda values, _scope: ({**values[0], "evidence_ids": ("unknown",)}, values[1]),
        lambda values, _scope: ({**values[0], "rationale": ""}, values[1]),
        lambda values, _scope: ({**values[0], "evidence_ids": ()}, values[1]),
        lambda values, _scope: ({**values[0], "mastery": 1}, values[1]),
    ),
)
def test_integrity_rejects_rubric_evidence_rationale_and_extra_field_drift(
    mutate: Callable[[tuple[JsonObject, ...], PreparedGradeScope], tuple[JsonObject, ...]],
) -> None:
    scope = _scope()
    values = (
        _criterion("anatomy", "met", scope.evidence[0].handle),
        _criterion("function", "not_met", scope.evidence[1].handle),
    )

    outcome = _integrity(scope, mutate(values, scope))

    assert outcome.passed is False
    assert outcome.reason is not None


def test_integrity_reresolves_every_evidence_handle_before_accepting_rationale() -> None:
    scope = _scope()

    class StaleContent(Content):
        def resolve(self, citation: Citation) -> ResolvedCitation:
            return ResolvedCitation(citation, "changed canonical source")

    outcome = asyncio.run(
        GradeResponseIntegrityValidator(StaleContent(scope.evidence)).validate(
            {
                "prepared_grade": {
                    "prepared_scope": scope.to_json(),
                    "prompt_projection": scope.prompt_projection,
                },
                "prepared_scope": scope.to_json(),
                "draft": {
                    "criteria": (
                        _criterion("anatomy", "met", scope.evidence[0].handle),
                        _criterion("function", "not_met", scope.evidence[1].handle),
                    )
                },
            }
        )
    )

    assert outcome.passed is False
    assert outcome.reason is not None and "canonical content" in outcome.reason
