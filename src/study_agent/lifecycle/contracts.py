"""Pure, bounded desired-intent contracts for lifecycle manifest version 1."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
from typing import Any, cast

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.ports.source_input import MAX_TOTAL_SOURCES
from study_agent.repository_config import (
    LocalConfigError,
    LocalRepositoryConfig,
    ModelAdapterConfig,
)
from study_agent.state import canonical_json_bytes

MANIFEST_SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_COURSES = 128
MAX_SOURCES_PER_COURSE = 1024
MAX_SETTINGS_DEPTH = 16
MAX_SETTINGS_NODES = 1024
MAX_CONTAINER_MEMBERS = 256
MAX_SETTINGS_KEY_LENGTH = 128
MAX_SETTINGS_STRING_LENGTH = 4096

_FINGERPRINT_DOMAIN = b"study-agent-lifecycle-manifest-v1\0"
_ROOT_FIELDS = frozenset({"schema_version", "repository", "courses"})
_REPOSITORY_FIELDS = frozenset({"path", "model"})
_MODEL_FIELDS = frozenset({"adapter_id", "credential_env", "settings"})
_COURSE_FIELDS = frozenset(
    {
        "course_id",
        "title",
        "language",
        "exam_date",
        "learning_goals",
        "assessment_styles",
        "sources",
    }
)
_SOURCE_FIELDS = frozenset(
    {"source_id", "path", "title", "trust_level", "source_role"}
)
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")
_WINDOWS_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)
_BEHAVIOR_FIELD_PARTS = frozenset(
    {
        "authority",
        "actor",
        "capability",
        "capabilities",
        "command",
        "commands",
        "correlation",
        "delete",
        "deletion",
        "exec",
        "executable",
        "glob",
        "hook",
        "hooks",
        "idempotency",
        "identity",
        "include",
        "instruction",
        "instructions",
        "import",
        "imports",
        "playbook",
        "playbooks",
        "plugin",
        "plugins",
        "prompt",
        "prompts",
        "principal",
        "remove",
        "removal",
        "script",
        "scripts",
        "skill",
        "skills",
        "tool",
        "tools",
        "function",
        "functions",
        "system",
    }
)


class ManifestValidationError(ValueError):
    """Manifest input is malformed, unsafe, or outside the public v1 bounds."""


@dataclass(frozen=True, slots=True)
class DesiredSource:
    source_id: str
    path: str
    title: str | None
    trust_level: int
    source_role: str

    def __post_init__(self) -> None:
        _text(self.source_id, "source.source_id", 256)
        _relative_path(self.path, "source.path")
        if not self.path.endswith((".txt", ".md")):
            raise ManifestValidationError("source.path must identify a .txt or .md file")
        if self.title is not None:
            _text(self.title, "source.title", 1024)
        if type(self.trust_level) is not int or not 0 <= self.trust_level <= 100:
            raise ManifestValidationError("source.trust_level must be an integer from 0 to 100")
        _text(self.source_role, "source.source_role", 256)

    def to_json(self) -> JsonObject:
        return {
            "path": self.path,
            "source_id": self.source_id,
            "source_role": self.source_role,
            "title": self.title,
            "trust_level": self.trust_level,
        }


@dataclass(frozen=True, slots=True)
class DesiredCourse:
    course_id: str
    title: str
    language: str
    exam_date: str | None
    learning_goals: tuple[str, ...]
    assessment_styles: tuple[str, ...]
    sources: tuple[DesiredSource, ...]

    def __post_init__(self) -> None:
        _text(self.course_id, "course.course_id", 256)
        _text(self.title, "course.title", 1024)
        _text(self.language, "course.language", 256)
        if self.exam_date is not None:
            _exam_date(self.exam_date)
        _text_tuple(self.learning_goals, "course.learning_goals", 1, 64, 2048)
        _text_tuple(self.assessment_styles, "course.assessment_styles", 0, 32, 512)
        if not isinstance(self.sources, tuple) or len(self.sources) > MAX_SOURCES_PER_COURSE:
            raise ManifestValidationError("course.sources must be an array with at most 1024 items")
        if any(not isinstance(item, DesiredSource) for item in self.sources):
            raise ManifestValidationError("course.sources contains an invalid source")
        _unique((item.source_id for item in self.sources), "source IDs within a course")
        ordered = tuple(sorted(self.sources, key=lambda item: item.source_id))
        object.__setattr__(self, "sources", ordered)

    def to_json(self) -> JsonObject:
        return {
            "assessment_styles": self.assessment_styles,
            "course_id": self.course_id,
            "exam_date": self.exam_date,
            "language": self.language,
            "learning_goals": self.learning_goals,
            "sources": tuple(item.to_json() for item in self.sources),
            "title": self.title,
        }


@dataclass(frozen=True, slots=True)
class DesiredRepository:
    path: str
    model: ModelAdapterConfig | None

    def __post_init__(self) -> None:
        _relative_path(self.path, "repository.path")
        if self.model is not None and not isinstance(self.model, ModelAdapterConfig):
            raise ManifestValidationError("repository.model must be a model config or null")
        try:
            if self.model is not None:
                _validate_settings_iteratively(self.model.settings)
            LocalRepositoryConfig(self.model).to_bytes()
        except LocalConfigError as error:
            raise ManifestValidationError("repository.model configuration is invalid") from error

    def to_json(self) -> JsonObject:
        model: JsonValue
        if self.model is None:
            model = None
        else:
            model = {
                "adapter_id": self.model.adapter_id,
                "credential_env": self.model.credential_env,
                "settings": self.model.settings,
            }
        return {"model": model, "path": self.path}


@dataclass(frozen=True, slots=True)
class LifecycleManifestV1:
    repository: DesiredRepository
    courses: tuple[DesiredCourse, ...]
    schema_version: int = field(default=MANIFEST_SCHEMA_VERSION)

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise ManifestValidationError("schema_version must be exactly 1")
        if not isinstance(self.repository, DesiredRepository):
            raise ManifestValidationError("repository is invalid")
        if not isinstance(self.courses, tuple) or len(self.courses) > MAX_COURSES:
            raise ManifestValidationError("courses must be an array with at most 128 items")
        if any(not isinstance(item, DesiredCourse) for item in self.courses):
            raise ManifestValidationError("courses contains an invalid course")
        _unique((item.course_id for item in self.courses), "course IDs")
        if sum(len(item.sources) for item in self.courses) > MAX_TOTAL_SOURCES:
            raise ManifestValidationError("manifest cannot contain more than 4096 sources")
        ordered = tuple(sorted(self.courses, key=lambda item: item.course_id))
        object.__setattr__(self, "courses", ordered)

    @classmethod
    def from_bytes(cls, payload: bytes) -> LifecycleManifestV1:
        if type(payload) is not bytes or not payload or len(payload) > MAX_MANIFEST_BYTES:
            raise ManifestValidationError("manifest must be non-empty UTF-8 JSON of at most 1 MiB")
        try:
            raw: Any = json.loads(
                payload.decode("utf-8", errors="strict"),
                object_pairs_hook=_object_without_duplicates,
                parse_constant=_invalid_json_constant,
            )
        except (OverflowError, RecursionError, UnicodeError, ValueError) as error:
            raise ManifestValidationError("manifest must be valid bounded UTF-8 JSON") from error
        try:
            return _decode_manifest(raw)
        except ManifestValidationError:
            raise
        except (LocalConfigError, RecursionError, TypeError, ValueError) as error:
            raise ManifestValidationError("manifest structure is invalid") from error

    def to_json(self) -> JsonObject:
        return {
            "courses": tuple(item.to_json() for item in self.courses),
            "repository": self.repository.to_json(),
            "schema_version": self.schema_version,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @property
    def fingerprint(self) -> str:
        return sha256(_FINGERPRINT_DOMAIN + self.canonical_bytes()).hexdigest()

    @property
    def source_count(self) -> int:
        return sum(len(item.sources) for item in self.courses)


def manifest_schema() -> JsonObject:
    """Return the closed, repository-free JSON schema for manifest version 1."""
    model_schema: JsonObject = {
        "additionalProperties": False,
        "properties": {
            "adapter_id": {"maxLength": 256, "minLength": 1, "type": "string"},
            "credential_env": {
                "anyOf": (
                    {"pattern": "^[A-Z_][A-Z0-9_]*$", "type": "string"},
                    {"type": "null"},
                )
            },
            "settings": {"maxProperties": MAX_CONTAINER_MEMBERS, "type": "object"},
        },
        "required": ("adapter_id", "credential_env", "settings"),
        "type": "object",
    }
    source_schema: JsonObject = {
        "additionalProperties": False,
        "properties": {
            "path": {"maxLength": 256, "minLength": 1, "type": "string"},
            "source_id": {"maxLength": 256, "minLength": 1, "type": "string"},
            "source_role": {"maxLength": 256, "minLength": 1, "type": "string"},
            "title": {
                "anyOf": (
                    {"maxLength": 1024, "minLength": 1, "type": "string"},
                    {"type": "null"},
                )
            },
            "trust_level": {"maximum": 100, "minimum": 0, "type": "integer"},
        },
        "required": ("source_id", "path", "title", "trust_level", "source_role"),
        "type": "object",
    }
    course_schema: JsonObject = {
        "additionalProperties": False,
        "properties": {
            "assessment_styles": {
                "items": {"maxLength": 512, "minLength": 1, "type": "string"},
                "maxItems": 32,
                "type": "array",
            },
            "course_id": {"maxLength": 256, "minLength": 1, "type": "string"},
            "exam_date": {
                "anyOf": (
                    {"format": "date", "type": "string"},
                    {"type": "null"},
                )
            },
            "language": {"maxLength": 256, "minLength": 1, "type": "string"},
            "learning_goals": {
                "items": {"maxLength": 2048, "minLength": 1, "type": "string"},
                "maxItems": 64,
                "minItems": 1,
                "type": "array",
            },
            "sources": {
                "items": source_schema,
                "maxItems": MAX_SOURCES_PER_COURSE,
                "type": "array",
            },
            "title": {"maxLength": 1024, "minLength": 1, "type": "string"},
        },
        "required": tuple(sorted(_COURSE_FIELDS)),
        "type": "object",
    }
    return {
        "$id": "https://study-agent.dev/schemas/lifecycle-manifest-v1.json",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "additionalProperties": False,
        "properties": {
            "courses": {"items": course_schema, "maxItems": MAX_COURSES, "type": "array"},
            "repository": {
                "additionalProperties": False,
                "properties": {
                    "model": {"anyOf": (model_schema, {"type": "null"})},
                    "path": {"maxLength": 256, "minLength": 1, "type": "string"},
                },
                "required": ("path", "model"),
                "type": "object",
            },
            "schema_version": {"const": MANIFEST_SCHEMA_VERSION, "type": "integer"},
        },
        "required": ("schema_version", "repository", "courses"),
        "title": "Study Agent lifecycle manifest v1",
        "type": "object",
    }


def _decode_manifest(raw: object) -> LifecycleManifestV1:
    root = _closed_object(raw, _ROOT_FIELDS, "manifest")
    schema_version = root["schema_version"]
    if type(schema_version) is not int:
        raise ManifestValidationError("schema_version must be an integer")
    repository = _decode_repository(root["repository"])
    courses_raw = _array(root["courses"], "courses", MAX_COURSES)
    courses = tuple(_decode_course(item) for item in courses_raw)
    return LifecycleManifestV1(repository, courses, schema_version)


def _decode_repository(raw: object) -> DesiredRepository:
    value = _closed_object(raw, _REPOSITORY_FIELDS, "repository")
    model_raw = value["model"]
    model = None if model_raw is None else _decode_model(model_raw)
    return DesiredRepository(_required_string(value["path"], "repository.path"), model)


def _decode_model(raw: object) -> ModelAdapterConfig:
    value = _closed_object(raw, _MODEL_FIELDS, "repository.model")
    adapter_id = _required_string(value["adapter_id"], "model.adapter_id")
    _text(adapter_id, "model.adapter_id", 256)
    credential_raw = value["credential_env"]
    if credential_raw is not None and not isinstance(credential_raw, str):
        raise ManifestValidationError("model.credential_env must be text or null")
    settings = value["settings"]
    if not isinstance(settings, dict):
        raise ManifestValidationError("model.settings must be an object")
    _validate_settings_iteratively(settings)
    try:
        model = ModelAdapterConfig(
            adapter_id,
            cast(JsonObject, settings),
            credential_raw,
        )
        LocalRepositoryConfig(model).to_bytes()
    except LocalConfigError as error:
        raise ManifestValidationError("repository.model configuration is invalid") from error
    return model


def _decode_course(raw: object) -> DesiredCourse:
    value = _closed_object(raw, _COURSE_FIELDS, "course")
    goals = _string_array(value["learning_goals"], "course.learning_goals", 1, 64)
    styles = _string_array(value["assessment_styles"], "course.assessment_styles", 0, 32)
    sources_raw = _array(value["sources"], "course.sources", MAX_SOURCES_PER_COURSE)
    exam_raw = value["exam_date"]
    if exam_raw is not None and not isinstance(exam_raw, str):
        raise ManifestValidationError("course.exam_date must be a date string or null")
    return DesiredCourse(
        _required_string(value["course_id"], "course.course_id"),
        _required_string(value["title"], "course.title"),
        _required_string(value["language"], "course.language"),
        exam_raw,
        goals,
        styles,
        tuple(_decode_source(item) for item in sources_raw),
    )


def _decode_source(raw: object) -> DesiredSource:
    value = _closed_object(raw, _SOURCE_FIELDS, "source")
    title = value["title"]
    if title is not None and not isinstance(title, str):
        raise ManifestValidationError("source.title must be text or null")
    trust = value["trust_level"]
    if type(trust) is not int:
        raise ManifestValidationError("source.trust_level must be an integer")
    return DesiredSource(
        _required_string(value["source_id"], "source.source_id"),
        _required_string(value["path"], "source.path"),
        title,
        trust,
        _required_string(value["source_role"], "source.source_role"),
    )


def _validate_settings_iteratively(settings: Mapping[str, JsonValue]) -> None:
    nodes = 0
    stack: list[tuple[object, int]] = [(settings, 1)]
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_SETTINGS_NODES:
            raise ManifestValidationError("model.settings exceeds the 1024-node bound")
        if depth > MAX_SETTINGS_DEPTH:
            raise ManifestValidationError("model.settings exceeds the nesting-depth bound")
        if isinstance(value, Mapping):
            if len(value) > MAX_CONTAINER_MEMBERS:
                raise ManifestValidationError("model.settings object is too wide")
            for key, child in value.items():
                _text(key, "model.settings key", MAX_SETTINGS_KEY_LENGTH)
                camel_split = _CAMEL_BOUNDARY.sub("_", key).lower()
                normalized = _NON_ALPHANUMERIC.sub("_", camel_split).strip("_")
                parts = frozenset(part for part in normalized.split("_") if part)
                if normalized in _BEHAVIOR_FIELD_PARTS or parts & _BEHAVIOR_FIELD_PARTS:
                    raise ManifestValidationError(
                        "model.settings cannot select behavior, identity, or authority"
                    )
                stack.append((child, depth + 1))
        elif isinstance(value, (list, tuple)):
            if len(value) > MAX_CONTAINER_MEMBERS:
                raise ManifestValidationError("model.settings array is too wide")
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            _text(value, "model.settings string", MAX_SETTINGS_STRING_LENGTH)
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise ManifestValidationError("model.settings numbers must be finite")
        elif not isinstance(value, (int, bool, type(None))):
            raise ManifestValidationError("model.settings must contain strict JSON values")


def _closed_object(raw: object, fields: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != fields:
        raise ManifestValidationError(f"{name} fields are incompatible")
    return cast(dict[str, Any], raw)


def _array(raw: object, name: str, maximum: int) -> list[Any]:
    if not isinstance(raw, list) or len(raw) > maximum:
        raise ManifestValidationError(f"{name} must be a bounded array")
    return raw


def _string_array(
    raw: object, name: str, minimum: int, maximum: int
) -> tuple[str, ...]:
    values = _array(raw, name, maximum)
    if len(values) < minimum or any(not isinstance(item, str) for item in values):
        raise ManifestValidationError(f"{name} must contain the required text items")
    return tuple(cast(list[str], values))


def _required_string(raw: object, name: str) -> str:
    if not isinstance(raw, str):
        raise ManifestValidationError(f"{name} must be text")
    return raw


def _text_tuple(
    values: tuple[str, ...], name: str, minimum: int, maximum: int, length: int
) -> None:
    if not isinstance(values, tuple) or not minimum <= len(values) <= maximum:
        raise ManifestValidationError(f"{name} has an invalid item count")
    for item in values:
        _text(item, name, length)


def _text(value: object, name: str, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        raise ManifestValidationError(f"{name} must be non-empty trimmed bounded text")


def _relative_path(value: object, name: str) -> None:
    _text(value, name, 256)
    assert isinstance(value, str)
    if (
        "\x00" in value
        or ":" in value
        or value.startswith("/")
        or value.startswith("\\")
        or "\\" in value
        or _WINDOWS_DRIVE.match(value) is not None
    ):
        raise ManifestValidationError(f"{name} must be a portable relative path")
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ManifestValidationError(f"{name} cannot be dot, empty, or traversing")
    if any(
        part.endswith((" ", "."))
        or part.split(".", 1)[0].upper() in _WINDOWS_DEVICE_NAMES
        for part in parts
    ):
        raise ManifestValidationError(f"{name} must use portable path components")


def _exam_date(value: object) -> None:
    _text(value, "course.exam_date", 10)
    assert isinstance(value, str)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ManifestValidationError("course.exam_date must use YYYY-MM-DD") from error
    if parsed.isoformat() != value:
        raise ManifestValidationError("course.exam_date must use YYYY-MM-DD")


def _unique(values: Iterable[str], name: str) -> None:
    materialized = tuple(values)
    if len(set(materialized)) != len(materialized):
        raise ManifestValidationError(f"{name} must be unique")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestValidationError("manifest cannot contain duplicate object keys")
        result[key] = value
    return result


def _invalid_json_constant(value: str) -> None:
    raise ManifestValidationError(f"invalid JSON number: {value}")


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "MAX_CONTAINER_MEMBERS",
    "MAX_COURSES",
    "MAX_MANIFEST_BYTES",
    "MAX_SETTINGS_DEPTH",
    "MAX_SETTINGS_KEY_LENGTH",
    "MAX_SETTINGS_NODES",
    "MAX_SETTINGS_STRING_LENGTH",
    "MAX_SOURCES_PER_COURSE",
    "MAX_TOTAL_SOURCES",
    "DesiredCourse",
    "DesiredRepository",
    "DesiredSource",
    "LifecycleManifestV1",
    "ManifestValidationError",
    "manifest_schema",
]
