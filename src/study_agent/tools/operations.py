"""Thin public adapters over the canonical agent-operation owners."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import cast

from study_agent.artifacts.contracts import ArtifactSnapshot
from study_agent.assessments.contracts import AssessmentSnapshot
from study_agent.courses import CourseService, course_profile_manifest
from study_agent.domain import (
    CourseId,
    CourseProfile,
    ExecutionContext,
    SourceId,
    SourcePolicy,
    TerminologyEntry,
    TerminologyPolicy,
)
from study_agent.domain._validation import JsonObject
from study_agent.ingestion import TextIngestionService
from study_agent.ports.artifact import ArtifactViewPort
from study_agent.ports.assessment import AssessmentViewPort
from study_agent.sessions import SessionService, SessionTurnService

from .contracts import IdempotencyMode, ToolEffect, ToolErrorCode, ToolManifest, ToolResult

_ERRORS = tuple(ToolErrorCode)
_TEXT: JsonObject = {"type": "string", "minLength": 1}
_INT: JsonObject = {"type": "integer", "minimum": 0}


def _object(properties: JsonObject, required: tuple[str, ...] = ()) -> JsonObject:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _array(items: JsonObject, *, maximum: int | None = None) -> JsonObject:
    schema: dict[str, object] = {"type": "array", "items": items}
    if maximum is not None:
        schema["maxItems"] = maximum
    return cast(JsonObject, schema)


def _manifest(
    name: str,
    input_schema: JsonObject,
    output_schema: JsonObject,
    *,
    effect: ToolEffect = ToolEffect.READ_ONLY,
    capability: str = "study:read",
    idempotency: IdempotencyMode = IdempotencyMode.NOT_APPLICABLE,
    events: tuple[str, ...] = (),
) -> ToolManifest:
    return ToolManifest(
        name,
        "1.0.0",
        input_schema,
        output_schema,
        effect,
        (capability,),
        events,
        _ERRORS,
        idempotency,
    )


_PROFILE = _object(
    {
        "id": _TEXT,
        "title": _TEXT,
        "language": _TEXT,
        "exam_date": {"type": ("string", "null")},
        "assessment_styles": _array(_TEXT),
        "learning_goals": _array(_TEXT),
        "source_policy": _object(
            {
                "allowed_roles": _array(_TEXT),
                "minimum_trust_level": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            ("allowed_roles", "minimum_trust_level"),
        ),
        "terminology_policy": _object(
            {
                "entries": _array(
                    _object(
                        {"concept": _TEXT, "preferred_term": _TEXT},
                        ("concept", "preferred_term"),
                    )
                )
            },
            ("entries",),
        ),
    },
    (
        "id",
        "title",
        "language",
        "exam_date",
        "assessment_styles",
        "learning_goals",
        "source_policy",
        "terminology_policy",
    ),
)
_SESSION = _object({"session_id": _TEXT, "status": _TEXT}, ("session_id", "status"))
_SESSION_LIFECYCLE = (
    ("start", "started"),
    ("suspend", "suspended"),
    ("resume", "resumed"),
    ("end", "ended"),
)
_SESSION_LIFECYCLE_MANIFESTS = tuple(
    _manifest(
        f"session.{operation}",
        _object({}),
        _SESSION,
        effect=ToolEffect.CANONICAL_WRITE,
        capability="study:session_write",
        events=(f"session.{event}",),
    )
    for operation, event in _SESSION_LIFECYCLE
)


@dataclass(frozen=True, slots=True)
class AgentOperationOwners:
    """Complete owner bundle required to compose the expanded public registry."""

    course_id: CourseId
    course_commands: CourseService
    ingestion: TextIngestionService
    sessions: SessionService
    session_turns: SessionTurnService
    artifacts: ArtifactViewPort
    assessments: AssessmentViewPort


@dataclass(frozen=True, slots=True)
class CourseCreateTool:
    service: CourseService
    manifest = _manifest(
        "course.create",
        _object({"profile": _PROFILE}, ("profile",)),
        _object({"profile": _PROFILE}, ("profile",)),
        effect=ToolEffect.CANONICAL_WRITE,
        capability="study:course_write",
        events=("course.created",),
    )

    async def invoke(self, arguments: JsonObject, context: ExecutionContext) -> ToolResult:
        profile = _profile(cast(JsonObject, arguments["profile"]))
        return ToolResult.success(
            {"profile": course_profile_manifest(self.service.create(profile, context))}
        )


@dataclass(frozen=True, slots=True)
class SourceIngestTextTool:
    service: TextIngestionService
    manifest = _manifest(
        "source.ingest_text",
        _object(
            {
                "filename": _TEXT,
                "content": {"type": "string", "minLength": 1, "maxLength": 1_000_000},
                "source_id": _TEXT,
                "title": _TEXT,
                "trust_level": {"type": "integer", "minimum": 0, "maximum": 100},
                "source_role": _TEXT,
                "expected_sequence": _INT,
            },
            ("filename", "content", "source_id", "title", "trust_level", "source_role"),
        ),
        _object(
            {"source_id": _TEXT, "revision_id": _TEXT, "status": _TEXT, "committed_sequence": _INT},
            ("source_id", "revision_id", "status", "committed_sequence"),
        ),
        effect=ToolEffect.CANONICAL_WRITE,
        capability="study:source_write",
        events=("source.revision_ingested", "source.revision_selected"),
    )

    async def invoke(self, arguments: JsonObject, context: ExecutionContext) -> ToolResult:
        result = self.service.ingest(
            filename=str(arguments["filename"]),
            content=str(arguments["content"]).encode("utf-8"),
            source_id=SourceId(str(arguments["source_id"])),
            title=str(arguments["title"]),
            trust_level=cast(int, arguments["trust_level"]),
            source_role=str(arguments["source_role"]),
            context=context,
            expected_sequence=cast(int | None, arguments.get("expected_sequence")),
        )
        return ToolResult.success(
            {
                "source_id": str(result.source.source_id),
                "revision_id": str(result.source.revision_id),
                "status": result.status.value,
                "committed_sequence": result.committed_sequence,
            }
        )


@dataclass(frozen=True, slots=True)
class SessionLifecycleTool:
    operation: str
    sessions: SessionService
    manifest: ToolManifest

    async def invoke(self, arguments: JsonObject, context: ExecutionContext) -> ToolResult:
        del arguments
        session = getattr(self.sessions, self.operation)(context)
        return ToolResult.success({"session_id": str(session.id), "status": session.status.value})


def session_lifecycle_tools(sessions: SessionService) -> tuple[SessionLifecycleTool, ...]:
    return tuple(
        SessionLifecycleTool(operation, sessions, manifest)
        for (operation, _), manifest in zip(
            _SESSION_LIFECYCLE,
            _SESSION_LIFECYCLE_MANIFESTS,
            strict=True,
        )
    )


@dataclass(frozen=True, slots=True)
class SessionRecordLearnerTurnTool:
    service: SessionTurnService
    manifest = _manifest(
        "session.record_learner_turn",
        _object({"content": _TEXT, "expected_sequence": _INT}, ("content", "expected_sequence")),
        _object({"interaction_id": _TEXT, "content": _TEXT}, ("interaction_id", "content")),
        effect=ToolEffect.CANONICAL_WRITE,
        capability="study:session_write",
        idempotency=IdempotencyMode.REQUIRED,
        events=("session.interaction_recorded",),
    )

    async def invoke(self, arguments: JsonObject, context: ExecutionContext) -> ToolResult:
        record = self.service.record_learner_turn(
            str(arguments["content"]), context, cast(int, arguments["expected_sequence"])
        )
        return ToolResult.success({"interaction_id": str(record.id), "content": record.content})


@dataclass(frozen=True, slots=True)
class ArtifactProposalListTool:
    artifacts: ArtifactViewPort
    manifest = _manifest(
        "artifact.proposal_list",
        _object({"limit": {"type": "integer", "minimum": 1, "maximum": 100}}),
        _object(
            {
                "sequence": _INT,
                "total_pending": _INT,
                "has_more": {"type": "boolean"},
                "proposals": _array(
                    _object(
                        {
                            "revision_id": _TEXT,
                            "artifact_id": _TEXT,
                            "kind": _TEXT,
                            "status": _TEXT,
                        },
                        ("revision_id", "artifact_id", "kind", "status"),
                    ),
                    maximum=100,
                ),
            },
            ("sequence", "total_pending", "has_more", "proposals"),
        ),
    )

    async def invoke(self, arguments: JsonObject, context: ExecutionContext) -> ToolResult:
        limit = cast(int, arguments.get("limit", 24))
        snapshot: ArtifactSnapshot = self.artifacts.get(context.course_id)
        pending = tuple(snapshot.pending())
        return ToolResult.success(
            {
                "sequence": snapshot.sequence,
                "total_pending": len(pending),
                "has_more": len(pending) > limit,
                "proposals": tuple(
                    {
                        "revision_id": str(item.id),
                        "artifact_id": str(item.artifact_id),
                        "kind": item.kind.value,
                        "status": item.status.value,
                    }
                    for item in pending[:limit]
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class AssessmentGetTool:
    assessments: AssessmentViewPort
    manifest = _manifest(
        "assessment.get",
        _object({}),
        _object(
            {"sequence": _INT, "presentations": _INT, "attempts": _INT, "grades": _INT},
            ("sequence", "presentations", "attempts", "grades"),
        ),
    )

    async def invoke(self, arguments: JsonObject, context: ExecutionContext) -> ToolResult:
        del arguments
        snapshot: AssessmentSnapshot = self.assessments.get(context.course_id)
        return ToolResult.success(
            {
                "sequence": snapshot.sequence,
                "presentations": len(snapshot.presentations),
                "attempts": len(snapshot.attempts),
                "grades": len(snapshot.grades),
            }
        )


def expanded_tools(owners: AgentOperationOwners) -> tuple[object, ...]:
    return (
        CourseCreateTool(owners.course_commands),
        SourceIngestTextTool(owners.ingestion),
        *session_lifecycle_tools(owners.sessions),
        SessionRecordLearnerTurnTool(owners.session_turns),
        ArtifactProposalListTool(owners.artifacts),
        AssessmentGetTool(owners.assessments),
    )


def public_operation_manifests() -> tuple[ToolManifest, ...]:
    """Return the nine extended manifests without composing a repository."""
    return (
        CourseCreateTool.manifest,
        SourceIngestTextTool.manifest,
        *_SESSION_LIFECYCLE_MANIFESTS,
        SessionRecordLearnerTurnTool.manifest,
        ArtifactProposalListTool.manifest,
        AssessmentGetTool.manifest,
    )


def _profile(value: JsonObject) -> CourseProfile:
    source = cast(JsonObject, value["source_policy"])
    terminology = cast(JsonObject, value["terminology_policy"])
    raw_date = value["exam_date"]
    exam_date = None if raw_date is None else date.fromisoformat(str(raw_date))
    return CourseProfile(
        CourseId(str(value["id"])),
        str(value["title"]),
        str(value["language"]),
        exam_date,
        tuple(str(item) for item in cast(tuple[object, ...], value["assessment_styles"])),
        tuple(str(item) for item in cast(tuple[object, ...], value["learning_goals"])),
        SourcePolicy(
            tuple(str(item) for item in cast(tuple[object, ...], source["allowed_roles"])),
            cast(int, source["minimum_trust_level"]),
        ),
        TerminologyPolicy(
            tuple(
                TerminologyEntry(
                    str(cast(JsonObject, item)["concept"]),
                    str(cast(JsonObject, item)["preferred_term"]),
                )
                for item in cast(tuple[object, ...], terminology["entries"])
            )
        ),
    )


__all__ = ["AgentOperationOwners", "expanded_tools", "public_operation_manifests"]
