"""Pure knowledge-base structure owned by the offline trunk.

This package owns model-free document trees.  It performs no I/O, holds no
provider or adapter dependency, and never becomes a second byte or event
authority.
"""

from __future__ import annotations

from .fragments import (
    MAX_CANONICAL_TEXT,
    MAX_FRAGMENTS,
    FragmentPromotionPolicy,
    draft_fragments,
    materialize_promoted_fragments,
    promoted_unit_drafts,
)
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
from .scopes import (
    SCOPE_CONFIGURED,
    SCOPE_CONFIGURED_SCHEMA_VERSION,
    SCOPE_MEMBERSHIP_CHANGED,
    SCOPE_MEMBERSHIP_SCHEMA_VERSION,
    ScopeConfigured,
    ScopeMembershipChanged,
    build_corpus_manifest,
    decode_scope_configured_event,
    decode_scope_membership_event,
    register_scope_events,
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
    unitize_drafts,
)

__all__ = [
    "DEFAULT_POLICY",
    "MAX_CANONICAL_TEXT",
    "MAX_FRAGMENTS",
    "PROJECTIONS_STATE_KEY",
    "PROJECTION_UNITS_STATE_KEY",
    "SCOPE_CONFIGURED",
    "SCOPE_CONFIGURED_SCHEMA_VERSION",
    "SCOPE_MEMBERSHIP_CHANGED",
    "SCOPE_MEMBERSHIP_SCHEMA_VERSION",
    "STRUCTURAL_PROJECTOR_NAME",
    "STRUCTURAL_PROJECTOR_VERSION",
    "TREE_FORMAT_VERSION",
    "V01_WINDOW_CHARACTERS",
    "AdmittedDocumentTree",
    "CitationRemap",
    "FragmentPromotionPolicy",
    "ProjectorPort",
    "RemapReport",
    "ScopeConfigured",
    "ScopeMembershipChanged",
    "StructuralProjector",
    "UnitDraft",
    "UnitizerPolicy",
    "admit_projection",
    "admit_tree",
    "build_corpus_manifest",
    "build_document_tree",
    "decode_scope_configured_event",
    "decode_scope_membership_event",
    "delete_all_projections",
    "delete_projections",
    "draft_fragments",
    "draft_units",
    "materialize_promoted_fragments",
    "promoted_unit_drafts",
    "project_structural",
    "projection_input_fingerprint",
    "reduce_projections",
    "register_scope_events",
    "remap_citations",
    "unitize",
    "unitize_drafts",
]
