"""Provider-neutral authority ports."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol

from study_agent.domain.authority import (
    AuthorityContext,
    Grant,
    IdempotencyKey,
    Principal,
    PrincipalKind,
    Scope,
)
from study_agent.domain.errors import UnauthorizedFailure


class AuthorityPort(Protocol):
    """Object-capability gate for one host-issued authority context."""

    def require(
        self,
        context: AuthorityContext,
        required_grants: Iterable[str | Grant] = (),
        required_scopes: Iterable[str | Scope] = (),
    ) -> None: ...

    def require_durable(
        self,
        context: AuthorityContext,
        required_grants: Iterable[str | Grant] = (),
        required_scopes: Iterable[str | Scope] = (),
        *,
        schema_validator: Callable[[], Any] | None = None,
        adapter: Callable[[], Any] | None = None,
    ) -> None: ...


def _required_names(
    values: Iterable[str | Grant | Scope],
    *,
    issuer: object,
    value_type: type[Grant] | type[Scope],
    label: str,
) -> frozenset[str]:
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(f"{label} must be a collection of values")
    names: set[str] = set()
    for value in values:
        if isinstance(value, (Grant, Scope)):
            if not isinstance(value, value_type):
                raise TypeError(f"{label} values must be the expected claim type")
            if value._issuer is not issuer:
                raise UnauthorizedFailure("authority claim was issued by a different host")
            names.add(value.name)
        elif isinstance(value, str) and value == value.strip() and value:
            names.add(value)
        else:
            raise TypeError(f"{label} values must be text or host-issued claims")
    return frozenset(names)


class _AuthorityGate:
    """Private gate paired with exactly one :class:`HostAuthority`."""

    __slots__ = ("_marker",)
    _marker: object

    def __init__(self, marker: object) -> None:
        object.__setattr__(self, "_marker", marker)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("authority gate is immutable")

    def _check_context(self, context: AuthorityContext) -> None:
        if not isinstance(context, AuthorityContext):
            raise UnauthorizedFailure("authority context is invalid")
        context._assert_issuer(self._marker)

    def require(
        self,
        context: AuthorityContext,
        required_grants: Iterable[str | Grant] = (),
        required_scopes: Iterable[str | Scope] = (),
    ) -> None:
        self._check_context(context)
        grants = _required_names(
            required_grants, issuer=self._marker, value_type=Grant, label="required grant"
        )
        scopes = _required_names(
            required_scopes, issuer=self._marker, value_type=Scope, label="required scope"
        )
        missing_grants = sorted(grants - context._grant_names())
        missing_scopes = sorted(scopes - context._scope_names())
        if missing_grants or missing_scopes:
            raise UnauthorizedFailure(
                "caller lacks the required authority",
                correlation_id=context.correlation_id,
                details={"missing_grants": missing_grants, "missing_scopes": missing_scopes},
            )

    def require_durable(
        self,
        context: AuthorityContext,
        required_grants: Iterable[str | Grant] = (),
        required_scopes: Iterable[str | Scope] = (),
        *,
        schema_validator: Callable[[], Any] | None = None,
        adapter: Callable[[], Any] | None = None,
    ) -> None:
        self._check_context(context)
        # This guard deliberately precedes claim normalization and callbacks.
        if context.principal_kind is PrincipalKind.MODEL:
            raise UnauthorizedFailure(
                "model authority cannot commit durable effects",
                correlation_id=context.correlation_id,
                details={"principal_kind": context.principal_kind.value},
            )
        self.require(context, required_grants, required_scopes)
        if schema_validator is not None:
            schema_validator()
        if adapter is not None:
            adapter()


class HostAuthority:
    """Composition-root issuer paired with a distinct capability gate."""

    __slots__ = ("_marker", "_port")

    def __init__(self) -> None:
        self._marker = object()
        self._port = _AuthorityGate(self._marker)

    @property
    def port(self) -> AuthorityPort:
        return self._port

    def issue(
        self,
        kind: PrincipalKind,
        principal_id: str,
        *,
        grants: Iterable[str | Grant] = (),
        scopes: Iterable[str | Scope] = (),
        correlation_id: str,
        session_id: str | None = None,
    ) -> AuthorityContext:
        if not isinstance(kind, PrincipalKind):
            raise TypeError("kind must be PrincipalKind")
        if isinstance(grants, (str, bytes, bytearray)):
            raise TypeError("grants must be a collection of values")
        if isinstance(scopes, (str, bytes, bytearray)):
            raise TypeError("scopes must be a collection of values")
        principal = Principal._mint(self._marker, kind, principal_id)
        issued_grants: list[Grant] = []
        for grant_value in grants:
            if isinstance(grant_value, Grant):
                if grant_value._issuer is not self._marker:
                    raise ValueError("grant belongs to a different host")
                issued_grants.append(grant_value)
            elif isinstance(grant_value, str):
                issued_grants.append(Grant._mint(self._marker, grant_value))
            else:
                raise TypeError("grant values must be text or host-issued claims")
        issued_scopes: list[Scope] = []
        for scope_value in scopes:
            if isinstance(scope_value, Scope):
                if scope_value._issuer is not self._marker:
                    raise ValueError("scope belongs to a different host")
                issued_scopes.append(scope_value)
            elif isinstance(scope_value, str):
                issued_scopes.append(Scope._mint(self._marker, scope_value))
            else:
                raise TypeError("scope values must be text or host-issued claims")
        return AuthorityContext._mint(
            self._marker,
            principal,
            tuple(issued_grants),
            tuple(issued_scopes),
            correlation_id,
            session_id,
        )

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
