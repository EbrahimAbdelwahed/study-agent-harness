"""Provider-neutral inward seam for host-installed workaround execution receipts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from study_agent.feedback.workarounds import (
        WorkaroundExecutionReceipt,
        WorkaroundTask,
    )


class WorkaroundExecutor(Protocol):
    """A host may inject an executor; the core never implements or discovers one."""

    def execute(
        self, task: WorkaroundTask, manifest_identity: str
    ) -> WorkaroundExecutionReceipt: ...


__all__ = ["WorkaroundExecutor"]
