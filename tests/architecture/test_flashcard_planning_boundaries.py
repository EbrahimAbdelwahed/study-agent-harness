from __future__ import annotations

import ast
from pathlib import Path

from study_agent.tools import public_study_tool_manifests
from study_agent.tools.flashcard_scope_bridge import BoundFlashcardScopeExecutor

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


def test_planning_values_do_not_import_behavior_provider_or_state_owners() -> None:
    assert (
        _violations(
            ROOT / "flashcards" / "planning.py",
            (
                "study_agent.prompts",
                "study_agent.skills",
                "study_agent.playbooks",
                "study_agent.capabilities",
                "study_agent.adapters",
                "study_agent.state",
                "openai",
                "anthropic",
                "deepseek",
            ),
        )
        == []
    )


def test_planning_port_does_not_reverse_import_tools_or_behavior_layers() -> None:
    assert (
        _violations(
            ROOT / "ports" / "flashcard_planning.py",
            (
                "study_agent.tools",
                "study_agent.prompts",
                "study_agent.skills",
                "study_agent.playbooks",
                "study_agent.capabilities",
                "study_agent.adapters",
                "study_agent.state",
            ),
        )
        == []
    )


def test_planning_modules_define_no_public_tool_or_provider_specific_surface() -> None:
    paths = (
        ROOT / "flashcards" / "planning.py",
        ROOT / "ports" / "flashcard_planning.py",
    )
    forbidden_names = {
        "StudyTool",
        "ToolManifest",
        "ModelClient",
        "OpenAI",
        "Anthropic",
        "DeepSeek",
        "LearnerState",
    }
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defined = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert defined.isdisjoint(forbidden_names)


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
    assert BoundFlashcardScopeExecutor.name == "source.prepare_flashcard_scope@1"
    assert str(BoundFlashcardScopeExecutor.behavior_version) == "1.0.0"
