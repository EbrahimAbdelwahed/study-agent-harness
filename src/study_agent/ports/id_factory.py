"""Host-supplied typed identifier creation.

The harness never reaches for a process-global UUID source.  A host can inject
an implementation that derives IDs from a deterministic fixture, a database,
or its own secure source of entropy.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from study_agent.domain.identifiers import Identifier

IdentifierT = TypeVar("IdentifierT", bound=Identifier)


@runtime_checkable
class IdFactory(Protocol):
    """Create one typed opaque identifier at the host boundary."""

    def new(self, identifier_type: type[IdentifierT]) -> IdentifierT: ...


# The explicit ``IdFactory`` spelling is the package contract.  This alias
# follows the existing ``ClockPort`` convention for older host integrations.
IdFactoryPort = IdFactory


__all__ = ["IdFactory", "IdFactoryPort", "IdentifierT"]
