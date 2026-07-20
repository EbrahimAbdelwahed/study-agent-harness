"""Framework-neutral public tools and private playbook bridges.

Application-backed public tools are loaded lazily so the canonical grounding use
case can import its private playbook bridge without creating an import cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .contracts import (
    IdempotencyMode,
    StudyEvent,
    StudyEventKind,
    ToolEffect,
    ToolError,
    ToolErrorCode,
    ToolManifest,
    ToolResult,
)
from .playbook_bridge import (
    BoundSessionContextExecutor,
    BoundSourceSearchExecutor,
    grounding_playbook_tools,
)
from .schema import SchemaValidationError, validate_json, validate_schema_definition

if TYPE_CHECKING:
    from .builtin import (
        CitationResolveTool,
        CourseGetTool,
        GroundingAskTool,
        SessionGetContextTool,
        SessionRecordNoteTool,
        SourceListTool,
        SourceSearchTool,
        builtin_tools,
        public_study_tool_manifests,
    )
    from .registry import StudyToolRegistry

_LAZY_BUILTINS = frozenset(
    {
        "CitationResolveTool",
        "CourseGetTool",
        "GroundingAskTool",
        "SessionGetContextTool",
        "SessionRecordNoteTool",
        "SourceListTool",
        "SourceSearchTool",
        "builtin_tools",
        "public_study_tool_manifests",
    }
)


def __getattr__(name: str) -> Any:
    if name in _LAZY_BUILTINS:
        from . import builtin

        return getattr(builtin, name)
    if name == "StudyToolRegistry":
        from .registry import StudyToolRegistry

        return StudyToolRegistry
    raise AttributeError(name)


__all__ = [
    "BoundSessionContextExecutor",
    "BoundSourceSearchExecutor",
    "CitationResolveTool",
    "CourseGetTool",
    "GroundingAskTool",
    "IdempotencyMode",
    "SchemaValidationError",
    "SessionGetContextTool",
    "SessionRecordNoteTool",
    "SourceListTool",
    "SourceSearchTool",
    "StudyEvent",
    "StudyEventKind",
    "StudyToolRegistry",
    "ToolEffect",
    "ToolError",
    "ToolErrorCode",
    "ToolManifest",
    "ToolResult",
    "builtin_tools",
    "grounding_playbook_tools",
    "public_study_tool_manifests",
    "validate_json",
    "validate_schema_definition",
]
