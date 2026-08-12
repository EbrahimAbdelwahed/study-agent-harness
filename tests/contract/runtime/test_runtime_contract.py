from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast

import pytest

from study_agent.adapters.memory.storage import (
    DeterministicIdFactory,
    FixedClock,
    InMemoryBlobStore,
    InMemoryEventStore,
    InMemoryRunStore,
    MemoryRepository,
)
from study_agent.api.authority import AuthorityContext, PrincipalKind
from study_agent.api.runtime import RuntimeDependencies, create_runtime
from study_agent.artifacts.service import ArtifactService
from study_agent.assessments.service import AssessmentService
from study_agent.domain.errors import ValidationFailure
from study_agent.domain.identifiers import CorrelationId
from study_agent.kernel.module import KernelModule
from study_agent.ports.authority import HostAuthority
from study_agent.ports.model import ModelCapabilities, ModelPort
from study_agent.recall.service import RecallService


class _Model:
    capabilities = ModelCapabilities()

    async def generate(self, request: object) -> object:
        raise AssertionError("model must not be called")

    def stream(self, request: object) -> object:
        raise AssertionError("model must not be called")

    async def cancel(self, token: object) -> None:
        return None


class _Policy:
    def authorize(self, operation: str, context: object, *, durable: bool) -> None:
        return None


class _Capability:
    def discover(self) -> tuple[object, ...]:
        return ()

    async def start_request(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("capability start is not part of this smoke")

    async def resume(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("capability resume is not part of this smoke")


def _bound_service(service_type: type[object], store: object) -> object:
    service = object.__new__(service_type)
    service._events = store  # type: ignore[attr-defined]
    return service


def _composition() -> tuple[RuntimeDependencies, tuple[KernelModule, ...], AuthorityContext]:
    store = InMemoryEventStore()
    repository = MemoryRepository(store, InMemoryBlobStore(), InMemoryRunStore())
    authority = HostAuthority()
    context = authority.issue(
        PrincipalKind.HUMAN,
        "test-user",
        correlation_id="corr-1",
    )
    dependencies = RuntimeDependencies(
        context.principal,
        repository,
        store,
        FixedClock(datetime.now(UTC)),
        DeterministicIdFactory(),
        cast(ModelPort, _Model()),
        _Policy(),
    )
    module = KernelModule(
        "test",
        "1.0.0",
        services=(
            ("capabilities", _Capability()),
            ("artifacts", _bound_service(ArtifactService, store)),
            ("assessments", _bound_service(AssessmentService, store)),
            ("recall", _bound_service(RecallService, store)),
        ),
    )
    return dependencies, (module,), context


def test_runtime_composes_and_discovers_then_closes_idempotently() -> None:
    dependencies, modules, context = _composition()
    runtime = create_runtime(dependencies, modules)
    assert asyncio.run(runtime.discover_capabilities(context, CorrelationId("corr-1"))) == ()
    asyncio.run(runtime.close())
    asyncio.run(runtime.close())


def test_runtime_rejects_missing_service() -> None:
    dependencies, _, _ = _composition()
    with pytest.raises(ValidationFailure):
        create_runtime(dependencies, ())


def test_sync_runtime_rejects_running_loop() -> None:
    dependencies, modules, context = _composition()
    runtime = create_runtime(dependencies, modules)
    from study_agent.application.runtime import SyncStudyAgentRuntime

    sync = SyncStudyAgentRuntime(runtime)

    async def call() -> None:
        with pytest.raises(RuntimeError, match="active event loop"):
            sync.discover_capabilities(context, CorrelationId("corr-1"))
        await runtime.close()

    asyncio.run(call())
