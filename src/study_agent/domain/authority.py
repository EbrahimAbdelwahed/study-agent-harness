"""Host-supplied authority and retry identity contracts.

These values deliberately contain no credentials, provider handles, cookies, or
policy payloads.  A host creates the values and passes them into a facade call;
model output is never accepted as a source of authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ConflictFailure, StaleFailure, UnauthorizedFailure
from .events import PrincipalKind


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


@dataclass(frozen=True, slots=True)
class Principal:
    """Opaque host-created identity for one caller."""

    kind: PrincipalKind
    principal_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PrincipalKind):
            raise TypeError("kind must be PrincipalKind")
        _text(self.principal_id, "principal_id")


@dataclass(frozen=True, slots=True)
class Grant:
    """One host-issued capability grant."""

    name: str

    def __post_init__(self) -> None:
        _text(self.name, "grant")

    @property
    def value(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class Scope:
    """One host-issued resource scope, represented opaquely."""

    name: str

    def __post_init__(self) -> None:
        _text(self.name, "scope")

    @property
    def value(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name


def _names(values: Iterable[str | Grant | Scope], name: str) -> frozenset[str]:
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a collection of values")
    normalized: set[str] = set()
    for value in values:
        candidate = value.name if isinstance(value, (Grant, Scope)) else _text(value, name)
        normalized.add(candidate)
    return frozenset(normalized)


@dataclass(frozen=True, slots=True)
class AuthorityContext:
    """Immutable host authority supplied to every facade operation."""

    principal: Principal
    grants: Iterable[str | Grant] = ()
    scopes: Iterable[str | Scope] = ()
    correlation_id: str = ""
    session_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.principal, Principal):
            raise TypeError("principal must be Principal")
        object.__setattr__(self, "grants", _names(self.grants, "grant"))
        object.__setattr__(self, "scopes", _names(self.scopes, "scope"))
        object.__setattr__(self, "correlation_id", _text(self.correlation_id, "correlation_id"))
        if self.session_id is not None:
            object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))

    @property
    def principal_kind(self) -> PrincipalKind:
        return self.principal.kind

    @property
    def principal_id(self) -> str:
        return self.principal.principal_id

    @property
    def is_trusted(self) -> bool:
        return self.principal.kind in (PrincipalKind.HUMAN, PrincipalKind.SERVICE)

    def can(self, grant: str | Grant, *, scope: str | Scope | None = None) -> bool:
        grant_name = grant.name if isinstance(grant, Grant) else _text(grant, "grant")
        if grant_name not in self.grants:
            return False
        if scope is None:
            return True
        scope_name = scope.name if isinstance(scope, Scope) else _text(scope, "scope")
        return scope_name in self.scopes

    def require(
        self,
        required_grants: Iterable[str | Grant] = (),
        required_scopes: Iterable[str | Scope] = (),
        *,
        durable: bool = False,
    ) -> None:
        """Fail closed for untrusted or insufficient authority."""

        if type(durable) is not bool:
            raise TypeError("durable must be a boolean")
        if durable and self.principal.kind is PrincipalKind.MODEL:
            raise UnauthorizedFailure(
                "model authority cannot commit durable effects",
                correlation_id=self.correlation_id,
                details={"principal_kind": self.principal.kind.value},
            )
        grants = _names(required_grants, "required grant")
        scopes = _names(required_scopes, "required scope")
        owned_grants = frozenset(self.grants)
        owned_scopes = frozenset(self.scopes)
        missing_grants = sorted(grants - owned_grants)
        missing_scopes = sorted(scopes - owned_scopes)
        if missing_grants or missing_scopes:
            raise UnauthorizedFailure(
                "caller lacks the required authority",
                correlation_id=self.correlation_id,
                details={
                    "missing_grants": tuple(missing_grants),
                    "missing_scopes": tuple(missing_scopes),
                },
            )

    def require_durable(
        self,
        required_grants: Iterable[str | Grant] = (),
        required_scopes: Iterable[str | Scope] = (),
        *,
        schema_validator: Callable[[], Any] | None = None,
        adapter: Callable[[], Any] | None = None,
    ) -> None:
        """Authorize before invoking schema or adapter callbacks.

        The optional callbacks are a small testable seam used by application
        ports.  They are intentionally invoked only after the host authority
        gate passes; callers may perform their own schema and adapter work after
        this method returns.
        """

        self.require(required_grants, required_scopes, durable=True)
        if schema_validator is not None:
            schema_validator()
        if adapter is not None:
            adapter()

    def require_approval(self, *required_grants: str | Grant) -> None:
        self.require(required_grants, durable=True)

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
