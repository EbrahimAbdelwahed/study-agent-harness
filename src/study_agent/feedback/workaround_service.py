"""Selection and receipt validation boundary for static workaround manifests."""

from __future__ import annotations

from .workarounds import (
    WorkaroundExecutionReceipt,
    WorkaroundGrant,
    WorkaroundRegistry,
    WorkaroundTask,
)


class WorkaroundService:
    """Never executes; it only selects and validates trusted host receipts."""

    def __init__(self, registry: WorkaroundRegistry) -> None:
        self._registry = registry

    def select(
        self, task: WorkaroundTask, grants: frozenset[str] | tuple[WorkaroundGrant, ...]
    ) -> WorkaroundExecutionReceipt:
        return self._registry.select(task, grants)

    def record_execution(
        self,
        task: WorkaroundTask,
        receipt: WorkaroundExecutionReceipt,
        *,
        grants: frozenset[str] | tuple[WorkaroundGrant, ...],
        approved: bool = False,
    ) -> WorkaroundExecutionReceipt:
        return self._registry.validate_execution(task, receipt, granted=grants, approved=approved)


__all__ = ["WorkaroundService"]
