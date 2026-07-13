from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

import study_agent.tools.registry as registry_module
from study_agent.adapters.filesystem import FilesystemBlobStore
from study_agent.application import GroundingAskService
from study_agent.domain import CorrelationId, CourseId, ExecutionContext, PrincipalKind
from study_agent.domain._validation import JsonObject
from study_agent.tools import (
    IdempotencyMode,
    StudyToolRegistry,
    ToolEffect,
    ToolErrorCode,
    ToolManifest,
    ToolResult,
)
from study_agent.tools.builtin import builtin_tools
from tests.integration.test_grounding_ask_service import COURSE, SESSION, composition

_MANIFEST_SNAPSHOT = {
    "citation.resolve": (
        "1.0.0",
        "1b7f74005dfaee7879322edd8f60ca7892e9e20d024b1807aafac0af5ecfcb71",
        ToolEffect.READ_ONLY,
        ("study:read",),
        IdempotencyMode.NOT_APPLICABLE,
        (),
    ),
    "course.get": (
        "1.0.0",
        "ccfeca393bc56a3de08abc0d91ef68a9104255a43f0d428312c46d841008934b",
        ToolEffect.READ_ONLY,
        ("study:read",),
        IdempotencyMode.NOT_APPLICABLE,
        (),
    ),
    "grounding.ask": (
        "1.0.0",
        "7452676719dfcfa31f4824f45ed1d1a417dcbbb7522494522955f762850eec0e",
        ToolEffect.ORCHESTRATION,
        ("study:ask",),
        IdempotencyMode.REQUIRED,
        (
            "grounding.accepted",
            "grounding.completed",
            "grounding.suspended",
            "grounding.failed",
        ),
    ),
    "session.get_context": (
        "1.0.0",
        "ea60a58728e9d9d96c11fa3cc69bc85e73e7fcbbb7fab9ce2b7821229734d3ba",
        ToolEffect.READ_ONLY,
        ("study:read",),
        IdempotencyMode.NOT_APPLICABLE,
        (),
    ),
    "session.record_note": (
        "1.0.0",
        "e4d3e7446a82e4570c67abb9da9ddab70c60e14350e412c18065bf33c1b04986",
        ToolEffect.CANONICAL_WRITE,
        ("study:write",),
        IdempotencyMode.REQUIRED,
        ("session.interaction_recorded", "session.continuation_summary_updated"),
    ),
    "source.list": (
        "1.0.0",
        "387d629a6bd69ffad34dae41a5fe1c88f2619bda4637fcfeb3be96ac21cef24b",
        ToolEffect.READ_ONLY,
        ("study:read",),
        IdempotencyMode.NOT_APPLICABLE,
        (),
    ),
    "source.search": (
        "1.0.0",
        "f66b9bf4a901367ab9867efeab53bd749218e8d01f1639282300abb55b2f5c97",
        ToolEffect.READ_ONLY,
        ("study:read",),
        IdempotencyMode.NOT_APPLICABLE,
        (),
    ),
}


def _context(
    *capabilities: str,
    key: str | None = None,
    principal: PrincipalKind = PrincipalKind.SERVICE,
) -> ExecutionContext:
    return ExecutionContext(
        principal,
        "contract-host",
        COURSE,
        CorrelationId("contract-correlation"),
        frozenset(capabilities),
        SESSION,
        idempotency_key=key,
    )


def _registry(
    tmp_path: Path,
) -> tuple[StudyToolRegistry, GroundingAskService, FilesystemBlobStore]:
    service, _, _, _, _, blobs = composition(tmp_path)
    registry = StudyToolRegistry(
        courses=service._courses,
        catalog=service._catalog,
        retrieval=service._retrieval,
        content=service._content,
        sessions=service._session_service,
        grounding=service,
    )
    return registry, service, blobs


def test_exact_manifest_snapshot_and_declarations_are_immutable(tmp_path: Path) -> None:
    registry, _, blobs = _registry(tmp_path)
    manifests = registry.manifests

    assert tuple(item.name for item in manifests) == tuple(sorted(_MANIFEST_SNAPSHOT))
    assert len({item.identity for item in manifests}) == 7
    assert len({item.fingerprint for item in manifests}) == 7
    for manifest in manifests:
        expected = _MANIFEST_SNAPSHOT[manifest.name]
        assert (
            manifest.version,
            manifest.fingerprint,
            manifest.effect,
            manifest.required_capabilities,
            manifest.idempotency,
            manifest.emitted_event_kinds,
        ) == expected
        assert manifest.error_codes == tuple(ToolErrorCode)
        assert manifest.input_schema["additionalProperties"] is False
        assert manifest.output_schema["additionalProperties"] is False
        with pytest.raises(TypeError):
            manifest.input_schema["type"] = "string"  # type: ignore[index]
    blobs.close()


@pytest.mark.parametrize(
    "authority",
    (
        "principal_id",
        "principal_kind",
        "course_id",
        "session_id",
        "correlation_id",
        "model_run_id",
        "idempotency_key",
        "provider",
        "model",
        "prompt_id",
        "run_id",
        "pins",
    ),
)
def test_authority_and_runtime_selectors_are_forbidden_before_effect(
    tmp_path: Path, authority: str
) -> None:
    registry, service, blobs = _registry(tmp_path)
    retrieval = cast(Any, service._retrieval)
    result = asyncio.run(
        registry.invoke(
            "source.search",
            {"query": "aortic valve", authority: "spoofed"},
            _context("study:read"),
        )
    )
    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert retrieval.search_calls == 0
    blobs.close()


def test_unknown_tool_and_model_capabilities_fail_closed(tmp_path: Path) -> None:
    registry, _, blobs = _registry(tmp_path)
    unknown = asyncio.run(registry.invoke("source.injected", {}, _context("study:read")))
    denied = asyncio.run(
        registry.invoke("course.get", {}, _context(principal=PrincipalKind.MODEL))
    )
    granted = asyncio.run(
        registry.invoke(
            "course.get", {}, _context("study:read", principal=PrincipalKind.MODEL)
        )
    )
    spoofed = asyncio.run(
        registry.invoke(
            "course.get",
            {"requested_capabilities": ("study:read",)},
            _context(principal=PrincipalKind.MODEL),
        )
    )

    assert unknown.error is not None and unknown.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert denied.error is not None and denied.error.code is ToolErrorCode.UNAUTHORIZED
    assert granted.error is None
    assert spoofed.error is not None and spoofed.error.code is ToolErrorCode.INVALID_ARGUMENTS
    blobs.close()


def test_all_read_tools_are_scoped_and_source_list_never_discloses_content(
    tmp_path: Path,
) -> None:
    registry, _, blobs = _registry(tmp_path)
    context = _context("study:read")
    course = asyncio.run(registry.invoke("course.get", {}, context))
    listed = asyncio.run(registry.invoke("source.list", {}, context))
    found = asyncio.run(
        registry.invoke(
            "source.search",
            {
                "query": "aortic valve",
                "limit": 1,
                "minimum_trust_level": 90,
                "source_roles": ("primary",),
                "include_superseded": False,
            },
            context,
        )
    )
    empty = asyncio.run(
        registry.invoke(
            "source.search",
            {"query": "aortic valve", "minimum_trust_level": 100},
            context,
        )
    )
    session = asyncio.run(registry.invoke("session.get_context", {}, context))

    for result in (course, listed, found, empty, session):
        assert result.error is None
    assert listed.value is not None
    source = cast(tuple[Mapping[str, object], ...], listed.value["sources"])[0]
    assert set(source) == {
        "source_id",
        "revision_id",
        "title",
        "kind",
        "source_role",
        "trust_level",
        "is_current_revision",
    }
    assert not ({"content", "text", "blob", "blob_ref", "path", "uri"} & set(source))
    assert found.value is not None and found.value["status"] == "sufficient"
    evidence = cast(tuple[Mapping[str, object], ...], found.value["evidence"])
    full_citation = cast(Mapping[str, object], evidence[0]["citation"])
    citation = cast(
        JsonObject,
        {
            name: full_citation[name]
            for name in (
                "source_id",
                "revision_id",
                "chunk_id",
                "start_offset",
                "end_offset",
            )
        },
    )
    resolved = asyncio.run(registry.invoke("citation.resolve", {"citation": citation}, context))
    assert resolved.error is None and resolved.value is not None
    assert resolved.value["text"] == "The aortic valve has three cusps."
    canonical = cast(Mapping[str, object], resolved.value["citation"])
    assert canonical["quoted_snippet"] == resolved.value["text"]
    assert empty.value is not None
    assert empty.value["status"] == "insufficient"
    assert empty.value["evidence"] == ()
    blobs.close()


def test_note_write_requires_key_is_idempotent_and_conflicts_on_changed_content(
    tmp_path: Path,
) -> None:
    registry, _, blobs = _registry(tmp_path)
    missing = asyncio.run(
        registry.invoke("session.record_note", {"content": "A note"}, _context("study:write"))
    )
    context = _context("study:write", key="note-key")
    first = asyncio.run(registry.invoke("session.record_note", {"content": "A note"}, context))
    retry = asyncio.run(registry.invoke("session.record_note", {"content": "A note"}, context))
    conflict = asyncio.run(
        registry.invoke("session.record_note", {"content": "Changed"}, context)
    )
    assert missing.error is not None and missing.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert first == retry
    assert first.error is None
    assert conflict.error is not None and conflict.error.code is ToolErrorCode.CONFLICT
    blobs.close()


def test_returned_json_graphs_are_deeply_immutable(tmp_path: Path) -> None:
    registry, _, blobs = _registry(tmp_path)
    result = asyncio.run(registry.invoke("source.list", {}, _context("study:read")))
    assert result.value is not None
    with pytest.raises(TypeError):
        result.value["sources"] = ()  # type: ignore[index]
    source = cast(tuple[JsonObject, ...], result.value["sources"])[0]
    with pytest.raises(TypeError):
        source["title"] = "tampered"  # type: ignore[index]
    blobs.close()


def test_duplicate_tool_names_are_rejected_at_composition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service, blobs = _registry(tmp_path)
    tools = builtin_tools(
        courses=service._courses,
        catalog=service._catalog,
        retrieval=service._retrieval,
        content=service._content,
        sessions=service._session_service,
        grounding=service,
    )
    duplicated = (*tools[:-1], tools[0])
    monkeypatch.setattr(registry_module, "builtin_tools", lambda **_: duplicated)
    with pytest.raises(RuntimeError, match="exactly seven unique"):
        StudyToolRegistry(
            courses=service._courses,
            catalog=service._catalog,
            retrieval=service._retrieval,
            content=service._content,
            sessions=service._session_service,
            grounding=service,
        )
    blobs.close()


@dataclass(frozen=True)
class _InvalidOutputTool:
    manifest: ToolManifest

    async def invoke(
        self, arguments: JsonObject, context: ExecutionContext
    ) -> ToolResult:
        del arguments, context
        return ToolResult.success({"unexpected": "provider-secret"})


def test_invalid_tool_output_fails_closed_without_leaking_value(tmp_path: Path) -> None:
    registry, _, blobs = _registry(tmp_path)
    manifest = next(item for item in registry.manifests if item.name == "course.get")
    tools = cast(dict[str, Any], registry._tools)
    tools["course.get"] = _InvalidOutputTool(manifest)

    result = asyncio.run(registry.invoke("course.get", {}, _context("study:read")))

    assert result.value is None
    assert result.error is not None
    assert result.error.code is ToolErrorCode.INCOMPATIBLE_RUNTIME
    assert "provider-secret" not in str(result.to_json())
    blobs.close()


def test_citation_resolution_rejects_a_context_for_another_course(tmp_path: Path) -> None:
    registry, _, blobs = _registry(tmp_path)
    local = _context("study:read")
    found = asyncio.run(
        registry.invoke("source.search", {"query": "aortic valve"}, local)
    )
    assert found.value is not None
    evidence = cast(tuple[Mapping[str, object], ...], found.value["evidence"])
    full = cast(Mapping[str, object], evidence[0]["citation"])
    citation = cast(
        JsonObject,
        {
            key: full[key]
            for key in (
                "source_id",
                "revision_id",
                "chunk_id",
                "start_offset",
                "end_offset",
            )
        },
    )
    foreign = ExecutionContext(
        PrincipalKind.SERVICE,
        "foreign-course-host",
        CourseId("course-foreign"),
        CorrelationId("foreign-correlation"),
        frozenset({"study:read"}),
        SESSION,
    )

    resolved = asyncio.run(
        registry.invoke("citation.resolve", {"citation": citation}, foreign)
    )

    assert resolved.value is None
    assert resolved.error is not None
    assert resolved.error.code in {ToolErrorCode.NOT_FOUND, ToolErrorCode.UNAUTHORIZED}
    blobs.close()
