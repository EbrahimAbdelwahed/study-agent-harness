"""Provider-neutral runtime DTOs and composition facade.

The public names in this module are deliberately small.  Runtime execution
belongs to ``study_agent.application.runtime``; this module only defines the
portable values and ports an embedding host is allowed to exchange.
"""

from __future__ import annotations

from collections.abc import Mapping as _Mapping
from dataclasses import dataclass as _dataclass
from typing import TYPE_CHECKING as _TYPE_CHECKING
from typing import Protocol as _Protocol

from study_agent.api.artifacts import ArtifactDecision as _ArtifactDecision
from study_agent.api.artifacts import ArtifactRevisionId as _ArtifactRevisionId
from study_agent.api.authority import AuthorityContext as _AuthorityContext
from study_agent.api.authority import Principal as _Principal
from study_agent.api.authority import ValidationFailure as _ValidationFailure
from study_agent.api.capabilities import CapabilityContinuation as _CapabilityContinuation
from study_agent.api.capabilities import CapabilityRequest as _CapabilityRequest
from study_agent.api.recall import RecallRating as _RecallRating
from study_agent.domain._validation import JsonObject as _JsonObject
from study_agent.domain._validation import JsonValue as _JsonValue
from study_agent.domain._validation import freeze_json as _freeze_json
from study_agent.domain._validation import freeze_object as _freeze_object
from study_agent.domain.identifiers import CorrelationId as _CorrelationId
from study_agent.domain.identifiers import CourseId as _CourseId
from study_agent.domain.identifiers import EventId as _EventId
from study_agent.domain.identifiers import GradeId as _GradeId
from study_agent.domain.identifiers import RunId as _RunId
from study_agent.domain.identifiers import SessionId as _SessionId
from study_agent.events.upcasting import EventUpcasterRegistry as _EventUpcasterRegistry
from study_agent.kernel.module import EventSchema as _EventSchema
from study_agent.kernel.module import KernelModule as _KernelModule
from study_agent.kernel.module import KernelModuleRegistry as _KernelModuleRegistry
from study_agent.kernel.module import ModuleRegistry as _ModuleRegistry
from study_agent.ports.clock import Clock as _Clock
from study_agent.ports.id_factory import IdFactory as _IdFactory
from study_agent.ports.model import ModelPort as _ModelPort
from study_agent.ports.storage import EventStore as _EventStore
from study_agent.ports.storage import Repository as _Repository

EventSchema = _EventSchema
EventUpcasterRegistry = _EventUpcasterRegistry
KernelModule = _KernelModule
KernelModuleRegistry = _KernelModuleRegistry
ModuleRegistry = _ModuleRegistry
Registry = _KernelModuleRegistry


class RuntimePolicyPort(_Protocol):
    """Host-supplied authority decision boundary."""

    def authorize(
        self,
        operation: str,
        context: _AuthorityContext,
        *,
        durable: bool,
    ) -> None: ...


def _invalid(message: str) -> _ValidationFailure:
    return _ValidationFailure(message)


def _course(value: object) -> _CourseId:
    if type(value) is not _CourseId:
        raise _invalid("course_id must be a CourseId")
    return value


def _session(value: object) -> _SessionId:
    if type(value) is not _SessionId:
        raise _invalid("session_id must be a SessionId")
    return value


def _correlation(value: object) -> _CorrelationId:
    if type(value) is not _CorrelationId:
        raise _invalid("correlation_id must be a CorrelationId")
    return value


def _high_water(value: object) -> int:
    if type(value) is not int or value < 0:
        raise _invalid("expected_stream_high_water must be a non-negative integer")
    return value


def _key(value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise _invalid("idempotency_key must be non-empty trimmed text")
    return value


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise _invalid(f"{name} must be non-empty trimmed text")
    return value


def _digest(value: object, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _invalid(f"{name} must be a lowercase SHA-256 digest")
    return value


def _authority(value: object) -> _AuthorityContext:
    if type(value) is not _AuthorityContext:
        raise _invalid("authority must be an AuthorityContext")
    return value


@_dataclass(frozen=True, slots=True)
class RuntimeDependencies:
    """The seven explicit host dependencies required by one runtime."""

    principal: _Principal
    repository: _Repository
    storage: _EventStore
    clock: _Clock
    id_factory: _IdFactory
    model_adapter: _ModelPort
    policy: RuntimePolicyPort

    def __post_init__(self) -> None:
        for name in (
            "principal",
            "repository",
            "storage",
            "clock",
            "id_factory",
            "model_adapter",
            "policy",
        ):
            if getattr(self, name) is None:
                raise _invalid(f"{name} is required")


@_dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    course_id: _CourseId
    stream_sequence: int
    state: _JsonObject
    fingerprint: str

    def __post_init__(self) -> None:
        _course(self.course_id)
        _high_water(self.stream_sequence)
        if not isinstance(self.state, _Mapping):
            raise _invalid("snapshot state must be a JSON object")
        try:
            object.__setattr__(self, "state", _freeze_object(self.state))
        except (TypeError, ValueError) as error:
            raise _invalid("snapshot state must contain JSON values") from error
        _digest(self.fingerprint, "snapshot fingerprint")


@_dataclass(frozen=True, slots=True)
class CapabilityStartRequest:
    course_id: _CourseId
    session_id: _SessionId
    capability: _CapabilityRequest

    def __post_init__(self) -> None:
        _course(self.course_id)
        _session(self.session_id)
        if type(self.capability) is not _CapabilityRequest:
            raise _invalid("capability must be a CapabilityRequest")


@_dataclass(frozen=True, slots=True)
class CapabilityResumeRequest:
    course_id: _CourseId
    session_id: _SessionId
    continuation: _CapabilityContinuation
    response: _JsonValue
    authority: _AuthorityContext
    correlation_id: _CorrelationId
    expected_stream_high_water: int
    idempotency_key: str

    def __post_init__(self) -> None:
        _course(self.course_id)
        _session(self.session_id)
        if type(self.continuation) is not _CapabilityContinuation:
            raise _invalid("continuation is invalid")
        try:
            object.__setattr__(self, "response", _freeze_json(self.response))
        except (TypeError, ValueError) as error:
            raise _invalid("response must be a JSON value") from error
        _authority(self.authority)
        _correlation(self.correlation_id)
        _high_water(self.expected_stream_high_water)
        _key(self.idempotency_key)


@_dataclass(frozen=True, slots=True)
class ArtifactDecisionRequest:
    course_id: _CourseId
    session_id: _SessionId
    artifact_revision_id: _ArtifactRevisionId
    decision: _ArtifactDecision | None
    supersedes_revision_id: _ArtifactRevisionId | None
    authority: _AuthorityContext
    correlation_id: _CorrelationId
    expected_stream_high_water: int
    idempotency_key: str

    def __post_init__(self) -> None:
        _course(self.course_id)
        _session(self.session_id)
        if type(self.artifact_revision_id) is not _ArtifactRevisionId:
            raise _invalid("artifact_revision_id is invalid")
        if self.decision is not None and type(self.decision) is not _ArtifactDecision:
            raise _invalid("decision is invalid")
        if self.supersedes_revision_id is not None and type(
            self.supersedes_revision_id
        ) is not _ArtifactRevisionId:
            raise _invalid("supersedes_revision_id is invalid")
        _authority(self.authority)
        _correlation(self.correlation_id)
        _high_water(self.expected_stream_high_water)
        _key(self.idempotency_key)


@_dataclass(frozen=True, slots=True)
class AssessmentObservationRequest:
    course_id: _CourseId
    session_id: _SessionId
    run_id: _RunId
    supersedes_grade_id: _GradeId | None
    authority: _AuthorityContext
    correlation_id: _CorrelationId
    expected_stream_high_water: int
    idempotency_key: str

    def __post_init__(self) -> None:
        _course(self.course_id)
        _session(self.session_id)
        if type(self.run_id) is not _RunId:
            raise _invalid("run_id is invalid")
        if self.supersedes_grade_id is not None and type(self.supersedes_grade_id) is not _GradeId:
            raise _invalid("supersedes_grade_id is invalid")
        _authority(self.authority)
        _correlation(self.correlation_id)
        _high_water(self.expected_stream_high_water)
        _key(self.idempotency_key)


@_dataclass(frozen=True, slots=True)
class RecallReviewRequest:
    course_id: _CourseId
    session_id: _SessionId
    revision_id: _ArtifactRevisionId
    rating: _RecallRating
    authority: _AuthorityContext
    correlation_id: _CorrelationId
    expected_stream_high_water: int
    idempotency_key: str
    latency_ms: int | None = None
    confidence_bps: int | None = None

    def __post_init__(self) -> None:
        _course(self.course_id)
        _session(self.session_id)
        if type(self.revision_id) is not _ArtifactRevisionId:
            raise _invalid("revision_id is invalid")
        if type(self.rating) is not _RecallRating:
            raise _invalid("rating is invalid")
        _authority(self.authority)
        _correlation(self.correlation_id)
        _high_water(self.expected_stream_high_water)
        _key(self.idempotency_key)
        if self.latency_ms is not None and (
            type(self.latency_ms) is not int or self.latency_ms < 0
        ):
            raise _invalid("latency_ms must be a non-negative integer or absent")
        if self.confidence_bps is not None and (
            type(self.confidence_bps) is not int or not 0 <= self.confidence_bps <= 10000
        ):
            raise _invalid("confidence_bps must be between 0 and 10000")


@_dataclass(frozen=True, slots=True)
class CommitReceipt:
    operation: str
    course_id: _CourseId
    stream_sequence: int
    event_ids: tuple[_EventId, ...]
    idempotency_key: str
    replayed: bool
    result: _JsonObject

    def __post_init__(self) -> None:
        _text(self.operation, "operation")
        _course(self.course_id)
        _high_water(self.stream_sequence)
        event_ids = tuple(self.event_ids)
        if not all(type(value) is _EventId for value in event_ids):
            raise _invalid("event_ids are invalid")
        if len(set(event_ids)) != len(event_ids):
            raise _invalid("event_ids must be unique")
        object.__setattr__(self, "event_ids", event_ids)
        _key(self.idempotency_key)
        if type(self.replayed) is not bool:
            raise _invalid("replayed must be boolean")
        if not isinstance(self.result, _Mapping):
            raise _invalid("result must be a JSON object")
        try:
            object.__setattr__(self, "result", _freeze_object(self.result))
        except (TypeError, ValueError) as error:
            raise _invalid("result must contain JSON values") from error


def create_runtime(
    dependencies: RuntimeDependencies,
    modules: tuple[KernelModule, ...] = (),
) -> AsyncStudyAgentRuntime:
    from study_agent.application.runtime import create_runtime as _create_runtime

    return _create_runtime(dependencies, modules)


__all__ = (
    "ArtifactDecisionRequest",
    "AssessmentObservationRequest",
    "AsyncStudyAgentRuntime",
    "CapabilityResumeRequest",
    "CapabilityStartRequest",
    "CommitReceipt",
    "EventSchema",
    "EventUpcasterRegistry",
    "KernelModule",
    "KernelModuleRegistry",
    "ModuleRegistry",
    "RecallReviewRequest",
    "Registry",
    "RuntimeDependencies",
    "RuntimePolicyPort",
    "RuntimeSnapshot",
    "SyncStudyAgentRuntime",
    "create_runtime",
)


if _TYPE_CHECKING:
    from study_agent.application.runtime import (
        AsyncStudyAgentRuntime,
        SyncStudyAgentRuntime,
    )
else:
    from study_agent.application.runtime import AsyncStudyAgentRuntime as _AsyncStudyAgentRuntime
    from study_agent.application.runtime import SyncStudyAgentRuntime as _SyncStudyAgentRuntime

    globals()["AsyncStudyAgentRuntime"] = _AsyncStudyAgentRuntime
    globals()["SyncStudyAgentRuntime"] = _SyncStudyAgentRuntime


def __dir__() -> list[str]:
    return list(__all__)
