"""The single replayable owner of retrievable unit rows.

Adapters and indexes never write an authoritative unit row: they consume this
projection.  Unit boundary algorithms are deliberately absent — KB-06 owns
them; this module owns identity, admission, and replay.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.identifiers import (
    RevisionId,
    SourceId,
    SubstrateId,
    UnitId,
    unit_id_for,
)
from study_agent.domain.source import SourceChunk
from study_agent.domain.units import (
    LinkKind,
    RetrievableUnit,
    ReviewStatus,
    TextSpan,
    UnitKind,
    UnitLink,
    UnitMeta,
    decode_canonical_ref,
)

#: Bumping this version deliberately changes every derived ``unit_id``.
UNITIZER_VERSION = "unitizer-v1"


@dataclass(frozen=True, slots=True)
class RevisionBinding:
    """What one revision is actually bound to in canonical state.

    ``unit_id`` deliberately excludes ``source_id`` and the substrate because
    ``revision_id`` already binds both (ADR-0014).  Identity alone therefore
    cannot detect a unit that names a real span under the wrong source, or a
    revision that was never ingested at all, so the caller must supply the real
    bindings and admission checks against them.
    """

    source_id: SourceId
    substrate_id: SubstrateId
    character_length: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise TypeError("binding source_id must be SourceId")
        if not isinstance(self.substrate_id, SubstrateId):
            raise TypeError("binding substrate_id must be SubstrateId")
        if type(self.character_length) is not int or self.character_length < 1:
            raise ValueError("binding character_length must be positive")


def derive_unit_id(
    unit: RetrievableUnit,
    *,
    unitizer_version: str = UNITIZER_VERSION,
) -> UnitId:
    """Re-derive the identity a unit must carry to be admissible.

    The version is explicit caller context rather than persisted unit state.
    This lets a migration validate old and new unitizer outputs without
    silently inferring a policy from an opaque ``UnitId`` digest.
    """
    _require_unitizer_version(unitizer_version)
    return unit_id_for(
        revision_id=unit.revision_id,
        structural_path=unit.structural_path,
        unit_kind=unit.unit_kind.value,
        granularity=unit.granularity,
        canonical_ref=dict(unit.canonical_ref.to_json()),
        unitizer_version=unitizer_version,
    )


def admit(
    unit: RetrievableUnit,
    *,
    unitizer_version: str = UNITIZER_VERSION,
) -> RetrievableUnit:
    """Reject any unit whose identity does not match its immutable fields."""
    if not isinstance(unit, RetrievableUnit):
        raise TypeError("unit projection requires RetrievableUnit values")
    if unit.unit_id != derive_unit_id(unit, unitizer_version=unitizer_version):
        raise ValueError("unit_id does not match its immutable placement fields")
    return unit


def reduce_units(
    state: JsonObject,
    units: Sequence[RetrievableUnit],
    *,
    bindings: Mapping[str, RevisionBinding],
    unitizer_version: str = UNITIZER_VERSION,
) -> Mapping[str, JsonValue]:
    """Materialize units idempotently into replayable projection state.

    Admission is transactional: the whole batch is validated for identity,
    revision coherence, and link integrity before any row is written, so a
    rejected batch can never leave a half-applied projection behind.
    """
    _require_unitizer_version(unitizer_version)
    rows = dict(_mapping(state.get("units", {}), "units"))
    by_revision = dict(_mapping(state.get("units_by_revision", {}), "units_by_revision"))
    for unit in units:
        admit(unit, unitizer_version=unitizer_version)
        _require_binding(unit, bindings)
    _require_revision_coherence(rows, units)
    _require_link_integrity(rows, units)
    for unit in units:
        key = str(unit.unit_id)
        encoded = unit.to_json()
        existing = rows.get(key)
        if existing is not None:
            if existing != encoded:
                raise ValueError("unit id already exists with different immutable metadata")
            continue
        rows[key] = encoded
        revision_key = str(unit.revision_id)
        current = by_revision.get(revision_key, ())
        if not isinstance(current, tuple) or any(
            not isinstance(value, str) for value in current
        ):
            raise ValueError("unit revision index is invalid")
        if key not in current:
            by_revision[revision_key] = (*current, key)
    return {**state, "units": rows, "units_by_revision": by_revision}


def _require_binding(
    unit: RetrievableUnit, bindings: Mapping[str, RevisionBinding]
) -> None:
    """Reject a unit that does not match real canonical state."""
    binding = bindings.get(str(unit.revision_id))
    if binding is None:
        raise ValueError("unit references a revision that is not ingested")
    if binding.source_id != unit.source_id:
        raise ValueError("unit source does not own its revision")
    ref = unit.canonical_ref
    if isinstance(ref, TextSpan):
        if ref.substrate_id != binding.substrate_id:
            raise ValueError("unit span references a substrate not bound to its revision")
        if ref.end > binding.character_length:
            raise ValueError("unit span exceeds the substrate character length")


def _require_revision_coherence(
    rows: Mapping[str, JsonValue], units: Sequence[RetrievableUnit]
) -> None:
    """One revision binds exactly one source and one text substrate.

    ``unit_id`` deliberately excludes ``source_id`` and the substrate, because
    ``revision_id`` already binds both.  That makes those two fields unchecked
    by identity alone, so the projection owner asserts the binding here rather
    than trusting whatever a unitizer supplied.
    """
    sources: dict[str, str] = {}
    substrates: dict[str, str] = {}
    for key, value in rows.items():
        row = _mapping(value, f"units.{key}")
        revision = row.get("revision_id")
        source = row.get("source_id")
        if isinstance(revision, str) and isinstance(source, str):
            sources[revision] = source
        ref = row.get("canonical_ref")
        if isinstance(ref, Mapping) and ref.get("kind") == "text_span":
            substrate = ref.get("substrate_id")
            if isinstance(revision, str) and isinstance(substrate, str):
                substrates[revision] = substrate
    for unit in units:
        revision = str(unit.revision_id)
        source = str(unit.source_id)
        known_source = sources.setdefault(revision, source)
        if known_source != source:
            raise ValueError("a revision cannot belong to two different sources")
        bound = unit.substrate_id
        if bound is None:
            continue
        known_substrate = substrates.setdefault(revision, str(bound))
        if known_substrate != str(bound):
            raise ValueError("a revision cannot bind two different text substrates")


def _require_link_integrity(
    rows: Mapping[str, JsonValue], units: Sequence[RetrievableUnit]
) -> None:
    """Every declared target must be known, and parent chains must be acyclic."""
    known = set(rows) | {str(unit.unit_id) for unit in units}
    parents: dict[str, str] = {}
    for key, value in rows.items():
        row = _mapping(value, f"units.{key}")
        links = row.get("links")
        if not isinstance(links, tuple):
            continue
        for entry in links:
            if isinstance(entry, Mapping) and entry.get("kind") == LinkKind.PARENT.value:
                stored = entry.get("target")
                if isinstance(stored, str):
                    parents[key] = stored
    for unit in units:
        for link in unit.links:
            if link.target is None:
                continue
            if str(link.target) not in known:
                raise ValueError(
                    "a link must reference a known unit or an explicit provisional target"
                )
            if link.kind is LinkKind.PARENT:
                parents[str(unit.unit_id)] = str(link.target)
    for start in parents:
        seen: set[str] = set()
        current: str | None = start
        while current is not None:
            if current in seen:
                raise ValueError("parent links must not form a cycle")
            seen.add(current)
            current = parents.get(current)


_UNIT_KEYS = frozenset(
    {
        "canonical_ref",
        "granularity",
        "links",
        "meta",
        "revision_id",
        "source_id",
        "structural_path",
        "unit_id",
        "unit_kind",
    }
)
_META_KEYS = frozenset(
    {
        "flags",
        "language",
        "ordinal",
        "page_hint",
        "review_status",
        "role",
        "source_class",
        "trust_level",
    }
)
_LINK_KEYS = frozenset({"kind", "provisional_target", "target"})


def decode_unit(
    payload: JsonObject,
    *,
    unitizer_version: str = UNITIZER_VERSION,
) -> RetrievableUnit:
    """Decode one strict unit row; unknown or missing fields fail closed."""
    top = _object(payload, "unit", _UNIT_KEYS)
    unit = RetrievableUnit(
        UnitId(_text(top.get("unit_id"), "unit_id")),
        SourceId(_text(top.get("source_id"), "source_id")),
        RevisionId(_text(top.get("revision_id"), "revision_id")),
        UnitKind(_text(top.get("unit_kind"), "unit_kind")),
        _integer(top.get("granularity"), "granularity"),
        _segments(top.get("structural_path")),
        decode_canonical_ref(_object(top.get("canonical_ref"), "canonical_ref", None)),
        _decode_meta(top.get("meta")),
        _decode_links(top.get("links")),
    )
    return admit(unit, unitizer_version=unitizer_version)


def _decode_meta(value: JsonValue | None) -> UnitMeta:
    payload = _object(value, "meta", _META_KEYS)
    page_hint = payload.get("page_hint")
    if page_hint is not None and type(page_hint) is not int:
        raise ValueError("meta.page_hint must be an integer or null")
    language = payload.get("language")
    if language is not None and not isinstance(language, str):
        raise ValueError("meta.language must be a string or null")
    return UnitMeta(
        _text(payload.get("source_class"), "meta.source_class"),
        _text(payload.get("role"), "meta.role"),
        _integer(payload.get("trust_level"), "meta.trust_level"),
        ReviewStatus(_text(payload.get("review_status"), "meta.review_status")),
        frozenset(_segments(payload.get("flags"))),
        _integer(payload.get("ordinal"), "meta.ordinal"),
        page_hint,
        language,
    )


def _decode_links(value: JsonValue | None) -> tuple[UnitLink, ...]:
    if not isinstance(value, tuple):
        raise ValueError("links must be an array")
    links: list[UnitLink] = []
    for index, entry in enumerate(value):
        payload = _object(entry, f"links[{index}]", _LINK_KEYS)
        target = payload.get("target")
        provisional = payload.get("provisional_target")
        if target is not None and not isinstance(target, str):
            raise ValueError(f"links[{index}].target must be a string or null")
        if provisional is not None and not isinstance(provisional, str):
            raise ValueError(f"links[{index}].provisional_target must be a string or null")
        links.append(
            UnitLink(
                LinkKind(_text(payload.get("kind"), f"links[{index}].kind")),
                None if target is None else UnitId(target),
                provisional,
            )
        )
    return tuple(links)


def _object(
    value: JsonValue | None, name: str, keys: frozenset[str] | None
) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    if keys is not None and frozenset(value) != keys:
        missing = sorted(keys - frozenset(value))
        extra = sorted(frozenset(value) - keys)
        raise ValueError(f"{name} fields mismatch; missing={missing}, extra={extra}")
    return value


def _segments(value: JsonValue | None) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError("expected an array of strings")
    if any(not isinstance(entry, str) for entry in value):
        raise ValueError("expected an array of strings")
    return tuple(str(entry) for entry in value)


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


def _integer(value: JsonValue | None, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def _require_unitizer_version(value: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("unitizer_version must be non-empty trimmed text")


def unit_from_legacy_chunk(
    chunk: SourceChunk,
    *,
    substrate_id: SubstrateId,
    meta: UnitMeta,
) -> RetrievableUnit:
    """The documented v0.1 migration seam.

    A v0.1 ``SourceChunk`` maps deterministically onto exactly one ``passage``
    unit over the same substrate span.  No v0.1 event is rewritten and no
    second unit authority is introduced.
    """
    if not isinstance(chunk, SourceChunk):
        raise TypeError("legacy migration requires SourceChunk")
    span = TextSpan(substrate_id, chunk.start_offset, chunk.end_offset)
    path = chunk.section_path or ("document",)
    return RetrievableUnit(
        unit_id_for(
            revision_id=chunk.revision_id,
            structural_path=path,
            unit_kind=UnitKind.PASSAGE.value,
            granularity=3,
            canonical_ref=dict(span.to_json()),
            unitizer_version=UNITIZER_VERSION,
        ),
        chunk.source_id,
        chunk.revision_id,
        UnitKind.PASSAGE,
        3,
        path,
        span,
        meta,
    )


def _mapping(value: JsonValue | None, name: str) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ValueError(f"projection field {name} must be an object")
    return value


__all__ = [
    "UNITIZER_VERSION",
    "RevisionBinding",
    "admit",
    "decode_unit",
    "derive_unit_id",
    "reduce_units",
    "unit_from_legacy_chunk",
]
