"""Closed, provider-neutral pedagogical profile contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, cast

from study_agent.domain._validation import JsonObject, JsonValue, freeze_object, require_text
from study_agent.domain.events import PrincipalKind
from study_agent.domain.identifiers import InteractionId, RevisionId


class PedagogicalProfileId(StrEnum):
    HYBRID_MACRO_DETAIL = "hybrid-macro-detail"
    MORPHOLOGY_FIRST_ANATOMY = "morphology-first-anatomy"


@dataclass(frozen=True, slots=True)
class PedagogicalProfileRef:
    id: PedagogicalProfileId
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.id, PedagogicalProfileId):
            raise TypeError("profile id must use PedagogicalProfileId")
        if type(self.version) is not int or self.version < 1:
            raise ValueError("profile version must be positive")

    @property
    def identity(self) -> str:
        return f"{self.id.value}@{self.version}"

    def to_json(self) -> JsonObject:
        return freeze_object({"id": self.id.value, "version": self.version})


HYBRID_MACRO_DETAIL_V1 = PedagogicalProfileRef(PedagogicalProfileId.HYBRID_MACRO_DETAIL, 1)
MORPHOLOGY_FIRST_ANATOMY_V1 = PedagogicalProfileRef(
    PedagogicalProfileId.MORPHOLOGY_FIRST_ANATOMY, 1
)


class ProfileSelectionMode(StrEnum):
    DEFAULT = "default"
    EXPLICIT_REQUEST = "explicit_request"
    TRUSTED_METADATA = "trusted_metadata"


class ProfileSelectorKind(StrEnum):
    HOST = "host"
    HUMAN = "human"
    TRUSTED_MATERIAL = "trusted_material"


@dataclass(frozen=True, slots=True)
class ProfileSelectionBasis:
    interaction_id: InteractionId | None = None
    source_revision_id: RevisionId | None = None

    def __post_init__(self) -> None:
        if self.interaction_id is not None and not isinstance(self.interaction_id, InteractionId):
            raise TypeError("selection interaction basis must use InteractionId")
        if self.source_revision_id is not None and not isinstance(
            self.source_revision_id, RevisionId
        ):
            raise TypeError("selection source basis must use RevisionId")
        present = int(self.interaction_id is not None) + int(self.source_revision_id is not None)
        if present > 1:
            raise ValueError("selection basis must contain at most one reference")


@dataclass(frozen=True, slots=True)
class ProfileSelectionReceipt:
    profile: PedagogicalProfileRef
    mode: ProfileSelectionMode
    selector_kind: ProfileSelectorKind
    selector_authority: PrincipalKind
    basis: ProfileSelectionBasis

    def __post_init__(self) -> None:
        if not isinstance(self.profile, PedagogicalProfileRef):
            raise TypeError("selection profile must be PedagogicalProfileRef")
        if self.profile not in (
            HYBRID_MACRO_DETAIL_V1,
            MORPHOLOGY_FIRST_ANATOMY_V1,
        ):
            raise ValueError(f"unknown pedagogical profile: {self.profile.identity}")
        if not isinstance(self.mode, ProfileSelectionMode):
            raise TypeError("selection mode must use ProfileSelectionMode")
        if not isinstance(self.selector_kind, ProfileSelectorKind):
            raise TypeError("selector kind must use ProfileSelectorKind")
        if not isinstance(self.selector_authority, PrincipalKind):
            raise TypeError("selector authority must use PrincipalKind")
        if self.selector_authority is PrincipalKind.MODEL:
            raise ValueError("MODEL cannot select a pedagogical profile")
        if not isinstance(self.basis, ProfileSelectionBasis):
            raise TypeError("selection basis must use ProfileSelectionBasis")

        has_interaction = self.basis.interaction_id is not None
        has_revision = self.basis.source_revision_id is not None
        if self.mode is ProfileSelectionMode.DEFAULT:
            if self.profile != HYBRID_MACRO_DETAIL_V1:
                raise ValueError("default selection is valid only for hybrid-macro-detail@1")
            if has_interaction or has_revision:
                raise ValueError("default selection cannot contain an evidence basis")
            if self.selector_kind is not ProfileSelectorKind.HOST:
                raise ValueError("default selection must be performed by the host")
        elif self.mode is ProfileSelectionMode.EXPLICIT_REQUEST:
            if not has_interaction or has_revision:
                raise ValueError("explicit selection requires one learner interaction basis")
            if self.selector_kind is not ProfileSelectorKind.HUMAN:
                raise ValueError("explicit selection must identify a human selector")
            if self.selector_authority is not PrincipalKind.HUMAN:
                raise ValueError("explicit selection requires HUMAN authority")
        elif self.mode is ProfileSelectionMode.TRUSTED_METADATA:
            if not has_revision or has_interaction:
                raise ValueError("trusted metadata selection requires one source revision basis")
            if self.selector_kind is not ProfileSelectorKind.TRUSTED_MATERIAL:
                raise ValueError("trusted metadata selection requires trusted material")

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "profile": self.profile.to_json(),
                "mode": self.mode.value,
                "selector_kind": self.selector_kind.value,
                "selector_authority": self.selector_authority.value,
                "basis": {
                    "interaction_id": (
                        str(self.basis.interaction_id) if self.basis.interaction_id else None
                    ),
                    "source_revision_id": (
                        str(self.basis.source_revision_id)
                        if self.basis.source_revision_id
                        else None
                    ),
                },
            }
        )

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> ProfileSelectionReceipt:
        _exact(
            value,
            {"profile", "mode", "selector_kind", "selector_authority", "basis"},
            "profile selection",
        )
        profile = _object(value, "profile")
        basis = _object(value, "basis")
        _exact(profile, {"id", "version"}, "selected profile")
        _exact(basis, {"interaction_id", "source_revision_id"}, "selection basis")
        interaction = _optional_string(basis, "interaction_id")
        revision = _optional_string(basis, "source_revision_id")
        return cls(
            profile=PedagogicalProfileRef(
                PedagogicalProfileId(_string(profile, "id")), _integer(profile, "version")
            ),
            mode=ProfileSelectionMode(_string(value, "mode")),
            selector_kind=ProfileSelectorKind(_string(value, "selector_kind")),
            selector_authority=PrincipalKind(_string(value, "selector_authority")),
            basis=ProfileSelectionBasis(
                InteractionId(interaction) if interaction else None,
                RevisionId(revision) if revision else None,
            ),
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> ProfileSelectionReceipt:
        decoded: Any = json.loads(data)
        if not isinstance(decoded, dict):
            raise ValueError("profile selection must be a JSON object")
        receipt = cls.from_json(cast(dict[str, JsonValue], decoded))
        if receipt.to_bytes() != data:
            raise ValueError("profile selection bytes are not canonical")
        return receipt


@dataclass(frozen=True, slots=True)
class PedagogicalProfileDescriptor:
    ref: PedagogicalProfileRef
    selection_rule: str
    recommended_ceiling_range: tuple[int, int] | None
    hard_ceiling: int
    ordered_roles: tuple[str, ...]
    grounding_invariants: tuple[str, ...]
    exporter_neutral_invariants: tuple[str, ...]
    macro_to_atomic_maximum: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ref, PedagogicalProfileRef):
            raise TypeError("profile descriptor ref must use PedagogicalProfileRef")
        for name in ("selection_rule",):
            require_text(getattr(self, name), name)
        for name in ("ordered_roles", "grounding_invariants", "exporter_neutral_invariants"):
            values = tuple(getattr(self, name))
            if not values or len(set(values)) != len(values):
                raise ValueError(f"{name} must be non-empty and unique")
            for value in values:
                require_text(value, f"{name} item")
            object.__setattr__(self, name, values)
        if type(self.hard_ceiling) is not int or self.hard_ceiling < 1:
            raise ValueError("profile hard ceiling must be positive")
        if self.recommended_ceiling_range is not None:
            ceiling_range = tuple(self.recommended_ceiling_range)
            if len(ceiling_range) != 2:
                raise ValueError("recommended ceiling range must contain low and high")
            low, high = ceiling_range
            if (
                type(low) is not int
                or type(high) is not int
                or not 1 <= low <= high <= self.hard_ceiling
            ):
                raise ValueError(
                    "recommended ceiling range must be positive, ordered, and within hard ceiling"
                )
            object.__setattr__(self, "recommended_ceiling_range", (low, high))
        if self.macro_to_atomic_maximum is not None and (
            type(self.macro_to_atomic_maximum) is not int or self.macro_to_atomic_maximum < 1
        ):
            raise ValueError("macro_to_atomic_maximum must be a positive integer")

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "profile": self.ref.to_json(),
                "selection_rule": self.selection_rule,
                "recommended_ceiling_range": self.recommended_ceiling_range,
                "hard_ceiling": self.hard_ceiling,
                "ordered_roles": self.ordered_roles,
                "grounding_invariants": self.grounding_invariants,
                "exporter_neutral_invariants": self.exporter_neutral_invariants,
                "macro_to_atomic_maximum": self.macro_to_atomic_maximum,
            }
        )


HYBRID_MACRO_DETAIL_DESCRIPTOR = PedagogicalProfileDescriptor(
    ref=HYBRID_MACRO_DETAIL_V1,
    selection_rule=(
        "Use by default for general medical lessons, mechanisms, sequences, "
        "comparisons, and mixed material."
    ),
    recommended_ceiling_range=(16, 22),
    hard_ceiling=24,
    ordered_roles=("overview", "section", "detail"),
    grounding_invariants=(
        "Build a compact whole-source index before proposing cards.",
        "Create bounded framework cards before earned details.",
        "Add a detail only when it is fragile and not recoverable from its parent.",
        "Treat budgets as ceilings, never quotas.",
    ),
    exporter_neutral_invariants=(
        "Use direct recall or contextual gaps, not Anki note types.",
        "Do not emit decks, tags, templates, raw HTML, or media filenames.",
    ),
)

MORPHOLOGY_FIRST_ANATOMY_DESCRIPTOR = PedagogicalProfileDescriptor(
    ref=MORPHOLOGY_FIRST_ANATOMY_V1,
    selection_rule=(
        "Use only when explicitly requested or supported by trusted material metadata "
        "for anatomical objects or regions whose retrieval job is spatial reconstruction."
    ),
    recommended_ceiling_range=None,
    hard_ceiling=24,
    ordered_roles=("macro_reconstruction", "atomic_discrimination"),
    grounding_invariants=(
        "Keep reconstruction cards dominant.",
        "Add no more than three earned discriminations per macro.",
        "Use contextual gaps only for compact relations or sequences.",
        "Verified media may support recall only with trusted blob and source linkage.",
    ),
    exporter_neutral_invariants=(
        "Represent answer structure and media as canonical data, not presentation markup.",
        "Do not emit decks, tags, templates, raw HTML, or media filenames.",
    ),
    macro_to_atomic_maximum=3,
)


class PedagogicalProfileCatalog:
    """Immutable closed catalog; hosts can discover but cannot register profiles."""

    def __init__(self) -> None:
        self._descriptors = MappingProxyType(
            {
                HYBRID_MACRO_DETAIL_V1: HYBRID_MACRO_DETAIL_DESCRIPTOR,
                MORPHOLOGY_FIRST_ANATOMY_V1: MORPHOLOGY_FIRST_ANATOMY_DESCRIPTOR,
            }
        )

    @property
    def default(self) -> PedagogicalProfileRef:
        return HYBRID_MACRO_DETAIL_V1

    def list(self) -> tuple[PedagogicalProfileDescriptor, ...]:
        return tuple(self._descriptors.values())

    def resolve(self, ref: PedagogicalProfileRef) -> PedagogicalProfileDescriptor:
        try:
            return self._descriptors[ref]
        except KeyError as exc:
            raise ValueError(f"unknown pedagogical profile: {ref.identity}") from exc


PEDAGOGICAL_PROFILE_CATALOG = PedagogicalProfileCatalog()


def _object(value: Mapping[str, JsonValue], key: str) -> Mapping[str, JsonValue]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise ValueError(f"{key} must be an object")
    return item


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        raise ValueError(f"{key} must be a string")
    return item


def _optional_string(value: Mapping[str, JsonValue], key: str) -> str | None:
    item = value.get(key)
    if item is not None and not isinstance(item, str):
        raise ValueError(f"{key} must be a string or null")
    return item


def _integer(value: Mapping[str, JsonValue], key: str) -> int:
    item = value.get(key)
    if type(item) is not int:
        raise ValueError(f"{key} must be an integer")
    return item


def _exact(value: Mapping[str, JsonValue], fields: set[str], name: str) -> None:
    if set(value) != fields:
        raise ValueError(f"{name} fields must be exactly {sorted(fields)}")


def _canonical_bytes(value: JsonObject) -> bytes:
    def plain(item: JsonValue) -> object:
        if isinstance(item, Mapping):
            return {key: plain(child) for key, child in item.items()}
        if isinstance(item, tuple):
            return [plain(child) for child in item]
        return item

    return json.dumps(
        plain(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


__all__ = [
    "HYBRID_MACRO_DETAIL_DESCRIPTOR",
    "HYBRID_MACRO_DETAIL_V1",
    "MORPHOLOGY_FIRST_ANATOMY_DESCRIPTOR",
    "MORPHOLOGY_FIRST_ANATOMY_V1",
    "PEDAGOGICAL_PROFILE_CATALOG",
    "PedagogicalProfileCatalog",
    "PedagogicalProfileDescriptor",
    "PedagogicalProfileId",
    "PedagogicalProfileRef",
    "ProfileSelectionBasis",
    "ProfileSelectionMode",
    "ProfileSelectionReceipt",
    "ProfileSelectorKind",
]
