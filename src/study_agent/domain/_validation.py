from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from types import MappingProxyType

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | tuple[JsonValue, ...] | Mapping[str, JsonValue]
type JsonObject = Mapping[str, JsonValue]


def require_text(value: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty and have no surrounding whitespace")


def require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def freeze_json(value: JsonValue) -> JsonValue:
    if isinstance(value, Mapping):
        frozen = {key: freeze_json(item) for key, item in value.items()}
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(freeze_json(item) for item in value)
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        raise ValueError("JSON numbers must be finite")
    if not isinstance(value, (str, int, float, bool, type(None))):
        raise ValueError(f"unsupported JSON value: {type(value).__name__}")
    return value


def freeze_object(value: Mapping[str, JsonValue]) -> JsonObject:
    frozen = freeze_json(value)
    if not isinstance(frozen, Mapping):  # pragma: no cover - narrowed by the input type
        raise TypeError("expected an object")
    return frozen
