from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from study_agent.adapters.memory.storage import (
    DeterministicIdFactory,
    FixedClock,
    InMemoryEventStore,
)
from study_agent.api.authority import AuthorityContext, HostAuthority, PrincipalKind
from study_agent.api.capabilities import (
    CancelledCapabilityOutcome,
    CapabilityContinuation,
    CapabilityId,
    CapabilityManifest,
    CapabilityOutcomeStatus,
    CapabilityRequest,
)
from study_agent.api.recall import RecallRating
from study_agent.api.runtime import (
    ArtifactDecisionRequest,
    AssessmentObservationRequest,
    CapabilityResumeRequest,
    CapabilityStartRequest,
    CommitReceipt,
    RecallReviewRequest,
    RuntimeDependencies,
    create_runtime,
)
from study_agent.artifacts.contracts import ArtifactSnapshot
from study_agent.artifacts.service import ArtifactService
from study_agent.assessments.contracts import GradeRecord
from study_agent.assessments.service import AssessmentService
from study_agent.domain._validation import JsonObject
from study_agent.domain.artifact import ArtifactDecision
from study_agent.domain.authority import CancellationOutcome
from study_agent.domain.errors import StaleFailure, ValidationFailure
from study_agent.domain.events import Actor, DomainEvent
from study_agent.domain.identifiers import (
    ArtifactRevisionId,
    CorrelationId,
    CourseId,
    EventId,
    RunId,
    SessionId,
)
from study_agent.kernel.module import KernelModule
from study_agent.playbooks import ReadDependency, ToolBehaviorPin, VersionPins
from study_agent.ports.storage import Repository
from study_agent.recall.contracts import RecallSnapshot
from study_agent.recall.service import RecallService
from study_agent.skills import ArtifactReference, SemanticVersion

SCHEMA = cast(
    JsonObject,
    {
    "type": "object",
    "required": ("topic",),
    "properties": {"topic": {"type": "string"}},
    "additionalProperties": False,
    },
)
COURSE = CourseId("course-1")
SESSION = SessionId("session-1")


@dataclass(frozen=True)
class _Result:
    sequence: int


class _Repository:
    def __init__(self, store: InMemoryEventStore) -> None:
        self.event_store = store
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class _Model:
    capabilities = object()

    async def generate(self, request: object) -> object:
        raise AssertionError("model must not be called")

    def stream(self, request: object) -> object:
        raise AssertionError("model must not be called")

    async def cancel(self, token: object) -> None:
        return None


class _Policy:
    def authorize(self, operation: str, context: object, *, durable: bool) -> None:
        return None


class _Capabilities:
    def __init__(self, manifest: CapabilityManifest) -> None:
        self.manifest = manifest
        self.start_calls: list[tuple[object, object]] = []
        self.resume_calls: list[tuple[object, object, object]] = []

    def discover(self) -> tuple[CapabilityManifest, ...]:
        return (self.manifest,)

    async def start_request(
        self, request: object, context: object, *, cancellation: object = None
    ) -> CancelledCapabilityOutcome:
        self.start_calls.append((request, context))
        return CancelledCapabilityOutcome(RunId("start-run"), "cancelled by test")

    async def resume(
        self,
        continuation: object,
        response: object,
        context: object,
        *,
        cancellation: object = None,
    ) -> CancelledCapabilityOutcome:
        self.resume_calls.append((continuation, response, context))
        return CancelledCapabilityOutcome(RunId("resume-run"), "cancelled by test")


class _Artifact(ArtifactService):
    def __init__(self, store: InMemoryEventStore) -> None:
        self._events = store
        self.calls: list[tuple[object, ...]] = []

    def record_human_decision(
        self,
        revision_id: ArtifactRevisionId,
        decision: ArtifactDecision,
        supersedes_revision_id: ArtifactRevisionId | None,
        context: object,
        expected_sequence: int,
    ) -> ArtifactSnapshot:
        self.calls.append(
            (revision_id, decision, supersedes_revision_id, context, expected_sequence)
        )
        current = cast(InMemoryEventStore, self._events).observe_high_water(
            cast(Any, context).course_id
        ).sequence
        if current > expected_sequence:
            return cast(ArtifactSnapshot, _Result(current))
        return cast(
            ArtifactSnapshot,
            _append_marker(
                cast(InMemoryEventStore, self._events), context, expected_sequence, "test.artifact"
            ),
        )


class _Assessment(AssessmentService):
    def __init__(self, store: InMemoryEventStore) -> None:
        self._events = store
        self.calls: list[tuple[object, ...]] = []

    def record_verified_grade(
        self,
        run_id: RunId,
        context: object,
        expected_sequence: int,
        *,
        supersedes_grade_id: object = None,
    ) -> GradeRecord:
        self.calls.append((run_id, context, expected_sequence, supersedes_grade_id))
        return cast(
            GradeRecord,
            _append_marker(
                cast(InMemoryEventStore, self._events),
                context,
                expected_sequence,
                "test.assessment",
            ),
        )


class _Recall(RecallService):
    def __init__(self, store: InMemoryEventStore) -> None:
        self._events = store
        self.calls: list[tuple[object, ...]] = []

    def review(
        self,
        revision_id: ArtifactRevisionId,
        rating: RecallRating,
        context: object,
        expected_sequence: int,
        *,
        latency_ms: int | None = None,
        confidence_bps: int | None = None,
        policy: object = None,
    ) -> RecallSnapshot:
        self.calls.append(
            (
                revision_id,
                rating,
                context,
                expected_sequence,
                latency_ms,
                confidence_bps,
                policy,
            )
        )
        return cast(
            RecallSnapshot,
            _append_marker(
                cast(InMemoryEventStore, self._events), context, expected_sequence, "test.recall"
            ),
        )


def _append_marker(
    store: InMemoryEventStore, context: object, expected_sequence: int, event_type: str
) -> _Result:
    execution = cast(Any, context)
    sequence = expected_sequence + 1
    event = DomainEvent(
        EventId(f"event-{sequence}"),
        execution.course_id,
        sequence,
        event_type,
        1,
        Actor(execution.principal_kind, execution.principal_id),
        datetime(2026, 1, 1, tzinfo=UTC),
        execution.correlation_id,
        {},
    )
    store.append(execution.course_id, expected_sequence, (event,))
    return _Result(sequence)


def _manifest() -> CapabilityManifest:
    return CapabilityManifest(
        CapabilityId("study.echo"),
        SemanticVersion.parse("1.0.0"),
        SCHEMA,
        SCHEMA,
        ("study:read",),
        True,
        SemanticVersion.parse("1.0.0"),
    )


def _continuation(manifest: CapabilityManifest) -> CapabilityContinuation:
    pins = VersionPins(
        ArtifactReference("study.skill", SemanticVersion.parse("1.0.0")),
        ArtifactReference("study.flow", SemanticVersion.parse("1.0.0")),
        ArtifactReference("study.prompt", SemanticVersion.parse("1.0.0")),
        (ToolBehaviorPin("study.lookup", SemanticVersion.parse("1.0.0")),),
        ArtifactReference("study.model", SemanticVersion.parse("1.0.0")),
        ArtifactReference("study.state", SemanticVersion.parse("1.0.0")),
    )
    return CapabilityContinuation(
        RunId("resume-run"),
        manifest.id,
        manifest.version,
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "e" * 64,
        "clarify",
        1,
        {"topic": "heart"},
        pins,
        (ReadDependency("course", "course-1", "sequence-1"),),
    )


def _composition() -> tuple[
    RuntimeDependencies, tuple[KernelModule, ...], AuthorityContext, dict[str, object]
]:
    store = InMemoryEventStore()
    repository = _Repository(store)
    host = HostAuthority()
    authority = host.issue(
        PrincipalKind.HUMAN,
        "test-user",
        grants=("study:read",),
        correlation_id="corr-1",
        session_id=str(SESSION),
    )
    capabilities = _Capabilities(_manifest())
    artifacts = _Artifact(store)
    assessments = _Assessment(store)
    recall = _Recall(store)
    dependencies = RuntimeDependencies(
        authority.principal,
        cast(Repository, repository),
        store,
        FixedClock(datetime(2026, 1, 1, tzinfo=UTC)),
        DeterministicIdFactory(),
        cast(Any, _Model()),
        _Policy(),
    )
    module = KernelModule(
        "runtime-test",
        "1.0.0",
        services=(
            ("capabilities", capabilities),
            ("artifacts", artifacts),
            ("assessments", assessments),
            ("recall", recall),
        ),
    )
    return (
        dependencies,
        (module,),
        authority,
        {
            "store": store,
            "repository": repository,
            "capabilities": capabilities,
            "artifacts": artifacts,
            "assessments": assessments,
            "recall": recall,
        },
    )


def test_capability_gateway_shape_discovery_start_and_resume_are_closed_outcomes() -> None:
    dependencies, modules, authority, parts = _composition()
    runtime = create_runtime(dependencies, modules)

    async def exercise() -> None:
        manifests = await runtime.discover_capabilities(authority, CorrelationId("corr-1"))
        assert manifests == (_manifest(),)
        start_request = CapabilityStartRequest(
            COURSE,
            SESSION,
            CapabilityRequest(
                manifests[0].identity,
                {"topic": "heart"},
                authority,
                CorrelationId("corr-1"),
                0,
                "cap-start",
            ),
        )
        started = await runtime.start_capability(start_request)
        assert started.status is CapabilityOutcomeStatus.CANCELLED
        assert isinstance(started, CancelledCapabilityOutcome)
        continuation = _continuation(manifests[0])
        resumed = await runtime.resume_capability(
            CapabilityResumeRequest(
                COURSE,
                SESSION,
                continuation,
                {"topic": "heart"},
                authority,
                CorrelationId("corr-1"),
                0,
                "cap-resume",
            )
        )
        assert resumed.status is CapabilityOutcomeStatus.CANCELLED
        assert isinstance(resumed, CancelledCapabilityOutcome)
        assert len(cast(_Capabilities, parts["capabilities"]).start_calls) == 1
        assert len(cast(_Capabilities, parts["capabilities"]).resume_calls) == 1
        await runtime.close()

    asyncio.run(exercise())


def test_durable_service_calls_share_store_and_return_one_event_receipt_each() -> None:
    dependencies, modules, authority, parts = _composition()
    runtime = create_runtime(dependencies, modules)
    revision = ArtifactRevisionId("revision-1")

    async def exercise() -> None:
        artifact = await runtime.record_artifact_decision(
            ArtifactDecisionRequest(
                COURSE,
                SESSION,
                revision,
                ArtifactDecision.ACCEPT,
                None,
                authority,
                CorrelationId("corr-1"),
                0,
                "artifact-1",
            )
        )
        assert isinstance(artifact, CommitReceipt)
        assert artifact.stream_sequence == 1
        assert artifact.replayed is False
        assert len(artifact.event_ids) == 1
        replayed = await runtime.record_artifact_decision(
            ArtifactDecisionRequest(
                COURSE,
                SESSION,
                revision,
                ArtifactDecision.ACCEPT,
                None,
                authority,
                CorrelationId("corr-1"),
                0,
                "artifact-1",
            )
        )
        assert isinstance(replayed, CommitReceipt)
        assert replayed.stream_sequence == 1
        assert replayed.replayed is True
        assert replayed.event_ids == ()

        assessment = await runtime.record_assessment_observation(
            AssessmentObservationRequest(
                COURSE,
                SESSION,
                RunId("run-1"),
                None,
                authority,
                CorrelationId("corr-1"),
                1,
                "assessment-1",
            )
        )
        assert isinstance(assessment, CommitReceipt)
        assert assessment.stream_sequence == 2
        assert len(assessment.event_ids) == 1

        recall = await runtime.review_recall(
            RecallReviewRequest(
                COURSE,
                SESSION,
                revision,
                RecallRating.GOOD,
                authority,
                CorrelationId("corr-1"),
                2,
                "recall-1",
                latency_ms=120,
                confidence_bps=8000,
            )
        )
        assert isinstance(recall, CommitReceipt)
        assert recall.stream_sequence == 3
        assert len(recall.event_ids) == 1

        artifact_call = cast(_Artifact, parts["artifacts"]).calls[0]
        assessment_call = cast(_Assessment, parts["assessments"]).calls[0]
        recall_call = cast(_Recall, parts["recall"]).calls[0]
        assert artifact_call[:3] == (revision, ArtifactDecision.ACCEPT, None)
        assert artifact_call[-1] == 0
        assert assessment_call[0] == RunId("run-1")
        assert assessment_call[2:] == (1, None)
        assert recall_call[:2] == (revision, RecallRating.GOOD)
        assert recall_call[3:] == (2, 120, 8000, None)
        assert cast(_Artifact, parts["artifacts"])._events is parts["store"]
        assert cast(_Assessment, parts["assessments"])._events is parts["store"]
        assert cast(_Recall, parts["recall"])._events is parts["store"]
        await runtime.close()

    asyncio.run(exercise())


def test_stale_and_cancelled_requests_reject_before_the_service_or_gateway_call() -> None:
    dependencies, modules, authority, parts = _composition()
    runtime = create_runtime(dependencies, modules)
    manifest = _manifest()
    request = CapabilityStartRequest(
        COURSE,
        SESSION,
        CapabilityRequest(
            manifest.identity,
            {"topic": "heart"},
            authority,
            CorrelationId("corr-1"),
            1,
            "stale-start",
        ),
    )
    artifact_request = ArtifactDecisionRequest(
        COURSE,
        SESSION,
        ArtifactRevisionId("revision-1"),
        ArtifactDecision.REJECT,
        None,
        authority,
        CorrelationId("corr-1"),
        0,
        "cancelled-artifact",
    )

    async def exercise() -> None:
        with pytest.raises(StaleFailure):
            await runtime.start_capability(request)
        cancelled = await runtime.record_artifact_decision(
            artifact_request, cancellation=lambda: True
        )
        assert cancelled == CancellationOutcome.before_commit(correlation_id="corr-1")
        assert cast(_Capabilities, parts["capabilities"]).start_calls == []
        assert cast(_Artifact, parts["artifacts"]).calls == []
        await runtime.close()

    asyncio.run(exercise())


def test_empty_snapshot_is_canonical_and_close_is_once_with_operations_rejected_afterward() -> None:
    dependencies, modules, authority, parts = _composition()
    runtime = create_runtime(dependencies, modules)

    async def exercise() -> None:
        snapshot = await runtime.read_snapshot(COURSE, authority, CorrelationId("corr-1"))
        assert snapshot.course_id == COURSE
        assert snapshot.stream_sequence == 0
        assert snapshot.state == {}
        assert len(snapshot.fingerprint) == 64
        await asyncio.gather(runtime.close(), runtime.close(), runtime.close())
        assert cast(_Repository, parts["repository"]).close_calls == 1
        with pytest.raises(ValidationFailure, match="runtime is closed"):
            await runtime.discover_capabilities(authority, CorrelationId("corr-1"))

    asyncio.run(exercise())
