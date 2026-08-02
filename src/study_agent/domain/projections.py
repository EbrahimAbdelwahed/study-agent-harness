"""Strict provider-neutral contracts for discardable index projections."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, cast

from study_agent.state.serialization import canonical_json_bytes, canonical_json_object

from ._validation import JsonObject, JsonValue, require_text
from .identifiers import UnitId
from .units import RetrievableUnit

MAX_HANDLE_LENGTH = 512
MAX_SUMMARY_LENGTH = 2_000
MAX_TERM_LENGTH = 128
MAX_TERM_COUNT = 32
MAX_CONTEXT_LENGTH = 1_024
MAX_IDENTITY_LENGTH = 128
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]*$")


def _digest(value: str, name: str) -> None:
    require_text(value, name)
    if _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _text(value: str, name: str, limit: int, *, multiline: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    if not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be trimmed non-empty text")
    if len(value) > limit:
        raise ValueError(f"{name} must be at most {limit} characters")
    if "\x00" in value or (not multiline and ("\r" in value or "\n" in value)):
        raise ValueError(f"{name} contains forbidden control characters")
    return value


def _identity(value: str, name: str, *, version: bool = False) -> str:
    value = _text(value, name, MAX_IDENTITY_LENGTH)
    pattern = _VERSION if version else _NAME
    if pattern.fullmatch(value) is None:
        raise ValueError(f"{name} is not a portable identity")
    return value


def _model(value: str, name: str = "model_id") -> str:
    """Model identity is opaque data, not a provider-specific selector."""
    return _text(value, name, MAX_IDENTITY_LENGTH)


def _terms(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    values = tuple(values)
    if len(values) > MAX_TERM_COUNT or len(set(values)) != len(values):
        raise ValueError(f"{name} must contain at most {MAX_TERM_COUNT} unique values")
    return tuple(_text(item, f"{name} item", MAX_TERM_LENGTH) for item in values)


def _object(value: JsonValue | None, name: str, keys: frozenset[str]) -> JsonObject:
    if not hasattr(value, "keys"):
        raise ValueError(f"{name} must be an object")
    payload = cast(JsonObject, value)
    if frozenset(payload) != keys:
        raise ValueError(f"{name} fields mismatch")
    return payload


def _required(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    return value


def _optional(value: JsonValue | None, name: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{name} must be text or null")
    return value


def _array(value: JsonValue | None, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be an array of strings")
    return tuple(item for item in value if isinstance(item, str))


@dataclass(frozen=True, slots=True)
class ProjectionId:
    """Identity binding unit, exact input, producer, model, and output hash."""

    unit_id: UnitId
    input_fingerprint: str
    projector_name: str
    projector_version: str
    model_id: str | None
    output_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.unit_id, UnitId):
            raise TypeError("unit_id must be UnitId")
        _digest(self.input_fingerprint, "input_fingerprint")
        _identity(self.projector_name, "projector_name")
        _identity(self.projector_version, "projector_version", version=True)
        if self.model_id is not None:
            _model(self.model_id)
        _digest(self.output_sha256, "output_sha256")

    def to_json(self) -> JsonObject:
        return {
            "input_fingerprint": self.input_fingerprint,
            "model_id": self.model_id,
            "output_sha256": self.output_sha256,
            "projector_name": self.projector_name,
            "projector_version": self.projector_version,
            "unit_id": str(self.unit_id),
        }

    @property
    def value(self) -> str:
        return (
            "projection:sha256:"
            + sha256(
                b"study-agent/index-projection-id/v1\0" + canonical_json_bytes(self.to_json())
            ).hexdigest()
        )

    def __str__(self) -> str:
        return self.value

    @property
    def projection_input_fingerprint(self) -> str:
        return self.input_fingerprint

    @property
    def producer_name(self) -> str:
        return self.projector_name

    @property
    def producer_version(self) -> str:
        return self.projector_version

    @classmethod
    def from_json(cls, value: JsonObject) -> ProjectionId:
        p = _object(
            value,
            "projection_id",
            frozenset(
                {
                    "input_fingerprint",
                    "model_id",
                    "output_sha256",
                    "projector_name",
                    "projector_version",
                    "unit_id",
                }
            ),
        )
        return cls(
            UnitId(_required(p.get("unit_id"), "unit_id")),
            _required(p.get("input_fingerprint"), "input_fingerprint"),
            _required(p.get("projector_name"), "projector_name"),
            _required(p.get("projector_version"), "projector_version"),
            _optional(p.get("model_id"), "model_id"),
            _required(p.get("output_sha256"), "output_sha256"),
        )

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> ProjectionId:
        value = canonical_json_object(data)
        if canonical_json_bytes(value) != data:
            raise ValueError("projection id bytes are not canonical")
        return cls.from_json(value)


@dataclass(frozen=True, slots=True)
class IndexProjection:
    """Bounded derived search fields; never canonical evidence."""

    unit_id: UnitId
    input_fingerprint: str
    handle: str
    summary: str | None
    key_terms: tuple[str, ...]
    aliases: tuple[str, ...]
    covers: tuple[str, ...]
    structural_context: str
    projector_name: str
    projector_version: str
    model_id: str | None
    output_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.unit_id, UnitId):
            raise TypeError("unit_id must be UnitId")
        _digest(self.input_fingerprint, "input_fingerprint")
        _text(self.handle, "handle", MAX_HANDLE_LENGTH)
        if self.summary is not None:
            _text(self.summary, "summary", MAX_SUMMARY_LENGTH, multiline=True)
        object.__setattr__(self, "key_terms", _terms(self.key_terms, "key_terms"))
        object.__setattr__(self, "aliases", _terms(self.aliases, "aliases"))
        object.__setattr__(self, "covers", _terms(self.covers, "covers"))
        _text(self.structural_context, "structural_context", MAX_CONTEXT_LENGTH)
        _identity(self.projector_name, "projector_name")
        _identity(self.projector_version, "projector_version", version=True)
        if self.model_id is not None:
            _model(self.model_id)
        _digest(self.output_sha256, "output_sha256")
        expected = self.derive_output_sha256(
            handle=self.handle,
            summary=self.summary,
            key_terms=self.key_terms,
            aliases=self.aliases,
            covers=self.covers,
            structural_context=self.structural_context,
        )
        if self.output_sha256 != expected:
            raise ValueError("output_sha256 does not match projection content")

    @staticmethod
    def derive_output_sha256(
        *,
        handle: str,
        summary: str | None,
        key_terms: tuple[str, ...],
        aliases: tuple[str, ...],
        covers: tuple[str, ...],
        structural_context: str,
    ) -> str:
        payload: JsonObject = {
            "aliases": tuple(aliases),
            "covers": tuple(covers),
            "handle": handle,
            "key_terms": tuple(key_terms),
            "structural_context": structural_context,
            "summary": summary,
        }
        return sha256(
            b"study-agent/index-projection-output/v1\0" + canonical_json_bytes(payload)
        ).hexdigest()

    @property
    def projection_id(self) -> ProjectionId:
        return ProjectionId(
            self.unit_id,
            self.input_fingerprint,
            self.projector_name,
            self.projector_version,
            self.model_id,
            self.output_sha256,
        )

    @property
    def projection_input_fingerprint(self) -> str:
        return self.input_fingerprint

    @property
    def producer_name(self) -> str:
        return self.projector_name

    @property
    def producer_version(self) -> str:
        return self.projector_version

    @property
    def ref(self) -> ProjectionRef:
        return ProjectionRef(self.unit_id, self.projection_id)

    def to_json(self) -> JsonObject:
        return {
            "aliases": self.aliases,
            "covers": self.covers,
            "handle": self.handle,
            "input_fingerprint": self.input_fingerprint,
            "key_terms": self.key_terms,
            "model_id": self.model_id,
            "output_sha256": self.output_sha256,
            "projector_name": self.projector_name,
            "projector_version": self.projector_version,
            "structural_context": self.structural_context,
            "summary": self.summary,
            "unit_id": str(self.unit_id),
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @classmethod
    def from_json(cls, value: JsonObject) -> IndexProjection:
        keys = frozenset(
            {
                "aliases",
                "covers",
                "handle",
                "input_fingerprint",
                "key_terms",
                "model_id",
                "output_sha256",
                "projector_name",
                "projector_version",
                "structural_context",
                "summary",
                "unit_id",
            }
        )
        p = _object(value, "index_projection", keys)
        return cls(
            UnitId(_required(p.get("unit_id"), "unit_id")),
            _required(p.get("input_fingerprint"), "input_fingerprint"),
            _required(p.get("handle"), "handle"),
            _optional(p.get("summary"), "summary"),
            _array(p.get("key_terms"), "key_terms"),
            _array(p.get("aliases"), "aliases"),
            _array(p.get("covers"), "covers"),
            _required(p.get("structural_context"), "structural_context"),
            _required(p.get("projector_name"), "projector_name"),
            _required(p.get("projector_version"), "projector_version"),
            _optional(p.get("model_id"), "model_id"),
            _required(p.get("output_sha256"), "output_sha256"),
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> IndexProjection:
        value = canonical_json_object(data)
        if canonical_json_bytes(value) != data:
            raise ValueError("index projection bytes are not canonical")
        return cls.from_json(value)


@dataclass(frozen=True, slots=True)
class ProjectionRef:
    """A non-citable pointer to a projection row."""

    unit_id: UnitId
    projection_id: ProjectionId

    def __post_init__(self) -> None:
        if not isinstance(self.unit_id, UnitId) or not isinstance(self.projection_id, ProjectionId):
            raise TypeError("projection ref requires typed ids")
        if self.unit_id != self.projection_id.unit_id:
            raise ValueError("projection ref unit_id must match projection id")

    def to_json(self) -> JsonObject:
        return {"projection_id": self.projection_id.to_json(), "unit_id": str(self.unit_id)}

    @classmethod
    def from_json(cls, value: JsonObject) -> ProjectionRef:
        p = _object(value, "projection_ref", frozenset({"projection_id", "unit_id"}))
        raw = p.get("projection_id")
        if not hasattr(raw, "keys"):
            raise ValueError("projection_id must be an object")
        return cls(
            UnitId(_required(p.get("unit_id"), "unit_id")),
            ProjectionId.from_json(cast(JsonObject, raw)),
        )

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> ProjectionRef:
        value = canonical_json_object(data)
        if canonical_json_bytes(value) != data:
            raise ValueError("projection ref bytes are not canonical")
        return cls.from_json(value)


@dataclass(frozen=True, slots=True)
class ProjectorManifest:
    name: str
    version: str
    model_id: str | None = None
    offline: bool = True

    def __post_init__(self) -> None:
        _identity(self.name, "name")
        _identity(self.version, "version", version=True)
        if self.model_id is not None:
            _model(self.model_id)
        if type(self.offline) is not bool:
            raise TypeError("offline must be boolean")

    @property
    def identity(self) -> str:
        return f"{self.name}@{self.version}"

    def to_json(self) -> JsonObject:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "offline": self.offline,
            "version": self.version,
        }

    @classmethod
    def from_json(cls, value: JsonObject) -> ProjectorManifest:
        p = _object(
            value,
            "projector_manifest",
            frozenset({"model_id", "name", "offline", "version"}),
        )
        offline = p.get("offline")
        if type(offline) is not bool:
            raise ValueError("offline must be boolean")
        return cls(
            _required(p.get("name"), "name"),
            _required(p.get("version"), "version"),
            _optional(p.get("model_id"), "model_id"),
            offline,
        )

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> ProjectorManifest:
        value = canonical_json_object(data)
        if canonical_json_bytes(value) != data:
            raise ValueError("projector manifest bytes are not canonical")
        return cls.from_json(value)


class ProjectorPort(Protocol):
    @property
    def manifest(self) -> ProjectorManifest: ...

    def project(
        self, unit: RetrievableUnit, admitted_tree: object
    ) -> IndexProjection: ...


__all__ = [
    "MAX_CONTEXT_LENGTH",
    "MAX_HANDLE_LENGTH",
    "MAX_IDENTITY_LENGTH",
    "MAX_SUMMARY_LENGTH",
    "MAX_TERM_COUNT",
    "MAX_TERM_LENGTH",
    "IndexProjection",
    "ProjectionId",
    "ProjectionRef",
    "ProjectorManifest",
    "ProjectorPort",
]
