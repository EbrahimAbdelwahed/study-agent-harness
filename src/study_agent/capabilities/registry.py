"""Closed deterministic discovery for trusted tutor capabilities."""

from __future__ import annotations

from .contracts import CapabilityManifest, TutorCapabilityId


class StudyCapabilityRegistry:
    """An immutable catalog assembled only by the trusted composition root."""

    def __init__(self, manifests: tuple[CapabilityManifest, ...]) -> None:
        values = tuple(manifests)
        if not all(isinstance(item, CapabilityManifest) for item in values):
            raise TypeError("capability registry accepts only CapabilityManifest values")
        identities = tuple(item.identity for item in values)
        if len(set(identities)) != len(identities):
            raise ValueError("capability manifest identities must be unique")
        ids = tuple(item.id for item in values)
        if len(set(ids)) != len(ids):
            raise ValueError("v1 permits only one version of each capability id")
        self._manifests = tuple(sorted(values, key=lambda item: item.identity))
        self._by_id = {item.id: item for item in self._manifests}

    def discover(self) -> tuple[CapabilityManifest, ...]:
        return self._manifests

    def get(self, capability_id: TutorCapabilityId) -> CapabilityManifest:
        if not isinstance(capability_id, TutorCapabilityId):
            raise TypeError("capability id must use TutorCapabilityId")
        try:
            return self._by_id[capability_id]
        except KeyError as error:
            raise KeyError(f"capability is not registered: {capability_id.value}") from error
