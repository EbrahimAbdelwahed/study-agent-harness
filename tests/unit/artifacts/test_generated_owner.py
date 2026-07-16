from __future__ import annotations

import json
from dataclasses import replace

import pytest

from study_agent.artifacts.generated_owner import (
    ExamGeneratedBatchOwnerReceipt,
    GeneratedBatchOwnerConflictError,
    GeneratedBatchOwnerRegistry,
    LessonGeneratedBatchOwnerReceipt,
    generated_batch_owner_from_bytes,
)
from study_agent.domain import RunId
from study_agent.state import canonical_json_bytes

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64


def _lesson() -> LessonGeneratedBatchOwnerReceipt:
    return LessonGeneratedBatchOwnerReceipt(
        child_run_id=RunId("child-run-1"),
        child_task_id="lesson-child:1",
        child_task_fingerprint=SHA_A,
        child_receipt_fingerprint=SHA_B,
        child_proof_fingerprint=SHA_C,
        lesson_run_id=RunId("lesson-run-1"),
        lesson_request_fingerprint=SHA_D,
        lesson_plan_fingerprint=SHA_E,
        lesson_profile_fingerprint=SHA_F,
        coordinator_fingerprint=SHA_A,
        page_position=1,
        bundle_order=("overview-1", "bundle-2"),
        bundle_id="bundle-2",
        bundle_fingerprint=SHA_B,
        wrapper_fingerprint=SHA_C,
        scope_fingerprint=SHA_D,
        read_set_fingerprint=SHA_E,
        revision_commitments_fingerprint=SHA_F,
        associated_overview_bundle_id="overview-1",
        overview_association_fingerprint=SHA_A,
    )


def _exam() -> ExamGeneratedBatchOwnerReceipt:
    request = canonical_json_bytes(
        {"sample_revision_ids": ("revision-1", "revision-2"), "language": "it"}
    )
    return ExamGeneratedBatchOwnerReceipt.create(
        child_run_id=RunId("exam-child-1"),
        child_task_id="exam-task:1",
        child_task_fingerprint=SHA_A,
        child_receipt_fingerprint=SHA_B,
        child_proof_fingerprint=SHA_C,
        request_bytes=request,
        opaque_request_key_fingerprint=SHA_D,
        scope_fingerprint=SHA_E,
        projection_fingerprint=SHA_F,
        evidence_mapping_fingerprint=SHA_A,
        coordinator_fingerprint=SHA_B,
    )


@pytest.mark.parametrize("receipt", (_lesson(), _exam()))
def test_owner_receipts_round_trip_canonical_bytes(receipt: object) -> None:
    assert isinstance(receipt, (LessonGeneratedBatchOwnerReceipt, ExamGeneratedBatchOwnerReceipt))
    assert generated_batch_owner_from_bytes(receipt.to_bytes()) == receipt
    assert len(receipt.fingerprint) == 64


def test_lesson_receipt_binds_canonical_page_order_and_association() -> None:
    with pytest.raises(ValueError, match="canonical page position"):
        replace(_lesson(), bundle_id="overview-1")
    with pytest.raises(ValueError, match="must precede"):
        replace(
            _lesson(),
            page_position=0,
            bundle_id="overview-1",
            associated_overview_bundle_id="bundle-2",
        )
    with pytest.raises(ValueError, match="both present or absent"):
        replace(_lesson(), overview_association_fingerprint=None)


def test_exam_receipt_binds_exact_canonical_request_bytes_without_raw_key() -> None:
    receipt = _exam()
    manifest = receipt.to_json()
    assert "opaque_request_key" not in manifest
    assert "opaque_request_key_fingerprint" in manifest
    with pytest.raises(ValueError, match="does not match"):
        replace(receipt, request_bytes_fingerprint=SHA_C)
    with pytest.raises(ValueError, match="canonical"):
        replace(receipt, request_bytes=b'{"language":"it", "sample_revision_ids":[] }')


def test_codec_rejects_unknown_fields_and_noncanonical_json() -> None:
    payload = json.loads(_lesson().to_bytes())
    payload["extra"] = True
    with pytest.raises(ValueError, match="fields must be exact"):
        generated_batch_owner_from_bytes(canonical_json_bytes(payload))
    with pytest.raises(ValueError, match="not canonical"):
        generated_batch_owner_from_bytes(b'{"kind": "lesson_page"}')


class _Store:
    def __init__(self) -> None:
        self.values: dict[RunId, bytes] = {}

    def create(self, child_run_id: RunId, payload: bytes) -> bool:
        if child_run_id in self.values:
            return False
        self.values[child_run_id] = payload
        return True

    def load(self, child_run_id: RunId) -> bytes:
        return self.values[child_run_id]


def test_registry_owns_one_exact_receipt_per_child_run() -> None:
    store = _Store()
    registry = GeneratedBatchOwnerRegistry(store)
    receipt = _lesson()

    assert registry.create(receipt) == receipt
    assert registry.create(receipt) == receipt
    assert registry.load(receipt.child_run_id) == receipt

    with pytest.raises(GeneratedBatchOwnerConflictError, match="another"):
        registry.create(replace(receipt, child_proof_fingerprint=SHA_D))


def test_registry_detects_slot_key_payload_mismatch() -> None:
    store = _Store()
    store.values[RunId("requested-run")] = _lesson().to_bytes()
    with pytest.raises(GeneratedBatchOwnerConflictError, match="identity changed"):
        GeneratedBatchOwnerRegistry(store).load(RunId("requested-run"))
