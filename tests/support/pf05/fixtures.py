"""Canonical, in-memory PF-05 source/citation fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from study_agent.domain import (
    BlobId,
    BlobRef,
    RetrievableUnit,
    RevisionId,
    SourceId,
    TextCitationV2,
    TextSpan,
    UnitKind,
    UnitMeta,
    substrate_id_for,
    unit_id_for,
)
from study_agent.domain.source import SourceRevision, SubstrateRef
from study_agent.knowledge.citation import text_citation_for
from study_agent.knowledge.units import UNITIZER_VERSION

TEXT = "Café myocardium is citable by exact code-point span.\n"
BYTES = TEXT.encode("utf-8")
SOURCE_ID = SourceId("source-pf05")
REVISION_ID = RevisionId("revision-sha256:" + "1" * 64)
SUBSTRATE_ID = substrate_id_for(BYTES)


def make_blob(content: bytes) -> BlobRef:
    """Return the only valid blob reference for ``content``."""

    digest = sha256(content).hexdigest()
    return BlobRef(BlobId(f"sha256:{digest}"), digest, len(content))


def make_substrate_ref(content: bytes = BYTES) -> SubstrateRef:
    """Build a normalized substrate whose bytes and identity agree."""

    return SubstrateRef(
        substrate_id_for(content),
        make_blob(content),
        len(content.decode("utf-8")),
        "utf8-newlines-nfc-v1",
    )


def make_source_revision(
    *,
    content: bytes = BYTES,
    normalized: bytes = BYTES,
    metadata: dict[str, object] | None = None,
) -> SourceRevision:
    """Build one immutable source revision manifest."""

    return SourceRevision.create(
        source_id=SOURCE_ID,
        content=content,
        media_type="text/markdown",
        created_at=datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
        normalization_version="utf8-newlines-nfc-v1",
        substrate_id=make_substrate_ref(normalized).substrate_id,
        metadata={} if metadata is None else metadata,
    )


def make_unit(*, start: int = 0, end: int = len(TEXT)) -> RetrievableUnit:
    """Build a revision-local passage over the canonical substrate."""

    span = TextSpan(SUBSTRATE_ID, start, end)
    return RetrievableUnit(
        unit_id_for(
            revision_id=REVISION_ID,
            structural_path=("document",),
            unit_kind=UnitKind.PASSAGE.value,
            granularity=3,
            canonical_ref=span.to_json(),
            unitizer_version=UNITIZER_VERSION,
        ),
        SOURCE_ID,
        REVISION_ID,
        UnitKind.PASSAGE,
        3,
        ("document",),
        span,
        UnitMeta("lecture-notes", "primary", 90),
    )


def make_text_citation(*, start: int = 0, end: int = len(TEXT)) -> TextCitationV2:
    """Mint a citation from canonical bytes, never from fixture text."""

    return text_citation_for(
        make_unit(),
        substrate_bytes=BYTES,
        start=start,
        end=end,
    )
