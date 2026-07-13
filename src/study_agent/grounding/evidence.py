from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from study_agent.domain import ChunkId, Citation, RevisionId, SourceId
from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.ports import (
    EvidenceStatus,
    RetrievalEvidence,
    RetrievalEvidenceSet,
    retrieval_read_set_fingerprint,
)


class GroundingContractError(ValueError):
    """Untrusted grounding JSON violates the canonical contract."""


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    handle: str
    evidence: RetrievalEvidence


@dataclass(frozen=True, slots=True)
class EvidenceEnvelope:
    status: EvidenceStatus
    items: tuple[EvidenceItem, ...]
    query_fingerprint: str
    strategy_id: str
    strategy_version: str
    index_version: str
    read_set_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        _fingerprint(self.query_fingerprint, "evidence.query_fingerprint")
        _text(self.strategy_id, "evidence.strategy_id")
        _text(self.strategy_version, "evidence.strategy_version")
        _text(self.index_version, "evidence.index_version")
        _fingerprint(self.read_set_fingerprint, "evidence.read_set_fingerprint")
        handles = tuple(item.handle for item in self.items)
        if len(set(handles)) != len(handles):
            raise GroundingContractError("evidence handles must be unique")
        if self.status is EvidenceStatus.INSUFFICIENT and self.items:
            raise GroundingContractError("insufficient evidence envelope must be empty")
        if self.status is not EvidenceStatus.INSUFFICIENT and not self.items:
            raise GroundingContractError("non-insufficient evidence envelope must not be empty")
        if self.read_set_fingerprint != retrieval_read_set_fingerprint(
            tuple(item.evidence for item in self.items)
        ):
            raise GroundingContractError(
                "read_set_fingerprint must commit to ordered evidence items"
            )

    @classmethod
    def from_retrieval(cls, evidence_set: RetrievalEvidenceSet) -> EvidenceEnvelope:
        return cls(
            evidence_set.status,
            tuple(
                EvidenceItem(evidence_handle(item.chunk.chunk_id), item)
                for item in evidence_set.evidence
            ),
            evidence_set.query_fingerprint,
            evidence_set.strategy_id,
            evidence_set.strategy_version,
            evidence_set.index_version,
            evidence_set.read_set_fingerprint,
        )

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "status": self.status.value,
                "query_fingerprint": self.query_fingerprint,
                "strategy_id": self.strategy_id,
                "strategy_version": self.strategy_version,
                "index_version": self.index_version,
                "read_set_fingerprint": self.read_set_fingerprint,
                "items": tuple(_item_json(item) for item in self.items),
            }
        )

    @classmethod
    def from_json(cls, value: JsonValue) -> EvidenceEnvelope:
        root = _strict_object(
            value,
            {
                "status",
                "query_fingerprint",
                "strategy_id",
                "strategy_version",
                "index_version",
                "read_set_fingerprint",
                "items",
            },
            "evidence",
        )
        status_raw = root["status"]
        if not isinstance(status_raw, str):
            raise GroundingContractError("evidence.status must be a string")
        try:
            status = EvidenceStatus(status_raw)
        except ValueError as error:
            raise GroundingContractError("evidence.status has an unsupported value") from error
        fingerprint = _text(root["query_fingerprint"], "evidence.query_fingerprint")
        strategy_id = _text(root["strategy_id"], "evidence.strategy_id")
        strategy_version = _text(root["strategy_version"], "evidence.strategy_version")
        index_version = _text(root["index_version"], "evidence.index_version")
        read_set_fingerprint = _text(
            root["read_set_fingerprint"], "evidence.read_set_fingerprint"
        )
        items_raw = _array(root["items"], "evidence.items")
        items = tuple(_parse_item(item, index) for index, item in enumerate(items_raw))
        envelope = cls(
            status,
            items,
            fingerprint,
            strategy_id,
            strategy_version,
            index_version,
            read_set_fingerprint,
        )
        for item in envelope.items:
            if item.handle != evidence_handle(item.evidence.chunk.chunk_id):
                raise GroundingContractError(
                    "evidence handle does not match trusted chunk identity"
                )
        return envelope

    def by_handle(self) -> dict[str, RetrievalEvidence]:
        return {item.handle: item.evidence for item in self.items}


def evidence_handle(chunk_id: ChunkId) -> str:
    digest = sha256(f"grounded-answer-evidence-v1\0{chunk_id}".encode()).hexdigest()
    return f"ev_{digest}"


def _item_json(item: EvidenceItem) -> JsonObject:
    evidence = item.evidence
    citation = evidence.citation
    return freeze_object(
        {
            "evidence_id": item.handle,
            "text": evidence.text,
            "score": evidence.score,
            "citation": {
                "source_id": str(citation.source_id),
                "revision_id": str(citation.revision_id),
                "chunk_id": str(citation.chunk_id),
                "start_offset": citation.start_offset,
                "end_offset": citation.end_offset,
                "locator": citation.locator,
                "quoted_snippet": citation.quoted_snippet,
            },
        }
    )


def _parse_item(value: JsonValue, index: int) -> EvidenceItem:
    path = f"evidence.items[{index}]"
    item = _strict_object(value, {"evidence_id", "text", "score", "citation"}, path)
    citation_raw = _strict_object(
        item["citation"],
        {
            "source_id",
            "revision_id",
            "chunk_id",
            "start_offset",
            "end_offset",
            "locator",
            "quoted_snippet",
        },
        f"{path}.citation",
    )
    source_id = SourceId(_text(citation_raw["source_id"], f"{path}.citation.source_id"))
    revision_id = RevisionId(
        _text(citation_raw["revision_id"], f"{path}.citation.revision_id")
    )
    chunk_id = ChunkId(_text(citation_raw["chunk_id"], f"{path}.citation.chunk_id"))
    text = _text(item["text"], f"{path}.text")
    quoted = _text(citation_raw["quoted_snippet"], f"{path}.citation.quoted_snippet")
    if quoted != text:
        raise GroundingContractError("evidence quote must equal evidence text")
    citation = Citation(
        source_id,
        revision_id,
        chunk_id,
        _integer(citation_raw["start_offset"], f"{path}.citation.start_offset"),
        _integer(citation_raw["end_offset"], f"{path}.citation.end_offset"),
        _text(citation_raw["locator"], f"{path}.citation.locator"),
        quoted,
    )
    from study_agent.domain import SourceChunk

    chunk = SourceChunk(
        chunk_id,
        source_id,
        revision_id,
        citation.start_offset,
        citation.end_offset,
        (),
        index,
        sha256(text.encode()).hexdigest(),
        "evidence-envelope-v1",
    )
    score = item["score"]
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise GroundingContractError(f"{path}.score must be a number")
    return EvidenceItem(
        _text(item["evidence_id"], f"{path}.evidence_id"),
        RetrievalEvidence(chunk, citation, text, float(score)),
    )


def _strict_object(value: JsonValue, fields: set[str], path: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise GroundingContractError(f"{path} must be an object")
    if set(value) != fields:
        raise GroundingContractError(f"{path} must contain exactly {sorted(fields)}")
    return value


def _array(value: JsonValue, path: str) -> tuple[JsonValue, ...]:
    if not isinstance(value, tuple):
        raise GroundingContractError(f"{path} must be an array")
    return value


def _text(value: JsonValue, path: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise GroundingContractError(f"{path} must be non-empty text")
    return value


def _integer(value: JsonValue, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise GroundingContractError(f"{path} must be an integer")
    return value


def _fingerprint(value: JsonValue, path: str) -> str:
    text = _text(value, path)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise GroundingContractError(f"{path} must be a lowercase SHA-256 fingerprint")
    return text
