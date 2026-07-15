from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256

from study_agent.domain import Citation
from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.grounding import (
    EvidenceEnvelope,
    GroundedAnswerIntegrityValidator,
    GroundingContractError,
)
from study_agent.playbooks import ValidationOutcome, ValidatorDisposition
from study_agent.ports import EvidenceStatus, SourceContentPort
from study_agent.skills import SemanticVersion

VERSION = SemanticVersion.parse("1.0.0")


class TutorEvidenceGateValidator:
    id = "tutor_evidence_gate"
    version = VERSION

    async def validate(self, inputs: JsonObject) -> ValidationOutcome:
        try:
            if set(inputs) != {"evidence"}:
                raise GroundingContractError("evidence gate requires exactly evidence")
            envelope = EvidenceEnvelope.from_json(inputs["evidence"])
        except (KeyError, GroundingContractError, ValueError) as error:
            return _failure(error)
        result = {
            "evidence_status": envelope.status.value,
            "can_continue": envelope.status is EvidenceStatus.SUFFICIENT,
        }
        if envelope.status is not EvidenceStatus.SUFFICIENT:
            return ValidationOutcome(
                True,
                ValidatorDisposition.TERMINATE,
                result,
                f"retrieval returned {envelope.status.value} evidence",
            )
        return ValidationOutcome(True, ValidatorDisposition.CONTINUE, result)


class ExplainConceptReadinessValidator:
    id = "explain_concept_readiness"
    version = VERSION

    async def validate(self, inputs: JsonObject) -> ValidationOutcome:
        try:
            if set(inputs) != {"evidence_gate", "target"}:
                raise ValueError("explanation readiness requires evidence_gate and target")
            _require_supported_gate(inputs["evidence_gate"])
            target = _nullable_text(inputs["target"], "target")
        except (KeyError, TypeError, ValueError) as error:
            return _failure(error)
        return ValidationOutcome(
            True,
            ValidatorDisposition.CONTINUE,
            {"needs_clarification": target is None},
        )


class AssessUnderstandingReadinessValidator:
    id = "assess_understanding_readiness"
    version = VERSION

    async def validate(self, inputs: JsonObject) -> ValidationOutcome:
        try:
            if set(inputs) != {"assessment_format", "evidence_gate", "scope"}:
                raise ValueError(
                    "assessment readiness requires evidence_gate, scope, and format"
                )
            _require_supported_gate(inputs["evidence_gate"])
            scope = _nullable_text(inputs["scope"], "scope")
            assessment_format = _nullable_text(
                inputs["assessment_format"], "assessment_format"
            )
        except (KeyError, TypeError, ValueError) as error:
            return _failure(error)
        return ValidationOutcome(
            True,
            ValidatorDisposition.CONTINUE,
            {
                "needs_clarification": scope is None,
                "effective_assessment_format": assessment_format or "free_response",
            },
        )


class ExplainConceptIntegrityValidator:
    id = "explain_concept_integrity"
    version = VERSION

    def __init__(self, content: SourceContentPort) -> None:
        self._delegate = GroundedAnswerIntegrityValidator(content)

    async def validate(self, inputs: JsonObject) -> ValidationOutcome:
        outcome = await self._delegate.validate(inputs)
        if set(inputs) == {"output"} or not outcome.passed:
            return outcome
        if outcome.result.get("status") != "answered":
            return _failure(ValueError("explanation must be an answered grounded result"))
        return outcome


class AssessUnderstandingIntegrityValidator:
    id = "assess_understanding_integrity"
    version = VERSION

    def __init__(self, content: SourceContentPort) -> None:
        self._content = content

    async def validate(self, inputs: JsonObject) -> ValidationOutcome:
        try:
            if set(inputs) == {"output"}:
                _parse_questions(inputs["output"])
                return ValidationOutcome(
                    True,
                    ValidatorDisposition.CONTINUE,
                    {"schema_valid": True},
                )
            if set(inputs) != {"evidence", "question_count", "questions"}:
                raise GroundingContractError(
                    "assessment integrity requires questions, count, and evidence"
                )
            count = inputs["question_count"]
            if type(count) is not int or not 1 <= count <= 10:
                raise GroundingContractError("question_count must be an integer from 1 to 10")
            envelope = EvidenceEnvelope.from_json(inputs["evidence"])
            if envelope.status is not EvidenceStatus.SUFFICIENT:
                raise GroundingContractError(
                    "assessment cannot consume insufficient or conflicting evidence"
                )
            questions = _parse_questions(inputs["questions"])
            if len(questions) != count:
                raise GroundingContractError("model question count differs from request")
            result = self._resolve_questions(questions, envelope)
        except (KeyError, GroundingContractError, TypeError, ValueError) as error:
            return _failure(error)
        return ValidationOutcome(True, ValidatorDisposition.CONTINUE, result)

    def _resolve_questions(
        self,
        questions: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...],
        evidence: EvidenceEnvelope,
    ) -> JsonObject:
        trusted = evidence.by_handle()
        resolved_questions: list[JsonObject] = []
        for kind, prompt, options, handles in questions:
            citations: list[JsonObject] = []
            for handle in handles:
                item = trusted.get(handle)
                if item is None:
                    raise GroundingContractError("question references unknown evidence")
                try:
                    resolved = self._content.resolve(item.citation)
                except Exception as error:
                    raise GroundingContractError(
                        "question citation does not resolve to canonical content"
                    ) from error
                if resolved.citation != item.citation or resolved.text != item.text:
                    raise GroundingContractError(
                        "question evidence no longer matches canonical content"
                    )
                citations.append(_citation_json(item.citation))
            resolved_questions.append(
                freeze_object(
                    {
                        "id": _question_id(kind, prompt, options, handles),
                        "kind": kind,
                        "prompt": prompt,
                        "options": options,
                        "citations": tuple(citations),
                    }
                )
            )
        return freeze_object({"questions": tuple(resolved_questions)})


def builtin_tutor_validators(
    content: SourceContentPort,
) -> tuple[
    TutorEvidenceGateValidator,
    ExplainConceptReadinessValidator,
    AssessUnderstandingReadinessValidator,
    ExplainConceptIntegrityValidator,
    AssessUnderstandingIntegrityValidator,
]:
    return (
        TutorEvidenceGateValidator(),
        ExplainConceptReadinessValidator(),
        AssessUnderstandingReadinessValidator(),
        ExplainConceptIntegrityValidator(content),
        AssessUnderstandingIntegrityValidator(content),
    )


def _require_supported_gate(value: JsonValue) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "can_continue",
        "evidence_status",
    }:
        raise ValueError("evidence gate result is malformed")
    if value["can_continue"] is not True or value["evidence_status"] != "sufficient":
        raise ValueError("readiness requires sufficient evidence")


def _nullable_text(value: JsonValue, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be null or non-empty trimmed text")
    return value


def _parse_questions(
    value: JsonValue,
) -> tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...]:
    if not isinstance(value, Mapping) or set(value) != {"questions"}:
        raise GroundingContractError("assessment draft must contain only questions")
    raw_questions = value["questions"]
    if not isinstance(raw_questions, tuple):
        raise GroundingContractError("assessment questions must be an array")
    parsed: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []
    for raw in raw_questions:
        if not isinstance(raw, Mapping) or set(raw) != {
            "evidence_ids",
            "kind",
            "options",
            "prompt",
        }:
            raise GroundingContractError("assessment question has unexpected fields")
        kind = _text(raw["kind"], "question kind")
        prompt = _text(raw["prompt"], "question prompt")
        if kind not in {"free_response", "multiple_choice"}:
            raise GroundingContractError("question kind is unsupported")
        options = _text_array(raw["options"], "question options", allow_empty=True)
        handles = _text_array(raw["evidence_ids"], "question evidence_ids")
        if kind == "free_response" and options:
            raise GroundingContractError("free-response questions cannot have options")
        if kind == "multiple_choice" and len(options) < 2:
            raise GroundingContractError("multiple-choice questions require two options")
        parsed.append((kind, prompt, options, handles))
    prompts = tuple(item[1] for item in parsed)
    if len(set(prompts)) != len(prompts):
        raise GroundingContractError("question prompts must be unique")
    identifiers = tuple(_question_id(*item) for item in parsed)
    if len(set(identifiers)) != len(identifiers):
        raise GroundingContractError("derived question ids must be unique")
    return tuple(parsed)


def _question_id(
    kind: str,
    prompt: str,
    options: tuple[str, ...],
    evidence_ids: tuple[str, ...],
) -> str:
    payload = json.dumps(
        {
            "evidence_ids": evidence_ids,
            "kind": kind,
            "options": options,
            "prompt": prompt,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = sha256(b"study-agent-assessment-question-v1\0" + payload).hexdigest()
    return f"question-sha256:{digest}"


def _text(value: JsonValue, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise GroundingContractError(f"{name} must be non-empty trimmed text")
    return value


def _text_array(
    value: JsonValue,
    name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise GroundingContractError(f"{name} must be an array")
    items = tuple(_text(item, name) for item in value)
    if not allow_empty and not items:
        raise GroundingContractError(f"{name} cannot be empty")
    if len(set(items)) != len(items):
        raise GroundingContractError(f"{name} must be unique")
    return items


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


def _failure(error: Exception) -> ValidationOutcome:
    reason = str(error).strip() or "built-in capability validation failed"
    return ValidationOutcome(
        False,
        ValidatorDisposition.TERMINATE,
        {"status": "failed", "code": "capability_validation_failed"},
        reason,
    )
