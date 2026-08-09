"""Host-supplied authority and retry identity contracts.

These values deliberately contain no credentials, provider handles, cookies, or
policy payloads.  A host creates the values and passes them into a facade call;
model output is never accepted as a source of authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ConflictFailure, StaleFailure, UnauthorizedFailure
from .events import PrincipalKind


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


class _OpaqueAuthorityValue:
    """Read-only, host-issued value with no transport or copy pathway."""

    __slots__ = ("_issuer",)
    _issuer: object

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("authority values are immutable")

    def __reduce__(self) -> str | tuple[Any, ...]:
        raise TypeError("authority values are not serializable")

    def __copy__(self) -> object:
        raise TypeError("authority values are not copyable")

    def __deepcopy__(self, memo: dict[int, object]) -> object:
        raise TypeError("authority values are not copyable")

    def __getstate__(self) -> object:
        raise TypeError("authority values are not serializable")

    def __repr__(self) -> str:
        return f"<{type(self).__name__.lower()} opaque>"

    def __str__(self) -> str:
        return self.__repr__()


class Principal(_OpaqueAuthorityValue):
    __slots__ = ("_kind", "_principal_id")
    _kind: PrincipalKind
    _principal_id: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("Principal values are issued by HostAuthority")

    @classmethod
    def _mint(cls, issuer: object, kind: PrincipalKind, principal_id: str) -> Principal:
        if not isinstance(kind, PrincipalKind):
            raise TypeError("kind must be PrincipalKind")
        principal = object.__new__(cls)
        object.__setattr__(principal, "_issuer", issuer)
        object.__setattr__(principal, "_kind", kind)
        object.__setattr__(principal, "_principal_id", _text(principal_id, "principal_id"))
        return principal

    @property
    def kind(self) -> PrincipalKind:
        return self._kind

    @property
    def principal_id(self) -> str:
        return self._principal_id


class Grant(_OpaqueAuthorityValue):
    __slots__ = ("_name",)
    _name: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("Grant values are issued by HostAuthority")

    @classmethod
    def _mint(cls, issuer: object, name: str) -> Grant:
        grant = object.__new__(cls)
        object.__setattr__(grant, "_issuer", issuer)
        object.__setattr__(grant, "_name", _text(name, "grant"))
        return grant

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> str:
        return self._name


class Scope(_OpaqueAuthorityValue):
    __slots__ = ("_name",)
    _name: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("Scope values are issued by HostAuthority")

    @classmethod
    def _mint(cls, issuer: object, name: str) -> Scope:
        scope = object.__new__(cls)
        object.__setattr__(scope, "_issuer", issuer)
        object.__setattr__(scope, "_name", _text(name, "scope"))
        return scope

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> str:
        return self._name


class AuthorityContext(_OpaqueAuthorityValue):
    """Opaque immutable context issued by one host composition root."""

    __slots__ = (
        "_correlation_id",
        "_grants",
        "_principal",
        "_scopes",
        "_session_id",
    )
    _principal: Principal
    _grants: tuple[Grant, ...]
    _scopes: tuple[Scope, ...]
    _correlation_id: str
    _session_id: str | None

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("AuthorityContext values are issued by HostAuthority")

    @classmethod
    def _mint(
        cls,
        issuer: object,
        principal: Principal,
        grants: tuple[Grant, ...],
        scopes: tuple[Scope, ...],
        correlation_id: str,
        session_id: str | None,
    ) -> AuthorityContext:
        context = object.__new__(cls)
        object.__setattr__(context, "_issuer", issuer)
        object.__setattr__(context, "_principal", principal)
        object.__setattr__(context, "_grants", grants)
        object.__setattr__(context, "_scopes", scopes)
        object.__setattr__(context, "_correlation_id", _text(correlation_id, "correlation_id"))
        object.__setattr__(
            context, "_session_id", None if session_id is None else _text(session_id, "session_id")
        )
        return context

    @property
    def principal(self) -> Principal:
        return self._principal

    @property
    def grants(self) -> tuple[Grant, ...]:
        return self._grants

    @property
    def scopes(self) -> tuple[Scope, ...]:
        return self._scopes

    @property
    def correlation_id(self) -> str:
        return self._correlation_id

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def principal_kind(self) -> PrincipalKind:
        return self._principal.kind

    @property
    def principal_id(self) -> str:
        return self._principal.principal_id

    def _assert_issuer(self, issuer: object) -> None:
        if self._issuer is not issuer:
            raise UnauthorizedFailure(
                "authority context was issued by a different host",
                correlation_id=self._correlation_id,
            )

    def _grant_names(self) -> frozenset[str]:
        return frozenset(grant.name for grant in self._grants)

    def _scope_names(self) -> frozenset[str]:
        return frozenset(scope.name for scope in self._scopes)

    @staticmethod
    def check_expected_sequence(
        *, expected: int, actual: int, correlation_id: object | None = None
    ) -> None:
        if type(expected) is not int or type(actual) is not int or expected < 0 or actual < 0:
            raise ValueError("expected and actual sequence must be non-negative integers")
        if expected != actual:
            raise StaleFailure(
                "the durable stream changed before commit",
                correlation_id=correlation_id,
                details={"expected": expected, "actual": actual},
            )


def _canonical(value: object) -> object:
    if isinstance(value, Mapping):
        keys = sorted(value)
        if any(not isinstance(key, str) for key in keys):
            raise TypeError("command mappings must have string keys")
        return {key: _canonical(value[key]) for key in keys}
    if isinstance(value, (tuple, list)):
        return tuple(_canonical(item) for item in value)
    if isinstance(value, (set, frozenset)):
        members = tuple(_canonical(item) for item in value)
        return tuple(sorted(members, key=lambda item: repr(item)))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    to_json = getattr(value, "to_json", None)
    if callable(to_json):
        return _canonical(to_json())
    raise TypeError(f"unsupported command input: {type(value).__name__}")


def canonical_input_bytes(command_kind: str, value: object) -> bytes:
    kind = _text(command_kind, "command_kind")
    canonical = {"command_kind": kind, "input": _canonical(value)}
    try:
        return json.dumps(
            canonical, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("command input is not canonical JSON") from error


def canonical_input_fingerprint(command_kind: str, value: object) -> str:
    return hashlib.sha256(canonical_input_bytes(command_kind, value)).hexdigest()


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Stable durable-command retry identity and canonical input fingerprint."""

    key: str
    command_kind: str
    input_fingerprint: str

    def __post_init__(self) -> None:
        _text(self.key, "idempotency key")
        _text(self.command_kind, "command_kind")
        _text(self.input_fingerprint, "input_fingerprint")
        if len(self.input_fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in self.input_fingerprint
        ):
            raise ValueError("input_fingerprint must be a lowercase SHA-256 digest")

    @classmethod
    def from_command(cls, key: str, command_kind: str, value: object) -> IdempotencyKey:
        return cls(key, command_kind, canonical_input_fingerprint(command_kind, value))

    @classmethod
    def for_command(cls, key: str, command_kind: str, value: object) -> IdempotencyKey:
        return cls.from_command(key, command_kind, value)

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.key, self.command_kind, self.input_fingerprint

    def matches(self, command_kind: str, value: object) -> bool:
        fingerprint = canonical_input_fingerprint(command_kind, value)
        return self.command_kind == command_kind and self.input_fingerprint == fingerprint

    def to_json(self) -> dict[str, str]:
        return {
            "key": self.key,
            "command_kind": self.command_kind,
            "input_fingerprint": self.input_fingerprint,
        }


def ensure_idempotency_compatible(
    existing: IdempotencyKey, incoming: IdempotencyKey
) -> None:
    if not isinstance(existing, IdempotencyKey) or not isinstance(incoming, IdempotencyKey):
        raise TypeError("idempotency values must be IdempotencyKey")
    if existing.key != incoming.key:
        return
    changed_kind = existing.command_kind != incoming.command_kind
    changed_input = existing.input_fingerprint != incoming.input_fingerprint
    if changed_kind or changed_input:
        raise ConflictFailure(
            "idempotency key already names a different command",
            details={"idempotency_key": existing.key},
        )


@dataclass(frozen=True, slots=True)
class CancellationOutcome:
    """Cooperative cancellation result; no canonical event was appended."""

    cancelled: bool
    committed: bool
    correlation_id: str | None = None

    @classmethod
    def before_commit(cls, *, correlation_id: object | None = None) -> CancellationOutcome:
        return cls(True, False, None if correlation_id is None else str(correlation_id))

    def to_json(self) -> dict[str, object]:
        return {
            "status": "cancelled" if self.cancelled else "completed",
            "cancelled": self.cancelled,
            "committed": self.committed,
            "correlation_id": self.correlation_id,
        }


__all__ = [
    "AuthorityContext",
    "CancellationOutcome",
    "Grant",
    "IdempotencyKey",
    "Principal",
    "PrincipalKind",
    "Scope",
    "canonical_input_bytes",
    "canonical_input_fingerprint",
    "ensure_idempotency_compatible",
]
