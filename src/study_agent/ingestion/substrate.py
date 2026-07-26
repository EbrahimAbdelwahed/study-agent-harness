"""Trusted application service for immutable normalized-text productions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any

from study_agent.domain.context import ExecutionContext
from study_agent.domain.events import Actor, DomainEvent, PrincipalKind
from study_agent.domain.identifiers import (
    BlobId,
    SourceId,
    substrate_id_for,
    substrate_production_event_id_for,
    substrate_production_id_for,
)
from study_agent.domain.source import BlobRef
from study_agent.domain.substrate import PageMapEntry, Substrate, SubstrateProduction
from study_agent.ingestion.normalization import InvalidUtf8Error, normalize_utf8
from study_agent.ports import BlobStore, ClockPort, EventStore
from study_agent.ports.storage import EventSequenceConflictError

from .substrate_events import (
    SOURCE_SUBSTRATE_PRODUCED,
    SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION,
    decode_substrate_produced_event,
    substrate_production_payload,
)


class SubstrateProductionStatus(StrEnum):
    EMITTED = "emitted"
    IDEMPOTENT = "idempotent"


@dataclass(frozen=True, slots=True)
class TrustedBlobReceipt:
    """Host-owned binding to an original immutable blob."""

    blob: BlobRef
    source_id: SourceId

    def __post_init__(self) -> None:
        if not isinstance(self.blob, BlobRef):
            raise TypeError("trusted blob receipt requires BlobRef")
        if not isinstance(self.source_id, SourceId):
            raise TypeError("trusted blob receipt source_id must be SourceId")


OriginalBlobReceipt = TrustedBlobReceipt


@dataclass(frozen=True, slots=True)
class ConverterReceipt:
    """Trusted converter output and its immutable policy metadata.

    ``content`` is the preferred seam for converters that return bytes.  A
    caller that already published the output may supply ``blob`` instead; the
    service still reloads and verifies it before appending an event.
    """

    content: bytes | None
    converter_name: str
    converter_version: str
    normalization_version: str
    admission_policy_version: str
    page_map_policy_version: str
    source_id: SourceId
    original_blob: BlobRef
    page_count: int | None = None
    page_map: tuple[PageMapEntry, ...] = ()
    blob: BlobRef | None = None

    def __post_init__(self) -> None:
        if self.content is not None and not isinstance(self.content, bytes):
            raise TypeError("converter content must be bytes")
        if self.content is None and self.blob is None:
            raise ValueError("converter receipt requires content or blob")
        if self.blob is not None and not isinstance(self.blob, BlobRef):
            raise TypeError("converter blob must be BlobRef")
        if not self.converter_name or self.converter_name != self.converter_name.strip():
            raise ValueError("converter_name must be non-empty and trimmed")
        if not self.converter_version or self.converter_version != self.converter_version.strip():
            raise ValueError("converter_version must be non-empty and trimmed")
        if not self.normalization_version or (
            self.normalization_version != self.normalization_version.strip()
        ):
            raise ValueError("normalization_version must be non-empty and trimmed")
        if (
            not self.admission_policy_version
            or self.admission_policy_version != self.admission_policy_version.strip()
        ):
            raise ValueError("admission_policy_version must be non-empty and trimmed")
        if not self.page_map_policy_version or (
            self.page_map_policy_version != self.page_map_policy_version.strip()
        ):
            raise ValueError("page_map_policy_version must be non-empty and trimmed")
        if not isinstance(self.source_id, SourceId):
            raise TypeError("converter source_id must be SourceId")
        if not isinstance(self.original_blob, BlobRef):
            raise TypeError("converter original_blob must be BlobRef")
        object.__setattr__(self, "page_map", tuple(self.page_map))
        if any(not isinstance(entry, PageMapEntry) for entry in self.page_map):
            raise TypeError("converter page_map must contain PageMapEntry values")

    @property
    def normalized_content(self) -> bytes | None:
        return self.content


@dataclass(frozen=True, slots=True)
class SubstrateProductionResult:
    status: SubstrateProductionStatus
    receipt: SubstrateProduction
    committed_sequence: int


class SubstrateProductionError(ValueError):
    """A trusted substrate production failed before canonical append."""


class SubstrateProductionService:
    """Publish and replay source substrate productions without providers."""

    def __init__(self, *, blobs: BlobStore, events: EventStore, clock: ClockPort) -> None:
        self._blobs = blobs
        self._events = events
        self._clock = clock

    def produce(
        self,
        *,
        source_id: SourceId,
        original_blob: TrustedBlobReceipt,
        converter: ConverterReceipt,
        context: ExecutionContext,
        expected_sequence: int | None = None,
    ) -> SubstrateProductionResult:
        if not isinstance(source_id, SourceId):
            raise TypeError("source_id must be SourceId")
        if expected_sequence is not None and (
            type(expected_sequence) is not int or expected_sequence < 0
        ):
            raise ValueError("expected_sequence must be a non-negative integer")
        if not isinstance(converter, ConverterReceipt):
            raise TypeError("converter must be ConverterReceipt")
        original = _coerce_original_blob(source_id, original_blob)
        if converter.source_id != source_id:
            raise SubstrateProductionError("converter receipt belongs to another source")
        if converter.original_blob != original:
            raise SubstrateProductionError(
                "converter receipt is not bound to the trusted original blob"
            )
        if context.principal_kind is not PrincipalKind.SERVICE:
            raise SubstrateProductionError("substrate production requires a service context")
        stream = tuple(self._events.read(context.course_id))
        current_sequence = stream[-1].course_sequence if stream else 0
        if expected_sequence is not None and current_sequence != expected_sequence:
            raise SubstrateProductionError(
                f"course stream does not match expected sequence {expected_sequence}; "
                f"observed {current_sequence}"
            )

        _verified_blob(self._blobs, original, "original_blob")
        normalized_bytes = self._converter_bytes(converter)
        try:
            normalized = normalize_utf8(normalized_bytes)
        except (InvalidUtf8Error, TypeError) as error:
            raise SubstrateProductionError("converter output must be valid UTF-8") from error
        if not normalized.content or normalized.content != normalized_bytes:
            raise SubstrateProductionError(
                "converter output must already be canonical newline-normalized NFC text"
            )
        character_length = len(normalized.text)
        substrate_ref = self._blobs.put(normalized.content)
        _verified_blob(self._blobs, substrate_ref, "substrate_blob")
        substrate_id = substrate_id_for(normalized.content)
        expected_substrate_ref = BlobRef(
            BlobId(f"sha256:{substrate_id.value.removeprefix('substrate:sha256:')}"),
            substrate_id.value.removeprefix("substrate:sha256:"),
            len(normalized.content),
        )
        if substrate_ref != expected_substrate_ref:
            raise SubstrateProductionError("blob store returned a forged substrate reference")
        try:
            substrate = Substrate(
                substrate_id,
                substrate_ref,
                character_length,
                converter.normalization_version,
                converter.page_count,
                converter.page_map,
            )
            production_id = substrate_production_id_for(
                source_id=source_id,
                original_blob_id=str(original.id),
                original_blob_sha256=original.checksum_sha256,
                original_blob_byte_length=original.byte_length,
                substrate_id=substrate.substrate_id,
                converter_name=converter.converter_name,
                converter_version=converter.converter_version,
                normalization_version=converter.normalization_version,
                page_map_policy_version=converter.page_map_policy_version,
                page_count=substrate.page_count,
                page_map=tuple(entry.to_json() for entry in substrate.page_map),
                admission_policy_version=converter.admission_policy_version,
                character_length=substrate.normalized_character_length,
            )
            receipt = SubstrateProduction(
                production_id,
                source_id,
                original,
                substrate,
                converter.converter_name,
                converter.converter_version,
                converter.normalization_version,
                converter.admission_policy_version,
                converter.page_map_policy_version,
                self._clock.now(),
            )
        except (TypeError, ValueError) as error:
            raise SubstrateProductionError(str(error)) from error

        if expected_sequence is not None:
            latest_stream = tuple(self._events.read(context.course_id))
            latest_sequence = latest_stream[-1].course_sequence if latest_stream else 0
            if latest_sequence != expected_sequence:
                raise SubstrateProductionError(
                    "course event sequence changed before idempotent return"
                )
            stream = latest_stream
        existing = _find_production(stream, self._blobs, receipt.substrate_production_id)
        if existing is not None:
            sequence = stream[-1].course_sequence if stream else 0
            return SubstrateProductionResult(
                SubstrateProductionStatus.IDEMPOTENT, existing, sequence
            )

        event = DomainEvent(
            substrate_production_event_id_for(
                context.course_id, receipt.substrate_production_id, current_sequence + 1
            ),
            context.course_id,
            current_sequence + 1,
            SOURCE_SUBSTRATE_PRODUCED,
            SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION,
            Actor(context.principal_kind, context.principal_id),
            receipt.produced_at,
            context.correlation_id,
            substrate_production_payload(receipt),
            session_id=context.session_id,
        )
        try:
            committed = self._events.append(context.course_id, current_sequence, (event,))
        except EventSequenceConflictError as error:
            concurrent_stream = tuple(self._events.read(context.course_id))
            concurrent = (
                _find_production(
                    concurrent_stream, self._blobs, receipt.substrate_production_id
                )
                if expected_sequence is None
                else None
            )
            if concurrent is not None:
                concurrent_sequence = (
                    concurrent_stream[-1].course_sequence if concurrent_stream else 0
                )
                return SubstrateProductionResult(
                    SubstrateProductionStatus.IDEMPOTENT, concurrent, concurrent_sequence
                )
            raise SubstrateProductionError(
                "course event sequence changed during production"
            ) from error
        return SubstrateProductionResult(
            SubstrateProductionStatus.EMITTED, receipt, committed
        )

    def produce_substrate(self, **kwargs: Any) -> SubstrateProductionResult:
        """Compatibility spelling for hosts that use the domain noun."""
        return self.produce(**kwargs)

    def _converter_bytes(self, converter: ConverterReceipt) -> bytes:
        if converter.content is not None:
            if converter.blob is not None:
                verified = _verified_blob(self._blobs, converter.blob, "converter_blob")
                if verified != converter.content:
                    raise SubstrateProductionError(
                        "converter content does not match converter blob"
                    )
            return converter.content
        assert converter.blob is not None
        return _verified_blob(self._blobs, converter.blob, "converter_blob")


def _coerce_original_blob(source_id: SourceId, value: TrustedBlobReceipt) -> BlobRef:
    if isinstance(value, TrustedBlobReceipt):
        if value.source_id != source_id:
            raise SubstrateProductionError("original blob receipt belongs to another source")
        return value.blob
    raise TypeError("original_blob must be TrustedBlobReceipt")


def _verified_blob(blobs: BlobStore, ref: BlobRef, name: str) -> bytes:
    if str(ref.id) != f"sha256:{ref.checksum_sha256}":
        raise SubstrateProductionError(f"{name} id does not match its checksum")
    try:
        content = blobs.get(ref)
    except Exception as error:
        raise SubstrateProductionError(f"{name} could not be loaded") from error
    if not isinstance(content, bytes):
        raise SubstrateProductionError(f"{name} loader must return bytes")
    if len(content) != ref.byte_length:
        raise SubstrateProductionError(f"{name} byte length does not match its reference")
    if sha256(content).hexdigest() != ref.checksum_sha256:
        raise SubstrateProductionError(f"{name} checksum does not match its reference")
    return content


def _find_production(
    events: Sequence[DomainEvent], blobs: BlobStore, production_id: object
) -> SubstrateProduction | None:
    target = str(production_id)
    for event in events:
        if event.event_type != SOURCE_SUBSTRATE_PRODUCED:
            continue
        decoded = decode_substrate_produced_event(event, blobs.get)
        if str(decoded.substrate_production_id) == target:
            return decoded
    return None


__all__ = [
    "ConverterReceipt",
    "OriginalBlobReceipt",
    "SubstrateProductionError",
    "SubstrateProductionResult",
    "SubstrateProductionService",
    "SubstrateProductionStatus",
    "TrustedBlobReceipt",
]
