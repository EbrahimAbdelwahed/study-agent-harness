from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import timedelta
from hashlib import sha256

import pytest

from study_agent.domain import (
    Actor,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
    substrate_production_event_id_for,
)
from study_agent.domain._validation import JsonValue
from study_agent.ingestion.substrate_events import (
    SOURCE_SUBSTRATE_PRODUCED,
    SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION,
    decode_source_substrate_produced,
    decode_source_substrate_produced_event,
    decode_substrate_produced_event,
    source_substrate_produced_payload,
    substrate_production_payload,
)
from tests.unit.knowledge.test_substrate_contracts import make_production

COURSE_ID = CourseId("course-kb-01")


def payload_mapping(event: DomainEvent, key: str) -> dict[str, JsonValue]:
    value = event.payload[key]
    assert isinstance(value, Mapping)
    return dict(value)


def integer(value: JsonValue) -> int:
    assert type(value) is int
    return value


def make_event(sequence: int = 1) -> tuple[DomainEvent, dict[str, bytes]]:
    receipt = make_production()
    occurred_at = receipt.produced_at + timedelta(seconds=sequence - 1)
    receipt = type(receipt)(
        receipt.substrate_production_id,
        receipt.source_id,
        receipt.original_blob,
        receipt.substrate,
        receipt.converter_name,
        receipt.converter_version,
        receipt.normalization_version,
        receipt.admission_policy_version,
        receipt.page_map_policy_version,
        occurred_at,
    )
    event = DomainEvent(
        substrate_production_event_id_for(
            COURSE_ID, receipt.substrate_production_id, sequence
        ),
        COURSE_ID,
        sequence,
        SOURCE_SUBSTRATE_PRODUCED,
        SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "substrate-test"),
        occurred_at,
        CorrelationId("correlation-kb-01"),
        substrate_production_payload(receipt),
    )
    blobs = {
        str(receipt.original_blob.id): b"source PDF bytes",
        str(receipt.substrate.blob.id): "Café\nheart valves".encode(),
    }
    return event, blobs


def test_event_codec_round_trip_verifies_event_identity_and_blob_bindings() -> None:
    event, blobs = make_event()
    decoded = decode_substrate_produced_event(event, lambda ref: blobs[str(ref.id)])
    assert decoded.substrate_production_id == make_production().substrate_production_id
    assert decoded.produced_at == event.occurred_at


def test_v1_and_v2_codec_names_are_symmetric() -> None:
    event, blobs = make_event()
    receipt = decode_substrate_produced_event(event, lambda ref: blobs[str(ref.id)])
    assert decode_source_substrate_produced(event.payload) == receipt
    assert decode_source_substrate_produced_event(
        event, lambda ref: blobs[str(ref.id)]
    ) == receipt
    assert source_substrate_produced_payload(receipt) == substrate_production_payload(receipt)


@pytest.mark.parametrize(
    "tamper",
    [
        lambda event: DomainEvent(
            EventId("event-forged"),
            event.course_id,
            event.course_sequence,
            event.event_type,
            event.schema_version,
            event.actor,
            event.occurred_at,
            event.correlation_id,
            event.payload,
        ),
        lambda event: DomainEvent(
            event.event_id,
            event.course_id,
            event.course_sequence,
            event.event_type,
            event.schema_version,
            event.actor,
            event.occurred_at + timedelta(seconds=1),
            event.correlation_id,
            event.payload,
        ),
        lambda event: DomainEvent(
            event.event_id,
            event.course_id,
            event.course_sequence,
            "source.substrate_produced",
            2,
            event.actor,
            event.occurred_at,
            event.correlation_id,
            event.payload,
        ),
    ],
)
def test_event_codec_rejects_forged_envelope_identity(
    tamper: Callable[[DomainEvent], DomainEvent],
) -> None:
    event, blobs = make_event()
    with pytest.raises(ValueError, match=r"event_id|occurred_at|envelope"):
        decode_substrate_produced_event(tamper(event), lambda ref: blobs[str(ref.id)])


def test_event_codec_rejects_corrupt_or_orphan_blob() -> None:
    event, blobs = make_event()
    substrate_binding = payload_mapping(event, "substrate")["blob"]
    assert isinstance(substrate_binding, Mapping)
    substrate_blob_id = str(substrate_binding["id"])
    with pytest.raises(ValueError, match=r"checksum|byte length"):
        decode_substrate_produced_event(
            event,
            lambda ref: (
                b"corrupt"
                if str(ref.id) == substrate_blob_id
                else blobs[str(ref.id)]
            ),
        )
    with pytest.raises(KeyError):
        decode_substrate_produced_event(event, lambda ref: blobs["missing"])


def test_event_codec_rejects_canonical_bytes_or_character_length_corruption() -> None:
    event, blobs = make_event()
    substrate = payload_mapping(event, "substrate")
    substrate_blob = substrate["blob"]
    assert isinstance(substrate_blob, Mapping)
    substrate_blob = dict(substrate_blob)
    substrate_blob["byte_length"] = integer(substrate_blob["byte_length"]) + 1
    substrate["blob"] = substrate_blob
    forged_bytes = DomainEvent(
        event.event_id,
        event.course_id,
        event.course_sequence,
        event.event_type,
        event.schema_version,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        {**event.payload, "substrate": substrate},
    )
    with pytest.raises(ValueError, match=r"production id|byte length"):
        decode_substrate_produced_event(forged_bytes, lambda ref: blobs[str(ref.id)])

    original_substrate = payload_mapping(event, "substrate")
    original_substrate["normalized_character_length"] = (
        integer(original_substrate["normalized_character_length"]) + 1
    )
    forged_length = DomainEvent(
        event.event_id,
        event.course_id,
        event.course_sequence,
        event.event_type,
        event.schema_version,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        {**event.payload, "substrate": original_substrate},
    )
    with pytest.raises(ValueError, match="character length"):
        decode_substrate_produced_event(forged_length, lambda ref: blobs[str(ref.id)])


def test_codec_rejects_page_map_with_duplicate_or_descending_entries() -> None:
    event, blobs = make_event()
    substrate = payload_mapping(event, "substrate")
    substrate["page_count"] = 3
    substrate["page_map"] = (
        {"offset": 0, "page": 1},
        {"offset": 0, "page": 2},
    )
    forged = DomainEvent(
        event.event_id,
        event.course_id,
        event.course_sequence,
        event.event_type,
        event.schema_version,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        {**event.payload, "substrate": substrate},
    )
    with pytest.raises(ValueError, match="offsets"):
        decode_substrate_produced_event(forged, lambda ref: blobs[str(ref.id)])


def test_codec_rejects_forged_original_blob_checksum_even_when_id_is_changed() -> None:
    event, blobs = make_event()
    original = payload_mapping(event, "original_blob")
    checksum = sha256(b"different").hexdigest()
    original["checksum_sha256"] = checksum
    original["id"] = f"sha256:{checksum}"
    forged = DomainEvent(
        event.event_id,
        event.course_id,
        event.course_sequence,
        event.event_type,
        event.schema_version,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        {**event.payload, "original_blob": original},
    )
    with pytest.raises(ValueError, match=r"checksum|metadata|immutable receipt"):
        decode_substrate_produced_event(forged, lambda ref: blobs[str(ref.id)])
