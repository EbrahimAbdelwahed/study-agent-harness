"""Closed deterministic discovery for trusted tutor capabilities.

Capability discovery is deliberately boring: a host gives the registry an
explicit collection of manifests and the registry freezes that collection.
There is no package scan, entry-point lookup, or import-time registration in
this module.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

from .contracts import CapabilityManifest, TutorCapabilityId

if TYPE_CHECKING:
    from study_agent.kernel.module import KernelModule


def _manifest_id(manifest: CapabilityManifest) -> object:
    """Return the stable id value without depending on provider objects."""

    return manifest.id


def _manifest_identity(manifest: CapabilityManifest) -> str:
    identity = manifest.identity
    if not isinstance(identity, str) or not identity.strip() or identity != identity.strip():
        raise ValueError("capability manifest identity must be non-empty text")
    return identity


def _namespace(value: object) -> str | None:
    candidate = value.value if isinstance(value, TutorCapabilityId) else value
    if not isinstance(candidate, str):
        return None
    prefix, separator, _ = candidate.partition(".")
    return prefix if separator else None


def _validate_namespace(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("capability namespace must be non-empty and trimmed")
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in value):
        raise ValueError("capability namespace must be lowercase and namespaced")
    if value[0] not in "abcdefghijklmnopqrstuvwxyz0123456789":
        raise ValueError("capability namespace must start with an alphanumeric character")
    return value


def _manifest_namespace(manifest: CapabilityManifest) -> str | None:
    return _namespace(_manifest_id(manifest))


class StudyCapabilityRegistry:
    """An immutable catalog assembled only by the trusted composition root."""

    __slots__ = ("_by_id", "_by_identity", "_manifests", "_namespace")

    def __init__(
        self,
        manifests: Iterable[CapabilityManifest],
        *,
        namespace: str | None = None,
    ) -> None:
        if isinstance(manifests, (str, bytes, bytearray, Mapping)):
            raise TypeError("capability registry requires an iterable of manifests")
        values = tuple(manifests)
        if not all(isinstance(item, CapabilityManifest) for item in values):
            raise TypeError("capability registry accepts only CapabilityManifest values")
        normalized_namespace = (
            None if namespace is None else _validate_namespace(namespace)
        )
        identities = tuple(_manifest_identity(item) for item in values)
        if len(set(identities)) != len(identities):
            raise ValueError("capability manifest identities must be unique")
        ids = tuple(_manifest_id(item) for item in values)
        if len(set(ids)) != len(ids):
            raise ValueError("v1 permits only one version of each capability id")
        if normalized_namespace is not None:
            for item in values:
                item_namespace = _manifest_namespace(item)
                if item_namespace is not None and item_namespace != normalized_namespace:
                    raise ValueError("capability manifest is outside the trusted namespace")

        self._manifests = tuple(sorted(values, key=lambda item: item.identity))
        self._by_id = MappingProxyType({item.id: item for item in self._manifests})
        self._by_identity = MappingProxyType(
            {item.identity: item for item in self._manifests}
        )
        self._namespace = normalized_namespace

    @classmethod
    def from_module(
        cls,
        module: KernelModule,
        *,
        namespace: str | None = None,
    ) -> StudyCapabilityRegistry:
        """Build a catalog from one explicit host module contribution.

        Kernel modules may still carry opaque non-capability registrations for
        event/runtime compatibility. Only typed ``CapabilityManifest`` values
        enter this catalog; no other object is inspected or imported.
        """

        registrations = getattr(module, "capabilities", None)
        if registrations is None:
            raise TypeError("capability registry requires a KernelModule contribution")
        trusted_namespace = namespace
        if trusted_namespace is None:
            trusted_namespace = getattr(module, "module_id", None)
        typed: list[CapabilityManifest] = []
        for registration in registrations:
            if not isinstance(registration, tuple) or len(registration) != 2:
                raise ValueError("capability registrations must be named pairs")
            name, candidate = registration
            if not isinstance(name, str) or not name.strip():
                raise ValueError("capability registration name must be non-empty text")
            if isinstance(candidate, CapabilityManifest):
                if trusted_namespace is not None and not name.startswith(
                    f"{trusted_namespace}."
                ):
                    raise ValueError("capability registration is outside the trusted namespace")
                typed.append(candidate)
        return cls(typed, namespace=namespace)

    def discover(self) -> tuple[CapabilityManifest, ...]:
        return self._manifests

    @property
    def namespace(self) -> str | None:
        return self._namespace

    def get(self, capability_id: TutorCapabilityId) -> CapabilityManifest:
        if not isinstance(capability_id, TutorCapabilityId):
            raise TypeError("capability id must use TutorCapabilityId")
        try:
            return self._by_id[capability_id]
        except KeyError as error:
            raise KeyError(f"capability is not registered: {capability_id.value}") from error

    def get_identity(self, identity: str) -> CapabilityManifest:
        """Resolve one exact immutable manifest identity."""

        if not isinstance(identity, str) or not identity.strip() or identity != identity.strip():
            raise TypeError("capability identity must be non-empty text")
        try:
            return self._by_identity[identity]
        except KeyError as error:
            raise KeyError(f"capability is not registered: {identity}") from error
