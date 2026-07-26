from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast

import pytest

from study_agent.domain import (
    BlobId,
    BlobRef,
    SourceId,
    Substrate,
    SubstrateProduction,
    SubstrateProductionId,
    substrate_id_for,
    substrate_production_id_for,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.substrate import PageMapEntry, validate_page_map
from study_agent.ingestion.substrate_events import (
    decode_substrate_production,
    substrate_production_payload,
)
from study_agent.state.serialization import canonical_json_bytes

NORMALIZED = "Café\nheart valves".encode()
ORIGINAL = b"source PDF bytes"
SOURCE_ID = SourceId("source-cardiac")
NORMALIZATION_VERSION = "utf8-newlines-nfc-v1"


def blob_ref(content: bytes) -> BlobRef:
    digest = sha256(content).hexdigest()
    return BlobRef(BlobId(f"sha256:{digest}"), digest, len(content))


def make_production(
    *,
    converter_version: str = "pdf-to-md-1",
    admission_policy_version: str = "admission-1",
    page_map_policy_version: str = "page-map-1",
    page_count: int | None = None,
    page_map: tuple[PageMapEntry, ...] = (),
    produced_at: datetime = datetime(2026, 7, 26, 20, 0, tzinfo=UTC),
) -> SubstrateProduction:
    substrate_blob = blob_ref(NORMALIZED)
    substrate_id = substrate_id_for(NORMALIZED)
    production_id = substrate_production_id_for(
        source_id=SOURCE_ID,
        original_blob_id=str(blob_ref(ORIGINAL).id),
        original_blob_sha256=blob_ref(ORIGINAL).checksum_sha256,
        original_blob_byte_length=len(ORIGINAL),
        substrate_id=substrate_id,
        converter_name="pdf-to-markdown",
        converter_version=converter_version,
        normalization_version=NORMALIZATION_VERSION,
        page_map_policy_version=page_map_policy_version,
        page_count=page_count,
        page_map=tuple(entry.to_json() for entry in page_map),
        admission_policy_version=admission_policy_version,
        character_length=len(NORMALIZED.decode("utf-8")),
    )
    substrate = Substrate(
        substrate_id,
        substrate_blob,
        len(NORMALIZED.decode("utf-8")),
        NORMALIZATION_VERSION,
        page_count,
        page_map,
    )
    return SubstrateProduction(
        production_id,
        SOURCE_ID,
        blob_ref(ORIGINAL),
        substrate,
        "pdf-to-markdown",
        converter_version,
        NORMALIZATION_VERSION,
        admission_policy_version,
        page_map_policy_version,
        produced_at,
    )


def test_substrate_and_production_golden_identities_are_domain_separated() -> None:
    substrate = substrate_id_for(NORMALIZED)
    assert str(substrate) == f"substrate:sha256:{sha256(NORMALIZED).hexdigest()}"
    assert substrate.value.startswith("substrate:sha256:")

    production = make_production()
    identity = cast(JsonObject, {
        "admission_policy_version": "admission-1",
        "converter_name": "pdf-to-markdown",
        "converter_version": "pdf-to-md-1",
        "normalization_version": NORMALIZATION_VERSION,
        "original_blob": {
            "byte_length": len(ORIGINAL),
            "checksum_sha256": sha256(ORIGINAL).hexdigest(),
            "id": f"sha256:{sha256(ORIGINAL).hexdigest()}",
        },
        "page_count": None,
        "page_map_policy_version": "page-map-1",
        "page_map": (),
        "source_id": str(SOURCE_ID),
        "substrate_id": str(substrate),
    })
    expected = sha256(
        b"study-agent/substrate-production/v1\0" + canonical_json_bytes(identity)
    ).hexdigest()
    assert str(production.substrate_production_id) == f"substrate-production:sha256:{expected}"
    assert production.substrate_production_id != SubstrateProductionId(
        f"substrate-production:sha256:{sha256(canonical_json_bytes(identity)).hexdigest()}"
    )


def test_page_map_policy_version_is_identity_bearing_but_substrate_is_bytes_only() -> None:
    first = make_production(page_map_policy_version="page-map-1")
    changed = make_production(page_map_policy_version="page-map-2")
    assert first.substrate.substrate_id == changed.substrate.substrate_id
    assert first.substrate_production_id != changed.substrate_production_id


@pytest.mark.parametrize(
    "value",
    [b"", b"\xff", b"\xc3("],
)
def test_substrate_identity_rejects_empty_and_invalid_utf8(value: bytes) -> None:
    with pytest.raises(ValueError, match=r"non-empty|valid UTF-8"):
        substrate_id_for(value)


@pytest.mark.parametrize(
    ("page_count", "page_map", "message"),
    [
        (None, (PageMapEntry(0, 1),), "empty when page_count is absent"),
        (1, (), "cannot be empty"),
        (0, (PageMapEntry(0, 1),), "positive"),
        (2, (PageMapEntry(1, 1),), "offset zero"),
        (2, (PageMapEntry(0, 1), PageMapEntry(0, 2)), "offsets"),
        (2, (PageMapEntry(0, 1), PageMapEntry(2, 1)), "pages"),
        (2, (PageMapEntry(0, 1), PageMapEntry(9, 2)), "bounds"),
        (1, (PageMapEntry(0, 2),), "exceeds"),
        (2, (PageMapEntry(0, 1), PageMapEntry(2, 3)), "exceeds"),
    ],
)
def test_page_map_rejects_malformed_boundaries(
    page_count: int | None,
    page_map: tuple[PageMapEntry, ...],
    message: str,
) -> None:
    with pytest.raises((ValueError, TypeError), match=message):
        validate_page_map(page_count, page_map, character_length=9)


def test_page_map_accepts_absent_or_strictly_ordered_present_mapping() -> None:
    assert validate_page_map(None, (), 9) == ()
    expected = (PageMapEntry(0, 1), PageMapEntry(4, 2), PageMapEntry(8, 3))
    assert validate_page_map(3, expected, 9) == expected


def test_page_map_entry_rejects_negative_offsets_and_pages() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        PageMapEntry(-1, 1)
    with pytest.raises(ValueError, match="positive"):
        PageMapEntry(0, 0)


@pytest.mark.parametrize(
    "page_map",
    [
        ({"offset": 0, "page": 1, "extra": "forged"},),
        ({"offset": 0},),
        ({"offset": True, "page": 1},),
        ({"offset": 0, "page": True},),
        ({"offset": 2, "page": 1}, {"offset": 1, "page": 2}),
        ({"offset": 0, "page": 2}, {"offset": 1, "page": 1}),
        ({"offset": 0, "page": 1}, {"offset": 100, "page": 2}),
        ({"offset": 0, "page": 3},),
    ],
)
def test_production_identity_rejects_malformed_page_map(
    page_map: tuple[Mapping[str, object], ...],
) -> None:
    with pytest.raises(ValueError):
        substrate_production_id_for(
            source_id=SOURCE_ID,
            original_blob_id=str(blob_ref(ORIGINAL).id),
            original_blob_sha256=blob_ref(ORIGINAL).checksum_sha256,
            original_blob_byte_length=len(ORIGINAL),
            substrate_id=substrate_id_for(NORMALIZED),
            converter_name="pdf-to-markdown",
            converter_version="pdf-to-md-1",
            normalization_version=NORMALIZATION_VERSION,
            page_map_policy_version="page-map-1",
            page_count=2,
            page_map=page_map,
            admission_policy_version="admission-1",
            character_length=len(NORMALIZED.decode()),
        )


def test_production_identity_requires_character_length_for_pagination() -> None:
    with pytest.raises(ValueError, match="character_length is required"):
        substrate_production_id_for(
            source_id=SOURCE_ID,
            original_blob_id=str(blob_ref(ORIGINAL).id),
            original_blob_sha256=blob_ref(ORIGINAL).checksum_sha256,
            original_blob_byte_length=len(ORIGINAL),
            substrate_id=substrate_id_for(NORMALIZED),
            converter_name="pdf-to-markdown",
            converter_version="pdf-to-md-1",
            normalization_version=NORMALIZATION_VERSION,
            page_map_policy_version="page-map-1",
            page_count=1,
            page_map=({"offset": 0, "page": 1},),
            admission_policy_version="admission-1",
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("normalized_character_length", True),
        ("normalized_character_length", -1),
        ("substrate_id", "substrate:sha256:" + "0" * 64),
    ],
)
def test_strict_decoder_rejects_bool_or_forged_identity(
    field: str, replacement: JsonValue
) -> None:
    payload = substrate_production_payload(make_production())
    if field == "substrate_id":
        substrate_value = payload["substrate"]
        assert isinstance(substrate_value, Mapping)
        substrate = dict(substrate_value)
        substrate[field] = replacement
        payload = {**payload, "substrate": substrate}
    else:
        substrate_value = payload["substrate"]
        assert isinstance(substrate_value, Mapping)
        substrate = dict(substrate_value)
        substrate[field] = replacement
        payload = {**payload, "substrate": substrate}
    with pytest.raises(
        ValueError, match=r"integer|positive|does not match|exact substrate"
    ):
        decode_substrate_production(payload)


@pytest.mark.parametrize("location", ["top", "substrate", "original_blob"])
def test_strict_decoder_rejects_missing_and_extra_fields(location: str) -> None:
    payload = substrate_production_payload(make_production())
    if location == "top":
        changed = dict(payload)
        changed.pop("source_id")
        changed["unexpected"] = "x"
        payload = changed
    elif location == "substrate":
        changed = dict(payload["substrate"])  # type: ignore[arg-type]
        changed.pop("page_map")
        changed["unexpected"] = "x"
        payload = {**payload, "substrate": changed}
    else:
        changed = dict(payload["original_blob"])  # type: ignore[arg-type]
        changed["unexpected"] = "x"
        payload = {**payload, "original_blob": changed}
    with pytest.raises(ValueError, match="fields mismatch"):
        decode_substrate_production(payload)


def test_strict_decoder_rejects_invalid_timestamp_and_blob_binding() -> None:
    payload = substrate_production_payload(make_production())
    with pytest.raises(ValueError, match=r"timezone-aware|ISO-8601"):
        decode_substrate_production({**payload, "produced_at": "2026-07-26T20:00:00"})
    original_blob = payload["original_blob"]
    assert isinstance(original_blob, Mapping)
    forged_blob = dict(original_blob)
    forged_blob["checksum_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="id must match"):
        decode_substrate_production({**payload, "original_blob": forged_blob})
