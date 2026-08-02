from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import pytest

from study_agent.domain import (
    Actor,
    BlobId,
    BlobRef,
    ChunkId,
    ContentOrigin,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
    RevisionId,
    RevisionRef,
    SelectionStatus,
    SourceChunk,
    SourceDocument,
    SourceId,
    SourceKind,
    SourceSuccession,
    StructureOrigin,
)
from study_agent.domain._validation import JsonObject
from study_agent.ingestion.events import PersistedChunkingConfig, SourceRevisionIngested
from study_agent.ingestion.identity import source_superseded_by_event_id_for
from study_agent.ingestion.projection import reduce_source_revision
from study_agent.ingestion.succession import (
    SOURCE_SUPERSEDED_BY,
    SOURCE_SUPERSEDED_BY_SCHEMA_VERSION,
    decode_source_superseded_by,
    decode_source_superseded_by_event,
    eligible_revision_ids,
    reduce_source_superseded_by,
    revision_manifest,
    revision_selection_status,
    source_lineage,
    source_superseded_by_payload,
    successor_of,
)

COURSE = CourseId("course-lineage")


def blob(text: str) -> BlobRef:
    raw = text.encode("utf-8")
    checksum = sha256(raw).hexdigest()
    return BlobRef(BlobId(f"sha256:{checksum}"), checksum, len(raw))


def document(source: str, text: str, *, title: str = "Dispensa") -> SourceDocument:
    original = blob(text)
    normalized = blob(text)
    return SourceDocument(
        SourceId(source),
        RevisionId(f"revision-sha256:{sha256(f'{source}/{text}'.encode()).hexdigest()}"),
        SourceKind.MARKDOWN,
        title,
        "text/markdown",
        original.checksum_sha256,
        original.byte_length,
        datetime(2026, 7, 27, tzinfo=UTC),
        80,
        "lecture",
        original,
        normalized,
        "utf8-newlines-nfc-v1",
        len(text),
        StructureOrigin.SOURCE_AUTHORED,
        "utf8-markdown-v1",
        ContentOrigin.ORIGINAL,
    )


def chunk_for(source: SourceDocument) -> SourceChunk:
    return SourceChunk(
        ChunkId(f"chunk-sha256:{sha256(str(source.revision_id).encode()).hexdigest()}"),
        source.source_id,
        source.revision_id,
        0,
        source.normalized_character_length,
        ("Dispensa",),
        0,
        source.normalized_blob.checksum_sha256,
        "heading-paragraph-v1",
    )


def ingest(state: JsonObject, source: SourceDocument) -> JsonObject:
    payload = SourceRevisionIngested(
        source,
        (chunk_for(source),),
        source.normalized_character_length,
        PersistedChunkingConfig("heading-paragraph-v1", 1200),
    )
    event = DomainEvent(
        _event_id(source),
        COURSE,
        1,
        "source.revision_ingested",
        1,
        Actor(PrincipalKind.SERVICE, "test"),
        source.created_at,
        CorrelationId("lineage-correlation"),
        {},
    )
    return dict(reduce_source_revision(state, event, payload))


def _event_id(source: SourceDocument) -> EventId:
    return EventId(f"event-sha256:{sha256(str(source.revision_id).encode()).hexdigest()}")


def succession_event(
    succession: SourceSuccession, sequence: int = 3
) -> DomainEvent:
    return DomainEvent(
        source_superseded_by_event_id_for(
            COURSE,
            succession.predecessor.source_id,
            succession.predecessor.revision_id,
            succession.successor.source_id,
            succession.successor.revision_id,
            sequence,
        ),
        COURSE,
        sequence,
        SOURCE_SUPERSEDED_BY,
        SOURCE_SUPERSEDED_BY_SCHEMA_VERSION,
        Actor(PrincipalKind.SERVICE, "test"),
        datetime(2026, 7, 27, tzinfo=UTC),
        CorrelationId("lineage-correlation"),
        source_superseded_by_payload(succession),
    )


def two_revisions() -> tuple[JsonObject, SourceDocument, SourceDocument]:
    first = document("dispensa", "prima edizione")
    second = document("dispensa", "seconda edizione")
    state = ingest(ingest({}, first), second)
    return state, first, second


def ref(source: SourceDocument) -> RevisionRef:
    return RevisionRef(source.source_id, source.revision_id)


def apply(state: JsonObject, succession: SourceSuccession) -> JsonObject:
    return dict(
        reduce_source_superseded_by(state, succession_event(succession), succession)
    )


# --- selection ------------------------------------------------------------


def test_a_newer_revision_becomes_current_and_older_ones_become_inactive() -> None:
    state, first, second = two_revisions()
    assert revision_selection_status(state, first.source_id, first.revision_id) is (
        SelectionStatus.INACTIVE
    )
    assert revision_selection_status(state, second.source_id, second.revision_id) is (
        SelectionStatus.CURRENT
    )


def test_an_inactive_revision_keeps_its_blobs_and_stays_resolvable() -> None:
    state, first, _ = two_revisions()
    manifest = revision_manifest(state, first.source_id, first.revision_id)
    assert manifest.original_blob == first.blob
    assert str(manifest.substrate_id) == f"substrate:sha256:{first.normalized_blob.checksum_sha256}"
    assert manifest.is_legacy_substrate


def test_default_eligibility_is_the_current_revision_only() -> None:
    state, first, second = two_revisions()
    assert eligible_revision_ids(state, first.source_id) == (second.revision_id,)


def test_a_historical_revision_remains_explicitly_readable() -> None:
    state, first, _ = two_revisions()
    lineage = source_lineage(state, first.source_id)
    assert lineage.revisions[0].manifest.revision_id == first.revision_id
    assert len(lineage.revisions) == 2
    assert lineage.current is not None
    assert lineage.current.manifest.revision_id != first.revision_id


def test_selection_status_rejects_an_unknown_endpoint() -> None:
    state, first, _ = two_revisions()
    with pytest.raises(KeyError):
        revision_selection_status(state, first.source_id, RevisionId("revision-sha256:zz"))
    with pytest.raises(KeyError):
        revision_selection_status(state, SourceId("assente"), first.revision_id)


# --- succession -----------------------------------------------------------


def test_cross_source_succession_requires_an_explicit_event() -> None:
    state, first, _ = two_revisions()
    nuova = document("dispensa-2027", "edizione nuova")
    state = ingest(state, nuova)
    assert successor_of(state, first.source_id, first.revision_id) is None

    state = apply(state, SourceSuccession(ref(first), ref(nuova), "new-edition"))
    assert successor_of(state, first.source_id, first.revision_id) == ref(nuova)


def test_succession_does_not_change_which_revision_is_current() -> None:
    state, first, second = two_revisions()
    nuova = document("dispensa-2027", "edizione nuova")
    state = ingest(state, nuova)
    before = revision_selection_status(state, second.source_id, second.revision_id)
    state = apply(state, SourceSuccession(ref(first), ref(nuova), "new-edition"))
    assert revision_selection_status(state, second.source_id, second.revision_id) is before


def test_a_self_link_is_rejected_by_the_contract() -> None:
    _, first, _ = two_revisions()
    with pytest.raises(ValueError, match="supersede itself"):
        SourceSuccession(ref(first), ref(first), "loop")


def test_a_missing_endpoint_is_rejected() -> None:
    state, first, _ = two_revisions()
    absent = document("mai-ingerita", "assente")
    with pytest.raises(ValueError, match="endpoint"):
        apply(state, SourceSuccession(ref(first), ref(absent), "new-edition"))
    with pytest.raises(ValueError, match="endpoint"):
        apply(state, SourceSuccession(ref(absent), ref(first), "new-edition"))


def test_a_conflicting_successor_is_rejected_but_an_exact_repeat_is_idempotent() -> None:
    state, first, _ = two_revisions()
    a = document("edizione-a", "a")
    b = document("edizione-b", "b")
    state = ingest(ingest(state, a), b)
    succession = SourceSuccession(ref(first), ref(a), "new-edition")
    state = apply(state, succession)

    assert apply(state, succession) == state
    with pytest.raises(ValueError, match="different declared successor"):
        apply(state, SourceSuccession(ref(first), ref(b), "new-edition"))


def test_a_cycle_is_rejected() -> None:
    state, first, _ = two_revisions()
    a = document("edizione-a", "a")
    b = document("edizione-b", "b")
    state = ingest(ingest(state, a), b)
    state = apply(state, SourceSuccession(ref(first), ref(a), "new-edition"))
    state = apply(state, SourceSuccession(ref(a), ref(b), "new-edition"))
    with pytest.raises(ValueError, match="cycle"):
        apply(state, SourceSuccession(ref(b), ref(first), "new-edition"))


def test_lineage_exposes_the_successor_without_migrating_the_citation() -> None:
    state, first, _ = two_revisions()
    nuova = document("dispensa-2027", "edizione nuova")
    state = ingest(state, nuova)
    state = apply(state, SourceSuccession(ref(first), ref(nuova), "new-edition"))

    lineage = source_lineage(state, first.source_id)
    entry = next(e for e in lineage.revisions if e.manifest.revision_id == first.revision_id)
    assert entry.successor == ref(nuova)
    assert entry.selection_status is SelectionStatus.INACTIVE
    # the predecessor still resolves against its own immutable substrate
    assert entry.manifest.original_blob == first.blob


# --- replay and codec -----------------------------------------------------


def test_lineage_replays_byte_identically_and_ignores_edge_order_effects() -> None:
    state, first, _ = two_revisions()
    nuova = document("dispensa-2027", "edizione nuova")
    state = ingest(state, nuova)
    once = apply(state, SourceSuccession(ref(first), ref(nuova), "new-edition"))
    twice = apply(once, SourceSuccession(ref(first), ref(nuova), "new-edition"))
    assert source_lineage(once, first.source_id).to_json() == (
        source_lineage(twice, first.source_id).to_json()
    )


def test_no_timestamp_participates_in_status_or_lineage_encoding() -> None:
    state, first, _ = two_revisions()
    encoded = source_lineage(state, first.source_id).to_json()
    assert "2026" not in repr(encoded)


def test_the_codec_round_trips_and_rejects_unknown_fields() -> None:
    _, first, second = two_revisions()
    succession = SourceSuccession(ref(first), ref(second), "new-edition")
    assert decode_source_superseded_by(source_superseded_by_payload(succession)) == (
        succession
    )
    with pytest.raises(ValueError, match="fields mismatch"):
        decode_source_superseded_by({**source_superseded_by_payload(succession), "x": 1})


def test_the_event_requires_service_authority_and_matching_identity() -> None:
    _, first, second = two_revisions()
    succession = SourceSuccession(ref(first), ref(second), "new-edition")
    event = succession_event(succession)
    assert decode_source_superseded_by_event(event) == succession

    human = DomainEvent(
        event.event_id,
        event.course_id,
        event.course_sequence,
        event.event_type,
        event.schema_version,
        Actor(PrincipalKind.HUMAN, "learner"),
        event.occurred_at,
        event.correlation_id,
        event.payload,
    )
    with pytest.raises(ValueError, match="service actor"):
        decode_source_superseded_by_event(human)


def test_the_event_rejects_a_forged_identity() -> None:
    _, first, second = two_revisions()
    succession = SourceSuccession(ref(first), ref(second), "new-edition")
    event = succession_event(succession)
    forged = DomainEvent(
        succession_event(succession, sequence=9).event_id,
        event.course_id,
        event.course_sequence,
        event.event_type,
        event.schema_version,
        event.actor,
        event.occurred_at,
        event.correlation_id,
        event.payload,
    )
    with pytest.raises(ValueError, match="does not match succession identity"):
        decode_source_superseded_by_event(forged)
