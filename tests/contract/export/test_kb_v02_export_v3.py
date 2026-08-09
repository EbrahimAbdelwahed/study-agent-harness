from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from study_agent.application import ExportBundleV3, ExportService, ExportVersion
from study_agent.domain import (
    Actor,
    CorrelationId,
    CourseId,
    DomainEvent,
    PrincipalKind,
    RevisionRef,
    ScopeId,
    ScopePolicy,
    SourceId,
    SourceSuccession,
    scope_event_id_for,
    substrate_production_event_id_for,
)
from study_agent.ingestion import (
    SOURCE_SUBSTRATE_PRODUCED,
    SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION,
    TextIngestionService,
    decode_source_revision_ingested,
    source_substrate_produced_payload,
)
from study_agent.ingestion.identity import source_superseded_by_event_id_for
from study_agent.ingestion.succession import (
    SOURCE_SUPERSEDED_BY,
    SOURCE_SUPERSEDED_BY_SCHEMA_VERSION,
    source_superseded_by_payload,
)
from study_agent.knowledge import (
    SCOPE_CONFIGURED,
    SCOPE_CONFIGURED_SCHEMA_VERSION,
    SCOPE_MEMBERSHIP_CHANGED,
    SCOPE_MEMBERSHIP_SCHEMA_VERSION,
    ScopeConfigured,
    ScopeMembershipChanged,
)
from study_agent.knowledge.scopes import scope_configured_payload, scope_membership_payload
from tests.contract.export.test_deterministic_export import (
    COURSE,
    NOW,
    _context,
    _stack,
)
from tests.unit.knowledge.test_substrate_contracts import make_production


class ReadOnlyEvents:
    def __init__(self, values: Sequence[DomainEvent]) -> None:
        self.values = tuple(values)

    def read(self, course_id: CourseId, after_sequence: int = 0) -> Sequence[DomainEvent]:
        assert course_id == COURSE
        return self.values[after_sequence:]

    def append(self, course_id: CourseId, expected_sequence: int, events: object) -> int:
        del course_id, expected_sequence, events
        raise AssertionError("export is read-only")


def test_v3_replays_kb_v02_substrate_lineage_and_scope_events(tmp_path: Path) -> None:
    blobs, events, courses, _ = _stack(tmp_path)
    TextIngestionService(
        blobs=blobs, events=events, clock=_Clock(), courses=courses
    ).ingest(
        filename="/Users/private/medical-secret-v2.md",
        content=b"Aortic valve updated content.",
        source_id=SourceId("source-aortic"),
        title="Aortic valve notes v2",
        trust_level=95,
        source_role="primary",
        context=_context(),
    )
    base = tuple(events.read(COURSE))
    predecessor = decode_source_revision_ingested(base[1].payload).source
    successor = decode_source_revision_ingested(base[3].payload).source

    succession = SourceSuccession(
        RevisionRef(predecessor.source_id, predecessor.revision_id),
        RevisionRef(successor.source_id, successor.revision_id),
        "updated lecture notes",
    )
    succession_payload = source_superseded_by_payload(succession)
    succession_event = DomainEvent(
        source_superseded_by_event_id_for(
            COURSE,
            predecessor.source_id,
            predecessor.revision_id,
            successor.source_id,
            successor.revision_id,
            5,
        ),
        COURSE,
        5,
        SOURCE_SUPERSEDED_BY,
        SOURCE_SUPERSEDED_BY_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "kb-worker"),
        NOW,
        CorrelationId("kb-v02"),
        succession_payload,
    )

    production = make_production(produced_at=NOW)
    substrate_event = DomainEvent(
        substrate_production_event_id_for(
            COURSE, production.substrate_production_id, 6
        ),
        COURSE,
        6,
        SOURCE_SUBSTRATE_PRODUCED,
        SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "kb-worker"),
        NOW,
        CorrelationId("kb-v02"),
        source_substrate_produced_payload(production),
    )

    scope = ScopeId("exam-scope")
    configured = ScopeConfigured(scope, ScopePolicy())
    configured_payload = scope_configured_payload(configured)
    configured_event = DomainEvent(
        scope_event_id_for(COURSE, scope, "configure", configured_payload, 7),
        COURSE,
        7,
        SCOPE_CONFIGURED,
        SCOPE_CONFIGURED_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "kb-worker"),
        NOW,
        CorrelationId("kb-v02"),
        configured_payload,
    )
    membership = ScopeMembershipChanged(scope, SourceId("source-aortic"), "add")
    membership_payload = scope_membership_payload(membership)
    membership_event = DomainEvent(
        scope_event_id_for(COURSE, scope, "add", membership_payload, 8),
        COURSE,
        8,
        SCOPE_MEMBERSHIP_CHANGED,
        SCOPE_MEMBERSHIP_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "kb-worker"),
        NOW,
        CorrelationId("kb-v02"),
        membership_payload,
    )

    stream = (*base, succession_event, substrate_event, configured_event, membership_event)
    bundle = ExportService(ReadOnlyEvents(stream)).assemble(
        COURSE, version=ExportVersion.V3
    )

    assert isinstance(bundle, ExportBundleV3)
    assert tuple(event["event_type"] for event in bundle.events[-4:]) == (
        SOURCE_SUPERSEDED_BY,
        SOURCE_SUBSTRATE_PRODUCED,
        SCOPE_CONFIGURED,
        SCOPE_MEMBERSHIP_CHANGED,
    )
    blobs.close()


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 7, 12, 12, 34, 56, 789012, tzinfo=UTC)
