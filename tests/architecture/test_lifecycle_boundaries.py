from __future__ import annotations

import ast
from pathlib import Path

from study_agent.tools.builtin import public_study_tool_manifests

ROOT = Path(__file__).parents[2] / "src" / "study_agent"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_lifecycle_contracts_do_not_import_cli_adapters_providers_or_stateful_services() -> None:
    forbidden = (
        "study_agent.adapters",
        "study_agent.application",
        "study_agent.cli",
        "study_agent.courses",
        "study_agent.ingestion",
        "study_agent.retrieval",
        "study_agent.sessions",
        "study_agent.tools",
        "openai",
        "anthropic",
        "deepseek",
        "httpx",
        "requests",
        "socket",
        "sqlite3",
    )
    imports = _imports(ROOT / "lifecycle" / "contracts.py")
    assert not {
        item
        for item in imports
        if any(item == prefix or item.startswith(prefix + ".") for prefix in forbidden)
    }


def test_domain_events_and_projections_do_not_import_lifecycle_intent() -> None:
    violations: list[str] = []
    for package in ("courses", "ingestion", "sessions"):
        for path in sorted((ROOT / package).rglob("*.py")):
            if path.name not in {"events.py", "projection.py"}:
                continue
            for imported in _imports(path):
                if imported == "study_agent.lifecycle" or imported.startswith(
                    "study_agent.lifecycle."
                ):
                    violations.append(f"{path.relative_to(ROOT)} imports {imported}")
    assert violations == []


def test_lifecycle_adds_no_study_tools_and_exact_seven_surface_is_unchanged() -> None:
    manifests = public_study_tool_manifests()
    assert tuple(item.name for item in manifests) == (
        "citation.resolve",
        "course.get",
        "grounding.ask",
        "session.get_context",
        "session.record_note",
        "source.list",
        "source.search",
    )
    assert len({item.identity for item in manifests}) == 7
