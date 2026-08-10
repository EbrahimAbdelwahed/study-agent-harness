from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

import pytest

from study_agent.application import (
    GroundingAskError,
    GroundingAskErrorCode,
)
from study_agent.domain import PrincipalKind
from study_agent.playbooks import ReadDependency
from tests.support.host_composition import (
    COURSE,
    SESSION,
    EngineScenario,
    FinalizerScenario,
    HostScenario,
    SupportedAnswer,
    build_host,
    context,
)


def test_insufficient_answer_is_canonical_and_retry_has_zero_effects(tmp_path: Path) -> None:
    host = build_host(tmp_path)
    try:
        before = len(host.events.read(COURSE))

        first = asyncio.run(host.grounding.ask("What is absent from these notes?", context()))
        after_first = len(host.events.read(COURSE))
        second = asyncio.run(host.grounding.ask("What is absent from these notes?", context()))

        assert first == second
        assert first.answer.answer.status.value == "insufficient_evidence"
        assert [event.kind.value for event in first.events] == [
            "grounding.accepted",
            "grounding.completed",
        ]
        assert after_first == before + 3
        assert len(host.events.read(COURSE)) == after_first
        assert host.retrieval.search_calls == 1
        assert host.engine_factory.created == 1
        host.engine_factory.model.assert_exhausted()
        assert host.events.verify_projection(COURSE)
    finally:
        host.close()


def test_supported_answer_executes_model_once_and_retry_is_identical(tmp_path: Path) -> None:
    host = build_host(
        tmp_path,
        scenario=HostScenario(
            supported_answer=SupportedAnswer("aortic valve"),
        ),
    )
    try:
        before = len(host.events.read(COURSE))

        first = asyncio.run(host.grounding.ask("aortic valve", context()))
        second = asyncio.run(host.grounding.ask("aortic valve", context()))

        assert first == second
        assert first.answer.answer.status.value == "answered"
        assert first.answer.answer.segments[0].citations[0].quoted_snippet == (
            "The aortic valve has three cusps."
        )
        assert host.retrieval.search_calls == 1
        assert len(host.events.read(COURSE)) == before + 3
        host.engine_factory.model.assert_exhausted()
    finally:
        host.close()


def test_changed_question_conflicts_before_any_new_effect(tmp_path: Path) -> None:
    host = build_host(tmp_path)
    try:
        asyncio.run(host.grounding.ask("What is absent from these notes?", context()))
        before = len(host.events.read(COURSE))

        with pytest.raises(GroundingAskError) as caught:
            asyncio.run(host.grounding.ask("A different question", context()))

        assert caught.value.code is GroundingAskErrorCode.CONFLICT
        assert len(host.events.read(COURSE)) == before
        assert host.retrieval.search_calls == 1
    finally:
        host.close()


def test_run_identity_commits_to_ordered_exact_read_dependencies(tmp_path: Path) -> None:
    host = build_host(tmp_path)
    try:
        dependencies = (
            ReadDependency("course_profile", str(COURSE), "course-v1"),
            ReadDependency("source_revision_set", str(COURSE), "source-v1"),
            ReadDependency("retrieval_index", str(COURSE), "index-v1"),
            ReadDependency("session_state", str(SESSION), "session-v1"),
        )

        baseline = host.run_id(COURSE, SESSION, "ask-1", "question-v1", dependencies)

        assert baseline == host.run_id(COURSE, SESSION, "ask-1", "question-v1", dependencies)
        for index, dependency in enumerate(dependencies):
            changed = list(dependencies)
            changed[index] = ReadDependency(
                dependency.kind, dependency.id, dependency.version + "-changed"
            )
            assert host.run_id(COURSE, SESSION, "ask-1", "question-v1", tuple(changed)) != baseline
        assert host.run_id(
            COURSE, SESSION, "ask-1", "question-v1", tuple(reversed(dependencies))
        ) != baseline
    finally:
        host.close()


def test_request_bound_executors_reject_authority_arguments(tmp_path: Path) -> None:
    host = build_host(tmp_path)
    try:
        asyncio.run(host.grounding.ask("What is absent from these notes?", context()))

        with pytest.raises(ValueError, match="accepts no playbook arguments"):
            asyncio.run(host.engine_factory.last_tools[0].invoke({"course_id": "forged"}))
        with pytest.raises(ValueError, match="trusted request question"):
            asyncio.run(
                host.engine_factory.last_tools[1].invoke(
                    {"query": "What is absent from these notes?", "session_id": "forged"}
                )
            )
    finally:
        host.close()


def test_completed_run_recovers_after_process_loss_without_repeating_search(
    tmp_path: Path,
) -> None:
    host = build_host(
        tmp_path,
        scenario=HostScenario(finalizer=FinalizerScenario.FAIL_ONCE),
    )
    try:
        before = len(host.events.read(COURSE))
        with pytest.raises(GroundingAskError) as caught:
            asyncio.run(host.grounding.ask("What is absent from these notes?", context()))
        assert caught.value.code is GroundingAskErrorCode.RETRYABLE_CONFLICT
        assert len(host.events.read(COURSE)) == before

        recovered = asyncio.run(
            host.grounding.ask("What is absent from these notes?", context())
        )

        assert recovered.answer.answer.status.value == "insufficient_evidence"
        assert host.retrieval.search_calls == 1
        assert host.finalizer.calls == 2
        assert len(host.events.read(COURSE)) == before + 3
    finally:
        host.close()


def test_authority_and_capability_rejections_happen_before_effects(tmp_path: Path) -> None:
    host = build_host(tmp_path)
    try:
        before = len(host.events.read(COURSE))
        unauthorized = context(capabilities=frozenset())

        with pytest.raises(GroundingAskError) as caught:
            asyncio.run(host.grounding.ask("Question", unauthorized))

        assert caught.value.code is GroundingAskErrorCode.UNAUTHORIZED
        assert len(host.events.read(COURSE)) == before
        assert host.retrieval.search_calls == 0
    finally:
        host.close()


def test_model_principal_with_explicit_grants_can_ask(tmp_path: Path) -> None:
    host = build_host(tmp_path)
    try:
        result = asyncio.run(
            host.grounding.ask(
                "What is absent from these notes?",
                context(principal_kind=PrincipalKind.MODEL),
            )
        )

        assert result.answer.answer.status.value == "insufficient_evidence"
        assert host.retrieval.search_calls == 1
        assert {event.actor.kind for event in host.events.read(COURSE)[-3:]} == {
            PrincipalKind.MODEL
        }
        assert host.events.verify_projection(COURSE)
    finally:
        host.close()


def test_string_principal_kind_is_rejected_before_effects(tmp_path: Path) -> None:
    host = build_host(tmp_path)
    try:
        forged = context(principal_kind=cast(PrincipalKind, "model"))
        before = len(host.events.read(COURSE))

        with pytest.raises(GroundingAskError) as caught:
            asyncio.run(host.grounding.ask("What is absent from these notes?", forged))

        assert caught.value.code is GroundingAskErrorCode.UNAUTHORIZED
        assert host.retrieval.search_calls == 0
        assert host.engine_factory.created == 0
        assert len(host.events.read(COURSE)) == before
    finally:
        host.close()


def test_forged_same_count_index_receipt_fails_before_execution(tmp_path: Path) -> None:
    host = build_host(
        tmp_path,
        scenario=HostScenario(receipt_fingerprint="0" * 64),
    )
    try:
        before = len(host.events.read(COURSE))

        with pytest.raises(GroundingAskError) as caught:
            asyncio.run(host.grounding.ask("What is absent from these notes?", context()))

        assert caught.value.code is GroundingAskErrorCode.INCOMPATIBLE_RUNTIME
        assert host.retrieval.search_calls == 0
        assert host.engine_factory.created == 0
        assert len(host.events.read(COURSE)) == before
    finally:
        host.close()


@pytest.mark.parametrize(
    ("persisted_status", "error_code"),
    [
        ("running", GroundingAskErrorCode.RUNNING),
        ("suspended", GroundingAskErrorCode.SUSPENDED),
        ("failed", GroundingAskErrorCode.FAILED),
        ("unknown", GroundingAskErrorCode.INCOMPATIBLE_RUNTIME),
    ],
)
def test_unsafe_persisted_states_never_reexecute(
    tmp_path: Path,
    persisted_status: str,
    error_code: GroundingAskErrorCode,
) -> None:
    host = build_host(
        tmp_path,
        scenario=HostScenario(finalizer=FinalizerScenario.FAIL_ONCE),
    )
    try:
        with pytest.raises(GroundingAskError):
            asyncio.run(host.grounding.ask("What is absent from these notes?", context()))
        run_id = next(iter(host.run_store.values))
        payload = json.loads(host.run_store.values[run_id])
        payload["checkpoint"]["status"] = persisted_status
        host.run_store.values[run_id] = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode()
        before = len(host.events.read(COURSE))

        with pytest.raises(GroundingAskError) as caught:
            asyncio.run(host.grounding.ask("What is absent from these notes?", context()))

        assert caught.value.code is error_code
        assert host.retrieval.search_calls == 1
        assert len(host.events.read(COURSE)) == before
    finally:
        host.close()


def test_corrupt_persisted_run_never_reexecutes(tmp_path: Path) -> None:
    host = build_host(
        tmp_path,
        scenario=HostScenario(finalizer=FinalizerScenario.FAIL_ONCE),
    )
    try:
        with pytest.raises(GroundingAskError):
            asyncio.run(host.grounding.ask("What is absent from these notes?", context()))
        run_id = next(iter(host.run_store.values))
        host.run_store.values[run_id] = b"not-json"
        before = len(host.events.read(COURSE))

        with pytest.raises(GroundingAskError) as caught:
            asyncio.run(host.grounding.ask("What is absent from these notes?", context()))

        assert caught.value.code is GroundingAskErrorCode.INCOMPATIBLE_RUNTIME
        assert host.retrieval.search_calls == 1
        assert len(host.events.read(COURSE)) == before
    finally:
        host.close()


def test_malformed_or_missing_model_output_never_writes_session_events(tmp_path: Path) -> None:
    host = build_host(tmp_path)
    try:
        before = len(host.events.read(COURSE))

        with pytest.raises(GroundingAskError) as caught:
            asyncio.run(host.grounding.ask("aortic valve", context()))

        assert caught.value.code is GroundingAskErrorCode.FAILED
        assert host.retrieval.search_calls == 1
        assert len(host.events.read(COURSE)) == before
        assert len(host.run_store.values) == 1
    finally:
        host.close()


def test_cancelled_playbook_result_is_existing_safe_failure_not_runtime_mismatch(
    tmp_path: Path,
) -> None:
    host = build_host(
        tmp_path,
        scenario=HostScenario(engine=EngineScenario.CANCELLED),
    )
    try:
        before = len(host.events.read(COURSE))
        with pytest.raises(GroundingAskError) as caught:
            asyncio.run(
                host.grounding.ask("What is absent from these notes?", context())
            )

        assert caught.value.code is GroundingAskErrorCode.FAILED
        assert len(host.events.read(COURSE)) == before
        assert host.retrieval.search_calls == 0
        assert host.engine_factory.created == 1
    finally:
        host.close()
