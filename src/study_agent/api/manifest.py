"""Immutable machine-readable description of the public API facade."""

import json as _json
import re as _re
from collections.abc import Iterable as _Iterable
from collections.abc import Mapping as _Mapping
from dataclasses import dataclass as _dataclass
from hashlib import sha256 as _sha256
from types import MappingProxyType as _MappingProxyType
from typing import cast as _cast

from study_agent import __version__ as _PACKAGE_VERSION

_SEMVER_PRERELEASE_IDENTIFIER = (
    r"(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
)
_SEMVER = _re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    rf"(?:-({_SEMVER_PRERELEASE_IDENTIFIER}(?:\.{_SEMVER_PRERELEASE_IDENTIFIER})*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_PYTHON_VERSIONS = ("3.12", "3.13")
_SUBFACADES = (
    "runtime",
    "authority",
    "storage",
    "sources",
    "capabilities",
    "artifacts",
    "assessments",
    "recall",
)
_EXPORTS = ("PublicManifest", "public_manifest", *_SUBFACADES)
_SCHEMA_VERSIONS = _MappingProxyType({"event_envelope": 1, "manifest": 1})


def _immutable_text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        raise TypeError(f"{field_name} must be a collection of strings")
    try:
        values = tuple(_cast(_Iterable[object], value))
    except TypeError:
        raise TypeError(f"{field_name} must be a collection of strings") from None
    if any(not isinstance(item, str) or not item for item in values):
        raise TypeError(f"{field_name} must contain non-empty strings")
    typed_values = tuple(item for item in values if isinstance(item, str))
    if len(set(typed_values)) != len(typed_values):
        raise ValueError(f"{field_name} must not contain duplicates")
    return typed_values


@_dataclass(frozen=True, slots=True)
class PublicManifest:
    """The exact versioned symbol boundary of ``study_agent.api``.

    The public facade is deliberately narrower than the implementation package.
    Nested collections are copied into immutable values at construction time so
    callers cannot mutate a manifest after it has been fingerprinted.
    """

    facade_version: int
    package_version: str
    python_versions: tuple[str, ...]
    subfacades: tuple[str, ...]
    exports: tuple[str, ...]
    schema_versions: _Mapping[str, int]

    def __post_init__(self) -> None:
        if type(self.facade_version) is not int or self.facade_version < 1:
            raise ValueError("facade_version must be a positive integer")
        if not isinstance(self.package_version, str) or _SEMVER.fullmatch(
            self.package_version
        ) is None:
            raise ValueError("package_version must be a semantic version")

        python_versions = _immutable_text_tuple(self.python_versions, "python_versions")
        subfacades = _immutable_text_tuple(self.subfacades, "subfacades")
        exports = _immutable_text_tuple(self.exports, "exports")
        if python_versions != tuple(sorted(python_versions)):
            raise ValueError("python_versions must be in canonical order")
        if subfacades != _SUBFACADES:
            raise ValueError("subfacades must use the approved canonical order")
        if exports != _EXPORTS:
            raise ValueError("exports must use the approved canonical order")

        if not isinstance(self.schema_versions, _Mapping):
            raise TypeError("schema_versions must be a mapping")
        schema_versions = dict(sorted(self.schema_versions.items()))
        if any(not isinstance(key, str) or not key for key in schema_versions):
            raise TypeError("schema_versions keys must be non-empty strings")
        if any(type(value) is not int or value < 1 for value in schema_versions.values()):
            raise ValueError("schema_versions values must be positive integers")

        object.__setattr__(self, "python_versions", python_versions)
        object.__setattr__(self, "subfacades", subfacades)
        object.__setattr__(self, "exports", exports)
        object.__setattr__(self, "schema_versions", _MappingProxyType(schema_versions))

    def to_json(self) -> dict[str, object]:
        """Return the manifest fields in a stable JSON-compatible shape."""

        return {
            "facade_version": self.facade_version,
            "package_version": self.package_version,
            "python_versions": self.python_versions,
            "subfacades": self.subfacades,
            "exports": self.exports,
            "schema_versions": dict(self.schema_versions),
        }

    def canonical_bytes(self) -> bytes:
        """Serialize the manifest with one deterministic UTF-8 representation."""

        return _json.dumps(
            self.to_json(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @property
    def fingerprint(self) -> str:
        """Return the SHA-256 fingerprint of the canonical manifest JSON."""

        return _sha256(self.canonical_bytes()).hexdigest()


_PUBLIC_MANIFEST = PublicManifest(
    facade_version=1,
    package_version=_PACKAGE_VERSION,
    python_versions=_PYTHON_VERSIONS,
    subfacades=_SUBFACADES,
    exports=_EXPORTS,
    schema_versions=_SCHEMA_VERSIONS,
)


def public_manifest() -> PublicManifest:
    """Return the process-stable public facade manifest."""

    return _PUBLIC_MANIFEST
