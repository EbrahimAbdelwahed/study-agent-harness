from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import fields, replace
from hashlib import sha256
from typing import Any, cast

import pytest

from study_agent.domain import (
    BlobId,
    ChunkId,
    Citation,
    RevisionId,
    SourceChunk,
    SourceId,
)
from study_agent.domain._validation import JsonValue, freeze_json
from study_agent.flashcards import (
    FlashcardScopeIndexEntry,
    PreparedFlashcardScope,
    VerifiedMediaEvidence,
)
from study_agent.grounding import EvidenceEnvelope
from study_agent.ports import (
    EvidenceStatus,
    RetrievalEvidence,
    RetrievalEvidenceSet,
    retrieval_read_set_fingerprint,
)


def _plain(value: JsonValue) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _evidence(item_count: int = 1) -> EvidenceEnvelope:
    items: list[RetrievalEvidence] = []
    for index in range(item_count):
        text = f"Canonical source excerpt {index}."
        source_id = SourceId(f"fixture-source-{index}")
        revision_id = RevisionId(f"fixture-revision-{index}")
        chunk = SourceChunk(
            ChunkId(f"fixture-chunk-{index}"),
            source_id,
            revision_id,
            0,
            len(text),
            (),
            index,
            sha256(text.encode()).hexdigest(),
            "fixture-chunker-v1",
        )
        citation = Citation(
            source_id,
            revision_id,
            chunk.chunk_id,
            0,
            len(text),
            f"Fixture > section {index}",
            text,
        )
        items.append(RetrievalEvidence(chunk, citation, text, 1.0))
    evidence = tuple(items)
    return EvidenceEnvelope.from_retrieval(
        RetrievalEvidenceSet(
            EvidenceStatus.SUFFICIENT,
            evidence,
            "a" * 64,
            "fixture_lexical",
            "1.0.0",
            "fixture-index-v1",
            retrieval_read_set_fingerprint(evidence),
        )
    )


def _entry(
    position: int = 0,
    *,
    topic_key: str | None = None,
    evidence_handles: tuple[str, ...] = (),
) -> FlashcardScopeIndexEntry:
    return FlashcardScopeIndexEntry(
        topic_key or f"topic-{position}",
        f"Section {position}",
        f"Source > section {position}",
        position,
        120 + position,
        evidence_handles,
    )


def _scope(entry_count: int = 1, *, with_evidence: bool = True) -> PreparedFlashcardScope:
    envelope = _evidence() if with_evidence else EvidenceEnvelope.from_retrieval(
        RetrievalEvidenceSet(
            EvidenceStatus.INSUFFICIENT,
            (),
            "b" * 64,
            "fixture_lexical",
            "1.0.0",
            "fixture-index-v1",
            retrieval_read_set_fingerprint(()),
        )
    )
    handle = envelope.items[0].handle if envelope.items else None
    return PreparedFlashcardScope.prepare(
        tuple(
            _entry(
                index,
                evidence_handles=((handle,) if handle is not None and index == 0 else ()),
            )
            for index in range(entry_count)
        ),
        envelope,
    )


def test_scope_accepts_exact_closed_entry_bounds_and_rejects_outside_them() -> None:
    assert len(_scope(1, with_evidence=False).index) == 1
    assert len(_scope(256, with_evidence=False).index) == 256

    envelope = _scope(with_evidence=False).evidence
    with pytest.raises(ValueError, match=r"1\.\.256"):
        PreparedFlashcardScope.prepare((), envelope)
    with pytest.raises(ValueError, match=r"1\.\.256"):
        PreparedFlashcardScope.prepare(tuple(_entry(index) for index in range(257)), envelope)


def test_scope_requires_unique_topics_and_contiguous_canonical_order() -> None:
    envelope = _scope(with_evidence=False).evidence
    with pytest.raises(ValueError, match="positions"):
        PreparedFlashcardScope.prepare((_entry(1), _entry(0)), envelope)
    with pytest.raises(ValueError, match="topic keys"):
        PreparedFlashcardScope.prepare(
            (_entry(0, topic_key="same-topic"), _entry(1, topic_key="same-topic")),
            envelope,
        )


def test_scope_links_only_unique_active_handles_inside_its_envelope() -> None:
    envelope = _evidence()
    active = envelope.items[0].handle
    prepared = PreparedFlashcardScope.prepare(
        (_entry(evidence_handles=(active,)),), envelope
    )
    assert prepared.index[0].evidence_handles == (active,)

    with pytest.raises(ValueError, match="unique"):
        _entry(evidence_handles=(active, active))
    with pytest.raises(ValueError, match="outside"):
        PreparedFlashcardScope.prepare(
            (_entry(evidence_handles=("opaque-unresolved-handle",)),), envelope
        )


def test_scope_rejects_more_than_twenty_four_active_evidence_items() -> None:
    envelope = _evidence(25)
    with pytest.raises(ValueError, match="24 active"):
        PreparedFlashcardScope.prepare((_entry(),), envelope)


def test_scope_round_trip_freezes_decoded_json_arrays_and_preserves_identity() -> None:
    prepared = _scope(2)
    raw_json = json.loads(prepared.to_bytes())
    assert isinstance(raw_json["index"], list)
    assert isinstance(raw_json["index"][0]["evidence_handles"], list)
    assert isinstance(raw_json["evidence"]["items"], list)

    decoded = PreparedFlashcardScope.from_bytes(prepared.to_bytes())

    assert decoded.index == prepared.index
    assert decoded.evidence.to_json() == prepared.evidence.to_json()
    assert decoded.scope_fingerprint == prepared.scope_fingerprint
    assert decoded.to_json() == prepared.to_json()
    assert decoded.to_bytes() == prepared.to_bytes()


def test_scope_fingerprint_pins_exact_domain_separated_payload_and_excludes_itself() -> None:
    prepared = _scope(2)
    payload = {
        "index": _plain(tuple(entry.to_json() for entry in prepared.index)),
        "evidence": _plain(prepared.evidence.to_json()),
    }
    canonical_payload = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    assert prepared.scope_fingerprint == sha256(
        b"prepared-flashcard-scope@1\0" + canonical_payload
    ).hexdigest()
    assert b"scope_fingerprint" not in canonical_payload


@pytest.mark.parametrize(
    "mutate",
    (
        lambda value: value.update(provider="fixture-provider"),
        lambda value: value.pop("scope_fingerprint"),
        lambda value: value.update(scope_fingerprint="f" * 64),
        lambda value: value["index"][0].update(extra="forbidden"),
        lambda value: value["index"][0].pop("heading"),
        lambda value: value["index"][0].update(evidence_handles="not-an-array"),
        lambda value: value["index"][0].update(evidence_handles=[1]),
        lambda value: value.update(index={"not": "an array"}),
        lambda value: value["evidence"].update(metadata={"provider": "forbidden"}),
    ),
)
def test_scope_codec_rejects_unknown_missing_malformed_and_forged_values(
    mutate: Any,
) -> None:
    payload = cast(dict[str, Any], _plain(_scope().to_json()))
    mutate(payload)

    with pytest.raises((TypeError, ValueError)):
        PreparedFlashcardScope.from_json(cast(Mapping[str, JsonValue], freeze_json(payload)))


def test_scope_bytes_reject_noncanonical_serialization() -> None:
    payload = _plain(_scope().to_json())
    noncanonical = json.dumps(payload, sort_keys=False, indent=2).encode()

    with pytest.raises(ValueError, match="canonical"):
        PreparedFlashcardScope.from_bytes(noncanonical)


def test_verified_media_evidence_binds_receipt_and_source_without_premature_commitment() -> None:
    digest = "c" * 64
    citation = Citation(
        SourceId("fixture-source"),
        RevisionId("fixture-revision"),
        ChunkId("fixture-chunk"),
        10,
        20,
        "Atlas > figure 2",
        "Aortic root",
    )
    media = VerifiedMediaEvidence(
        handle="opaque-media-handle",
        evidence_handle="opaque-evidence-handle",
        blob_id=BlobId(f"sha256:{digest}"),
        sha256=digest,
        citation=citation,
        verifier_id="trusted_media",
        verifier_version="1.0.0",
        verifier_fingerprint="d" * 64,
        alt_text="Diagram of the aortic root and its three sinuses.",
    )

    assert VerifiedMediaEvidence.from_json(media.to_json()) == media
    assert tuple(media.to_json()) == (
        "handle",
        "evidence_handle",
        "blob_id",
        "sha256",
        "citation",
        "verifier_id",
        "verifier_version",
        "verifier_fingerprint",
        "alt_text",
    )
    assert {field.name for field in fields(VerifiedMediaEvidence)}.isdisjoint(
        {"source_commitment_index", "provider", "path", "deck", "model", "state_writes"}
    )

    forged = dict(media.to_json())
    forged["source_commitment_index"] = 0
    with pytest.raises(ValueError, match="fields"):
        VerifiedMediaEvidence.from_json(
            cast(Mapping[str, JsonValue], freeze_json(forged))
        )


def test_verified_media_rejects_digest_mismatch_and_malformed_metadata() -> None:
    digest = "e" * 64
    base = VerifiedMediaEvidence(
        "opaque-media",
        "opaque-evidence",
        BlobId(f"sha256:{digest}"),
        digest,
        Citation(
            SourceId("fixture-source"),
            RevisionId("fixture-revision"),
            ChunkId("fixture-chunk"),
            0,
            4,
            "Atlas > figure",
            "Root",
        ),
        "trusted_media",
        "1.0.0",
        "f" * 64,
        "A labelled root.",
    )

    with pytest.raises(ValueError, match="match"):
        replace(base, sha256="a" * 64)
    with pytest.raises(ValueError, match="portable"):
        replace(base, verifier_id="Provider Specific")
    with pytest.raises(ValueError, match="HTML"):
        replace(base, alt_text="<b>Root</b>")
