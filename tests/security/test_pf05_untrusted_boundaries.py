from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

import pytest

import study_agent.api.sources as sources_api
import study_agent.application.errors as application_errors
from study_agent.api.authority import HarnessError, ValidationFailure
from study_agent.api.sources import SourceRevision, citation_from_bytes
from study_agent.domain import ChunkId, Citation
from study_agent.domain.citation_v2 import CitationFailure, CitationFailureKind
from study_agent.ingestion import decode_source_revision_event
from tests.support.pf05.fixtures import make_source_revision, make_unit
from tests.unit.ingestion.test_source_revision_state import _replace_source, make_event


class _MissingLegacyBinding:
    def resolve(self, source_id: object, revision_id: object, chunk_id: object) -> None:
        del source_id, revision_id, chunk_id
        return None


def test_legacy_source_event_upcasts_unbound_title_trust_and_role_forgery() -> None:
    event, load_blob = make_event(legacy_identity=True)
    forged = _replace_source(
        event,
        title="Trusted forged title",
        trust_level=100,
        source_role="authoritative-primary",
    )

    decoded = decode_source_revision_event(forged, load_blob)

    assert decoded.source.title == "Legacy source"
    assert decoded.source.trust_level == 0
    assert decoded.source.source_role == "legacy-unverified"


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

    upgrade = getattr(sources_api, "upgrade_legacy_citation", None)
    assert callable(upgrade)
    with pytest.raises(HarnessError) as error:
        cast(Callable[..., object], upgrade)(
            forged,
            bindings=_MissingLegacyBinding(),
        )

    assert isinstance(error.value, ValidationFailure)
    details = error.value.to_json()["details"]
    assert isinstance(details, dict)
    assert details["reason_kind"] == "reference_mismatch"


def test_citation_decoder_bounds_deep_json_as_a_typed_corruption() -> None:
    nested = b'{"version":2,"nested":' + b"[" * 20_000 + b"0" + b"]" * 20_000 + b"}"

    with pytest.raises(HarnessError) as error:
        citation_from_bytes(nested)

    assert isinstance(error.value, ValidationFailure)
    details = error.value.to_json()["details"]
    assert isinstance(details, dict)
    assert details["reason_kind"] == "corrupt"


def test_source_metadata_bounds_reject_deep_values_without_recursion_escape() -> None:
    nested: object = "leaf"
    for _ in range(1_100):
        nested = {"nested": nested}

    with pytest.raises(ValueError):
        make_source_revision(metadata={"nested": nested})


def test_source_metadata_bounds_reject_oversized_strings() -> None:
    with pytest.raises(ValueError):
        make_source_revision(metadata={"payload": "x" * 20_000})


@pytest.mark.parametrize("value", [0.0, -0.0, float("nan"), float("inf"), -float("inf")])
def test_source_metadata_rejects_float_and_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError):
        make_source_revision(metadata={"weight": value})


def test_revision_decoder_rejects_created_at_provenance_forgery() -> None:
    original = make_source_revision()
    forged = dict(original.to_json())
    forged["created_at"] = datetime(2099, 1, 1, tzinfo=UTC).isoformat(
        timespec="microseconds"
    )

    decode = cast(Callable[..., SourceRevision], SourceRevision.from_json)
    with pytest.raises(ValueError, match=r"created_at|provenance"):
        decode(forged, receipt_created_at=original.created_at)


@pytest.mark.parametrize(
    ("payload", "reason_kind"),
    [(b"not-json", "corrupt"), (b'{"version":99}', "unsupported_version")],
)
def test_public_citation_failures_are_closed_harness_errors(
    payload: bytes, reason_kind: str
) -> None:
    with pytest.raises(HarnessError) as caught:
        citation_from_bytes(payload)

    assert isinstance(caught.value, ValidationFailure)
    encoded = caught.value.serialize()
    assert len(encoded) <= 16 * 1024
    assert payload.decode() not in encoded.decode()
    details = caught.value.to_json()["details"]
    assert isinstance(details, dict)
    assert details["reason_kind"] == reason_kind


@pytest.mark.parametrize("kind", tuple(CitationFailureKind))
def test_private_citation_failure_mapping_is_exhaustive_and_safe(
    kind: CitationFailureKind,
) -> None:
    error = CitationFailure(kind, "Bearer sk-test-secret")
    mapper = getattr(application_errors, "citation_failure_to_harness_error", None)
    assert callable(mapper)
    translated = cast(Callable[..., HarnessError], mapper)(
        error,
        correlation_id="citation-correlation",
    )

    assert type(translated) is ValidationFailure
    payload = translated.to_json()
    assert payload["message"] == "citation failed validation"
    assert payload["retryable"] is False
    assert payload["correlation_id"] == "citation-correlation"
    details = payload["details"]
    assert isinstance(details, dict)
    assert details["reason_kind"] == kind.value
    assert "sk-test-secret" not in json.dumps(payload)
    assert translated.__cause__ is error


def test_public_sources_facade_does_not_export_private_citation_failures() -> None:
    assert "CitationFailure" not in sources_api.__all__
    assert "CitationFailureKind" not in sources_api.__all__
