"""Pure knowledge-base structure owned by the offline trunk.

This package owns model-free document trees.  It performs no I/O, holds no
provider or adapter dependency, and never becomes a second byte or event
authority.
"""

from __future__ import annotations

from .tree import TREE_FORMAT_VERSION, build_document_tree
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
    "TREE_FORMAT_VERSION",
    "V01_WINDOW_CHARACTERS",
    "CitationRemap",
    "RemapReport",
    "UnitDraft",
    "UnitizerPolicy",
    "build_document_tree",
    "draft_units",
    "remap_citations",
    "unitize",
]
