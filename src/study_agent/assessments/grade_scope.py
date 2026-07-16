"""Request-bound contracts and validators for free-response grading."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from study_agent.domain import (
    ArtifactRevisionId,
    AttemptId,
    Citation,
    CourseId,
    PresentationId,
    SessionId,
)
from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.grounding import GroundingContractError
from study_agent.playbooks import ValidationOutcome, ValidatorDisposition
from study_agent.ports import SourceContentPort
from study_agent.skills import SemanticVersion
from study_agent.state import canonical_json_bytes

from .contracts import FreeResponse, response_fingerprint

VERSION = SemanticVersion.parse("1.0.0")
_MAX_TEXT = 4096
_MAX_CRITERIA = 64
_MAX_EVIDENCE = 64


@dataclass(frozen=True, slots=True)
class GradeEvidence:
    handle: str
    citation: Citation
    text: str

    def __post_init__(self) -> None:
        _text(self.handle, "evidence handle", 128)
        _text(self.text, "evidence text", _MAX_TEXT)
        if not isinstance(self.citation, Citation):
            raise TypeError("grade evidence citation must be Citation")
        if self.citation.quoted_snippet != self.text:
            raise ValueError("grade evidence quote must equal its immutable text")

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "evidence_id": self.handle,
                "text": self.text,
                "citation": _citation_json(self.citation),
            }
        )

    def to_prompt_json(self) -> JsonObject:
        return freeze_object({"evidence_id": self.handle, "text": self.text})


@dataclass(frozen=True, slots=True)
class PreparedGradeScope:
    course_id: CourseId
    session_id: SessionId
    attempt_id: AttemptId
    presentation_id: PresentationId
    revision_id: ArtifactRevisionId
    response: str
    response_fingerprint: str
    expected_response: str
    rubric: tuple[str, ...]
    rubric_fingerprint: str
    artifact_content_fingerprint: str
    source_commitments_fingerprint: str
    evidence: tuple[GradeEvidence, ...]
    language: str

    def __post_init__(self) -> None:
        for value, cls, name in (
            (self.course_id, CourseId, "course_id"),
            (self.session_id, SessionId, "session_id"),
            (self.attempt_id, AttemptId, "attempt_id"),
            (self.presentation_id, PresentationId, "presentation_id"),
            (self.revision_id, ArtifactRevisionId, "revision_id"),
        ):
            if not isinstance(value, cls):
                raise TypeError(f"prepared grade {name} has the wrong type")
        _text(self.response, "learner response", _MAX_TEXT)
        _text(self.expected_response, "expected response", _MAX_TEXT)
        _text(self.language, "language", 64)
        rubric = tuple(self.rubric)
        if not 1 <= len(rubric) <= _MAX_CRITERIA or len(set(rubric)) != len(rubric):
            raise ValueError("grade rubric must be bounded, ordered, and unique")
        for criterion in rubric:
            _text(criterion, "rubric criterion", 1024)
        evidence = tuple(self.evidence)
        if not 1 <= len(evidence) <= _MAX_EVIDENCE:
            raise ValueError("grade evidence must be non-empty and bounded")
        handles = tuple(item.handle for item in evidence)
        if len(set(handles)) != len(handles):
            raise ValueError("grade evidence handles must be unique")
        for fingerprint, name in (
            (self.response_fingerprint, "response_fingerprint"),
            (self.rubric_fingerprint, "rubric_fingerprint"),
            (self.artifact_content_fingerprint, "artifact_content_fingerprint"),
            (self.source_commitments_fingerprint, "source_commitments_fingerprint"),
        ):
            _fingerprint(fingerprint, name)
        if self.rubric_fingerprint != _rubric_fingerprint(rubric):
            raise ValueError("prepared grade rubric fingerprint is stale")
        if self.response_fingerprint != response_fingerprint(FreeResponse(self.response)):
            raise ValueError("prepared grade response fingerprint is stale")
        if self.source_commitments_fingerprint != source_commitments_fingerprint(evidence):
            raise ValueError("prepared grade source commitments fingerprint is stale")
        object.__setattr__(self, "rubric", rubric)
        object.__setattr__(self, "evidence", evidence)

    @property
    def scope_fingerprint(self) -> str:
        return sha256(
            b"study-agent-prepared-grade-scope-v1\0"
            + canonical_json_bytes(self._json(include_scope_fingerprint=False))
        ).hexdigest()

    @property
    def prompt_projection(self) -> JsonObject:
        return freeze_object(
            {
                "language": self.language,
                "response": self.response,
                "expected_response": self.expected_response,
                "rubric": self.rubric,
                "evidence": tuple(item.to_prompt_json() for item in self.evidence),
            }
        )

    def to_json(self) -> JsonObject:
        return self._json(include_scope_fingerprint=True)

    def _json(self, *, include_scope_fingerprint: bool) -> JsonObject:
        value: dict[str, JsonValue] = {
            "course_id": str(self.course_id),
            "session_id": str(self.session_id),
            "attempt_id": str(self.attempt_id),
            "presentation_id": str(self.presentation_id),
            "revision_id": str(self.revision_id),
            "response": self.response,
            "response_fingerprint": self.response_fingerprint,
            "expected_response": self.expected_response,
            "rubric": self.rubric,
            "rubric_fingerprint": self.rubric_fingerprint,
            "artifact_content_fingerprint": self.artifact_content_fingerprint,
            "source_commitments_fingerprint": self.source_commitments_fingerprint,
            "evidence": tuple(item.to_json() for item in self.evidence),
            "language": self.language,
        }
        if include_scope_fingerprint:
            value["scope_fingerprint"] = self.scope_fingerprint
        return freeze_object(value)

    @classmethod
    def from_json(cls, raw: JsonValue) -> PreparedGradeScope:
        value = _object(
            raw,
            {
                "course_id",
                "session_id",
                "attempt_id",
                "presentation_id",
                "revision_id",
                "response",
                "response_fingerprint",
                "expected_response",
                "rubric",
                "rubric_fingerprint",
                "artifact_content_fingerprint",
                "source_commitments_fingerprint",
                "evidence",
                "language",
                "scope_fingerprint",
            },
            "prepared grade scope",
        )
        scope = cls(
            CourseId(_string(value, "course_id")),
            SessionId(_string(value, "session_id")),
            AttemptId(_string(value, "attempt_id")),
            PresentationId(_string(value, "presentation_id")),
            ArtifactRevisionId(_string(value, "revision_id")),
            _string(value, "response"),
            _string(value, "response_fingerprint"),
            _string(value, "expected_response"),
            _strings(value, "rubric"),
            _string(value, "rubric_fingerprint"),
            _string(value, "artifact_content_fingerprint"),
            _string(value, "source_commitments_fingerprint"),
            _evidence(value.get("evidence")),
            _string(value, "language"),
        )
        if _string(value, "scope_fingerprint") != scope.scope_fingerprint:
            raise ValueError("prepared grade scope fingerprint is stale")
        return scope


class GradeResponseReadinessValidator:
    id = "grade_response_readiness"
    version = VERSION

    async def validate(self, inputs: JsonObject) -> ValidationOutcome:
        try:
            if set(inputs) != {"prepared_grade", "prepared_scope", "prompt_projection"}:
                raise ValueError("grade readiness inputs are not exact")
            prepared = inputs["prepared_grade"]
            if not isinstance(prepared, Mapping) or set(prepared) != {
                "prepared_scope",
                "prompt_projection",
            }:
                raise ValueError("prepared grade wrapper is malformed")
            scope = PreparedGradeScope.from_json(inputs["prepared_scope"])
            if prepared["prepared_scope"] != inputs["prepared_scope"]:
                raise ValueError("prepared grade wrapper contains another trusted scope")
            if prepared["prompt_projection"] != inputs["prompt_projection"]:
                raise ValueError("prepared grade wrapper contains another prompt projection")
            if inputs["prompt_projection"] != scope.prompt_projection:
                raise ValueError("grade prompt projection differs from its trusted scope")
        except (GroundingContractError, KeyError, TypeError, ValueError) as error:
            return _failure(error)
        return ValidationOutcome(
            True,
            ValidatorDisposition.CONTINUE,
            {"ready": True, "scope_fingerprint": scope.scope_fingerprint},
        )


class GradeResponseIntegrityValidator:
    id = "grade_response_integrity"
    version = VERSION

    def __init__(self, content: SourceContentPort) -> None:
        self._content = content

    async def validate(self, inputs: JsonObject) -> ValidationOutcome:
        try:
            if set(inputs) == {"output"}:
                _draft(inputs["output"])
                return ValidationOutcome(
                    True, ValidatorDisposition.CONTINUE, {"schema_valid": True}
                )
            if set(inputs) != {"prepared_grade", "prepared_scope", "draft"}:
                raise GroundingContractError("grade integrity inputs are not exact")
            scope = PreparedGradeScope.from_json(inputs["prepared_scope"])
            prepared = inputs["prepared_grade"]
            if (
                not isinstance(prepared, Mapping)
                or prepared.get("prepared_scope") != scope.to_json()
            ):
                raise GroundingContractError("grade scope wrapper changed before integrity")
            criteria = _draft(inputs["draft"])
            if tuple(item["criterion"] for item in criteria) != scope.rubric:
                raise GroundingContractError(
                    "grade criteria must match the immutable rubric exactly and in order"
                )
            self._resolve_evidence(scope, criteria)
            result = _final_grade(criteria)
        except (GroundingContractError, KeyError, TypeError, ValueError) as error:
            return _failure(error)
        return ValidationOutcome(True, ValidatorDisposition.CONTINUE, result)

    def _resolve_evidence(
        self, scope: PreparedGradeScope, criteria: tuple[JsonObject, ...]
    ) -> None:
        evidence = {item.handle: item for item in scope.evidence}
        for criterion in criteria:
            handles = criterion["evidence_ids"]
            if not isinstance(handles, tuple):  # guarded by _draft
                raise GroundingContractError("criterion evidence must be an array")
            for handle in handles:
                item = evidence.get(str(handle))
                if item is None:
                    raise GroundingContractError("criterion references unknown evidence")
                try:
                    resolved = self._content.resolve(item.citation)
                except Exception as error:
                    raise GroundingContractError(
                        "grade evidence no longer resolves to canonical content"
                    ) from error
                if resolved.citation != item.citation or resolved.text != item.text:
                    raise GroundingContractError(
                        "grade evidence differs from its immutable source text"
                    )


def _draft(raw: JsonValue) -> tuple[JsonObject, ...]:
    root = _object(raw, {"criteria"}, "grade draft")
    values = root["criteria"]
    if not isinstance(values, tuple) or not 1 <= len(values) <= _MAX_CRITERIA:
        raise GroundingContractError("grade criteria must be a bounded array")
    parsed: list[JsonObject] = []
    for raw_item in values:
        item = _object(
            raw_item,
            {
                "criterion",
                "status",
                "rationale",
                "evidence_ids",
                "confidence",
                "evidence_insufficient",
            },
            "criterion proposal",
        )
        criterion = _string(item, "criterion")
        _text(criterion, "criterion", 1024)
        status = _string(item, "status")
        if status not in {"met", "not_met", "uncertain"}:
            raise GroundingContractError("criterion status is unsupported")
        rationale = _string(item, "rationale")
        _text(rationale, "criterion rationale", 2048)
        handles = _strings(item, "evidence_ids", allow_empty=True)
        if len(handles) > 32 or len(set(handles)) != len(handles):
            raise GroundingContractError("criterion evidence must be bounded and unique")
        confidence = item["confidence"]
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            raise GroundingContractError("criterion confidence must be between zero and one")
        insufficient = item["evidence_insufficient"]
        if not isinstance(insufficient, bool):
            raise GroundingContractError("evidence_insufficient must be boolean")
        if insufficient and (status != "uncertain" or handles):
            raise GroundingContractError(
                "evidence insufficiency requires uncertain status and no evidence handles"
            )
        if not insufficient and not handles:
            raise GroundingContractError(
                "determinate or reviewable criteria require supporting evidence"
            )
        parsed.append(freeze_object(dict(item)))
    return tuple(parsed)


def _final_grade(criteria: tuple[JsonObject, ...]) -> JsonObject:
    all_insufficient = all(item["evidence_insufficient"] is True for item in criteria)
    if all_insufficient:
        status = "ungradable"
    elif any(item["status"] == "uncertain" for item in criteria):
        status = "needs_review"
    else:
        status = "graded"
    numerator = sum(item["status"] == "met" for item in criteria)
    return freeze_object(
        {
            "status": status,
            "criteria": criteria,
            "score": {"numerator": numerator, "denominator": len(criteria)},
        }
    )


def evidence_handle(citation: Citation) -> str:
    payload = canonical_json_bytes(_citation_json(citation))
    return f"grade-ev-sha256:{sha256(b'grade-evidence-v1\0' + payload).hexdigest()}"


def source_commitments_fingerprint(values: tuple[GradeEvidence, ...]) -> str:
    return sha256(
        b"grade-source-commitments-v1\0"
        + canonical_json_bytes(
            {"commitments": tuple(_citation_json(item.citation) for item in values)}
        )
    ).hexdigest()


def rubric_fingerprint(rubric: tuple[str, ...]) -> str:
    return _rubric_fingerprint(rubric)


def _rubric_fingerprint(rubric: tuple[str, ...]) -> str:
    return sha256(canonical_json_bytes({"evaluation_criteria": rubric})).hexdigest()


def _evidence(raw: JsonValue | None) -> tuple[GradeEvidence, ...]:
    if not isinstance(raw, tuple):
        raise ValueError("grade evidence must be an array")
    result: list[GradeEvidence] = []
    for raw_item in raw:
        item = _object(raw_item, {"evidence_id", "text", "citation"}, "grade evidence")
        citation_raw = _object(
            item["citation"],
            {
                "source_id",
                "revision_id",
                "chunk_id",
                "start_offset",
                "end_offset",
                "locator",
                "quoted_snippet",
            },
            "grade evidence citation",
        )
        from study_agent.domain import ChunkId, RevisionId, SourceId

        citation = Citation(
            SourceId(_string(citation_raw, "source_id")),
            RevisionId(_string(citation_raw, "revision_id")),
            ChunkId(_string(citation_raw, "chunk_id")),
            _integer(citation_raw, "start_offset"),
            _integer(citation_raw, "end_offset"),
            _string(citation_raw, "locator"),
            _string(citation_raw, "quoted_snippet"),
        )
        result.append(
            GradeEvidence(
                _string(item, "evidence_id"), citation, _string(item, "text")
            )
        )
    return tuple(result)


def _citation_json(citation: Citation) -> JsonObject:
    return freeze_object(
        {
            "source_id": str(citation.source_id),
            "revision_id": str(citation.revision_id),
            "chunk_id": str(citation.chunk_id),
            "start_offset": citation.start_offset,
            "end_offset": citation.end_offset,
            "locator": citation.locator,
            "quoted_snippet": citation.quoted_snippet,
        }
    )


def _object(raw: JsonValue, fields: set[str], name: str) -> Mapping[str, JsonValue]:
    if not isinstance(raw, Mapping) or set(raw) != fields:
        raise GroundingContractError(f"{name} fields are not exact")
    return raw


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    raw = value[key]
    if not isinstance(raw, str):
        raise GroundingContractError(f"{key} must be text")
    return raw


def _strings(
    value: Mapping[str, JsonValue], key: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    raw = value[key]
    if not isinstance(raw, tuple) or (not allow_empty and not raw):
        raise GroundingContractError(f"{key} must be a non-empty array")
    if any(not isinstance(item, str) for item in raw):
        raise GroundingContractError(f"{key} entries must be text")
    return tuple(item for item in raw if isinstance(item, str))


def _integer(value: Mapping[str, JsonValue], key: str) -> int:
    raw = value[key]
    if type(raw) is not int:
        raise GroundingContractError(f"{key} must be an integer")
    return raw


def _text(value: str, name: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be non-empty trimmed text within {maximum} characters")


def _fingerprint(value: str, name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 fingerprint")


def _failure(error: Exception) -> ValidationOutcome:
    return ValidationOutcome(
        False,
        ValidatorDisposition.TERMINATE,
        {"error": str(error)},
        str(error),
    )


__all__ = [
    "VERSION",
    "GradeEvidence",
    "GradeResponseIntegrityValidator",
    "GradeResponseReadinessValidator",
    "PreparedGradeScope",
    "evidence_handle",
    "rubric_fingerprint",
    "source_commitments_fingerprint",
]
