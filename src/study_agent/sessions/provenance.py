"""Assemble answer provenance from verified engine receipts only."""

from __future__ import annotations

from collections.abc import Mapping

from study_agent.domain._validation import JsonValue
from study_agent.domain.grounding import AnswerSegment, AnswerStatus, GroundedAnswer, SegmentKind
from study_agent.domain.identifiers import ChunkId, RevisionId, SourceId
from study_agent.domain.provenance import (
    AnswerProvenance,
    ClaimOrigin,
    ModelProvenance,
    ModelUsageProvenance,
    PromptProvenance,
    RetrievalProvenance,
    SourceCommitment,
    ValidatorProvenance,
    VersionPins,
)
from study_agent.domain.source import Citation
from study_agent.grounding import EvidenceEnvelope
from study_agent.playbooks import PlaybookRunStatus, StepTraceStatus, VerifiedRunRecord
from study_agent.ports import SourceContentPort


class ProvenanceAssemblyError(ValueError):
    """A verified run does not contain a complete trusted answer receipt."""


def assemble_grounded_answer(
    run: VerifiedRunRecord,
    content: SourceContentPort,
) -> GroundedAnswer:
    """Build a canonical answer without trusting identity claims from model output."""
    _validate_run_inputs(run)
    envelope = EvidenceEnvelope.from_json(_required_output(run, "evidence"))
    validators = _validators(run)
    retrieval = RetrievalProvenance(
        envelope.strategy_id,
        envelope.strategy_version,
        envelope.query_fingerprint,
        envelope.index_version,
        envelope.read_set_fingerprint,
    )
    pin_set = _pins(run, has_model=run.status is PlaybookRunStatus.COMPLETED)

    if run.status is PlaybookRunStatus.TERMINATED:
        if run.termination is None or not run.termination.passed:
            raise ProvenanceAssemblyError("only successful deterministic termination may persist")
        result = _strict_object(
            run.termination.result,
            {"status", "segments", "unsupported_information_note"},
            "termination",
        )
        if _text(result.get("status"), "termination.status") != "insufficient_evidence":
            raise ProvenanceAssemblyError("only insufficient-evidence termination may persist")
        if _array(result.get("segments"), "termination.segments"):
            raise ProvenanceAssemblyError("insufficient termination cannot contain claims")
        if envelope.items:
            raise ProvenanceAssemblyError("insufficient termination must have no evidence")
        if any(trace.step_kind == "model" for trace in run.traces):
            raise ProvenanceAssemblyError("insufficient termination must not contain a model trace")
        prompt = PromptProvenance(run.pins.prompt.id, str(run.pins.prompt.version))
        provenance = AnswerProvenance(
            (), prompt, None, retrieval, validators, pin_set, run.run_id
        )
        note = _text(
            result.get("unsupported_information_note"),
            "termination.unsupported_information_note",
        )
        return GroundedAnswer(AnswerStatus.INSUFFICIENT_EVIDENCE, (), note, provenance)

    raw_answer = _strict_object(
        _required_output(run, "validated_answer"),
        {"status", "segments", "unsupported_information_note"},
        "validated_answer",
    )
    status = _answer_status(raw_answer.get("status"))
    if status not in {AnswerStatus.ANSWERED, AnswerStatus.CONFLICTING_EVIDENCE}:
        raise ProvenanceAssemblyError("completed runs must contain a grounded answer status")
    segments = _segments(raw_answer.get("segments"), content, envelope)
    prompt, model = _model_receipt(run)
    commitments = tuple(
        dict.fromkeys(
            SourceCommitment(
                citation.source_id,
                citation.revision_id,
                citation.chunk_id,
                citation.start_offset,
                citation.end_offset,
            )
            for segment in segments
            for citation in segment.citations
        )
    )
    provenance = AnswerProvenance(
        commitments,
        prompt,
        model,
        retrieval,
        validators,
        pin_set,
        run.run_id,
    )
    note_raw = raw_answer.get("unsupported_information_note")
    completion_note = (
        None if note_raw is None else _text(note_raw, "unsupported_information_note")
    )
    return GroundedAnswer(status, segments, completion_note, provenance)


def _validate_run_inputs(run: VerifiedRunRecord) -> None:
    if set(run.inputs) != {"course_id", "session_id", "question"}:
        raise ProvenanceAssemblyError("grounded run inputs are not exact")
    for key in ("course_id", "session_id", "question"):
        _text(run.inputs.get(key), f"inputs.{key}")
    if (
        run.pins.skill.id != "grounded_answer"
        or str(run.pins.skill.version) != "1.0.0"
        or run.pins.playbook.id != "grounded_answer_flow"
        or str(run.pins.playbook.version) != "1.0.0"
        or run.pins.prompt.id != "grounded_answer.v1"
        or str(run.pins.prompt.version) != "1.0.0"
    ):
        raise ProvenanceAssemblyError("verified run is not the pinned grounded-answer v1 flow")
    tool_pins = tuple(
        (item.tool_name, str(item.version)) for item in run.pins.tool_behaviors
    )
    if tool_pins != (
        ("session.get_context", "1.0.0"),
        ("source.search", "1.0.0"),
    ):
        raise ProvenanceAssemblyError("verified run tool-behavior pins are not canonical")


def _required_output(run: VerifiedRunRecord, key: str) -> JsonValue:
    try:
        return run.outputs[key]
    except KeyError as error:
        raise ProvenanceAssemblyError(f"verified run is missing {key}") from error


def _pins(run: VerifiedRunRecord, *, has_model: bool) -> VersionPins:
    pins = run.pins
    tool_pin = ",".join(
        f"{item.tool_name}@{item.version}" for item in pins.tool_behaviors
    )
    return VersionPins(
        f"{pins.skill.id}@{pins.skill.version}",
        f"{pins.playbook.id}@{pins.playbook.version}",
        f"{pins.prompt.id}@{pins.prompt.version}",
        f"{pins.model_adapter.id}@{pins.model_adapter.version}" if has_model else None,
        f"{pins.state_contract.id}@{pins.state_contract.version}",
        tool_pin,
    )


def _validators(run: VerifiedRunRecord) -> tuple[ValidatorProvenance, ...]:
    result: list[ValidatorProvenance] = []
    for trace in run.traces:
        if trace.status is not StepTraceStatus.COMPLETED:
            continue
        receipts: list[Mapping[str, JsonValue]] = []
        direct = trace.details.get("validator")
        if isinstance(direct, Mapping):
            receipts.append(direct)
        fallback = trace.details.get("fallback_validators", ())
        if not isinstance(fallback, tuple):
            raise ProvenanceAssemblyError("fallback validator receipt is not an array")
        for value in fallback:
            if not isinstance(value, Mapping):
                raise ProvenanceAssemblyError("fallback validator receipt is invalid")
            receipts.append(value)
        for receipt in receipts:
            validator = ValidatorProvenance(
                _text(receipt.get("validator_id"), "validator_id"),
                _text(receipt.get("validator_version"), "validator_version"),
                _boolean(receipt.get("passed"), "validator.passed"),
                _text(receipt.get("disposition"), "validator.disposition"),
                _fingerprint(receipt.get("result_fingerprint"), "validator.result_fingerprint"),
            )
            key = (validator.validator_id, validator.version)
            matching_index = next(
                (
                    index
                    for index, item in enumerate(result)
                    if (item.validator_id, item.version) == key
                ),
                None,
            )
            if matching_index is None:
                result.append(validator)
            else:
                # Portable structured-output fallback runs the schema form of the
                # integrity validator before its later, evidence-aware execution.
                # The final canonical receipt supersedes that preliminary receipt.
                result[matching_index] = validator
    if not result or any(not item.passed for item in result):
        raise ProvenanceAssemblyError("answer requires successful validator receipts")
    return tuple(result)


def _model_receipt(
    run: VerifiedRunRecord,
) -> tuple[PromptProvenance, ModelProvenance]:
    model_traces = tuple(
        trace
        for trace in run.traces
        if trace.step_kind == "model" and trace.status is StepTraceStatus.COMPLETED
    )
    if len(model_traces) != 1:
        raise ProvenanceAssemblyError("grounded answer requires exactly one model invocation")
    details = model_traces[0].details
    invocation = _strict_object(
        details.get("model_invocation"),
        {"adapter_id", "adapter_version", "model_id", "response_id"},
        "model_invocation",
    )
    prompt_raw = _strict_object(
        details.get("prompt"), {"id", "version", "fingerprint", "layers"}, "prompt"
    )
    layers_raw = _array(prompt_raw.get("layers"), "prompt.layers")
    layer_fingerprints: list[str] = []
    for index, raw in enumerate(layers_raw):
        layer = _strict_object(
            raw,
            {"id", "version", "kind", "input_fingerprint"},
            f"prompt.layers[{index}]",
        )
        layer_fingerprints.append(
            _fingerprint(
                layer.get("input_fingerprint"),
                f"prompt.layers[{index}].input_fingerprint",
            )
        )
    if prompt_raw["id"] != run.pins.prompt.id or prompt_raw["version"] != str(
        run.pins.prompt.version
    ):
        raise ProvenanceAssemblyError("prompt trace differs from prompt pin")
    prompt = PromptProvenance(
        _text(prompt_raw["id"], "prompt.id"),
        _text(prompt_raw["version"], "prompt.version"),
        _fingerprint(prompt_raw.get("fingerprint"), "prompt.fingerprint"),
        tuple(layer_fingerprints),
    )
    usage_raw = details.get("model_usage")
    usage = None
    if usage_raw is not None:
        usage_obj = _strict_object(
            usage_raw, {"input_tokens", "output_tokens"}, "model_usage"
        )
        usage = ModelUsageProvenance(
            _integer(usage_obj.get("input_tokens"), "model_usage.input_tokens"),
            _integer(usage_obj.get("output_tokens"), "model_usage.output_tokens"),
        )
    response_id = invocation.get("response_id")
    if response_id is None:
        raise ProvenanceAssemblyError("successful model invocation has no response identity")
    model = ModelProvenance(
        _text(invocation.get("adapter_id"), "model_invocation.adapter_id"),
        _text(invocation.get("adapter_version"), "model_invocation.adapter_version"),
        _text(invocation.get("model_id"), "model_invocation.model_id"),
        _text(response_id, "model_invocation.response_id"),
        run.run_id,
        usage,
    )
    return prompt, model


def _segments(
    value: JsonValue | None,
    content: SourceContentPort,
    envelope: EvidenceEnvelope,
) -> tuple[AnswerSegment, ...]:
    raw_segments = _array(value, "segments")
    trusted = {item.evidence.citation for item in envelope.items}
    result: list[AnswerSegment] = []
    for index, raw in enumerate(raw_segments):
        segment = _strict_object(
            raw,
            {"kind", "text", "citations"},
            f"segments[{index}]",
        )
        try:
            kind = SegmentKind(_text(segment.get("kind"), f"segments[{index}].kind"))
        except ValueError as error:
            raise ProvenanceAssemblyError("answer segment kind is unsupported") from error
        citations = tuple(
            _citation(item, f"segments[{index}].citations[{citation_index}]")
            for citation_index, item in enumerate(
                _array(segment.get("citations"), f"segments[{index}].citations")
            )
        )
        for citation in citations:
            if citation not in trusted:
                raise ProvenanceAssemblyError("citation is outside the trusted retrieval read set")
            resolved = content.resolve(citation)
            if resolved.citation != citation or resolved.text != citation.quoted_snippet:
                raise ProvenanceAssemblyError("citation no longer resolves to canonical content")
        result.append(
            AnswerSegment(
                kind,
                _text(segment.get("text"), f"segments[{index}].text"),
                citations,
                ClaimOrigin.INFERRED,
            )
        )
    return tuple(result)


def _citation(value: JsonValue, name: str) -> Citation:
    raw = _strict_object(
        value,
        {
            "source_id",
            "revision_id",
            "chunk_id",
            "start_offset",
            "end_offset",
            "locator",
            "quoted_snippet",
        },
        name,
    )
    return Citation(
        SourceId(_text(raw.get("source_id"), f"{name}.source_id")),
        RevisionId(_text(raw.get("revision_id"), f"{name}.revision_id")),
        ChunkId(_text(raw.get("chunk_id"), f"{name}.chunk_id")),
        _integer(raw.get("start_offset"), f"{name}.start_offset"),
        _integer(raw.get("end_offset"), f"{name}.end_offset"),
        _text(raw.get("locator"), f"{name}.locator"),
        _text(raw.get("quoted_snippet"), f"{name}.quoted_snippet"),
    )


def _answer_status(value: JsonValue | None) -> AnswerStatus:
    try:
        return AnswerStatus(_text(value, "answer.status"))
    except ValueError as error:
        raise ProvenanceAssemblyError("answer status is unsupported") from error


def _object(value: JsonValue, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ProvenanceAssemblyError(f"{name} must be an object")
    return value


def _strict_object(
    value: JsonValue | None, fields: set[str], name: str
) -> Mapping[str, JsonValue]:
    raw = _object(value, name)
    if set(raw) != fields:
        raise ProvenanceAssemblyError(f"{name} fields are invalid")
    return raw


def _array(value: JsonValue | None, name: str) -> tuple[JsonValue, ...]:
    if not isinstance(value, tuple):
        raise ProvenanceAssemblyError(f"{name} must be an array")
    return value


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProvenanceAssemblyError(f"{name} must be non-empty trimmed text")
    return value


def _fingerprint(value: JsonValue | None, name: str) -> str:
    result = _text(value, name)
    if len(result) != 64 or any(char not in "0123456789abcdef" for char in result):
        raise ProvenanceAssemblyError(f"{name} must be a SHA-256 fingerprint")
    return result


def _boolean(value: JsonValue | None, name: str) -> bool:
    if not isinstance(value, bool):
        raise ProvenanceAssemblyError(f"{name} must be a boolean")
    return value


def _integer(value: JsonValue | None, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProvenanceAssemblyError(f"{name} must be a non-negative integer")
    return value
