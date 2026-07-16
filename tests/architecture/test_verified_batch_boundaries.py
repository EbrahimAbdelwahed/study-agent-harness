from __future__ import annotations

import ast
import inspect
from pathlib import Path

from study_agent.artifacts.verified_batch import VerifiedGeneratedBatchAdapter

PROJECT_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "study_agent"
ADAPTER = SOURCE_ROOT / "artifacts" / "verified_batch.py"
PORT = SOURCE_ROOT / "ports" / "verified_batch.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_verified_batch_adapter_has_exact_recovery_interface() -> None:
    assert ADAPTER.is_file() and PORT.is_file()
    assert tuple(inspect.signature(VerifiedGeneratedBatchAdapter.recover).parameters) == (
        "self",
        "run_id",
        "context",
    )


def test_verified_batch_seam_has_no_concrete_runtime_or_provider_dependency() -> None:
    forbidden = (
        "study_agent.adapters",
        "study_agent.capabilities.gateway",
        "study_agent.models",
        "study_agent.playbooks.engine",
        "study_agent.state.events",
        "study_agent.state.store",
        "anthropic",
        "deepseek",
        "openai",
        "sqlite3",
    )
    violations = {
        imported
        for path in (ADAPTER, PORT)
        for imported in _imports(path)
        if any(imported == prefix or imported.startswith(prefix + ".") for prefix in forbidden)
    }
    assert violations == set()


def test_adapter_does_not_define_gateway_model_or_event_write_methods() -> None:
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"), filename=str(ADAPTER))
    forbidden = {"append", "execute", "invoke", "start", "resume", "save", "write"}
    assert {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in forbidden
    } == set()
