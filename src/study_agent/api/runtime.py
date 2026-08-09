"""Curated event evolution and explicit kernel registration facade."""

from study_agent.events.upcasting import EventUpcasterRegistry
from study_agent.kernel.module import (
    EventSchema,
    KernelModule,
    KernelModuleRegistry,
    ModuleRegistry,
)

Registry = KernelModuleRegistry

__all__ = (
    "EventSchema",
    "EventUpcasterRegistry",
    "KernelModule",
    "KernelModuleRegistry",
    "ModuleRegistry",
    "Registry",
)
