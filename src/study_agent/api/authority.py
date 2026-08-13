"""Closed failures and host-supplied authority facade contracts."""

from typing import TYPE_CHECKING

import study_agent.application.errors as _application_errors
import study_agent.domain.authority as _domain_authority
import study_agent.domain.errors as _domain_errors
import study_agent.ports.authority as _authority_port

if TYPE_CHECKING:
    from study_agent.application.errors import (
        failure_from_exception,
        translate_exception,
        translate_study_error,
    )
    from study_agent.domain.authority import (
        AuthorityContext,
        CancellationOutcome,
        Grant,
        IdempotencyKey,
        Principal,
        PrincipalKind,
        Scope,
        canonical_input_bytes,
        canonical_input_fingerprint,
        ensure_idempotency_compatible,
    )
    from study_agent.domain.errors import (
        ConflictFailure,
        HarnessError,
        InternalFailure,
        NotFoundFailure,
        StaleFailure,
        UnauthorizedFailure,
        UnavailableDependencyFailure,
        ValidationFailure,
    )
    from study_agent.ports.authority import AuthorityPort, HostAuthority

    __all__ = (
        "AuthorityContext",
        "AuthorityPort",
        "CancellationOutcome",
        "ConflictFailure",
        "Grant",
        "HarnessError",
        "HostAuthority",
        "IdempotencyKey",
        "InternalFailure",
        "NotFoundFailure",
        "Principal",
        "PrincipalKind",
        "Scope",
        "StaleFailure",
        "UnauthorizedFailure",
        "UnavailableDependencyFailure",
        "ValidationFailure",
        "canonical_input_bytes",
        "canonical_input_fingerprint",
        "ensure_idempotency_compatible",
        "failure_from_exception",
        "translate_exception",
        "translate_study_error",
    )

_AuthorityContext = _domain_authority.AuthorityContext
_AuthorityPort = _authority_port.AuthorityPort
_CancellationOutcome = _domain_authority.CancellationOutcome
_ConflictFailure = _domain_errors.ConflictFailure
_Grant = _domain_authority.Grant
_HarnessError = _domain_errors.HarnessError
_HostAuthority = _authority_port.HostAuthority
_IdempotencyKey = _domain_authority.IdempotencyKey
_InternalFailure = _domain_errors.InternalFailure
_NotFoundFailure = _domain_errors.NotFoundFailure
_Principal = _domain_authority.Principal
_PrincipalKind = _domain_authority.PrincipalKind
_Scope = _domain_authority.Scope
_StaleFailure = _domain_errors.StaleFailure
_UnauthorizedFailure = _domain_errors.UnauthorizedFailure
_UnavailableDependencyFailure = _domain_errors.UnavailableDependencyFailure
_ValidationFailure = _domain_errors.ValidationFailure
_canonical_input_bytes = _domain_authority.canonical_input_bytes
_canonical_input_fingerprint = _domain_authority.canonical_input_fingerprint
_ensure_idempotency_compatible = _domain_authority.ensure_idempotency_compatible
_failure_from_exception = _application_errors.failure_from_exception
_translate_exception = _application_errors.translate_exception
_translate_study_error = _application_errors.translate_study_error

# PF-01 currently treats subfacades as import targets rather than star-export
# surfaces.  Keep that boundary stable while direct typed imports remain
# available from this module.
if not TYPE_CHECKING:
    __all__ = ()

_PUBLIC = {
    "AuthorityContext": _AuthorityContext,
    "AuthorityPort": _AuthorityPort,
    "CancellationOutcome": _CancellationOutcome,
    "ConflictFailure": _ConflictFailure,
    "Grant": _Grant,
    "HarnessError": _HarnessError,
    "HostAuthority": _HostAuthority,
    "IdempotencyKey": _IdempotencyKey,
    "InternalFailure": _InternalFailure,
    "NotFoundFailure": _NotFoundFailure,
    "Principal": _Principal,
    "PrincipalKind": _PrincipalKind,
    "Scope": _Scope,
    "StaleFailure": _StaleFailure,
    "UnauthorizedFailure": _UnauthorizedFailure,
    "UnavailableDependencyFailure": _UnavailableDependencyFailure,
    "ValidationFailure": _ValidationFailure,
    "canonical_input_bytes": _canonical_input_bytes,
    "canonical_input_fingerprint": _canonical_input_fingerprint,
    "ensure_idempotency_compatible": _ensure_idempotency_compatible,
    "failure_from_exception": _failure_from_exception,
    "translate_exception": _translate_exception,
    "translate_study_error": _translate_study_error,
}


def __getattr__(name: str) -> object:
    try:
        return _PUBLIC[name]
    except KeyError:
        raise AttributeError(name) from None


def __dir__() -> list[str]:
    return [name for name in globals() if name.startswith("_")]
