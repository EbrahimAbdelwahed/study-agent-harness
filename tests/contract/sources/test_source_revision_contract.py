from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from study_agent.api.sources import (
    BlobRef,
    SourceRevision,
    SourceRevisionRef,
    SubstrateRef,
    TextCitationV2,
)
from study_agent.domain import SourceId, substrate_id_for
from study_agent.domain.bounded_json import (
    MAX_BOUNDARY_DEPTH,
    MAX_BOUNDARY_ITEMS,
    MAX_BOUNDARY_NODES,
    MAX_BOUNDARY_STRING_BYTES,
    MAX_IDENTITY_INTEGER,
    MAX_METADATA_BYTES,
    MIN_IDENTITY_INTEGER,
    BoundedJsonError,
    canonical_json_bytes,
    decode_json_bytes,
    validate_json,
)
from study_agent.domain.source_identity import (
    SOURCE_REVISION_ID_NAMESPACE,
    SOURCE_REVISION_ID_PREFIX,
    source_revision_id_for,
    source_revision_manifest,
)
from tests.support.pf05 import (
    BYTES,
    SOURCE_ID,
    make_blob,
    make_source_revision,
    make_substrate_ref,
)


def _is_frozen_dataclass(value: object) -> bool:
    if not is_dataclass(value) or not isinstance(value, type):
        return False
    params = getattr(value, "__dataclass_params__", None)
    return bool(getattr(params, "frozen", False))


def _make_revision(
    *,
    source_id: SourceId = SOURCE_ID,
    content: bytes = BYTES,
    media_type: str = "text/markdown",
    normalization_version: str = "utf8-newlines-nfc-v1",
    normalized: bytes = BYTES,
    created_at: datetime = datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
    metadata: dict[str, object] | None = None,
) -> SourceRevision:
    return SourceRevision.create(
        source_id=source_id,
        content=content,
        media_type=media_type,
        created_at=created_at,
        normalization_version=normalization_version,
        substrate_id=make_substrate_ref(normalized).substrate_id,
        metadata=(
            {
                "kind": "markdown",
                "source_role": "primary",
                "title": "PF05 notes",
                "trust_level": 90,
            }
            if metadata is None
            else metadata
        ),
    )


def test_public_source_values_are_frozen_and_importable_from_the_sources_facade() -> None:
    assert BlobRef.__name__ == "BlobRef"
    assert SourceRevision.__name__ == "SourceRevision"
    assert SourceRevisionRef.__name__ == "SourceRevisionRef"
    assert SubstrateRef.__name__ == "SubstrateRef"
    assert TextCitationV2.__name__ == "TextCitationV2"
    assert all(
        _is_frozen_dataclass(value)
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
    first = make_source_revision(
        metadata={
            "kind": "markdown",
            "source_role": "primary",
            "title": "PF05 notes",
            "trust_level": 90,
        }
    )
    retry = make_source_revision(
        metadata={
            "kind": "markdown",
            "source_role": "primary",
            "title": "PF05 notes",
            "trust_level": 90,
        }
    )
    changed = make_source_revision(
        content=BYTES + b" changed",
        metadata={
            "kind": "markdown",
            "source_role": "primary",
            "title": "PF05 notes",
            "trust_level": 90,
        },
    )

    assert first == retry
    assert changed != first


@pytest.mark.parametrize(
    "change",
    [
        lambda: {"source_id": SourceId("other-source")},
        lambda: {"content": BYTES + b" changed"},
        lambda: {"media_type": "text/plain"},
        lambda: {"normalization_version": "utf8-newlines-nfc-v2"},
        lambda: {"normalized": BYTES + b" substrate"},
        lambda: {
            "metadata": {
                "kind": "markdown",
                "source_role": "secondary",
                "title": "PF05 notes",
                "trust_level": 90,
            }
        },
        lambda: {
            "metadata": {
                "kind": "markdown",
                "source_role": "primary",
                "title": "PF05 notes",
                "trust_level": 90,
                "opaque": "admitted",
            }
        },
    ],
)
def test_each_current_identity_input_changes_the_revision_id(
    change: object,
) -> None:
    base = _make_revision()
    changed = _make_revision(**change())  # type: ignore[arg-type]

    assert changed.revision_id != base.revision_id


def test_provenance_and_derived_policy_do_not_change_revision_identity() -> None:
    base = _make_revision()
    later = _make_revision(created_at=base.created_at + timedelta(days=1))

    assert later.revision_id == base.revision_id
    # Filenames and chunking are intentionally absent from SourceRevision's
    # closed manifest; the integration lane separately verifies rechunking.
    assert base.revision_id == _make_revision().revision_id


def test_public_and_ingestion_revision_ids_share_one_identity_domain_and_codec() -> None:
    revision = make_source_revision(
        metadata={
            "kind": "markdown",
            "source_role": "primary",
            "title": "PF05 notes",
            "trust_level": 90,
        }
    )
    manifest = source_revision_manifest(
        source_id=revision.source_id,
        blob=revision.blob,
        media_type=revision.media_type,
        normalization_version=revision.normalization_version,
        substrate_id=revision.substrate_id,
        metadata=revision.metadata,
    )

    assert SOURCE_REVISION_ID_NAMESPACE == b"study-agent/source-revision/v3\0"
    assert revision.revision_id == source_revision_id_for(manifest)
    assert str(make_source_revision().revision_id).startswith(SOURCE_REVISION_ID_PREFIX)


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
    assert SourceRevision.from_json(
        first.to_json(), receipt_created_at=first.created_at
    ) == first


def test_source_revision_json_rejects_a_forged_immutable_manifest() -> None:
    revision = make_source_revision(metadata={"role": "primary"})
    forged = dict(revision.to_json())
    forged["metadata"] = {"role": "forged"}

    with pytest.raises(ValueError, match="revision_id"):
        SourceRevision.from_json(forged, receipt_created_at=revision.created_at)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("media_type", "text/plain"),
        ("normalization_version", "future-normalization-v2"),
        ("substrate_id", "substrate:sha256:" + "0" * 64),
    ],
)
def test_source_revision_json_rejects_mutation_of_each_identity_field(
    field: str, value: str
) -> None:
    revision = make_source_revision()
    forged = dict(revision.to_json())
    forged[field] = value

    with pytest.raises(ValueError, match="revision_id"):
        SourceRevision.from_json(forged, receipt_created_at=revision.created_at)


def test_bounded_json_accepts_exact_limits_and_rejects_the_next_value() -> None:
    nested: object = None
    for _ in range(MAX_BOUNDARY_DEPTH):
        nested = [nested]
    validate_json(nested)
    with pytest.raises(BoundedJsonError):
        validate_json([nested])

    exact_nodes = [[None] * 50 for _ in range(5)]
    assert MAX_BOUNDARY_NODES == 1 + 5 + 5 * 50
    validate_json(exact_nodes)
    over_nodes = [[None] * 50 for _ in range(5)]
    over_nodes[0].append(None)
    with pytest.raises(BoundedJsonError):
        validate_json(over_nodes)
    validate_json([None] * MAX_BOUNDARY_ITEMS)
    with pytest.raises(BoundedJsonError):
        validate_json([None] * (MAX_BOUNDARY_ITEMS + 1))
    validate_json("x" * MAX_BOUNDARY_STRING_BYTES)
    with pytest.raises(BoundedJsonError):
        validate_json("x" * (MAX_BOUNDARY_STRING_BYTES + 1))
    validate_json({"k" * MAX_BOUNDARY_STRING_BYTES: None})
    with pytest.raises(BoundedJsonError):
        validate_json({"k" * (MAX_BOUNDARY_STRING_BYTES + 1): None})

    metadata = {"values": ["x" * MAX_BOUNDARY_STRING_BYTES] * 15 + [""]}
    empty_last_size = len(canonical_json_bytes(metadata))
    exact_last_size = MAX_METADATA_BYTES - empty_last_size
    exact = {"values": ["x" * MAX_BOUNDARY_STRING_BYTES] * 15 + ["x" * exact_last_size]}
    assert len(canonical_json_bytes(exact, max_bytes=MAX_METADATA_BYTES)) == MAX_METADATA_BYTES
    with pytest.raises(BoundedJsonError):
        canonical_json_bytes(
            {"values": ["x" * MAX_BOUNDARY_STRING_BYTES] * 15 + ["x" * (exact_last_size + 1)]},
            max_bytes=MAX_METADATA_BYTES,
        )


def test_bounded_json_rejects_hostile_shapes_and_noncanonical_numbers() -> None:
    cycle: list[object] = []
    cycle.append(cycle)

    class CustomList(list[object]):
        pass

    with pytest.raises(BoundedJsonError):
        validate_json(cycle)
    with pytest.raises(BoundedJsonError):
        validate_json(CustomList([1]))
    with pytest.raises(BoundedJsonError):
        validate_json({1: "not a JSON object key"})
    with pytest.raises(BoundedJsonError):
        validate_json("\ud800")
    with pytest.raises(BoundedJsonError):
        decode_json_bytes(b'{"value":1,"value":2}', max_bytes=MAX_METADATA_BYTES)

    assert validate_json(MIN_IDENTITY_INTEGER) == MIN_IDENTITY_INTEGER
    assert validate_json(MAX_IDENTITY_INTEGER) == MAX_IDENTITY_INTEGER
    assert validate_json(True) is True
    assert validate_json(None) is None
    for number in (MIN_IDENTITY_INTEGER - 1, MAX_IDENTITY_INTEGER + 1):
        with pytest.raises(BoundedJsonError):
            validate_json(number)
    for number in (0.0, -0.0, 1.5, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(BoundedJsonError):
            validate_json(number)
    with pytest.raises(BoundedJsonError):
        decode_json_bytes(b"-0", max_bytes=MAX_METADATA_BYTES)
