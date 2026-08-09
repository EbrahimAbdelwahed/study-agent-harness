"""Curated event evolution and explicit kernel registration facade."""

from study_agent.events.upcasting import EventUpcasterRegistry
from study_agent.kernel.module import (
    EventSchema,
    KernelModule,
    KernelModuleRegistry,
    ModuleRegistry,
)
from study_agent.state.registry import EventRegistry

Registry = EventRegistry

__all__ = (
    "EventRegistry",
    "EventSchema",
    "EventUpcasterRegistry",
    "KernelModule",
    "KernelModuleRegistry",
    "ModuleRegistry",
    "Registry",
)
