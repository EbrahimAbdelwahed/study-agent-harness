from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from study_agent.domain._validation import JsonValue
from study_agent.playbooks import (
    DataReference,
    DataSourceKind,
    DialogueGate,
    DialogueStep,
    ModelStep,
    PlaybookDefinition,
    ToolStep,
    ValidateStep,
)
from study_agent.ports import MessageRole, ModelMessage, ModelRequest
from study_agent.skills import ArtifactReference, JsonSchema, SemanticVersion, VersionRange

V1 = SemanticVersion.parse("1.0.0")
V2 = SemanticVersion.parse("2.0.0")
RESPONSE_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("text",),
        "properties": {"text": {"type": "string"}},
        "additionalProperties": False,
    }
)


def _gate(key: str = "readiness") -> DialogueGate:
    return DialogueGate(
        DataReference(
            DataSourceKind.STEP_OUTPUT,
            key,
            ("result", "needs_clarification"),
        ),
        {"text": "Use the explicit task as provided."},
    )


def _dialogue(gate: DialogueGate) -> DialogueStep:
    return DialogueStep(
        "clarify",
        "Which aspect should we focus on?",
        RESPONSE_SCHEMA,
        "clarification",
        gate,
    )


def test_dialogue_gate_freezes_default_and_rejects_non_step_or_flat_condition() -> None:
    raw_default: dict[str, JsonValue] = {
        "text": "Use the explicit task as provided.",
        "metadata": {"source": "default"},
    }
    gate = DialogueGate(
        DataReference(
            DataSourceKind.STEP_OUTPUT,
            "readiness",
            ("needs_clarification",),
        ),
        raw_default,
    )
    raw_default["text"] = "mutated"
    assert gate.default_response == {
        "text": "Use the explicit task as provided.",
        "metadata": {"source": "default"},
    }
    with pytest.raises(TypeError):
        cast(dict[str, JsonValue], gate.default_response)["text"] = "forged"
    with pytest.raises(FrozenInstanceError):
        gate.default_response = {}  # type: ignore[misc]

    with pytest.raises(ValueError, match="step output"):
        DialogueGate(
            DataReference(DataSourceKind.RUN_INPUT, "topic", ("ready",)),
            {"text": "default"},
        )
    with pytest.raises(ValueError, match="non-empty path"):
        DialogueGate(
            DataReference(DataSourceKind.STEP_OUTPUT, "readiness"),
            {"text": "default"},
        )
    with pytest.raises(ValueError, match="provider/model-specific"):
        DialogueGate(
            DataReference(
                DataSourceKind.STEP_OUTPUT,
                "readiness",
                ("needs_clarification",),
            ),
            {"provider_options": {"reasoning_effort": "high"}},
        )


def test_definition_accepts_only_a_previous_validate_step_nested_condition() -> None:
    seed = ToolStep(
        "seed",
        ArtifactReference("fixture.seed", V1),
        {},
        "seed",
    )
    readiness = ValidateStep(
        "readiness",
        ArtifactReference("fixture.readiness", V1),
        ("seed",),
        "readiness",
    )
    accepted = PlaybookDefinition(
        "optional_dialogue",
        V1,
        VersionRange(V1, V2),
        (seed, readiness, _dialogue(_gate())),
    )
    dialogue = accepted.steps[-1]
    assert isinstance(dialogue, DialogueStep)
    assert dialogue.gate == _gate()

    model = ModelStep(
        "model_readiness",
        ArtifactReference("fixture.prompt", V1),
        ModelRequest((ModelMessage(MessageRole.USER, "Check readiness."),)),
        JsonSchema({"type": "boolean"}),
        "model_readiness",
    )
    invalid_predecessors = (
        (seed, _dialogue(_gate("seed"))),
        (model, _dialogue(_gate("model_readiness"))),
    )
    for steps in invalid_predecessors:
        with pytest.raises(ValueError, match="previous validate step"):
            PlaybookDefinition(
                "invalid_optional_dialogue",
                V1,
                VersionRange(V1, V2),
                steps,
            )

    with pytest.raises(ValueError, match="previous validate step"):
        PlaybookDefinition(
            "forward_optional_dialogue",
            V1,
            VersionRange(V1, V2),
            (_dialogue(_gate("readiness")), seed, readiness),
        )
    with pytest.raises(ValueError, match="previous validate step"):
        PlaybookDefinition(
            "same_step_optional_dialogue",
            V1,
            VersionRange(V1, V2),
            (_dialogue(_gate("clarification")),),
        )
