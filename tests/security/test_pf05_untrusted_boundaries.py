from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from study_agent.api.authority import HarnessError, ValidationFailure
from study_agent.api.sources import (
    CitationFailure,
    CitationFailureKind,
    SourceRevision,
    citation_from_bytes,
)
from study_agent.application.errors import translate_exception
from study_agent.domain import ChunkId, Citation
from study_agent.domain.citation_v2 import citation_from_bytes as decode_citation_bytes
from study_agent.ingestion import decode_source_revision_event
from study_agent.knowledge.citation import upgrade_v1_citation
from tests.support.pf05.fixtures import BYTES, make_source_revision, make_unit
from tests.unit.ingestion.test_source_revision_state import _replace_source, make_event


def test_legacy_source_event_rejects_unbound_title_trust_and_role_forgery() -> None:
    event, load_blob = make_event(legacy_identity=True)
    forged = _replace_source(
        event,
        title="Trusted forged title",
        trust_level=100,
        source_role="authoritative-primary",
    )

    with pytest.raises(ValueError, match=r"revision_id|legacy|metadata"):
        decode_source_revision_event(forged, load_blob)


def test_v01_upgrade_rejects_a_legacy_chunk_without_a_trusted_mapping() -> None:
    unit = make_unit()
    forged = Citation(
        unit.source_id,
        unit.revision_id,
        ChunkId("chunk-sha256:" + "0" * 64),
        0,
        4,
        "unknown chunk",
        None,
    )

    with pytest.raises(CitationFailure) as error:
        upgrade_v1_citation(forged, unit=unit, substrate_bytes=BYTES)

    assert error.value.kind is CitationFailureKind.REFERENCE_MISMATCH


def test_citation_decoder_bounds_deep_json_as_a_typed_corruption() -> None:
    nested = b'{"version":2,"nested":' + b"[" * 20_000 + b"0" + b"]" * 20_000 + b"}"

    with pytest.raises(CitationFailure) as error:
        decode_citation_bytes(nested)

    assert error.value.kind is CitationFailureKind.CORRUPT


def test_source_metadata_bounds_reject_deep_values_without_recursion_escape() -> None:
    nested: object = "leaf"
    for _ in range(1_100):
        nested = {"nested": nested}

    with pytest.raises(ValueError):
        make_source_revision(metadata={"nested": nested})


def test_source_metadata_bounds_reject_oversized_strings() -> None:
    with pytest.raises(ValueError):
        make_source_revision(metadata={"payload": "x" * 20_000})


def test_equal_metadata_values_converge_on_one_revision_identity_for_negative_zero() -> None:
    positive_zero = make_source_revision(metadata={"weight": 0.0})
    negative_zero = make_source_revision(metadata={"weight": -0.0})

    assert positive_zero.metadata == negative_zero.metadata
    assert positive_zero.revision_id == negative_zero.revision_id


def test_revision_decoder_rejects_created_at_provenance_forgery() -> None:
    original = make_source_revision()
    forged = dict(original.to_json())
    forged["created_at"] = datetime(2099, 1, 1, tzinfo=UTC).isoformat(
        timespec="microseconds"
    )

    with pytest.raises(ValueError, match=r"created_at|provenance"):
        SourceRevision.from_json(forged)


@pytest.mark.parametrize("payload", [b"not-json", b'{"version":99}'])
def test_public_citation_failures_are_closed_harness_errors(payload: bytes) -> None:
    with pytest.raises(HarnessError) as caught:
        citation_from_bytes(payload)

    assert isinstance(caught.value, ValidationFailure)
    encoded = caught.value.serialize()
    assert len(encoded) <= 16 * 1024
    assert payload.decode() not in encoded.decode()


@pytest.mark.parametrize("kind", tuple(CitationFailureKind))
def test_every_citation_failure_kind_survives_as_bounded_safe_detail(
    kind: CitationFailureKind,
) -> None:
    translated = translate_exception(CitationFailure(kind, "Bearer sk-test-secret"))

    assert isinstance(translated, HarnessError)
    details = translated.to_json()["details"]
    assert isinstance(details, dict)
    assert details["citation_kind"] == kind.value
    assert "sk-test-secret" not in json.dumps(translated.to_json())
