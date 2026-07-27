"""Deterministic, provider-free lexical enrichment for index projections.

The lexical projector is deliberately a derived layer.  It consumes canonical
unit text and an admitted structural projection, but it never stores or emits
canonical text.  Every choice that can change its output is represented by the
versioned :class:`LexicalPolicy` and included in the KB-08 input fingerprint.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite, log
from types import MappingProxyType
from typing import cast

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.projections import IndexProjection, ProjectorManifest
from study_agent.domain.units import RetrievableUnit, TextSpan
from study_agent.knowledge.projections import (
    STRUCTURAL_PROJECTOR_NAME,
    STRUCTURAL_PROJECTOR_VERSION,
    project_structural,
    projection_input_fingerprint,
)
from study_agent.knowledge.tree import AdmittedDocumentTree
from study_agent.state.serialization import canonical_json_bytes, canonical_json_object

LEXICAL_PROJECTOR_NAME = "lexical"
LEXICAL_PROJECTOR_VERSION = "lexical-v1"

# Version pins are separate because changing one policy dimension must be
# visible in the cache key even when the other dimensions remain unchanged.
TOKENIZATION_VERSION = "unicode-medical-word-v1"
NORMALIZATION_VERSION = "nfc-casefold-preserve-v1"
STOP_POLICY_VERSION = "explicit-stop-words-v1"
IDF_VERSION = "smooth-log-v1"
ALIAS_POLICY_VERSION = "literal-casefold-alias-v1"
CAP_POLICY_VERSION = "term-cap-stable-v1"

MAX_CORPUS_UNITS = 4_096
MAX_TEXT_CHARACTERS = 64_000
MAX_TEXT_BYTES = 512_000
MAX_TOKENS_PER_UNIT = 8_192
MAX_STOP_WORDS = 256
MAX_ALIAS_KEYS = 1_024
MAX_ALIASES_PER_KEY = 32
MAX_ALIAS_LENGTH = 128
MAX_POLICY_ID_LENGTH = 128
MAX_TERM_CAP = 32  # IndexProjection's public bound.
MAX_ALIAS_CAP = 32

_IDENTITY = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]*$")
# ``\w`` is Unicode-aware under Python's default Unicode regex semantics.  The
# explicit separator set preserves identifiers such as IL-6, H2O2, and Greek medical names
# as one term while intentionally discarding FTS/control punctuation.
_TOKEN = re.compile(r"[^\W_]+(?:[-/'\u2019\.·][^\W_]+)*", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def _identity(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    if len(value) > MAX_POLICY_ID_LENGTH or _IDENTITY.fullmatch(value) is None:
        raise ValueError(f"{name} is not a portable bounded identity")
    return value


def _normalize(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    if "\x00" in value:
        raise ValueError(f"{name} contains a NUL character")
    # NFC preserves medical Unicode distinctions (Greek letters and accents);
    # casefold gives deterministic case-insensitive matching without ASCII fold.
    return unicodedata.normalize("NFC", value).casefold()


def tokenize(value: str, *, stop_words: frozenset[str] = frozenset()) -> tuple[str, ...]:
    """Return normalized Unicode medical tokens in source order.

    No query language is parsed here.  Brackets, quotes, boolean words, and
    other search syntax are simply punctuation/data and are never executed.
    """
    normalized = _normalize(value, "text")
    tokens = tuple(_normalize(match, "token") for match in _TOKEN.findall(normalized))
    return tuple(token for token in tokens if token not in stop_words)


def _phrase_key(value: str, name: str) -> str:
    normalized = _normalize(value, name)
    return _WHITESPACE.sub(" ", normalized).strip()


def _ensure_finite(value: float, name: str) -> float:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class LexicalPolicy:
    """All lexical algorithm choices that participate in projection identity."""

    tokenization_version: str = TOKENIZATION_VERSION
    normalization_version: str = NORMALIZATION_VERSION
    stop_policy_version: str = STOP_POLICY_VERSION
    idf_version: str = IDF_VERSION
    alias_policy_version: str = ALIAS_POLICY_VERSION
    cap_policy_version: str = CAP_POLICY_VERSION
    stop_words: tuple[str, ...] = ()
    term_cap: int = 16
    alias_cap: int = 16
    max_corpus_units: int = MAX_CORPUS_UNITS
    max_text_characters: int = MAX_TEXT_CHARACTERS
    max_tokens_per_unit: int = MAX_TOKENS_PER_UNIT

    def __post_init__(self) -> None:
        for version_value, name in (
            (self.tokenization_version, "tokenization_version"),
            (self.normalization_version, "normalization_version"),
            (self.stop_policy_version, "stop_policy_version"),
            (self.idf_version, "idf_version"),
            (self.alias_policy_version, "alias_policy_version"),
            (self.cap_policy_version, "cap_policy_version"),
        ):
            _identity(version_value, name)
        if type(self.term_cap) is not int or not 0 <= self.term_cap <= MAX_TERM_CAP:
            raise ValueError(f"term_cap must be between 0 and {MAX_TERM_CAP}")
        if type(self.alias_cap) is not int or not 0 <= self.alias_cap <= MAX_ALIAS_CAP:
            raise ValueError(f"alias_cap must be between 0 and {MAX_ALIAS_CAP}")
        for limit_value, name, limit in (
            (self.max_corpus_units, "max_corpus_units", MAX_CORPUS_UNITS),
            (self.max_text_characters, "max_text_characters", MAX_TEXT_CHARACTERS),
            (self.max_tokens_per_unit, "max_tokens_per_unit", MAX_TOKENS_PER_UNIT),
        ):
            if type(limit_value) is not int or limit_value < 1 or limit_value > limit:
                raise ValueError(f"{name} must be between 1 and {limit}")
        stop_words = tuple(self.stop_words)
        if len(stop_words) > MAX_STOP_WORDS:
            raise ValueError(f"stop_words must contain at most {MAX_STOP_WORDS} entries")
        normalized = tuple(_single_token(word, "stop_words item") for word in stop_words)
        if len(set(normalized)) != len(normalized):
            raise ValueError("stop_words must be unique after normalization")
        object.__setattr__(self, "stop_words", normalized)

    @property
    def stop_set(self) -> frozenset[str]:
        return frozenset(self.stop_words)

    def to_json(self) -> JsonObject:
        return {
            "alias_cap": self.alias_cap,
            "alias_policy_version": self.alias_policy_version,
            "cap_policy_version": self.cap_policy_version,
            "idf_version": self.idf_version,
            "max_corpus_units": self.max_corpus_units,
            "max_text_characters": self.max_text_characters,
            "max_tokens_per_unit": self.max_tokens_per_unit,
            "normalization_version": self.normalization_version,
            "stop_policy_version": self.stop_policy_version,
            "stop_words": self.stop_words,
            "term_cap": self.term_cap,
            "tokenization_version": self.tokenization_version,
        }

    @classmethod
    def from_json(cls, value: JsonObject) -> LexicalPolicy:
        expected = frozenset(
            {
                "alias_cap",
                "alias_policy_version",
                "cap_policy_version",
                "idf_version",
                "max_corpus_units",
                "max_text_characters",
                "max_tokens_per_unit",
                "normalization_version",
                "stop_policy_version",
                "stop_words",
                "term_cap",
                "tokenization_version",
            }
        )
        if not isinstance(value, Mapping) or frozenset(value) != expected:
            raise ValueError("lexical policy fields mismatch")

        def text(name: str) -> str:
            raw = value.get(name)
            if not isinstance(raw, str):
                raise ValueError(f"{name} must be text")
            return raw

        def integer(name: str) -> int:
            raw = value.get(name)
            if type(raw) is not int:
                raise ValueError(f"{name} must be an integer")
            return raw

        raw_stop_words = value.get("stop_words")
        if not isinstance(raw_stop_words, tuple) or any(
            not isinstance(item, str) for item in raw_stop_words
        ):
            raise ValueError("stop_words must be an array of strings")
        return cls(
            tokenization_version=text("tokenization_version"),
            normalization_version=text("normalization_version"),
            stop_policy_version=text("stop_policy_version"),
            idf_version=text("idf_version"),
            alias_policy_version=text("alias_policy_version"),
            cap_policy_version=text("cap_policy_version"),
            stop_words=cast(tuple[str, ...], raw_stop_words),
            term_cap=integer("term_cap"),
            alias_cap=integer("alias_cap"),
            max_corpus_units=integer("max_corpus_units"),
            max_text_characters=integer("max_text_characters"),
            max_tokens_per_unit=integer("max_tokens_per_unit"),
        )

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> LexicalPolicy:
        value = canonical_json_object(data)
        if canonical_json_bytes(value) != data:
            raise ValueError("lexical policy bytes are not canonical")
        return cls.from_json(value)

    @property
    def fingerprint(self) -> str:
        return sha256(
            b"study-agent/lexical-policy/v1\0" + canonical_json_bytes(self.to_json())
        ).hexdigest()


DEFAULT_POLICY = LexicalPolicy()


@dataclass(frozen=True, slots=True)
class LexicalCorpusItem:
    """One immutable unit, canonical text slice, and admitted structure."""

    unit: RetrievableUnit
    structural_projection: IndexProjection
    canonical_text: str
    admitted_tree: AdmittedDocumentTree

    def __post_init__(self) -> None:
        if not isinstance(self.unit, RetrievableUnit):
            raise TypeError("unit must be RetrievableUnit")
        if not isinstance(self.structural_projection, IndexProjection):
            raise TypeError("structural_projection must be IndexProjection")
        if self.structural_projection.unit_id != self.unit.unit_id:
            raise ValueError("structural projection must belong to the unit")
        if self.structural_projection.projector_name != STRUCTURAL_PROJECTOR_NAME:
            raise ValueError("lexical projection requires a structural projection")
        if self.structural_projection.projector_version != STRUCTURAL_PROJECTOR_VERSION:
            raise ValueError("lexical projection requires the current structural projector")
        if self.structural_projection.model_id is not None:
            raise ValueError("structural projection must be offline")
        if (
            self.structural_projection.summary is not None
            or self.structural_projection.key_terms
            or self.structural_projection.aliases
            or self.structural_projection.covers
        ):
            raise ValueError("structural projection must not contain lexical/model terms")
        if not isinstance(self.canonical_text, str):
            raise TypeError("canonical_text must be text")
        if len(self.canonical_text) > MAX_TEXT_CHARACTERS:
            raise ValueError(f"canonical_text exceeds {MAX_TEXT_CHARACTERS} characters")
        encoded_length = len(self.canonical_text.encode("utf-8"))
        if encoded_length > MAX_TEXT_BYTES:
            raise ValueError(f"canonical_text exceeds {MAX_TEXT_BYTES} UTF-8 bytes")
        if "\x00" in self.canonical_text:
            raise ValueError("canonical_text contains a NUL character")
        if not isinstance(self.admitted_tree, AdmittedDocumentTree):
            raise TypeError("admitted_tree must be AdmittedDocumentTree")
        expected_structural = project_structural(self.unit, self.admitted_tree)
        if expected_structural != self.structural_projection:
            raise ValueError("structural projection fails admitted-tree re-derivation")
        if (
            self.unit.substrate_id is not None
            and self.unit.substrate_id != self.admitted_tree.substrate_id
        ):
            raise ValueError("unit substrate does not match admitted tree")
        reference = self.unit.canonical_ref
        if isinstance(reference, TextSpan):
            start, end = reference.start, reference.end
            if end > len(self.admitted_tree.text):
                raise ValueError("unit text span exceeds admitted substrate")
            if self.canonical_text != self.admitted_tree.text[start:end]:
                raise ValueError("canonical_text does not match the admitted unit span")


def _single_token(value: str, name: str) -> str:
    phrase = _phrase_key(value, name)
    tokens = tokenize(phrase)
    if len(tokens) != 1 or tokens[0] != phrase:
        raise ValueError(f"{name} must normalize to exactly one token")
    if len(tokens[0]) > MAX_ALIAS_LENGTH:
        raise ValueError(f"{name} is too long")
    return tokens[0]


def _validate_text(text: str, policy: LexicalPolicy) -> None:
    if not isinstance(text, str):
        raise TypeError("canonical_text must be text")
    if len(text) > policy.max_text_characters:
        raise ValueError("canonical_text exceeds lexical policy bound")
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("canonical_text exceeds UTF-8 byte bound")
    if "\x00" in text:
        raise ValueError("canonical_text contains a NUL character")


def _validate_aliases(
    aliases: Mapping[str, Sequence[str]],
) -> tuple[dict[str, tuple[str, ...]], str]:
    if not isinstance(aliases, Mapping):
        raise TypeError("aliases must be a mapping of canonical terms to literal aliases")
    if len(aliases) > MAX_ALIAS_KEYS:
        raise ValueError(f"aliases must contain at most {MAX_ALIAS_KEYS} keys")
    normalized: dict[str, tuple[str, ...]] = {}
    owner: dict[str, str] = {}
    for raw_key, raw_values in aliases.items():
        if not isinstance(raw_key, str):
            raise TypeError("alias canonical terms must be strings")
        key = _phrase_key(raw_key, "alias canonical term")
        key_tokens = tokenize(key)
        if not key_tokens:
            raise ValueError("alias canonical term cannot be empty")
        if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes, bytearray)):
            raise TypeError("alias values must be sequences of literal strings")
        if len(raw_values) > MAX_ALIASES_PER_KEY:
            raise ValueError(f"a canonical term may have at most {MAX_ALIASES_PER_KEY} aliases")
        values: list[str] = []
        for raw_alias in raw_values:
            if not isinstance(raw_alias, str):
                raise TypeError("aliases must be strings")
            alias = _phrase_key(raw_alias, "alias")
            if not alias:
                # Empty aliases are explicit no-ops, useful when a scope has an
                # optional terminology field but no value yet.
                continue
            if len(alias) > MAX_ALIAS_LENGTH:
                raise ValueError(f"alias must be at most {MAX_ALIAS_LENGTH} characters")
            if not tokenize(alias):
                raise ValueError("non-empty aliases must contain a medical token")
            previous = owner.get(alias)
            if previous is not None and previous != key:
                raise ValueError("alias collision maps one literal alias to multiple terms")
            owner[alias] = key
            if alias not in values:
                values.append(alias)
        if values:
            prior = normalized.get(key, ())
            normalized[key] = tuple(sorted(set(prior).union(values)))
    payload: JsonObject = {
        "aliases": tuple(
            {"canonical": key, "values": values} for key, values in sorted(normalized.items())
        ),
        "version": ALIAS_POLICY_VERSION,
    }
    fingerprint = sha256(
        b"study-agent/lexical-alias-policy/v1\0" + canonical_json_bytes(payload)
    ).hexdigest()
    return normalized, fingerprint


def _corpus_fingerprint(items: tuple[LexicalCorpusItem, ...]) -> str:
    rows: list[JsonValue] = []
    for item in items:
        encoded = item.canonical_text.encode("utf-8")
        rows.append(
            {
                "projection": item.structural_projection.to_json(),
                "text_sha256": sha256(encoded).hexdigest(),
                "text_bytes": len(encoded),
                "unit": item.unit.to_json(),
            }
        )
    return sha256(
        b"study-agent/lexical-corpus/v1\0" + canonical_json_bytes({"items": tuple(rows)})
    ).hexdigest()


def _contains(tokens: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    if not phrase or len(phrase) > len(tokens):
        return False
    width = len(phrase)
    return any(
        tokens[offset : offset + width] == phrase
        for offset in range(len(tokens) - width + 1)
    )


def _alias_terms(
    tokens: tuple[str, ...], aliases: Mapping[str, tuple[str, ...]], cap: int
) -> tuple[str, ...]:
    values: set[str] = set()
    for canonical, literal_aliases in aliases.items():
        if _contains(tokens, tuple(tokenize(canonical))):
            values.update(literal_aliases)
    return tuple(sorted(values)[:cap])


class LexicalProjector:
    """One scope-local, corpus-IDF lexical projector.

    The pinned smooth-IDF formula is ``ln((N + 1) / (df + 1)) + 1``.  ``N``
    counts deduplicated corpus units and ``df`` counts units containing a term;
    therefore a one-document corpus remains finite and deterministic.
    """

    manifest = ProjectorManifest(LEXICAL_PROJECTOR_NAME, LEXICAL_PROJECTOR_VERSION)

    def __init__(
        self,
        entries: Sequence[LexicalCorpusItem],
        *,
        scope_id: str,
        aliases: Mapping[str, Sequence[str]] | None = None,
        policy: LexicalPolicy = DEFAULT_POLICY,
    ) -> None:
        if not isinstance(policy, LexicalPolicy):
            raise TypeError("policy must be LexicalPolicy")
        self.policy = policy
        self.scope_id = _identity(scope_id, "scope_id")
        if isinstance(entries, (str, bytes, bytearray)) or not isinstance(entries, Sequence):
            raise TypeError("entries must be a sequence of LexicalCorpusItem values")
        if len(entries) > policy.max_corpus_units:
            raise ValueError("lexical corpus exceeds max_corpus_units")
        deduped: dict[str, LexicalCorpusItem] = {}
        for item in entries:
            if not isinstance(item, LexicalCorpusItem):
                raise TypeError("entries must contain LexicalCorpusItem values")
            _validate_text(item.canonical_text, policy)
            tokens = tokenize(item.canonical_text, stop_words=policy.stop_set)
            if len(tokens) > policy.max_tokens_per_unit:
                raise ValueError("unit token count exceeds lexical policy bound")
            key = str(item.unit.unit_id)
            previous = deduped.get(key)
            if previous is not None and previous != item:
                raise ValueError("duplicate unit id has conflicting lexical corpus data")
            deduped[key] = item
        self.entries = tuple(deduped[key] for key in sorted(deduped))
        self._by_unit = MappingProxyType(
            {str(item.unit.unit_id): item for item in self.entries}
        )
        validated_aliases, self.alias_fingerprint = _validate_aliases(aliases or {})
        self.aliases = MappingProxyType(validated_aliases)
        self.corpus_fingerprint = _corpus_fingerprint(self.entries)
        frequencies: dict[str, int] = {}
        unit_tokens: dict[str, tuple[str, ...]] = {}
        for item in self.entries:
            tokens = tokenize(item.canonical_text, stop_words=policy.stop_set)
            unit_tokens[str(item.unit.unit_id)] = tokens
            for token in set(tokens):
                frequencies[token] = frequencies.get(token, 0) + 1
        self._unit_tokens = MappingProxyType(unit_tokens)
        count = len(self.entries)
        self._idf = MappingProxyType(
            {
                token: _ensure_finite(log((count + 1) / (df + 1)) + 1.0, "idf")
                for token, df in frequencies.items()
            }
        )

    def _producer_policy(self) -> Mapping[str, JsonValue]:
        return {
            "alias_fingerprint": self.alias_fingerprint,
            "corpus_fingerprint": self.corpus_fingerprint,
            "policy": self.policy.to_json(),
            "scope_id": self.scope_id,
        }

    def project(self, unit: RetrievableUnit, admitted_tree: object) -> IndexProjection:
        if not isinstance(unit, RetrievableUnit):
            raise TypeError("lexical projector requires RetrievableUnit")
        item = self._by_unit.get(str(unit.unit_id))
        if item is None:
            raise ValueError("unit is not part of this lexical corpus")
        if item.unit != unit:
            raise ValueError("unit metadata differs from lexical corpus input")
        if (
            not isinstance(admitted_tree, AdmittedDocumentTree)
            or admitted_tree != item.admitted_tree
        ):
            raise ValueError("lexical projection requires the item's admitted tree")
        tokens = self._unit_tokens[str(unit.unit_id)]
        counts = Counter(tokens)
        key_terms = tuple(
            sorted(
                counts,
                key=lambda token: (-self._idf[token], -counts[token], token),
            )[: self.policy.term_cap]
        )
        aliases = _alias_terms(tokens, self.aliases, self.policy.alias_cap)
        fingerprint = projection_input_fingerprint(
            unit,
            item.admitted_tree,
            producer_policy=self._producer_policy(),
        )
        output_sha256 = IndexProjection.derive_output_sha256(
            handle=item.structural_projection.handle,
            summary=item.structural_projection.summary,
            key_terms=key_terms,
            aliases=aliases,
            covers=item.structural_projection.covers,
            structural_context=item.structural_projection.structural_context,
        )
        return IndexProjection(
            unit.unit_id,
            fingerprint,
            item.structural_projection.handle,
            item.structural_projection.summary,
            key_terms,
            aliases,
            item.structural_projection.covers,
            item.structural_projection.structural_context,
            self.manifest.name,
            self.manifest.version,
            self.manifest.model_id,
            output_sha256,
        )

    def project_all(self) -> tuple[IndexProjection, ...]:
        return tuple(self.project(item.unit, item.admitted_tree) for item in self.entries)


def project_lexical(
    entries: Sequence[LexicalCorpusItem],
    *,
    scope_id: str,
    aliases: Mapping[str, Sequence[str]] | None = None,
    policy: LexicalPolicy = DEFAULT_POLICY,
) -> tuple[IndexProjection, ...]:
    """Project a bounded scope corpus in stable unit-id order."""
    return LexicalProjector(
        entries, scope_id=scope_id, aliases=aliases, policy=policy
    ).project_all()


__all__ = [
    "ALIAS_POLICY_VERSION",
    "CAP_POLICY_VERSION",
    "DEFAULT_POLICY",
    "IDF_VERSION",
    "LEXICAL_PROJECTOR_NAME",
    "LEXICAL_PROJECTOR_VERSION",
    "MAX_ALIAS_KEYS",
    "MAX_ALIAS_LENGTH",
    "MAX_CORPUS_UNITS",
    "MAX_TERM_CAP",
    "MAX_TEXT_CHARACTERS",
    "NORMALIZATION_VERSION",
    "STOP_POLICY_VERSION",
    "TOKENIZATION_VERSION",
    "LexicalCorpusItem",
    "LexicalPolicy",
    "LexicalProjector",
    "project_lexical",
    "tokenize",
]
