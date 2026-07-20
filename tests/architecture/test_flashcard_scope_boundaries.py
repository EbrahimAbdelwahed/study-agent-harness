from __future__ import annotations

import ast
from pathlib import Path

from study_agent.tools import public_study_tool_manifests

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


def _violations(path: Path, forbidden: tuple[str, ...]) -> list[str]:
    return sorted(
        item
        for item in _imports(path)
        if any(item == prefix or item.startswith(prefix + ".") for prefix in forbidden)
    )


def test_flashcard_values_keep_ports_tools_and_capabilities_outward() -> None:
    forbidden = (
        "study_agent.ports",
        "study_agent.tools",
        "study_agent.capabilities",
        "study_agent.playbooks",
        "study_agent.adapters",
    )
    assert _violations(ROOT / "flashcards" / "scope.py", forbidden) == []
    assert _violations(ROOT / "flashcards" / "__init__.py", forbidden) == []


def test_flashcard_ports_do_not_reverse_import_tools_playbooks_or_capabilities() -> None:
    assert _violations(
        ROOT / "ports" / "flashcard.py",
        (
            "study_agent.tools",
            "study_agent.playbooks",
            "study_agent.capabilities",
            "study_agent.adapters",
        ),
    ) == []


def test_private_bridge_is_the_only_foundation_file_joining_port_and_playbook_contracts() -> None:
    bridge_imports = _imports(ROOT / "tools" / "flashcard_scope_bridge.py")
    assert "study_agent.ports.flashcard" in bridge_imports
    assert "study_agent.playbooks" in bridge_imports
    assert _violations(
        ROOT / "tools" / "flashcard_scope_bridge.py",
        ("study_agent.capabilities", "study_agent.adapters", "study_agent.state"),
    ) == []


def test_foundation_adds_no_capability_event_state_or_provider_owner() -> None:
    paths = (
        ROOT / "flashcards" / "scope.py",
        ROOT / "ports" / "flashcard.py",
        ROOT / "tools" / "flashcard_scope_bridge.py",
    )
    forbidden = (
        "study_agent.capabilities",
        "study_agent.state",
        "study_agent.artifacts.events",
        "study_agent.adapters",
        "openai",
        "anthropic",
        "deepseek",
    )
    assert {str(path): _violations(path, forbidden) for path in paths} == {
        str(path): [] for path in paths
    }


def test_public_study_tool_surface_remains_exactly_seven() -> None:
    assert tuple(item.name for item in public_study_tool_manifests()) == (
        "citation.resolve",
        "course.get",
        "grounding.ask",
        "session.get_context",
        "session.record_note",
        "source.list",
        "source.search",
    )
