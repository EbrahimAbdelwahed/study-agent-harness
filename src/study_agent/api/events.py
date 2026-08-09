"""Curated event envelope and upcasting boundary."""

from study_agent.domain.events import Actor, EventEnvelope, PrincipalKind
from study_agent.events.upcasting import EventUpcasterRegistry

__all__ = ["Actor", "EventEnvelope", "EventUpcasterRegistry", "PrincipalKind"]
