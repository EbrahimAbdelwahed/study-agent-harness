"""One small, iterative JSON profile for identity-bearing boundaries.

The source and citation codecs intentionally share this profile.  It is kept
independent from the event-state serializer because identity boundaries need
stricter numeric and resource limits than general projection state.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import cast

from ._validation import JsonObject, JsonValue

MAX_BOUNDARY_DEPTH = 8
MAX_BOUNDARY_NODES = 256
MAX_BOUNDARY_ITEMS = 64
MAX_BOUNDARY_STRING_BYTES = 1_024
MAX_METADATA_BYTES = 16 * 1_024
MAX_CITATION_BYTES = 16 * 1_024
MIN_IDENTITY_INTEGER = -(2**63)
MAX_IDENTITY_INTEGER = 2**63 - 1


class BoundedJsonError(ValueError):
    """A value is not representable in the bounded identity JSON profile."""


class _FrozenObject(Mapping[str, JsonValue]):
    """Private immutable object produced by this validator.

    ``MappingProxyType`` is intentionally not accepted as construction input:
    a proxy can wrap an arbitrary user mapping and invoke its methods while it
    is being walked.  This small private type is the trusted representation we
    create after validating exact built-in dictionaries.
    """

    __slots__ = ("_items_data",)
    _items_data: tuple[tuple[str, JsonValue], ...]

    def __init__(self, items: tuple[tuple[str, JsonValue], ...]) -> None:
        object.__setattr__(self, "_items_data", items)

    def __setattr__(self, name: str, value: object) -> None:
        raise TypeError("bounded JSON objects are immutable")

    def __delattr__(self, name: str) -> None:
        raise TypeError("bounded JSON objects are immutable")

    def __getitem__(self, key: str) -> JsonValue:
        for item_key, item in self._items_data:
            if item_key == key:
                return item
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items_data)

    def __len__(self) -> int:
        return len(self._items_data)

    def _items(self) -> tuple[tuple[str, JsonValue], ...]:
        return self._items_data


def _is_object(value: object) -> bool:
    return type(value) is dict or type(value) is _FrozenObject


def _is_array(value: object) -> bool:
    return type(value) is list or type(value) is tuple


def _string(value: object, name: str) -> str:
    if type(value) is not str:
        raise BoundedJsonError(f"{name} must be a string")
    try:
        size = len(value.encode("utf-8", errors="strict"))
    except UnicodeError as error:
        raise BoundedJsonError(f"{name} must be strict UTF-8") from error
    if size > MAX_BOUNDARY_STRING_BYTES:
        raise BoundedJsonError(f"{name} exceeds the UTF-8 byte bound")
    return value


def _validate(value: object, *, max_bytes: int | None) -> JsonValue:
    """Validate without recursion and return a deeply frozen JSON value."""

    # Each frame contains (value, depth, parent, slot, exiting).  ``active``
    # catches cycles while still allowing the same immutable value at two
    # branches.
    root: object = value
    nodes = 0
    active: set[int] = set()
    missing = object()
    normalized_root: object = missing
    frames: list[tuple[object, int, object | None, object | None, bool]] = [
        (root, 0, None, None, False)
    ]

    while frames:
        current, depth, parent, slot, exiting = frames.pop()
        if exiting:
            active.discard(id(current))
            continue
        nodes += 1
        if nodes > MAX_BOUNDARY_NODES:
            raise BoundedJsonError("JSON node bound exceeded")
        if depth > MAX_BOUNDARY_DEPTH:
            raise BoundedJsonError("JSON depth bound exceeded")

        if current is None or type(current) is bool:
            result: object = current
        elif type(current) is int:
            if not MIN_IDENTITY_INTEGER <= current <= MAX_IDENTITY_INTEGER:
                raise BoundedJsonError("JSON integer is outside signed 64-bit range")
            result = current
        elif type(current) is str:
            result = _string(current, "JSON string")
        elif type(current) is float:
            raise BoundedJsonError("floating-point JSON values are not supported")
        elif _is_object(current):
            current_id = id(current)
            if current_id in active:
                raise BoundedJsonError("cyclic JSON values are not supported")
            active.add(current_id)
            if type(current) is _FrozenObject:
                items = cast(tuple[tuple[object, object], ...], current._items())
            else:
                items = tuple(cast(dict[object, object], current).items())
            if len(items) > MAX_BOUNDARY_ITEMS:
                raise BoundedJsonError("JSON object item bound exceeded")
            child: dict[str, object] = {}
            frames.append((current, depth, parent, slot, True))
            for key, item in reversed(items):
                key_text = _string(key, "JSON object key")
                frames.append((item, depth + 1, child, key_text, False))
            result = child
        elif _is_array(current):
            current_id = id(current)
            if current_id in active:
                raise BoundedJsonError("cyclic JSON values are not supported")
            active.add(current_id)
            array_items: tuple[object, ...]
            if type(current) is tuple:
                array_items = cast(tuple[object, ...], current)
            else:
                array_items = tuple(cast(list[object], current))
            if len(array_items) > MAX_BOUNDARY_ITEMS:
                raise BoundedJsonError("JSON array item bound exceeded")
            child_array: list[object] = [None] * len(array_items)
            frames.append((current, depth, parent, slot, True))
            for index in range(len(array_items) - 1, -1, -1):
                frames.append(
                    (array_items[index], depth + 1, child_array, index, False)
                )
            result = child_array
        else:
            raise BoundedJsonError("unsupported JSON value")

        if parent is None:
            normalized_root = result
        elif isinstance(parent, (dict, list)) and (
            isinstance(slot, str) or type(slot) is int
        ):
            if (isinstance(parent, dict) and isinstance(slot, str)) or (
                isinstance(parent, list) and type(slot) is int
            ):
                if isinstance(parent, dict):
                    parent[cast(str, slot)] = result
                else:
                    parent[cast(int, slot)] = result
            else:  # pragma: no cover - internal frame invariant
                raise BoundedJsonError("invalid JSON traversal state")
        else:  # pragma: no cover - internal frame invariant
            raise BoundedJsonError("invalid JSON traversal state")

    if normalized_root is missing:
        raise BoundedJsonError("JSON root is missing")

    def freeze(value_to_freeze: object) -> JsonValue:
        # The validated tree is bounded to eight levels, so this final small
        # conversion cannot receive hostile depth.  It also never invokes
        # user-defined methods because the tree contains only built-ins.
        if isinstance(value_to_freeze, dict):
            return _FrozenObject(
                tuple((key, freeze(item)) for key, item in value_to_freeze.items())
            )
        if isinstance(value_to_freeze, list):
            return tuple(freeze(item) for item in value_to_freeze)
        return cast(JsonValue, value_to_freeze)

    frozen = freeze(normalized_root)
    if max_bytes is not None:
        encoded = _encode_frozen(frozen)
        if len(encoded) > max_bytes:
            raise BoundedJsonError("canonical JSON byte bound exceeded")
    return frozen


def _thaw(value: JsonValue) -> object:
    if type(value) is _FrozenObject:
        return {key: _thaw(item) for key, item in value._items()}
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _encode_frozen(value: JsonValue) -> bytes:
    try:
        return json.dumps(
            _thaw(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8", errors="strict")
    except (TypeError, UnicodeError, ValueError, RecursionError) as error:
        raise BoundedJsonError("JSON cannot be canonically encoded") from error


def validate_json(value: object, *, max_bytes: int | None = None) -> JsonValue:
    """Validate a construction-boundary value and return frozen JSON."""

    return _validate(value, max_bytes=max_bytes)


def freeze_json(value: object, *, max_bytes: int | None = None) -> JsonValue:
    """Compatibility spelling for the bounded validator."""

    return validate_json(value, max_bytes=max_bytes)


def canonical_json_bytes(value: object, *, max_bytes: int | None = None) -> bytes:
    """Return strict, sorted, whitespace-free UTF-8 JSON after validation."""

    frozen = validate_json(value, max_bytes=max_bytes)
    encoded = _encode_frozen(frozen)
    if max_bytes is not None and len(encoded) > max_bytes:
        raise BoundedJsonError("canonical JSON byte bound exceeded")
    return encoded


def decode_json_bytes(data: bytes, *, max_bytes: int) -> JsonValue:
    """Decode one canonical JSON value with duplicate-key rejection."""

    if type(data) is not bytes or len(data) > max_bytes:
        raise BoundedJsonError("JSON input exceeds its byte bound")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in items:
            if key in result:
                raise BoundedJsonError("duplicate JSON object key")
            result[key] = item
        return result

    try:
        decoded = json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError, BoundedJsonError) as error:
        raise BoundedJsonError("invalid bounded JSON bytes") from error
    frozen = validate_json(decoded, max_bytes=max_bytes)
    if canonical_json_bytes(frozen, max_bytes=max_bytes) != data:
        raise BoundedJsonError("JSON bytes are not canonical")
    return frozen


def validate_json_object(value: object, *, max_bytes: int | None = None) -> JsonObject:
    frozen = validate_json(value, max_bytes=max_bytes)
    if not isinstance(frozen, Mapping):
        raise BoundedJsonError("JSON root must be an object")
    return frozen


__all__ = [
    "MAX_BOUNDARY_DEPTH",
    "MAX_BOUNDARY_ITEMS",
    "MAX_BOUNDARY_NODES",
    "MAX_BOUNDARY_STRING_BYTES",
    "MAX_CITATION_BYTES",
    "MAX_IDENTITY_INTEGER",
    "MAX_METADATA_BYTES",
    "MIN_IDENTITY_INTEGER",
    "BoundedJsonError",
    "canonical_json_bytes",
    "decode_json_bytes",
    "freeze_json",
    "validate_json",
    "validate_json_object",
]
