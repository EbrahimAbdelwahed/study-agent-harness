"""Framework-neutral public study-tool protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from study_agent.domain import ExecutionContext
from study_agent.domain._validation import JsonObject

if TYPE_CHECKING:
    from study_agent.tools.contracts import ToolManifest, ToolResult


class StudyTool(Protocol):
    @property
    def manifest(self) -> ToolManifest: ...

    async def invoke(self, arguments: JsonObject, context: ExecutionContext) -> ToolResult: ...
