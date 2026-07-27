"""Immutable, provider-neutral registry for bounded retriever ports."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from study_agent.ports.retrievers import (
    RetrieverCandidateList,
    RetrieverHostAuthority,
    RetrieverManifest,
    RetrieverNetwork,
    RetrieverPort,
    RetrieverQuery,
    RetrieverSearchBatch,
    RetrieverSkipReason,
    RetrieverSkipReceipt,
)


class RetrieverRegistryError(ValueError):
    """A registry or adapter violated the portable retriever contract."""


@dataclass(frozen=True, slots=True)
class _Registration:
    port: RetrieverPort
    manifest: RetrieverManifest
    manifest_fingerprint: str


class RetrieverRegistry:
    """Constructor-only registry with host-authorized deterministic fan-out."""

    __slots__ = ("_authority", "_registrations", "_sealed")
    _authority: RetrieverHostAuthority
    _registrations: tuple[_Registration, ...]
    _sealed: bool

    def __init__(
        self,
        retrievers: tuple[RetrieverPort, ...] | list[RetrieverPort],
        authority: RetrieverHostAuthority,
    ) -> None:
        if not isinstance(authority, RetrieverHostAuthority):
            raise TypeError("authority must be RetrieverHostAuthority")
        values = tuple(retrievers)
        if not values:
            raise ValueError("registry requires the lex_projection baseline")
        registrations: list[_Registration] = []
        identities: set[str] = set()
        names: set[str] = set()
        surfaces: set[str] = set()
        for port in values:
            try:
                manifest = port.manifest
            except Exception as error:
                raise RetrieverRegistryError("retriever manifest could not be loaded") from error
            if not isinstance(manifest, RetrieverManifest):
                raise RetrieverRegistryError("retriever manifest must be RetrieverManifest")
            if manifest.identity in identities:
                raise RetrieverRegistryError("duplicate retriever manifest identity")
            if manifest.name in names:
                raise RetrieverRegistryError("duplicate active retriever name")
            if manifest.surface in surfaces:
                raise RetrieverRegistryError("duplicate retriever surface")
            identities.add(manifest.identity)
            names.add(manifest.name)
            surfaces.add(manifest.surface)
            registrations.append(_Registration(port, manifest, manifest.fingerprint))
        baseline = [item for item in registrations if item.manifest.name == "lex_projection"]
        if len(baseline) != 1:
            raise RetrieverRegistryError("registry requires exactly one lex_projection baseline")
        baseline_manifest = baseline[0].manifest
        if (
            baseline_manifest.surface != "lex_projection"
            or baseline_manifest.cost.value != "free"
            or baseline_manifest.network is not RetrieverNetwork.NEVER
            or baseline_manifest.required_capability is not None
            or baseline_manifest.provider_id is not None
            or baseline_manifest.model_id is not None
        ):
            raise RetrieverRegistryError("lex_projection baseline must be free and offline")
        object.__setattr__(self, "_authority", authority)
        object.__setattr__(
            self,
            "_registrations",
            tuple(sorted(registrations, key=lambda item: item.manifest.identity)),
        )
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("retriever registry is immutable")
        object.__setattr__(self, name, value)

    @property
    def authority(self) -> RetrieverHostAuthority:
        return self._authority

    @property
    def host_fingerprint(self) -> str:
        return self._authority.fingerprint

    @property
    def manifests(self) -> tuple[RetrieverManifest, ...]:
        return tuple(item.manifest for item in self._registrations)

    def search(self, query: RetrieverQuery) -> RetrieverSearchBatch:
        if not isinstance(query, RetrieverQuery):
            raise TypeError("query must be RetrieverQuery")
        results: list[RetrieverCandidateList] = []
        skips: list[RetrieverSkipReceipt] = []
        for registration in self._registrations:
            manifest = self._current_manifest(registration)
            reason = self._skip_reason(manifest, query)
            if reason is not None:
                skips.append(
                    RetrieverSkipReceipt(manifest.identity, manifest.fingerprint, reason)
                )
                continue
            returned = registration.port.search(query)
            self._current_manifest(registration)
            if not isinstance(returned, RetrieverCandidateList):
                raise RetrieverRegistryError("retriever returned a non-portable candidate list")
            self._validate_result(returned, query, manifest)
            results.append(returned)
        return RetrieverSearchBatch(
            query=query,
            host_fingerprint=self.host_fingerprint,
            results=tuple(results),
            skips=tuple(skips),
        )

    def _current_manifest(self, registration: _Registration) -> RetrieverManifest:
        try:
            current = registration.port.manifest
        except Exception as error:
            raise RetrieverRegistryError("retriever manifest could not be read") from error
        if not isinstance(current, RetrieverManifest):
            raise RetrieverRegistryError("retriever manifest was spoofed")
        if (
            current != registration.manifest
            or current.fingerprint != registration.manifest_fingerprint
        ):
            raise RetrieverRegistryError("retriever manifest changed after registration")
        return current

    def _skip_reason(
        self, manifest: RetrieverManifest, query: RetrieverQuery
    ) -> RetrieverSkipReason | None:
        if (
            manifest.required_capability is not None
            and manifest.required_capability not in self.authority.capabilities
        ):
            return RetrieverSkipReason.MISSING_CAPABILITY
        if (
            manifest.provider_id is not None
            and manifest.provider_id not in self.authority.provider_ids
        ):
            return RetrieverSkipReason.PROVIDER_UNAVAILABLE
        if manifest.model_id is not None and manifest.model_id not in self.authority.model_ids:
            return RetrieverSkipReason.MODEL_UNAVAILABLE
        if manifest.network is RetrieverNetwork.REQUIRED and not self.authority.network_allowed:
            return RetrieverSkipReason.NETWORK_FORBIDDEN
        if any(item.name not in manifest.supported_filters for item in query.filters):
            return RetrieverSkipReason.UNSUPPORTED_FILTER
        return None

    @staticmethod
    def _validate_result(
        result: RetrieverCandidateList,
        query: RetrieverQuery,
        manifest: RetrieverManifest,
    ) -> None:
        if result.query_fingerprint != query.fingerprint:
            raise RetrieverRegistryError("retriever returned a different query fingerprint")
        if result.retriever_identity != manifest.identity:
            raise RetrieverRegistryError("retriever returned a spoofed identity")
        if result.manifest_fingerprint != manifest.fingerprint:
            raise RetrieverRegistryError("retriever returned a spoofed manifest fingerprint")
        if result.surface != manifest.surface:
            raise RetrieverRegistryError("retriever returned a different surface")
        if result.limit != query.limit:
            raise RetrieverRegistryError("retriever returned a different query limit")
        for candidate in result.candidates:
            if candidate.query_fingerprint != query.fingerprint:
                raise RetrieverRegistryError("candidate query provenance is invalid")
            if candidate.retriever_identity != manifest.identity:
                raise RetrieverRegistryError("candidate retriever provenance is invalid")
            if candidate.manifest_fingerprint != manifest.fingerprint:
                raise RetrieverRegistryError("candidate manifest provenance is invalid")
            if candidate.surface != manifest.surface:
                raise RetrieverRegistryError("candidate surface provenance is invalid")

    def fingerprint(self) -> str:
        payload = "|".join(
            f"{item.manifest.identity}:{item.manifest_fingerprint}"
            for item in self._registrations
        ).encode("utf-8")
        return sha256(b"study-agent/retriever-registry/v1\0" + payload).hexdigest()


__all__ = ["RetrieverRegistry", "RetrieverRegistryError"]
