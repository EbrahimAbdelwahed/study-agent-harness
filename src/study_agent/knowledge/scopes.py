"""Canonical scope events and deterministic agent-facing manifests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.events import DomainEvent, PrincipalKind
from study_agent.domain.identifiers import ScopeId, SourceId, scope_event_id_for
from study_agent.domain.scopes import (
    WHOLE_CORPUS,
    CorpusManifest,
    ManifestSnapshot,
    ManifestSource,
    ScopePolicy,
    ScopeSelection,
    ScopeSelectionKind,
)
from study_agent.state import EventRegistry

SCOPE_CONFIGURED = "knowledge.scope_configured"
SCOPE_CONFIGURED_SCHEMA_VERSION = 1
SCOPE_MEMBERSHIP_CHANGED = "knowledge.scope_membership_changed"
SCOPE_MEMBERSHIP_SCHEMA_VERSION = 1

_CONFIG_KEYS = frozenset({"policy", "previous_policy_version", "scope_id"})
_MEMBERSHIP_KEYS = frozenset({"operation", "scope_id", "source_id"})
_SCOPE_ROW_KEYS = frozenset({"policy", "source_ids"})


@dataclass(frozen=True, slots=True)
class ScopeConfigured:
    scope_id: ScopeId
    policy: ScopePolicy
    previous_policy_version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope_id, ScopeId):
            raise TypeError("scope configuration requires ScopeId")
        if len(str(self.scope_id)) > 128:
            raise ValueError("scope configuration scope_id is too long")
        if not isinstance(self.policy, ScopePolicy):
            raise TypeError("scope configuration requires ScopePolicy")
        if self.previous_policy_version is not None and (
            not isinstance(self.previous_policy_version, str)
            or not self.previous_policy_version.strip()
            or self.previous_policy_version != self.previous_policy_version.strip()
            or len(self.previous_policy_version) > 128
        ):
            raise ValueError("previous_policy_version must be bounded trimmed text or null")


@dataclass(frozen=True, slots=True)
class ScopeMembershipChanged:
    scope_id: ScopeId
    source_id: SourceId
    operation: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope_id, ScopeId):
            raise TypeError("membership requires ScopeId")
        if not isinstance(self.source_id, SourceId):
            raise TypeError("membership requires SourceId")
        if len(str(self.scope_id)) > 128 or len(str(self.source_id)) > 128:
            raise ValueError("membership identifiers are too long")
        if self.operation not in {"add", "remove"}:
            raise ValueError("membership operation must be add or remove")


def scope_configured_payload(payload: ScopeConfigured) -> JsonObject:
    if not isinstance(payload, ScopeConfigured):
        raise TypeError("scope configuration payload requires ScopeConfigured")
    return {
        "policy": payload.policy.to_json(),
        "previous_policy_version": payload.previous_policy_version,
        "scope_id": str(payload.scope_id),
    }


def scope_membership_payload(payload: ScopeMembershipChanged) -> JsonObject:
    if not isinstance(payload, ScopeMembershipChanged):
        raise TypeError("membership payload requires ScopeMembershipChanged")
    return {
        "operation": payload.operation,
        "scope_id": str(payload.scope_id),
        "source_id": str(payload.source_id),
    }


def decode_scope_configured(payload: JsonObject) -> ScopeConfigured:
    top = _object(payload, "scope configuration", _CONFIG_KEYS)
    previous = top.get("previous_policy_version")
    if previous is not None and (
        not isinstance(previous, str)
        or not previous.strip()
        or previous != previous.strip()
        or len(previous) > 128
    ):
        raise ValueError("previous_policy_version must be text or null")
    return ScopeConfigured(
        ScopeId(_text(top.get("scope_id"), "scope_id")),
        decode_scope_policy(_object(top.get("policy"), "policy")),
        previous,
    )


def decode_scope_membership(payload: JsonObject) -> ScopeMembershipChanged:
    top = _object(payload, "scope membership", _MEMBERSHIP_KEYS)
    operation = _text(top.get("operation"), "operation")
    if operation not in {"add", "remove"}:
        raise ValueError("operation must be add or remove")
    return ScopeMembershipChanged(
        ScopeId(_text(top.get("scope_id"), "scope_id")),
        SourceId(_text(top.get("source_id"), "source_id")),
        operation,
    )


def decode_scope_configured_event(event: DomainEvent) -> ScopeConfigured:
    _event_envelope(event, SCOPE_CONFIGURED, SCOPE_CONFIGURED_SCHEMA_VERSION)
    payload = decode_scope_configured(event.payload)
    _require_authority(event)
    expected = scope_event_id_for(
        event.course_id,
        payload.scope_id,
        "configure",
        scope_configured_payload(payload),
        event.course_sequence,
    )
    if event.event_id != expected:
        raise ValueError("event_id does not match scope configuration identity")
    return payload


def decode_scope_membership_event(event: DomainEvent) -> ScopeMembershipChanged:
    _event_envelope(event, SCOPE_MEMBERSHIP_CHANGED, SCOPE_MEMBERSHIP_SCHEMA_VERSION)
    payload = decode_scope_membership(event.payload)
    _require_authority(event)
    expected = scope_event_id_for(
        event.course_id,
        payload.scope_id,
        payload.operation,
        scope_membership_payload(payload),
        event.course_sequence,
    )
    if event.event_id != expected:
        raise ValueError("event_id does not match scope membership identity")
    return payload


def reduce_scope_configured(
    state: JsonObject, _: DomainEvent, payload: ScopeConfigured
) -> Mapping[str, JsonValue]:
    scopes = dict(_mapping(state.get("scopes", {}), "scopes"))
    key = str(payload.scope_id)
    existing_value = scopes.get(key)
    encoded: JsonObject = {"policy": payload.policy.to_json(), "source_ids": ()}
    if existing_value is None:
        if payload.previous_policy_version is not None:
            raise ValueError("new scope configuration cannot name a previous policy")
        scopes[key] = encoded
        return {**state, "scopes": scopes}
    existing = _object(existing_value, f"scopes.{key}", _SCOPE_ROW_KEYS)
    current_policy = decode_scope_policy(_object(existing.get("policy"), f"scopes.{key}.policy"))
    source_ids = _source_ids(existing.get("source_ids"), f"scopes.{key}.source_ids")
    if payload.previous_policy_version is None:
        if current_policy == payload.policy:
            return state
        raise ValueError("scope already exists; update requires previous policy version")
    if payload.previous_policy_version != current_policy.policy_version:
        raise ValueError("scope policy compare-and-set version is stale")
    if current_policy == payload.policy:
        return state
    if payload.policy.policy_version == current_policy.policy_version:
        raise ValueError("a policy version cannot carry different content")
    scopes[key] = {"policy": payload.policy.to_json(), "source_ids": source_ids}
    return {**state, "scopes": scopes}


def reduce_scope_membership(
    state: JsonObject, _: DomainEvent, payload: ScopeMembershipChanged
) -> Mapping[str, JsonValue]:
    scopes = dict(_mapping(state.get("scopes", {}), "scopes"))
    key = str(payload.scope_id)
    if key not in scopes:
        raise ValueError("scope must be configured before membership changes")
    sources = _mapping(state.get("sources", {}), "sources")
    source_key = str(payload.source_id)
    if source_key not in sources:
        raise ValueError("membership source is unknown")
    row = _object(scopes[key], f"scopes.{key}", _SCOPE_ROW_KEYS)
    current = list(_source_ids(row.get("source_ids"), f"scopes.{key}.source_ids"))
    if payload.operation == "add":
        if source_key in current:
            return state
        current.append(source_key)
        current.sort()
    elif source_key not in current:
        raise ValueError("cannot remove absent scope membership")
    else:
        current.remove(source_key)
    scopes[key] = {"policy": row["policy"], "source_ids": tuple(current)}
    return {**state, "scopes": scopes}


def register_scope_events(registry: EventRegistry) -> None:
    registry.register_event(
        SCOPE_CONFIGURED,
        SCOPE_CONFIGURED_SCHEMA_VERSION,
        decode_scope_configured_event,
        reduce_scope_configured,
    )
    registry.register_event(
        SCOPE_MEMBERSHIP_CHANGED,
        SCOPE_MEMBERSHIP_SCHEMA_VERSION,
        decode_scope_membership_event,
        reduce_scope_membership,
    )


def decode_scope_policy(payload: JsonObject) -> ScopePolicy:
    keys = frozenset(
        {
            "aliases",
            "answering_hints",
            "fragment_idf_percentile",
            "fragment_min_characters",
            "fragment_promotion_threshold",
            "fragment_signal_weights",
            "max_units_per_section",
            "max_units_per_source",
            "policy_version",
            "source_class_order",
            "source_class_priors",
        }
    )
    top = _object(payload, "policy", keys)
    return ScopePolicy(
        policy_version=_text(top.get("policy_version"), "policy_version"),
        source_class_order=_texts(top.get("source_class_order"), "source_class_order"),
        source_class_priors=_named_numbers(
            top.get("source_class_priors"), "source_class_priors", "class", "prior"
        ),
        max_units_per_source=_integer(top.get("max_units_per_source"), "max_units_per_source"),
        max_units_per_section=_integer(top.get("max_units_per_section"), "max_units_per_section"),
        aliases=_aliases(top.get("aliases")),
        fragment_min_characters=_integer(
            top.get("fragment_min_characters"), "fragment_min_characters"
        ),
        fragment_idf_percentile=_number(
            top.get("fragment_idf_percentile"), "fragment_idf_percentile"
        ),
        fragment_signal_weights=_named_numbers(
            top.get("fragment_signal_weights"), "fragment_signal_weights", "name", "weight"
        ),
        fragment_promotion_threshold=_number(
            top.get("fragment_promotion_threshold"), "fragment_promotion_threshold"
        ),
        answering_hints=_texts(top.get("answering_hints"), "answering_hints"),
    )


def build_corpus_manifest(
    state: JsonObject,
    selection: ScopeSelection,
    *,
    snapshot: ManifestSnapshot,
) -> CorpusManifest:
    """Summarize canonical sources/units plus explicitly supplied derivatives."""
    if not isinstance(selection, ScopeSelection):
        raise TypeError("manifest selection must be ScopeSelection")
    if not isinstance(snapshot, ManifestSnapshot):
        raise TypeError("manifest requires explicit ManifestSnapshot")
    sources = _mapping(state.get("sources", {}), "sources")
    units = _mapping(state.get("units", {}), "units")
    policy: ScopePolicy | None = None
    if selection.kind is ScopeSelectionKind.WHOLE_CORPUS:
        selected_ids = set(sources)
    else:
        scopes = _mapping(state.get("scopes", {}), "scopes")
        scope_key = str(cast(ScopeId, selection.scope_id))
        if scope_key not in scopes:
            raise ValueError("manifest scope is unknown")
        scope_row = _object(scopes[scope_key], f"scopes.{scope_key}", _SCOPE_ROW_KEYS)
        selected_ids = set(
            _source_ids(scope_row.get("source_ids"), f"scopes.{scope_key}.source_ids")
        )
        if not selected_ids:
            raise ValueError("manifest scope has no source members")
        policy = decode_scope_policy(_object(scope_row.get("policy"), f"scopes.{scope_key}.policy"))
    connector_by_source = {str(item.source_id): item for item in snapshot.connector_hints}
    manifest_sources: list[ManifestSource] = []
    for source_id in sorted(selected_ids):
        source_row = _mapping(sources.get(source_id), f"sources.{source_id}")
        descriptor = _source_descriptor(source_row, source_id)
        title = _text(descriptor.get("title"), f"sources.{source_id}.title")
        source_class = _text(descriptor.get("source_role"), f"sources.{source_id}.source_role")
        revision_ids_value = source_row.get("revision_ids", ())
        revisions = _texts(revision_ids_value, f"sources.{source_id}.revision_ids")
        source_units = []
        for unit_key, value in units.items():
            row = _mapping(value, f"units.{unit_key}")
            row_source_id = _text(row.get("source_id"), f"units.{unit_key}.source_id")
            if row_source_id == source_id:
                _text(row.get("unit_kind"), f"units.{unit_key}.unit_kind")
                source_units.append(row)
        unit_count = len(source_units)
        figure_count = sum(1 for row in source_units if row.get("unit_kind") == "figure")
        hints: list[tuple[str, str]] = []
        connector_hint = connector_by_source.get(source_id)
        if connector_hint is not None:
            hints.extend((hint, "connector") for hint in connector_hint.hints)
        if policy is not None:
            hints.extend((hint, "scope_policy") for hint in policy.answering_hints)
        manifest_sources.append(
            ManifestSource(
                SourceId(source_id),
                title,
                source_class,
                revisions,
                unit_count,
                figure_count,
                tuple(sorted(set(hints))),
            )
        )
    total_units = sum(source.unit_count for source in manifest_sources)
    total_figures = sum(source.figure_count for source in manifest_sources)
    return CorpusManifest(
        selection,
        policy,
        tuple(manifest_sources),
        total_units,
        total_figures,
        tuple(sorted(snapshot.projection_coverage, key=lambda item: item.name)),
        snapshot.retrievers,
        tuple(sorted(snapshot.adapters, key=lambda item: item.name)),
        tuple(sorted(snapshot.conformance, key=lambda item: item.scope)),
    )


def _source_descriptor(source: Mapping[str, JsonValue], source_id: str) -> Mapping[str, JsonValue]:
    """Read source metadata from the canonical row or its current revision."""
    if source.get("title") is not None and source.get("source_role") is not None:
        return source
    current_revision_id = _text(
        source.get("current_revision_id"), f"sources.{source_id}.current_revision_id"
    )
    revisions = _mapping(source.get("revisions"), f"sources.{source_id}.revisions")
    revision = _mapping(
        revisions.get(current_revision_id),
        f"sources.{source_id}.revisions.{current_revision_id}",
    )
    return _mapping(
        revision.get("source"),
        f"sources.{source_id}.revisions.{current_revision_id}.source",
    )


def _event_envelope(event: DomainEvent, event_type: str, schema: int) -> None:
    if event.event_type != event_type or event.schema_version != schema:
        raise ValueError(f"event envelope does not match {event_type}@{schema}")


def _require_authority(event: DomainEvent) -> None:
    if event.actor.kind is PrincipalKind.MODEL:
        raise ValueError("model actors cannot author scope state")
    if event.actor.kind not in (PrincipalKind.HUMAN, PrincipalKind.SERVICE):
        raise ValueError("scope events require human or service authority")


def _object(
    value: JsonValue | None, name: str, keys: frozenset[str] | None = None
) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    if keys is not None and frozenset(value) != keys:
        missing = sorted(keys - frozenset(value))
        extra = sorted(frozenset(value) - keys)
        raise ValueError(f"{name} fields mismatch; missing={missing}, extra={extra}")
    return value


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    return _object(value, name)


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    if len(value) > 128:
        raise ValueError(f"{name} is too long")
    return value


def _integer(value: JsonValue | None, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def _number(value: JsonValue | None, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    return float(value)


def _texts(value: JsonValue | None, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be an array")
    values = tuple(_text(item, f"{name}[{index}]") for index, item in enumerate(value))
    if len(values) > 256 or len(set(values)) != len(values):
        raise ValueError(f"{name} is invalid or too large")
    return values


def _named_numbers(
    value: JsonValue | None, name: str, key_name: str, number_name: str
) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be an array")
    if len(value) > 256:
        raise ValueError(f"{name} is too large")
    result = []
    for index, item in enumerate(value):
        row = _object(item, f"{name}[{index}]", frozenset({key_name, number_name}))
        result.append(
            (
                _text(row.get(key_name), f"{name}[{index}].{key_name}"),
                _number(row.get(number_name), f"{name}[{index}].{number_name}"),
            )
        )
    return tuple(result)


def _aliases(value: JsonValue | None) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if not isinstance(value, tuple):
        raise ValueError("aliases must be an array")
    if len(value) > 256:
        raise ValueError("aliases is too large")
    result = []
    for index, item in enumerate(value):
        row = _object(item, f"aliases[{index}]", frozenset({"alias", "values"}))
        result.append(
            (
                _text(row.get("alias"), f"aliases[{index}].alias"),
                _texts(row.get("values"), f"aliases[{index}].values"),
            )
        )
    return tuple(result)


def _source_ids(value: JsonValue | None, name: str) -> tuple[str, ...]:
    return tuple(sorted(_texts(value, name)))


__all__ = [
    "SCOPE_CONFIGURED",
    "SCOPE_CONFIGURED_SCHEMA_VERSION",
    "SCOPE_MEMBERSHIP_CHANGED",
    "SCOPE_MEMBERSHIP_SCHEMA_VERSION",
    "WHOLE_CORPUS",
    "ScopeConfigured",
    "ScopeMembershipChanged",
    "build_corpus_manifest",
    "decode_scope_configured",
    "decode_scope_configured_event",
    "decode_scope_membership",
    "decode_scope_membership_event",
    "decode_scope_policy",
    "reduce_scope_configured",
    "reduce_scope_membership",
    "register_scope_events",
    "scope_configured_payload",
    "scope_membership_payload",
]
