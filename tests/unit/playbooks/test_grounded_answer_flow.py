from study_agent.playbooks import ModelStep, ToolStep, ValidateStep
from study_agent.playbooks.builtin import GROUNDED_ANSWER_FLOW
from study_agent.prompts import GROUNDED_ANSWER_PROMPT


def test_grounded_answer_flow_is_the_canonical_sequential_ast() -> None:
    flow = GROUNDED_ANSWER_FLOW

    assert flow.id == "grounded_answer_flow"
    assert flow.input_keys == ("course_id", "session_id", "question")
    assert [step.id for step in flow.steps] == [
        "load_context",
        "search_sources",
        "check_evidence",
        "generate_answer",
        "validate_answer",
    ]
    assert [type(step) for step in flow.steps] == [
        ToolStep,
        ToolStep,
        ValidateStep,
        ModelStep,
        ValidateStep,
    ]
    model = flow.steps[3]
    assert isinstance(model, ModelStep)
    assert model.prompt == GROUNDED_ANSWER_PROMPT
    assert model.request.structured_output is not None
    assert {binding.target for binding in model.prompt_bindings} == {
        "question",
        "course_profile",
        "continuation_summary",
        "evidence",
    }


def test_final_validator_receives_only_trusted_evidence_and_model_draft() -> None:
    validation = GROUNDED_ANSWER_FLOW.steps[-1]

    assert isinstance(validation, ValidateStep)
    assert validation.validator.id == "grounded_answer_integrity"
    assert validation.input_keys == ("evidence",)
    assert tuple(binding.target for binding in validation.bindings) == ("answer",)
