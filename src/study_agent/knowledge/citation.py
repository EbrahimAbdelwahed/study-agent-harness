"""The single citation verifier. Evidence resolves from canonical bytes only.

The verifier takes the bytes it is asked to trust as explicit arguments and
performs no I/O itself, so no index text, snippet, or cached projection can
reach it. Every check fails closed with a typed reason.

**Caller obligation.** ``substrate_id`` is a hash of content bytes only, so it
carries no source or revision binding. The only thing tying a citation to a
source and revision is the ``RetrievableUnit`` the caller supplies. That unit
MUST be looked up by ``citation.unit_id`` in the canonical unit registry for
its revision; it must never be reconstructed from connector, request, or model
input. A fabricated but internally consistent unit will verify here, and
catching that is the job of the KB-05 binding gate, not of this module.

For the same reason, ``DerivedRef.subject`` is not verified when a derived
reference is constructed: a consumer that shows a subject citation as
grounding must verify it here first.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from study_agent.domain.citation_v2 import (
    TEXT_CITATION_VERSION,
    Citation,
    CitationFailure,
    CitationFailureKind,
    DerivedRef,
    FigureCitationV1,
    TextCitationV2,
)
from study_agent.domain.identifiers import substrate_id_for
from study_agent.domain.lineage import RevisionRef, SelectionStatus
from study_agent.domain.source import Citation as LegacyCitation
from study_agent.domain.units import RetrievableUnit, TextSpan


@dataclass(frozen=True, slots=True)
class ResolvedCitation:
    """A verified citation plus the revision status a reader must see."""

    citation: Citation
    text: str | None
    selection_status: SelectionStatus
    successor: RevisionRef | None = None

    @property
    def is_superseded(self) -> bool:
        return self.successor is not None

    @property
    def is_current(self) -> bool:
        return self.selection_status is SelectionStatus.CURRENT


def _fail(kind: CitationFailureKind, message: str) -> CitationFailure:
    return CitationFailure(kind, message)


def verify_text_citation(
    citation: TextCitationV2,
    *,
    substrate_bytes: bytes,
    unit: RetrievableUnit,
    selection_status: SelectionStatus,
    successor: RevisionRef | None = None,
) -> ResolvedCitation:
    """Resolve one text citation against the substrate bytes and its unit."""
    if isinstance(citation, DerivedRef):
        raise _fail(CitationFailureKind.NOT_A_CITATION, "derived text is not evidence")
    if not isinstance(citation, TextCitationV2):
        raise _fail(
            CitationFailureKind.UNSUPPORTED_VERSION,
            "only TextCitationV2 resolves through this verifier",
        )
    if citation.version != TEXT_CITATION_VERSION:
        raise _fail(CitationFailureKind.UNSUPPORTED_VERSION, "unknown citation version")
    if not isinstance(substrate_bytes, bytes) or not substrate_bytes:
        raise _fail(CitationFailureKind.MISSING, "substrate bytes were not supplied")

    text = _canonical_text(substrate_bytes)
    if substrate_id_for(substrate_bytes) != citation.substrate_id:
        raise _fail(
            CitationFailureKind.CORRUPT, "substrate bytes do not match substrate_id"
        )

    _require_unit_agreement(citation, unit)
    span = unit.canonical_ref
    if not isinstance(span, TextSpan):
        raise _fail(
            CitationFailureKind.REFERENCE_MISMATCH,
            "a text citation cannot resolve against a figure unit",
        )
    if span.substrate_id != citation.substrate_id:
        raise _fail(
            CitationFailureKind.REFERENCE_MISMATCH,
            "unit and citation reference different substrates",
        )
    if citation.end > len(text):
        raise _fail(CitationFailureKind.MALFORMED_SPAN, "span exceeds the substrate")
    if citation.start < span.start or citation.end > span.end:
        raise _fail(CitationFailureKind.OUT_OF_UNIT, "span escapes its unit")

    quoted = text[citation.start : citation.end]
    if sha256(quoted.encode("utf-8")).hexdigest() != citation.quoted_sha256:
        raise _fail(
            CitationFailureKind.MISMATCHED_CHECKSUM,
            "quoted bytes do not match the citation checksum",
        )
    return ResolvedCitation(citation, quoted, selection_status, successor)


def verify_figure_citation(
    citation: FigureCitationV1,
    *,
    image_bytes: bytes,
    selection_status: SelectionStatus,
    successor: RevisionRef | None = None,
) -> ResolvedCitation:
    """Resolve one figure citation against the image bytes themselves."""
    if isinstance(citation, DerivedRef):
        raise _fail(CitationFailureKind.NOT_A_CITATION, "derived text is not evidence")
    if not isinstance(citation, FigureCitationV1):
        raise _fail(
            CitationFailureKind.UNSUPPORTED_VERSION,
            "only FigureCitationV1 resolves through this verifier",
        )
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise _fail(CitationFailureKind.MISSING, "image bytes were not supplied")
    if len(image_bytes) != citation.byte_length:
        raise _fail(CitationFailureKind.CORRUPT, "image length does not match the citation")
    if sha256(image_bytes).hexdigest() != citation.figure_sha256:
        raise _fail(
            CitationFailureKind.MISMATCHED_CHECKSUM,
            "image bytes do not match the figure hash",
        )
    # anchor_unit_id and page_hint are links and hints; they are deliberately
    # not part of image identity and are never verified as such.
    return ResolvedCitation(citation, None, selection_status, successor)


def _canonical_text(substrate_bytes: bytes) -> str:
    """Decode canonical bytes, converting every Unicode failure into a typed one."""
    try:
        return substrate_bytes.decode("utf-8", errors="strict")
    except (UnicodeDecodeError, AttributeError) as error:
        raise _fail(CitationFailureKind.CORRUPT, "substrate is not valid UTF-8") from error


def _quoted_digest(value: str, reason: str) -> str:
    try:
        return sha256(value.encode("utf-8")).hexdigest()
    except UnicodeEncodeError as error:
        raise _fail(CitationFailureKind.CORRUPT, reason) from error


def _require_unit_agreement(citation: TextCitationV2, unit: RetrievableUnit) -> None:
    if not isinstance(unit, RetrievableUnit):
        raise _fail(CitationFailureKind.MISSING, "the citing unit was not supplied")
    if unit.unit_id != citation.unit_id:
        raise _fail(CitationFailureKind.REFERENCE_MISMATCH, "unit_id does not match")
    if unit.source_id != citation.source_id:
        raise _fail(CitationFailureKind.REFERENCE_MISMATCH, "source_id does not match")
    if unit.revision_id != citation.revision_id:
        raise _fail(CitationFailureKind.REFERENCE_MISMATCH, "revision_id does not match")


def text_citation_for(
    unit: RetrievableUnit,
    *,
    substrate_bytes: bytes,
    start: int,
    end: int,
    locator: str | None = None,
    page_hint: int | None = None,
) -> TextCitationV2:
    """Mint a citation from canonical bytes, never from caller-supplied text."""
    if not isinstance(unit.canonical_ref, TextSpan):
        raise _fail(
            CitationFailureKind.REFERENCE_MISMATCH,
            "only a text unit can produce a text citation",
        )
    text = _canonical_text(substrate_bytes)
    if start < 0 or end <= start or end > len(text):
        raise _fail(CitationFailureKind.MALFORMED_SPAN, "span is outside the substrate")
    citation = TextCitationV2(
        unit.source_id,
        unit.revision_id,
        unit.unit_id,
        unit.canonical_ref.substrate_id,
        start,
        end,
        _quoted_digest(text[start:end], "canonical bytes are not encodable"),
        locator,
        page_hint,
    )
    # Minting goes through the same gate as reading, so a caller cannot mint a
    # citation this verifier would reject for the same unit. It does not, and
    # cannot, establish that the unit itself is authentic; see the module
    # docstring.
    verify_text_citation(
        citation,
        substrate_bytes=substrate_bytes,
        unit=unit,
        selection_status=SelectionStatus.CURRENT,
    )
    return citation


def upgrade_v1_citation(
    legacy: LegacyCitation,
    *,
    unit: RetrievableUnit,
    substrate_bytes: bytes,
) -> TextCitationV2:
    """Upgrade a v0.1 citation, refusing to guess any missing binding.

    v0.1 citations name a chunk, not a unit or a substrate, so the caller must
    supply the migrated unit. The v0.1 snippet, when present, must match the
    canonical bytes exactly; a mismatch is a migration failure, never a silent
    re-anchor. The v0.1 contract itself is untouched and stays readable.
    """
    if not isinstance(legacy, LegacyCitation):
        raise _fail(CitationFailureKind.UNSUPPORTED_VERSION, "expected a v0.1 Citation")
    if legacy.source_id != unit.source_id or legacy.revision_id != unit.revision_id:
        raise _fail(
            CitationFailureKind.REFERENCE_MISMATCH,
            "the supplied unit does not belong to the legacy citation",
        )
    upgraded = text_citation_for(
        unit,
        substrate_bytes=substrate_bytes,
        start=legacy.start_offset,
        end=legacy.end_offset,
        locator=legacy.locator,
    )
    if legacy.quoted_snippet is not None:
        expected = _quoted_digest(
            legacy.quoted_snippet, "the v0.1 snippet is not encodable UTF-8"
        )
        if expected != upgraded.quoted_sha256:
            raise _fail(
                CitationFailureKind.MISMATCHED_CHECKSUM,
                "the v0.1 snippet does not match the canonical bytes",
            )
    return upgraded


__all__ = [
    "ResolvedCitation",
    "text_citation_for",
    "upgrade_v1_citation",
    "verify_figure_citation",
    "verify_text_citation",
]
