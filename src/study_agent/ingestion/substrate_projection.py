"""Deterministic projection for canonical substrate production receipts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.events import DomainEvent
from study_agent.domain.substrate import SubstrateProduction


def substrate_manifest(production: SubstrateProduction) -> JsonObject:
    """Encode only the bytes-owned substrate identity in projection state."""
    substrate = production.substrate
    return {
        "blob": {
            "byte_length": substrate.blob.byte_length,
            "checksum_sha256": substrate.blob.checksum_sha256,
            "id": str(substrate.blob.id),
        },
        "character_length": substrate.normalized_character_length,
        "substrate_id": str(substrate.substrate_id),
    }


def production_manifest(production: SubstrateProduction) -> JsonObject:
    """Encode the complete immutable conversion receipt."""
    return production.to_json()


def reduce_substrate_produced(
    state: JsonObject, _: DomainEvent, production: SubstrateProduction
) -> Mapping[str, JsonValue]:
    """Append one immutable production to the replayable substrate view."""
    substrates = dict(_mapping(state.get("substrates", {}), "substrates"))
    productions = dict(
        _mapping(state.get("substrate_productions", {}), "substrate_productions")
    )
    by_source = dict(
        _mapping(
            state.get("substrate_productions_by_source", {}),
            "substrate_productions_by_source",
        )
    )
    production_id = str(production.substrate_production_id)
    substrate_id = str(production.substrate.substrate_id)
    production_value = production_manifest(production)
    substrate_value = substrate_manifest(production)

    existing_production = productions.get(production_id)
    if existing_production is not None and existing_production != production_value:
        raise ValueError("substrate production id already exists with different metadata")
    existing_substrate = substrates.get(substrate_id)
    if existing_substrate is not None:
        # ``substrate_id`` is bytes-only.  Page maps and normalization policy
        # belong to the production receipt, so a reconversion may legitimately
        # reference the same frozen bytes with different structural metadata.
        existing_manifest = _mapping(existing_substrate, f"substrates.{substrate_id}")
        for field in ("substrate_id", "blob", "character_length"):
            if existing_manifest.get(field) != substrate_value.get(field):
                raise ValueError("substrate id already exists with different bytes")
    else:
        substrates[substrate_id] = substrate_value
    productions[production_id] = production_value

    source_id = str(production.source_id)
    source_productions_value = by_source.get(source_id, ())
    if not isinstance(source_productions_value, tuple) or any(
        not isinstance(value, str) for value in source_productions_value
    ):
        raise ValueError("substrate source production index is invalid")
    source_productions = cast(tuple[str, ...], source_productions_value)
    if production_id not in source_productions:
        source_productions = (*source_productions, production_id)
    by_source[source_id] = source_productions
    return {
        **state,
        "substrates": substrates,
        "substrate_productions": productions,
        "substrate_productions_by_source": by_source,
    }


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"projection field {name} must be an object")
    return value

__all__ = [
    "production_manifest",
    "reduce_substrate_produced",
    "substrate_manifest",
]
