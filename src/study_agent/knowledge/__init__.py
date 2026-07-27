"""Pure knowledge-base structure owned by the offline trunk.

This package owns model-free document trees.  It performs no I/O, holds no
provider or adapter dependency, and never becomes a second byte or event
authority.
"""

from __future__ import annotations

from .tree import TREE_FORMAT_VERSION, build_document_tree

__all__ = ["TREE_FORMAT_VERSION", "build_document_tree"]
