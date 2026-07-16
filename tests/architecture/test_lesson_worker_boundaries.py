from __future__ import annotations

import ast
from pathlib import Path

from study_agent.tools import public_study_tool_manifests

PROJECT_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "study_agent"
COORDINATOR_FILES = (
    SOURCE_ROOT / "flashcards" / "lesson_worker_contracts.py",
    SOURCE_ROOT / "flashcards" / "lesson_worker_service.py",
    SOURCE_ROOT / "flashcards" / "lesson_worker_view.py",
    SOURCE_ROOT / "ports" / "lesson_worker.py",
    SOURCE_ROOT / "tools" / "planned_flashcard_scope_bridge.py",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_lesson_worker_files_exist_only_at_the_declared_boundary() -> None:
    missing = [
        path.relative_to(PROJECT_ROOT) for path in COORDINATOR_FILES if not path.is_file()
    ]
    assert missing == []


def test_coordinator_cannot_import_direct_execution_or_canonical_state_owners() -> None:
    forbidden = (
        "study_agent.adapters",
        "study_agent.artifacts",
        "study_agent.capabilities.dispatch",
        "study_agent.capabilities.flashcard_dispatch",
        "study_agent.capabilities.gateway",
        "study_agent.events",
        "study_agent.models",
        "study_agent.playbooks.engine",
        "study_agent.ports.model",
        "study_agent.state.events",
        "study_agent.state.store",
        "study_agent.validators",
        "anthropic",
        "deepseek",
        "google.generativeai",
        "openai",
    )
    violations = [
        f"{path.relative_to(PROJECT_ROOT)} imports {name}"
        for path in COORDINATOR_FILES
        for name in sorted(_imports(path))
        # Candidate batches are transient verified output contracts, not the
        # canonical artifact aggregate/service guarded by this boundary.
        if name != "study_agent.artifacts.candidates"
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
    ]
    assert violations == []


def test_coordinator_has_no_public_tool_or_canonical_write_declarations() -> None:
    forbidden_names = {
        "CapabilityGateway",
        "FlashcardCapabilityDispatcher",
        "ModelAdapter",
        "StudyToolManifest",
        "ValidatorExecutor",
    }
    forbidden_arguments = {
        "artifact_store",
        "dispatcher",
        "event_store",
        "gateway",
        "model",
        "provider",
        "validator",
    }
    violations: list[str] = []
    for path in COORDINATOR_FILES:
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} references {node.id}")
            if isinstance(node, ast.arg) and node.arg in forbidden_arguments:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} accepts {node.arg}")
    assert violations == []


def test_private_planned_scope_bridge_is_not_a_public_study_tool() -> None:
    names = tuple(manifest.name for manifest in public_study_tool_manifests())
    assert names == (
        "citation.resolve",
        "course.get",
        "grounding.ask",
        "session.get_context",
        "session.record_note",
        "source.list",
        "source.search",
    )
    assert "source.prepare_planned_flashcard_scope" not in names
