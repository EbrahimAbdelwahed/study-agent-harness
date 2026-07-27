from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from study_agent.domain import (
    WHOLE_CORPUS,
    Actor,
    AdapterAvailability,
    AnsweringHint,
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
    decode_scope_membership_event,
    decode_scope_policy,
    reduce_scope_configured,
    reduce_scope_membership,
    scope_configured_payload,
    scope_membership_payload,
)
from study_agent.state import canonical_json_bytes, event_from_bytes, event_to_bytes

COURSE = CourseId("course")
SCOPE_A = ScopeId("anatomia")
SOURCE_A = SourceId("book")
SOURCE_B = SourceId("transcript")
NOW = datetime(2026, 7, 27, tzinfo=UTC)


def policy(version: str = "p1", *, hints: tuple[str, ...] = ()) -> ScopePolicy:
    return ScopePolicy(
        policy_version=version,
        source_class_order=("edited", "transcript"),
        source_class_priors=(("edited", 1.0), ("transcript", 0.8)),
        aliases=(("rotator", ("cuffia", "rotatori")),),
        fragment_signal_weights=(("idf", 0.5), ("structure", 0.5)),
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
        Actor(actor, "scope-independent-test"),
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
        Actor(actor, "scope-independent-test"),
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


def configured_state(scope_id: ScopeId = SCOPE_A) -> JsonObject:
    payload = ScopeConfigured(scope_id, policy())
    return reduce_scope_configured(source_state(), config_event(payload), payload)


def scope_row(state: Mapping[str, JsonValue], scope_id: ScopeId) -> Mapping[str, JsonValue]:
    scopes = state["scopes"]
    assert isinstance(scopes, Mapping)
    row = scopes[str(scope_id)]
    assert isinstance(row, Mapping)
    return row


def test_model_authority_is_rejected_for_configuration_and_membership() -> None:
    configured = ScopeConfigured(SCOPE_A, policy())
    with pytest.raises(ValueError, match="model"):
        decode_scope_configured_event(config_event(configured, actor=PrincipalKind.MODEL))

    state = configured_state()
    membership = ScopeMembershipChanged(SCOPE_A, SOURCE_A, "add")
    with pytest.raises(ValueError, match="model"):
        decode_scope_membership_event(
            membership_event(membership, sequence=2, actor=PrincipalKind.MODEL)
        )
    assert "scopes" in state and "units" in state


def test_event_identity_binds_course_sequence_and_payload() -> None:
    payload = ScopeConfigured(SCOPE_A, policy())
    event = config_event(payload)
    for forged in (
        replace(event, event_id=EventId("event-sha256:" + "0" * 64)),
        replace(event, course_id=CourseId("other-course")),
        replace(event, course_sequence=2),
        replace(event, payload={**event.payload, "scope_id": "forged"}),
    ):
        with pytest.raises(ValueError, match="event_id"):
            decode_scope_configured_event(forged)

    membership = ScopeMembershipChanged(SCOPE_A, SOURCE_A, "add")
    event = membership_event(membership, sequence=2)
    with pytest.raises(ValueError, match="event_id"):
        decode_scope_membership_event(replace(event, course_id=CourseId("other-course")))


def test_policy_retry_conflict_and_stale_compare_and_set_are_distinct() -> None:
    initial = ScopeConfigured(SCOPE_A, policy())
    state = reduce_scope_configured(source_state(), config_event(initial), initial)
    assert reduce_scope_configured(state, config_event(initial), initial) == state

    same_version = ScopeConfigured(SCOPE_A, policy("p1", hints=("different",)), "p1")
    with pytest.raises(ValueError, match="policy version"):
        reduce_scope_configured(state, config_event(same_version, sequence=3), same_version)

    stale = ScopeConfigured(SCOPE_A, policy("p3"), "p0")
    with pytest.raises(ValueError, match="stale"):
        reduce_scope_configured(state, config_event(stale, sequence=4), stale)

    updated = ScopeConfigured(SCOPE_A, policy("p2"), "p1")
    changed = reduce_scope_configured(state, config_event(updated, sequence=5), updated)
    assert scope_row(changed, SCOPE_A)["policy"] == updated.policy.to_json()


def test_membership_rejects_unknown_scope_source_and_absent_removal() -> None:
    unconfigured = source_state()
    unknown_scope = ScopeMembershipChanged(ScopeId("missing"), SOURCE_A, "add")
    with pytest.raises(ValueError, match="configured"):
        reduce_scope_membership(
            unconfigured, membership_event(unknown_scope, sequence=1), unknown_scope
        )

    state = configured_state()
    unknown_source = ScopeMembershipChanged(SCOPE_A, SourceId("missing"), "add")
    with pytest.raises(ValueError, match="unknown"):
        reduce_scope_membership(
            state, membership_event(unknown_source, sequence=2), unknown_source
        )

    absent = ScopeMembershipChanged(SCOPE_A, SOURCE_B, "remove")
    with pytest.raises(ValueError, match="absent"):
        reduce_scope_membership(state, membership_event(absent, sequence=3), absent)


def test_one_source_can_belong_to_many_scopes_without_copying_units() -> None:
    state = configured_state()
    second = ScopeId("biochem")
    second_config = ScopeConfigured(second, policy())
    state = reduce_scope_configured(
        state, config_event(second_config, sequence=2), second_config
    )
    first_add = ScopeMembershipChanged(SCOPE_A, SOURCE_A, "add")
    second_add = ScopeMembershipChanged(second, SOURCE_A, "add")
    state = reduce_scope_membership(state, membership_event(first_add, sequence=3), first_add)
    state = reduce_scope_membership(state, membership_event(second_add, sequence=4), second_add)

    assert scope_row(state, SCOPE_A)["source_ids"] == (str(SOURCE_A),)
    assert scope_row(state, second)["source_ids"] == (str(SOURCE_A),)
    assert state["units"] == source_state()["units"]
    scopes = state["scopes"]
    assert isinstance(scopes, Mapping)
    assert all(isinstance(row, Mapping) and "units" not in row for row in scopes.values())


def test_whole_corpus_is_explicit_and_unknown_or_empty_scope_fails() -> None:
    snapshot = ManifestSnapshot()
    whole = build_corpus_manifest(source_state(), WHOLE_CORPUS, snapshot=snapshot)
    assert whole.policy is None
    assert [item.source_id for item in whole.sources] == [SOURCE_A, SOURCE_B]

    with pytest.raises(ValueError, match="unknown"):
        build_corpus_manifest(
            source_state(), ScopeSelection.scope(ScopeId("missing")), snapshot=snapshot
        )

    empty_scope = configured_state(ScopeId("empty"))
    with pytest.raises(ValueError, match="no source members"):
        build_corpus_manifest(
            empty_scope, ScopeSelection.scope(ScopeId("empty")), snapshot=snapshot
        )


def test_manifest_order_is_deterministic_and_availability_is_bounded() -> None:
    snapshot = ManifestSnapshot(
        projection_coverage=(
            ProjectionCoverage("z-index", 1, 2, "degraded"),
            ProjectionCoverage("a-index", 0, 2, "absent"),
        ),
        retrievers=("z-retriever", "a-retriever"),
        adapters=(
            AdapterAvailability("z-adapter", AvailabilityStatus.DEGRADED, "timeout"),
            AdapterAvailability("a-adapter", AvailabilityStatus.ABSENT),
        ),
        conformance=(
            ConformanceSummary("z-scope", "degraded"),
            ConformanceSummary("a-scope", "ok"),
        ),
    )
    first = build_corpus_manifest(source_state(), WHOLE_CORPUS, snapshot=snapshot)
    second = build_corpus_manifest(source_state(), WHOLE_CORPUS, snapshot=snapshot)
    assert first.to_json() == second.to_json()
    assert [item.name for item in first.projection_coverage] == ["a-index", "z-index"]
    assert [item.name for item in first.adapters] == ["a-adapter", "z-adapter"]
    assert first.adapters[1].status is AvailabilityStatus.DEGRADED
    assert first.adapters[1].detail == "timeout"

    with pytest.raises(ValueError, match="too large"):
        ManifestSnapshot(
            adapters=tuple(
                AdapterAvailability(f"adapter-{index}", AvailabilityStatus.ABSENT)
                for index in range(257)
            )
        )


def test_manifest_hints_accept_only_declared_connector_or_scope_policy_sources() -> None:
    configured = ScopeConfigured(SCOPE_A, policy("p2", hints=("scope owner hint",)), "p1")
    state = reduce_scope_configured(
        configured_state(), config_event(configured, sequence=2), configured
    )
    membership = ScopeMembershipChanged(SCOPE_A, SOURCE_A, "add")
    state = reduce_scope_membership(state, membership_event(membership, sequence=3), membership)
    snapshot = ManifestSnapshot(
        connector_hints=(
            ConnectorHint(SOURCE_A, "notes", "v1", ("connector hint",)),
            ConnectorHint(SOURCE_B, "notes", "v1", ("unselected source hint",)),
        )
    )
    manifest = build_corpus_manifest(state, ScopeSelection.scope(SCOPE_A), snapshot=snapshot)
    assert manifest.sources[0].answering_hints == (
        AnsweringHint("connector hint", "connector", "notes", "v1"),
        AnsweringHint("scope owner hint", "scope_policy"),
    )
    assert all(
        hint.provenance_kind in {"connector", "scope_policy"}
        for source in manifest.sources
        for hint in source.answering_hints
    )


def test_malformed_canonical_source_and_unit_rows_fail_closed() -> None:
    malformed_source = {"sources": {str(SOURCE_A): {"title": "missing role"}}, "units": {}}
    with pytest.raises(ValueError, match=r"source_role|revision_ids|current_revision_id"):
        build_corpus_manifest(malformed_source, WHOLE_CORPUS, snapshot=ManifestSnapshot())

    orphan_unit = source_state()
    units_value = orphan_unit["units"]
    assert isinstance(units_value, Mapping)
    units = dict(units_value)
    units["orphan"] = {"source_id": "not-in-sources", "unit_kind": "passage"}
    orphan_unit = {**orphan_unit, "units": units}
    with pytest.raises(ValueError, match=r"unknown|source"):
        build_corpus_manifest(orphan_unit, WHOLE_CORPUS, snapshot=ManifestSnapshot())


def test_event_codec_round_trip_and_strict_canonical_bytes() -> None:
    event = config_event(ScopeConfigured(SCOPE_A, policy()))
    encoded = event_to_bytes(event)
    assert event_from_bytes(encoded) == event

    with pytest.raises(ValueError, match="canonical"):
        event_from_bytes(encoded + b" ")


def test_event_codec_rejects_unknown_envelope_fields() -> None:
    event = config_event(ScopeConfigured(SCOPE_A, policy()))
    encoded = event_to_bytes(event)
    envelope = json.loads(encoded)
    assert isinstance(envelope, dict)
    envelope["forged"] = True
    forged = canonical_json_bytes(envelope)
    with pytest.raises(ValueError, match=r"field|unknown"):
        event_from_bytes(forged)


def test_scope_policy_decoder_rejects_noncanonical_or_unknown_shape() -> None:
    payload = policy().to_json()
    with pytest.raises(ValueError, match="fields mismatch"):
        decode_scope_policy({**payload, "model_inference": True})
    with pytest.raises(ValueError, match="fields mismatch"):
        decode_scope_policy({key: value for key, value in payload.items() if key != "aliases"})
