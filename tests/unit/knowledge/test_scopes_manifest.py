from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from study_agent.domain import (
    WHOLE_CORPUS,
    Actor,
    AdapterAvailability,
    AvailabilityStatus,
    ConformanceSummary,
    ConnectorHint,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    ManifestSnapshot,
    PrincipalKind,
    ProjectionCoverage,
    ScopeId,
    ScopePolicy,
    ScopeSelection,
    SourceId,
    scope_event_id_for,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.knowledge.scopes import (
    SCOPE_CONFIGURED,
    SCOPE_CONFIGURED_SCHEMA_VERSION,
    SCOPE_MEMBERSHIP_CHANGED,
    SCOPE_MEMBERSHIP_SCHEMA_VERSION,
    ScopeConfigured,
    ScopeMembershipChanged,
    build_corpus_manifest,
    decode_scope_configured_event,
    decode_scope_policy,
    reduce_scope_configured,
    reduce_scope_membership,
    register_scope_events,
    scope_configured_payload,
    scope_membership_payload,
)
from study_agent.state import EventRegistry

COURSE = CourseId("course")
SCOPE_A = ScopeId("anatomia")
SOURCE_A = SourceId("book")
SOURCE_B = SourceId("transcript")
NOW = datetime(2026, 7, 27, tzinfo=UTC)


def policy(version: str = "p1", *, hints: tuple[str, ...] = ()) -> ScopePolicy:
    return ScopePolicy(
        policy_version=version,
        source_class_order=("edited", "transcript"),
        source_class_priors=(
            ("edited", 1.0),
            ("transcript", 0.8),
        ),
        aliases=(("rotator", ("cuffia", "rotatori")),),
        fragment_signal_weights=(
            ("idf", 0.5),
            ("structure", 0.5),
        ),
        answering_hints=hints,
    )


def config_event(
    payload: ScopeConfigured,
    *,
    sequence: int = 1,
    actor: PrincipalKind = PrincipalKind.SERVICE,
) -> DomainEvent:
    encoded = scope_configured_payload(payload)
    return DomainEvent(
        scope_event_id_for(COURSE, payload.scope_id, "configure", encoded, sequence),
        COURSE,
        sequence,
        SCOPE_CONFIGURED,
        SCOPE_CONFIGURED_SCHEMA_VERSION,
        Actor(actor, "scope-test"),
        NOW,
        CorrelationId("scope-correlation"),
        encoded,
    )


def membership_event(
    payload: ScopeMembershipChanged,
    *,
    sequence: int,
    actor: PrincipalKind = PrincipalKind.SERVICE,
) -> DomainEvent:
    encoded = scope_membership_payload(payload)
    return DomainEvent(
        scope_event_id_for(COURSE, payload.scope_id, payload.operation, encoded, sequence),
        COURSE,
        sequence,
        SCOPE_MEMBERSHIP_CHANGED,
        SCOPE_MEMBERSHIP_SCHEMA_VERSION,
        Actor(actor, "scope-test"),
        NOW,
        CorrelationId("scope-correlation"),
        encoded,
    )


def source_state() -> JsonObject:
    return {
        "sources": {
            str(SOURCE_A): {
                "title": "Edited book",
                "source_role": "edited",
                "revision_ids": ("rev-book",),
            },
            str(SOURCE_B): {
                "title": "Lecture transcript",
                "source_role": "transcript",
                "revision_ids": ("rev-transcript",),
            },
        },
        "units": {
            "u1": {"source_id": str(SOURCE_A), "unit_kind": "passage"},
            "u2": {"source_id": str(SOURCE_A), "unit_kind": "figure"},
            "u3": {"source_id": str(SOURCE_B), "unit_kind": "passage"},
        },
    }


def configured_state() -> JsonObject:
    state = reduce_scope_configured(
        source_state(),
        config_event(ScopeConfigured(SCOPE_A, policy())),
        ScopeConfigured(SCOPE_A, policy()),
    )
    return dict(
        reduce_scope_membership(
            state,
            membership_event(ScopeMembershipChanged(SCOPE_A, SOURCE_A, "add"), sequence=2),
            ScopeMembershipChanged(SCOPE_A, SOURCE_A, "add"),
        )
    )


def scope_row(state: JsonObject, scope_id: ScopeId) -> Mapping[str, JsonValue]:
    scopes = state["scopes"]
    assert isinstance(scopes, Mapping)
    row = scopes[str(scope_id)]
    assert isinstance(row, Mapping)
    return row


def test_policy_codec_is_strict_and_round_trips_owner_data() -> None:
    original = policy(hints=("answers factual anatomy",))
    assert decode_scope_policy(original.to_json()) == original
    with pytest.raises(ValueError, match="fields mismatch"):
        decode_scope_policy({**original.to_json(), "unexpected": True})


def test_event_identity_and_model_authority_fail_closed() -> None:
    payload = ScopeConfigured(SCOPE_A, policy())
    event = config_event(payload)
    assert decode_scope_configured_event(event) == payload
    forged = DomainEvent(
        EventId("event-sha256:" + "0" * 64),
        event.course_id,
        event.course_sequence,
        event.event_type,
        event.schema_version,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        event.payload,
    )
    with pytest.raises(ValueError, match="event_id"):
        decode_scope_configured_event(forged)
    with pytest.raises(ValueError, match="model"):
        decode_scope_configured_event(config_event(payload, actor=PrincipalKind.MODEL))


def test_registered_scope_events_decode_and_replay_through_event_registry() -> None:
    registry = EventRegistry()
    register_scope_events(registry)
    payload = ScopeConfigured(SCOPE_A, policy())
    event = config_event(payload)
    assert registry.decode(event) == payload
    state = registry.reduce(source_state(), event)
    membership = ScopeMembershipChanged(SCOPE_A, SOURCE_A, "add")
    state = registry.reduce(
        state,
        membership_event(membership, sequence=2),
    )
    assert scope_row(state, SCOPE_A)["source_ids"] == (str(SOURCE_A),)


def test_configuration_create_update_cas_and_exact_retry_are_deterministic() -> None:
    initial = ScopeConfigured(SCOPE_A, policy())
    state = reduce_scope_configured(source_state(), config_event(initial), initial)
    assert reduce_scope_configured(state, config_event(initial), initial) == state
    updated = ScopeConfigured(SCOPE_A, policy("p2"), "p1")
    changed = reduce_scope_configured(state, config_event(updated, sequence=3), updated)
    changed_policy = scope_row(changed, SCOPE_A)["policy"]
    assert isinstance(changed_policy, Mapping)
    assert changed_policy["policy_version"] == "p2"
    with pytest.raises(ValueError, match="stale"):
        stale = ScopeConfigured(SCOPE_A, policy("p3"), "p0")
        reduce_scope_configured(state, config_event(stale, sequence=4), stale)
    with pytest.raises(ValueError, match="policy version"):
        conflict = ScopeConfigured(SCOPE_A, policy("p1", hints=("different",)), "p1")
        reduce_scope_configured(state, config_event(conflict, sequence=5), conflict)


def test_membership_requires_known_scope_and_source_and_does_not_copy_units() -> None:
    state = source_state()
    add = ScopeMembershipChanged(SCOPE_A, SOURCE_A, "add")
    with pytest.raises(ValueError, match="configured"):
        reduce_scope_membership(state, membership_event(add, sequence=2), add)
    state = configured_state()
    second_scope = ScopeId("biochimica")
    config = ScopeConfigured(second_scope, policy())
    state = dict(reduce_scope_configured(state, config_event(config, sequence=5), config))
    add_second = ScopeMembershipChanged(second_scope, SOURCE_A, "add")
    state = dict(
        reduce_scope_membership(state, membership_event(add_second, sequence=6), add_second)
    )
    assert scope_row(state, SCOPE_A)["source_ids"] == (str(SOURCE_A),)
    assert scope_row(state, second_scope)["source_ids"] == (str(SOURCE_A),)
    assert "units" in state and "sources" in state
    unknown = ScopeMembershipChanged(SCOPE_A, SourceId("unknown"), "add")
    with pytest.raises(ValueError, match="unknown"):
        reduce_scope_membership(state, membership_event(unknown, sequence=7), unknown)
    absent = ScopeMembershipChanged(SCOPE_A, SOURCE_B, "remove")
    with pytest.raises(ValueError, match="absent"):
        reduce_scope_membership(state, membership_event(absent, sequence=8), absent)


def test_manifest_is_explicit_bounded_deterministic_and_labels_derived_absence() -> None:
    state = configured_state()
    snapshot = ManifestSnapshot(
        projection_coverage=(ProjectionCoverage("lexical", 1, 1),),
        adapters=(AdapterAvailability("embeddings", AvailabilityStatus.ABSENT),),
        conformance=(ConformanceSummary("scope", "degraded", ("ocr_missing",)),),
    )
    scoped = build_corpus_manifest(state, ScopeSelection.scope(SCOPE_A), snapshot=snapshot)
    assert scoped.total_units == 2
    assert scoped.total_figures == 1
    assert scoped.retrievers == ()
    assert scoped.adapters[0].status is AvailabilityStatus.ABSENT
    assert scoped.sources[0].source_id == SOURCE_A
    whole = build_corpus_manifest(source_state(), WHOLE_CORPUS, snapshot=snapshot)
    assert whole.policy is None
    assert [source.source_id for source in whole.sources] == [SOURCE_A, SOURCE_B]
    assert (
        whole.to_json()
        == build_corpus_manifest(source_state(), WHOLE_CORPUS, snapshot=snapshot).to_json()
    )


def test_manifest_hints_record_only_connector_and_trusted_scope_policy_provenance() -> None:
    state = configured_state()
    policy_payload = ScopeConfigured(SCOPE_A, policy("p2", hints=("scope hint",)), "p1")
    updated = reduce_scope_configured(
        state, config_event(policy_payload, sequence=9), policy_payload
    )
    snapshot = ManifestSnapshot(
        connector_hints=(ConnectorHint(SOURCE_A, "notes", "v1", ("connector hint",)),)
    )
    manifest = build_corpus_manifest(updated, ScopeSelection.scope(SCOPE_A), snapshot=snapshot)
    assert manifest.sources[0].answering_hints == (
        ("connector hint", "connector"),
        ("scope hint", "scope_policy"),
    )
    assert all(
        "model" not in provenance
        for source in manifest.sources
        for _, provenance in source.answering_hints
    )
