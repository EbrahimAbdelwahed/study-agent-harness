"""Strict transient flashcard candidates produced by verified playbook runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from study_agent.domain import (
    MorphologyCognitiveFunction,
    MorphologyFamily,
    RetrievalForm,
)
from study_agent.domain._validation import JsonObject, JsonValue, freeze_object, require_text


class FlashcardPedagogicalRole(StrEnum):
    OVERVIEW = "overview"
    SECTION = "section"
    DETAIL = "detail"
    MACRO_RECONSTRUCTION = "macro_reconstruction"
    ATOMIC_DISCRIMINATION = "atomic_discrimination"


_HYBRID_ROLES = frozenset(
    {
        FlashcardPedagogicalRole.OVERVIEW,
        FlashcardPedagogicalRole.SECTION,
        FlashcardPedagogicalRole.DETAIL,
    }
)
_MORPHOLOGY_ROLES = frozenset(
    {
        FlashcardPedagogicalRole.MACRO_RECONSTRUCTION,
        FlashcardPedagogicalRole.ATOMIC_DISCRIMINATION,
    }
)


@dataclass(frozen=True, slots=True)
class FlashcardAnswerBlock:
    label: str
    text: str
    key_points: tuple[str, ...]

    def __post_init__(self) -> None:
        _bounded_text(self.label, "answer block label", 200, reject_html=True)
        _bounded_text(self.text, "answer block text", 4000, reject_html=True)
        points = _unique_texts(self.key_points, "answer block key points", 12, 4000)
        object.__setattr__(self, "key_points", points)

    def to_json(self) -> JsonObject:
        return freeze_object(
            {"label": self.label, "text": self.text, "key_points": self.key_points}
        )

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> FlashcardAnswerBlock:
        _exact(value, {"label", "text", "key_points"}, "answer block")
        return cls(
            _string(value, "label"),
            _string(value, "text"),
            _string_tuple(value, "key_points"),
        )


@dataclass(frozen=True, slots=True)
class FlashcardCandidate:
    candidate_key: str
    parent_candidate_key: str | None
    retrieval_form: RetrievalForm
    prompt: str
    answer_blocks: tuple[FlashcardAnswerBlock, ...]
    pedagogical_role: FlashcardPedagogicalRole
    morphology_family: MorphologyFamily | None
    cognitive_function: MorphologyCognitiveFunction | None
    rationale: str
    evidence_ids: tuple[str, ...]
    media_evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _bounded_text(self.candidate_key, "candidate key", 128)
        _reject_canonical_identity(self.candidate_key, "candidate key")
        if self.parent_candidate_key is not None:
            _bounded_text(self.parent_candidate_key, "parent candidate key", 128)
            _reject_canonical_identity(self.parent_candidate_key, "parent candidate key")
            if self.parent_candidate_key == self.candidate_key:
                raise ValueError("candidate cannot be its own parent")
        if not isinstance(self.retrieval_form, RetrievalForm):
            raise TypeError("candidate retrieval form must use RetrievalForm")
        _bounded_text(self.prompt, "candidate prompt", 4000, reject_html=True)
        blocks = tuple(self.answer_blocks)
        if not 1 <= len(blocks) <= 8 or not all(
            isinstance(item, FlashcardAnswerBlock) for item in blocks
        ):
            raise ValueError("candidate answer blocks must contain 1..8 records")
        object.__setattr__(self, "answer_blocks", blocks)
        if not isinstance(self.pedagogical_role, FlashcardPedagogicalRole):
            raise TypeError("candidate role must use FlashcardPedagogicalRole")
        if self.pedagogical_role in _HYBRID_ROLES:
            if self.morphology_family is not None or self.cognitive_function is not None:
                raise ValueError("hybrid candidates forbid morphology fields")
        elif self.pedagogical_role in _MORPHOLOGY_ROLES and (
            not isinstance(self.morphology_family, MorphologyFamily) or not isinstance(
                self.cognitive_function, MorphologyCognitiveFunction
            )
        ):
            raise ValueError("morphology candidates require family and cognitive function")
        _bounded_text(self.rationale, "candidate rationale", 4000, reject_html=True)
        evidence_ids = _unique_texts(
            self.evidence_ids, "candidate evidence ids", 16, 256
        )
        if not evidence_ids:
            raise ValueError("candidate evidence ids must contain 1..16 handles")
        for evidence_id in evidence_ids:
            _reject_receipt_handle(evidence_id, "candidate evidence id")
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(
            self,
            "media_evidence_ids",
            _unique_texts(
                self.media_evidence_ids, "candidate media evidence ids", 8, 256
            ),
        )
        for evidence_id in self.media_evidence_ids:
            _reject_receipt_handle(evidence_id, "candidate media evidence id")
            _reject_media_filename(evidence_id)

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "candidate_key": self.candidate_key,
                "parent_candidate_key": self.parent_candidate_key,
                "retrieval_form": self.retrieval_form.value,
                "prompt": self.prompt,
                "answer_blocks": tuple(item.to_json() for item in self.answer_blocks),
                "pedagogical_role": self.pedagogical_role.value,
                "morphology_family": (
                    self.morphology_family.value if self.morphology_family else None
                ),
                "cognitive_function": (
                    self.cognitive_function.value if self.cognitive_function else None
                ),
                "rationale": self.rationale,
                "evidence_ids": self.evidence_ids,
                "media_evidence_ids": self.media_evidence_ids,
            }
        )

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> FlashcardCandidate:
        _exact(
            value,
            {
                "candidate_key",
                "parent_candidate_key",
                "retrieval_form",
                "prompt",
                "answer_blocks",
                "pedagogical_role",
                "morphology_family",
                "cognitive_function",
                "rationale",
                "evidence_ids",
                "media_evidence_ids",
            },
            "flashcard candidate",
        )
        parent = _optional_string(value, "parent_candidate_key")
        family = _optional_string(value, "morphology_family")
        function = _optional_string(value, "cognitive_function")
        raw_blocks = _array(value, "answer_blocks")
        return cls(
            candidate_key=_string(value, "candidate_key"),
            parent_candidate_key=parent,
            retrieval_form=RetrievalForm(_string(value, "retrieval_form")),
            prompt=_string(value, "prompt"),
            answer_blocks=tuple(
                FlashcardAnswerBlock.from_json(_mapping(item, "answer block"))
                for item in raw_blocks
            ),
            pedagogical_role=FlashcardPedagogicalRole(
                _string(value, "pedagogical_role")
            ),
            morphology_family=MorphologyFamily(family) if family else None,
            cognitive_function=(
                MorphologyCognitiveFunction(function) if function else None
            ),
            rationale=_string(value, "rationale"),
            evidence_ids=_string_tuple(value, "evidence_ids"),
            media_evidence_ids=_string_tuple(value, "media_evidence_ids"),
        )


@dataclass(frozen=True, slots=True)
class FlashcardOmission:
    reason: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _bounded_text(self.reason, "omission reason", 1000, reject_html=True)
        evidence_ids = _unique_texts(
            self.evidence_ids, "omission evidence ids", 16, 256
        )
        for evidence_id in evidence_ids:
            _reject_receipt_handle(evidence_id, "omission evidence id")
        object.__setattr__(
            self,
            "evidence_ids",
            evidence_ids,
        )

    def to_json(self) -> JsonObject:
        return freeze_object({"reason": self.reason, "evidence_ids": self.evidence_ids})

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> FlashcardOmission:
        _exact(value, {"reason", "evidence_ids"}, "flashcard omission")
        return cls(_string(value, "reason"), _string_tuple(value, "evidence_ids"))


@dataclass(frozen=True, slots=True)
class FlashcardCandidateBatch:
    candidates: tuple[FlashcardCandidate, ...]
    omissions: tuple[FlashcardOmission, ...]

    def __post_init__(self) -> None:
        candidates = tuple(self.candidates)
        omissions = tuple(self.omissions)
        if len(candidates) > 24 or not all(
            isinstance(item, FlashcardCandidate) for item in candidates
        ):
            raise ValueError("candidate batch must contain 0..24 candidates")
        if len(omissions) > 24 or not all(
            isinstance(item, FlashcardOmission) for item in omissions
        ):
            raise ValueError("candidate batch must contain 0..24 omissions")
        if len(set(omissions)) != len(omissions):
            raise ValueError("candidate batch omissions must be unique")
        keys = tuple(item.candidate_key for item in candidates)
        if len(set(keys)) != len(keys):
            raise ValueError("candidate keys must be unique")
        seen: set[str] = set()
        for candidate in candidates:
            parent = candidate.parent_candidate_key
            if parent is not None and parent not in seen:
                raise ValueError("candidate parent must name a lower same-batch candidate")
            seen.add(candidate.candidate_key)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "omissions", omissions)

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "candidates": tuple(item.to_json() for item in self.candidates),
                "omissions": tuple(item.to_json() for item in self.omissions),
            }
        )

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_json())

    @classmethod
    def from_json(cls, value: Mapping[str, JsonValue]) -> FlashcardCandidateBatch:
        _exact(value, {"candidates", "omissions"}, "flashcard candidate batch")
        raw_candidates = _array(value, "candidates")
        candidate_objects = tuple(
            _mapping(item, "flashcard candidate") for item in raw_candidates
        )
        candidate_keys = tuple(
            _string(candidate, "candidate_key") for candidate in candidate_objects
        )
        if len(set(candidate_keys)) != len(candidate_keys):
            raise ValueError("candidate keys must be unique")
        return cls(
            tuple(
                FlashcardCandidate.from_json(item) for item in candidate_objects
            ),
            tuple(
                FlashcardOmission.from_json(_mapping(item, "flashcard omission"))
                for item in _array(value, "omissions")
            ),
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> FlashcardCandidateBatch:
        decoded: Any = json.loads(data)
        if not isinstance(decoded, dict):
            raise ValueError("flashcard candidate batch must be a JSON object")
        batch = cls.from_json(cast(dict[str, JsonValue], decoded))
        if batch.to_bytes() != data:
            raise ValueError("flashcard candidate batch bytes are not canonical")
        return batch


def _bounded_text(value: str, name: str, maximum: int, *, reject_html: bool = False) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    require_text(value, name)
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")
    if reject_html and ("<" in value or ">" in value):
        raise ValueError(f"{name} cannot contain raw HTML")


def _unique_texts(
    values: tuple[str, ...], name: str, maximum_items: int, maximum_length: int
) -> tuple[str, ...]:
    items = tuple(values)
    if len(items) > maximum_items:
        raise ValueError(f"{name} exceeds {maximum_items} items")
    for item in items:
        _bounded_text(item, f"{name} item", maximum_length, reject_html=True)
    if len(set(items)) != len(items):
        raise ValueError(f"{name} must be unique")
    return items


def _reject_canonical_identity(value: str, name: str) -> None:
    lowered = value.lower()
    if "-sha256:" in lowered or lowered.startswith("sha256:"):
        raise ValueError(f"{name} must be temporary, not canonical")


def _reject_media_filename(value: str) -> None:
    if "." in value or "/" in value or "\\" in value:
        raise ValueError("media evidence ids must be opaque handles, not filenames")


def _reject_receipt_handle(value: str, name: str) -> None:
    lowered = value.lower()
    canonical_names = ("source", "revision", "chunk", "blob", "digest", "verifier")
    canonical_prefixes = tuple(
        f"{prefix}{separator}"
        for prefix in canonical_names
        for separator in (":", "-", "_", ".", "/", "\\")
    )
    if (
        lowered in canonical_names
        or lowered.startswith(canonical_prefixes)
        or lowered.startswith("sha256:")
        or "-sha256:" in lowered
        or (len(lowered) == 64 and all(char in "0123456789abcdef" for char in lowered))
    ):
        raise ValueError(f"{name} must be an opaque handle, not a canonical receipt")


def _exact(value: Mapping[str, JsonValue], fields: set[str], name: str) -> None:
    if set(value) != fields:
        raise ValueError(f"{name} fields must be exactly {sorted(fields)}")


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        raise ValueError(f"{key} must be a string")
    return item


def _optional_string(value: Mapping[str, JsonValue], key: str) -> str | None:
    item = value.get(key)
    if item is not None and not isinstance(item, str):
        raise ValueError(f"{key} must be a string or null")
    return item


def _array(value: Mapping[str, JsonValue], key: str) -> tuple[JsonValue, ...]:
    item: object = value.get(key)
    if not isinstance(item, (list, tuple)):
        raise ValueError(f"{key} must be an array")
    return cast(tuple[JsonValue, ...], tuple(item))


def _string_tuple(value: Mapping[str, JsonValue], key: str) -> tuple[str, ...]:
    items = _array(value, key)
    if not all(isinstance(item, str) for item in items):
        raise ValueError(f"{key} must contain only strings")
    return cast(tuple[str, ...], items)


def _mapping(value: JsonValue, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _canonical_bytes(value: JsonObject) -> bytes:
    def plain(item: JsonValue) -> object:
        if isinstance(item, Mapping):
            return {key: plain(child) for key, child in item.items()}
        if isinstance(item, tuple):
            return [plain(child) for child in item]
        return item

    return json.dumps(
        plain(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


__all__ = [
    "FlashcardAnswerBlock",
    "FlashcardCandidate",
    "FlashcardCandidateBatch",
    "FlashcardOmission",
    "FlashcardPedagogicalRole",
]
