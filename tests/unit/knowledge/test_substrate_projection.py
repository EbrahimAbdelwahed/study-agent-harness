from __future__ import annotations

from collections.abc import Mapping

import pytest

from study_agent.domain import (
    Actor,
    CorrelationId,
    CourseId,
    DomainEvent,
    PrincipalKind,
    SubstrateProduction,
    substrate_production_event_id_for,
)
from study_agent.ingestion.projection import ensure_legacy_substrates
from study_agent.ingestion.substrate_events import (
    SOURCE_SUBSTRATE_PRODUCED,
    SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION,
    substrate_production_payload,
)
from study_agent.ingestion.substrate_projection import reduce_substrate_produced
from tests.unit.knowledge.test_substrate_contracts import make_production


def event_for(production: SubstrateProduction, sequence: int = 1) -> DomainEvent:
    course_id = CourseId("course-projection")
    return DomainEvent(
        substrate_production_event_id_for(
            course_id, production.substrate_production_id, sequence
        ),
        course_id,
        sequence,
        SOURCE_SUBSTRATE_PRODUCED,
        SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "projection-test"),
        production.produced_at,
        CorrelationId("projection-correlation"),
        substrate_production_payload(production),
    )


def test_projection_is_deterministic_and_retains_all_productions() -> None:
    first = make_production()
    second = make_production(admission_policy_version="admission-2")
    state = reduce_substrate_produced({}, event_for(first), first)
    reduced = reduce_substrate_produced(state, event_for(second, 2), second)

    substrates = reduced["substrates"]
    productions = reduced["substrate_productions"]
    assert isinstance(substrates, Mapping)
    assert isinstance(productions, Mapping)
    assert tuple(substrates) == (str(first.substrate.substrate_id),)
    assert tuple(productions) == (
        str(first.substrate_production_id),
        str(second.substrate_production_id),
    )
    assert reduced["substrate_productions_by_source"] == {
        str(first.source_id): (
            str(first.substrate_production_id),
            str(second.substrate_production_id),
        )
    }


def test_projection_rejects_corruption_for_existing_immutable_keys() -> None:
    production = make_production()
    event = event_for(production)
    state = reduce_substrate_produced({}, event, production)
    corrupted = dict(state)
    productions_value = corrupted["substrate_productions"]
    assert isinstance(productions_value, Mapping)
    productions = dict(productions_value)
    manifest_value = productions[str(production.substrate_production_id)]
    assert isinstance(manifest_value, Mapping)
    manifest = dict(manifest_value)
    manifest["converter_version"] = "forged"
    productions[str(production.substrate_production_id)] = manifest
    corrupted["substrate_productions"] = productions

    with pytest.raises(ValueError, match="different metadata"):
        reduce_substrate_produced(corrupted, event, production)


def test_projection_rejects_corrupted_source_index_shape() -> None:
    production = make_production()
    event = event_for(production)
    with pytest.raises(ValueError, match="source production index"):
        reduce_substrate_produced(
            {"substrate_productions_by_source": {str(production.source_id): "bad"}},
            event,
            production,
        )


def test_legacy_migration_is_noop_without_source_revisions() -> None:
    state = {"course": {"title": "Medicine"}}

    assert ensure_legacy_substrates(state) is state
