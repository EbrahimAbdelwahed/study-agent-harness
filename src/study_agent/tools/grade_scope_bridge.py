"""Trusted request-bound bridge from assessment state to a grading prompt scope."""

from __future__ import annotations

from hashlib import sha256

from study_agent.artifacts.content import AssessmentItemContent
from study_agent.assessments.contracts import FreeResponse
from study_agent.assessments.grade_scope import (
    GradeEvidence,
    PreparedGradeScope,
    evidence_handle,
    rubric_fingerprint,
    source_commitments_fingerprint,
)
from study_agent.domain import (
    ArtifactRevisionStatus,
    AssessmentFormat,
    AttemptId,
    Citation,
    ExecutionContext,
    StudyArtifactKind,
)
from study_agent.domain._validation import JsonObject
from study_agent.ports import ArtifactViewPort, AssessmentViewPort, SourceContentPort
from study_agent.skills import SemanticVersion

VERSION = SemanticVersion.parse("1.0.0")


class BoundGradeScopeExecutor:
    name = "assessment.prepare_grade_scope@1"
    behavior_version = VERSION

    def __init__(
        self,
        *,
        attempt_id: AttemptId,
        language: str,
        context: ExecutionContext,
        assessments: AssessmentViewPort,
        artifacts: ArtifactViewPort,
        content: SourceContentPort,
    ) -> None:
        if not isinstance(attempt_id, AttemptId):
            raise TypeError("grade scope attempt_id must be AttemptId")
        if not language or language != language.strip() or len(language) > 64:
            raise ValueError("grade scope language must be bounded trimmed text")
        if context.session_id is None or "course:read" not in context.requested_capabilities:
            raise ValueError("grade scope requires a session-bound course:read context")
        self._attempt_id = attempt_id
        self._language = language
        self._context = context
        self._assessments = assessments
        self._artifacts = artifacts
        self._content = content

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        if arguments != {
            "attempt_id": str(self._attempt_id),
            "language": self._language,
        }:
            raise ValueError("grade scope arguments differ from the trusted request")
        scope = self._prepare()
        return {
            "prepared_scope": scope.to_json(),
            "prompt_projection": scope.prompt_projection,
        }

    def _prepare(self) -> PreparedGradeScope:
        snapshot = self._assessments.get(self._context.course_id)
        attempt = snapshot.attempt(self._attempt_id)
        presentation = snapshot.presentation(attempt.presentation_id)
        if (
            attempt.course_id != self._context.course_id
            or presentation.course_id != self._context.course_id
            or attempt.session_id != self._context.session_id
            or presentation.session_id != self._context.session_id
        ):
            raise ValueError("grade target belongs to another course or session")
        if not isinstance(attempt.response, FreeResponse):
            raise ValueError("grade_response accepts only a committed free response")
        if presentation.content.format is not AssessmentFormat.FREE_RESPONSE:
            raise ValueError("grade target is not a free-response presentation")

        artifact_snapshot = self._artifacts.get(self._context.course_id)
        revision = artifact_snapshot.revision(presentation.revision_id)
        batch = next(
            (item for item in artifact_snapshot.batches if item.id == revision.batch_id),
            None,
        )
        if (
            revision.status is not ArtifactRevisionStatus.ACCEPTED
            or revision.kind is not StudyArtifactKind.ASSESSMENT_ITEM
            or batch is None
            or batch.session_id != self._context.session_id
            or not isinstance(revision.content.content, AssessmentItemContent)
        ):
            raise ValueError("grade target is not the accepted session-owned assessment item")
        content_bytes = revision.content.to_bytes()
        if (
            revision.content.content != presentation.content
            or sha256(content_bytes).hexdigest() != presentation.content_fingerprint
        ):
            raise ValueError("presented assessment content is stale")

        evidence = tuple(
            self._resolve(commitment)
            for commitment in revision.provenance.source_commitments
        )
        return PreparedGradeScope(
            self._context.course_id,
            self._context.session_id,
            attempt.id,
            presentation.id,
            revision.id,
            attempt.response.text,
            attempt.response_fingerprint,
            revision.content.content.expected_response,
            revision.content.content.evaluation_criteria,
            rubric_fingerprint(revision.content.content.evaluation_criteria),
            presentation.content_fingerprint,
            source_commitments_fingerprint(evidence),
            evidence,
            self._language,
        )

    def _resolve(self, commitment: object) -> GradeEvidence:
        from study_agent.domain import SourceCommitment

        if not isinstance(commitment, SourceCommitment):
            raise TypeError("artifact source commitment is invalid")
        requested = Citation(
            commitment.source_id,
            commitment.revision_id,
            commitment.chunk_id,
            commitment.start_offset,
            commitment.end_offset,
            "bound grade evidence",
        )
        resolved = self._content.resolve(requested)
        citation = resolved.citation
        expected = (
            commitment.source_id,
            commitment.revision_id,
            commitment.chunk_id,
            commitment.start_offset,
            commitment.end_offset,
        )
        actual = (
            citation.source_id,
            citation.revision_id,
            citation.chunk_id,
            citation.start_offset,
            citation.end_offset,
        )
        if actual != expected or citation.quoted_snippet != resolved.text:
            raise ValueError("artifact source commitment did not resolve exactly")
        return GradeEvidence(evidence_handle(citation), citation, resolved.text)


__all__ = ["VERSION", "BoundGradeScopeExecutor"]
