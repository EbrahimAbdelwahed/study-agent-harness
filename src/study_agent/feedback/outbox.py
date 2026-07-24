"""Strict, local-only capability-gap outbox contracts and export service.

The outbox is deliberately narrower than the local aggregate.  It contains
only closed dimensions, trusted fingerprints, bounded counters, timestamps,
and lifecycle enums.  Publication is an injected local effect: this module
does not know how to reach a network, Flywheel, GitHub, or a provider.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol, cast

from study_agent.state import canonical_json_bytes, canonical_json_object

from .contracts import (
    CapabilityGapAggregate,
    CapabilityGapCollisionError,
    CapabilityGapCorruptionError,
    CapabilityGapDimensions,
    CapabilityGapValidationError,
    GapExportState,
    GapKeyV1,
    GapResolutionKind,
    ImpactKind,
    VerificationKind,
)

OUTBOX_SCHEMA_VERSION = 1
_OUTBOX_DOMAIN = b"study-agent-gap-outbox-v1\0"
_MAX_OUTBOX_BYTES = 512 * 1024
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class GapOutboxValidationError(ValueError):
    """A caller supplied a value outside the strict outbox contract."""


class GapOutboxCorruptionError(RuntimeError):
    """Persisted or imported outbox bytes are not the exact contract."""


class GapOutboxPublicationError(RuntimeError):
    """The explicit local publisher did not durably publish the bundle."""


class GapOutboxPublisher(Protocol):
    """Trusted local publication effect injected by the embedding host.

    Implementations must return normally only after the exact bytes are
    durable.  A hosted/network implementation belongs to a later adapter and
    is intentionally not part of this core module.
    """

    def publish(self, payload: bytes) -> None: ...


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise GapOutboxValidationError(f"invalid_{field}")
    return value


def _version(value: object, field: str = "harness_version") -> str:
    if not isinstance(value, str) or _VERSION.fullmatch(value) is None:
        raise GapOutboxValidationError(f"invalid_{field}")
    return value


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise GapOutboxValidationError(f"invalid_{field}")
    normalized = value.astimezone(UTC)
    return normalized


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise GapOutboxCorruptionError("outbox_record_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise GapOutboxCorruptionError("outbox_record_invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GapOutboxCorruptionError("outbox_record_invalid")
    return parsed.astimezone(UTC)


def _exact_object(data: bytes, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(data, bytes) or len(data) > _MAX_OUTBOX_BYTES:
        raise GapOutboxCorruptionError("outbox_payload_invalid")
    try:
        value = canonical_json_object(data)
    except (TypeError, ValueError, UnicodeDecodeError):
        raise GapOutboxCorruptionError("outbox_payload_invalid") from None
    if tuple(sorted(value)) != tuple(sorted(fields)):
        raise GapOutboxCorruptionError("outbox_payload_invalid")
    if canonical_json_bytes(cast(Any, value)) != data:
        raise GapOutboxCorruptionError("outbox_payload_noncanonical")
    return dict(value)


@dataclass(frozen=True, slots=True)
class GapOutboxRecord:
    """One immutable, credential-free projection of a local aggregate."""

    gap_key: GapKeyV1
    dimensions: CapabilityGapDimensions
    verification_kind: VerificationKind
    impact_kind: ImpactKind
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
    resolution: GapResolutionKind = GapResolutionKind.UNRESOLVED
    export_state: GapExportState = GapExportState.PENDING
    resolution_authority_fingerprint: str | None = None
    resolved_at: datetime | None = None
    schema_version: int = OUTBOX_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != OUTBOX_SCHEMA_VERSION:
            raise GapOutboxValidationError("invalid_schema_version")
        if not isinstance(self.gap_key, GapKeyV1):
            raise GapOutboxValidationError("invalid_gap_key")
        if not isinstance(self.dimensions, CapabilityGapDimensions):
            raise GapOutboxValidationError("invalid_dimensions")
        try:
            self.gap_key.verify(self.dimensions)
        except CapabilityGapCollisionError:
            raise
        if not isinstance(self.verification_kind, VerificationKind):
            raise GapOutboxValidationError("invalid_verification_kind")
        if not isinstance(self.impact_kind, ImpactKind):
            raise GapOutboxValidationError("invalid_impact_kind")
        first = _utc(self.first_seen, "first_seen")
        last = _utc(self.last_seen, "last_seen")
        if last < first:
            raise GapOutboxValidationError("invalid_seen_range")
        if type(self.occurrence_count) is not int or self.occurrence_count < 1:
            raise GapOutboxValidationError("invalid_occurrence_count")
        if not isinstance(self.resolution, GapResolutionKind):
            raise GapOutboxValidationError("invalid_resolution")
        if not isinstance(self.export_state, GapExportState):
            raise GapOutboxValidationError("invalid_export_state")
        if self.resolution is GapResolutionKind.UNRESOLVED:
            if self.resolution_authority_fingerprint is not None or self.resolved_at is not None:
                raise GapOutboxValidationError("invalid_resolution")
        else:
            _digest(self.resolution_authority_fingerprint, "resolution_authority_fingerprint")
            if self.resolved_at is None:
                raise GapOutboxValidationError("invalid_resolution")
        if self.resolved_at is not None:
            resolved = _utc(self.resolved_at, "resolved_at")
            if resolved < first:
                raise GapOutboxValidationError("invalid_resolution")
            object.__setattr__(self, "resolved_at", resolved)
        object.__setattr__(self, "first_seen", first)
        object.__setattr__(self, "last_seen", last)

    @classmethod
    def from_aggregate(cls, aggregate: CapabilityGapAggregate) -> GapOutboxRecord:
        if not isinstance(aggregate, CapabilityGapAggregate):
            raise GapOutboxValidationError("invalid_aggregate")
        return cls(
            gap_key=aggregate.gap_key,
            dimensions=aggregate.dimensions,
            verification_kind=aggregate.verification_kind,
            impact_kind=aggregate.impact_kind,
            first_seen=aggregate.first_seen,
            last_seen=aggregate.last_seen,
            occurrence_count=aggregate.occurrence_count,
            resolution=aggregate.resolution,
            export_state=aggregate.export_state,
            resolution_authority_fingerprint=aggregate.resolution_authority_fingerprint,
            resolved_at=aggregate.resolved_at,
        )

    def to_aggregate(self) -> CapabilityGapAggregate:
        return CapabilityGapAggregate(
            gap_key=self.gap_key,
            dimensions=self.dimensions,
            verification_kind=self.verification_kind,
            impact_kind=self.impact_kind,
            first_seen=self.first_seen,
            last_seen=self.last_seen,
            occurrence_count=self.occurrence_count,
            resolution=self.resolution,
            export_state=self.export_state,
            resolution_authority_fingerprint=self.resolution_authority_fingerprint,
            resolved_at=self.resolved_at,
        )

    def to_json(self) -> dict[str, object]:
        return {
            "dimensions": self.dimensions.to_json(),
            "export_state": self.export_state.value,
            "first_seen": _timestamp(self.first_seen),
            "gap_key": self.gap_key.value,
            "impact_kind": self.impact_kind.value,
            "last_seen": _timestamp(self.last_seen),
            "occurrence_count": self.occurrence_count,
            "resolution": self.resolution.value,
            "resolution_authority_fingerprint": self.resolution_authority_fingerprint,
            "resolved_at": None if self.resolved_at is None else _timestamp(self.resolved_at),
            "schema_version": self.schema_version,
            "verification_kind": self.verification_kind.value,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(cast(Any, self.to_json()))

    @classmethod
    def from_bytes(cls, data: bytes) -> GapOutboxRecord:
        value = _exact_object(
            data,
            (
                "schema_version",
                "gap_key",
                "dimensions",
                "verification_kind",
                "impact_kind",
                "first_seen",
                "last_seen",
                "occurrence_count",
                "resolution",
                "export_state",
                "resolution_authority_fingerprint",
                "resolved_at",
            ),
        )
        try:
            nested = value["dimensions"]
            if not isinstance(nested, Mapping):
                raise ValueError
            record = cls(
                schema_version=value["schema_version"],
                gap_key=GapKeyV1(value["gap_key"]),
                dimensions=CapabilityGapDimensions.from_bytes(
                    canonical_json_bytes(cast(Any, nested))
                ),
                verification_kind=VerificationKind(value["verification_kind"]),
                impact_kind=ImpactKind(value["impact_kind"]),
                first_seen=_parse_timestamp(value["first_seen"], "first_seen"),
                last_seen=_parse_timestamp(value["last_seen"], "last_seen"),
                occurrence_count=value["occurrence_count"],
                resolution=GapResolutionKind(value["resolution"]),
                export_state=GapExportState(value["export_state"]),
                resolution_authority_fingerprint=value["resolution_authority_fingerprint"],
                resolved_at=(
                    None
                    if value["resolved_at"] is None
                    else _parse_timestamp(value["resolved_at"], "resolved_at")
                ),
            )
        except CapabilityGapCollisionError:
            raise
        except (
            KeyError,
            TypeError,
            ValueError,
            CapabilityGapValidationError,
            CapabilityGapCorruptionError,
        ):
            raise GapOutboxCorruptionError("outbox_record_invalid") from None
        if record.to_bytes() != data:
            raise GapOutboxCorruptionError("outbox_payload_noncanonical")
        return record


@dataclass(frozen=True, slots=True)
class GapOutboxBundle:
    """Versioned deterministic bundle containing only sorted gap records."""

    harness_version: str
    records: tuple[GapOutboxRecord, ...]
    schema_version: int = OUTBOX_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != OUTBOX_SCHEMA_VERSION:
            raise GapOutboxValidationError("invalid_schema_version")
        _version(self.harness_version)
        if not isinstance(self.records, tuple):
            raise GapOutboxValidationError("records_must_be_tuple")
        if any(not isinstance(item, GapOutboxRecord) for item in self.records):
            raise GapOutboxValidationError("invalid_record")
        keys = tuple(item.gap_key.value for item in self.records)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise GapOutboxValidationError("records_not_canonical")

    @property
    def bundle_fingerprint(self) -> str:
        return sha256(_OUTBOX_DOMAIN + self.to_bytes()).hexdigest()

    @property
    def harness_fingerprint(self) -> str:
        return sha256(
            b"study-agent-gap-harness-v1\0" + self.harness_version.encode("ascii")
        ).hexdigest()

    def to_json(self) -> dict[str, object]:
        return {
            "harness_version": self.harness_version,
            "records": tuple(item.to_json() for item in self.records),
            "schema_version": self.schema_version,
        }

    def to_bytes(self) -> bytes:
        payload = canonical_json_bytes(cast(Any, self.to_json()))
        if len(payload) > _MAX_OUTBOX_BYTES:
            raise GapOutboxValidationError("outbox_too_large")
        return payload

    @classmethod
    def from_bytes(cls, data: bytes) -> GapOutboxBundle:
        value = _exact_object(data, ("schema_version", "harness_version", "records"))
        try:
            raw_records = value["records"]
            if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
                raise ValueError
            records = tuple(
                GapOutboxRecord.from_bytes(canonical_json_bytes(cast(Any, item)))
                for item in raw_records
            )
            bundle = cls(
                harness_version=value["harness_version"],
                records=records,
                schema_version=value["schema_version"],
            )
        except CapabilityGapCollisionError:
            raise
        except GapOutboxCorruptionError:
            raise
        except (KeyError, TypeError, ValueError, GapOutboxValidationError):
            raise GapOutboxCorruptionError("outbox_bundle_invalid") from None
        if bundle.to_bytes() != data:
            raise GapOutboxCorruptionError("outbox_payload_noncanonical")
        return bundle


@dataclass(frozen=True, slots=True)
class GapOutboxPublication:
    """Receipt returned only after the publisher accepted durable bytes."""

    bundle: GapOutboxBundle
    payload: bytes
    exported_gap_keys: tuple[GapKeyV1, ...]

    def __post_init__(self) -> None:
        if self.payload != self.bundle.to_bytes():
            raise GapOutboxValidationError("publication_payload_mismatch")
        if tuple(item.gap_key for item in self.bundle.records) != self.exported_gap_keys:
            raise GapOutboxValidationError("publication_keys_mismatch")

    @property
    def bundle_fingerprint(self) -> str:
        return self.bundle.bundle_fingerprint


class GapOutboxExportService:
    """Explicit local export coordinator with publish-before-export ordering."""

    def __init__(
        self,
        store: Any,
        publisher: GapOutboxPublisher,
        *,
        harness_version: str,
    ) -> None:
        _version(harness_version)
        if not callable(getattr(store, "list_aggregates", None)):
            raise GapOutboxValidationError("store_snapshot_unsupported")
        if not callable(getattr(store, "set_export_state", None)):
            raise GapOutboxValidationError("store_export_unsupported")
        if not callable(getattr(publisher, "publish", None)):
            raise GapOutboxValidationError("publisher_unsupported")
        self._store = store
        self._publisher = publisher
        self._harness_version = harness_version

    def snapshot(self, *, include_exported: bool = False) -> GapOutboxBundle:
        states = (
            frozenset(GapExportState)
            if include_exported
            else frozenset(
                {GapExportState.LOCAL, GapExportState.PENDING, GapExportState.FAILED}
            )
        )
        payloads = self._store.list_aggregates(states=states)
        records = tuple(
            sorted(
                (
                    GapOutboxRecord.from_aggregate(_decode_aggregate(payload))
                    for payload in payloads
                ),
                key=lambda item: item.gap_key.value,
            )
        )
        return GapOutboxBundle(self._harness_version, records)

    def export_pending(self) -> GapOutboxPublication:
        """Publish a stable local snapshot and then mark its source rows.

        A failure leaves rows pending/failed; a crash after publication and
        before marking is safe because those rows remain pending and the next
        explicit call publishes the same bytes again.
        """

        initial = self.snapshot()
        keys = tuple(record.gap_key for record in initial.records)
        self._set_export_states(keys, GapExportState.PENDING)
        bundle = self.snapshot()
        payload = bundle.to_bytes()
        try:
            self._publisher.publish(payload)
        except Exception as error:
            with suppress(Exception):
                self._set_export_states(
                    tuple(record.gap_key for record in bundle.records), GapExportState.FAILED
                )
            raise GapOutboxPublicationError("outbox_publish_failed") from error
        self._set_export_states(
            tuple(record.gap_key for record in bundle.records), GapExportState.EXPORTED
        )
        return GapOutboxPublication(bundle, payload, tuple(item.gap_key for item in bundle.records))

    def _set_export_states(
        self, keys: tuple[GapKeyV1, ...], state: GapExportState
    ) -> None:
        values = tuple(key.value for key in keys)
        bulk = getattr(self._store, "set_export_states", None)
        if callable(bulk):
            bulk(values, state)
            return
        for value in values:
            self._store.set_export_state(value, state)

    # Concise aliases make the explicit action convenient without introducing
    # a second semantic path.
    export = export_pending
    publish_pending = export_pending


def _decode_aggregate(payload: object) -> CapabilityGapAggregate:
    if not isinstance(payload, bytes):
        raise GapOutboxCorruptionError("outbox_source_invalid")
    try:
        return CapabilityGapAggregate.from_bytes(payload)
    except (CapabilityGapCorruptionError, CapabilityGapCollisionError):
        raise GapOutboxCorruptionError("outbox_source_invalid") from None


# Versioned spellings are useful to downstream adapters while the short names
# remain ergonomic for the core and tests.
GapOutboxRecordV1 = GapOutboxRecord
GapOutboxBundleV1 = GapOutboxBundle
GapOutboxExportReceipt = GapOutboxPublication


__all__ = [
    "OUTBOX_SCHEMA_VERSION",
    "GapOutboxBundle",
    "GapOutboxBundleV1",
    "GapOutboxCorruptionError",
    "GapOutboxExportReceipt",
    "GapOutboxExportService",
    "GapOutboxPublication",
    "GapOutboxPublicationError",
    "GapOutboxPublisher",
    "GapOutboxRecord",
    "GapOutboxRecordV1",
    "GapOutboxValidationError",
]
