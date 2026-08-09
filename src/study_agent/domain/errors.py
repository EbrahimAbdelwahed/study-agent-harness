from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from ._validation import JsonObject, freeze_object, require_text


class ErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SOURCE_INTEGRITY_ERROR = "source_integrity_error"
    RETRIEVAL_ERROR = "retrieval_error"
    MODEL_UNAVAILABLE = "model_unavailable"
    MODEL_PROTOCOL_ERROR = "model_protocol_error"
    VALIDATION_ERROR = "validation_error"
    PERSISTENCE_ERROR = "persistence_error"
    CANCELLED = "cancelled"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass(frozen=True, slots=True)
class StudyError:
    code: ErrorCode
    message: str
    retryable: bool = False
    details: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.message, "message")
        object.__setattr__(self, "details", freeze_object(self.details))


MAX_ERROR_DEPTH = 8
MAX_ERROR_NODES = 256
MAX_ERROR_ITEMS = 64
MAX_ERROR_STRING_BYTES = 1024
MAX_ERROR_DETAILS_BYTES = 16 * 1024
MAX_ERROR_BYTES = 20 * 1024

_REDACTED = "[REDACTED]"
_UNSUPPORTED = "[UNSUPPORTED]"
_CYCLE = "[CYCLE]"
_DEPTH_LIMIT = "[DEPTH_LIMIT]"
_NODE_LIMIT = "[NODE_LIMIT]"
_ITEM_LIMIT = "[ITEM_LIMIT]"
_STRING_LIMIT = "[STRING_LIMIT]"
_NON_FINITE = "[NON_FINITE]"
_NON_STRING_KEY = "[NON_STRING_KEY]"
_DETAILS_LIMIT = "[DETAILS_LIMIT]"

_SECRET_FIELD = re.compile(
    r"(?:api[_-]?key|authorization|cookie|credential|password|secret|token|prompt|"
    r"chain[-_ ]of[-_ ]thought|traceback|stack[_ -]?trace|exception|provider)",
    re.IGNORECASE,
)


def _has_sensitive_marker(value: str) -> bool:
    return _SECRET_FIELD.search(value) is not None


def _bounded_text(value: str) -> str:
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return _UNSUPPORTED
    if len(encoded) > MAX_ERROR_STRING_BYTES:
        return _STRING_LIMIT
    if _has_sensitive_marker(value):
        return _REDACTED
    return value


def _safe_message(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "operation failed safely"
    bounded = _bounded_text(value.strip())
    if bounded in {_REDACTED, _STRING_LIMIT, _UNSUPPORTED}:
        return "operation failed safely"
    return bounded


class _SanitizeState:
    __slots__ = ("active", "nodes")

    def __init__(self) -> None:
        self.nodes = 0
        self.active: set[int] = set()


def _safe_value(value: object, *, key: str | None = None) -> object:
    """Return bounded JSON-compatible data without invoking arbitrary repr/str."""

    state = _SanitizeState()

    def visit(item: object, depth: int, item_key: str | None = None) -> object:
        if item_key is not None and _has_sensitive_marker(item_key):
            return _REDACTED
        if depth > MAX_ERROR_DEPTH:
            return _DEPTH_LIMIT
        state.nodes += 1
        if state.nodes > MAX_ERROR_NODES:
            return _NODE_LIMIT
        if isinstance(item, str):
            return _bounded_text(item)
        if item is None or isinstance(item, (bool, int)):
            return item
        if isinstance(item, float):
            return item if math.isfinite(item) else _NON_FINITE
        if not isinstance(item, (Mapping, list, tuple)):
            return _UNSUPPORTED

        identity = id(item)
        if identity in state.active:
            return _CYCLE
        state.active.add(identity)
        try:
            if isinstance(item, Mapping):
                result: dict[str, object] = {}
                count = 0
                try:
                    for raw_key, raw_value in item.items():
                        if count >= MAX_ERROR_ITEMS:
                            return {"_": _ITEM_LIMIT}
                        count += 1
                        if not isinstance(raw_key, str):
                            result[_NON_STRING_KEY] = _NON_STRING_KEY
                            continue
                        result[raw_key] = visit(raw_value, depth + 1, raw_key)
                except Exception:
                    return _UNSUPPORTED
                return result
            if len(item) > MAX_ERROR_ITEMS:
                return [_ITEM_LIMIT]
            return [visit(child, depth + 1) for child in item]
        finally:
            state.active.remove(identity)

    return visit(value, 0, key)


def _freeze_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_safe(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_safe(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_safe(item) for item in value)
    return value


def _bounded_details(value: object) -> object:
    safe = _safe_value(value)
    try:
        encoded = json.dumps(
            safe, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        return {"_": _UNSUPPORTED}
    return safe if len(encoded) <= MAX_ERROR_DETAILS_BYTES else {"_": _DETAILS_LIMIT}


class HarnessError(RuntimeError):
    """Facade-visible base for the seven safe public failure categories."""

    code = "internal"
    default_retryable = False

    def __init__(
        self,
        message: str = "operation failed safely",
        *,
        retryable: bool | None = None,
        correlation_id: object | None = None,
        details: Mapping[str, object] | None = None,
    ) -> None:
        if retryable is not None and type(retryable) is not bool:
            raise TypeError("retryable must be a boolean")
        self.message = _safe_message(message)
        self.retryable = self.default_retryable if retryable is None else retryable
        if correlation_id is None:
            self.correlation_id = None
        elif isinstance(correlation_id, str) and correlation_id.strip():
            candidate = _bounded_text(correlation_id.strip())
            self.correlation_id = candidate if candidate not in {_REDACTED, _STRING_LIMIT} else None
        else:
            self.correlation_id = None
        safe_details = _bounded_details({} if details is None else details)
        self.details = _freeze_safe(safe_details)
        super().__init__(self.message)

    def to_json(self) -> dict[str, object]:
        """Return a stable, bounded, strict-JSON-safe failure document."""

        payload: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "correlation_id": self.correlation_id,
            "details": _safe_value(self.details),
        }
        try:
            encoded = json.dumps(
                payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeEncodeError):
            return {
                "code": self.code,
                "message": "operation failed safely",
                "retryable": bool(self.retryable),
                "correlation_id": None,
                "details": {"_": _UNSUPPORTED},
            }
        if len(encoded) <= MAX_ERROR_BYTES:
            return payload
        return {
            "code": self.code,
            "message": "operation failed safely",
            "retryable": bool(self.retryable),
            "correlation_id": None,
            "details": {"_": _DETAILS_LIMIT},
        }

    def as_dict(self) -> dict[str, object]:
        return self.to_json()

    def serialize(self) -> bytes:
        return json.dumps(
            self.to_json(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def __str__(self) -> str:
        return self.message


class ValidationFailure(HarnessError):
    code = "validation"


class StaleFailure(HarnessError):
    code = "stale"
    default_retryable = True


class UnauthorizedFailure(HarnessError):
    code = "unauthorized"


class ConflictFailure(HarnessError):
    code = "conflict"


class NotFoundFailure(HarnessError):
    code = "not_found"


class UnavailableDependencyFailure(HarnessError):
    code = "unavailable_dependency"
    default_retryable = True


class InternalFailure(HarnessError):
    code = "internal"


__all__ = [
    "ConflictFailure",
    "ErrorCode",
    "HarnessError",
    "InternalFailure",
    "NotFoundFailure",
    "StaleFailure",
    "StudyError",
    "UnauthorizedFailure",
    "UnavailableDependencyFailure",
    "ValidationFailure",
]
