"""Immutable scope policy and agent-facing corpus-manifest contracts.

Scope membership is canonical event state; these values contain only bounded
provider/model-neutral data.  Manifest availability snapshots are explicitly
derived inputs and never become mutation authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from ._validation import JsonObject, require_text
from .identifiers import ScopeId, SourceId

_MAX_ITEMS = 256
_MAX_TEXT = 128


class ScopeSelectionKind(StrEnum):
    SCOPE = "scope"
    WHOLE_CORPUS = "whole_corpus"


def _label(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    require_text(value, name)
    if len(value) > _MAX_TEXT:
        raise ValueError(f"{name} must be at most {_MAX_TEXT} characters")
    return value


def _texts(values: Sequence[str], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence of strings")
    result = tuple(_label(value, f"{name}[{index}]") for index, value in enumerate(values))
    if len(result) > _MAX_ITEMS:
        raise ValueError(f"{name} is too large")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _pairs(
    values: Mapping[str, float] | Sequence[tuple[str, float]], name: str
) -> tuple[tuple[str, float], ...]:
    if isinstance(values, Mapping):
        is_mapping = True
        raw = tuple(values.items())
    else:
        is_mapping = False
        raw = tuple(values)
    if len(raw) > _MAX_ITEMS:
        raise ValueError(f"{name} is too large")
    result = tuple(
        (_label(key, f"{name}.key"), _finite(value, f"{name}[{key}]")) for key, value in raw
    )
    if len({key for key, _ in result}) != len(result):
        raise ValueError(f"{name} keys must be unique")
    return tuple(sorted(result)) if is_mapping else result


def _alias_pairs(
    values: Mapping[str, Sequence[str]] | Sequence[tuple[str, Sequence[str]]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if isinstance(values, Mapping):
        is_mapping = True
        raw = tuple(values.items())
    else:
        is_mapping = False
        raw = tuple(values)
    if len(raw) > _MAX_ITEMS:
        raise ValueError("aliases is too large")
    result = tuple(
        (_label(key, "alias"), _texts(alias_values, f"aliases[{key}]")) for key, alias_values in raw
    )
    if len({key for key, _ in result}) != len(result):
        raise ValueError("aliases keys must be unique")
    return tuple(sorted(result)) if is_mapping else result


@dataclass(frozen=True, slots=True)
class ScopePolicy:
    """Owner-supplied, versioned scope defaults with no learner state."""

    policy_version: str = "scope-policy-v1"
    source_class_order: tuple[str, ...] = ()
    source_class_priors: tuple[tuple[str, float], ...] = ()
    max_units_per_source: int = 20
    max_units_per_section: int = 3
    aliases: tuple[tuple[str, tuple[str, ...]], ...] = ()
    fragment_min_characters: int = 80
    fragment_idf_percentile: float = 0.9
    fragment_signal_weights: tuple[tuple[str, float], ...] = ()
    fragment_promotion_threshold: float = 1.0
    answering_hints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _label(self.policy_version, "policy_version"))
        order = _texts(self.source_class_order, "source_class_order")
        priors = _pairs(self.source_class_priors, "source_class_priors")
        if priors and not {key for key, _ in priors} <= set(order):
            raise ValueError("source_class_priors must name declared source classes")
        for value, name in (
            (self.max_units_per_source, "max_units_per_source"),
            (self.max_units_per_section, "max_units_per_section"),
            (self.fragment_min_characters, "fragment_min_characters"),
        ):
            if type(value) is not int or value < 1 or value > 100_000:
                raise ValueError(f"{name} must be a bounded positive integer")
        object.__setattr__(self, "source_class_order", order)
        object.__setattr__(self, "source_class_priors", priors)
        object.__setattr__(self, "aliases", _alias_pairs(self.aliases))
        percentile = _finite(self.fragment_idf_percentile, "fragment_idf_percentile")
        if not 0.0 <= percentile <= 1.0:
            raise ValueError("fragment_idf_percentile must be between zero and one")
        object.__setattr__(self, "fragment_idf_percentile", percentile)
        weights = _pairs(self.fragment_signal_weights, "fragment_signal_weights")
        object.__setattr__(self, "fragment_signal_weights", weights)
        threshold = _finite(self.fragment_promotion_threshold, "fragment_promotion_threshold")
        if threshold < 0:
            raise ValueError("fragment_promotion_threshold must be non-negative")
        object.__setattr__(self, "fragment_promotion_threshold", threshold)
        object.__setattr__(self, "answering_hints", _texts(self.answering_hints, "answering_hints"))

    def to_json(self) -> JsonObject:
        return {
            "aliases": tuple({"alias": key, "values": values} for key, values in self.aliases),
            "answering_hints": self.answering_hints,
            "fragment_idf_percentile": self.fragment_idf_percentile,
            "fragment_min_characters": self.fragment_min_characters,
            "fragment_promotion_threshold": self.fragment_promotion_threshold,
            "fragment_signal_weights": tuple(
                {"name": key, "weight": value} for key, value in self.fragment_signal_weights
            ),
            "max_units_per_section": self.max_units_per_section,
            "max_units_per_source": self.max_units_per_source,
            "policy_version": self.policy_version,
            "source_class_order": self.source_class_order,
            "source_class_priors": tuple(
                {"class": key, "prior": value} for key, value in self.source_class_priors
            ),
        }


@dataclass(frozen=True, slots=True)
class ScopeSelection:
    """Explicit scope selector; whole-corpus is a named value, never ``None``."""

    kind: ScopeSelectionKind
    scope_id: ScopeId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ScopeSelectionKind):
            raise TypeError("selection kind must be ScopeSelectionKind")
        if self.kind is ScopeSelectionKind.SCOPE:
            if not isinstance(self.scope_id, ScopeId):
                raise TypeError("scope selection requires ScopeId")
            _label(str(self.scope_id), "scope_id")
        elif self.scope_id is not None:
            raise ValueError("whole-corpus selection cannot carry a scope id")

    @classmethod
    def scope(cls, scope_id: ScopeId) -> ScopeSelection:
        return cls(ScopeSelectionKind.SCOPE, scope_id)

    @classmethod
    def whole_corpus(cls) -> ScopeSelection:
        return cls(ScopeSelectionKind.WHOLE_CORPUS)

    def to_json(self) -> JsonObject:
        return {
            "kind": self.kind.value,
            "scope_id": None if self.scope_id is None else str(self.scope_id),
        }


WHOLE_CORPUS = ScopeSelection.whole_corpus()


@dataclass(frozen=True, slots=True)
class ProjectionCoverage:
    name: str
    covered_units: int
    total_units: int
    status: str = "available"

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _label(self.name, "coverage.name"))
        object.__setattr__(self, "status", _label(self.status, "coverage.status"))
        for value, name in (
            (self.covered_units, "covered_units"),
            (self.total_units, "total_units"),
        ):
            if type(value) is not int or value < 0 or value > 10_000_000:
                raise ValueError(f"coverage.{name} is out of bounds")
        if self.covered_units > self.total_units:
            raise ValueError("covered_units cannot exceed total_units")

    def to_json(self) -> JsonObject:
        return {
            "covered_units": self.covered_units,
            "name": self.name,
            "status": self.status,
            "total_units": self.total_units,
        }


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    ABSENT = "absent"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class AdapterAvailability:
    name: str
    status: AvailabilityStatus
    detail: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _label(self.name, "adapter.name"))
        if not isinstance(self.status, AvailabilityStatus):
            raise TypeError("adapter status must be AvailabilityStatus")
        if self.detail is not None:
            object.__setattr__(self, "detail", _label(self.detail, "adapter.detail"))

    def to_json(self) -> JsonObject:
        return {"detail": self.detail, "name": self.name, "status": self.status.value}


@dataclass(frozen=True, slots=True)
class ConformanceSummary:
    scope: str
    status: str
    findings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", _label(self.scope, "conformance.scope"))
        object.__setattr__(self, "status", _label(self.status, "conformance.status"))
        object.__setattr__(self, "findings", _texts(self.findings, "conformance.findings"))

    def to_json(self) -> JsonObject:
        return {"findings": self.findings, "scope": self.scope, "status": self.status}


@dataclass(frozen=True, slots=True)
class ConnectorHint:
    source_id: SourceId
    connector_name: str
    connector_version: str
    hints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise TypeError("connector hint source_id must be SourceId")
        _label(str(self.source_id), "connector hint source_id")
        object.__setattr__(self, "connector_name", _label(self.connector_name, "connector_name"))
        object.__setattr__(
            self, "connector_version", _label(self.connector_version, "connector_version")
        )
        object.__setattr__(self, "hints", _texts(self.hints, "connector hints"))

    def to_json(self) -> JsonObject:
        return {
            "connector_name": self.connector_name,
            "connector_version": self.connector_version,
            "hints": self.hints,
            "source_id": str(self.source_id),
        }


@dataclass(frozen=True, slots=True)
class ManifestSource:
    source_id: SourceId
    title: str
    source_class: str
    revisions: tuple[str, ...]
    unit_count: int
    figure_count: int
    answering_hints: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise TypeError("manifest source_id must be SourceId")
        _label(str(self.source_id), "manifest source_id")
        object.__setattr__(self, "title", _label(self.title, "source.title"))
        object.__setattr__(self, "source_class", _label(self.source_class, "source.source_class"))
        object.__setattr__(self, "revisions", _texts(self.revisions, "source.revisions"))
        for value, name in ((self.unit_count, "unit_count"), (self.figure_count, "figure_count")):
            if type(value) is not int or value < 0 or value > 10_000_000:
                raise ValueError(f"source.{name} is out of bounds")
        if self.figure_count > self.unit_count:
            raise ValueError("source.figure_count cannot exceed unit_count")
        hints = tuple(
            (_label(value, "hint"), _label(provenance, "hint provenance"))
            for value, provenance in self.answering_hints
        )
        if len(hints) > _MAX_ITEMS:
            raise ValueError("source.answering_hints is too large")
        if any(provenance not in {"connector", "scope_policy"} for _, provenance in hints):
            raise ValueError("hint provenance must be connector or scope_policy")
        object.__setattr__(self, "answering_hints", tuple(sorted(set(hints))))

    def to_json(self) -> JsonObject:
        return {
            "answering_hints": tuple(
                {"provenance": provenance, "text": text}
                for text, provenance in self.answering_hints
            ),
            "figure_count": self.figure_count,
            "revisions": self.revisions,
            "source_class": self.source_class,
            "source_id": str(self.source_id),
            "title": self.title,
            "unit_count": self.unit_count,
        }


@dataclass(frozen=True, slots=True)
class ManifestSnapshot:
    """Explicitly supplied derived availability, bounded before aggregation."""

    projection_coverage: tuple[ProjectionCoverage, ...] = ()
    retrievers: tuple[str, ...] = ()
    adapters: tuple[AdapterAvailability, ...] = ()
    conformance: tuple[ConformanceSummary, ...] = ()
    connector_hints: tuple[ConnectorHint, ...] = ()

    def __post_init__(self) -> None:
        coverage = tuple(self.projection_coverage)
        adapters = tuple(self.adapters)
        conformance = tuple(self.conformance)
        connector_hints = tuple(self.connector_hints)
        for coverage_item in coverage:
            if not isinstance(coverage_item, ProjectionCoverage):
                raise TypeError("projection_coverage must contain ProjectionCoverage values")
        for adapter in adapters:
            if not isinstance(adapter, AdapterAvailability):
                raise TypeError("adapters must contain AdapterAvailability values")
        for conformance_item in conformance:
            if not isinstance(conformance_item, ConformanceSummary):
                raise TypeError("conformance must contain ConformanceSummary values")
        for hint in connector_hints:
            if not isinstance(hint, ConnectorHint):
                raise TypeError("connector_hints must contain ConnectorHint values")
        object.__setattr__(
            self,
            "projection_coverage",
            tuple(sorted(coverage, key=lambda item: item.name)),
        )
        object.__setattr__(self, "retrievers", tuple(sorted(_texts(self.retrievers, "retrievers"))))
        object.__setattr__(self, "adapters", tuple(sorted(adapters, key=lambda item: item.name)))
        object.__setattr__(
            self, "conformance", tuple(sorted(conformance, key=lambda item: item.scope))
        )
        object.__setattr__(
            self,
            "connector_hints",
            tuple(
                sorted(
                    connector_hints,
                    key=lambda item: (
                        str(item.source_id),
                        item.connector_name,
                        item.connector_version,
                    ),
                )
            ),
        )
        for value, name in (
            (self.projection_coverage, "projection_coverage"),
            (self.adapters, "adapters"),
            (self.conformance, "conformance"),
            (self.connector_hints, "connector_hints"),
        ):
            if len(value) > _MAX_ITEMS:
                raise ValueError(f"{name} is too large")


@dataclass(frozen=True, slots=True)
class CorpusManifest:
    selection: ScopeSelection
    policy: ScopePolicy | None
    sources: tuple[ManifestSource, ...]
    total_units: int
    total_figures: int
    projection_coverage: tuple[ProjectionCoverage, ...]
    retrievers: tuple[str, ...]
    adapters: tuple[AdapterAvailability, ...]
    conformance: tuple[ConformanceSummary, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.selection, ScopeSelection):
            raise TypeError("manifest selection must be ScopeSelection")
        if self.selection.kind is ScopeSelectionKind.SCOPE and not isinstance(
            self.policy, ScopePolicy
        ):
            raise TypeError("scoped manifest requires ScopePolicy")
        if self.selection.kind is ScopeSelectionKind.WHOLE_CORPUS and self.policy is not None:
            raise ValueError("whole-corpus manifest cannot carry one scope policy")
        sources = tuple(self.sources)
        coverage = tuple(self.projection_coverage)
        adapters = tuple(self.adapters)
        conformance = tuple(self.conformance)
        for source in sources:
            if not isinstance(source, ManifestSource):
                raise TypeError("sources must contain ManifestSource values")
        for coverage_item in coverage:
            if not isinstance(coverage_item, ProjectionCoverage):
                raise TypeError("projection_coverage must contain ProjectionCoverage values")
        for adapter in adapters:
            if not isinstance(adapter, AdapterAvailability):
                raise TypeError("adapters must contain AdapterAvailability values")
        for conformance_item in conformance:
            if not isinstance(conformance_item, ConformanceSummary):
                raise TypeError("conformance must contain ConformanceSummary values")
        object.__setattr__(
            self, "sources", tuple(sorted(sources, key=lambda item: str(item.source_id)))
        )
        object.__setattr__(
            self, "projection_coverage", tuple(sorted(coverage, key=lambda item: item.name))
        )
        object.__setattr__(
            self, "retrievers", tuple(sorted(_texts(self.retrievers, "manifest.retrievers")))
        )
        object.__setattr__(self, "adapters", tuple(sorted(adapters, key=lambda item: item.name)))
        object.__setattr__(
            self, "conformance", tuple(sorted(conformance, key=lambda item: item.scope))
        )
        for values, name in (
            (sources, "manifest.sources"),
            (coverage, "manifest.projection_coverage"),
            (adapters, "manifest.adapters"),
            (conformance, "manifest.conformance"),
        ):
            if len(values) > _MAX_ITEMS:
                raise ValueError(f"{name} is too large")
        for value, name in (
            (self.total_units, "total_units"),
            (self.total_figures, "total_figures"),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"manifest.{name} must be non-negative")
        if self.total_figures > self.total_units:
            raise ValueError("manifest.total_figures cannot exceed total_units")
        if self.total_units != sum(source.unit_count for source in self.sources):
            raise ValueError("manifest.total_units must equal source unit counts")
        if self.total_figures != sum(source.figure_count for source in self.sources):
            raise ValueError("manifest.total_figures must equal source figure counts")

    def to_json(self) -> JsonObject:
        return {
            "adapters": tuple(adapter.to_json() for adapter in self.adapters),
            "conformance": tuple(item.to_json() for item in self.conformance),
            "policy": None if self.policy is None else self.policy.to_json(),
            "projection_coverage": tuple(item.to_json() for item in self.projection_coverage),
            "retrievers": self.retrievers,
            "selection": self.selection.to_json(),
            "sources": tuple(item.to_json() for item in self.sources),
            "total_figures": self.total_figures,
            "total_units": self.total_units,
        }


__all__ = [
    "WHOLE_CORPUS",
    "AdapterAvailability",
    "AvailabilityStatus",
    "ConformanceSummary",
    "ConnectorHint",
    "CorpusManifest",
    "ManifestSnapshot",
    "ManifestSource",
    "ProjectionCoverage",
    "ScopePolicy",
    "ScopeSelection",
    "ScopeSelectionKind",
]
