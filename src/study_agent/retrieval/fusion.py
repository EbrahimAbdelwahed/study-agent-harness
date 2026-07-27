"""Deterministic, provider-neutral candidate fusion.

The fusion stage consumes only the portable KB-11 search batch and admitted
``RetrievableUnit`` values.  It does not inspect retriever implementations,
canonical text, persistence, or model state.  All state crossing the seam is
immutable and bounded so a caller can safely replay the same inputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from study_agent.domain.identifiers import UnitId
from study_agent.domain.units import (
    CanonicalRef,
    FigureBlob,
    LinkKind,
    RetrievableUnit,
    ReviewStatus,
    TextSpan,
    UnitKind,
    UnitLink,
    UnitMeta,
)
from study_agent.ports.retrievers import (
    RetrieverSearchBatch,
)

MAX_FUSION_POLICY_ITEMS = 64
MAX_FUSION_CATALOG_UNITS = 10_000
MAX_FUSION_RESULTS = 256
MAX_FUSION_ATTACHMENTS = 32
MAX_FUSION_RRF_K = 10_000

_MAX_LABEL = 128
type _PAIR_VALUE = tuple[str, float]


class FusionError(ValueError):
    """A batch, catalog, or policy violated the fusion contract."""


class FusionResultStatus(StrEnum):
    READY = "ready"
    INSUFFICIENT = "insufficient"


# Readable compatibility spelling for callers that name the result state
# directly.  Both names refer to the same closed enum.
FusionStatus = FusionResultStatus


def _label(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    if not value or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    if len(value) > _MAX_LABEL or "\x00" in value:
        raise ValueError(f"{name} must be at most {_MAX_LABEL} characters")
    return value


def _bounded_nonnegative(value: float, name: str, *, maximum: float = 1.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not isfinite(result) or result < 0.0 or result > maximum:
        raise ValueError(f"{name} must be finite and between 0 and {maximum}")
    return result


def _pairs(
    values: Mapping[str | UnitKind | ReviewStatus, float]
    | Sequence[tuple[str | UnitKind | ReviewStatus, float]],
    name: str,
    *,
    maximum: float = 1.0,
) -> tuple[_PAIR_VALUE, ...]:
    """Normalize policy maps without retaining caller-owned mappings."""
    raw = tuple(values.items()) if isinstance(values, Mapping) else tuple(values)
    if len(raw) > MAX_FUSION_POLICY_ITEMS:
        raise ValueError(f"{name} is too large")
    normalized: list[_PAIR_VALUE] = []
    for key, value in raw:
        if isinstance(key, (UnitKind, ReviewStatus)):
            key_text = key.value
        else:
            key_text = _label(key, f"{name} key")
        normalized.append(
            (
                key_text,
                _bounded_nonnegative(value, f"{name}[{key_text}]", maximum=maximum),
            )
        )
    if len({key for key, _ in normalized}) != len(normalized):
        raise ValueError(f"{name} keys must be unique")
    return tuple(sorted(normalized))


def _labels(values: Sequence[str], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence of strings")
    result = tuple(_label(value, f"{name} item") for value in values)
    if len(result) > MAX_FUSION_POLICY_ITEMS or len(set(result)) != len(result):
        raise ValueError(f"{name} must contain unique bounded values")
    return tuple(sorted(result))


@dataclass(frozen=True, slots=True)
class FusionPolicy:
    """Immutable, bounded per-scope fusion and context policy.

    Empty ``retriever_weights`` means an explicit, deterministic weight of
    ``1.0`` for every retriever in the sealed batch.  Once any weights are
    supplied, the set must exactly match the batch manifest identities; this
    prevents silently changing the score when a registry gains a retriever.
    """

    rrf_k: int = 60
    retriever_weights: tuple[tuple[str, float], ...] = ()
    structural_priors: tuple[tuple[str | UnitKind, float], ...] = ()
    source_class_priors: tuple[tuple[str, float], ...] = ()
    review_priors: tuple[tuple[str | ReviewStatus, float], ...] = ()
    uncertainty_penalty: float = 0.05
    max_results: int = 20
    max_units_per_source: int = 20
    max_units_per_section: int = 3
    max_parent_attachments: int = 1
    max_sibling_attachments: int = 2
    max_window_attachments: int = 2
    max_attachments_per_group: int = 8
    uncertainty_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.rrf_k) is not int or not 1 <= self.rrf_k <= MAX_FUSION_RRF_K:
            raise ValueError(f"rrf_k must be between 1 and {MAX_FUSION_RRF_K}")
        weights = _pairs(self.retriever_weights, "retriever_weights", maximum=100.0)
        for _, weight in weights:
            if weight <= 0.0:
                raise ValueError("retriever weights must be positive")
        object.__setattr__(self, "retriever_weights", weights)
        object.__setattr__(
            self,
            "structural_priors",
            _pairs(self.structural_priors, "structural_priors"),
        )
        object.__setattr__(
            self,
            "source_class_priors",
            _pairs(self.source_class_priors, "source_class_priors"),
        )
        object.__setattr__(self, "review_priors", _pairs(self.review_priors, "review_priors"))
        object.__setattr__(
            self,
            "uncertainty_penalty",
            _bounded_nonnegative(self.uncertainty_penalty, "uncertainty_penalty"),
        )
        for value, name in (
            (self.max_results, "max_results"),
            (self.max_units_per_source, "max_units_per_source"),
            (self.max_units_per_section, "max_units_per_section"),
            (self.max_parent_attachments, "max_parent_attachments"),
            (self.max_sibling_attachments, "max_sibling_attachments"),
            (self.max_window_attachments, "max_window_attachments"),
            (self.max_attachments_per_group, "max_attachments_per_group"),
        ):
            if type(value) is not int or not 0 <= value <= MAX_FUSION_ATTACHMENTS:
                raise ValueError(f"{name} must be between 0 and {MAX_FUSION_ATTACHMENTS}")
        if self.max_results < 1:
            raise ValueError("max_results must be positive")
        if self.max_units_per_source < 1 or self.max_units_per_section < 1:
            raise ValueError("diversity caps must be positive")
        object.__setattr__(
            self,
            "uncertainty_flags",
            _labels(self.uncertainty_flags, "uncertainty_flags"),
        )

    @property
    def weights(self) -> tuple[tuple[str, float], ...]:
        return self.retriever_weights


@dataclass(frozen=True, slots=True)
class FusionPriorReceipt:
    """The independently inspectable prior components applied to a group."""

    structural_prior: float = 0.0
    source_class_prior: float = 0.0
    review_prior: float = 0.0
    uncertainty_penalty: float = 0.0
    uncertainty: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.structural_prior, "structural_prior"),
            (self.source_class_prior, "source_class_prior"),
            (self.review_prior, "review_prior"),
            (self.uncertainty_penalty, "uncertainty_penalty"),
        ):
            object.__setattr__(self, name, _bounded_nonnegative(value, name))
        if type(self.uncertainty) is not bool:
            raise TypeError("uncertainty must be a boolean")
        if self.uncertainty and self.uncertainty_penalty <= 0.0:
            # A policy may intentionally use a zero penalty, but the flag must
            # still be carried.  No additional validation is needed here.
            return

    @property
    def total(self) -> float:
        return (
            self.structural_prior
            + self.source_class_prior
            + self.review_prior
            - self.uncertainty_penalty
        )

    @property
    def structural(self) -> float:
        return self.structural_prior

    @property
    def source_class(self) -> float:
        return self.source_class_prior

    @property
    def review(self) -> float:
        return self.review_prior


@dataclass(frozen=True, slots=True)
class FusionContextAttachment:
    """One wider context unit attached after the primary was ranked."""

    unit: RetrievableUnit
    relation: str

    def __post_init__(self) -> None:
        if not isinstance(self.unit, RetrievableUnit):
            raise TypeError("attachment unit must be RetrievableUnit")
        if self.relation not in {"parent", "sibling", "window"}:
            raise ValueError("attachment relation is unsupported")

    @property
    def unit_id(self) -> UnitId:
        return self.unit.unit_id

    @property
    def attachment_unit(self) -> RetrievableUnit:
        return self.unit

    @property
    def kind(self) -> str:
        return self.relation

    @property
    def reason(self) -> str:
        return self.relation


@dataclass(frozen=True, slots=True)
class FusedEvidenceGroup:
    """One deduplicated, ranked evidence group with a narrow primary."""

    primary_unit: RetrievableUnit
    score: float
    rrf_score: float
    consensus: int
    retriever_provenance: tuple[str, ...]
    prior_receipt: FusionPriorReceipt
    members: tuple[UnitId, ...] = ()
    attachments: tuple[FusionContextAttachment, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.primary_unit, RetrievableUnit):
            raise TypeError("primary_unit must be RetrievableUnit")
        for value, name in ((self.score, "score"), (self.rrf_score, "rrf_score")):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(float(value))
            ):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, float(value))
        if type(self.consensus) is not int or not 1 <= self.consensus <= MAX_FUSION_POLICY_ITEMS:
            raise ValueError("consensus is outside its bound")
        provenance = tuple(self.retriever_provenance)
        if len(provenance) != len(set(provenance)) or any(
            not isinstance(item, str) for item in provenance
        ):
            raise ValueError("retriever_provenance must contain unique text")
        object.__setattr__(self, "retriever_provenance", tuple(sorted(provenance)))
        if not isinstance(self.prior_receipt, FusionPriorReceipt):
            raise TypeError("prior_receipt must be FusionPriorReceipt")
        members = tuple(self.members)
        if any(not isinstance(item, UnitId) for item in members):
            raise TypeError("members must contain UnitId values")
        if len(members) > MAX_FUSION_CATALOG_UNITS or len(set(members)) != len(members):
            raise ValueError("members must be unique and bounded")
        object.__setattr__(self, "members", tuple(sorted(members, key=str)))
        attachments = tuple(self.attachments)
        if len(attachments) > MAX_FUSION_ATTACHMENTS or any(
            not isinstance(item, FusionContextAttachment) for item in attachments
        ):
            raise ValueError("attachments are invalid or exceed the bound")
        object.__setattr__(
            self,
            "attachments",
            tuple(sorted(attachments, key=lambda item: (item.relation, str(item.unit_id)))),
        )

    @property
    def unit(self) -> RetrievableUnit:
        return self.primary_unit

    @property
    def primary(self) -> RetrievableUnit:
        return self.primary_unit

    @property
    def unit_id(self) -> UnitId:
        return self.primary_unit.unit_id

    @property
    def canonical_ref(self) -> CanonicalRef:
        return self.primary_unit.canonical_ref

    @property
    def prior(self) -> FusionPriorReceipt:
        return self.prior_receipt

    @property
    def uncertainty(self) -> bool:
        return self.prior_receipt.uncertainty


@dataclass(frozen=True, slots=True)
class FusionResult:
    """Bounded result with an explicit empty/insufficient state."""

    status: FusionResultStatus
    groups: tuple[FusedEvidenceGroup, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, FusionResultStatus):
            raise TypeError("status must be FusionResultStatus")
        groups = tuple(self.groups)
        if len(groups) > MAX_FUSION_RESULTS or any(
            not isinstance(item, FusedEvidenceGroup) for item in groups
        ):
            raise ValueError("groups are invalid or exceed the bound")
        if self.status is FusionResultStatus.INSUFFICIENT and groups:
            raise ValueError("insufficient results cannot contain groups")
        if self.status is FusionResultStatus.READY and not groups:
            raise ValueError("ready results require at least one group")
        if self.reason is not None:
            _label(self.reason, "reason")
        object.__setattr__(self, "groups", groups)

    @property
    def ready(self) -> bool:
        return self.status is FusionResultStatus.READY

    @property
    def insufficient(self) -> bool:
        return self.status is FusionResultStatus.INSUFFICIENT

    @property
    def evidence(self) -> tuple[FusedEvidenceGroup, ...]:
        return self.groups


@dataclass(frozen=True, slots=True)
class AdmittedUnitCatalog:
    """A detached, exact-identity catalog used by the pure fusion stage."""

    units: tuple[RetrievableUnit, ...]

    def __post_init__(self) -> None:
        values = tuple(self.units)
        if len(values) > MAX_FUSION_CATALOG_UNITS:
            raise ValueError(f"catalog cannot contain more than {MAX_FUSION_CATALOG_UNITS} units")
        if any(not isinstance(item, RetrievableUnit) for item in values):
            raise TypeError("catalog must contain RetrievableUnit values")
        values = tuple(_snapshot_unit(item) for item in values)
        ids = tuple(item.unit_id for item in values)
        if len(ids) != len(set(ids)):
            raise ValueError("catalog unit identities must be unique")
        object.__setattr__(self, "units", tuple(sorted(values, key=lambda item: str(item.unit_id))))

    @classmethod
    def from_values(
        cls, values: Mapping[UnitId, RetrievableUnit] | Sequence[RetrievableUnit]
    ) -> AdmittedUnitCatalog:
        if isinstance(values, Mapping):
            entries = tuple(values.items())
            if any(key != unit.unit_id for key, unit in entries):
                raise FusionError("catalog key does not match unit_id")
            values = tuple(unit for _, unit in entries)
        return cls(tuple(values))

    def by_id(self) -> dict[UnitId, RetrievableUnit]:
        return {item.unit_id: item for item in self.units}


def _snapshot_unit(unit: RetrievableUnit) -> RetrievableUnit:
    """Detach catalog-owned values from hostile post-construction mutation."""
    reference = unit.canonical_ref
    if isinstance(reference, TextSpan):
        canonical_ref: CanonicalRef = TextSpan(
            reference.substrate_id,
            reference.start,
            reference.end,
        )
    else:
        canonical_ref = FigureBlob(reference.checksum_sha256, reference.byte_length)
    meta = UnitMeta(
        unit.meta.source_class,
        unit.meta.role,
        unit.meta.trust_level,
        unit.meta.review_status,
        frozenset(unit.meta.flags),
        unit.meta.ordinal,
        unit.meta.page_hint,
        unit.meta.language,
    )
    links = tuple(
        UnitLink(link.kind, link.target, link.provisional_target) for link in unit.links
    )
    return RetrievableUnit(
        unit.unit_id,
        unit.source_id,
        unit.revision_id,
        unit.unit_kind,
        unit.granularity,
        tuple(unit.structural_path),
        canonical_ref,
        meta,
        links,
    )


def _catalog(
    values: Mapping[UnitId, RetrievableUnit] | Sequence[RetrievableUnit] | AdmittedUnitCatalog,
) -> AdmittedUnitCatalog:
    if isinstance(values, AdmittedUnitCatalog):
        return values
    try:
        return AdmittedUnitCatalog.from_values(values)
    except FusionError:
        raise
    except (TypeError, ValueError) as error:
        raise FusionError("admitted unit catalog is invalid") from error


def _validate_ancestry(catalog: AdmittedUnitCatalog) -> dict[UnitId, RetrievableUnit]:
    by_id = catalog.by_id()
    parent_by_id: dict[UnitId, UnitId | None] = {}
    for unit in catalog.units:
        parents = tuple(link for link in unit.links if link.kind is LinkKind.PARENT)
        if not parents:
            parent_by_id[unit.unit_id] = None
            continue
        link = parents[0]
        if link.target is None or link.target not in by_id:
            raise FusionError("catalog contains a missing or provisional parent")
        parent = by_id[link.target]
        if parent.source_id != unit.source_id or parent.revision_id != unit.revision_id:
            raise FusionError("catalog contains cross-source or cross-revision ancestry")
        parent_by_id[unit.unit_id] = parent.unit_id
    for unit_id in parent_by_id:
        seen: set[UnitId] = set()
        current: UnitId | None = unit_id
        while current is not None:
            if current in seen:
                raise FusionError("catalog contains cyclic parent ancestry")
            seen.add(current)
            current = parent_by_id[current]
    return by_id


def _parent_id(unit: RetrievableUnit) -> UnitId | None:
    for link in unit.links:
        if link.kind is LinkKind.PARENT:
            return link.target
    return None


def _uncertain(unit: RetrievableUnit, policy: FusionPolicy) -> bool:
    if not unit.meta.flags:
        return False
    if not policy.uncertainty_flags:
        return True
    return bool(set(unit.meta.flags) & set(policy.uncertainty_flags))


def _section_key(
    unit: RetrievableUnit, by_id: Mapping[UnitId, RetrievableUnit]
) -> tuple[str, str, str]:
    current: RetrievableUnit | None = unit
    seen: set[UnitId] = set()
    while current is not None:
        if current.unit_id in seen:
            raise FusionError("catalog contains cyclic parent ancestry")
        seen.add(current.unit_id)
        if current.unit_kind is UnitKind.SECTION:
            return (str(current.source_id), str(current.revision_id), str(current.unit_id))
        parent = _parent_id(current)
        current = None if parent is None else by_id[parent]
    prefix = unit.structural_path[0] if unit.structural_path else ""
    return (str(unit.source_id), str(unit.revision_id), prefix)


def _lookup_prior(pairs: tuple[_PAIR_VALUE, ...], key: str) -> float:
    for candidate, value in pairs:
        if candidate == key:
            return value
    return 0.0


def _ladder_groups(
    units: tuple[RetrievableUnit, ...], by_id: Mapping[UnitId, RetrievableUnit]
) -> tuple[tuple[RetrievableUnit, ...], ...]:
    """Collapse only candidate units on one parent chain.

    A candidate with an ancestor candidate joins that ancestor's group.  A
    sibling remains a distinct group unless it too is explicitly represented
    by the same ladder; no text or non-parent relation is consulted.
    """
    candidate_ids = {unit.unit_id for unit in units}
    children_by_parent: dict[UnitId, tuple[UnitId, ...]] = {}
    for unit in units:
        parent = _parent_id(unit)
        if parent in candidate_ids:
            children_by_parent[parent] = tuple(
                sorted(
                    (*children_by_parent.get(parent, ()), unit.unit_id),
                    key=str,
                )
            )

    def owner(unit: RetrievableUnit) -> UnitId:
        current = unit
        while True:
            parent = _parent_id(current)
            if parent not in candidate_ids:
                return current.unit_id
            # A parent with multiple candidate children is not a single
            # ancestry ladder; keep each child as its own group.
            if len(children_by_parent.get(parent, ())) > 1:
                return current.unit_id
            current = by_id[parent]

    grouped: dict[UnitId, list[RetrievableUnit]] = {}
    for unit in sorted(units, key=lambda item: str(item.unit_id)):
        grouped.setdefault(owner(unit), []).append(unit)
    return tuple(
        tuple(sorted(values, key=lambda item: str(item.unit_id)))
        for _, values in sorted(grouped.items(), key=lambda item: str(item[0]))
    )


def _primary(
    group: tuple[RetrievableUnit, ...], unit_scores: Mapping[UnitId, float]
) -> RetrievableUnit:
    return sorted(
        group,
        key=lambda unit: (-unit.granularity, -unit_scores[unit.unit_id], str(unit.unit_id)),
    )[0]


def _attachments(
    primary: RetrievableUnit,
    members: tuple[UnitId, ...],
    by_id: Mapping[UnitId, RetrievableUnit],
    policy: FusionPolicy,
) -> tuple[FusionContextAttachment, ...]:
    excluded = set(members) | {primary.unit_id}
    selected: list[FusionContextAttachment] = []
    seen: set[UnitId] = set(excluded)

    parent = _parent_id(primary)
    depth = 0
    current = parent
    while current is not None and depth < policy.max_parent_attachments:
        if current not in seen:
            selected.append(FusionContextAttachment(by_id[current], "parent"))
            seen.add(current)
        depth += 1
        current = _parent_id(by_id[current])

    sibling_limit = policy.max_sibling_attachments
    primary_parent = _parent_id(primary)
    if sibling_limit and primary_parent is not None:
        siblings = [
            unit
            for unit in by_id.values()
            if unit.unit_id not in seen
            and _parent_id(unit) == primary_parent
            and unit.source_id == primary.source_id
            and unit.revision_id == primary.revision_id
        ]
        siblings.sort(
            key=lambda unit: (
                abs(unit.meta.ordinal - primary.meta.ordinal),
                unit.meta.ordinal,
                str(unit.unit_id),
            )
        )
        for unit in siblings[:sibling_limit]:
            selected.append(FusionContextAttachment(unit, "sibling"))
            seen.add(unit.unit_id)

    window_limit = policy.max_window_attachments
    if window_limit:
        same_parent = [
            unit
            for unit in by_id.values()
            if unit.unit_id not in seen
            and _parent_id(unit) == primary_parent
            and unit.source_id == primary.source_id
            and unit.revision_id == primary.revision_id
        ]
        same_parent.sort(
            key=lambda unit: (
                abs(unit.meta.ordinal - primary.meta.ordinal),
                unit.meta.ordinal,
                str(unit.unit_id),
            )
        )
        for unit in same_parent[:window_limit]:
            selected.append(FusionContextAttachment(unit, "window"))
            seen.add(unit.unit_id)
    return tuple(selected[: policy.max_attachments_per_group])


def fuse_candidates(
    batch: RetrieverSearchBatch,
    admitted_units: Mapping[UnitId, RetrievableUnit]
    | Sequence[RetrievableUnit]
    | AdmittedUnitCatalog,
    policy: FusionPolicy,
) -> FusionResult:
    """Fuse one sealed search batch into deterministic evidence groups."""
    if not isinstance(batch, RetrieverSearchBatch):
        raise TypeError("batch must be RetrieverSearchBatch")
    if not isinstance(policy, FusionPolicy):
        raise TypeError("policy must be FusionPolicy")
    catalog = _catalog(admitted_units)
    by_id = _validate_ancestry(catalog)
    manifest_ids = tuple(identity for identity, _ in batch.manifest_snapshot)
    configured = dict(policy.retriever_weights)
    unknown_weights = set(configured) - set(manifest_ids)
    if unknown_weights:
        raise FusionError("retriever weights contain an unknown manifest identity")
    required_weights = {result.retriever_identity for result in batch.results}
    if not configured and batch.results:
        raise FusionError("retriever weights are required for every result list")
    missing_weights = required_weights - set(configured)
    if missing_weights:
        raise FusionError("retriever weights are missing for a result retriever")

    contributions: dict[UnitId, dict[str, tuple[float, int]]] = {}
    unit_scores: dict[UnitId, float] = {}
    for result in batch.results:
        weight = configured[result.retriever_identity]
        for candidate in result.candidates:
            unit = by_id.get(candidate.unit_id)
            if unit is None:
                raise FusionError("candidate unit is not present in the admitted catalog")
            contribution = weight / (policy.rrf_k + candidate.rank)
            per_retriever = contributions.setdefault(candidate.unit_id, {})
            previous = per_retriever.get(result.retriever_identity)
            if previous is None or contribution > previous[0]:
                per_retriever[result.retriever_identity] = (contribution, candidate.rank)
            unit_scores[candidate.unit_id] = sum(item[0] for item in per_retriever.values())

    if not contributions:
        return FusionResult(FusionResultStatus.INSUFFICIENT, reason="no_candidates")

    candidate_units = tuple(by_id[unit_id] for unit_id in contributions)
    groups = _ladder_groups(candidate_units, by_id)
    fused: list[FusedEvidenceGroup] = []
    structural = dict(policy.structural_priors)
    source_class = dict(policy.source_class_priors)
    review = dict(policy.review_priors)
    for group_units in groups:
        primary = _primary(group_units, unit_scores)
        retrievers: set[str] = set()
        for unit in group_units:
            for retriever in contributions[unit.unit_id]:
                retrievers.add(retriever)
        # One contribution per retriever: use the best rank represented by the
        # entire ladder rather than summing parent/child duplicates.
        rrf_score = sum(
                max(
                contributions[unit.unit_id][retriever][0]
                for unit in group_units
                if retriever in contributions[unit.unit_id]
            )
            for retriever in retrievers
        )
        uncertain = _uncertain(primary, policy)
        receipt = FusionPriorReceipt(
            structural.get(primary.unit_kind.value, 0.0),
            source_class.get(primary.meta.source_class, 0.0),
            review.get(primary.meta.review_status.value, 0.0),
            policy.uncertainty_penalty if uncertain else 0.0,
            uncertain,
        )
        fused.append(
            FusedEvidenceGroup(
                primary,
                rrf_score + receipt.total,
                rrf_score,
                len(retrievers),
                tuple(retrievers),
                receipt,
                tuple(unit.unit_id for unit in group_units),
                (),
            )
        )

    ordered = sorted(fused, key=lambda group: (-group.score, -group.consensus, str(group.unit_id)))
    source_counts: dict[str, int] = {}
    section_counts: dict[tuple[str, str, str], int] = {}
    selected: list[FusedEvidenceGroup] = []
    for group in ordered:
        source = str(group.primary_unit.source_id)
        section = _section_key(group.primary_unit, by_id)
        if source_counts.get(source, 0) >= policy.max_units_per_source:
            continue
        if section_counts.get(section, 0) >= policy.max_units_per_section:
            continue
        selected.append(group)
        source_counts[source] = source_counts.get(source, 0) + 1
        section_counts[section] = section_counts.get(section, 0) + 1
        if len(selected) >= policy.max_results:
            break

    if not selected:
        return FusionResult(FusionResultStatus.INSUFFICIENT, reason="diversity_caps")
    expanded = [
        FusedEvidenceGroup(
            group.primary_unit,
            group.score,
            group.rrf_score,
            group.consensus,
            group.retriever_provenance,
            group.prior_receipt,
            group.members,
            _attachments(group.primary_unit, group.members, by_id, policy),
        )
        for group in selected
    ]
    return FusionResult(FusionResultStatus.READY, tuple(expanded))


__all__ = [
    "AdmittedUnitCatalog",
    "FusedEvidenceGroup",
    "FusionContextAttachment",
    "FusionError",
    "FusionPolicy",
    "FusionPriorReceipt",
    "FusionResult",
    "FusionResultStatus",
    "FusionStatus",
    "fuse_candidates",
]
