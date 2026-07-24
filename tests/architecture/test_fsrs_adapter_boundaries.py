from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "src" / "study_agent"
ADAPTER_PREFIX = SOURCE / "adapters" / "scheduling"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_fsrs_imports_are_confined_to_scheduling_adapter() -> None:
    violations: list[str] = []
    for path in sorted(SOURCE.rglob("*.py")):
        if path == ADAPTER_PREFIX / "py_fsrs.py":
            continue
        if any(module == "fsrs" or module.startswith("fsrs.") for module in _imports(path)):
            violations.append(str(path.relative_to(ROOT)))
    assert violations == []


def test_provider_neutral_recall_modules_do_not_import_adapter() -> None:
    violations: list[str] = []
    for path in sorted((SOURCE / "recall").rglob("*.py")):
        if any(
            module == "study_agent.adapters" or module.startswith("study_agent.adapters.")
            for module in _imports(path)
        ):
            violations.append(str(path.relative_to(ROOT)))
    assert violations == []
