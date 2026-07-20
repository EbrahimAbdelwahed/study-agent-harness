from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from typing import cast

import pytest

from study_agent.capabilities import CapabilityContinuation, TutorCapabilityId
from study_agent.domain import RunId
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import (
    PlaybookRunStatus,
    ReadDependency,
    ToolBehaviorPin,
    ValidatorDisposition,
    VerifiedRunRecord,
    VersionPins,
)
from study_agent.skills import ArtifactReference, SemanticVersion
from study_agent.state import canonical_json_bytes
from study_agent.workers import (
    MAX_CONTINUATION_SUMMARY_BYTES,
    MAX_OUTPUT_SCHEMA_BYTES,
    MAX_PAYLOAD_BYTES,
    MAX_TASK_BYTES,
    MAX_VERIFIED_OUTPUT_BYTES,
    ChildCapabilityObservation,
    GenerationWorkerReceipt,
    GenerationWorkerStatus,
    GenerationWorkerTask,
    GenerationWorkerTaskKind,
    ObservedValidationReceipt,
    ValidationExpectation,
    ValidationReceiptSource,
    VerifiedPromptReceipt,
    fingerprint_output_schema,
)
from study_agent.workers.contracts import (
    fingerprint_output,
    fingerprint_run,
    fingerprint_validations,
)

V1 = SemanticVersion.parse("1.0.0")
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SCHEMA: JsonObject = {
    "type": "object",
    "required": ("cards",),
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ("front", "back"),
                "properties": {
                    "front": {"type": "string"},
                    "back": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }
    },
    "additionalProperties": False,
}


def _pins() -> VersionPins:
    return VersionPins(
        ArtifactReference("hybrid_flashcards", V1),
        ArtifactReference("hybrid_flashcards_flow", V1),
        ArtifactReference("hybrid_flashcards.v1", V1),
        (ToolBehaviorPin("source.prepare_flashcard_scope", V1),),
        ArtifactReference("model-adapter", V1),
        ArtifactReference("event-state", V1),
    )


def _expectations() -> tuple[ValidationExpectation, ...]:
    return (
        ValidationExpectation(
            "integrity",
            ValidationReceiptSource.VALIDATE_STEP,
            "hybrid_flashcard_integrity",
            "1.0.0",
        ),
        ValidationExpectation(
            "schema_fallback",
            ValidationReceiptSource.STRUCTURED_OUTPUT_FALLBACK,
            "structured_output_schema",
            "1.0.0",
        ),
    )


def _task(**changes: object) -> GenerationWorkerTask:
    values: dict[str, object] = {
        "task_id": "lesson-1:hybrid",
        "task_kind": GenerationWorkerTaskKind.FLASHCARD_BUNDLE,
        "capability_id": TutorCapabilityId.PROPOSE_FLASHCARDS,
        "capability_version": V1,
        "manifest_fingerprint": SHA_A,
        "required_authority": ("source.read",),
        "pins": _pins(),
        "definition_fingerprint": SHA_B,
        "language": "it",
        "preferences": {"exam_format": "oral"},
        "continuation_summary": {"known": ("aortic valve",)},
        "index_references": ("scope-index:lesson-1",),
        "evidence_references": ("evidence:chunk-1",),
        "payload": {"query": "Generate a parsimonious bundle", "scope": "lesson-1"},
        "output_schema": SCHEMA,
        "output_schema_fingerprint": fingerprint_output_schema(SCHEMA),
        "expected_validations": _expectations(),
    }
    values.update(changes)
    return GenerationWorkerTask(**values)  # type: ignore[arg-type]


def _validations() -> tuple[ObservedValidationReceipt, ...]:
    return tuple(
        ObservedValidationReceipt(
            item.step_id,
            item.source,
            item.validator_id,
            item.validator_version,
            True,
            SHA_C if index == 0 else SHA_D,
        )
        for index, item in enumerate(_expectations())
    )


def _verified_run(*, run_id: str = "child-run-1") -> VerifiedRunRecord:
    task = _task()
    return VerifiedRunRecord(
        RunId(run_id),
        task.definition_fingerprint,
        task.capability_inputs(),
        task.pins,
        (),
        {"proposal": {"cards": ({"front": "Valve?", "back": "Three cusps."},)}},
        (),
        PlaybookRunStatus.COMPLETED,
    )


def _completed_observation() -> ChildCapabilityObservation:
    task = _task()
    return ChildCapabilityObservation(
        GenerationWorkerStatus.COMPLETED,
        task.capability_id,
        task.capability_version,
        task.manifest_fingerprint,
        RunId("child-run-1"),
        task.pins,
        task.definition_fingerprint,
        task.output_schema_fingerprint,
        _validations(),
        VerifiedPromptReceipt(task.pins.prompt.id, str(task.pins.prompt.version), SHA_B, (SHA_C,)),
        verified_run=_verified_run(),
        output={"cards": ({"front": "Valve?", "back": "Three cusps."},)},
    )


def test_task_and_receipt_round_trip_only_canonical_exact_bytes() -> None:
    task = _task()
    assert GenerationWorkerTask.from_bytes(task.to_bytes()) == task
    pretty = task.to_bytes().replace(b'"task_id":', b'"task_id" : ', 1)
    with pytest.raises(ValueError, match="canonical"):
        GenerationWorkerTask.from_bytes(pretty)
    extra = dict(task.to_json())
    extra["provider"] = "forged"
    with pytest.raises(ValueError, match="fields must be exact"):
        GenerationWorkerTask.from_bytes(canonical_json_bytes(extra))

    observation = _completed_observation()
    receipt = GenerationWorkerReceipt(
        task.task_id,
        task.task_kind,
        GenerationWorkerStatus.COMPLETED,
        observation.run_id,
        task.fingerprint,
        task.pins_fingerprint,
        task.payload_fingerprint,
        fingerprint_output(observation.output),
        fingerprint_validations(observation.validations),
        fingerprint_run(observation),
        observation.prompt.composition_fingerprint if observation.prompt else None,
    )
    assert GenerationWorkerReceipt.from_bytes(receipt.to_bytes()) == receipt
    forged = dict(receipt.to_json())
    forged["raw_output"] = {"secret": True}
    with pytest.raises(ValueError, match="fields must be exact"):
        GenerationWorkerReceipt.from_bytes(canonical_json_bytes(forged))


def test_task_pins_all_execution_and_ordered_validation_identity() -> None:
    task = _task()
    assert task.capability_inputs() == task.payload
    assert task.expected_validations == _expectations()
    assert task.pins.skill.id == "hybrid_flashcards"
    assert task.pins.playbook.id == "hybrid_flashcards_flow"
    assert task.pins.prompt.id == "hybrid_flashcards.v1"
    assert task.output_schema_fingerprint == fingerprint_output_schema(task.output_schema)

    with pytest.raises(ValueError, match="output schema fingerprint"):
        _task(output_schema_fingerprint=SHA_D)
    with pytest.raises(ValueError, match="ordered and unique"):
        _task(expected_validations=(_expectations()[0], _expectations()[0]))


@pytest.mark.parametrize(
    "field",
    (
        "api_key",
        "secret",
        "nested_token",
        "principal_id",
        "session_id",
        "provider",
        "model_id",
        "messages",
        "conversation_history",
        "canonical_decision",
        "artifact_revision_id",
        "principalId",
        "sessionId",
        "accessToken",
        "providerName",
        "messageHistory",
        "canonicalDecision",
    ),
)
def test_recursive_structural_secrets_and_ambient_context_are_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="forbidden structural field"):
        _task(payload={"safe": ({"nested": {field: "do not delegate"}},)})


def test_innocent_natural_language_is_not_rejected_by_secret_scanner() -> None:
    task = _task(
        payload={
            "query": "Explain why the word provider appears in this source paragraph.",
            "note": "Never paste an API key or a conversation history here.",
        }
    )
    assert "provider" in task.payload["query"]  # type: ignore[operator]


def test_task_rejects_noncanonical_or_malformed_summaries_and_forged_pins() -> None:
    task = _task()
    raw = task.to_bytes().replace(b'"known":[', b'"known" : [', 1)
    with pytest.raises(ValueError, match="canonical"):
        GenerationWorkerTask.from_bytes(raw)
    forged = dict(task.to_json())
    pins = dict(forged["pins"])  # type: ignore[arg-type]
    prompt = dict(pins["prompt"])  # type: ignore[arg-type]
    prompt["version"] = "forged"
    pins["prompt"] = prompt
    forged["pins"] = pins
    with pytest.raises(ValueError):
        GenerationWorkerTask.from_bytes(canonical_json_bytes(forged))


def _sized_object(maximum: int, key: str = "text") -> dict[str, str]:
    overhead = len(canonical_json_bytes({key: ""}))
    return {key: "x" * (maximum - overhead)}


def test_exact_component_bounds_accept_limit_and_reject_limit_plus_one() -> None:
    assert len(canonical_json_bytes(_sized_object(MAX_PAYLOAD_BYTES))) == MAX_PAYLOAD_BYTES
    _task(payload=_sized_object(MAX_PAYLOAD_BYTES))
    with pytest.raises(ValueError, match="worker payload"):
        _task(payload=_sized_object(MAX_PAYLOAD_BYTES + 1))

    assert (
        len(canonical_json_bytes(_sized_object(MAX_CONTINUATION_SUMMARY_BYTES)))
        == MAX_CONTINUATION_SUMMARY_BYTES
    )
    _task(continuation_summary=_sized_object(MAX_CONTINUATION_SUMMARY_BYTES))
    with pytest.raises(ValueError, match="continuation summary"):
        _task(continuation_summary=_sized_object(MAX_CONTINUATION_SUMMARY_BYTES + 1))


def test_output_schema_verified_output_and_task_have_hard_byte_bounds() -> None:
    schema = {
        "type": "object",
        "required": ("padding",),
        "properties": {
            "padding": {"type": "string", "enum": ("x" * (MAX_OUTPUT_SCHEMA_BYTES - 128),)}
        },
        "additionalProperties": False,
    }
    while len(canonical_json_bytes(cast(JsonObject, schema))) < MAX_OUTPUT_SCHEMA_BYTES:
        schema["properties"]["padding"]["enum"] = (  # type: ignore[index]
            schema["properties"]["padding"]["enum"][0] + "x",  # type: ignore[index]
        )
    while len(canonical_json_bytes(cast(JsonObject, schema))) > MAX_OUTPUT_SCHEMA_BYTES:
        schema["properties"]["padding"]["enum"] = (  # type: ignore[index]
            schema["properties"]["padding"]["enum"][0][:-1],  # type: ignore[index]
        )
    typed_schema = cast(JsonObject, schema)
    _task(
        output_schema=typed_schema,
        output_schema_fingerprint=fingerprint_output_schema(typed_schema),
    )
    too_large_schema = dict(schema)
    too_large_schema["properties"] = {
        "padding": {
            "type": "string",
            "enum": (schema["properties"]["padding"]["enum"][0] + "x",),  # type: ignore[index]
        }
    }
    with pytest.raises(ValueError, match="worker output schema"):
        _task(
            output_schema=cast(JsonObject, too_large_schema),
            output_schema_fingerprint=fingerprint_output_schema(
                cast(JsonObject, too_large_schema)
            ),
        )

    output = "x" * (MAX_VERIFIED_OUTPUT_BYTES - 2)
    task = _task()
    ChildCapabilityObservation(
        GenerationWorkerStatus.COMPLETED,
        task.capability_id,
        task.capability_version,
        task.manifest_fingerprint,
        RunId("large-output"),
        task.pins,
        task.definition_fingerprint,
        task.output_schema_fingerprint,
        _validations(),
        VerifiedPromptReceipt(task.pins.prompt.id, str(task.pins.prompt.version), SHA_A),
        verified_run=_verified_run(run_id="large-output"),
        output=output,
    )
    with pytest.raises(ValueError, match="verified output"):
        ChildCapabilityObservation(
            GenerationWorkerStatus.COMPLETED,
            task.capability_id,
            task.capability_version,
            task.manifest_fingerprint,
            RunId("too-large-output"),
            task.pins,
            task.definition_fingerprint,
            task.output_schema_fingerprint,
            _validations(),
            VerifiedPromptReceipt(task.pins.prompt.id, str(task.pins.prompt.version), SHA_A),
            verified_run=_verified_run(run_id="too-large-output"),
            output=output + "x",
        )

    huge_preferences = {"text": "x" * MAX_TASK_BYTES}
    with pytest.raises(ValueError, match="worker task exceeds"):
        _task(preferences=huge_preferences)


def test_fingerprints_are_domain_separated_and_pin_exact_content() -> None:
    task = _task()
    observation = _completed_observation()
    fingerprints = {
        task.fingerprint,
        task.payload_fingerprint,
        task.pins_fingerprint,
        task.output_schema_fingerprint,
        fingerprint_output(observation.output),
        fingerprint_validations(observation.validations),
        fingerprint_run(observation),
    }
    assert len(fingerprints) == 7
    expected_task = sha256(b"generation-worker-task@1\0" + task.to_bytes()).hexdigest()
    assert task.fingerprint == expected_task
    assert replace(task, language="en").fingerprint != task.fingerprint


def test_observation_shape_prevents_unverified_or_nonterminal_detail() -> None:
    task = _task()
    with pytest.raises(ValueError, match="only completed observations carry verified output"):
        ChildCapabilityObservation(
            GenerationWorkerStatus.FAILED,
            task.capability_id,
            task.capability_version,
            task.manifest_fingerprint,
            RunId("failed"),
            task.pins,
            task.definition_fingerprint,
            task.output_schema_fingerprint,
            output={"cards": ()},
            failure_code="failed",
        )


@pytest.mark.parametrize(
    "failure_code",
    (
        "Provider OpenAI returned the API key",
        "provider_openai_error",
        "credential_rejected",
        "sk-live-secret",
        "UPPERCASE_FAILURE",
    ),
)
def test_failure_codes_reject_free_text_and_sensitive_implementation_metadata(
    failure_code: str,
) -> None:
    task = _task()
    with pytest.raises(ValueError, match="failure_code"):
        ChildCapabilityObservation(
            GenerationWorkerStatus.FAILED,
            task.capability_id,
            task.capability_version,
            task.manifest_fingerprint,
            RunId("failed"),
            task.pins,
            task.definition_fingerprint,
            task.output_schema_fingerprint,
            failure_code=failure_code,
        )


def test_validation_receipt_carries_typed_disposition_in_its_fingerprint() -> None:
    task = _task()
    continued = _validations()[0]
    terminated = replace(continued, disposition=ValidatorDisposition.TERMINATE)
    assert continued.to_json()["disposition"] == "continue"
    assert terminated.to_json()["disposition"] == "terminate"
    assert fingerprint_validations((continued,)) != fingerprint_validations((terminated,))
    with pytest.raises(ValueError, match="prompt and validation provenance"):
        ChildCapabilityObservation(
            GenerationWorkerStatus.COMPLETED,
            task.capability_id,
            task.capability_version,
            task.manifest_fingerprint,
            RunId("completed"),
            task.pins,
            task.definition_fingerprint,
            task.output_schema_fingerprint,
            verified_run=_verified_run(run_id="completed"),
            output={"cards": ()},
        )


def test_continuation_requires_exact_child_identity() -> None:
    task = _task()
    continuation = CapabilityContinuation(
        RunId("child-run-1"),
        task.capability_id,
        task.capability_version,
        task.manifest_fingerprint,
        SHA_A,
        SHA_B,
        task.definition_fingerprint,
        SHA_C,
        "clarify",
        1,
        task.capability_inputs(),
        task.pins,
        (ReadDependency("source", "lesson-1", "revision-1"),),
    )
    observation = ChildCapabilityObservation(
        GenerationWorkerStatus.SUSPENDED,
        task.capability_id,
        task.capability_version,
        task.manifest_fingerprint,
        continuation.run_id,
        task.pins,
        task.definition_fingerprint,
        task.output_schema_fingerprint,
        continuation=continuation,
    )
    assert observation.output is None
    assert observation.verified_run is None
