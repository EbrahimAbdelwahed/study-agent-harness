"""Static, host-owned workaround manifests and truthful receipts.

This module intentionally has no executor, filesystem, network, subprocess, or
dynamic loading capability.  It only describes already-installed strategies
and validates host-supplied execution receipts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any, cast

from study_agent.state import canonical_json_bytes, canonical_json_object


class WorkaroundInputKind(StrEnum):
    PDF = "pdf"
    TEXT = "text"
    MARKDOWN = "markdown"
    TABULAR = "tabular"


class WorkaroundOutputKind(StrEnum):
    TEXT = "text"
    MARKDOWN = "markdown"
    TABULAR = "tabular"


class WorkaroundEffect(StrEnum):
    PURE = "pure"
    READ_LOCAL = "read_local"
    WRITE_DERIVED = "write_derived"
    NETWORK = "network"
    CREDENTIAL = "credential"


class WorkaroundApprovalPolicy(StrEnum):
    NONE = "none"
    HOST_APPROVAL = "host_approval"


class WorkaroundReceiptStatus(StrEnum):
    NOT_AVAILABLE = "not_available"
    REQUIRES_APPROVAL = "requires_approval"
    ATTEMPTED_SUCCEEDED = "attempted_succeeded"
    ATTEMPTED_FAILED = "attempted_failed"


_OPAQUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _opaque(value: object, field: str) -> str:
    if not isinstance(value, str) or _OPAQUE.fullmatch(value) is None:
        raise ValueError(f"invalid_{field}")
    return value


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"invalid_{field}")
    return value


@dataclass(frozen=True, slots=True)
class WorkaroundManifest:
    identity: str
    version: int
    input_kind: WorkaroundInputKind
    output_kind: WorkaroundOutputKind
    effects: tuple[WorkaroundEffect, ...]
    approval_policy: WorkaroundApprovalPolicy
    preconditions: tuple[str, ...] = ()
    quality_limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _opaque(self.identity, "identity")
        if type(self.version) is not int or self.version < 1:
            raise ValueError("invalid_version")
        if not isinstance(self.input_kind, WorkaroundInputKind):
            raise ValueError("invalid_input_kind")
        if not isinstance(self.output_kind, WorkaroundOutputKind):
            raise ValueError("invalid_output_kind")
        if not isinstance(self.approval_policy, WorkaroundApprovalPolicy):
            raise ValueError("invalid_approval_policy")
        if not self.effects:
            raise ValueError("invalid_effects")
        if tuple(sorted(set(self.effects), key=lambda value: value.value)) != self.effects:
            raise ValueError("noncanonical_effects")
        for effect in self.effects:
            if not isinstance(effect, WorkaroundEffect):
                raise ValueError("invalid_effects")
        for value in (*self.preconditions, *self.quality_limitations):
            _opaque(value, "manifest_text")
        if WorkaroundEffect.NETWORK in self.effects or WorkaroundEffect.CREDENTIAL in self.effects:
            raise ValueError("undeclared_effect")

    def to_json(self) -> dict[str, Any]:
        return {
            "approval_policy": self.approval_policy.value,
            "effects": [effect.value for effect in self.effects],
            "identity": self.identity,
            "input_kind": self.input_kind.value,
            "output_kind": self.output_kind.value,
            "preconditions": list(self.preconditions),
            "quality_limitations": list(self.quality_limitations),
            "schema_version": 1,
            "version": self.version,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(cast(Any, self.to_json()))

    @property
    def fingerprint(self) -> str:
        return sha256(b"study-agent-workaround-manifest-v1\0" + self.to_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class WorkaroundTask:
    input_kind: WorkaroundInputKind
    output_kind: WorkaroundOutputKind
    input_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.input_kind, WorkaroundInputKind):
            raise ValueError("invalid_input_kind")
        if not isinstance(self.output_kind, WorkaroundOutputKind):
            raise ValueError("invalid_output_kind")
        _digest(self.input_fingerprint, "input_fingerprint")


@dataclass(frozen=True, slots=True)
class WorkaroundExecutionReceipt:
    status: WorkaroundReceiptStatus
    manifest_identity: str
    manifest_version: int
    input_fingerprint: str
    output_fingerprint: str | None = None
    provenance_fingerprint: str | None = None
    limitation_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, WorkaroundReceiptStatus):
            raise ValueError("invalid_status")
        _opaque(self.manifest_identity, "manifest_identity")
        if type(self.manifest_version) is not int or self.manifest_version < 1:
            raise ValueError("invalid_manifest_version")
        _digest(self.input_fingerprint, "input_fingerprint")
        if (
            self.status is WorkaroundReceiptStatus.ATTEMPTED_SUCCEEDED
            and (self.output_fingerprint is None or self.provenance_fingerprint is None)
        ):
            raise ValueError("success_requires_provenance")
        if self.output_fingerprint is not None:
            _digest(self.output_fingerprint, "output_fingerprint")
        if self.provenance_fingerprint is not None:
            _digest(self.provenance_fingerprint, "provenance_fingerprint")
        if self.limitation_fingerprint is not None:
            _digest(self.limitation_fingerprint, "limitation_fingerprint")

    def to_json(self) -> dict[str, object]:
        return {
            "input_fingerprint": self.input_fingerprint,
            "limitation_fingerprint": self.limitation_fingerprint,
            "manifest_identity": self.manifest_identity,
            "manifest_version": self.manifest_version,
            "output_fingerprint": self.output_fingerprint,
            "provenance_fingerprint": self.provenance_fingerprint,
            "schema_version": 1,
            "status": self.status.value,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(cast(Any, self.to_json()))

    @classmethod
    def from_bytes(cls, data: bytes) -> WorkaroundExecutionReceipt:
        try:
            value = canonical_json_object(data)
            fields = {
                "schema_version", "status", "manifest_identity", "manifest_version",
                "input_fingerprint", "output_fingerprint", "provenance_fingerprint",
                "limitation_fingerprint",
            }
            if set(value) != fields or canonical_json_bytes(value) != data:
                raise ValueError
            if value["schema_version"] != 1:
                raise ValueError
            return cls(
                WorkaroundReceiptStatus(value["status"]),
                value["manifest_identity"],
                value["manifest_version"],
                value["input_fingerprint"],
                value["output_fingerprint"],
                value["provenance_fingerprint"],
                value["limitation_fingerprint"],
            )
        except (TypeError, ValueError, UnicodeDecodeError):
            raise ValueError("invalid_execution_receipt") from None


class WorkaroundRegistry:
    """Deterministic lookup over host-installed static manifests."""

    def __init__(self, manifests: tuple[WorkaroundManifest, ...] = ()) -> None:
        by_identity: dict[str, WorkaroundManifest] = {}
        for manifest in manifests:
            if manifest.identity in by_identity:
                raise ValueError("duplicate_manifest_identity")
            by_identity[manifest.identity] = manifest
        self._manifests = by_identity

    def select(self, task: WorkaroundTask, granted: frozenset[str]) -> WorkaroundExecutionReceipt:
        for identity in sorted(self._manifests):
            manifest = self._manifests[identity]
            if (
                manifest.input_kind is task.input_kind
                and manifest.output_kind is task.output_kind
                and identity in granted
            ):
                if manifest.approval_policy is WorkaroundApprovalPolicy.HOST_APPROVAL:
                    return WorkaroundExecutionReceipt(
                        WorkaroundReceiptStatus.REQUIRES_APPROVAL,
                        manifest.identity,
                        manifest.version,
                        task.input_fingerprint,
                    )
                return WorkaroundExecutionReceipt(
                    WorkaroundReceiptStatus.NOT_AVAILABLE,
                    manifest.identity,
                    manifest.version,
                    task.input_fingerprint,
                )
        return WorkaroundExecutionReceipt(
            WorkaroundReceiptStatus.NOT_AVAILABLE,
            "none@1",
            1,
            task.input_fingerprint,
        )

    def get(self, identity: str) -> WorkaroundManifest:
        try:
            return self._manifests[identity]
        except KeyError:
            raise ValueError("manifest_not_found") from None

    @property
    def manifests(self) -> tuple[WorkaroundManifest, ...]:
        return tuple(self._manifests[key] for key in sorted(self._manifests))

    def validate_execution(
        self,
        task: WorkaroundTask,
        receipt: WorkaroundExecutionReceipt,
        *,
        granted: frozenset[str],
        approved: bool = False,
    ) -> WorkaroundExecutionReceipt:
        if receipt.status not in {
            WorkaroundReceiptStatus.ATTEMPTED_SUCCEEDED,
            WorkaroundReceiptStatus.ATTEMPTED_FAILED,
        }:
            raise ValueError("execution_not_attempted")
        manifest = self.get(receipt.manifest_identity)
        if receipt.manifest_identity not in granted:
            raise PermissionError("workaround_not_granted")
        if (
            manifest.approval_policy is WorkaroundApprovalPolicy.HOST_APPROVAL
            and not approved
        ):
            raise PermissionError("workaround_approval_required")
        if receipt.manifest_version != manifest.version:
            raise ValueError("manifest_version_mismatch")
        if receipt.input_fingerprint != task.input_fingerprint:
            raise ValueError("input_fingerprint_mismatch")
        if (
            manifest.input_kind is not task.input_kind
            or manifest.output_kind is not task.output_kind
        ):
            raise ValueError("task_kind_mismatch")
        return receipt


__all__ = [
    "WorkaroundApprovalPolicy",
    "WorkaroundEffect",
    "WorkaroundExecutionReceipt",
    "WorkaroundInputKind",
    "WorkaroundManifest",
    "WorkaroundOutputKind",
    "WorkaroundReceiptStatus",
    "WorkaroundRegistry",
    "WorkaroundTask",
]
