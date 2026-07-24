"""Auditable composition root for one local study-agent repository."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol

from study_agent.adapters.filesystem import (
    FilesystemBlobStore,
    LocalRepositoryError,
    LocalRepositoryPaths,
    initialize_local_repository,
    validate_local_repository_layout,
)
from study_agent.adapters.filesystem.repository_target import RepositoryObservationHandle
from study_agent.adapters.model import (
    ADAPTER_ID as OPENAI_COMPATIBLE_ADAPTER_ID,
)
from study_agent.adapters.model import (
    ADAPTER_VERSION as OPENAI_COMPATIBLE_ADAPTER_VERSION,
)
from study_agent.adapters.model import (
    OpenAICompatibleConfig,
    OpenAICompatibleModel,
)
from study_agent.adapters.sqlite import (
    SQLiteConnectionIdentityGuard,
    SQLiteEventStore,
    SQLiteFtsRetrieval,
    SQLiteRunStore,
)
from study_agent.adapters.system import SystemClock
from study_agent.application import (
    GroundingAskConfiguration,
    GroundingAskError,
    GroundingAskErrorCode,
    GroundingAskService,
    GroundingEngineFactory,
)
from study_agent.artifacts import register_artifact_events
from study_agent.assessments import (
    ProjectionAssessmentView,
    ProjectionLearnerEvidenceView,
    register_assessment_events,
)
from study_agent.courses import (
    CourseService,
    ProjectionCourseCatalog,
    ProjectionCourseView,
    register_course_events,
)
from study_agent.domain import ChunkId, Citation, CourseId, ResolvedCitation
from study_agent.grounding import (
    EvidenceSufficiencyValidator,
    GroundedAnswerIntegrityValidator,
)
from study_agent.ingestion import TextIngestionService, register_source_revision_events
from study_agent.playbooks import (
    PlaybookEngine,
    PromptComposerRegistration,
    RuntimeRegistries,
    ToolBehaviorPin,
    ToolExecutor,
    VersionPins,
)
from study_agent.playbooks.builtin import GROUNDED_ANSWER_FLOW
from study_agent.ports import IndexReceipt, ModelCapabilities, ModelPort
from study_agent.ports.retrieval import RetrievalDocument, retrieval_catalog_fingerprint
from study_agent.ports.scheduling import SchedulingPolicyPort
from study_agent.prompts import GROUNDED_ANSWER_PROMPT, CanonicalPromptComposer
from study_agent.recall import (
    RecallAvailability,
    RecallComposition,
    compose_recall,
    register_recall_events,
)
from study_agent.repository_config import LocalRepositoryConfig, ModelAdapterConfig
from study_agent.retrieval import CourseSourceContent
from study_agent.sessions import (
    GroundedSessionFinalizer,
    ProjectionAssistantTurnView,
    ProjectionSessionView,
    SessionService,
    SessionTurnService,
    register_session_events,
)
from study_agent.skills import ArtifactReference, SemanticVersion
from study_agent.skills.builtin import GROUNDED_ANSWER_SKILL
from study_agent.state import EventRegistry
from study_agent.study_context import (
    ProjectionStudyContextView,
    StudyContextService,
    register_study_context_events,
)
from study_agent.tutor_snapshot import TutorSnapshotReader

if TYPE_CHECKING:
    from study_agent.tools import StudyToolRegistry

_V1 = SemanticVersion.parse("1.0.0")


class ModelAdapterConfigurationError(ValueError):
    """A configured technical model adapter cannot be constructed safely."""


class ModelAdapterBuilder(Protocol):
    def __call__(self, config: ModelAdapterConfig, credential: str | None) -> ModelPort: ...


class ModelAdapterRegistry:
    """Closed-at-composition registry keyed only by technical adapter identity."""

    def __init__(
        self,
        builders: Mapping[str, ModelAdapterBuilder],
        *,
        versions: Mapping[str, str] | None = None,
    ) -> None:
        copied = dict(builders)
        if not copied or any(
            not isinstance(key, str) or not key or key != key.strip() for key in copied
        ):
            raise ValueError("model adapter ids must be unique non-empty trimmed text")
        if any(not callable(builder) for builder in copied.values()):
            raise ValueError("model adapter builders must be callable")
        raw_versions = dict(versions or {})
        if set(raw_versions) - set(copied):
            raise ValueError("model adapter versions cannot name unregistered adapters")
        if any(not isinstance(value, str) for value in raw_versions.values()):
            raise ValueError("model adapter versions must be semantic-version text")
        try:
            parsed_versions = {
                adapter_id: SemanticVersion.parse(raw_versions.get(adapter_id, "1.0.0"))
                for adapter_id in copied
            }
        except ValueError as error:
            raise ValueError("model adapter versions must be semantic versions") from error
        self._builders = MappingProxyType(copied)
        self._versions = MappingProxyType(parsed_versions)

    @property
    def adapter_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._builders))

    def create(
        self,
        config: ModelAdapterConfig,
        environment: Mapping[str, str] | None = None,
    ) -> ModelPort:
        try:
            builder = self._builders[config.adapter_id]
        except KeyError as error:
            raise ModelAdapterConfigurationError(
                "configured model adapter is unavailable"
            ) from error
        source = os.environ if environment is None else environment
        try:
            credential = (
                None if config.credential_env is None else source.get(config.credential_env)
            )
        except Exception:
            raise ModelAdapterConfigurationError(
                "configured model credential could not be resolved"
            ) from None
        if config.credential_env is not None and (
            not isinstance(credential, str) or not credential
        ):
            raise ModelAdapterConfigurationError("configured model credential is unavailable")
        try:
            return builder(config, credential)
        except Exception:
            raise ModelAdapterConfigurationError(
                "configured model adapter could not be constructed"
            ) from None

    def artifact(self, adapter_id: str) -> ArtifactReference:
        try:
            return ArtifactReference(adapter_id, self._versions[adapter_id])
        except KeyError as error:
            raise ModelAdapterConfigurationError(
                "configured model adapter is unavailable"
            ) from error


def default_model_adapters() -> ModelAdapterRegistry:
    return ModelAdapterRegistry(
        {OPENAI_COMPATIBLE_ADAPTER_ID: _openai_compatible_model},
        versions={
            OPENAI_COMPATIBLE_ADAPTER_ID: OPENAI_COMPATIBLE_ADAPTER_VERSION,
        },
    )


def _openai_compatible_model(config: ModelAdapterConfig, credential: str | None) -> ModelPort:
    expected = {"endpoint_url", "model_id", "timeout_seconds"}
    if set(config.settings) != expected:
        raise ModelAdapterConfigurationError(
            "openai-compatible settings must contain endpoint_url, model_id, and timeout_seconds"
        )
    endpoint = config.settings["endpoint_url"]
    model_id = config.settings["model_id"]
    timeout = config.settings["timeout_seconds"]
    if not isinstance(endpoint, str) or not isinstance(model_id, str):
        raise ModelAdapterConfigurationError("model endpoint and id must be text")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        raise ModelAdapterConfigurationError("model timeout must be numeric")
    if config.credential_env is None or credential is None:
        raise ModelAdapterConfigurationError("model adapter requires credential_env")
    try:
        return OpenAICompatibleModel(
            OpenAICompatibleConfig(
                endpoint,
                model_id,
                credential,
                float(timeout),
                ModelCapabilities(structured_output=True),
            )
        )
    except ValueError as error:
        raise ModelAdapterConfigurationError("model adapter configuration is invalid") from error


class _EngineFactory(GroundingEngineFactory):
    def __init__(
        self,
        *,
        model: ModelPort,
        run_store: SQLiteRunStore,
        clock: SystemClock,
        content: CourseSourceContent,
        model_adapter: ArtifactReference,
    ) -> None:
        self._model = model
        self._run_store = run_store
        self._clock = clock
        self._content = content
        self._model_adapter = model_adapter

    def create(self, *, tools: tuple[ToolExecutor, ...]) -> PlaybookEngine:
        return PlaybookEngine(
            engine_version=_V1,
            model_adapter=self._model_adapter,
            state_contract=ArtifactReference("event_state", _V1),
            model=self._model,
            registries=RuntimeRegistries(
                tools,
                (
                    EvidenceSufficiencyValidator(),
                    GroundedAnswerIntegrityValidator(self._content),
                ),
                (PromptComposerRegistration(GROUNDED_ANSWER_PROMPT, CanonicalPromptComposer()),),
            ),
            run_store=self._run_store,
            clock=self._clock,
        )


@dataclass(frozen=True, slots=True)
class CourseRepository:
    content: CourseSourceContent
    retrieval: SQLiteFtsRetrieval
    ingestion: TextIngestionService


class _RepositorySourceCatalog:
    """Complete canonical catalog required by the single repository FTS database."""

    def __init__(
        self,
        course_ids: Callable[[], tuple[CourseId, ...]],
        events: SQLiteEventStore,
        blobs: FilesystemBlobStore,
    ) -> None:
        self._course_ids = course_ids
        self._events = events
        self._blobs = blobs

    def _contents(self) -> tuple[CourseSourceContent, ...]:
        return tuple(
            CourseSourceContent(course_id, self._events, self._blobs)
            for course_id in self._course_ids()
        )

    def documents(self, *, include_superseded: bool = False) -> tuple[RetrievalDocument, ...]:
        return tuple(
            document
            for content in self._contents()
            for document in content.documents(include_superseded=include_superseded)
        )

    def canonical_document(self, chunk_id: ChunkId) -> RetrievalDocument:
        matches = tuple(
            document
            for document in self.documents(include_superseded=True)
            if document.chunk.chunk_id == chunk_id
        )
        if len(matches) != 1:
            raise LookupError("canonical chunk was not found uniquely")
        return matches[0]

    def resolve(self, citation: Citation) -> ResolvedCitation:
        document = self.canonical_document(citation.chunk_id)
        return CourseSourceContent(document.course_id, self._events, self._blobs).resolve(citation)


class LocalRepository:
    """Existing services wired over durable local adapters; no behavior is reimplemented."""

    def __init__(
        self,
        paths: LocalRepositoryPaths,
        config: LocalRepositoryConfig,
        *,
        model_adapters: ModelAdapterRegistry | None = None,
        environment: Mapping[str, str] | None = None,
        observation: RepositoryObservationHandle | None = None,
        recall_scheduler: SchedulingPolicyPort | None = None,
        recall_scheduler_factory: Callable[[], SchedulingPolicyPort] | None = None,
    ) -> None:
        if recall_scheduler is not None and recall_scheduler_factory is not None:
            raise TypeError("recall_scheduler and recall_scheduler_factory are mutually exclusive")
        if observation is None:
            validate_local_repository_layout(paths)
            persisted = LocalRepositoryConfig.load(paths.config)
            if persisted != config:
                raise LocalRepositoryError("loaded repository configuration is incompatible")
            blobs = FilesystemBlobStore(paths.blobs)
        else:
            if paths != observation.mutation_paths():
                raise LocalRepositoryError("repository observation paths are incompatible")
            blob_descriptor = observation.directory_descriptor("blobs")
            try:
                blobs = FilesystemBlobStore.from_descriptor(blob_descriptor, read_only=False)
            finally:
                os.close(blob_descriptor)
        events_database = (
            paths.events if observation is None else observation.mutation_database_path("events")
        )
        runs_database = (
            paths.runs if observation is None else observation.mutation_database_path("runs")
        )
        retrieval_database = (
            paths.retrieval
            if observation is None
            else observation.mutation_database_path("retrieval")
        )
        events_guard = (
            None
            if observation is None
            else SQLiteConnectionIdentityGuard(
                observation.database_connection_identity("events"),
                observation.verify_binding,
            )
        )
        runs_guard = (
            None
            if observation is None
            else SQLiteConnectionIdentityGuard(
                observation.database_connection_identity("runs"),
                observation.verify_binding,
            )
        )
        retrieval_guard = (
            None
            if observation is None
            else SQLiteConnectionIdentityGuard(
                observation.database_connection_identity("retrieval"),
                observation.verify_binding,
            )
        )
        self.paths = paths
        self._retrieval_database = retrieval_database
        self._retrieval_connection_identity_guard = retrieval_guard
        self.config = config
        self.clock = SystemClock()
        self.blobs = blobs
        registry = EventRegistry()
        register_course_events(registry)
        register_source_revision_events(registry, self.blobs.get)
        register_session_events(registry)
        register_study_context_events(registry)
        register_artifact_events(registry)
        register_assessment_events(registry)
        register_recall_events(registry)
        self.events = SQLiteEventStore(
            events_database, registry, connection_identity_guard=events_guard
        )
        self.runs = SQLiteRunStore(
            runs_database, connection_identity_guard=runs_guard
        )
        self._source_catalog = _RepositorySourceCatalog(
            self.events.list_course_ids, self.events, self.blobs
        )
        self.courses = ProjectionCourseView(self.events.projection)
        self.course_catalog = ProjectionCourseCatalog(self.events.list_course_ids, self.courses)
        self.course_service = CourseService(self.events, self.clock, self.courses)
        self.sessions = ProjectionSessionView(self.events.projection)
        self.session_service = SessionService(self.events, self.clock, self.sessions, self.courses)
        self.assistant_turns = ProjectionAssistantTurnView(self.events.projection)
        self.session_turn_service = SessionTurnService(
            self.events, self.clock, self.sessions, self.assistant_turns
        )
        self.study_context = ProjectionStudyContextView(self.events.projection)
        self.assessments = ProjectionAssessmentView(self.events.projection)
        self.learner_evidence = ProjectionLearnerEvidenceView(self.assessments)
        self.study_context_service = StudyContextService(
            self.events, self.clock, self.study_context, self.courses, self.sessions
        )
        self.tutor_snapshots = TutorSnapshotReader(self.events, registry)
        self.recall_composition = compose_recall(
            events=self.events,
            load_projection=self.events.projection,
            clock=self.clock,
            scheduler=recall_scheduler,
            scheduler_factory=recall_scheduler_factory,
        )
        self.recall: RecallComposition | None = (
            self.recall_composition if self.recall_composition.availability.available else None
        )
        self.recall_availability: RecallAvailability = self.recall_composition.availability
        self._model_adapters = model_adapters or default_model_adapters()
        self._environment = environment
        if observation is not None:
            observation.adopt_created_database_bindings()

    @classmethod
    def open(
        cls,
        root: str | Path,
        *,
        model_adapters: ModelAdapterRegistry | None = None,
        environment: Mapping[str, str] | None = None,
        recall_scheduler: SchedulingPolicyPort | None = None,
        recall_scheduler_factory: Callable[[], SchedulingPolicyPort] | None = None,
    ) -> LocalRepository:
        paths = LocalRepositoryPaths.at(root)
        config = LocalRepositoryConfig.load(paths.config)
        return cls(
            paths,
            config,
            model_adapters=model_adapters,
            environment=environment,
            recall_scheduler=recall_scheduler,
            recall_scheduler_factory=recall_scheduler_factory,
        )

    @classmethod
    def from_observation(
        cls,
        observation: RepositoryObservationHandle,
        config: LocalRepositoryConfig,
        *,
        model_adapters: ModelAdapterRegistry | None = None,
        environment: Mapping[str, str] | None = None,
        recall_scheduler: SchedulingPolicyPort | None = None,
        recall_scheduler_factory: Callable[[], SchedulingPolicyPort] | None = None,
    ) -> LocalRepository:
        """Compose mutable adapters while retaining an inspected repository owner."""
        if not isinstance(observation, RepositoryObservationHandle):
            raise TypeError("observation must be a RepositoryObservationHandle")
        if not isinstance(config, LocalRepositoryConfig):
            raise TypeError("config must be a LocalRepositoryConfig")
        return cls(
            observation.mutation_paths(),
            config,
            model_adapters=model_adapters,
            environment=environment,
            observation=observation,
            recall_scheduler=recall_scheduler,
            recall_scheduler_factory=recall_scheduler_factory,
        )

    def for_course(self, course_id: CourseId) -> CourseRepository:
        content = CourseSourceContent(course_id, self.events, self.blobs)
        return CourseRepository(
            content,
            SQLiteFtsRetrieval(
                self._retrieval_database,
                self._source_catalog,
                connection_identity_guard=self._retrieval_connection_identity_guard,
            ),
            TextIngestionService(
                blobs=self.blobs,
                events=self.events,
                clock=self.clock,
                courses=self.courses,
            ),
        )

    def rebuild_retrieval(self) -> IndexReceipt:
        """Rebuild the one discardable index from the complete canonical catalog."""
        retrieval = SQLiteFtsRetrieval(
            self._retrieval_database,
            self._source_catalog,
            connection_identity_guard=self._retrieval_connection_identity_guard,
        )
        documents = tuple(self._source_catalog.documents(include_superseded=True))
        return retrieval.rebuild(documents)

    def course_index_receipt(
        self, course_id: CourseId, repository_receipt: IndexReceipt
    ) -> IndexReceipt:
        """Bind an audited repository index version to one ask service's course reads."""
        if (
            type(repository_receipt) is not IndexReceipt
            or type(repository_receipt.indexed_chunks) is not int
            or type(repository_receipt.index_version) is not str
            or type(repository_receipt.catalog_fingerprint) is not str
        ):
            raise LocalRepositoryError("repository retrieval receipt is incompatible")
        content = CourseSourceContent(course_id, self.events, self.blobs)
        documents = tuple(content.documents(include_superseded=True))
        retrieval = SQLiteFtsRetrieval(
            self._retrieval_database,
            self._source_catalog,
            connection_identity_guard=self._retrieval_connection_identity_guard,
        )
        try:
            audited = retrieval.index(())
        except (OSError, RuntimeError, ValueError) as error:
            raise LocalRepositoryError(
                "retrieval index does not match the canonical repository catalog"
            ) from error
        if audited != repository_receipt:
            raise LocalRepositoryError("repository retrieval receipt is stale or incompatible")
        return IndexReceipt(
            len(documents),
            repository_receipt.index_version,
            retrieval_catalog_fingerprint(documents),
        )

    def grounding_service(
        self, course_id: CourseId, index_receipt: IndexReceipt
    ) -> GroundingAskService:
        if self.config.model is None:
            raise ModelAdapterConfigurationError("no model adapter is configured")
        course = self.for_course(course_id)
        model = self._model_adapters.create(self.config.model, self._environment)
        model_adapter = self._model_adapters.artifact(self.config.model.adapter_id)
        engine_factory = _EngineFactory(
            model=model,
            run_store=self.runs,
            clock=self.clock,
            content=course.content,
            model_adapter=model_adapter,
        )
        pins = VersionPins(
            ArtifactReference(GROUNDED_ANSWER_SKILL.id, GROUNDED_ANSWER_SKILL.version),
            ArtifactReference(GROUNDED_ANSWER_FLOW.id, GROUNDED_ANSWER_FLOW.version),
            GROUNDED_ANSWER_PROMPT,
            (
                ToolBehaviorPin("session.get_context", _V1),
                ToolBehaviorPin("source.search", _V1),
            ),
            model_adapter,
            ArtifactReference("event_state", _V1),
        )
        finalizer = GroundedSessionFinalizer(
            self.events,
            self.clock,
            self.sessions,
            course.content,
            GROUNDED_ANSWER_SKILL.state_write_policy,
        )
        return GroundingAskService(
            courses=self.courses,
            session_service=self.session_service,
            sessions=self.sessions,
            retrieval=course.retrieval,
            catalog=course.content,
            content=course.content,
            finalizer=finalizer,
            engine_factory=engine_factory,
            run_store=self.runs,
            configuration=GroundingAskConfiguration(pins, index_receipt),
        )

    def study_tools(self, course_id: CourseId) -> StudyToolRegistry:
        """Compose the exact public tool registry from this repository's services."""
        from study_agent.tools import StudyToolRegistry
        from study_agent.tools.builtin import GroundingAskServiceProvider

        course = self.for_course(course_id)

        def resolve_grounding() -> GroundingAskService:
            if self.config.model is None:
                raise GroundingAskError(
                    GroundingAskErrorCode.INCOMPATIBLE_RUNTIME,
                    "grounding requires a configured model adapter",
                )
            try:
                receipt = self.rebuild_retrieval()
                return self.grounding_service(
                    course_id, self.course_index_receipt(course_id, receipt)
                )
            except ModelAdapterConfigurationError as error:
                raise GroundingAskError(
                    GroundingAskErrorCode.INCOMPATIBLE_RUNTIME,
                    "grounding model configuration is unavailable",
                ) from error

        return StudyToolRegistry(
            courses=self.courses,
            catalog=course.content,
            retrieval=course.retrieval,
            content=course.content,
            sessions=self.session_service,
            grounding=GroundingAskServiceProvider(resolve_grounding),
        )

    def close(self) -> None:
        self.blobs.close()

    def __enter__(self) -> LocalRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


__all__ = [
    "CourseRepository",
    "LocalRepository",
    "LocalRepositoryError",
    "LocalRepositoryPaths",
    "ModelAdapterBuilder",
    "ModelAdapterConfigurationError",
    "ModelAdapterRegistry",
    "default_model_adapters",
    "initialize_local_repository",
]
