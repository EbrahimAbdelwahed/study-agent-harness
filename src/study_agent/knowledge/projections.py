"""Deterministic structural projection and discardable projection state."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from math import isfinite

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.projections import (
    IndexProjection,
    ProjectionId,
    ProjectorManifest,
    ProjectorPort,
)
from study_agent.domain.tree import TreeNode
from study_agent.domain.units import RetrievableUnit
from study_agent.knowledge.units import decode_unit
from study_agent.state.serialization import canonical_json_bytes

STRUCTURAL_PROJECTOR_NAME = "structural"
STRUCTURAL_PROJECTOR_VERSION = "structural-v1"
PROJECTIONS_STATE_KEY = "projections"
PROJECTION_UNITS_STATE_KEY = "projection_ids_by_unit"
MAX_ANCESTOR_COUNT = 6
MAX_ANCESTOR_DEPTH = 6
MAX_POLICY_DEPTH = 8
MAX_POLICY_ITEMS = 256
MAX_POLICY_TEXT = 512
TRUNCATION_MARKER = "…"


def _validated_ancestors(
    unit: RetrievableUnit, headings: Sequence[TreeNode]
) -> tuple[TreeNode, ...]:
    if isinstance(headings, (str, bytes, bytearray)):
        raise TypeError("ancestor_headings must be a sequence of TreeNode values")
    values = tuple(headings)
    if len(values) > MAX_ANCESTOR_COUNT:
        raise ValueError("ancestor_headings exceeds the tree depth bound")
    seen: set[object] = set()
    previous: TreeNode | None = None
    for heading in values:
        if not isinstance(heading, TreeNode):
            raise TypeError("ancestor_headings must contain TreeNode values")
        if heading.region_kind.value != "body":
            raise ValueError("ancestor headings must be BODY tree nodes")
        if heading.depth > MAX_ANCESTOR_DEPTH:
            raise ValueError("ancestor heading depth exceeds the tree bound")
        if heading.node_id in seen:
            raise ValueError("ancestor headings must be unique")
        seen.add(heading.node_id)
        if (
            len(heading.path) > len(unit.structural_path)
            or tuple(unit.structural_path[: heading.depth]) != heading.path
        ):
            raise ValueError("ancestor heading path is not a prefix of the unit path")
        if previous is not None and (
            heading.depth <= previous.depth or heading.parent_id != previous.node_id
        ):
            raise ValueError("ancestor headings must be ordered root-to-leaf")
        previous = heading
    return values


def _labels(unit: RetrievableUnit, headings: Sequence[TreeNode]) -> tuple[str, ...]:
    values = _validated_ancestors(unit, headings)
    labels: list[str] = []
    for heading in values:
        label = heading.heading_text.strip()
        if not label and heading.path:
            label = heading.path[-1].replace("-", " ").strip()
        if label:
            labels.append(label)
    if labels:
        return tuple(labels)
    return tuple(s.replace("-", " ").strip() for s in unit.structural_path if s.strip())


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER


def _context(unit: RetrievableUnit, headings: Sequence[TreeNode]) -> str:
    labels = _labels(unit, headings)
    return _truncate(" > ".join(labels) if labels else "document", 1_024)


def _weak(value: str) -> bool:
    normalized = " ".join(value.lower().split())
    return len(normalized) < 3 or normalized in {
        "body",
        "content",
        "document",
        "heading",
        "root",
        "section",
        "untitled",
    }


def _policy(value: Mapping[str, JsonValue] | Sequence[JsonValue], name: str) -> JsonValue:
    count = 0

    def visit(item: JsonValue, depth: int) -> JsonValue:
        nonlocal count
        count += 1
        if count > MAX_POLICY_ITEMS:
            raise ValueError(f"{name} exceeds the policy item bound")
        if depth > MAX_POLICY_DEPTH:
            raise ValueError(f"{name} exceeds the policy depth bound")
        if isinstance(item, Mapping):
            result: dict[str, JsonValue] = {}
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > MAX_POLICY_TEXT:
                    raise ValueError(f"{name} keys must be bounded strings")
                result[key] = visit(child, depth + 1)
            return result
        if isinstance(item, tuple):
            return tuple(visit(child, depth + 1) for child in item)
        if isinstance(item, str):
            if len(item) > MAX_POLICY_TEXT or "\x00" in item:
                raise ValueError(f"{name} text values are too large")
            return item
        if isinstance(item, float) and not isfinite(item):
            raise ValueError(f"{name} numeric values must be finite")
        if isinstance(item, (str, int, float, bool)) or item is None:
            return item
        raise TypeError(f"{name} contains unsupported value")

    if isinstance(value, Mapping):
        return visit(value, 0)
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a mapping or sequence")
    return visit(tuple(value), 0)


def projection_input_fingerprint(
    unit: RetrievableUnit,
    ancestor_headings: Sequence[TreeNode],
    *,
    scope_policy: Mapping[str, JsonValue] | Sequence[JsonValue] = (),
    producer_policy: Mapping[str, JsonValue] | Sequence[JsonValue] = (),
) -> str:
    ancestors = _validated_ancestors(unit, ancestor_headings)
    context = _context(unit, ancestors)
    payload: JsonObject = {
        "ancestor_nodes": tuple(node.to_json() for node in ancestors),
        "ancestor_headings": _labels(unit, ancestors),
        "producer_policy": _policy(producer_policy, "producer_policy"),
        "scope_policy": _policy(scope_policy, "scope_policy"),
        "structural_context": context,
        "unit": unit.to_json(),
    }
    return sha256(
        b"study-agent/index-projection-input/v1\0" + canonical_json_bytes(payload)
    ).hexdigest()


class StructuralProjector:
    """Offline projector using only a unit and admitted heading context."""

    manifest = ProjectorManifest(STRUCTURAL_PROJECTOR_NAME, STRUCTURAL_PROJECTOR_VERSION)

    def project(
        self,
        unit: RetrievableUnit,
        ancestor_headings: Sequence[TreeNode],
        *,
        scope_policy: Mapping[str, JsonValue] | Sequence[JsonValue] = (),
        producer_policy: Mapping[str, JsonValue] | Sequence[JsonValue] = (),
    ) -> IndexProjection:
        if not isinstance(unit, RetrievableUnit):
            raise TypeError("structural projector requires RetrievableUnit")
        ancestors = _validated_ancestors(unit, ancestor_headings)
        labels = _labels(unit, ancestors)
        context = _context(unit, ancestors)
        descriptive = tuple(label for label in labels if not _weak(label))
        handle = (
            f"{unit.unit_kind.value}: {_truncate(descriptive[-1], 512)}"
            if descriptive
            else f"{unit.unit_kind.value} unit in {context}"
        )
        handle = _truncate(handle, 512)
        fingerprint = projection_input_fingerprint(
            unit, ancestors, scope_policy=scope_policy, producer_policy=producer_policy
        )
        output = IndexProjection.derive_output_sha256(
            handle=handle,
            summary=None,
            key_terms=(),
            aliases=(),
            covers=(),
            structural_context=context,
        )
        return IndexProjection(
            unit.unit_id,
            fingerprint,
            handle,
            None,
            (),
            (),
            (),
            context,
            self.manifest.name,
            self.manifest.version,
            self.manifest.model_id,
            output,
        )


def project_structural(
    unit: RetrievableUnit,
    ancestor_headings: Sequence[TreeNode],
    *,
    scope_policy: Mapping[str, JsonValue] | Sequence[JsonValue] = (),
    producer_policy: Mapping[str, JsonValue] | Sequence[JsonValue] = (),
) -> IndexProjection:
    return StructuralProjector().project(
        unit, ancestor_headings, scope_policy=scope_policy, producer_policy=producer_policy
    )


def admit_projection(projection: IndexProjection) -> IndexProjection:
    if not isinstance(projection, IndexProjection):
        raise TypeError("projection state requires IndexProjection values")
    _ = projection.projection_id
    return projection


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def reduce_projections(
    state: JsonObject, projections: Sequence[IndexProjection]
) -> Mapping[str, JsonValue]:
    canonical_units = _canonical_units(state)
    rows = dict(_mapping(state.get(PROJECTIONS_STATE_KEY, {}), PROJECTIONS_STATE_KEY))
    by_unit = dict(_mapping(state.get(PROJECTION_UNITS_STATE_KEY, {}), PROJECTION_UNITS_STATE_KEY))
    for projection in projections:
        admit_projection(projection)
        if str(projection.unit_id) not in canonical_units:
            raise ValueError("projection references an unknown canonical unit")
        key, encoded = str(projection.projection_id), projection.to_json()
        if key in rows and rows[key] != encoded:
            raise ValueError("projection id already exists with different content")
        rows[key] = encoded
        unit_key = str(projection.unit_id)
        current = by_unit.get(unit_key, ())
        if not isinstance(current, tuple) or any(not isinstance(item, str) for item in current):
            raise ValueError("projection unit index is invalid")
        if key not in current:
            by_unit[unit_key] = (*current, key)
    return {**state, PROJECTIONS_STATE_KEY: rows, PROJECTION_UNITS_STATE_KEY: by_unit}


def _canonical_units(state: JsonObject) -> Mapping[str, JsonValue]:
    units = state.get("units")
    if not isinstance(units, Mapping):
        raise ValueError("canonical state must contain a units object")
    for key, raw in units.items():
        if not isinstance(key, str) or not isinstance(raw, Mapping):
            raise ValueError("canonical units state is malformed")
        decoded = decode_unit(raw)
        if str(decoded.unit_id) != key:
            raise ValueError("canonical unit index key does not match unit identity")
    return units


def delete_projections(
    state: JsonObject,
    *,
    projection_ids: Sequence[ProjectionId | str] = (),
    unit_ids: Sequence[object] = (),
    projector_name: str | None = None,
    projector_version: str | None = None,
) -> Mapping[str, JsonValue]:
    if projector_version is not None and projector_name is None:
        raise ValueError("projector_version requires projector_name")
    rows = dict(_mapping(state.get(PROJECTIONS_STATE_KEY, {}), PROJECTIONS_STATE_KEY))
    by_unit = dict(_mapping(state.get(PROJECTION_UNITS_STATE_KEY, {}), PROJECTION_UNITS_STATE_KEY))
    selected, units = {str(x) for x in projection_ids}, {str(x) for x in unit_ids}
    if not selected and not units and projector_name is None and projector_version is None:
        return state
    for key, raw in tuple(rows.items()):
        if not isinstance(raw, Mapping):
            raise ValueError("projection state row is invalid")
        projection = IndexProjection.from_json(raw)
        producer_match = (
            (projector_name is None or projection.projector_name == projector_name)
            and (projector_version is None or projection.projector_version == projector_version)
            and (projector_name is not None or projector_version is not None)
        )
        remove = key in selected or str(projection.unit_id) in units or producer_match
        if remove:
            rows.pop(key)
    for unit_key, keys in tuple(by_unit.items()):
        if not isinstance(keys, tuple):
            raise ValueError("projection unit index is invalid")
        remaining = tuple(key for key in keys if key in rows)
        if remaining:
            by_unit[unit_key] = remaining
        else:
            by_unit.pop(unit_key)
    return {**state, PROJECTIONS_STATE_KEY: rows, PROJECTION_UNITS_STATE_KEY: by_unit}


def delete_all_projections(state: JsonObject) -> Mapping[str, JsonValue]:
    rows = _mapping(state.get(PROJECTIONS_STATE_KEY, {}), PROJECTIONS_STATE_KEY)
    return delete_projections(state, projection_ids=tuple(rows))


__all__ = [
    "PROJECTIONS_STATE_KEY",
    "PROJECTION_UNITS_STATE_KEY",
    "STRUCTURAL_PROJECTOR_NAME",
    "STRUCTURAL_PROJECTOR_VERSION",
    "ProjectorPort",
    "StructuralProjector",
    "admit_projection",
    "delete_all_projections",
    "delete_projections",
    "project_structural",
    "projection_input_fingerprint",
    "reduce_projections",
]
