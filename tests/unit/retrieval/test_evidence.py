from __future__ import annotations

from dataclasses import replace

import pytest

from study_agent.domain import (
    DialectProfile,
    HeadingSyntax,
    RevisionId,
    SourceId,
    TextSpan,
    UnitKind,
    UnitMeta,
    unit_id_for,
)
from study_agent.domain.identifiers import ScopeId, substrate_id_for
from study_agent.domain.units import RetrievableUnit
from study_agent.knowledge.projections import project_structural
from study_agent.knowledge.tree import admit_tree, build_document_tree
from study_agent.ports.knowledge import LexicalProjectionBinding
from study_agent.retrieval.evidence import EvidenceCatalog


def test_catalog_rejects_binding_that_is_not_its_canonical_unit() -> None:
    text = "# Document\ncanonical text\n"
    substrate = substrate_id_for(text.encode())
    profile = DialectProfile("markdown", "v1", heading_syntax=HeadingSyntax.ATX)
    tree = admit_tree(build_document_tree(text, profile, substrate_id=substrate), text, profile)
    reference = TextSpan(substrate, 0, len(text))
    unit = RetrievableUnit(
        unit_id_for(
            revision_id=RevisionId("revision"),
            structural_path=("document",),
            unit_kind=UnitKind.PASSAGE.value,
            granularity=3,
            canonical_ref=reference.to_json(),
            unitizer_version="unitizer-v1",
        ),
        SourceId("source"),
        RevisionId("revision"),
        UnitKind.PASSAGE,
        3,
        ("document",),
        reference,
        UnitMeta("notes", "primary", 80),
    )
    forged = replace(unit, source_id=SourceId("forged-source"))
    binding = LexicalProjectionBinding(
        ScopeId("scope"), project_structural(unit, tree), forged, text.encode()
    )

    with pytest.raises(ValueError, match="not the canonical unit"):
        EvidenceCatalog((binding,), (unit,), {substrate: text.encode()})
