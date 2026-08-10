"""Curated, provider-neutral capability contracts.

The public API package exposes typed subfacades as import targets rather than
as star-export surfaces.  Keep that boundary here: callers can import the
listed contracts directly, while implementation modules and built-in product
bindings remain outside the discoverable public namespace.
"""

from typing import TYPE_CHECKING

import study_agent.capabilities.bindings as _bindings
import study_agent.capabilities.contracts as _contracts
import study_agent.capabilities.gateway as _gateway
import study_agent.capabilities.registry as _registry

if TYPE_CHECKING:
    from study_agent.capabilities.bindings import (
        CapabilityBinding,
        CapabilityDependencyResolver,
    )
    from study_agent.capabilities.contracts import (
        CancelledCapabilityOutcome,
        CapabilityContinuation,
        CapabilityGatewayError,
        CapabilityGatewayErrorCode,
        CapabilityId,
        CapabilityIdentifier,
        CapabilityManifest,
        CapabilityOutcome,
        CapabilityOutcomeStatus,
        CapabilityRequest,
        CompletedCapabilityOutcome,
        FailedCapabilityOutcome,
        StaleCapabilityOutcome,
        SuspendedCapabilityOutcome,
        TutorCapabilityId,
        encode_capability_outcome,
    )
    from study_agent.capabilities.gateway import StudyCapabilityGateway
    from study_agent.capabilities.registry import StudyCapabilityRegistry

    __all__ = (
        "CancelledCapabilityOutcome",
        "CapabilityBinding",
        "CapabilityContinuation",
        "CapabilityDependencyResolver",
        "CapabilityGatewayError",
        "CapabilityGatewayErrorCode",
        "CapabilityId",
        "CapabilityIdentifier",
        "CapabilityManifest",
        "CapabilityOutcome",
        "CapabilityOutcomeStatus",
        "CapabilityRequest",
        "CompletedCapabilityOutcome",
        "FailedCapabilityOutcome",
        "StaleCapabilityOutcome",
        "StudyCapabilityGateway",
        "StudyCapabilityRegistry",
        "SuspendedCapabilityOutcome",
        "TutorCapabilityId",
        "encode_capability_outcome",
    )

if not TYPE_CHECKING:
    # PF-01 treats subfacades as import targets, not star-export surfaces.
    __all__ = ()


_PUBLIC = {
    "CapabilityBinding": _bindings.CapabilityBinding,
    "CapabilityContinuation": _contracts.CapabilityContinuation,
    "CapabilityDependencyResolver": _bindings.CapabilityDependencyResolver,
    "CapabilityGatewayError": _contracts.CapabilityGatewayError,
    "CapabilityGatewayErrorCode": _contracts.CapabilityGatewayErrorCode,
    "CapabilityId": _contracts.CapabilityId,
    "CapabilityIdentifier": _contracts.CapabilityIdentifier,
    "CapabilityManifest": _contracts.CapabilityManifest,
    "CapabilityOutcome": _contracts.CapabilityOutcome,
    "CapabilityOutcomeStatus": _contracts.CapabilityOutcomeStatus,
    "CapabilityRequest": _contracts.CapabilityRequest,
    "CancelledCapabilityOutcome": _contracts.CancelledCapabilityOutcome,
    "CompletedCapabilityOutcome": _contracts.CompletedCapabilityOutcome,
    "FailedCapabilityOutcome": _contracts.FailedCapabilityOutcome,
    "StaleCapabilityOutcome": _contracts.StaleCapabilityOutcome,
    "StudyCapabilityGateway": _gateway.StudyCapabilityGateway,
    "StudyCapabilityRegistry": _registry.StudyCapabilityRegistry,
    "SuspendedCapabilityOutcome": _contracts.SuspendedCapabilityOutcome,
    "TutorCapabilityId": _contracts.TutorCapabilityId,
    "encode_capability_outcome": _contracts.encode_capability_outcome,
}


def __getattr__(name: str) -> object:
    """Resolve only the curated typed capability surface."""

    try:
        return _PUBLIC[name]
    except KeyError:
        raise AttributeError(name) from None


def __dir__() -> list[str]:
    """Keep internal implementation names out of namespace discovery."""

    return [name for name in globals() if name.startswith("_")]
