from __future__ import annotations

from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from study_agent.api.sources import (
    BlobRef,
    SourceRevision,
    SourceRevisionRef,
    SubstrateRef,
    TextCitationV2,
)
from study_agent.domain import SourceKind, substrate_id_for
from study_agent.ingestion.identity import CHUNKER_POLICY_VERSION, revision_id_for
from tests.support.pf05 import (
    BYTES,
    SOURCE_ID,
    make_blob,
    make_source_revision,
    make_substrate_ref,
)


def test_public_source_values_are_frozen_and_importable_from_the_sources_facade() -> None:
    assert BlobRef.__name__ == "BlobRef"
    assert SourceRevision.__name__ == "SourceRevision"
    assert SourceRevisionRef.__name__ == "SourceRevisionRef"
    assert SubstrateRef.__name__ == "SubstrateRef"
    assert TextCitationV2.__name__ == "TextCitationV2"
    assert all(
        value.__dataclass_params__.frozen
        for value in (BlobRef, SourceRevision, SourceRevisionRef, SubstrateRef, TextCitationV2)
    )


def test_raw_blob_normalized_substrate_and_revision_keep_distinct_identities() -> None:
    raw = "Cafe\u0301 myocardium\r\n".encode("utf-8")
    normalized = "Café myocardium\n".encode()
    raw_blob = make_blob(raw)
    normalized_blob = make_blob(normalized)
    raw_substrate = make_substrate_ref(raw)
    normalized_substrate = make_substrate_ref(normalized)

    assert raw_blob != normalized_blob
    assert raw_blob.id != normalized_blob.id
    assert raw_substrate.substrate_id != normalized_substrate.substrate_id
    assert raw_substrate.blob != normalized_substrate.blob

    revision = make_source_revision(content=raw, normalized=normalized)
    assert revision.blob == raw_blob
    assert revision.normalized_substrate_id == normalized_substrate.substrate_id
    assert revision.blob != normalized_blob

    with pytest.raises(FrozenInstanceError):
        revision.media_type = "mutated"  # type: ignore[misc]


def test_revision_identity_reuses_equal_bytes_and_changes_for_new_bytes() -> None:
    kwargs = {
        "source_id": SOURCE_ID,
        "kind": SourceKind.MARKDOWN,
        "title": "PF05 notes",
        "trust_level": 90,
        "source_role": "primary",
        "normalization_version": "utf8-newlines-nfc-v1",
        "chunker_version": CHUNKER_POLICY_VERSION,
        "max_characters": 1200,
    }
    first = revision_id_for(original_sha256=sha256(BYTES).hexdigest(), **kwargs)
    retry = revision_id_for(original_sha256=sha256(BYTES).hexdigest(), **kwargs)
    changed = revision_id_for(
        original_sha256=sha256(BYTES + b" changed").hexdigest(), **kwargs
    )

    assert first == retry
    assert changed != first


def test_substrate_identity_is_derived_from_normalized_canonical_bytes() -> None:
    substrate = make_substrate_ref()

    assert substrate.substrate_id == substrate_id_for(BYTES)
    assert substrate.blob.checksum_sha256 == sha256(BYTES).hexdigest()
    assert substrate.blob.byte_length == len(BYTES)
    assert substrate.normalized_character_length == len(BYTES.decode("utf-8"))


def test_source_revision_ref_keeps_logical_source_and_revision_identity_explicit() -> None:
    revision = make_source_revision()
    reference = SourceRevisionRef(revision.source_id, revision.revision_id)

    assert reference.source_id == SOURCE_ID
    assert reference.revision_id == revision.revision_id
    assert revision.ref == reference
    assert revision.normalized_substrate_id == substrate_id_for(BYTES)


def test_source_revision_creation_reuses_equal_manifest_and_changes_for_new_bytes() -> None:
    first = make_source_revision(metadata={"role": "primary"})
    retry = make_source_revision(metadata={"role": "primary"})
    changed = make_source_revision(content=BYTES + b" changed", metadata={"role": "primary"})

    assert first.revision_id == retry.revision_id
    assert changed.revision_id != first.revision_id
    assert first.to_json() == retry.to_json()
    assert SourceRevision.from_json(first.to_json()) == first


def test_source_revision_json_rejects_a_forged_immutable_manifest() -> None:
    revision = make_source_revision(metadata={"role": "primary"})
    forged = dict(revision.to_json())
    forged["metadata"] = {"role": "forged"}

    with pytest.raises(ValueError, match="revision_id"):
        SourceRevision.from_json(forged)
