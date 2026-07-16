"""Trusted profile dispatcher for the public flashcard proposal capability."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import NoReturn

from study_agent.artifacts.candidates import FlashcardCandidateBatch
from study_agent.domain import ExecutionContext, PrincipalKind, RunId
from study_agent.domain._validation import JsonObject, JsonValue, freeze_object
from study_agent.pedagogy import (
    HYBRID_MACRO_DETAIL_V1,
    MORPHOLOGY_FIRST_ANATOMY_V1,
    PEDAGOGICAL_PROFILE_CATALOG,
    PedagogicalProfileRef,
    ProfileSelectionBasis,
    ProfileSelectionMode,
    ProfileSelectionReceipt,
    ProfileSelectorKind,
)
from study_agent.playbooks import (
    EngineErrorCode,
    InspectedRunRecord,
    playbook_definition_fingerprint,
)

from .bindings import PROFILE_SELECTION_RECEIPT_INPUT, ProfiledCapabilityBinding
from .builtin import PROPOSE_FLASHCARDS_MANIFEST
from .contracts import (
    CapabilityContinuation,
    CapabilityGatewayError,
    CapabilityGatewayErrorCode,
    CapabilityManifest,
    CapabilityOutcome,
    CompletedCapabilityOutcome,
    FailedCapabilityOutcome,
)
from .gateway import StudyCapabilityGateway, _run_id

_MAX_CONTINUATION_BYTES = 16 * 1024


class FlashcardCapabilityDispatcher:
    """Route one public capability to exactly two trusted profile bindings."""

    def __init__(
        self,
        *,
        bindings: tuple[ProfiledCapabilityBinding, ...],
        gateway: StudyCapabilityGateway,
    ) -> None:
        values = tuple(bindings)
        if len(values) != 2 or not all(
            isinstance(item, ProfiledCapabilityBinding) for item in values
        ):
            raise ValueError("flashcard dispatcher requires exactly two profiled bindings")
        if not isinstance(gateway, StudyCapabilityGateway):
            raise TypeError("flashcard dispatcher gateway must be StudyCapabilityGateway")
        if any(item.manifest != PROPOSE_FLASHCARDS_MANIFEST for item in values):
            raise ValueError("flashcard bindings must share the public manifest")
        profiles = tuple(item.profile for item in values)
        if set(profiles) != {
            HYBRID_MACRO_DETAIL_V1,
            MORPHOLOGY_FIRST_ANATOMY_V1,
        }:
            raise ValueError("flashcard bindings must cover the exact closed profile catalog")
        skill_ids = tuple((item.skill.id, item.skill.version) for item in values)
        playbook_ids = tuple((item.playbook.id, item.playbook.version) for item in values)
        fingerprints = tuple(playbook_definition_fingerprint(item.playbook) for item in values)
        if len(set(skill_ids)) != 2:
            raise ValueError("profile skill identities must be pairwise distinct")
        if len(set(playbook_ids)) != 2:
            raise ValueError("profile playbook identities must be pairwise distinct")
        if len(set(fingerprints)) != 2:
            raise ValueError("profile playbook definition fingerprints must be distinct")
        self._bindings = values
        self._by_profile = {item.profile: item for item in values}
        self._gateway = gateway

    def discover(self) -> tuple[CapabilityManifest, ...]:
        return (PROPOSE_FLASHCARDS_MANIFEST,)

    async def start(
        self,
        inputs: JsonObject,
        context: ExecutionContext,
        selection: ProfileSelectionReceipt | None = None,
    ) -> CapabilityOutcome:
        public_inputs = _validate_public_inputs(inputs)
        authority, retry = self._gateway._authorize(
            self._bindings[0], context
        )
        requested = selection if selection is not None else _default_receipt(context)
        if not isinstance(requested, ProfileSelectionReceipt):
            raise TypeError("flashcard profile selection must be ProfileSelectionReceipt")
        PEDAGOGICAL_PROFILE_CATALOG.resolve(requested.profile)
        run_id = _run_id(self._bindings[0], authority, retry)
        owner = self._locate_owner(run_id)
        if owner is not None:
            persisted = _persisted_receipt(owner[1])
            bound = self._binding_for(persisted.profile)
            if bound is not owner[0]:
                _incompatible("persisted profile receipt does not own its playbook")
            if persisted != requested:
                _conflict("idempotency identity was reused with another profile selection")
            execution_inputs = _execution_inputs(public_inputs, persisted)
            outcome = await self._gateway._start_bound(
                bound, public_inputs, execution_inputs, context
            )
            return _verified_candidate_outcome(outcome)

        bound = self._binding_for(requested.profile)
        outcome = await self._gateway._start_bound(
            bound,
            public_inputs,
            _execution_inputs(public_inputs, requested),
            context,
        )
        return _verified_candidate_outcome(outcome)

    async def resume(
        self,
        continuation: CapabilityContinuation,
        response: JsonValue,
        context: ExecutionContext,
    ) -> CapabilityOutcome:
        if not isinstance(continuation, CapabilityContinuation):
            raise TypeError("continuation must be CapabilityContinuation")
        self._gateway._authorize(self._bindings[0], context)
        owner = self._locate_owner(continuation.run_id)
        if owner is None:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.NOT_FOUND,
                "flashcard capability checkpoint was not found",
            )
        persisted = _persisted_receipt(owner[1])
        bound = self._binding_for(persisted.profile)
        if bound is not owner[0]:
            _incompatible("persisted profile receipt does not own its playbook")
        outcome = await self._gateway._resume_bound(
            bound, continuation, response, context
        )
        return _verified_candidate_outcome(outcome)

    def _binding_for(self, profile: PedagogicalProfileRef) -> ProfiledCapabilityBinding:
        try:
            return self._by_profile[profile]
        except KeyError as error:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.INVALID_REQUEST,
                "profile selection is not in the closed catalog",
            ) from error

    def _locate_owner(
        self, run_id: RunId
    ) -> tuple[ProfiledCapabilityBinding, InspectedRunRecord] | None:
        matches: list[tuple[ProfiledCapabilityBinding, InspectedRunRecord]] = []
        failures: list[EngineErrorCode] = []
        for binding in self._bindings:
            inspected, failure = self._gateway._probe_bound(binding, run_id)
            if inspected is not None:
                matches.append((binding, inspected))
            elif failure is not None:
                failures.append(failure)
        if len(matches) > 1:
            _incompatible("multiple profile definitions own one flashcard run")
        if matches:
            return matches[0]
        if failures and all(
            item is EngineErrorCode.CHECKPOINT_NOT_FOUND for item in failures
        ):
            return None
        _incompatible("flashcard checkpoint could not be matched to a closed definition")


def _default_receipt(context: ExecutionContext) -> ProfileSelectionReceipt:
    if not isinstance(context, ExecutionContext):
        raise TypeError("flashcard context must be ExecutionContext")
    if context.principal_kind not in {PrincipalKind.HUMAN, PrincipalKind.SERVICE}:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.UNAUTHORIZED,
            "profile selection authority must be a trusted human or service",
        )
    return ProfileSelectionReceipt(
        profile=HYBRID_MACRO_DETAIL_V1,
        mode=ProfileSelectionMode.DEFAULT,
        selector_kind=ProfileSelectorKind.HOST,
        selector_authority=context.principal_kind,
        basis=ProfileSelectionBasis(),
    )


def _validate_public_inputs(inputs: JsonObject) -> JsonObject:
    try:
        frozen = freeze_object(inputs)
        properties = PROPOSE_FLASHCARDS_MANIFEST.input_schema["properties"]
        if not isinstance(properties, Mapping) or set(frozen) != set(properties):
            raise ValueError("public flashcard input fields are not exact")
        query = frozen["query"]
        scope = frozen["scope"]
        language = frozen["language"]
        ceiling = frozen["candidate_ceiling"]
        summary = frozen["continuation_summary_json"]
        _bounded_input_text(query, "query", 4000)
        if scope is not None:
            _bounded_input_text(scope, "scope", 1000)
        _bounded_input_text(language, "language", 64)
        if type(ceiling) is not int or not 1 <= ceiling <= 24:
            raise ValueError("candidate_ceiling must be an integer from 1 through 24")
        if summary is not None:
            _validate_continuation_summary(summary)
        return frozen
    except (KeyError, TypeError, ValueError) as error:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INVALID_REQUEST,
            "flashcard inputs violate the public task envelope",
        ) from error


def _bounded_input_text(value: JsonValue, name: str, maximum: int) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be trimmed non-empty text")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")


def _validate_continuation_summary(value: JsonValue) -> None:
    if not isinstance(value, str):
        raise ValueError("continuation summary must be JSON text or null")
    encoded = value.encode("utf-8")
    if len(encoded) > _MAX_CONTINUATION_BYTES:
        raise ValueError("continuation summary exceeds 16 KiB")
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("continuation summary must encode one object")
    canonical = json.dumps(
        decoded,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if canonical != value:
        raise ValueError("continuation summary must be canonical compact JSON")


def _execution_inputs(
    public_inputs: JsonObject, receipt: ProfileSelectionReceipt
) -> JsonObject:
    return freeze_object(
        {
            **public_inputs,
            PROFILE_SELECTION_RECEIPT_INPUT: receipt.to_bytes().decode("utf-8"),
        }
    )


def _persisted_receipt(inspected: InspectedRunRecord) -> ProfileSelectionReceipt:
    value = inspected.inputs.get(PROFILE_SELECTION_RECEIPT_INPUT)
    if not isinstance(value, str):
        _incompatible("persisted flashcard run has no canonical profile receipt")
    try:
        return ProfileSelectionReceipt.from_bytes(value.encode("utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "persisted profile receipt is invalid",
        ) from error


def _verified_candidate_outcome(outcome: CapabilityOutcome) -> CapabilityOutcome:
    if not isinstance(outcome, CompletedCapabilityOutcome):
        return outcome
    try:
        if not isinstance(outcome.output, Mapping):
            raise ValueError("candidate batch output must be an object")
        batch = FlashcardCandidateBatch.from_json(outcome.output)
        ceiling = outcome.run.inputs.get("candidate_ceiling")
        if type(ceiling) is not int or len(batch.candidates) > ceiling:
            raise ValueError("candidate batch exceeds the requested ceiling")
    except (TypeError, ValueError):
        return FailedCapabilityOutcome(
            outcome.run.run_id,
            "verified flashcard output violates the candidate codec",
        )
    return CompletedCapabilityOutcome(outcome.run, batch.to_json())


def _conflict(message: str) -> NoReturn:
    raise CapabilityGatewayError(CapabilityGatewayErrorCode.CONFLICT, message)


def _incompatible(message: str) -> NoReturn:
    raise CapabilityGatewayError(CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME, message)


__all__ = ["FlashcardCapabilityDispatcher"]
