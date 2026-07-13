from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from study_agent.domain._validation import JsonObject
from study_agent.ports import ModelMessage
from study_agent.skills import ArtifactReference, JsonSchema, PromptLayer


class PromptCompositionError(ValueError):
    """A pinned prompt could not be composed from its declared inputs."""


@dataclass(frozen=True, slots=True)
class PromptLayerRecord:
    id: str
    version: str
    kind: str
    input_fingerprint: str


@dataclass(frozen=True, slots=True)
class ComposedPrompt:
    prompt: ArtifactReference
    messages: tuple[ModelMessage, ...]
    layers: tuple[PromptLayerRecord, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "messages", tuple(self.messages))
        object.__setattr__(self, "layers", tuple(self.layers))
        if not self.messages or len(self.messages) != len(self.layers):
            raise ValueError("composed prompt messages and layers must align")


class PromptComposer(Protocol):
    def compose(
        self,
        *,
        prompt: ArtifactReference,
        layers: tuple[PromptLayer, ...],
        inputs: JsonObject,
        output_schema: JsonSchema,
    ) -> ComposedPrompt: ...
