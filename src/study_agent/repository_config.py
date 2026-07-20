"""Strict, non-secret configuration shared by repository composition and lifecycle."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.state import canonical_json_bytes

CONFIG_SCHEMA_VERSION = 1
CONFIG_FILENAME = "study-agent.json"
MAX_CONFIG_BYTES = 64 * 1024
_ENVIRONMENT_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_SECRET_FIELD_PARTS = frozenset(
    {
        "api_key",
        "apikey",
        "auth",
        "authentication",
        "authorization",
        "bearer",
        "cookie",
        "credential",
        "credentials",
        "key",
        "passphrase",
        "password",
        "private_key",
        "secret",
        "token",
    }
)
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


class LocalConfigError(ValueError):
    """The local configuration is absent, malformed, or contains secret material."""


@dataclass(frozen=True, slots=True)
class ModelAdapterConfig:
    """Provider-neutral operational selection for one technical model adapter."""

    adapter_id: str
    settings: JsonObject = field(default_factory=dict, repr=False)
    credential_env: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.adapter_id, str):
            raise LocalConfigError("model.adapter_id must be text")
        _trimmed(self.adapter_id, "model.adapter_id")
        if not isinstance(self.settings, Mapping):
            raise LocalConfigError("model.settings must be an object")
        try:
            settings = freeze_object(self.settings)
        except (RecursionError, TypeError, ValueError) as error:
            raise LocalConfigError("model.settings must contain strict JSON values") from error
        _reject_secret_fields(settings)
        object.__setattr__(self, "settings", settings)
        if self.credential_env is not None and (
            not isinstance(self.credential_env, str)
            or _ENVIRONMENT_NAME.fullmatch(self.credential_env) is None
        ):
            raise LocalConfigError(
                "model.credential_env must be an uppercase environment-variable name"
            )


@dataclass(frozen=True, slots=True)
class LocalRepositoryConfig:
    """Versioned repository configuration; credentials are references, never values."""

    model: ModelAdapterConfig | None = None
    schema_version: int = CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != CONFIG_SCHEMA_VERSION:
            raise LocalConfigError(
                f"schema_version must be exactly {CONFIG_SCHEMA_VERSION}"
            )
        if self.model is not None and not isinstance(self.model, ModelAdapterConfig):
            raise LocalConfigError("model must be a ModelAdapterConfig or null")

    def to_bytes(self) -> bytes:
        model: JsonValue
        if self.model is None:
            model = None
        else:
            model = {
                "adapter_id": self.model.adapter_id,
                "credential_env": self.model.credential_env,
                "settings": self.model.settings,
            }
        payload = canonical_json_bytes(
            {"schema_version": self.schema_version, "model": model}
        ) + b"\n"
        if len(payload) > MAX_CONFIG_BYTES:
            raise LocalConfigError("serialized configuration exceeds the 64 KiB bound")
        return payload

    @classmethod
    def from_bytes(cls, payload: bytes) -> LocalRepositoryConfig:
        if type(payload) is not bytes or not payload or len(payload) > MAX_CONFIG_BYTES:
            raise LocalConfigError("configuration must be non-empty bounded UTF-8 JSON")
        try:
            raw: Any = json.loads(
                payload.decode("utf-8", errors="strict"),
                object_pairs_hook=_object_without_duplicates,
                parse_constant=_invalid_json_constant,
            )
        except (OverflowError, RecursionError, UnicodeError, ValueError) as error:
            raise LocalConfigError("configuration must be valid UTF-8 JSON") from error
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "model"}:
            raise LocalConfigError("configuration fields are incompatible")
        schema_version = raw["schema_version"]
        if type(schema_version) is not int:
            raise LocalConfigError("schema_version must be an integer")
        model_raw = raw["model"]
        model = None if model_raw is None else _decode_model(model_raw)
        return cls(model=model, schema_version=schema_version)

    @classmethod
    def load(cls, path: Path) -> LocalRepositoryConfig:
        if path.is_symlink() or not path.is_file():
            raise LocalConfigError("configuration must be a regular non-symlink file")
        try:
            return cls.from_bytes(path.read_bytes())
        except OSError as error:
            raise LocalConfigError("configuration could not be read") from error


def _decode_model(raw: object) -> ModelAdapterConfig:
    if not isinstance(raw, dict) or set(raw) != {
        "adapter_id",
        "credential_env",
        "settings",
    }:
        raise LocalConfigError("model configuration fields are incompatible")
    adapter_id = raw["adapter_id"]
    if not isinstance(adapter_id, str):
        raise LocalConfigError("model.adapter_id must be text")
    credential_env = raw["credential_env"]
    if credential_env is not None and not isinstance(credential_env, str):
        raise LocalConfigError("model.credential_env must be text or null")
    settings = raw["settings"]
    if not isinstance(settings, dict):
        raise LocalConfigError("model.settings must be an object")
    return ModelAdapterConfig(
        adapter_id=adapter_id,
        credential_env=credential_env,
        settings=cast(JsonObject, settings),
    )


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LocalConfigError("configuration cannot contain duplicate object keys")
        result[key] = value
    return result


def _invalid_json_constant(value: str) -> None:
    raise LocalConfigError(f"invalid JSON number: {value}")


def _trimmed(value: str, name: str) -> None:
    if not value or value != value.strip():
        raise LocalConfigError(f"{name} must be non-empty trimmed text")


def _reject_secret_fields(value: JsonValue) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            camel_split = _CAMEL_BOUNDARY.sub("_", key).lower()
            normalized = _NON_ALPHANUMERIC.sub("_", camel_split).strip("_")
            parts = tuple(part for part in normalized.split("_") if part)
            if (
                normalized in _SECRET_FIELD_PARTS
                or any(normalized.endswith(f"_{part}") for part in _SECRET_FIELD_PARTS)
                or any(part in _SECRET_FIELD_PARTS for part in parts)
            ):
                raise LocalConfigError("model.settings cannot contain credential fields")
            _reject_secret_fields(item)
    elif isinstance(value, tuple):
        for item in value:
            _reject_secret_fields(item)


EMPTY_CONFIG = LocalRepositoryConfig()

__all__ = [
    "CONFIG_FILENAME",
    "CONFIG_SCHEMA_VERSION",
    "EMPTY_CONFIG",
    "MAX_CONFIG_BYTES",
    "LocalConfigError",
    "LocalRepositoryConfig",
    "ModelAdapterConfig",
]
