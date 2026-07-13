from __future__ import annotations

import ast
from pathlib import Path

from study_agent.playbooks import RuntimeRegistries, ToolStep
from study_agent.playbooks.builtin import GROUNDED_ANSWER_FLOW
from study_agent.tools import StudyToolRegistry

ROOT = Path(__file__).parents[2] / "src" / "study_agent"


def test_public_and_internal_registries_are_distinct_contracts() -> None:
    assert StudyToolRegistry.__module__ == "study_agent.tools.registry"
    assert RuntimeRegistries.__module__ == "study_agent.playbooks.runtime"
    assert not issubclass(StudyToolRegistry, RuntimeRegistries)


def test_grounding_ask_is_not_a_playbook_required_tool() -> None:
    required = tuple(
        f"{step.tool.id}@{step.tool.version}"
        for step in GROUNDED_ANSWER_FLOW.steps
        if isinstance(step, ToolStep)
    )
    assert required == ("session.get_context@1.0.0", "source.search@1.0.0")
    assert all(not item.startswith("grounding.ask@") for item in required)


def test_core_tool_boundaries_do_not_import_provider_or_transport_frameworks() -> None:
    forbidden = ("openai", "deepseek", "anthropic", "httpx", "requests", "mcp", "tau")
    checked = (
        ROOT / "ports" / "tools.py",
        ROOT / "tools" / "contracts.py",
        ROOT / "tools" / "registry.py",
        ROOT / "tools" / "playbook_bridge.py",
    )
    for path in checked:
        tree = ast.parse(path.read_text())
        imports = tuple(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ) + tuple(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(
            imported == item or imported.startswith(item + ".")
            for imported in imports
            for item in forbidden
        ), path
