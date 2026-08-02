"""Closed, capability-enforcing registry for the seven public v0.1 tools."""

from __future__ import annotations

from typing import cast

from study_agent.application.grounding_ask import (
    GroundingAskError,
    GroundingAskErrorCode,
    GroundingAskService,
)
from study_agent.courses import (
    CourseCommandError,
    CourseConflictError,
    RetryableCourseConflictError,
)
from study_agent.domain import ExecutionContext, PrincipalKind
from study_agent.domain._validation import JsonObject
from study_agent.ingestion import TextIngestionError
from study_agent.ports import (
    CourseNotFoundError,
    CourseViewPort,
    RetrievalPort,
    SourceContentPort,
    StudyTool,
)
from study_agent.ports.retrieval import RetrievalCatalogPort
from study_agent.ports.storage import EventSequenceConflictError
from study_agent.retrieval import SourceContentError
from study_agent.sessions import (
    IdempotencyConflictError,
    RetryableSessionConflictError,
    SessionCommandError,
    SessionService,
)

from .builtin import GroundingAskServiceProvider, builtin_tools
from .contracts import IdempotencyMode, ToolError, ToolErrorCode, ToolManifest, ToolResult
from .operations import AgentOperationOwners
from .schema import SchemaValidationError, validate_json, validate_schema_definition


class StudyToolRegistry:
    """A closed composition-root registry; callers cannot register generated tools."""

    def __init__(
        self,
        *,
        courses: CourseViewPort,
        catalog: RetrievalCatalogPort,
        retrieval: RetrievalPort,
        content: SourceContentPort,
        sessions: SessionService,
        grounding: GroundingAskService | GroundingAskServiceProvider,
        owners: AgentOperationOwners | None = None,
    ) -> None:
        tools = cast(
            tuple[StudyTool, ...],
            builtin_tools(
                courses=courses,
                catalog=catalog,
                retrieval=retrieval,
                content=content,
                sessions=sessions,
                grounding=grounding,
                owners=owners,
            ),
        )
        self._tools = {tool.manifest.name: tool for tool in tools}
        expected = 7 if owners is None else 16
        if len(tools) != expected or len(self._tools) != expected:
            if owners is None:
                raise RuntimeError(
                    "the public v0.1 registry must contain exactly seven unique tools"
                )
            raise RuntimeError("the public registry must contain the complete closed inventory")
        self._course_id = None if owners is None else owners.course_id
        for tool in tools:
            validate_schema_definition(tool.manifest.input_schema)
            validate_schema_definition(tool.manifest.output_schema)

    @property
    def manifests(self) -> tuple[ToolManifest, ...]:
        return tuple(self._tools[name].manifest for name in sorted(self._tools))

    async def invoke(
        self, name: str, arguments: JsonObject, context: ExecutionContext
    ) -> ToolResult:
        if self._course_id is not None and context.course_id != self._course_id:
            return _failure(ToolErrorCode.UNAUTHORIZED, "tool context course is not authorized")
        tool = self._tools.get(name)
        if tool is None:
            return _failure(ToolErrorCode.INVALID_ARGUMENTS, "unknown study tool")
        manifest = tool.manifest
        try:
            validate_json(arguments, manifest.input_schema)
        except (SchemaValidationError, ValueError, TypeError):
            return _failure(ToolErrorCode.INVALID_ARGUMENTS, "tool arguments are invalid")
        if not set(manifest.required_capabilities) <= context.requested_capabilities:
            return _failure(ToolErrorCode.UNAUTHORIZED, "required capability was not granted")
        if not isinstance(context.principal_kind, PrincipalKind):
            return _failure(ToolErrorCode.UNAUTHORIZED, "tool context principal is not trusted")
        if (
            name in {"course.create", "session.record_learner_turn"}
            and context.principal_kind is PrincipalKind.MODEL
        ):
            return _failure(ToolErrorCode.UNAUTHORIZED, "tool principal is not authorized")
        if manifest.idempotency is IdempotencyMode.REQUIRED and context.idempotency_key is None:
            return _failure(ToolErrorCode.INVALID_ARGUMENTS, "tool invocation requires idempotency")
        try:
            result = await tool.invoke(arguments, context)
            if result.error is not None:
                if result.error.code not in manifest.error_codes:
                    return _failure(
                        ToolErrorCode.INCOMPATIBLE_RUNTIME, "tool returned an undeclared error"
                    )
                return result
            assert result.value is not None
            try:
                validate_json(result.value, manifest.output_schema)
            except (SchemaValidationError, ValueError, TypeError):
                return _failure(
                    ToolErrorCode.INCOMPATIBLE_RUNTIME,
                    "tool output violated its declared contract",
                )
            declared = set(manifest.emitted_event_kinds)
            if any(event.kind.value not in declared for event in result.events):
                return _failure(
                    ToolErrorCode.INCOMPATIBLE_RUNTIME, "tool emitted an undeclared event"
                )
            return result
        except GroundingAskError as error:
            return _grounding_error(error)
        except (CourseNotFoundError, LookupError):
            return _failure(ToolErrorCode.NOT_FOUND, "requested study state was not found")
        except SourceContentError as error:
            if error.code.value == "not_found":
                return _failure(ToolErrorCode.NOT_FOUND, "requested source state was not found")
            return _failure(ToolErrorCode.CONFLICT, "canonical source state could not be verified")
        except (IdempotencyConflictError, CourseConflictError):
            return _failure(ToolErrorCode.CONFLICT, "request conflicts with canonical state")
        except (RetryableSessionConflictError, RetryableCourseConflictError):
            return _failure(
                ToolErrorCode.RETRYABLE_CONFLICT,
                "canonical state advanced; retry safely",
                retryable=True,
            )
        except TextIngestionError as error:
            return _ingestion_error(error)
        except EventSequenceConflictError:
            return _failure(
                ToolErrorCode.RETRYABLE_CONFLICT,
                "canonical state advanced; retry safely",
                retryable=True,
            )
        except SessionCommandError:
            return _failure(ToolErrorCode.INVALID_ARGUMENTS, "request violates the study contract")
        except CourseCommandError:
            return _failure(ToolErrorCode.INVALID_ARGUMENTS, "request violates the study contract")
        except (ValueError, TypeError):
            if name in {"artifact.proposal_list", "assessment.get"}:
                return _failure(
                    ToolErrorCode.INCOMPATIBLE_RUNTIME,
                    "canonical projection runtime is incompatible",
                )
            return _failure(ToolErrorCode.INVALID_ARGUMENTS, "request violates the study contract")
        except Exception:
            return _failure(ToolErrorCode.EXECUTION_FAILED, "study tool execution failed safely")


def _failure(code: ToolErrorCode, message: str, *, retryable: bool = False) -> ToolResult:
    return ToolResult.failure(ToolError(code, message, retryable))


def _grounding_error(error: GroundingAskError) -> ToolResult:
    code = {
        GroundingAskErrorCode.INVALID_REQUEST: ToolErrorCode.INVALID_ARGUMENTS,
        GroundingAskErrorCode.UNAUTHORIZED: ToolErrorCode.UNAUTHORIZED,
        GroundingAskErrorCode.NOT_FOUND: ToolErrorCode.NOT_FOUND,
        GroundingAskErrorCode.CONFLICT: ToolErrorCode.CONFLICT,
        GroundingAskErrorCode.RETRYABLE_CONFLICT: ToolErrorCode.RETRYABLE_CONFLICT,
        GroundingAskErrorCode.RUNNING: ToolErrorCode.CONFLICT,
        GroundingAskErrorCode.SUSPENDED: ToolErrorCode.CONFLICT,
        GroundingAskErrorCode.FAILED: ToolErrorCode.EXECUTION_FAILED,
        GroundingAskErrorCode.INCOMPATIBLE_RUNTIME: ToolErrorCode.INCOMPATIBLE_RUNTIME,
        GroundingAskErrorCode.EXECUTION_FAILED: ToolErrorCode.EXECUTION_FAILED,
    }[error.code]
    return _failure(
        code,
        "grounded question could not be completed",
        retryable=code is ToolErrorCode.RETRYABLE_CONFLICT,
    )


def _ingestion_error(error: TextIngestionError) -> ToolResult:
    if error.retryable or error.code.value == "sequence_conflict":
        return _failure(
            ToolErrorCode.RETRYABLE_CONFLICT,
            "canonical state advanced; retry safely",
            retryable=True,
        )
    if error.code.value in {
        "unsupported_extension",
        "invalid_utf8",
        "invalid_content",
    }:
        return _failure(ToolErrorCode.INVALID_ARGUMENTS, "request violates the study contract")
    if error.code.value in {"blob_mismatch", "unsupported_configuration"}:
        return _failure(
            ToolErrorCode.INCOMPATIBLE_RUNTIME,
            "canonical ingestion runtime is incompatible",
        )
    return _failure(ToolErrorCode.EXECUTION_FAILED, "study tool execution failed safely")
