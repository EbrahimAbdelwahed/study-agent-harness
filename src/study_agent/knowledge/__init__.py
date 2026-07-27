"""Pure knowledge-base structure owned by the offline trunk.

This package owns model-free document trees.  It performs no I/O, holds no
provider or adapter dependency, and never becomes a second byte or event
authority.
"""

from __future__ import annotations

from .projections import (
    PROJECTION_UNITS_STATE_KEY,
    PROJECTIONS_STATE_KEY,
    STRUCTURAL_PROJECTOR_NAME,
    STRUCTURAL_PROJECTOR_VERSION,
    ProjectorPort,
    StructuralProjector,
    admit_projection,
    delete_all_projections,
    delete_projections,
    project_structural,
    projection_input_fingerprint,
    reduce_projections,
)
from .tree import TREE_FORMAT_VERSION, AdmittedDocumentTree, admit_tree, build_document_tree
from .unitizer import (
    DEFAULT_POLICY,
    V01_WINDOW_CHARACTERS,
    CitationRemap,
    RemapReport,
    UnitDraft,
    UnitizerPolicy,
    draft_units,
    remap_citations,
    unitize,
)

__all__ = [
    "DEFAULT_POLICY",
    "PROJECTION_UNITS_STATE_KEY",
    "PROJECTIONS_STATE_KEY",
    "STRUCTURAL_PROJECTOR_NAME",
    "STRUCTURAL_PROJECTOR_VERSION",
    "TREE_FORMAT_VERSION",
    "AdmittedDocumentTree",
    "V01_WINDOW_CHARACTERS",
    "CitationRemap",
    "RemapReport",
    "UnitDraft",
    "UnitizerPolicy",
    "ProjectorPort",
    "StructuralProjector",
    "admit_projection",
    "admit_tree",
    "build_document_tree",
    "delete_all_projections",
    "delete_projections",
    "draft_units",
    "project_structural",
    "projection_input_fingerprint",
    "remap_citations",
    "reduce_projections",
    "unitize",
]
