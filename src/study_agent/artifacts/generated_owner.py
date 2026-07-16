"""Canonical durable ownership receipts for generated artifact recovery."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any, cast

from study_agent.domain import RunId
from study_agent.domain._validation import JsonObject, JsonValue, freeze_json, freeze_object
from study_agent.ports.generated_owner import GeneratedBatchOwnerStore
from study_agent.state import canonical_json_bytes

MAX_GENERATED_OWNER_BYTES = 512 * 1024
MAX_EXAM_REQUEST_BYTES = 128 * 1024
MAX_LESSON_PAGES = 256

_OWNER_DOMAIN = b"generated-batch-owner@1\0"
_REQUEST_BYTES_DOMAIN = b"exam-analysis-request-bytes@1\0"
_PORTABLE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]*")


class GeneratedBatchOwnerKind(StrEnum):
    LESSON_PAGE = "lesson_page"
    EXAM_ANALYSIS = "exam_analysis"


@dataclass(frozen=True, slots=True)
class LessonGeneratedBatchOwnerReceipt:
    child_run_id: RunId
    child_task_id: str
    child_task_fingerprint: str
    child_receipt_fingerprint: str
    child_proof_fingerprint: str
    lesson_run_id: RunId
    lesson_request_fingerprint: str
    lesson_plan_fingerprint: str
    lesson_profile_fingerprint: str
    coordinator_fingerprint: str
    page_position: int
    bundle_order: tuple[str, ...]
    bundle_id: str
    bundle_fingerprint: str
    wrapper_fingerprint: str
    scope_fingerprint: str
    read_set_fingerprint: str
    revision_commitments_fingerprint: str
    associated_overview_bundle_id: str | None = None
    overview_association_fingerprint: str | None = None
    kind: GeneratedBatchOwnerKind = GeneratedBatchOwnerKind.LESSON_PAGE

    def __post_init__(self) -> None:
        _common(
            self.child_run_id,
            self.child_task_id,
            self.child_task_fingerprint,
            self.child_receipt_fingerprint,
            self.child_proof_fingerprint,
        )
        if not isinstance(self.lesson_run_id, RunId):
            raise TypeError("lesson_run_id must be RunId")
        for value, name in (
            (self.lesson_request_fingerprint, "lesson_request_fingerprint"),
            (self.lesson_plan_fingerprint, "lesson_plan_fingerprint"),
            (self.lesson_profile_fingerprint, "lesson_profile_fingerprint"),
            (self.coordinator_fingerprint, "coordinator_fingerprint"),
            (self.bundle_fingerprint, "bundle_fingerprint"),
            (self.wrapper_fingerprint, "wrapper_fingerprint"),
            (self.scope_fingerprint, "scope_fingerprint"),
            (self.read_set_fingerprint, "read_set_fingerprint"),
            (
                self.revision_commitments_fingerprint,
                "revision_commitments_fingerprint",
            ),
        ):
            _sha(value, name)
        order = tuple(self.bundle_order)
        if not 1 <= len(order) <= MAX_LESSON_PAGES:
            raise ValueError("bundle_order must contain 1..256 bundle ids")
        for item in order:
            _portable(item, "bundle_order item")
        if len(set(order)) != len(order):
            raise ValueError("bundle_order must be ordered and unique")
        if type(self.page_position) is not int or not 0 <= self.page_position < len(order):
            raise ValueError("page_position must select one canonical bundle")
        _portable(self.bundle_id, "bundle_id")
        if order[self.page_position] != self.bundle_id:
            raise ValueError("bundle_id does not match canonical page position")
        object.__setattr__(self, "bundle_order", order)
        association = self.associated_overview_bundle_id
        association_fingerprint = self.overview_association_fingerprint
        if (association is None) != (association_fingerprint is None):
            raise ValueError(
                "overview association id and fingerprint must be both present or absent"
            )
        if association is not None:
            _portable(association, "associated_overview_bundle_id")
            _sha(cast(str, association_fingerprint), "overview_association_fingerprint")
            if association not in order[: self.page_position]:
                raise ValueError("associated overview bundle must precede the selected page")
        if self.kind is not GeneratedBatchOwnerKind.LESSON_PAGE:
            raise ValueError("lesson owner receipt kind is invalid")

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_json())

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "kind": self.kind.value,
                "child_run_id": str(self.child_run_id),
                "child_task_id": self.child_task_id,
                "child_task_fingerprint": self.child_task_fingerprint,
                "child_receipt_fingerprint": self.child_receipt_fingerprint,
                "child_proof_fingerprint": self.child_proof_fingerprint,
                "lesson_run_id": str(self.lesson_run_id),
                "lesson_request_fingerprint": self.lesson_request_fingerprint,
                "lesson_plan_fingerprint": self.lesson_plan_fingerprint,
                "lesson_profile_fingerprint": self.lesson_profile_fingerprint,
                "coordinator_fingerprint": self.coordinator_fingerprint,
                "page_position": self.page_position,
                "bundle_order": self.bundle_order,
                "bundle_id": self.bundle_id,
                "bundle_fingerprint": self.bundle_fingerprint,
                "wrapper_fingerprint": self.wrapper_fingerprint,
                "scope_fingerprint": self.scope_fingerprint,
                "read_set_fingerprint": self.read_set_fingerprint,
                "revision_commitments_fingerprint": self.revision_commitments_fingerprint,
                "associated_overview_bundle_id": self.associated_overview_bundle_id,
                "overview_association_fingerprint": self.overview_association_fingerprint,
            }
        )

    def to_bytes(self) -> bytes:
        return _bounded_bytes(self.to_json())


@dataclass(frozen=True, slots=True)
class ExamGeneratedBatchOwnerReceipt:
    child_run_id: RunId
    child_task_id: str
    child_task_fingerprint: str
    child_receipt_fingerprint: str
    child_proof_fingerprint: str
    request_bytes: bytes
    request_bytes_fingerprint: str
    opaque_request_key_fingerprint: str
    scope_fingerprint: str
    projection_fingerprint: str
    evidence_mapping_fingerprint: str
    coordinator_fingerprint: str
    kind: GeneratedBatchOwnerKind = GeneratedBatchOwnerKind.EXAM_ANALYSIS

    def __post_init__(self) -> None:
        _common(
            self.child_run_id,
            self.child_task_id,
            self.child_task_fingerprint,
            self.child_receipt_fingerprint,
            self.child_proof_fingerprint,
        )
        if not isinstance(self.request_bytes, bytes):
            raise TypeError("request_bytes must be bytes")
        if not 1 <= len(self.request_bytes) <= MAX_EXAM_REQUEST_BYTES:
            raise ValueError("request_bytes must contain 1..128 KiB")
        _canonical_exam_request_bytes(self.request_bytes)
        expected = sha256(_REQUEST_BYTES_DOMAIN + self.request_bytes).hexdigest()
        if self.request_bytes_fingerprint != expected:
            raise ValueError("request_bytes_fingerprint does not match request_bytes")
        for value, name in (
            (self.opaque_request_key_fingerprint, "opaque_request_key_fingerprint"),
            (self.scope_fingerprint, "scope_fingerprint"),
            (self.projection_fingerprint, "projection_fingerprint"),
            (self.evidence_mapping_fingerprint, "evidence_mapping_fingerprint"),
            (self.coordinator_fingerprint, "coordinator_fingerprint"),
        ):
            _sha(value, name)
        if self.kind is not GeneratedBatchOwnerKind.EXAM_ANALYSIS:
            raise ValueError("exam owner receipt kind is invalid")

    @classmethod
    def create(
        cls,
        *,
        child_run_id: RunId,
        child_task_id: str,
        child_task_fingerprint: str,
        child_receipt_fingerprint: str,
        child_proof_fingerprint: str,
        request_bytes: bytes,
        opaque_request_key_fingerprint: str,
        scope_fingerprint: str,
        projection_fingerprint: str,
        evidence_mapping_fingerprint: str,
        coordinator_fingerprint: str,
    ) -> ExamGeneratedBatchOwnerReceipt:
        return cls(
            child_run_id,
            child_task_id,
            child_task_fingerprint,
            child_receipt_fingerprint,
            child_proof_fingerprint,
            request_bytes,
            sha256(_REQUEST_BYTES_DOMAIN + request_bytes).hexdigest(),
            opaque_request_key_fingerprint,
            scope_fingerprint,
            projection_fingerprint,
            evidence_mapping_fingerprint,
            coordinator_fingerprint,
        )

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_json())

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "kind": self.kind.value,
                "child_run_id": str(self.child_run_id),
                "child_task_id": self.child_task_id,
                "child_task_fingerprint": self.child_task_fingerprint,
                "child_receipt_fingerprint": self.child_receipt_fingerprint,
                "child_proof_fingerprint": self.child_proof_fingerprint,
                "request_bytes": base64.b64encode(self.request_bytes).decode("ascii"),
                "request_bytes_fingerprint": self.request_bytes_fingerprint,
                "opaque_request_key_fingerprint": self.opaque_request_key_fingerprint,
                "scope_fingerprint": self.scope_fingerprint,
                "projection_fingerprint": self.projection_fingerprint,
                "evidence_mapping_fingerprint": self.evidence_mapping_fingerprint,
                "coordinator_fingerprint": self.coordinator_fingerprint,
            }
        )

    def to_bytes(self) -> bytes:
        return _bounded_bytes(self.to_json())


type GeneratedBatchOwnerReceipt = LessonGeneratedBatchOwnerReceipt | ExamGeneratedBatchOwnerReceipt


class GeneratedBatchOwnerConflictError(RuntimeError):
    """A child run is already bound to another generated batch owner."""


class GeneratedBatchOwnerRegistry:
    """Own the one canonical owner receipt permitted for each child run."""

    def __init__(self, store: GeneratedBatchOwnerStore) -> None:
        self._store = store

    def create(self, receipt: GeneratedBatchOwnerReceipt) -> GeneratedBatchOwnerReceipt:
        if not isinstance(
            receipt, (LessonGeneratedBatchOwnerReceipt, ExamGeneratedBatchOwnerReceipt)
        ):
            raise TypeError("generated owner receipt is invalid")
        payload = receipt.to_bytes()
        if self._store.create(receipt.child_run_id, payload):
            return receipt
        existing = generated_batch_owner_from_bytes(self._store.load(receipt.child_run_id))
        if existing.to_bytes() != payload:
            raise GeneratedBatchOwnerConflictError(
                "child run already belongs to another generated batch owner"
            )
        return existing

    def load(self, child_run_id: RunId) -> GeneratedBatchOwnerReceipt:
        if not isinstance(child_run_id, RunId):
            raise TypeError("child_run_id must be RunId")
        receipt = generated_batch_owner_from_bytes(self._store.load(child_run_id))
        if receipt.child_run_id != child_run_id:
            raise GeneratedBatchOwnerConflictError("owner slot child run identity changed")
        return receipt


def generated_batch_owner_from_bytes(data: bytes) -> GeneratedBatchOwnerReceipt:
    value = _decode(data)
    kind = value.get("kind")
    if kind == GeneratedBatchOwnerKind.LESSON_PAGE.value:
        _exact(value, _LESSON_FIELDS, "lesson generated owner")
        receipt: GeneratedBatchOwnerReceipt = LessonGeneratedBatchOwnerReceipt(
            child_run_id=RunId(_string(value, "child_run_id")),
            child_task_id=_string(value, "child_task_id"),
            child_task_fingerprint=_string(value, "child_task_fingerprint"),
            child_receipt_fingerprint=_string(value, "child_receipt_fingerprint"),
            child_proof_fingerprint=_string(value, "child_proof_fingerprint"),
            lesson_run_id=RunId(_string(value, "lesson_run_id")),
            lesson_request_fingerprint=_string(value, "lesson_request_fingerprint"),
            lesson_plan_fingerprint=_string(value, "lesson_plan_fingerprint"),
            lesson_profile_fingerprint=_string(value, "lesson_profile_fingerprint"),
            coordinator_fingerprint=_string(value, "coordinator_fingerprint"),
            page_position=_integer(value, "page_position"),
            bundle_order=_strings(value, "bundle_order"),
            bundle_id=_string(value, "bundle_id"),
            bundle_fingerprint=_string(value, "bundle_fingerprint"),
            wrapper_fingerprint=_string(value, "wrapper_fingerprint"),
            scope_fingerprint=_string(value, "scope_fingerprint"),
            read_set_fingerprint=_string(value, "read_set_fingerprint"),
            revision_commitments_fingerprint=_string(value, "revision_commitments_fingerprint"),
            associated_overview_bundle_id=_optional_string(value, "associated_overview_bundle_id"),
            overview_association_fingerprint=_optional_string(
                value, "overview_association_fingerprint"
            ),
        )
    elif kind == GeneratedBatchOwnerKind.EXAM_ANALYSIS.value:
        _exact(value, _EXAM_FIELDS, "exam generated owner")
        receipt = ExamGeneratedBatchOwnerReceipt(
            child_run_id=RunId(_string(value, "child_run_id")),
            child_task_id=_string(value, "child_task_id"),
            child_task_fingerprint=_string(value, "child_task_fingerprint"),
            child_receipt_fingerprint=_string(value, "child_receipt_fingerprint"),
            child_proof_fingerprint=_string(value, "child_proof_fingerprint"),
            request_bytes=_base64(value, "request_bytes"),
            request_bytes_fingerprint=_string(value, "request_bytes_fingerprint"),
            opaque_request_key_fingerprint=_string(value, "opaque_request_key_fingerprint"),
            scope_fingerprint=_string(value, "scope_fingerprint"),
            projection_fingerprint=_string(value, "projection_fingerprint"),
            evidence_mapping_fingerprint=_string(value, "evidence_mapping_fingerprint"),
            coordinator_fingerprint=_string(value, "coordinator_fingerprint"),
        )
    else:
        raise ValueError("generated owner kind is unsupported")
    if receipt.to_bytes() != data:
        raise ValueError("generated owner bytes are not canonical")
    return receipt


_COMMON_FIELDS = {
    "kind",
    "child_run_id",
    "child_task_id",
    "child_task_fingerprint",
    "child_receipt_fingerprint",
    "child_proof_fingerprint",
}
_LESSON_FIELDS = _COMMON_FIELDS | {
    "lesson_run_id",
    "lesson_request_fingerprint",
    "lesson_plan_fingerprint",
    "lesson_profile_fingerprint",
    "coordinator_fingerprint",
    "page_position",
    "bundle_order",
    "bundle_id",
    "bundle_fingerprint",
    "wrapper_fingerprint",
    "scope_fingerprint",
    "read_set_fingerprint",
    "revision_commitments_fingerprint",
    "associated_overview_bundle_id",
    "overview_association_fingerprint",
}
_EXAM_FIELDS = _COMMON_FIELDS | {
    "request_bytes",
    "request_bytes_fingerprint",
    "opaque_request_key_fingerprint",
    "scope_fingerprint",
    "projection_fingerprint",
    "evidence_mapping_fingerprint",
    "coordinator_fingerprint",
}


def _common(run_id: RunId, task_id: str, *fingerprints: str) -> None:
    if not isinstance(run_id, RunId):
        raise TypeError("child_run_id must be RunId")
    _portable(task_id, "child_task_id")
    for value, name in zip(
        fingerprints,
        (
            "child_task_fingerprint",
            "child_receipt_fingerprint",
            "child_proof_fingerprint",
        ),
        strict=True,
    ):
        _sha(value, name)


def _canonical_exam_request_bytes(data: bytes) -> None:
    value = _decode(data)
    _exact(value, {"sample_revision_ids", "language"}, "exam analysis request")
    revisions = value["sample_revision_ids"]
    language = value["language"]
    if (
        not isinstance(revisions, tuple)
        or not 1 <= len(revisions) <= 16
        or not all(isinstance(item, str) and item for item in revisions)
        or len(set(revisions)) != len(revisions)
        or not isinstance(language, str)
        or not language
        or language != language.strip()
    ):
        raise ValueError("exam analysis request bytes are structurally invalid")


def _fingerprint(value: JsonObject) -> str:
    return sha256(_OWNER_DOMAIN + canonical_json_bytes(value)).hexdigest()


def _bounded_bytes(value: JsonObject) -> bytes:
    data = canonical_json_bytes(value)
    if len(data) > MAX_GENERATED_OWNER_BYTES:
        raise ValueError("generated owner receipt exceeds 512 KiB")
    return data


def _decode(data: bytes) -> JsonObject:
    if not isinstance(data, bytes):
        raise TypeError("generated owner payload must be bytes")
    if not 1 <= len(data) <= MAX_GENERATED_OWNER_BYTES:
        raise ValueError("generated owner payload must contain 1..512 KiB")
    try:
        raw: Any = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("generated owner payload must be JSON") from error
    frozen = freeze_json(cast(JsonValue, raw))
    if not isinstance(frozen, Mapping):
        raise ValueError("generated owner payload must be an object")
    value = freeze_object(frozen)
    if canonical_json_bytes(value) != data:
        raise ValueError("generated owner payload bytes are not canonical")
    return value


def _portable(value: str, name: str) -> None:
    if not isinstance(value, str) or _PORTABLE.fullmatch(value) is None or len(value) > 256:
        raise ValueError(f"{name} must be bounded portable text")


def _sha(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256")


def _exact(value: Mapping[str, JsonValue], fields: set[str], name: str) -> None:
    if set(value) != fields:
        raise ValueError(f"{name} fields must be exact")


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        raise ValueError(f"{key} must be text")
    return item


def _optional_string(value: Mapping[str, JsonValue], key: str) -> str | None:
    item = value.get(key)
    if item is not None and not isinstance(item, str):
        raise ValueError(f"{key} must be text or null")
    return item


def _integer(value: Mapping[str, JsonValue], key: str) -> int:
    item = value.get(key)
    if type(item) is not int:
        raise ValueError(f"{key} must be an integer")
    return item


def _strings(value: Mapping[str, JsonValue], key: str) -> tuple[str, ...]:
    item = value.get(key)
    if not isinstance(item, tuple) or not all(isinstance(child, str) for child in item):
        raise ValueError(f"{key} must be an array of text")
    return cast(tuple[str, ...], item)


def _base64(value: Mapping[str, JsonValue], key: str) -> bytes:
    item = _string(value, key)
    try:
        decoded = base64.b64decode(item, validate=True)
    except ValueError as error:
        raise ValueError(f"{key} must be canonical base64") from error
    if base64.b64encode(decoded).decode("ascii") != item:
        raise ValueError(f"{key} must be canonical base64")
    return decoded


__all__ = [
    "ExamGeneratedBatchOwnerReceipt",
    "GeneratedBatchOwnerConflictError",
    "GeneratedBatchOwnerKind",
    "GeneratedBatchOwnerReceipt",
    "GeneratedBatchOwnerRegistry",
    "LessonGeneratedBatchOwnerReceipt",
    "generated_batch_owner_from_bytes",
]
