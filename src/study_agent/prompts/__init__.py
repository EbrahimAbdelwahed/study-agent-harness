"""Versioned prompt definitions and deterministic composition."""

from .assess_understanding_v1 import (
    ASSESS_UNDERSTANDING_LAYERS,
    ASSESS_UNDERSTANDING_PROMPT,
)
from .composer import CanonicalPromptComposer, canonical_json
from .contracts import (
    ComposedPrompt,
    PromptComposer,
    PromptCompositionError,
    PromptLayerRecord,
)
from .explain_concept_v1 import EXPLAIN_CONCEPT_LAYERS, EXPLAIN_CONCEPT_PROMPT
from .grounded_answer_v1 import GROUNDED_ANSWER_LAYERS, GROUNDED_ANSWER_PROMPT

__all__ = [
    "ASSESS_UNDERSTANDING_LAYERS",
    "ASSESS_UNDERSTANDING_PROMPT",
    "EXPLAIN_CONCEPT_LAYERS",
    "EXPLAIN_CONCEPT_PROMPT",
    "GROUNDED_ANSWER_LAYERS",
    "GROUNDED_ANSWER_PROMPT",
    "CanonicalPromptComposer",
    "ComposedPrompt",
    "PromptComposer",
    "PromptCompositionError",
    "PromptLayerRecord",
    "canonical_json",
]
