"""Portable public contracts for trusted adaptive-tutor capabilities."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256

from study_agent.domain._validation import (
    JsonObject,
    JsonValue,
    freeze_json,
    freeze_object,
    require_text,
)
from study_agent.domain.authority import AuthorityContext
from study_agent.domain.identifiers import CorrelationId, RunId
from study_agent.playbooks import (
    PlaybookRunStatus,
    ReadDependency,
    ToolBehaviorPin,
    VerifiedRunRecord,
    VersionPins,
)
from study_agent.portability import (
    reject_provider_selector_name,
    reject_provider_selectors,
)
from study_agent.skills import ArtifactReference, SemanticVersion
from study_agent.tools.schema import validate_schema_definition


class TutorCapabilityId(StrEnum):
    EXPLAIN_CONCEPT = "explain_concept"
    ASSESS_UNDERSTANDING = "assess_understanding"
    PROPOSE_FLASHCARDS = "propose_flashcards"
    ANALYZE_EXAM_SAMPLE = "analyze_exam_sample"
    GRADE_RESPONSE = "grade_response"


_NAMESPACED_CAPABILITY_ID = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9]+)+$")
_NAMESPACED_AUTHORITY = re.compile(r"^[a-z][a-z0-9]*(?:[._:/-][a-z0-9]+)+$")


class CapabilityId(str):
    """A lowercase, namespaced capability identity supplied by a host."""

    def __new__(cls, value: str) -> CapabilityId:
        require_text(value, "capability id")
        if _NAMESPACED_CAPABILITY_ID.fullmatch(value) is None:
            raise ValueError("capability id must use one canonical dot namespace")
        return str.__new__(cls, value)

    @property
    def value(self) -> str:
        """Match the value protocol used by legacy capability identifiers."""

        return str(self)


type CapabilityIdentifier = TutorCapabilityId | CapabilityId


class CapabilityOutcomeStatus(StrEnum):
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    STALE = "stale"
    FAILED = "failed"


class CapabilityGatewayErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    IN_PROGRESS = "in_progress"
    INCOMPATIBLE_RUNTIME = "incompatible_runtime"


class CapabilityGatewayError(RuntimeError):
    def __init__(
        self,
        code: CapabilityGatewayErrorCode,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        if not isinstance(code, CapabilityGatewayErrorCode):
            raise TypeError("gateway error code must use CapabilityGatewayErrorCode")
        require_text(message, "gateway error message")
        if retryable != (code is CapabilityGatewayErrorCode.IN_PROGRESS):
            raise ValueError("only in_progress gateway errors are retryable")
        self.code = code
        self.retryable = retryable
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    id: CapabilityIdentifier
    version: SemanticVersion
    input_schema: JsonObject
    output_schema: JsonObject
    required_authority: tuple[str, ...]
    supports_suspension: bool
    implementation_version: SemanticVersion

    def __post_init__(self) -> None:
        if isinstance(self.id, str) and not isinstance(
            self.id, (TutorCapabilityId, CapabilityId)
        ):
            object.__setattr__(self, "id", CapabilityId(self.id))
        if not isinstance(self.id, (TutorCapabilityId, CapabilityId)):
            raise TypeError("capability id must use CapabilityId")
        if not isinstance(self.version, SemanticVersion):
            raise TypeError("capability version must be a SemanticVersion")
        if not isinstance(self.supports_suspension, bool):
            raise TypeError("supports_suspension must be boolean")
        if not isinstance(self.implementation_version, SemanticVersion):
            raise TypeError("implementation_version must be a SemanticVersion")

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
            if _NAMESPACED_AUTHORITY.fullmatch(grant) is None:
                raise ValueError("required authority entries must be lowercase namespaced names")
        if len(set(authority)) != len(authority):
            raise ValueError("required authority entries must be unique")
        object.__setattr__(self, "required_authority", tuple(sorted(authority)))

    @property
    def identity(self) -> str:
        return f"{self.id.value}@{self.version}"

    @property
    def implementation_contract_version(self) -> SemanticVersion:
        """Alias for the specification's implementation-contract wording."""

        return self.implementation_version

    def to_json(self) -> JsonObject:
        payload: JsonObject = {
            "id": self.id.value,
            "version": str(self.version),
            "identity": self.identity,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "required_authority": self.required_authority,
            "supports_suspension": self.supports_suspension,
            "implementation_version": str(self.implementation_version),
        }
        return payload

    @property
    def fingerprint(self) -> str:
        return _fingerprint("study-agent-capability-manifest-v1", self.to_json())

    def to_bytes(self) -> bytes:
        """Return the canonical wire representation of this manifest."""

        return _canonical_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> CapabilityManifest:
        raw = _decode_object(data, "capability manifest")
        manifest = cls.from_json(raw)
        if manifest.to_bytes() != data:
            raise ValueError("capability manifest is not semantically canonical")
        return manifest

    @classmethod
    def from_json(cls, raw: JsonObject) -> CapabilityManifest:
        expected = {
            "id",
            "version",
            "identity",
            "input_schema",
            "output_schema",
            "required_authority",
            "supports_suspension",
        }
        expected.add("implementation_version")
        if set(raw) != expected:
            raise ValueError("capability manifest has an unexpected shape")
        identifier = _capability_identifier(_string_value(raw.get("id"), "id"))
        version = SemanticVersion.parse(_string_value(raw.get("version"), "version"))
        implementation = SemanticVersion.parse(
            _string_value(raw.get("implementation_version"), "implementation_version")
        )
        grants = raw.get("required_authority")
        if not isinstance(grants, (tuple, list)):
            raise ValueError("required_authority must be an array")
        schema_input = _object_value(raw.get("input_schema"), "input_schema")
        schema_output = _object_value(raw.get("output_schema"), "output_schema")
        suspension = raw.get("supports_suspension")
        if not isinstance(suspension, bool):
            raise ValueError("supports_suspension must be boolean")
        manifest = cls(
            identifier,
            version,
            schema_input,
            schema_output,
            tuple(_string_value(item, "required authority") for item in grants),
            suspension,
            implementation,
        )
        if _string_value(raw.get("identity"), "identity") != manifest.identity:
            raise ValueError("capability manifest identity is inconsistent")
        return manifest


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    """A host-issued, provider-neutral request for one manifested capability."""

    manifest_identity: str
    inputs: JsonObject
    authority: AuthorityContext
    correlation_id: CorrelationId | str
    expected_stream_high_water: int
    idempotency_key: str

    def __post_init__(self) -> None:
        _canonical_capability_identity(self.manifest_identity)
        object.__setattr__(self, "inputs", freeze_object(self.inputs))
        if not isinstance(self.authority, AuthorityContext):
            raise TypeError("authority must be an AuthorityContext")
        correlation = self.correlation_id
        if isinstance(correlation, str):
            correlation = CorrelationId(correlation)
        if not isinstance(correlation, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")
        object.__setattr__(self, "correlation_id", correlation)
        if type(self.expected_stream_high_water) is not int or self.expected_stream_high_water < 0:
            raise ValueError("expected_stream_high_water must be a non-negative integer")
        require_text(self.idempotency_key, "idempotency_key")

    @property
    def capability_identity(self) -> str:
        """Compatibility alias for consumers that call the field capability identity."""

        return self.manifest_identity

    @property
    def input(self) -> JsonObject:
        """Singular alias retained for hosts using the request vocabulary."""

        return self.inputs

    @property
    def expected_stream_sequence(self) -> int:
        return self.expected_stream_high_water

    @property
    def input_fingerprint(self) -> str:
        return _fingerprint(
            "study-agent-capability-request-input-v1",
            {"manifest_identity": self.manifest_identity, "inputs": self.inputs},
        )

    @property
    def authority_fingerprint(self) -> str:
        return _fingerprint(
            "study-agent-capability-request-authority-v1", _authority_json(self.authority)
        )

    @property
    def retry_identity_fingerprint(self) -> str:
        return _fingerprint(
            "study-agent-capability-request-retry-v1",
            {
                "idempotency_key": self.idempotency_key,
                "input_fingerprint": self.input_fingerprint,
            },
        )

    def to_json(self) -> JsonObject:
        return {
            "manifest_identity": self.manifest_identity,
            "inputs": self.inputs,
            "authority": _authority_json(self.authority),
            "correlation_id": str(self.correlation_id),
            "expected_stream_high_water": self.expected_stream_high_water,
            "idempotency_key": self.idempotency_key,
            "input_fingerprint": self.input_fingerprint,
            "authority_fingerprint": self.authority_fingerprint,
            "retry_identity_fingerprint": self.retry_identity_fingerprint,
        }

    def to_bytes(self) -> bytes:
        """Return deterministic request bytes without serializing opaque authority."""

        return _canonical_bytes(self.to_json())

    @classmethod
    def from_bytes(
        cls, data: bytes, *, authority: AuthorityContext
    ) -> CapabilityRequest:
        raw = _decode_object(data, "capability request")
        expected = {
            "manifest_identity",
            "inputs",
            "authority",
            "correlation_id",
            "expected_stream_high_water",
            "idempotency_key",
            "input_fingerprint",
            "authority_fingerprint",
            "retry_identity_fingerprint",
        }
        if set(raw) != expected:
            raise ValueError("capability request has an unexpected shape")
        if raw.get("authority") != _authority_json(authority):
            raise ValueError("capability request authority does not match the host context")
        high_water = raw.get("expected_stream_high_water")
        if type(high_water) is not int:
            raise ValueError("expected_stream_high_water must be an integer")
        request = cls(
            _string_value(raw.get("manifest_identity"), "manifest_identity"),
            _object_value(raw.get("inputs"), "inputs"),
            authority,
            _string_value(raw.get("correlation_id"), "correlation_id"),
            high_water,
            _string_value(raw.get("idempotency_key"), "idempotency_key"),
        )
        for name, actual in (
            ("input_fingerprint", request.input_fingerprint),
            ("authority_fingerprint", request.authority_fingerprint),
            ("retry_identity_fingerprint", request.retry_identity_fingerprint),
        ):
            if _string_value(raw.get(name), name) != actual:
                raise ValueError(f"capability request {name} is inconsistent")
        if request.to_bytes() != data:
            raise ValueError("capability request is not semantically canonical")
        return request


@dataclass(frozen=True, slots=True)
class CapabilityContinuation:
    run_id: RunId
    capability_id: CapabilityIdentifier
    capability_version: SemanticVersion
    manifest_fingerprint: str
    authority_fingerprint: str
    retry_identity_fingerprint: str
    definition_fingerprint: str
    checkpoint_fingerprint: str
    dialogue_step_id: str
    next_step_index: int
    inputs: JsonObject
    pins: VersionPins
    read_dependencies: tuple[ReadDependency, ...]
    input_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("continuation run_id must be a RunId")
        if isinstance(self.capability_id, str) and not isinstance(
            self.capability_id, (TutorCapabilityId, CapabilityId)
        ):
            object.__setattr__(self, "capability_id", CapabilityId(self.capability_id))
        if not isinstance(self.capability_id, (TutorCapabilityId, CapabilityId)):
            raise TypeError("continuation capability_id must use CapabilityId")
        if not isinstance(self.capability_version, SemanticVersion):
            raise TypeError("continuation capability_version must be SemanticVersion")
        for value, name in (
            (self.manifest_fingerprint, "manifest_fingerprint"),
            (self.authority_fingerprint, "authority_fingerprint"),
            (self.retry_identity_fingerprint, "retry_identity_fingerprint"),
            (self.definition_fingerprint, "definition_fingerprint"),
            (self.checkpoint_fingerprint, "checkpoint_fingerprint"),
        ):
            _require_sha256(value, name)
        require_text(self.dialogue_step_id, "dialogue_step_id")
        if type(self.next_step_index) is not int or self.next_step_index < 1:
            raise ValueError("continuation next_step_index must be positive")
        object.__setattr__(self, "inputs", freeze_object(self.inputs))
        if not isinstance(self.pins, VersionPins):
            raise TypeError("continuation pins must be VersionPins")
        dependencies = tuple(self.read_dependencies)
        if not all(isinstance(item, ReadDependency) for item in dependencies):
            raise TypeError("continuation dependencies must use ReadDependency")
        keys = tuple((item.kind, item.id) for item in dependencies)
        if len(set(keys)) != len(keys):
            raise ValueError("continuation dependencies must be unique by kind and id")
        object.__setattr__(self, "read_dependencies", dependencies)
        expected_input_fingerprint = _fingerprint(
            "study-agent-capability-input-v1", {"inputs": self.inputs}
        )
        if (
            self.input_fingerprint is not None
            and self.input_fingerprint != expected_input_fingerprint
        ):
            raise ValueError("continuation input_fingerprint is inconsistent with inputs")
        object.__setattr__(self, "input_fingerprint", expected_input_fingerprint)

    @property
    def fingerprint(self) -> str:
        return _fingerprint("study-agent-capability-continuation-v1", self.to_json())

    def to_json(self) -> JsonObject:
        return {
            "run_id": str(self.run_id),
            "capability_id": self.capability_id.value,
            "capability_version": str(self.capability_version),
            "manifest_fingerprint": self.manifest_fingerprint,
            "authority_fingerprint": self.authority_fingerprint,
            "retry_identity_fingerprint": self.retry_identity_fingerprint,
            "definition_fingerprint": self.definition_fingerprint,
            "checkpoint_fingerprint": self.checkpoint_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "dialogue_step_id": self.dialogue_step_id,
            "next_step_index": self.next_step_index,
            "inputs": self.inputs,
            "pins": _pins_json(self.pins),
            "read_dependencies": tuple(
                {"kind": item.kind, "id": item.id, "version": item.version}
                for item in self.read_dependencies
            ),
        }

    def to_bytes(self) -> bytes:
        """Return the canonical wire representation of this continuation."""

        return _canonical_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> CapabilityContinuation:
        continuation = cls.from_json(_decode_object(data, "capability continuation"))
        if continuation.to_bytes() != data:
            raise ValueError("capability continuation is not semantically canonical")
        return continuation

    @classmethod
    def from_json(cls, raw: JsonObject) -> CapabilityContinuation:
        expected = {
            "run_id",
            "capability_id",
            "capability_version",
            "manifest_fingerprint",
            "authority_fingerprint",
            "retry_identity_fingerprint",
            "definition_fingerprint",
            "checkpoint_fingerprint",
            "input_fingerprint",
            "dialogue_step_id",
            "next_step_index",
            "inputs",
            "pins",
            "read_dependencies",
        }
        if set(raw) != expected:
            raise ValueError("capability continuation has an unexpected shape")
        dependencies = raw.get("read_dependencies")
        if not isinstance(dependencies, (tuple, list)):
            raise ValueError("read_dependencies must be an array")
        decoded_dependencies = tuple(
            ReadDependency(
                _string_value(_object_value(item, "read dependency").get("kind"), "kind"),
                _string_value(_object_value(item, "read dependency").get("id"), "id"),
                _string_value(
                    _object_value(item, "read dependency").get("version"), "version"
                ),
            )
            for item in dependencies
        )
        next_step_index = raw.get("next_step_index")
        if type(next_step_index) is not int:
            raise ValueError("next_step_index must be an integer")
        inputs = _object_value(raw.get("inputs"), "inputs")
        return cls(
            RunId(_string_value(raw.get("run_id"), "run_id")),
            _capability_identifier(_string_value(raw.get("capability_id"), "capability_id")),
            SemanticVersion.parse(
                _string_value(raw.get("capability_version"), "capability_version")
            ),
            _string_value(raw.get("manifest_fingerprint"), "manifest_fingerprint"),
            _string_value(raw.get("authority_fingerprint"), "authority_fingerprint"),
            _string_value(
                raw.get("retry_identity_fingerprint"), "retry_identity_fingerprint"
            ),
            _string_value(raw.get("definition_fingerprint"), "definition_fingerprint"),
            _string_value(raw.get("checkpoint_fingerprint"), "checkpoint_fingerprint"),
            _string_value(raw.get("dialogue_step_id"), "dialogue_step_id"),
            next_step_index,
            inputs,
            _pins_from_json(_object_value(raw.get("pins"), "pins")),
            decoded_dependencies,
            _string_value(raw.get("input_fingerprint"), "input_fingerprint"),
        )


@dataclass(frozen=True, slots=True)
class CompletedCapabilityOutcome:
    run: VerifiedRunRecord
    output: JsonValue
    status: CapabilityOutcomeStatus = field(
        default=CapabilityOutcomeStatus.COMPLETED, init=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.run, VerifiedRunRecord):
            raise TypeError("completed capability run must be VerifiedRunRecord")
        if self.run.status is not PlaybookRunStatus.COMPLETED:
            raise ValueError("completed capability outcomes require a completed verified run")
        object.__setattr__(self, "output", freeze_json(self.output))

    def to_json(self) -> JsonObject:
        return {
            "status": self.status.value,
            "run": _verified_run_json(self.run),
            "output": self.output,
        }

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())


@dataclass(frozen=True, slots=True)
class SuspendedCapabilityOutcome:
    run_id: RunId
    dialogue_request: str
    continuation: CapabilityContinuation
    response_schema: JsonObject
    status: CapabilityOutcomeStatus = field(
        default=CapabilityOutcomeStatus.SUSPENDED, init=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("suspended outcome run_id must be RunId")
        if not isinstance(self.continuation, CapabilityContinuation):
            raise TypeError("suspended outcome continuation is invalid")
        if self.run_id != self.continuation.run_id:
            raise ValueError("suspended outcome and continuation run ids differ")
        require_text(self.dialogue_request, "dialogue_request")
        schema = freeze_object(self.response_schema)
        validate_schema_definition(schema)
        reject_provider_selectors(schema, "response_schema")
        object.__setattr__(self, "response_schema", schema)

    def to_json(self) -> JsonObject:
        return {
            "status": self.status.value,
            "run_id": str(self.run_id),
            "dialogue_request": self.dialogue_request,
            "continuation": self.continuation.to_json(),
            "response_schema": self.response_schema,
        }

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())


@dataclass(frozen=True, slots=True)
class TerminatedCapabilityOutcome:
    """Legacy runtime observation excluded from the public outcome union."""

    run: VerifiedRunRecord
    status: str = field(default="terminated", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.run, VerifiedRunRecord):
            raise TypeError("terminated capability run must be VerifiedRunRecord")
        if self.run.status is not PlaybookRunStatus.TERMINATED:
            raise ValueError("terminated capability outcomes require a terminated verified run")

    def to_json(self) -> JsonObject:
        return {"status": self.status, "run": _verified_run_json(self.run)}

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())


@dataclass(frozen=True, slots=True)
class CancelledCapabilityOutcome:
    run_id: RunId
    message: str
    status: CapabilityOutcomeStatus = field(
        default=CapabilityOutcomeStatus.CANCELLED, init=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("cancelled outcome run_id must be RunId")
        require_text(self.message, "cancelled outcome message")

    def to_json(self) -> JsonObject:
        return {"status": self.status.value, "run_id": str(self.run_id), "message": self.message}

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())


@dataclass(frozen=True, slots=True)
class StaleCapabilityOutcome:
    run_id: RunId
    message: str
    status: CapabilityOutcomeStatus = field(
        default=CapabilityOutcomeStatus.STALE, init=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("stale outcome run_id must be RunId")
        require_text(self.message, "stale outcome message")

    def to_json(self) -> JsonObject:
        return {"status": self.status.value, "run_id": str(self.run_id), "message": self.message}

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())


@dataclass(frozen=True, slots=True)
class FailedCapabilityOutcome:
    run_id: RunId
    message: str
    status: CapabilityOutcomeStatus = field(
        default=CapabilityOutcomeStatus.FAILED, init=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("failed outcome run_id must be RunId")
        require_text(self.message, "failed outcome message")

    def to_json(self) -> JsonObject:
        return {"status": self.status.value, "run_id": str(self.run_id), "message": self.message}

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())


type CapabilityOutcome = (
    CompletedCapabilityOutcome
    | SuspendedCapabilityOutcome
    | CancelledCapabilityOutcome
    | StaleCapabilityOutcome
    | FailedCapabilityOutcome
)


def _capability_identifier(value: str) -> CapabilityIdentifier:
    try:
        return TutorCapabilityId(value)
    except ValueError:
        return CapabilityId(value)


def _canonical_capability_identity(value: str) -> str:
    require_text(value, "manifest_identity")
    if value.count("@") != 1:
        raise ValueError("manifest_identity must contain one capability/version separator")
    identifier_value, version_value = value.split("@")
    identifier = _capability_identifier(identifier_value)
    version = SemanticVersion.parse(version_value)
    canonical = f"{identifier.value}@{version}"
    if value != canonical:
        raise ValueError("manifest_identity must use canonical full semantic version")
    return canonical


def _authority_json(authority: AuthorityContext) -> JsonObject:
    return {
        "principal_kind": authority.principal_kind.value,
        "principal_id": authority.principal_id,
        "grants": tuple(sorted(grant.name for grant in authority.grants)),
        "scopes": tuple(sorted(scope.name for scope in authority.scopes)),
        "correlation_id": authority.correlation_id,
        "session_id": authority.session_id,
    }


def _verified_run_json(run: VerifiedRunRecord) -> JsonObject:
    termination = run.termination
    return {
        "run_id": str(run.run_id),
        "definition_fingerprint": run.definition_fingerprint,
        "inputs": run.inputs,
        "pins": _pins_json(run.pins),
        "read_dependencies": tuple(
            {"kind": item.kind, "id": item.id, "version": item.version}
            for item in run.read_dependencies
        ),
        "outputs": run.outputs,
        "traces": tuple(
            {
                "step_id": item.step_id,
                "step_kind": item.step_kind,
                "status": item.status.value,
                "occurred_at": item.occurred_at.isoformat(),
                "details": item.details,
            }
            for item in run.traces
        ),
        "status": run.status.value,
        "termination": (
            None
            if termination is None
            else {
                "passed": termination.passed,
                "disposition": termination.disposition.value,
                "result": termination.result,
                "reason": termination.reason,
            }
        ),
    }


def _pins_from_json(raw: JsonObject) -> VersionPins:
    expected = {"skill", "playbook", "prompt", "tool_behaviors", "model_adapter", "state_contract"}
    if set(raw) != expected:
        raise ValueError("capability pins have an unexpected shape")

    def reference(value: object, name: str) -> ArtifactReference:
        item = _object_value(value, name)
        return ArtifactReference(
            _string_value(item.get("id"), f"{name}.id"),
            SemanticVersion.parse(_string_value(item.get("version"), f"{name}.version")),
        )

    raw_tools = raw.get("tool_behaviors")
    if not isinstance(raw_tools, (tuple, list)):
        raise ValueError("tool_behaviors must be an array")
    tools = tuple(
        ToolBehaviorPin(
            _string_value(_object_value(item, "tool behavior").get("name"), "tool name"),
            SemanticVersion.parse(
                _string_value(
                    _object_value(item, "tool behavior").get("version"), "tool version"
                )
            ),
        )
        for item in raw_tools
    )
    return VersionPins(
        reference(raw.get("skill"), "skill"),
        reference(raw.get("playbook"), "playbook"),
        reference(raw.get("prompt"), "prompt"),
        tools,
        reference(raw.get("model_adapter"), "model_adapter"),
        reference(raw.get("state_contract"), "state_contract"),
    )


def encode_capability_outcome(outcome: CapabilityOutcome) -> bytes:
    """Encode any closed capability outcome with canonical JSON ordering."""

    if not isinstance(
        outcome,
        (
            CompletedCapabilityOutcome,
            SuspendedCapabilityOutcome,
            CancelledCapabilityOutcome,
            StaleCapabilityOutcome,
            FailedCapabilityOutcome,
        ),
    ):
        raise TypeError("outcome must be a CapabilityOutcome")
    return outcome.to_bytes()


def _canonical_bytes(value: JsonValue) -> bytes:
    try:
        return json.dumps(
            _plain(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("capability contract is not canonical JSON") from error


def _decode_object(data: bytes, name: str) -> JsonObject:
    if not isinstance(data, bytes):
        raise TypeError(f"{name} bytes must be bytes")
    try:
        decoded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not valid JSON") from error
    if not isinstance(decoded, dict):
        raise ValueError(f"{name} must encode a JSON object")
    raw = _thaw_json(decoded)
    if not isinstance(raw, Mapping):  # pragma: no cover - guarded by decoded's shape
        raise ValueError(f"{name} must encode a JSON object")
    if _canonical_bytes(raw) != data:
        raise ValueError(f"{name} must use canonical JSON encoding")
    return raw


def _thaw_json(value: object) -> JsonValue:
    if isinstance(value, dict):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_thaw_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("contract JSON contains an unsupported value")


def _string_value(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    return value


def _object_value(value: object, name: str) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _plain(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _require_sha256(value: str, name: str) -> None:
    require_text(value, name)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _fingerprint(domain: str, value: JsonObject) -> str:
    payload = _canonical_bytes(value)
    return sha256(domain.encode("utf-8") + b"\0" + payload).hexdigest()


def _pins_json(pins: VersionPins) -> JsonObject:
    return {
        "skill": {"id": pins.skill.id, "version": str(pins.skill.version)},
        "playbook": {"id": pins.playbook.id, "version": str(pins.playbook.version)},
        "prompt": {"id": pins.prompt.id, "version": str(pins.prompt.version)},
        "tool_behaviors": tuple(
            {"name": item.tool_name, "version": str(item.version)}
            for item in pins.tool_behaviors
        ),
        "model_adapter": {
            "id": pins.model_adapter.id,
            "version": str(pins.model_adapter.version),
        },
        "state_contract": {
            "id": pins.state_contract.id,
            "version": str(pins.state_contract.version),
        },
    }
