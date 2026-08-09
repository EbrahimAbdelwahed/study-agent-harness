"""Provider-neutral authority ports."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from study_agent.domain.authority import (
    AuthorityContext,
    Grant,
    IdempotencyKey,
    Principal,
    PrincipalKind,
    Scope,
)


class AuthorityPort(Protocol):
    """Host-owned seam for checking an already-created authority context."""

    def authorize(
        self,
        context: AuthorityContext,
        required_grants: Iterable[str | Grant] = (),
        required_scopes: Iterable[str | Scope] = (),
        *,
        durable: bool = False,
    ) -> None: ...


class HostAuthority:
    """Small default port implementation with no global state or discovery."""

    def authorize(
        self,
        context: AuthorityContext,
        required_grants: Iterable[str | Grant] = (),
        required_scopes: Iterable[str | Scope] = (),
        *,
        durable: bool = False,
    ) -> None:
        if not isinstance(context, AuthorityContext):
            raise TypeError("context must be AuthorityContext")
        context.require(required_grants, required_scopes, durable=durable)


__all__ = [
    "AuthorityContext",
    "AuthorityPort",
    "Grant",
    "HostAuthority",
    "IdempotencyKey",
    "Principal",
    "PrincipalKind",
    "Scope",
]
