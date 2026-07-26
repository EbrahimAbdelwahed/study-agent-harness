"""Strict codec and event-envelope validation for substrate productions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from hashlib import sha256

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.events import DomainEvent, PrincipalKind
from study_agent.domain.identifiers import (
    BlobId,
    SourceId,
    SubstrateId,
    SubstrateProductionId,
    substrate_id_for,
    substrate_production_event_id_for,
)
from study_agent.domain.source import BlobRef
from study_agent.domain.substrate import PageMapEntry, Substrate, SubstrateProduction
from study_agent.ingestion.normalization import InvalidUtf8Error, normalize_utf8

SOURCE_SUBSTRATE_PRODUCED = "source.substrate_produced"
SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION = 1
SUBSTRATE_PRODUCED = SOURCE_SUBSTRATE_PRODUCED
SUBSTRATE_PRODUCED_SCHEMA_VERSION = SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION

type BlobLoader = Callable[[BlobRef], bytes]

_TOP_LEVEL_KEYS = frozenset(
    {
        "admission_policy_version",
        "converter_name",
        "converter_version",
        "original_blob",
        "page_map_policy_version",
        "produced_at",
        "source_id",
        "substrate",
        "substrate_production_id",
    }
)
_SUBSTRATE_KEYS = frozenset(
    {
        "blob",
        "normalization_version",
        "normalized_character_length",
        "page_count",
        "page_map",
        "substrate_id",
    }
)
_BLOB_KEYS = frozenset({"byte_length", "checksum_sha256", "id"})
_PAGE_KEYS = frozenset({"offset", "page"})


def substrate_production_payload(receipt: SubstrateProduction) -> JsonObject:
    """Return the exact canonical event payload for one receipt."""
    if not isinstance(receipt, SubstrateProduction):
        raise TypeError("substrate production payload requires SubstrateProduction")
    return receipt.to_json()


def source_substrate_produced_payload(receipt: SubstrateProduction) -> JsonObject:
    return substrate_production_payload(receipt)


def decode_substrate_production(payload: JsonObject) -> SubstrateProduction:
    """Decode a strict payload; no unknown or missing fields are accepted."""
    top = _object(payload, "payload", _TOP_LEVEL_KEYS)
    original_blob = _blob(top.get("original_blob"), "original_blob")
    substrate_payload = _object(top.get("substrate"), "substrate", _SUBSTRATE_KEYS)
    substrate_blob = _blob(substrate_payload.get("blob"), "substrate.blob")
    page_count_value = substrate_payload.get("page_count")
    if page_count_value is None:
        page_count: int | None = None
    elif type(page_count_value) is not int or page_count_value < 1:
        raise ValueError("substrate.page_count must be positive or null")
    else:
        page_count = page_count_value
    page_map_value = substrate_payload.get("page_map")
    if not isinstance(page_map_value, tuple):
        raise ValueError("substrate.page_map must be an array")
    page_map = tuple(
        _page(value, index) for index, value in enumerate(page_map_value)
    )
    substrate = Substrate(
        SubstrateId(_text(substrate_payload.get("substrate_id"), "substrate.substrate_id")),
        substrate_blob,
        _integer(
            substrate_payload.get("normalized_character_length"),
            "substrate.normalized_character_length",
        ),
        _text(
            substrate_payload.get("normalization_version"),
            "substrate.normalization_version",
        ),
        page_count,
        page_map,
    )
    return SubstrateProduction(
        SubstrateProductionId(
            _text(top.get("substrate_production_id"), "substrate_production_id")
        ),
        SourceId(_text(top.get("source_id"), "source_id")),
        original_blob,
        substrate,
        _text(top.get("converter_name"), "converter_name"),
        _text(top.get("converter_version"), "converter_version"),
        substrate.normalization_version,
        _text(top.get("admission_policy_version"), "admission_policy_version"),
        _text(top.get("page_map_policy_version"), "page_map_policy_version"),
        _timestamp(top.get("produced_at")),
    )


def decode_source_substrate_produced(payload: JsonObject) -> SubstrateProduction:
    return decode_substrate_production(payload)


def decode_substrate_produced_event(
    event: DomainEvent, load_blob: BlobLoader
) -> SubstrateProduction:
    if (
        event.event_type != SOURCE_SUBSTRATE_PRODUCED
        or event.schema_version != SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION
    ):
        raise ValueError("event envelope does not match source.substrate_produced@1")
    receipt = decode_substrate_production(event.payload)
    expected_id = substrate_production_event_id_for(
        event.course_id, receipt.substrate_production_id, event.course_sequence
    )
    if event.event_id != expected_id:
        raise ValueError("event_id does not match substrate production identity")
    if event.actor.kind is not PrincipalKind.SERVICE:
        raise ValueError("substrate production events require a service actor")
    if receipt.produced_at != event.occurred_at.astimezone(UTC):
        raise ValueError("production produced_at must equal event.occurred_at")
    _verified_blob(load_blob, receipt.original_blob, "original_blob")
    substrate_bytes = _verified_blob(load_blob, receipt.substrate.blob, "substrate.blob")
    if not substrate_bytes:
        raise ValueError("substrate.blob must contain non-empty text")
    try:
        normalized = normalize_utf8(substrate_bytes)
    except (InvalidUtf8Error, TypeError) as error:
        raise ValueError("substrate.blob must contain strict UTF-8 text") from error
    if normalized.content != substrate_bytes:
        raise ValueError("substrate.blob is not canonical newline-normalized NFC text")
    if substrate_id_for(substrate_bytes) != receipt.substrate.substrate_id:
        raise ValueError("substrate_id does not match substrate bytes")
    if len(normalized.text) != receipt.substrate.normalized_character_length:
        raise ValueError("substrate character length does not match substrate bytes")
    return receipt


def decode_source_substrate_produced_event(
    event: DomainEvent, load_blob: BlobLoader
) -> SubstrateProduction:
    return decode_substrate_produced_event(event, load_blob)


def _object(value: JsonValue | None, name: str, keys: frozenset[str]) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    actual = frozenset(value)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise ValueError(f"{name} fields mismatch; missing={missing}, extra={extra}")
    return value


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


def _integer(value: JsonValue | None, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def _blob(value: JsonValue | None, name: str) -> BlobRef:
    payload = _object(value, name, _BLOB_KEYS)
    checksum = _text(payload.get("checksum_sha256"), f"{name}.checksum_sha256")
    blob_id = _text(payload.get("id"), f"{name}.id")
    if blob_id != f"sha256:{checksum}":
        raise ValueError(f"{name}.id must match its SHA-256 checksum")
    return BlobRef(
        BlobId(blob_id), checksum, _integer(payload.get("byte_length"), f"{name}.byte_length")
    )


def _page(value: JsonValue, index: int) -> PageMapEntry:
    name = f"substrate.page_map[{index}]"
    payload = _object(value, name, _PAGE_KEYS)
    return PageMapEntry(
        _integer(payload.get("offset"), f"{name}.offset"),
        _integer(payload.get("page"), f"{name}.page"),
    )


def _timestamp(value: JsonValue | None) -> datetime:
    text = _text(value, "produced_at")
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("produced_at must be an ISO-8601 timestamp") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("produced_at must be timezone-aware")
    return result.astimezone(UTC)


def _verified_blob(load_blob: BlobLoader, ref: BlobRef, name: str) -> bytes:
    content = load_blob(ref)
    if not isinstance(content, bytes):
        raise ValueError(f"{name} loader must return bytes")
    if len(content) != ref.byte_length:
        raise ValueError(f"{name} byte length does not match loaded content")
    if sha256(content).hexdigest() != ref.checksum_sha256:
        raise ValueError(f"{name} checksum does not match loaded content")
    return content


__all__ = [
    "SOURCE_SUBSTRATE_PRODUCED",
    "SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION",
    "SUBSTRATE_PRODUCED",
    "SUBSTRATE_PRODUCED_SCHEMA_VERSION",
    "BlobLoader",
    "decode_source_substrate_produced",
    "decode_source_substrate_produced_event",
    "decode_substrate_produced_event",
    "decode_substrate_production",
    "source_substrate_produced_payload",
    "substrate_production_payload",
]
