from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Protocol, cast

import pytest

from study_agent.capabilities import (
    ASSESS_UNDERSTANDING_MANIFEST,
    EXPLAIN_CONCEPT_MANIFEST,
    CapabilityBinding,
    CapabilityDependencyResolver,
    CapabilityManifest,
    assess_understanding_binding,
    builtin_capability_bindings,
    builtin_tutor_validators,
    explain_concept_binding,
)
from study_agent.domain import (
    ChunkId,
    Citation,
    ResolvedCitation,
    RevisionId,
    SourceChunk,
    SourceId,
)
from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.grounding import EvidenceEnvelope
from study_agent.playbooks import (
    DialogueStep,
    ModelStep,
    PlaybookDefinition,
    ToolStep,
    ValidateStep,
    ValidatorDisposition,
    ValidatorExecutor,
)
from study_agent.playbooks.builtin import (
    ASSESS_UNDERSTANDING_FLOW,
    EXPLAIN_CONCEPT_FLOW,
)
from study_agent.portability import reject_provider_selectors
from study_agent.ports import (
    EvidenceStatus,
    RetrievalEvidence,
    RetrievalEvidenceSet,
    retrieval_read_set_fingerprint,
)
from study_agent.prompts import (
    ASSESS_UNDERSTANDING_LAYERS,
    ASSESS_UNDERSTANDING_PROMPT,
    EXPLAIN_CONCEPT_LAYERS,
    EXPLAIN_CONCEPT_PROMPT,
)
from study_agent.skills import (
    ArtifactReference,
    PromptLayer,
    PromptLayerKind,
    SemanticVersion,
    SkillPackage,
)
from study_agent.skills.builtin import (
    ASSESS_UNDERSTANDING_MODEL_SCHEMA,
    ASSESS_UNDERSTANDING_SKILL,
    EXPLAIN_CONCEPT_MODEL_SCHEMA,
    EXPLAIN_CONCEPT_SKILL,
)
from study_agent.tools import public_study_tool_manifests

V1 = SemanticVersion.parse("1.0.0")
MODEL_ADAPTER = ArtifactReference("fixture_model", V1)
STATE_CONTRACT = ArtifactReference("event_state", V1)
EXPLAIN_INPUTS = (
    "query",
    "target",
    "language",
    "learner_goal",
    "continuation_summary_json",
)
ASSESS_INPUTS = (
    "query",
    "scope",
    "assessment_format",
    "question_count",
    "language",
    "continuation_summary_json",
)


class BindingFactory(Protocol):
    def __call__(
        self,
        *,
        dependency_resolver: CapabilityDependencyResolver,
        model_adapter: ArtifactReference,
        state_contract: ArtifactReference,
    ) -> CapabilityBinding: ...


@dataclass(frozen=True, slots=True)
class PackageCase:
    manifest: CapabilityManifest
    skill: SkillPackage
    flow: PlaybookDefinition
    prompt: ArtifactReference
    layers: tuple[PromptLayer, ...]
    model_schema: JsonObject
    factory: BindingFactory
    input_keys: tuple[str, ...]
    output_key: str
    readiness_validator: str
    integrity_validator: str


PACKAGES = (
    PackageCase(
        EXPLAIN_CONCEPT_MANIFEST,
        EXPLAIN_CONCEPT_SKILL,
        EXPLAIN_CONCEPT_FLOW,
        EXPLAIN_CONCEPT_PROMPT,
        EXPLAIN_CONCEPT_LAYERS,
        EXPLAIN_CONCEPT_MODEL_SCHEMA.value,
        explain_concept_binding,
        EXPLAIN_INPUTS,
        "explanation",
        "explain_concept_readiness",
        "explain_concept_integrity",
    ),
    PackageCase(
        ASSESS_UNDERSTANDING_MANIFEST,
        ASSESS_UNDERSTANDING_SKILL,
        ASSESS_UNDERSTANDING_FLOW,
        ASSESS_UNDERSTANDING_PROMPT,
        ASSESS_UNDERSTANDING_LAYERS,
        ASSESS_UNDERSTANDING_MODEL_SCHEMA.value,
        assess_understanding_binding,
        ASSESS_INPUTS,
        "assessment",
        "assess_understanding_readiness",
        "assess_understanding_integrity",
    ),
)


class Content:
    def __init__(self, citation: Citation, text: str) -> None:
        self.citation = citation
        self.text = text

    def get_text(self, revision_id: RevisionId) -> str:
        assert revision_id == self.citation.revision_id
        return self.text

    def resolve(self, citation: Citation) -> ResolvedCitation:
        if citation != self.citation:
            raise ValueError("citation is stale or non-canonical")
        return ResolvedCitation(citation, self.text)


def _evidence(
    status: EvidenceStatus = EvidenceStatus.SUFFICIENT,
) -> tuple[EvidenceEnvelope, Content]:
    text = "The aortic valve has three cusps."
    source = SourceId("source-heart")
    revision = RevisionId("revision-heart")
    chunk = SourceChunk(
        ChunkId("chunk-heart"),
        source,
        revision,
        0,
        len(text),
        (),
        0,
        sha256(text.encode()).hexdigest(),
        "chunker-v1",
    )
    citation = Citation(
        source,
        revision,
        chunk.chunk_id,
        0,
        len(text),
        "Heart > Aortic valve",
        text,
    )
    items = () if status is EvidenceStatus.INSUFFICIENT else (
        RetrievalEvidence(chunk, citation, text, 0.9),
    )
    envelope = EvidenceEnvelope.from_retrieval(
        RetrievalEvidenceSet(
            status,
            items,
            "a" * 64,
            "fixture_lexical",
            "1.0.0",
            "fixture-index-v1",
            retrieval_read_set_fingerprint(items),
        )
    )
    return envelope, Content(citation, text)


def _validators(content: Content) -> dict[str, ValidatorExecutor]:
    return {item.id: item for item in builtin_tutor_validators(content)}


def _resolver(
    *, context: object, inputs: JsonObject
) -> tuple[object, ...]:
    del context, inputs
    return ()


def _manifest_snapshot() -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (item.name, item.version, item.fingerprint)
        for item in public_study_tool_manifests()
    )


@pytest.mark.parametrize("package", PACKAGES, ids=("explain", "assess"))
def test_builtin_package_is_closed_linear_portable_and_binding_complete(
    package: PackageCase,
) -> None:
    before_tools = _manifest_snapshot()
    binding = package.factory(
        dependency_resolver=cast(CapabilityDependencyResolver, _resolver),
        model_adapter=MODEL_ADAPTER,
        state_contract=STATE_CONTRACT,
    )

    assert package.manifest.version == V1
    assert package.manifest.input_schema == package.skill.input_schema.value
    assert package.manifest.output_schema == package.skill.output_schema.value
    assert package.manifest.supports_suspension is True
    assert package.skill.id == package.manifest.id.value
    assert package.skill.playbook == ArtifactReference(package.flow.id, V1)
    assert package.flow.input_keys == package.input_keys
    assert package.manifest.input_schema["required"] == package.input_keys
    properties = cast(Mapping[str, JsonValue], package.manifest.input_schema["properties"])
    assert tuple(properties) == package.input_keys
    assert package.manifest.input_schema["additionalProperties"] is False

    assert tuple(type(step) for step in package.flow.steps) == (
        ToolStep,
        ValidateStep,
        ValidateStep,
        DialogueStep,
        ModelStep,
        ValidateStep,
    )
    assert sum(isinstance(step, ModelStep) for step in package.flow.steps) == 1
    search = package.flow.steps[0]
    dialogue = package.flow.steps[3]
    model = package.flow.steps[4]
    assert isinstance(search, ToolStep)
    assert search.tool == ArtifactReference("source.search", V1)
    assert isinstance(dialogue, DialogueStep) and dialogue.gate is not None
    assert dialogue.gate.default_response == {"provided": False, "text": ""}
    assert isinstance(model, ModelStep)
    assert model.prompt == package.prompt
    assert model.output_schema.value == package.model_schema
    evidence_gate = package.flow.steps[1]
    readiness = package.flow.steps[2]
    integrity = package.flow.steps[-1]
    assert isinstance(evidence_gate, ValidateStep)
    assert isinstance(readiness, ValidateStep)
    assert isinstance(integrity, ValidateStep)
    assert evidence_gate.validator.id == "tutor_evidence_gate"
    assert readiness.validator.id == package.readiness_validator
    assert integrity.validator.id == package.integrity_validator

    assert tuple((item.name, item.behavior_version) for item in package.skill.required_tools) == (
        ("source.search", V1),
    )
    assert package.skill.state_write_policy.allowed_event_types == ()
    assert {item.id for item in package.skill.validators} == {
        "tutor_evidence_gate",
        package.readiness_validator,
        package.integrity_validator,
    }
    assert len(package.skill.fallbacks) == 1
    assert package.skill.fallbacks[0].validator_ids == (package.integrity_validator,)
    assert tuple(item.tool_name for item in binding.pins.tool_behaviors) == (
        "source.search",
    )
    assert binding.manifest is package.manifest
    assert binding.skill is package.skill
    assert binding.playbook is package.flow
    assert binding.pins.prompt == package.prompt
    assert binding.pins.model_adapter == MODEL_ADAPTER
    assert binding.pins.state_contract == STATE_CONTRACT
    assert binding.output_key == package.output_key

    assert tuple(layer.kind for layer in package.layers) == tuple(PromptLayerKind)
    assert package.skill.prompt_layers == package.layers
    assert "untrusted" in package.layers[0].template.lower()
    assert "authority" in package.layers[4].template.lower()
    for portable in (
        package.manifest.input_schema,
        package.manifest.output_schema,
        package.model_schema,
        search.arguments,
    ):
        reject_provider_selectors(portable, "package")
    prompt_text = " ".join(layer.template.lower() for layer in package.layers)
    assert not {"openai", "anthropic", "deepseek"} & set(prompt_text.split())
    assert not hasattr(binding, "tools")
    assert _manifest_snapshot() == before_tools


def test_builtin_binding_factory_returns_exact_pair_without_tool_registration() -> None:
    before = _manifest_snapshot()
    bindings = builtin_capability_bindings(
        explain_dependency_resolver=cast(CapabilityDependencyResolver, _resolver),
        assess_dependency_resolver=cast(CapabilityDependencyResolver, _resolver),
        model_adapter=MODEL_ADAPTER,
        state_contract=STATE_CONTRACT,
    )
    assert tuple(item.manifest for item in bindings) == (
        EXPLAIN_CONCEPT_MANIFEST,
        ASSESS_UNDERSTANDING_MANIFEST,
    )
    assert len({item.manifest.id for item in bindings}) == 2
    assert _manifest_snapshot() == before


def test_builtin_input_envelopes_pin_nullable_fields_and_assessment_count_bounds() -> None:
    explain_properties = cast(
        Mapping[str, JsonValue],
        EXPLAIN_CONCEPT_MANIFEST.input_schema["properties"],
    )
    assess_properties = cast(
        Mapping[str, JsonValue],
        ASSESS_UNDERSTANDING_MANIFEST.input_schema["properties"],
    )
    for field in ("target", "learner_goal", "continuation_summary_json"):
        schema = cast(Mapping[str, JsonValue], explain_properties[field])
        assert schema["type"] == ("string", "null")
    for field in ("scope", "assessment_format", "continuation_summary_json"):
        schema = cast(Mapping[str, JsonValue], assess_properties[field])
        assert schema["type"] == ("string", "null")
    count = cast(Mapping[str, JsonValue], assess_properties["question_count"])
    assert count == {"type": "integer", "minimum": 1, "maximum": 10}


@pytest.mark.parametrize(
    ("status", "passed", "disposition", "can_continue"),
    (
        (EvidenceStatus.SUFFICIENT, True, ValidatorDisposition.CONTINUE, True),
        (EvidenceStatus.INSUFFICIENT, True, ValidatorDisposition.TERMINATE, False),
        (EvidenceStatus.CONFLICTING, True, ValidatorDisposition.TERMINATE, False),
    ),
)
def test_evidence_gate_distinguishes_supported_and_terminal_evidence(
    status: EvidenceStatus,
    passed: bool,
    disposition: ValidatorDisposition,
    can_continue: bool,
) -> None:
    envelope, content = _evidence(status)
    gate = _validators(content)["tutor_evidence_gate"]
    outcome = asyncio.run(gate.validate({"evidence": envelope.to_json()}))
    assert outcome.passed is passed
    assert outcome.disposition is disposition
    assert outcome.result == {
        "evidence_status": status.value,
        "can_continue": can_continue,
    }


@pytest.mark.parametrize(
    "malformed",
    (
        {},
        {"evidence": {"status": "sufficient"}},
        {"evidence": {"provider": "forged"}},
        {"evidence": "not-an-envelope"},
    ),
)
def test_evidence_gate_rejects_malformed_or_selector_shaped_evidence(
    malformed: JsonObject,
) -> None:
    _, content = _evidence()
    outcome = asyncio.run(_validators(content)["tutor_evidence_gate"].validate(malformed))
    assert not outcome.passed
    assert outcome.disposition is ValidatorDisposition.TERMINATE
    assert outcome.result == {
        "status": "failed",
        "code": "capability_validation_failed",
    }


def test_readiness_clarifies_only_missing_target_or_scope_and_defaults_format() -> None:
    _, content = _evidence()
    validators = _validators(content)
    gate: JsonObject = {
        "evidence_status": "sufficient",
        "can_continue": True,
    }
    explain = validators["explain_concept_readiness"]
    missing_target = asyncio.run(
        explain.validate({"evidence_gate": gate, "target": None})
    )
    explicit_target = asyncio.run(
        explain.validate({"evidence_gate": gate, "target": "valve cusps"})
    )
    assert missing_target.result == {"needs_clarification": True}
    assert explicit_target.result == {"needs_clarification": False}

    assess = validators["assess_understanding_readiness"]
    missing_scope = asyncio.run(
        assess.validate(
            {
                "evidence_gate": gate,
                "scope": None,
                "assessment_format": None,
            }
        )
    )
    explicit_scope = asyncio.run(
        assess.validate(
            {
                "evidence_gate": gate,
                "scope": "aortic valve",
                "assessment_format": "multiple_choice",
            }
        )
    )
    assert missing_scope.result == {
        "needs_clarification": True,
        "effective_assessment_format": "free_response",
    }
    assert explicit_scope.result == {
        "needs_clarification": False,
        "effective_assessment_format": "multiple_choice",
    }


def _explanation(handle: str) -> JsonObject:
    return freeze_object(
        {
            "status": "answered",
            "segments": (
                {
                    "kind": "supported_claim",
                    "text": "The aortic valve has three cusps.",
                    "evidence_ids": (handle,),
                },
            ),
            "unsupported_information_note": None,
        }
    )


def test_explanation_integrity_resolves_citations_and_rejects_unknown_or_stale_handles() -> None:
    envelope, content = _evidence()
    handle = envelope.items[0].handle
    validator = _validators(content)["explain_concept_integrity"]
    accepted = asyncio.run(
        validator.validate(
            {"answer": _explanation(handle), "evidence": envelope.to_json()}
        )
    )
    assert accepted.passed
    segments = cast(tuple[JsonValue, ...], accepted.result["segments"])
    segment = cast(Mapping[str, JsonValue], segments[0])
    citations = cast(tuple[JsonValue, ...], segment["citations"])
    citation = cast(Mapping[str, JsonValue], citations[0])
    assert citation["revision_id"] == "revision-heart"
    assert citation["quoted_snippet"] == content.text

    unknown = asyncio.run(
        validator.validate(
            {"answer": _explanation("ev_unknown"), "evidence": envelope.to_json()}
        )
    )
    stale_content = Content(replace(content.citation, locator="changed"), content.text)
    stale = asyncio.run(
        _validators(stale_content)["explain_concept_integrity"].validate(
            {"answer": _explanation(handle), "evidence": envelope.to_json()}
        )
    )
    assert not unknown.passed and not stale.passed
    assert unknown.disposition is stale.disposition is ValidatorDisposition.TERMINATE


def _question(
    handle: str,
    *,
    prompt: str = "How many cusps does the aortic valve have?",
    kind: str = "free_response",
    options: tuple[str, ...] = (),
    extra: tuple[str, JsonValue] | None = None,
) -> JsonObject:
    value: dict[str, JsonValue] = {
        "kind": kind,
        "prompt": prompt,
        "options": options,
        "evidence_ids": (handle,),
    }
    if extra is not None:
        value[extra[0]] = extra[1]
    return value


def _assessment_input(
    envelope: EvidenceEnvelope,
    questions: tuple[JsonObject, ...],
    *,
    count: int | None = None,
) -> JsonObject:
    return {
        "questions": {"questions": questions},
        "question_count": len(questions) if count is None else count,
        "evidence": envelope.to_json(),
    }


def test_assessment_integrity_enforces_count_formats_citations_and_deterministic_ids() -> None:
    envelope, content = _evidence()
    handle = envelope.items[0].handle
    validator = _validators(content)["assess_understanding_integrity"]
    questions = (
        _question(handle),
        _question(
            handle,
            prompt="Which option names an aortic valve cusp?",
            kind="multiple_choice",
            options=("Right coronary", "Papillary muscle"),
        ),
    )
    first = asyncio.run(validator.validate(_assessment_input(envelope, questions)))
    second = asyncio.run(validator.validate(_assessment_input(envelope, questions)))
    assert first.passed and second.passed
    assert first.result == second.result
    resolved = cast(tuple[JsonValue, ...], first.result["questions"])
    assert len(resolved) == 2
    identifiers: list[str] = []
    for item in resolved:
        question = cast(Mapping[str, JsonValue], item)
        assert set(question) == {"id", "kind", "prompt", "options", "citations"}
        identifier = cast(str, question["id"])
        assert identifier.startswith("question-sha256:")
        identifiers.append(identifier)
        citations = cast(tuple[JsonValue, ...], question["citations"])
        citation = cast(Mapping[str, JsonValue], citations[0])
        assert citation["quoted_snippet"] == content.text
    assert len(set(identifiers)) == 2

    wrong_count = asyncio.run(
        validator.validate(_assessment_input(envelope, questions, count=1))
    )
    out_of_bounds = tuple(
        asyncio.run(
            validator.validate(
                _assessment_input(envelope, (_question(handle),), count=count)
            )
        )
        for count in (0, 11)
    )
    invalid_free_response = asyncio.run(
        validator.validate(
            _assessment_input(
                envelope,
                (_question(handle, options=("A", "B")),),
            )
        )
    )
    invalid_multiple_choice = asyncio.run(
        validator.validate(
            _assessment_input(
                envelope,
                (_question(handle, kind="multiple_choice", options=("Only",)),),
            )
        )
    )
    assert not wrong_count.passed
    assert all(not outcome.passed for outcome in out_of_bounds)
    assert not invalid_free_response.passed
    assert not invalid_multiple_choice.passed


def test_assessment_rejects_duplicate_prompts_unknown_handles_and_forbidden_fields() -> None:
    envelope, content = _evidence()
    handle = envelope.items[0].handle
    validator = _validators(content)["assess_understanding_integrity"]
    duplicate = (
        _question(handle, options=()),
        _question(handle, options=()),
    )
    duplicate_outcome = asyncio.run(
        validator.validate(_assessment_input(envelope, duplicate))
    )
    unknown = asyncio.run(
        validator.validate(
            _assessment_input(envelope, (_question("ev_unknown"),))
        )
    )
    assert not duplicate_outcome.passed and not unknown.passed

    forbidden = (
        "answer",
        "rubric",
        "grade",
        "attempt",
        "mastery",
        "schedule",
        "provider",
        "model",
    )
    for field in forbidden:
        outcome = asyncio.run(
            validator.validate(
                _assessment_input(
                    envelope,
                    (_question(handle, extra=(field, "forged")),),
                )
            )
        )
        assert not outcome.passed, field
        assert outcome.disposition is ValidatorDisposition.TERMINATE
