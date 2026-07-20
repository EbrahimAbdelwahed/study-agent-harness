"""Deterministic artifact identity and strict revision provenance."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Any, cast

from study_agent.domain._validation import JsonObject, JsonValue, freeze_object, require_text
from study_agent.domain.artifact import ArtifactReadDependency, StudyArtifactKind, require_sha256
from study_agent.domain.events import PrincipalKind
from study_agent.domain.identifiers import (
    ArtifactBatchId,
    ArtifactId,
    ArtifactRevisionId,
    ChunkId,
    CourseId,
    InteractionId,
    RevisionId,
    RunId,
    SessionId,
    SourceId,
)
from study_agent.domain.provenance import (
    ModelProvenance,
    ModelUsageProvenance,
    PromptProvenance,
    RetrievalProvenance,
    SourceCommitment,
    ValidatorProvenance,
    VersionPins,
)
from study_agent.pedagogy import (
    PedagogicalProfileId,
    PedagogicalProfileRef,
    ProfileSelectionBasis,
    ProfileSelectionMode,
    ProfileSelectionReceipt,
    ProfileSelectorKind,
)


def artifact_batch_id_for(
    course_id: CourseId,
    session_id: SessionId,
    run_id: RunId,
    retry_identity: str,
) -> ArtifactBatchId:
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("artifact batch requires typed course and session ids")
    if not isinstance(run_id, RunId):
        raise TypeError("generated artifact batch requires RunId")
    require_text(retry_identity, "retry_identity")
    payload = f"artifact-batch@1\0{course_id}\0{session_id}\0{run_id}\0{retry_identity}".encode()
    return ArtifactBatchId(f"artifact-batch-sha256:{sha256(payload).hexdigest()}")


def human_authored_artifact_batch_id_for(
    course_id: CourseId,
    session_id: SessionId,
    interaction_id: InteractionId,
    retry_identity: str,
) -> ArtifactBatchId:
    """Derive a HUMAN-authored batch without inventing a verified run identity."""
    require_text(retry_identity, "retry_identity")
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("human artifact batch requires typed course and session ids")
    if not isinstance(interaction_id, InteractionId):
        raise TypeError("human artifact batch requires InteractionId")
    payload = (
        f"human-artifact-batch@1\0{course_id}\0{session_id}\0{interaction_id}\0{retry_identity}"
    ).encode()
    return ArtifactBatchId(f"artifact-batch-sha256:{sha256(payload).hexdigest()}")


def artifact_id_for(batch_id: ArtifactBatchId, ordinal: int) -> ArtifactId:
    if type(ordinal) is not int or ordinal < 0:
        raise ValueError("artifact ordinal must be non-negative")
    payload = f"artifact@1\0{batch_id}\0{ordinal}".encode()
    return ArtifactId(f"artifact-sha256:{sha256(payload).hexdigest()}")


def artifact_revision_id_for(
    artifact_id: ArtifactId,
    kind: StudyArtifactKind,
    content_bytes: bytes,
    provenance_bytes: bytes,
    prior_revision_id: ArtifactRevisionId | None = None,
) -> ArtifactRevisionId:
    if not content_bytes or not provenance_bytes:
        raise ValueError("revision identity requires content and provenance bytes")
    # Decode through the exact codecs before assigning canonical identity. This is
    # the aggregate boundary at which otherwise-valid leaves are proven coherent.
    from study_agent.artifacts.content import (
        ExamBlueprintContent,
        HybridFlashcardContent,
        MorphologyFlashcardContent,
        StudyArtifactEnvelope,
    )

    content = StudyArtifactEnvelope.from_bytes(content_bytes)
    provenance = artifact_provenance_from_bytes(provenance_bytes)
    if content.kind is not kind:
        raise ValueError("artifact revision kind does not match canonical content")
    if provenance.prior_revision_id != prior_revision_id:
        raise ValueError("artifact revision prior identity does not match provenance")
    commitment_count = len(provenance.source_commitments)
    referenced_indices: tuple[int, ...] = ()
    if isinstance(content.content, (HybridFlashcardContent, MorphologyFlashcardContent)):
        referenced_indices = content.content.source_commitment_indices
    elif isinstance(content.content, ExamBlueprintContent):
        referenced_indices = tuple(
            index
            for observation in (
                *content.content.observed_topics,
                *content.content.observed_formats,
            )
            for index in observation.source_commitment_indices
        )
    if any(index >= commitment_count for index in referenced_indices):
        raise ValueError("artifact content references a missing source commitment")
    if isinstance(provenance, GeneratedArtifactProvenance):
        expected_output_fingerprint = sha256(content_bytes).hexdigest()
        if provenance.output_fingerprint != expected_output_fingerprint:
            raise ValueError("generated provenance output fingerprint does not commit to content")
        if isinstance(content.content, (HybridFlashcardContent, MorphologyFlashcardContent)):
            if provenance.profile_selection is None:
                raise ValueError("generated flashcard provenance requires profile selection")
            if content.content.profile != provenance.profile_selection.profile:
                raise ValueError(
                    "flashcard content profile does not match generated profile selection"
                )
        elif provenance.profile_selection is not None:
            raise ValueError("non-flashcard provenance cannot contain flashcard profile selection")
    payload = b"\0".join(
        (
            b"artifact-revision@1",
            str(artifact_id).encode(),
            kind.value.encode(),
            content_bytes,
            provenance_bytes,
            str(prior_revision_id).encode() if prior_revision_id else b"",
        )
    )
    return ArtifactRevisionId(f"artifact-revision-sha256:{sha256(payload).hexdigest()}")


class ArtifactProvenanceOrigin(StrEnum):
    GENERATED = "generated"
    HUMAN_AUTHORED = "human_authored"


@dataclass(frozen=True, slots=True)
class GeneratedArtifactProvenance:
    source_commitments: tuple[SourceCommitment, ...]
    prompt: PromptProvenance
    model: ModelProvenance | None
    retrieval: RetrievalProvenance
    validators: tuple[ValidatorProvenance, ...]
    pins: VersionPins
    profile_selection: ProfileSelectionReceipt | None
    read_dependencies: tuple[ArtifactReadDependency, ...]
    output_fingerprint: str
    run_id: RunId
    prior_revision_id: ArtifactRevisionId | None = None
    origin: ArtifactProvenanceOrigin = field(default=ArtifactProvenanceOrigin.GENERATED, init=False)

    def __post_init__(self) -> None:
        commitments, dependencies = _validate_common(
            self.source_commitments, self.read_dependencies
        )
        object.__setattr__(self, "source_commitments", commitments)
        object.__setattr__(self, "read_dependencies", dependencies)
        validators = tuple(self.validators)
        if not all(isinstance(item, ValidatorProvenance) for item in validators):
            raise TypeError("validators must use ValidatorProvenance")
        if not validators or any(not item.passed for item in validators):
            raise ValueError("generated provenance requires passed validators")
        keys = tuple((item.validator_id, item.version) for item in validators)
        if len(set(keys)) != len(keys):
            raise ValueError("validators must be ordered and unique by identity")
        object.__setattr__(self, "validators", validators)
        require_sha256(self.output_fingerprint, "output_fingerprint")
        if self.profile_selection is not None and not isinstance(
            self.profile_selection, ProfileSelectionReceipt
        ):
            raise TypeError("profile_selection must use ProfileSelectionReceipt or be absent")
        if self.model is None:
            if self.pins.model_adapter is not None:
                raise ValueError("model adapter pin must be absent without a model call")
            if self.prompt.composition_fingerprint is not None or self.prompt.layer_fingerprints:
                raise ValueError("composed model prompt proof requires a model call")
        else:
            expected = f"{self.model.adapter_id}@{self.model.adapter_version}"
            if self.pins.model_adapter != expected:
                raise ValueError("model receipt must match its adapter version pin")
            if self.model.run_id != self.run_id:
                raise ValueError("model receipt and verified run identity differ")


@dataclass(frozen=True, slots=True)
class HumanAuthoredArtifactProvenance:
    authority: PrincipalKind
    interaction_id: InteractionId
    source_commitments: tuple[SourceCommitment, ...]
    read_dependencies: tuple[ArtifactReadDependency, ...]
    prior_revision_id: ArtifactRevisionId | None = None
    origin: ArtifactProvenanceOrigin = field(
        default=ArtifactProvenanceOrigin.HUMAN_AUTHORED, init=False
    )

    def __post_init__(self) -> None:
        if self.authority is not PrincipalKind.HUMAN:
            raise ValueError("human-authored provenance requires HUMAN authority")
        if not isinstance(self.interaction_id, InteractionId):
            raise TypeError("human-authored provenance requires InteractionId")
        commitments, dependencies = _validate_common(
            self.source_commitments, self.read_dependencies
        )
        object.__setattr__(self, "source_commitments", commitments)
        object.__setattr__(self, "read_dependencies", dependencies)


type ArtifactProvenance = GeneratedArtifactProvenance | HumanAuthoredArtifactProvenance


def artifact_provenance_to_json(value: ArtifactProvenance) -> JsonObject:
    common: dict[str, JsonValue] = {
        "origin": value.origin.value,
        "source_commitments": tuple(_source_json(item) for item in value.source_commitments),
        "read_dependencies": tuple(_dependency_json(item) for item in value.read_dependencies),
        "prior_revision_id": str(value.prior_revision_id) if value.prior_revision_id else None,
    }
    if isinstance(value, HumanAuthoredArtifactProvenance):
        common.update(
            authority=value.authority.value,
            interaction_id=str(value.interaction_id),
        )
    else:
        common.update(
            prompt=_prompt_json(value.prompt),
            model=_model_json(value.model) if value.model else None,
            retrieval=_retrieval_json(value.retrieval),
            validators=tuple(_validator_json(item) for item in value.validators),
            pins=_pins_json(value.pins),
            profile_selection=(
                _selection_json(value.profile_selection) if value.profile_selection else None
            ),
            output_fingerprint=value.output_fingerprint,
            run_id=str(value.run_id),
        )
    return freeze_object(common)


def artifact_provenance_to_bytes(value: ArtifactProvenance) -> bytes:
    return _canonical_bytes(artifact_provenance_to_json(value))


def artifact_provenance_from_json(value: Mapping[str, JsonValue]) -> ArtifactProvenance:
    _reject_secret_fields(value)
    origin = _string(value, "origin")
    common_fields = {"origin", "source_commitments", "read_dependencies", "prior_revision_id"}
    commitments = _source_items(value, "source_commitments")
    dependencies = _dependency_items(value, "read_dependencies")
    prior_raw = value.get("prior_revision_id")
    if prior_raw is not None and not isinstance(prior_raw, str):
        raise ValueError("prior_revision_id has invalid type")
    prior = ArtifactRevisionId(prior_raw) if prior_raw else None
    if origin == ArtifactProvenanceOrigin.HUMAN_AUTHORED:
        _exact(value, common_fields | {"authority", "interaction_id"}, "human provenance")
        return HumanAuthoredArtifactProvenance(
            authority=PrincipalKind(_string(value, "authority")),
            interaction_id=InteractionId(_string(value, "interaction_id")),
            source_commitments=commitments,
            read_dependencies=dependencies,
            prior_revision_id=prior,
        )
    if origin != ArtifactProvenanceOrigin.GENERATED:
        raise ValueError("unknown artifact provenance origin")
    _exact(
        value,
        common_fields
        | {
            "prompt",
            "model",
            "retrieval",
            "validators",
            "pins",
            "profile_selection",
            "output_fingerprint",
            "run_id",
        },
        "generated provenance",
    )
    model_raw = value.get("model")
    if model_raw is not None and not isinstance(model_raw, Mapping):
        raise ValueError("model must be an object or null")
    return GeneratedArtifactProvenance(
        source_commitments=commitments,
        prompt=_prompt(_mapping(value, "prompt")),
        model=_model(model_raw) if isinstance(model_raw, Mapping) else None,
        retrieval=_retrieval(_mapping(value, "retrieval")),
        validators=_validators(value, "validators"),
        pins=_pins(_mapping(value, "pins")),
        profile_selection=_optional_selection(value, "profile_selection"),
        read_dependencies=dependencies,
        output_fingerprint=_string(value, "output_fingerprint"),
        run_id=RunId(_string(value, "run_id")),
        prior_revision_id=prior,
    )


def artifact_provenance_from_bytes(data: bytes) -> ArtifactProvenance:
    decoded: Any = json.loads(data)
    if not isinstance(decoded, dict):
        raise ValueError("artifact provenance must be a JSON object")
    result = artifact_provenance_from_json(cast(dict[str, JsonValue], decoded))
    if artifact_provenance_to_bytes(result) != data:
        raise ValueError("artifact provenance bytes are not canonical")
    return result


def _validate_common(
    commitments: tuple[SourceCommitment, ...], dependencies: tuple[ArtifactReadDependency, ...]
) -> tuple[tuple[SourceCommitment, ...], tuple[ArtifactReadDependency, ...]]:
    frozen_commitments = tuple(commitments)
    frozen_dependencies = tuple(dependencies)
    if not all(isinstance(item, SourceCommitment) for item in frozen_commitments):
        raise TypeError("source commitments must use SourceCommitment")
    if not all(isinstance(item, ArtifactReadDependency) for item in frozen_dependencies):
        raise TypeError("read dependencies must use ArtifactReadDependency")
    if not frozen_commitments or len(set(frozen_commitments)) != len(frozen_commitments):
        raise ValueError("source commitments must be non-empty, ordered, and unique")
    keys = tuple((item.kind, item.id, item.version) for item in frozen_dependencies)
    if not frozen_dependencies or len(set(keys)) != len(keys):
        raise ValueError("read dependencies must be non-empty, ordered, and unique")
    available = set(keys)
    for item in frozen_commitments:
        if ("source_revision", str(item.source_id), str(item.revision_id)) not in available:
            raise ValueError(
                "every source commitment requires its exact source revision dependency"
            )
    return frozen_commitments, frozen_dependencies


def _optional_selection(value: Mapping[str, JsonValue], key: str) -> ProfileSelectionReceipt | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, Mapping):
        raise ValueError(f"{key} must be an object or null")
    return _selection(item)


def _source_json(value: SourceCommitment) -> dict[str, JsonValue]:
    return {
        "source_id": str(value.source_id),
        "revision_id": str(value.revision_id),
        "chunk_id": str(value.chunk_id),
        "start_offset": value.start_offset,
        "end_offset": value.end_offset,
    }


def _dependency_json(value: ArtifactReadDependency) -> dict[str, JsonValue]:
    return {"kind": value.kind, "id": value.id, "version": value.version}


def _prompt_json(value: PromptProvenance) -> dict[str, JsonValue]:
    return {
        "prompt_id": value.prompt_id,
        "version": value.version,
        "composition_fingerprint": value.composition_fingerprint,
        "layer_fingerprints": value.layer_fingerprints,
    }


def _model_json(value: ModelProvenance) -> dict[str, JsonValue]:
    usage: JsonValue = (
        None
        if value.usage is None
        else {"input_tokens": value.usage.input_tokens, "output_tokens": value.usage.output_tokens}
    )
    return {
        "adapter_id": value.adapter_id,
        "adapter_version": value.adapter_version,
        "model_id": value.model_id,
        "response_id": value.response_id,
        "run_id": str(value.run_id),
        "usage": usage,
    }


def _retrieval_json(value: RetrievalProvenance) -> dict[str, JsonValue]:
    return {
        "strategy_id": value.strategy_id,
        "strategy_version": value.strategy_version,
        "query_fingerprint": value.query_fingerprint,
        "index_version": value.index_version,
        "read_set_fingerprint": value.read_set_fingerprint,
    }


def _validator_json(value: ValidatorProvenance) -> dict[str, JsonValue]:
    return {
        "validator_id": value.validator_id,
        "version": value.version,
        "passed": value.passed,
        "disposition": value.disposition,
        "result_fingerprint": value.result_fingerprint,
    }


def _pins_json(value: VersionPins) -> dict[str, JsonValue]:
    return {
        "skill": value.skill,
        "playbook": value.playbook,
        "prompt": value.prompt,
        "model_adapter": value.model_adapter,
        "state_contract": value.state_contract,
        "tool_behavior": value.tool_behavior,
    }


def _selection_json(value: ProfileSelectionReceipt) -> dict[str, JsonValue]:
    return {
        "profile": {"id": value.profile.id.value, "version": value.profile.version},
        "mode": value.mode.value,
        "selector_kind": value.selector_kind.value,
        "selector_authority": value.selector_authority.value,
        "basis": {
            "interaction_id": str(value.basis.interaction_id)
            if value.basis.interaction_id
            else None,
            "source_revision_id": str(value.basis.source_revision_id)
            if value.basis.source_revision_id
            else None,
        },
    }


def _source_items(value: Mapping[str, JsonValue], key: str) -> tuple[SourceCommitment, ...]:
    return tuple(
        SourceCommitment(
            SourceId(_string(item, "source_id")),
            RevisionId(_string(item, "revision_id")),
            ChunkId(_string(item, "chunk_id")),
            _integer(item, "start_offset"),
            _integer(item, "end_offset"),
        )
        for item in _objects(
            value, key, {"source_id", "revision_id", "chunk_id", "start_offset", "end_offset"}
        )
    )


def _dependency_items(
    value: Mapping[str, JsonValue], key: str
) -> tuple[ArtifactReadDependency, ...]:
    return tuple(
        ArtifactReadDependency(_string(item, "kind"), _string(item, "id"), _string(item, "version"))
        for item in _objects(value, key, {"kind", "id", "version"})
    )


def _prompt(value: Mapping[str, JsonValue]) -> PromptProvenance:
    _exact(
        value,
        {"prompt_id", "version", "composition_fingerprint", "layer_fingerprints"},
        "prompt provenance",
    )
    composition = value.get("composition_fingerprint")
    if composition is not None and not isinstance(composition, str):
        raise ValueError("composition_fingerprint has invalid type")
    return PromptProvenance(
        _string(value, "prompt_id"),
        _string(value, "version"),
        composition,
        _strings(value, "layer_fingerprints"),
    )


def _model(value: Mapping[str, JsonValue]) -> ModelProvenance:
    _exact(
        value,
        {"adapter_id", "adapter_version", "model_id", "response_id", "run_id", "usage"},
        "model provenance",
    )
    raw_usage = value.get("usage")
    usage = None
    if raw_usage is not None:
        if not isinstance(raw_usage, Mapping):
            raise ValueError("model usage must be an object or null")
        _exact(raw_usage, {"input_tokens", "output_tokens"}, "model usage")
        usage = ModelUsageProvenance(
            _integer(raw_usage, "input_tokens"), _integer(raw_usage, "output_tokens")
        )
    response_id = value.get("response_id")
    if response_id is not None and not isinstance(response_id, str):
        raise ValueError("response_id must be a string or null")
    return ModelProvenance(
        _string(value, "adapter_id"),
        _string(value, "adapter_version"),
        _string(value, "model_id"),
        response_id,
        RunId(_string(value, "run_id")),
        usage,
    )


def _retrieval(value: Mapping[str, JsonValue]) -> RetrievalProvenance:
    _exact(
        value,
        {
            "strategy_id",
            "strategy_version",
            "query_fingerprint",
            "index_version",
            "read_set_fingerprint",
        },
        "retrieval provenance",
    )
    return RetrievalProvenance(
        _string(value, "strategy_id"),
        _string(value, "strategy_version"),
        _string(value, "query_fingerprint"),
        _string(value, "index_version"),
        _string(value, "read_set_fingerprint"),
    )


def _validators(value: Mapping[str, JsonValue], key: str) -> tuple[ValidatorProvenance, ...]:
    return tuple(
        ValidatorProvenance(
            _string(item, "validator_id"),
            _string(item, "version"),
            _boolean(item, "passed"),
            _string(item, "disposition"),
            _string(item, "result_fingerprint"),
        )
        for item in _objects(
            value, key, {"validator_id", "version", "passed", "disposition", "result_fingerprint"}
        )
    )


def _pins(value: Mapping[str, JsonValue]) -> VersionPins:
    _exact(
        value,
        {"skill", "playbook", "prompt", "model_adapter", "state_contract", "tool_behavior"},
        "version pins",
    )
    model_adapter = value.get("model_adapter")
    if model_adapter is not None and not isinstance(model_adapter, str):
        raise ValueError("model_adapter has invalid type")
    return VersionPins(
        _string(value, "skill"),
        _string(value, "playbook"),
        _string(value, "prompt"),
        model_adapter,
        _string(value, "state_contract"),
        _string(value, "tool_behavior"),
    )


def _selection(value: Mapping[str, JsonValue]) -> ProfileSelectionReceipt:
    _exact(
        value,
        {"profile", "mode", "selector_kind", "selector_authority", "basis"},
        "profile selection",
    )
    profile = _mapping(value, "profile")
    basis = _mapping(value, "basis")
    _exact(profile, {"id", "version"}, "selected profile")
    _exact(basis, {"interaction_id", "source_revision_id"}, "selection basis")
    interaction = basis.get("interaction_id")
    revision = basis.get("source_revision_id")
    if interaction is not None and not isinstance(interaction, str):
        raise ValueError("interaction_id has invalid type")
    if revision is not None and not isinstance(revision, str):
        raise ValueError("source_revision_id has invalid type")
    return ProfileSelectionReceipt(
        PedagogicalProfileRef(
            PedagogicalProfileId(_string(profile, "id")), _integer(profile, "version")
        ),
        ProfileSelectionMode(_string(value, "mode")),
        ProfileSelectorKind(_string(value, "selector_kind")),
        PrincipalKind(_string(value, "selector_authority")),
        ProfileSelectionBasis(
            InteractionId(interaction) if interaction else None,
            RevisionId(revision) if revision else None,
        ),
    )


def _objects(
    value: Mapping[str, JsonValue], key: str, fields: set[str]
) -> tuple[Mapping[str, JsonValue], ...]:
    raw = value.get(key)
    if not isinstance(raw, (tuple, list)):
        raise ValueError(f"{key} must be an array")
    result = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError(f"{key} items must be objects")
        _exact(item, fields, f"{key} item")
        result.append(item)
    return tuple(result)


def _mapping(value: Mapping[str, JsonValue], key: str) -> Mapping[str, JsonValue]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise ValueError(f"{key} must be an object")
    return item


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        raise ValueError(f"{key} must be a string")
    return item


def _integer(value: Mapping[str, JsonValue], key: str) -> int:
    item = value.get(key)
    if type(item) is not int:
        raise ValueError(f"{key} must be an integer")
    return item


def _boolean(value: Mapping[str, JsonValue], key: str) -> bool:
    item = value.get(key)
    if type(item) is not bool:
        raise ValueError(f"{key} must be a boolean")
    return item


def _strings(value: Mapping[str, JsonValue], key: str) -> tuple[str, ...]:
    raw = value.get(key)
    if not isinstance(raw, (tuple, list)) or any(not isinstance(item, str) for item in raw):
        raise ValueError(f"{key} must be an array of strings")
    return tuple(cast(str, item) for item in raw)


def _exact(value: Mapping[str, JsonValue], fields: set[str], name: str) -> None:
    if set(value) != fields:
        raise ValueError(f"{name} fields must be exactly {sorted(fields)}")


def _reject_secret_fields(value: JsonValue, path: str = "provenance") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = key.lower().replace("-", "_")
            if normalized in {
                "api_key",
                "credentials",
                "password",
                "secret",
                "access_token",
                "policy_internals",
            }:
                raise ValueError(f"{path}.{key} is forbidden")
            _reject_secret_fields(item, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _reject_secret_fields(item, f"{path}[{index}]")


def _canonical_bytes(value: JsonObject) -> bytes:
    def plain(item: JsonValue) -> object:
        if isinstance(item, Mapping):
            return {key: plain(child) for key, child in item.items()}
        if isinstance(item, tuple):
            return [plain(child) for child in item]
        return item

    return json.dumps(
        plain(value), ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode()


__all__ = [
    "ArtifactProvenance",
    "ArtifactProvenanceOrigin",
    "GeneratedArtifactProvenance",
    "HumanAuthoredArtifactProvenance",
    "artifact_batch_id_for",
    "artifact_id_for",
    "artifact_provenance_from_bytes",
    "artifact_provenance_from_json",
    "artifact_provenance_to_bytes",
    "artifact_provenance_to_json",
    "artifact_revision_id_for",
    "human_authored_artifact_batch_id_for",
]
