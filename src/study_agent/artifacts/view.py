"""Projection-backed artifact lifecycle reader."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from study_agent.domain import (
    ArtifactBatchId,
    ArtifactDecision,
    ArtifactId,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    CourseId,
    EventId,
    RunId,
    SessionId,
    StudyArtifactKind,
)
from study_agent.domain._validation import JsonValue
from study_agent.ports import CourseNotFoundError
from study_agent.state import Projection

from .content import StudyArtifactEnvelope
from .contracts import (
    ArtifactBatchRecord,
    ArtifactDecisionRecord,
    ArtifactProposalOrigin,
    ArtifactRevisionRecord,
    ArtifactSnapshot,
    ServiceDecisionPolicyReceipt,
)
from .identity import artifact_provenance_from_bytes

type ProjectionLoader = Callable[[CourseId], Projection]


class ProjectionArtifactView:
    def __init__(self, load_projection: ProjectionLoader) -> None:
        self._load_projection = load_projection

    def get(self, course_id: CourseId) -> ArtifactSnapshot:
        projection = self._load_projection(course_id)
        if projection.course_id != course_id:
            raise ValueError("projection loader returned another course")
        if "course" not in projection.state:
            raise CourseNotFoundError(course_id)
        raw = projection.state.get("study_artifacts", {})
        if not isinstance(raw, Mapping) or (
            raw and set(raw) != {"artifacts", "revisions", "batches", "decisions", "commands"}
        ):
            raise ValueError("artifact projection fields are corrupt")
        revisions_raw = _mapping(raw.get("revisions", {}), "revisions")
        batches_raw = _mapping(raw.get("batches", {}), "batches")
        decisions_raw = raw.get("decisions", ())
        if not isinstance(decisions_raw, tuple):
            raise ValueError("artifact decisions projection is corrupt")
        revisions = tuple(
            sorted(
                (self._revision(key, value) for key, value in revisions_raw.items()),
                key=lambda item: (item.proposed_at, str(item.id)),
            )
        )
        batches = tuple(
            sorted(
                (self._batch(course_id, key, value) for key, value in batches_raw.items()),
                key=lambda item: (item.recorded_at, str(item.id)),
            )
        )
        decisions = tuple(self._decision(value) for value in decisions_raw)
        return ArtifactSnapshot(course_id, projection.sequence, batches, revisions, decisions)

    def command_fingerprint(self, course_id: CourseId, event_id: EventId) -> str | None:
        projection = self._load_projection(course_id)
        raw = projection.state.get("study_artifacts", {})
        commands = _mapping(_mapping(raw, "study_artifacts").get("commands", {}), "commands")
        value = commands.get(str(event_id))
        if value is None:
            return None
        entry = _mapping(value, "command")
        if set(entry) != {"command_fingerprint", "result_id"}:
            raise ValueError("artifact command entry is corrupt")
        fingerprint = _text(entry.get("command_fingerprint"), "command_fingerprint")
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise ValueError("artifact command fingerprint is corrupt")
        return fingerprint

    @staticmethod
    def _revision(key: object, raw: JsonValue) -> ArtifactRevisionRecord:
        value = _mapping(raw, "revision")
        if not isinstance(key, str) or value.get("revision_id") != key:
            raise ValueError("artifact revision identity is corrupt")
        content = StudyArtifactEnvelope.from_bytes(_text(value.get("content"), "content").encode())
        provenance = artifact_provenance_from_bytes(
            _text(value.get("provenance"), "provenance").encode()
        )
        return ArtifactRevisionRecord(
            ArtifactRevisionId(key),
            ArtifactId(_text(value.get("artifact_id"), "artifact_id")),
            ArtifactBatchId(_text(value.get("batch_id"), "batch_id")),
            _integer(value.get("ordinal"), "ordinal"),
            StudyArtifactKind(_text(value.get("kind"), "kind")),
            ArtifactRevisionStatus(_text(value.get("status"), "status")),
            content,
            provenance,
            _optional_revision_id(value.get("prior_revision_id")),
            _optional_artifact_id(value.get("parent_artifact_id")),
            _timestamp(value.get("proposed_at"), "proposed_at"),
            _optional_timestamp(value.get("decided_at"), "decided_at"),
        )

    @staticmethod
    def _batch(course_id: CourseId, key: object, raw: JsonValue) -> ArtifactBatchRecord:
        value = _mapping(raw, "batch")
        ids = value.get("revision_ids")
        if not isinstance(key, str) or value.get("batch_id") != key or not isinstance(ids, tuple):
            raise ValueError("artifact batch identity is corrupt")
        run = value.get("run_id")
        return ArtifactBatchRecord(
            ArtifactBatchId(key),
            course_id,
            SessionId(_text(value.get("session_id"), "session_id")),
            ArtifactProposalOrigin(_text(value.get("origin"), "origin")),
            tuple(ArtifactRevisionId(_text(item, "revision_id")) for item in ids),
            RunId(run) if isinstance(run, str) else None,
            _timestamp(value.get("recorded_at"), "recorded_at"),
        )

    @staticmethod
    def _decision(raw: JsonValue) -> ArtifactDecisionRecord:
        value = _mapping(raw, "decision")
        receipt_raw = value.get("policy_receipt")
        receipt = None
        if isinstance(receipt_raw, Mapping):
            supersedes = receipt_raw.get("supersedes_revision_id")
            receipt = ServiceDecisionPolicyReceipt(
                _text(receipt_raw.get("request_id"), "request_id"),
                ArtifactDecision(_text(receipt_raw.get("decision"), "decision")),
                ArtifactRevisionId(supersedes) if isinstance(supersedes, str) else None,
                _text(receipt_raw.get("policy_id"), "policy_id"),
                _text(receipt_raw.get("policy_version"), "policy_version"),
                _text(receipt_raw.get("policy_fingerprint"), "policy_fingerprint"),
                _text(receipt_raw.get("result_fingerprint"), "result_fingerprint"),
            )
        return ArtifactDecisionRecord(
            ArtifactRevisionId(_text(value.get("revision_id"), "revision_id")),
            ArtifactDecision(_text(value.get("decision"), "decision")),
            _optional_revision_id(value.get("supersedes_revision_id")),
            _timestamp(value.get("decided_at"), "decided_at"),
            receipt,
        )


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"projected {name} must be an object")
    return value


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"projected {name} must be text")
    return value


def _integer(value: JsonValue | None, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"projected {name} must be an integer")
    return value


def _timestamp(value: JsonValue | None, name: str) -> datetime:
    result = datetime.fromisoformat(_text(value, name).replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"projected {name} must be timezone-aware")
    return result


def _optional_timestamp(value: JsonValue | None, name: str) -> datetime | None:
    return None if value is None else _timestamp(value, name)


def _optional_revision_id(value: JsonValue | None) -> ArtifactRevisionId | None:
    if value is None:
        return None
    return ArtifactRevisionId(_text(value, "optional revision identity"))


def _optional_artifact_id(value: JsonValue | None) -> ArtifactId | None:
    if value is None:
        return None
    return ArtifactId(_text(value, "optional artifact identity"))


__all__ = ["ProjectionArtifactView"]
