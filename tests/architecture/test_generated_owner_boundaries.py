from __future__ import annotations

import ast
import inspect
from pathlib import Path

from study_agent.ports.generated_owner import GeneratedBatchOwnerStore

PROJECT_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "study_agent"
OWNER = SOURCE_ROOT / "artifacts" / "generated_owner.py"
PORT = SOURCE_ROOT / "ports" / "generated_owner.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_generated_owner_files_exist_at_declared_seam() -> None:
    assert OWNER.is_file()
    assert PORT.is_file()
    assert tuple(inspect.signature(GeneratedBatchOwnerStore.create).parameters) == (
        "self",
        "child_run_id",
        "payload",
    )
    assert tuple(inspect.signature(GeneratedBatchOwnerStore.load).parameters) == (
        "self",
        "child_run_id",
    )


def test_generated_owner_has_no_runtime_or_provider_dependency() -> None:
    forbidden = (
        "study_agent.adapters",
        "study_agent.capabilities.gateway",
        "study_agent.events",
        "study_agent.models",
        "study_agent.playbooks.engine",
        "study_agent.state.events",
        "anthropic",
        "deepseek",
        "openai",
        "sqlite3",
    )
    violations = {
        imported
        for path in (OWNER, PORT)
        for imported in _imports(path)
        if any(imported == prefix or imported.startswith(prefix + ".") for prefix in forbidden)
    }
    assert violations == set()


def test_store_protocol_has_no_discovery_or_filesystem_surface() -> None:
    assert set(GeneratedBatchOwnerStore.__dict__) & {"list", "scan", "find", "path"} == set()
