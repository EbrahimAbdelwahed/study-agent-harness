from __future__ import annotations

import ast
from pathlib import Path

from study_agent.tools import public_study_tool_manifests
from study_agent.workers import generation_worker_child_context

PROJECT_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "study_agent"
WORKERS = SOURCE_ROOT / "workers"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _violations(forbidden: tuple[str, ...]) -> list[str]:
    return [
        f"{path.relative_to(PROJECT_ROOT)} imports {item}"
        for path in sorted(WORKERS.rglob("*.py"))
        for item in sorted(_imports(path))
        if any(item == prefix or item.startswith(prefix + ".") for prefix in forbidden)
    ]


def test_worker_package_has_no_provider_sdk_or_adapter_dependency() -> None:
    assert _violations(
        (
            "openai",
            "anthropic",
            "deepseek",
            "google.generativeai",
            "study_agent.adapters",
        )
    ) == []


def test_worker_package_does_not_own_artifact_state_or_tutor_history() -> None:
    assert _violations(
        (
            "study_agent.artifacts",
            "study_agent.state.events",
            "study_agent.state.store",
            "study_agent.sessions",
            "study_agent.study_context",
            "study_agent.tutor",
            "study_agent.lifecycle",
        )
    ) == []


def test_worker_package_cannot_call_models_validators_or_dispatchers_directly() -> None:
    assert _violations(
        (
            "study_agent.ports.model",
            "study_agent.models",
            "study_agent.validators",
            "study_agent.playbooks.engine",
            "study_agent.capabilities.gateway",
            "study_agent.capabilities.dispatch",
            "study_agent.capabilities.flashcard_dispatch",
        )
    ) == []


def test_worker_operational_ports_are_inward_and_provider_neutral() -> None:
    imports = _imports(SOURCE_ROOT / "ports" / "worker.py")
    assert "study_agent.workers.contracts" in imports
    assert not any(
        item == prefix or item.startswith(prefix + ".")
        for item in imports
        for prefix in (
            "study_agent.adapters",
            "study_agent.tools",
            "study_agent.sessions",
            "study_agent.artifacts",
            "openai",
            "anthropic",
            "deepseek",
        )
    )


def test_workers_are_not_registered_as_public_study_tools() -> None:
    names = tuple(item.name for item in public_study_tool_manifests())
    assert names == (
        "citation.resolve",
        "course.get",
        "grounding.ask",
        "session.get_context",
        "session.record_note",
        "source.list",
        "source.search",
    )
    assert not any("worker" in name or "bundle" in name for name in names)


def test_worker_package_contains_no_study_tool_manifest_or_raw_callable_field() -> None:
    forbidden_names = {
        "StudyToolManifest",
        "ToolExecutor",
        "CapabilityGateway",
        "FlashcardCapabilityDispatcher",
        "ModelAdapter",
        "ValidatorExecutor",
    }
    violations: list[str] = []
    for path in sorted(WORKERS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} references {node.id}")
            if isinstance(node, ast.arg) and node.arg in {
                "dispatcher",
                "model",
                "validator",
                "callback",
            }:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} accepts raw {node.arg}")
    assert violations == []


def test_worker_service_start_and_resume_share_public_child_context_helper() -> None:
    assert callable(generation_worker_child_context)
    service_path = WORKERS / "service.py"
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    service = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "GenerationWorkerService"
    )
    methods = {
        node.name: node
        for node in service.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    for method_name in ("_drive_start", "_drive_resume"):
        calls = {
            node.func.id
            for node in ast.walk(methods[method_name])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "generation_worker_child_context" in calls
        assert "ExecutionContext" not in calls
