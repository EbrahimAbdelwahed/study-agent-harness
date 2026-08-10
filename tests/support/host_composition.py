"""Canonical deep host composition for integration and contract tests."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import cast

from study_agent.adapters.filesystem import FilesystemBlobStore
from study_agent.adapters.model import ScriptedExchange, ScriptedModel
from study_agent.adapters.sqlite import SQLiteEventStore, SQLiteFtsRetrieval
from study_agent.application import (
    GroundingAskConfiguration,
    GroundingAskService,
    StudyHarness,
)
from study_agent.courses import course_profile_manifest, register_course_events
from study_agent.domain import (
    CorrelationId,
    CourseId,
    ExecutionContext,
    PrincipalKind,
    RunId,
    SessionId,
    SourceId,
)
from study_agent.domain._validation import JsonObject
from study_agent.grounding import (
    EvidenceEnvelope,
    EvidenceSufficiencyValidator,
    GroundedAnswerIntegrityValidator,
)
from study_agent.ingestion import TextIngestionService, register_source_revision_events
from study_agent.playbooks import (
    CancelledRunResult,
    EngineErrorCode,
    EngineFailure,
    ModelStep,
    PlaybookEngine,
    PromptComposerRegistration,
    ReadDependency,
    RuntimeRegistries,
    ToolBehaviorPin,
    ToolExecutor,
    VersionPins,
)
from study_agent.playbooks.builtin import GROUNDED_ANSWER_FLOW
from study_agent.ports import (
    CourseViewPort,
    IndexReceipt,
    ModelCapabilities,
    ModelFinishReason,
    ModelInvocation,
    ModelResponse,
    RetrievalPort,
)
from study_agent.ports.retrieval import RetrievalDocument, RetrievalEvidenceSet, RetrievalQuery
from study_agent.prompts import GROUNDED_ANSWER_PROMPT, CanonicalPromptComposer
from study_agent.retrieval import CourseSourceContent
from study_agent.sessions import (
    GroundedSessionFinalizer,
    ProjectionSessionView,
    RetryableSessionConflictError,
    SessionService,
    register_session_events,
)
from study_agent.skills import ArtifactReference, SemanticVersion
from study_agent.skills.builtin import GROUNDED_ANSWER_SKILL
from study_agent.state import EventRegistry
from study_agent.tools.registry import StudyToolRegistry
from tests.course_fixtures import canonical_profile, create_canonical_course

V1 = SemanticVersion.parse("1.0.0")
COURSE = CourseId("course-grounding-ask")
SESSION = SessionId("session-grounding-ask")


@dataclass(frozen=True, slots=True)
class SupportedAnswer:
    question: str
    text: str = "The aortic valve has three cusps."
    response_id: str = "response-supported"


class FinalizerScenario(Enum):
    NORMAL = "normal"
    FAIL_ONCE = "fail_once"


class EngineScenario(Enum):
    NORMAL = "normal"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class HostScenario:
    supported_answer: SupportedAnswer | None = None
    finalizer: FinalizerScenario = FinalizerScenario.NORMAL
    receipt_fingerprint: str | None = None
    engine: EngineScenario = EngineScenario.NORMAL


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 7, 12, 8, tzinfo=UTC)


class _RunStoreProbe:
    def __init__(self) -> None:
        self.values: dict[RunId, bytes] = {}

    def create(self, run_id: RunId, payload: bytes) -> bool:
        if run_id in self.values:
            return False
        self.values[run_id] = payload
        return True

    def compare_and_set(
        self, run_id: RunId, expected: bytes, replacement: bytes
    ) -> bool:
        if self.values.get(run_id) != expected:
            return False
        self.values[run_id] = replacement
        return True

    def load(self, run_id: RunId) -> bytes:
        return self.values[run_id]


class _RetrievalProbe:
    def __init__(self, inner: RetrievalPort) -> None:
        self._inner = inner
        self.search_calls = 0

    def index(self, documents: Sequence[RetrievalDocument]) -> IndexReceipt:
        raise AssertionError(f"service attempted indexing: {documents!r}")

    def search(self, query: RetrievalQuery) -> RetrievalEvidenceSet:
        self.search_calls += 1
        return self._inner.search(query)


class _CancelledEngine:
    async def execute(self, **kwargs: object) -> CancelledRunResult:
        assert kwargs["run_id"]
        return CancelledRunResult(
            {},
            (),
            EngineFailure(
                EngineErrorCode.CANCELLED,
                "model execution was cancelled",
                "draft_answer",
            ),
        )


class _EngineFactoryProbe:
    def __init__(
        self,
        store: _RunStoreProbe,
        content: CourseSourceContent,
        *,
        model: ScriptedModel,
        scenario: EngineScenario,
    ) -> None:
        self.run_store = store
        self._content = content
        self.created = 0
        self.last_tools: tuple[ToolExecutor, ...] = ()
        self._model = model
        self._scenario = scenario

    @property
    def model(self) -> ScriptedModel:
        return self._model

    def create(self, *, tools: tuple[ToolExecutor, ...]) -> PlaybookEngine:
        self.created += 1
        self.last_tools = tools
        if self._scenario is EngineScenario.CANCELLED:
            return cast(PlaybookEngine, _CancelledEngine())
        return PlaybookEngine(
            engine_version=V1,
            model_adapter=ArtifactReference("scripted-model", V1),
            state_contract=ArtifactReference("event_state", V1),
            model=self._model,
            registries=RuntimeRegistries(
                tools,
                (
                    EvidenceSufficiencyValidator(),
                    GroundedAnswerIntegrityValidator(self._content),
                ),
                (
                    PromptComposerRegistration(
                        GROUNDED_ANSWER_PROMPT, CanonicalPromptComposer()
                    ),
                ),
            ),
            run_store=self.run_store,
            clock=_Clock(),
        )


class _FinalizerProbe:
    def __init__(
        self, inner: GroundedSessionFinalizer, scenario: FinalizerScenario
    ) -> None:
        self._inner = inner
        self._scenario = scenario
        self.calls = 0

    def finalize_grounded_run(self, **kwargs: object) -> object:
        self.calls += 1
        if self._scenario is FinalizerScenario.FAIL_ONCE and self.calls == 1:
            raise RetryableSessionConflictError("simulated process loss before commit")
        return self._inner.finalize_grounded_run(**kwargs)  # type: ignore[arg-type]


@dataclass(slots=True)
class HostComposition:
    grounding: GroundingAskService
    registry: StudyToolRegistry
    harness: StudyHarness
    events: SQLiteEventStore
    retrieval: _RetrievalProbe
    engine_factory: _EngineFactoryProbe
    finalizer: _FinalizerProbe
    run_store: _RunStoreProbe
    blobs: FilesystemBlobStore
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.blobs.close()

    def run_id(
        self,
        course_id: CourseId,
        session_id: SessionId,
        key: str,
        question_fingerprint: str,
        dependencies: tuple[ReadDependency, ...],
    ) -> RunId:
        return self.grounding._run_id(
            course_id, session_id, key, question_fingerprint, dependencies
        )


def _pins() -> VersionPins:
    return VersionPins(
        ArtifactReference(GROUNDED_ANSWER_SKILL.id, GROUNDED_ANSWER_SKILL.version),
        ArtifactReference(GROUNDED_ANSWER_FLOW.id, GROUNDED_ANSWER_FLOW.version),
        GROUNDED_ANSWER_PROMPT,
        (
            ToolBehaviorPin("session.get_context", V1),
            ToolBehaviorPin("source.search", V1),
        ),
        ArtifactReference("scripted-model", V1),
        ArtifactReference("event_state", V1),
    )


def context(
    *,
    key: str = "ask-1",
    capabilities: frozenset[str] | None = None,
    principal_kind: PrincipalKind = PrincipalKind.SERVICE,
) -> ExecutionContext:
    return ExecutionContext(
        principal_kind,
        "grounding-test",
        COURSE,
        CorrelationId("correlation-grounding-ask"),
        capabilities if capabilities is not None else frozenset({"study:ask"}),
        SESSION,
        idempotency_key=key,
    )


def _build_supported_model(
    answer: SupportedAnswer, retrieval: _RetrievalProbe
) -> ScriptedModel:
    evidence = EvidenceEnvelope.from_retrieval(
        retrieval._inner.search(RetrievalQuery(COURSE, answer.question))
    ).to_json()
    first_item = cast(tuple[JsonObject, ...], evidence["items"])[0]
    evidence_id = cast(str, first_item["evidence_id"])
    step = cast(ModelStep, GROUNDED_ANSWER_FLOW.steps[3])
    composed = CanonicalPromptComposer().compose(
        prompt=GROUNDED_ANSWER_PROMPT,
        layers=GROUNDED_ANSWER_SKILL.prompt_layers,
        inputs={
            "question": answer.question,
            "course_profile": course_profile_manifest(canonical_profile(COURSE)),
            "continuation_summary": None,
            "evidence": evidence,
        },
        output_schema=step.output_schema,
    )
    request = replace(
        step.request,
        messages=composed.messages,
        metadata={
            "prompt_fingerprint": composed.fingerprint,
            "prompt_id": composed.prompt.id,
            "prompt_version": str(composed.prompt.version),
        },
    )
    return ScriptedModel(
        (
            ScriptedExchange(
                request,
                ModelResponse(
                    "",
                    None,
                    ModelFinishReason.STOP,
                    ModelInvocation(
                        "scripted-model", "1.0.0", "fixture-model", answer.response_id
                    ),
                    structured_output={
                        "status": "answered",
                        "segments": (
                            {
                                "kind": "supported_claim",
                                "text": answer.text,
                                "evidence_ids": (evidence_id,),
                            },
                        ),
                        "unsupported_information_note": None,
                    },
                ),
            ),
        ),
        ModelCapabilities(structured_output=True),
        adapter_id="scripted-model",
        adapter_version="1.0.0",
        model_id="fixture-model",
    )


def _build_registry(
    *,
    courses: CourseViewPort,
    catalog: CourseSourceContent,
    retrieval: _RetrievalProbe,
    content: CourseSourceContent,
    sessions: SessionService,
    grounding: GroundingAskService,
) -> StudyToolRegistry:
    return StudyToolRegistry(
        courses=courses,
        catalog=catalog,
        retrieval=retrieval,
        content=content,
        sessions=sessions,
        grounding=grounding,
    )


def build_host(
    tmp_path: Path,
    *,
    scenario: HostScenario = HostScenario(),  # noqa: B008
) -> HostComposition:
    registry = EventRegistry()
    register_course_events(registry)
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    register_source_revision_events(registry, blobs.get)
    register_session_events(registry)
    events = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    courses = create_canonical_course(events, COURSE)
    ingest = TextIngestionService(blobs=blobs, events=events, clock=_Clock(), courses=courses)
    ingest.ingest(
        filename="heart.txt",
        content=b"The aortic valve has three cusps.",
        source_id=SourceId("heart"),
        title="Heart",
        trust_level=90,
        source_role="primary",
        context=ExecutionContext(
            PrincipalKind.SERVICE,
            "ingestion",
            COURSE,
            CorrelationId("correlation-ingestion"),
        ),
    )
    content = CourseSourceContent(COURSE, events, blobs)
    fts = SQLiteFtsRetrieval(tmp_path / "fts.sqlite3", content)
    documents = content.documents(include_superseded=True)
    receipt = fts.index(documents)
    if scenario.receipt_fingerprint is not None:
        receipt = replace(receipt, catalog_fingerprint=scenario.receipt_fingerprint)
    retrieval = _RetrievalProbe(fts)
    sessions = ProjectionSessionView(events.projection)
    session_service = SessionService(events, _Clock(), sessions, courses)
    session_service.start(context(key="session-start"))
    real_finalizer = GroundedSessionFinalizer(
        events,
        _Clock(),
        sessions,
        content,
        GROUNDED_ANSWER_SKILL.state_write_policy,
    )
    finalizer = _FinalizerProbe(real_finalizer, scenario.finalizer)
    run_store = _RunStoreProbe()
    model = (
        _build_supported_model(scenario.supported_answer, retrieval)
        if scenario.supported_answer is not None
        else ScriptedModel(
            (),
            ModelCapabilities(structured_output=True),
            adapter_id="scripted-model",
            adapter_version="1.0.0",
            model_id="unused-insufficient-model",
        )
    )
    engine_factory = _EngineFactoryProbe(
        run_store,
        content,
        model=model,
        scenario=scenario.engine,
    )
    grounding = GroundingAskService(
        courses=courses,
        session_service=session_service,
        sessions=sessions,
        retrieval=retrieval,
        catalog=content,
        content=content,
        finalizer=cast(GroundedSessionFinalizer, finalizer),
        engine_factory=engine_factory,
        run_store=run_store,
        configuration=GroundingAskConfiguration(_pins(), receipt),
    )
    public_registry = _build_registry(
        courses=courses,
        catalog=content,
        retrieval=retrieval,
        content=content,
        sessions=session_service,
        grounding=grounding,
    )
    return HostComposition(
        grounding,
        public_registry,
        StudyHarness(grounding),
        events,
        retrieval,
        engine_factory,
        finalizer,
        run_store,
        blobs,
    )


__all__ = [
    "COURSE",
    "SESSION",
    "EngineScenario",
    "FinalizerScenario",
    "HostComposition",
    "HostScenario",
    "SupportedAnswer",
    "build_host",
    "context",
]
