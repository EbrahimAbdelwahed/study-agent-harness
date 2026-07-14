"""Portable public contracts for trusted adaptive-tutor capabilities."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from study_agent.domain._validation import JsonObject, JsonValue, freeze_object, require_text
from study_agent.portability import (
    reject_provider_selector_name,
    reject_provider_selectors,
)
from study_agent.skills import SemanticVersion
from study_agent.tools.schema import validate_schema_definition


class TutorCapabilityId(StrEnum):
    EXPLAIN_CONCEPT = "explain_concept"
    ASSESS_UNDERSTANDING = "assess_understanding"


class CapabilityOutcomeStatus(StrEnum):
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    CANCELLED = "cancelled"
    STALE = "stale"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    id: TutorCapabilityId
    version: SemanticVersion
    input_schema: JsonObject
    output_schema: JsonObject
    required_authority: tuple[str, ...]
    supports_suspension: bool

    def __post_init__(self) -> None:
        if not isinstance(self.id, TutorCapabilityId):
            raise TypeError("capability id must use the closed TutorCapabilityId vocabulary")
        if not isinstance(self.version, SemanticVersion):
            raise TypeError("capability version must be a SemanticVersion")
        if not isinstance(self.supports_suspension, bool):
            raise TypeError("supports_suspension must be boolean")

        input_schema = freeze_object(self.input_schema)
        output_schema = freeze_object(self.output_schema)
        validate_schema_definition(input_schema)
        validate_schema_definition(output_schema)
        reject_provider_selectors(input_schema, "input_schema")
        reject_provider_selectors(output_schema, "output_schema")
        object.__setattr__(self, "input_schema", input_schema)
        object.__setattr__(self, "output_schema", output_schema)

        authority = tuple(self.required_authority)
        if not authority:
            raise ValueError("required authority cannot be empty")
        for grant in authority:
            if not isinstance(grant, str):
                raise TypeError("required authority entries must be strings")
            require_text(grant, "required authority")
            reject_provider_selector_name(grant, "required authority")
        if len(set(authority)) != len(authority):
            raise ValueError("required authority entries must be unique")
        object.__setattr__(self, "required_authority", tuple(sorted(authority)))

    @property
    def identity(self) -> str:
        return f"{self.id.value}@{self.version.major}"

    def to_json(self) -> JsonObject:
        return {
            "id": self.id.value,
            "version": str(self.version),
            "identity": self.identity,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "required_authority": self.required_authority,
            "supports_suspension": self.supports_suspension,
        }

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            _plain(self.to_json()),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(b"study-agent-capability-manifest-v1\0" + payload).hexdigest()


def _plain(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value
