"""Offline KB-13 evidence assembly over admitted lexical bindings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from study_agent.domain.citation_v2 import TextCitationV2
from study_agent.domain.evidence import (
    EvidenceExpansion,
    EvidencePacket,
    EvidencePacketStatus,
    EvidenceRow,
)
from study_agent.domain.identifiers import ScopeId, SubstrateId, UnitId
from study_agent.domain.units import RetrievableUnit, TextSpan
from study_agent.knowledge.citation import text_citation_for, verify_text_citation
from study_agent.ports.knowledge import LexicalProjectionBinding
from study_agent.ports.retrievers import RetrieverQuery

from .fusion import (
    FusedEvidenceGroup,
    FusionContextAttachment,
    FusionPolicy,
    FusionResultStatus,
    fuse_candidates,
)
from .registry import RetrieverRegistry


class EvidenceAssemblyError(ValueError):
    """The canonical catalog cannot safely support the requested evidence."""


@dataclass(frozen=True, slots=True)
class EvidenceCatalog:
    """Scope bindings checked against separately supplied canonical records."""

    bindings: tuple[LexicalProjectionBinding, ...]
    canonical_units: tuple[RetrievableUnit, ...]
    canonical_substrates: Mapping[SubstrateId, bytes]

    def __post_init__(self) -> None:
        values = tuple(self.bindings)
        if not values:
            raise ValueError("evidence catalog requires at least one lexical binding")
        if any(not isinstance(item, LexicalProjectionBinding) for item in values):
            raise TypeError("evidence catalog requires lexical projection bindings")
        keys = {(item.scope_id, item.unit_id) for item in values}
        if len(keys) != len(values):
            raise ValueError("evidence catalog contains duplicate scope/unit bindings")
        canonical_units = tuple(self.canonical_units)
        if not canonical_units or any(
            not isinstance(item, RetrievableUnit) for item in canonical_units
        ):
            raise TypeError("evidence catalog requires canonical retrievable units")
        canonical_by_id = {item.unit_id: item for item in canonical_units}
        if len(canonical_by_id) != len(canonical_units):
            raise ValueError("canonical units must not repeat unit ids")
        substrates = dict(self.canonical_substrates)
        for substrate_id, substrate_bytes in substrates.items():
            if not isinstance(substrate_id, SubstrateId) or not isinstance(substrate_bytes, bytes):
                raise TypeError("canonical substrates must map SubstrateId to bytes")
        for item in values:
            canonical = canonical_by_id.get(item.unit_id)
            if canonical != item.unit:
                raise ValueError("binding unit is not the canonical unit")
            reference = canonical.canonical_ref
            if not isinstance(reference, TextSpan):
                raise ValueError("KB-13 baseline supports text units only")
            if substrates.get(reference.substrate_id) != item.substrate_bytes:
                raise ValueError("binding substrate is not the canonical substrate")
        object.__setattr__(
            self,
            "bindings",
            tuple(sorted(values, key=lambda item: (str(item.scope_id), str(item.unit_id)))),
        )
        object.__setattr__(self, "canonical_units", tuple(canonical_by_id.values()))
        object.__setattr__(self, "canonical_substrates", substrates)

    def for_scope(self, scope_id: ScopeId) -> tuple[LexicalProjectionBinding, ...]:
        if not isinstance(scope_id, ScopeId):
            raise TypeError("scope_id must be ScopeId")
        return tuple(
            item for item in self.bindings if item.scope_id == scope_id and item.scope_member
        )

    def canonical_binding(self, binding: LexicalProjectionBinding) -> LexicalProjectionBinding:
        """Return a binding rebuilt from canonical unit and substrate records."""
        canonical = next(
            (item for item in self.canonical_units if item.unit_id == binding.unit_id), None
        )
        if canonical is None or canonical != binding.unit:
            raise EvidenceAssemblyError("binding does not resolve to its canonical unit")
        reference = canonical.canonical_ref
        if not isinstance(reference, TextSpan):
            raise EvidenceAssemblyError("KB-13 baseline supports text units only")
        substrate_bytes = self.canonical_substrates.get(reference.substrate_id)
        if substrate_bytes is None or substrate_bytes != binding.substrate_bytes:
            raise EvidenceAssemblyError("binding does not resolve to its canonical substrate")
        return LexicalProjectionBinding(
            binding.scope_id,
            binding.projection,
            canonical,
            substrate_bytes,
            binding.selection_status,
            binding.scope_member,
        )


class EvidenceService:
    """Expose search/expand/resolve without a model, planner, or transport layer."""

    def __init__(self, *, registry: RetrieverRegistry, catalog: EvidenceCatalog) -> None:
        if not isinstance(registry, RetrieverRegistry):
            raise TypeError("registry must be RetrieverRegistry")
        if not isinstance(catalog, EvidenceCatalog):
            raise TypeError("catalog must be EvidenceCatalog")
        if len(registry.manifests) != 1 or registry.manifests[0].name != "lex_projection":
            raise ValueError("EvidenceService currently supports only lex_projection retrieval")
        self._registry = registry
        self._catalog = catalog

    def search(self, *, scope_id: ScopeId, query: str, policy: FusionPolicy) -> EvidencePacket:
        """Discover candidates then re-resolve each returned row from canonical bytes."""
        if not isinstance(scope_id, ScopeId):
            raise TypeError("scope_id must be ScopeId")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be non-empty text")
        if not isinstance(policy, FusionPolicy):
            raise TypeError("policy must be FusionPolicy")
        bindings = self._catalog.for_scope(scope_id)
        if not bindings:
            return EvidencePacket(
                scope_id,
                query,
                EvidencePacketStatus.INSUFFICIENT,
                self._registry.fingerprint(),
                (),
                "empty_scope",
            )
        batch = self._registry.search(RetrieverQuery(scope_id, query, limit=policy.max_results))
        units = {binding.unit_id: binding.unit for binding in bindings}
        fused = fuse_candidates(batch, units, policy)
        if fused.status is FusionResultStatus.INSUFFICIENT:
            return EvidencePacket(
                scope_id,
                query,
                EvidencePacketStatus.INSUFFICIENT,
                batch.registry_fingerprint,
                (),
                fused.reason,
            )
        by_unit = {binding.unit_id: binding for binding in bindings}
        rows = tuple(self._row(group.primary_unit, group, by_unit) for group in fused.groups)
        return EvidencePacket(
            scope_id,
            query,
            EvidencePacketStatus.READY,
            batch.registry_fingerprint,
            rows,
        )

    def resolve(self, *, scope_id: ScopeId, unit_id: UnitId) -> EvidenceRow:
        """Resolve one explicitly addressed unit through the same citation gate."""
        if not isinstance(unit_id, UnitId):
            raise TypeError("unit_id must be UnitId")
        binding = next(
            (item for item in self._catalog.for_scope(scope_id) if item.unit_id == unit_id), None
        )
        if binding is None:
            raise EvidenceAssemblyError("unit is not a member of the requested scope")
        return self._resolved_row(binding, score=0.0, retrievers=("direct_resolve",), expansions=())

    def _row(
        self,
        unit: RetrievableUnit,
        group: FusedEvidenceGroup,
        by_unit: Mapping[UnitId, LexicalProjectionBinding],
    ) -> EvidenceRow:
        binding = by_unit.get(unit.unit_id)
        if binding is None:
            raise EvidenceAssemblyError("fused unit lacks a canonical lexical binding")
        expansions = tuple(self._expansion(item, by_unit) for item in group.attachments)
        return self._resolved_row(
            binding,
            score=group.score,
            retrievers=group.retriever_provenance,
            expansions=expansions,
        )

    def _expansion(
        self,
        attachment: FusionContextAttachment,
        by_unit: Mapping[UnitId, LexicalProjectionBinding],
    ) -> EvidenceExpansion:
        binding = by_unit.get(attachment.unit.unit_id)
        if binding is None:
            raise EvidenceAssemblyError("fusion attachment lacks a canonical lexical binding")
        citation, text = self._citation(self._catalog.canonical_binding(binding))
        return EvidenceExpansion(attachment.relation, citation, text, binding.selection_status)

    @staticmethod
    def _citation(binding: LexicalProjectionBinding) -> tuple[TextCitationV2, str]:
        reference = binding.unit.canonical_ref
        if not isinstance(reference, TextSpan):
            raise EvidenceAssemblyError("KB-13 baseline supports text units only")
        citation = text_citation_for(
            binding.unit,
            substrate_bytes=binding.substrate_bytes,
            start=reference.start,
            end=reference.end,
        )
        resolved = verify_text_citation(
            citation,
            substrate_bytes=binding.substrate_bytes,
            unit=binding.unit,
            selection_status=binding.selection_status,
        )
        if resolved.text is None:
            raise EvidenceAssemblyError("text citation resolved without canonical text")
        return citation, resolved.text

    def _resolved_row(
        self,
        binding: LexicalProjectionBinding,
        *,
        score: float,
        retrievers: Sequence[str],
        expansions: tuple[EvidenceExpansion, ...],
    ) -> EvidenceRow:
        canonical = self._catalog.canonical_binding(binding)
        citation, text = self._citation(canonical)
        return EvidenceRow(
            canonical.unit_id,
            canonical.projection_id,
            citation,
            text,
            canonical.selection_status,
            score,
            tuple(retrievers),
            canonical.projection.projector_name,
            canonical.projection.projector_version,
            expansions,
        )


__all__ = ["EvidenceAssemblyError", "EvidenceCatalog", "EvidenceService"]
