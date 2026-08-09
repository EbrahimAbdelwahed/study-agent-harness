from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import ANY, Mock

import pytest

from study_agent.courses import CourseCommandError, course_profile_manifest
from study_agent.domain import (
    CorrelationId,
    CourseId,
    CourseProfile,
    ExecutionContext,
    InteractionId,
    PrincipalKind,
    SessionId,
    SessionStatus,
    SourceId,
)
from study_agent.domain._validation import JsonObject
from study_agent.ingestion import IngestionErrorCode, TextIngestionError
from study_agent.ports import StudyTool
from study_agent.ports.storage import EventSequenceConflictError
from study_agent.sessions import SessionCommandError
from study_agent.tools import StudyToolRegistry, ToolErrorCode
from study_agent.tools.builtin import (
    public_agent_operation_manifests,
    public_study_tool_manifests,
)
from study_agent.tools.operations import AgentOperationOwners, expanded_tools

COURSE = CourseId("course-public-tools")
OTHER_COURSE = CourseId("course-other")
SESSION = SessionId("session-public-tools")


def _context(
    course_id: CourseId = COURSE,
    *capabilities: str,
    session_id: SessionId | None = SESSION,
    key: str | None = None,
    principal: PrincipalKind = PrincipalKind.SERVICE,
) -> ExecutionContext:
    return ExecutionContext(
        principal,
        "public-tools-test",
        course_id,
        CorrelationId("public-tools-correlation"),
        frozenset(capabilities),
        session_id,
        idempotency_key=key,
    )


def _profile(course_id: CourseId = COURSE) -> CourseProfile:
    return CourseProfile(course_id, "Public tools", "en", learning_goals=("test",))


def _owners(
    *,
    course_commands: Any = None,
    ingestion: Any = None,
    sessions: Any = None,
    session_turns: Any = None,
    artifacts: Any = None,
    assessments: Any = None,
) -> AgentOperationOwners:
    return AgentOperationOwners(
        course_id=COURSE,
        course_commands=cast(Any, course_commands or SimpleNamespace()),
        ingestion=cast(Any, ingestion or SimpleNamespace()),
        sessions=cast(Any, sessions or SimpleNamespace()),
        session_turns=cast(Any, session_turns or SimpleNamespace()),
        artifacts=cast(Any, artifacts or SimpleNamespace()),
        assessments=cast(Any, assessments or SimpleNamespace()),
    )


def _registry(owners: AgentOperationOwners) -> StudyToolRegistry:
    # Baseline tools are only composed here; all behavior under test is in the
    # typed owner-bound extensions.
    unavailable = cast(Any, object())
    return StudyToolRegistry(
        courses=unavailable,
        catalog=unavailable,
        retrieval=unavailable,
        content=unavailable,
        sessions=unavailable,
        grounding=unavailable,
        owners=owners,
    )


def test_public_inventory_is_exact_sorted_and_legacy_surface_is_unchanged() -> None:
    assert tuple(item.name for item in public_study_tool_manifests()) == (
        "citation.resolve",
        "course.get",
        "grounding.ask",
        "session.get_context",
        "session.record_note",
        "source.list",
        "source.search",
    )

    names = tuple(item.name for item in public_agent_operation_manifests())
    assert names == tuple(sorted(names))
    assert len(names) == len(set(names)) == 16
    assert names == (
        "artifact.proposal_list",
        "assessment.get",
        "citation.resolve",
        "course.create",
        "course.get",
        "grounding.ask",
        "session.end",
        "session.get_context",
        "session.record_learner_turn",
        "session.record_note",
        "session.resume",
        "session.start",
        "session.suspend",
        "source.ingest_text",
        "source.list",
        "source.search",
    )
    assert "recall" not in names


def test_extended_tools_delegate_arguments_and_results_to_canonical_owner_seams() -> None:
    profile = _profile()
    created = Mock(return_value=profile)
    source = SimpleNamespace(source_id=SourceId("source-1"), revision_id="revision-1")
    ingestion_result = SimpleNamespace(
        source=source, status=SimpleNamespace(value="emitted"), committed_sequence=4
    )
    ingest = Mock(return_value=ingestion_result)
    session = SimpleNamespace(id=SESSION, status=SessionStatus.ACTIVE)
    lifecycle = {name: Mock(return_value=session) for name in ("start", "suspend", "resume", "end")}
    interaction = SimpleNamespace(id=InteractionId("interaction-1"), content="hello")
    learner_turn = Mock(return_value=interaction)
    artifact_item = SimpleNamespace(
        id="revision-1",
        artifact_id="artifact-1",
        kind=SimpleNamespace(value="flashcard"),
        status=SimpleNamespace(value="proposed"),
    )
    artifact_get = Mock(return_value=SimpleNamespace(sequence=7, pending=lambda: (artifact_item,)))
    assessment_get = Mock(
        return_value=SimpleNamespace(sequence=8, presentations=(1, 2), attempts=(3,), grades=())
    )
    owners = _owners(
        course_commands=SimpleNamespace(create=created),
        ingestion=SimpleNamespace(ingest=ingest),
        sessions=SimpleNamespace(**lifecycle),
        session_turns=SimpleNamespace(record_learner_turn=learner_turn),
        artifacts=SimpleNamespace(get=artifact_get),
        assessments=SimpleNamespace(get=assessment_get),
    )
    tools = {
        tool.manifest.name: tool
        for tool in cast(tuple[StudyTool, ...], expanded_tools(owners))
    }

    created_result = asyncio.run(
        tools["course.create"].invoke(
            {"profile": course_profile_manifest(profile)},
            _context(COURSE, "study:course_write"),
        )
    )
    assert created_result.error is None
    created.assert_called_once()
    assert created.call_args.args[0] == profile

    ingest_arguments: JsonObject = {
        "filename": "notes.md",
        "content": "canonical text",
        "source_id": "source-1",
        "title": "Notes",
        "trust_level": 90,
        "source_role": "primary",
        "expected_sequence": 3,
    }
    ingest_result_tool = asyncio.run(
        tools["source.ingest_text"].invoke(
            ingest_arguments, _context(COURSE, "study:source_write")
        )
    )
    assert ingest_result_tool.error is None
    ingest.assert_called_once()
    assert ingest.call_args.kwargs["content"] == b"canonical text"
    assert ingest.call_args.kwargs["expected_sequence"] == 3

    for name, method in lifecycle.items():
        result = asyncio.run(
            tools[f"session.{name}"].invoke({}, _context(COURSE, "study:session_write"))
        )
        assert result.error is None
        method.assert_called_once()

    first_turn = asyncio.run(
        tools["session.record_learner_turn"].invoke(
            {"content": "hello", "expected_sequence": 9},
            _context(COURSE, "study:session_write", key="turn-1"),
        )
    )
    retry_turn = asyncio.run(
        tools["session.record_learner_turn"].invoke(
            {"content": "hello", "expected_sequence": 9},
            _context(COURSE, "study:session_write", key="turn-1"),
        )
    )
    assert first_turn == retry_turn
    assert learner_turn.call_count == 2
    learner_turn.assert_called_with("hello", ANY, 9)

    proposals = asyncio.run(
        tools["artifact.proposal_list"].invoke({}, _context(COURSE, "study:read"))
    )
    assessment = asyncio.run(
        tools["assessment.get"].invoke({}, _context(COURSE, "study:read"))
    )
    assert proposals.value == {
        "sequence": 7,
        "total_pending": 1,
        "has_more": False,
        "proposals": (
            {
                "revision_id": "revision-1",
                "artifact_id": "artifact-1",
                "kind": "flashcard",
                "status": "proposed",
            },
        ),
    }
    assert assessment.value == {
        "sequence": 8,
        "presentations": 2,
        "attempts": 1,
        "grades": 0,
    }
    artifact_get.assert_called_with(COURSE)
    assessment_get.assert_called_with(COURSE)


def test_course_binding_rejects_mismatch_before_owner_access() -> None:
    ingest = Mock(side_effect=AssertionError("owner was accessed"))
    registry = _registry(_owners(ingestion=SimpleNamespace(ingest=ingest)))
    result = asyncio.run(
        registry.invoke(
            "source.ingest_text",
            {
                "filename": "notes.md",
                "content": "text",
                "source_id": "source-1",
                "title": "Notes",
                "trust_level": 90,
                "source_role": "primary",
            },
            _context(OTHER_COURSE, "study:source_write"),
        )
    )
    assert result.error is not None
    assert result.error.code is ToolErrorCode.UNAUTHORIZED
    ingest.assert_not_called()


def test_missing_capability_is_rejected_before_owner_effect() -> None:
    ingest = Mock(side_effect=AssertionError("owner was accessed"))
    registry = _registry(_owners(ingestion=SimpleNamespace(ingest=ingest)))
    result = asyncio.run(
        registry.invoke(
            "source.ingest_text",
            {
                "filename": "notes.md",
                "content": "text",
                "source_id": "source-1",
                "title": "Notes",
                "trust_level": 90,
                "source_role": "primary",
            },
            _context(),
        )
    )
    assert result.error is not None
    assert result.error.code is ToolErrorCode.UNAUTHORIZED
    ingest.assert_not_called()


def test_ingestion_schema_enforces_declared_content_bound_before_owner_effect() -> None:
    ingest = Mock(side_effect=AssertionError("owner was accessed"))
    registry = _registry(_owners(ingestion=SimpleNamespace(ingest=ingest)))
    result = asyncio.run(
        registry.invoke(
            "source.ingest_text",
            {
                "filename": "notes.md",
                "content": "x" * 1_000_001,
                "source_id": "source-1",
                "title": "Notes",
                "trust_level": 90,
                "source_role": "primary",
            },
            _context(COURSE, "study:source_write"),
        )
    )
    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS
    ingest.assert_not_called()


@pytest.mark.parametrize(
    ("raised", "expected", "retryable"),
    [
        (
            TextIngestionError(
                IngestionErrorCode.SEQUENCE_CONFLICT,
                "secret sequence",
                retryable=True,
            ),
            ToolErrorCode.RETRYABLE_CONFLICT,
            True,
        ),
        (
            TextIngestionError(IngestionErrorCode.INVALID_UTF8, "secret bytes"),
            ToolErrorCode.INVALID_ARGUMENTS,
            False,
        ),
        (
            TextIngestionError(IngestionErrorCode.INVALID_CONTENT, "secret content"),
            ToolErrorCode.INVALID_ARGUMENTS,
            False,
        ),
        (
            TextIngestionError(
                IngestionErrorCode.UNSUPPORTED_CONFIGURATION,
                "secret config",
            ),
            ToolErrorCode.INCOMPATIBLE_RUNTIME,
            False,
        ),
        (
            TextIngestionError(IngestionErrorCode.BLOB_MISMATCH, "secret blob"),
            ToolErrorCode.INCOMPATIBLE_RUNTIME,
            False,
        ),
    ],
)
def test_ingestion_errors_are_closed_and_do_not_leak_owner_messages(
    raised: TextIngestionError, expected: ToolErrorCode, retryable: bool
) -> None:
    ingest = Mock(side_effect=raised)
    registry = _registry(_owners(ingestion=SimpleNamespace(ingest=ingest)))
    result = asyncio.run(
        registry.invoke(
            "source.ingest_text",
            {
                "filename": "notes.md",
                "content": "text",
                "source_id": "source-1",
                "title": "Notes",
                "trust_level": 90,
                "source_role": "primary",
            },
            _context(COURSE, "study:source_write"),
        )
    )
    assert result.error is not None
    assert result.error.code is expected
    assert result.error.retryable is retryable
    assert "secret" not in result.error.message


def test_raw_event_sequence_conflict_is_retryable_and_message_is_closed() -> None:
    ingest = Mock(side_effect=EventSequenceConflictError(COURSE, 1, 2))
    registry = _registry(_owners(ingestion=SimpleNamespace(ingest=ingest)))
    result = asyncio.run(
        registry.invoke(
            "source.ingest_text",
            {
                "filename": "notes.md",
                "content": "text",
                "source_id": "source-1",
                "title": "Notes",
                "trust_level": 90,
                "source_role": "primary",
            },
            _context(COURSE, "study:source_write"),
        )
    )
    assert result.error is not None
    assert result.error.code is ToolErrorCode.RETRYABLE_CONFLICT
    assert result.error.retryable is True
    assert "expected" not in result.error.message


def test_artifact_proposal_list_bounds_results_and_reports_pending_metadata() -> None:
    items = tuple(
        SimpleNamespace(
            id=f"revision-{index}",
            artifact_id=f"artifact-{index}",
            kind=SimpleNamespace(value="flashcard"),
            status=SimpleNamespace(value="proposed"),
        )
        for index in range(30)
    )
    artifact_get = Mock(return_value=SimpleNamespace(sequence=11, pending=lambda: items))
    registry = _registry(_owners(artifacts=SimpleNamespace(get=artifact_get)))

    default_result = asyncio.run(
        registry.invoke("artifact.proposal_list", {}, _context(COURSE, "study:read"))
    )
    explicit_result = asyncio.run(
        registry.invoke(
            "artifact.proposal_list",
            {"limit": 2},
            _context(COURSE, "study:read"),
        )
    )

    assert default_result.error is None
    assert default_result.value is not None
    assert default_result.value["sequence"] == 11
    assert default_result.value["total_pending"] == 30
    assert default_result.value["has_more"] is True
    assert len(cast(tuple[object, ...], default_result.value["proposals"])) == 24
    assert explicit_result.error is None
    assert explicit_result.value is not None
    assert explicit_result.value["total_pending"] == 30
    assert explicit_result.value["has_more"] is True
    assert len(cast(tuple[object, ...], explicit_result.value["proposals"])) == 2
    assert artifact_get.call_count == 2


@pytest.mark.parametrize(
    ("name", "owner", "arguments", "message"),
    [
        (
            "course.create",
            "course_commands",
            {"profile": course_profile_manifest(_profile())},
            "course creation requires a trusted human or service actor",
        ),
        (
            "session.record_learner_turn",
            "session_turns",
            {"content": "hello", "expected_sequence": 0},
            "session turn command authority is not trusted",
        ),
    ],
)
def test_model_principal_authority_denials_are_unauthorized_and_redacted(
    name: str, owner: str, arguments: JsonObject, message: str
) -> None:
    command = Mock(side_effect=AssertionError("owner must not be called"))
    method = "create" if name == "course.create" else "record_learner_turn"
    owners = _owners(**{owner: SimpleNamespace(**{method: command})})
    registry = _registry(owners)
    context = _context(
        COURSE,
        "study:course_write" if name == "course.create" else "study:session_write",
        key="turn-1" if name != "course.create" else None,
        principal=PrincipalKind.MODEL,
    )

    result = asyncio.run(registry.invoke(name, arguments, context))

    assert result.error is not None
    assert result.error.code is ToolErrorCode.UNAUTHORIZED
    assert message not in result.error.message
    command.assert_not_called()


@pytest.mark.parametrize(
    ("name", "owner", "arguments", "raised"),
    [
        (
            "course.create",
            "course_commands",
            {"profile": course_profile_manifest(_profile())},
            CourseCommandError("state secret"),
        ),
        (
            "session.record_learner_turn",
            "session_turns",
            {"content": "hello", "expected_sequence": 0},
            SessionCommandError("state secret"),
        ),
    ],
)
def test_other_command_errors_remain_invalid_arguments_and_redacted(
    name: str, owner: str, arguments: JsonObject, raised: Exception
) -> None:
    command = Mock(side_effect=raised)
    method = "create" if name == "course.create" else "record_learner_turn"
    owners = _owners(**{owner: SimpleNamespace(**{method: command})})
    registry = _registry(owners)
    result = asyncio.run(
        registry.invoke(
            name,
            arguments,
            _context(
                COURSE,
                "study:course_write" if name == "course.create" else "study:session_write",
                key="turn-1" if name != "course.create" else None,
                principal=PrincipalKind.SERVICE,
            ),
        )
    )

    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert "secret" not in result.error.message


@pytest.mark.parametrize("name", ("artifact.proposal_list", "assessment.get"))
@pytest.mark.parametrize("error_type", (ValueError, TypeError))
def test_projection_errors_are_incompatible_runtime_and_redacted(
    name: str, error_type: type[Exception]
) -> None:
    owner_name = "artifacts" if name == "artifact.proposal_list" else "assessments"
    method_name = "get"
    owner = SimpleNamespace(**{method_name: Mock(side_effect=error_type("projection secret"))})
    registry = _registry(_owners(**{owner_name: owner}))

    result = asyncio.run(registry.invoke(name, {}, _context(COURSE, "study:read")))

    assert result.error is not None
    assert result.error.code is ToolErrorCode.INCOMPATIBLE_RUNTIME
    assert "secret" not in result.error.message
